"""SQLite storage and private data-directory handling.

The store deliberately contains no host or model integration.  Its public
surface is small so callers can make lifecycle decisions in ``service`` while
all current projections and their append-only events share a transaction.
"""

from __future__ import annotations

from collections.abc import Iterator
import contextlib
import ctypes
from ctypes import wintypes
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sqlite3
from typing import Any


SCHEMA_VERSION = 1
DATABASE_NAME = "advocate.sqlite3"
FINISHED_RUN_STATE = "finished"
PENDING_EVIDENCE_PREFIX = ".pending-"
PENDING_EVIDENCE_SUFFIX = ".evidence"


class AdvocateError(Exception):
    """An error suitable for a stable CLI response."""

    exit_code = 2
    error_type = "request_error"


class RequestError(AdvocateError):
    """The requested operation or JSON payload is invalid."""


class ConflictError(RequestError):
    error_type = "conflict"


class SetupError(AdvocateError):
    error_type = "setup_error"


class StoreUnavailableError(AdvocateError):
    exit_code = 3
    error_type = "store_unavailable"


class ContentionError(AdvocateError):
    exit_code = 4
    error_type = "contention"


def json_text(value: Any) -> str:
    """Stable serialization used for idempotency comparisons."""

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def json_value(value: str) -> Any:
    return json.loads(value)


def resolve_data_dir(value: str | Path | None = None) -> Path:
    """Choose the configured private directory without creating it."""

    raw = str(value) if value is not None else os.environ.get("AGENT_ADVOCATE_DATA_DIR")
    if raw is not None:
        if not raw.strip():
            raise RequestError("private data directory must not be empty")
        return Path(os.path.abspath(Path(raw).expanduser()))
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(os.path.abspath(Path(base) / "agent-advocate"))
        return Path(os.path.abspath(Path.home() / "AppData" / "Local" / "agent-advocate"))
    base = os.environ.get("XDG_DATA_HOME")
    if base:
        return Path(os.path.abspath(Path(base) / "agent-advocate"))
    return Path(os.path.abspath(Path.home() / ".local" / "share" / "agent-advocate"))


def reject_git_worktree(path: Path) -> None:
    """Reject a directory whose resolved location sits under a Git worktree.

    A normal worktree has a ``.git`` directory and a linked worktree has a
    ``.git`` file, so existence is sufficient and does not require invoking
    Git.  ``resolve`` handles a data-directory symlink into a worktree.
    """

    try:
        requested = Path(os.path.abspath(path.expanduser()))
        resolved = requested.resolve(strict=False)
        for candidate in (requested, resolved):
            current = candidate
            while True:
                if (current / ".git").exists():
                    raise SetupError(
                        f"refusing private data directory inside a Git worktree: {resolved}"
                    )
                parent = current.parent
                if parent == current:
                    break
                current = parent
    except OSError as error:
        raise SetupError(f"cannot inspect private data directory {path}: {error}") from error


class Store:
    """The version-1 SQLite store.

    Connections have a five-second lock wait.  Write methods use an immediate
    transaction and do only projection/event writes while it is held.
    """

    def __init__(self, data_dir: Path) -> None:
        self.requested_data_dir = Path(os.path.abspath(data_dir.expanduser()))
        self.data_dir = self.requested_data_dir.resolve(strict=False)
        self.database_path = self.data_dir / DATABASE_NAME
        self.evidence_dir = self.data_dir / "evidence"
        self.logs_dir = self.data_dir / "logs"

    def initialize(self) -> None:
        reject_git_worktree(self.requested_data_dir)
        try:
            _make_private_directory(self.data_dir)
        except OSError as error:
            raise SetupError(f"cannot create private data directory {self.data_dir}: {error}") from error
        try:
            conn = self._connect()
            started = False
            try:
                conn.execute("BEGIN IMMEDIATE")
                started = True
                version = int(conn.execute("PRAGMA user_version").fetchone()[0])
                table_count = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'"
                    ).fetchone()[0]
                )
                if version == 0 and table_count == 0:
                    self._create_schema(conn)
                elif version != SCHEMA_VERSION or not _has_version_one_schema(conn):
                    raise StoreUnavailableError(
                        "unsupported store schema; preserve this directory and initialize a different --data-dir"
                    )
                conn.execute("COMMIT")
                started = False
            except sqlite3.DatabaseError as error:
                _rollback_if_needed(conn, started)
                raise _database_error(
                    error,
                    "store is corrupt or unavailable; preserve this directory and initialize a different --data-dir",
                ) from error
            finally:
                conn.close()
            _restrict_private_file(self.database_path)
        except OSError as error:
            raise SetupError(f"cannot secure private store files: {error}") from error
        try:
            _make_private_directory(self.evidence_dir)
            _make_private_directory(self.logs_dir)
        except OSError as error:
            raise SetupError(f"cannot create private store directories: {error}") from error

    def require_ready(self) -> None:
        reject_git_worktree(self.requested_data_dir)
        if not self.database_path.is_file():
            raise SetupError(
                f"private store is not initialized at {self.data_dir}; run 'agent-advocate --data-dir PATH init'"
            )
        try:
            conn = self._connect()
            try:
                version = int(conn.execute("PRAGMA user_version").fetchone()[0])
                table_count = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'"
                    ).fetchone()[0]
                )
                if version == 0 and table_count == 0:
                    raise SetupError(
                        "private store initialization is incomplete; run 'agent-advocate "
                        "--data-dir PATH init' again for this empty directory"
                    )
                if version != SCHEMA_VERSION or not _has_version_one_schema(conn):
                    raise StoreUnavailableError(
                        "unsupported store schema; preserve this directory and initialize a different --data-dir"
                    )
            finally:
                conn.close()
        except sqlite3.DatabaseError as error:
            raise _database_error(
                error,
                "store is corrupt or unavailable; preserve this directory and initialize a different --data-dir",
            ) from error

    def _connect(self) -> sqlite3.Connection:
        conn: sqlite3.Connection | None = None
        try:
            conn = sqlite3.connect(
                str(self.database_path), timeout=5.0, isolation_level=None
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA busy_timeout = 5000")
            return conn
        except sqlite3.DatabaseError as error:
            if conn is not None:
                with contextlib.suppress(sqlite3.Error):
                    conn.close()
            raise _database_error(error, f"cannot open private store: {error}") from error

    def _create_schema(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """CREATE TABLE runs (
                run_id TEXT PRIMARY KEY,
                project_path TEXT NOT NULL,
                spec_json TEXT NOT NULL,
                models_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                state TEXT NOT NULL,
                last_checkpoint_at TEXT NOT NULL,
                next_check_at TEXT NOT NULL,
                deadline_at TEXT,
                outcome TEXT,
                summary TEXT,
                finish_json TEXT
            )"""
        )
        conn.execute(
            """CREATE TABLE events (
                event_id TEXT PRIMARY KEY,
                run_id TEXT REFERENCES runs(run_id) ON DELETE RESTRICT,
                recorded_at TEXT NOT NULL,
                kind TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )"""
        )
        conn.execute("CREATE INDEX events_run_recorded ON events(run_id, recorded_at)")
        conn.execute(
            """CREATE TABLE observations (
                observation_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE RESTRICT,
                request_json TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                data_json TEXT NOT NULL
            )"""
        )
        conn.execute("CREATE INDEX observations_run_recorded ON observations(run_id, recorded_at)")
        conn.execute(
            """CREATE TABLE patterns (
                pattern_key TEXT PRIMARY KEY,
                data_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )"""
        )
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    @contextlib.contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        self.require_ready()
        conn = self._connect()
        started = False
        try:
            conn.execute("BEGIN IMMEDIATE")
            started = True
            yield conn
            conn.execute("COMMIT")
        except sqlite3.OperationalError as error:
            _rollback_if_needed(conn, started)
            raise _database_error(error, f"private store write failed: {error}") from error
        except sqlite3.DatabaseError as error:
            _rollback_if_needed(conn, started)
            raise _database_error(error, f"private store write failed: {error}") from error
        except BaseException:
            _rollback_if_needed(conn, started)
            raise
        finally:
            conn.close()

    @contextlib.contextmanager
    def read_connection(self) -> Iterator[sqlite3.Connection]:
        self.require_ready()
        conn = self._connect()
        try:
            yield conn
        except sqlite3.DatabaseError as error:
            raise _database_error(error, f"private store read failed: {error}") from error
        finally:
            conn.close()

    def run(self, run_id: str, conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
        if conn is None:
            with self.read_connection() as read_conn:
                return self.run(run_id, read_conn)
        row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return _run_from_row(row) if row else None

    def insert_run(self, spec: dict[str, Any], now: str, event_id: str) -> tuple[dict[str, Any], bool]:
        """Insert a run, or return its current projection for an exact retry."""

        with self.transaction() as conn:
            existing = self.run(spec["run_id"], conn)
            if existing:
                existing_spec = conn.execute(
                    "SELECT spec_json FROM runs WHERE run_id = ?", (spec["run_id"],)
                ).fetchone()[0]
                if existing_spec == json_text(spec):
                    return existing, True
                raise ConflictError("run_id already exists with a different RunSpec")
            conn.execute(
                """INSERT INTO runs
                   (run_id, project_path, spec_json, models_json, created_at, state,
                    last_checkpoint_at, next_check_at, deadline_at)
                   VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?)""",
                (
                    spec["run_id"],
                    spec["project_path"],
                    json_text(spec),
                    json_text(spec["models"]),
                    now,
                    now,
                    spec["next_check_at"],
                    spec["deadline_at"],
                ),
            )
            payload = {"run_spec": spec}
            conn.execute(
                "INSERT INTO events (event_id, run_id, recorded_at, kind, payload_json) VALUES (?, ?, ?, 'start', ?)",
                (event_id, spec["run_id"], now, json_text(payload)),
            )
            current = self.run(spec["run_id"], conn)
            if current is None:
                raise StoreUnavailableError("new run projection is missing")
            return current, False

    def checkpoint(
        self, run_id: str, event_id: str, payload: dict[str, Any], now: str | None = None
    ) -> tuple[dict[str, Any], bool]:
        """Record one checkpoint, preserving an exact event retry.

        Validation and projection selection happen after the write lock is held,
        so an older writer cannot replace a newer timer expectation.
        """

        with self.transaction() as conn:
            existing_event = conn.execute(
                "SELECT run_id, kind, payload_json FROM events WHERE event_id = ?", (event_id,)
            ).fetchone()
            if existing_event:
                if (
                    existing_event["run_id"] == run_id
                    and existing_event["kind"] == "checkpoint"
                    and existing_event["payload_json"] == json_text(payload)
                ):
                    current = self.run(run_id, conn)
                    if current is None:
                        raise StoreUnavailableError("checkpoint event has no current run")
                    return current, True
                raise ConflictError("event_id already exists with a different event payload")
            current = self.run(run_id, conn)
            if current is None:
                raise RequestError("unknown run_id")
            if current["state"] == FINISHED_RUN_STATE:
                raise RequestError("cannot checkpoint a finished run")
            timestamp = now or utc_now()
            _validate_checkpoint_expectations(payload, current, timestamp)
            deadline_at = current["deadline_at"]
            if payload["deadline_change"] != "preserve":
                deadline_at = payload["deadline_change"]
            if _timestamp_not_before(timestamp, current["last_checkpoint_at"]):
                conn.execute(
                    """UPDATE runs SET state = ?, last_checkpoint_at = ?, next_check_at = ?,
                       deadline_at = ? WHERE run_id = ?""",
                    (payload["state"], timestamp, payload["next_check_at"], deadline_at, run_id),
                )
            conn.execute(
                "INSERT INTO events (event_id, run_id, recorded_at, kind, payload_json) VALUES (?, ?, ?, 'checkpoint', ?)",
                (event_id, run_id, timestamp, json_text(payload)),
            )
            updated = self.run(run_id, conn)
            if updated is None:
                raise StoreUnavailableError("checkpoint run projection is missing")
            return updated, False

    def insert_observation(
        self,
        run_id: str,
        observation_id: str,
        request: dict[str, Any],
        data: dict[str, Any],
        now: str,
        event_id: str,
        pending_copies: list[tuple[Path, str]] | None = None,
    ) -> tuple[dict[str, Any], bool]:
        """Insert an observation or return its exact, same-run replay.

        Prepared evidence is atomically published only by the writer that wins
        the observation record, and is discarded for retries or failed writes.
        """

        prepared = pending_copies or []
        published: list[Path] = []
        result: tuple[dict[str, Any], bool]
        try:
            with self.transaction() as conn:
                existing = conn.execute(
                    "SELECT run_id, request_json, data_json FROM observations WHERE observation_id = ?",
                    (observation_id,),
                ).fetchone()
                if existing:
                    if (
                        existing["run_id"] == run_id
                        and existing["request_json"] == json_text(request)
                    ):
                        result = (json_value(existing["data_json"]), True)
                    else:
                        raise ConflictError(
                            "observation_id already exists with a different run or observation payload"
                        )
                else:
                    current = self.run(run_id, conn)
                    if current is None:
                        raise RequestError("unknown run_id")
                    if current["state"] == FINISHED_RUN_STATE:
                        raise RequestError("cannot observe a finished run")
                    supersedes = request["supersedes"]
                    if supersedes:
                        row = conn.execute(
                            "SELECT run_id FROM observations WHERE observation_id = ?", (supersedes,)
                        ).fetchone()
                        if row is None or row["run_id"] != run_id:
                            raise RequestError("supersedes must name an observation from this run")
                    published = self._publish_evidence_copies(prepared)
                    conn.execute(
                        """INSERT INTO observations
                           (observation_id, run_id, request_json, recorded_at, data_json)
                           VALUES (?, ?, ?, ?, ?)""",
                        (observation_id, run_id, json_text(request), now, json_text(data)),
                    )
                    conn.execute(
                        "INSERT INTO events (event_id, run_id, recorded_at, kind, payload_json) VALUES (?, ?, ?, 'observation', ?)",
                        (event_id, run_id, now, json_text({"observation_id": observation_id, "request": request})),
                    )
                    result = (data, False)
        except BaseException:
            _remove_private_files(published, suppress_errors=True)
            _remove_private_files([path for path, _ in prepared], suppress_errors=True)
            raise
        else:
            _remove_private_files([path for path, _ in prepared])
        return result

    def finish(
        self, run_id: str, payload: dict[str, Any], now: str, event_id: str
    ) -> tuple[dict[str, Any], bool]:
        """Finish a run, or return its current projection for an exact retry."""

        encoded = json_text(payload)
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT finish_json FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if row is None:
                raise RequestError("unknown run_id")
            if row["finish_json"] is not None:
                if row["finish_json"] == encoded:
                    current = self.run(run_id, conn)
                    if current is None:
                        raise StoreUnavailableError("finished run projection is missing")
                    return current, True
                raise ConflictError("run is already finished with a different outcome or summary")
            conn.execute(
                """UPDATE runs SET state = ?, outcome = ?, summary = ?,
                   last_checkpoint_at = ?, finish_json = ? WHERE run_id = ?""",
                (FINISHED_RUN_STATE, payload["outcome"], payload["summary"], now, encoded, run_id),
            )
            conn.execute(
                "INSERT INTO events (event_id, run_id, recorded_at, kind, payload_json) VALUES (?, ?, ?, 'finish', ?)",
                (event_id, run_id, now, encoded),
            )
            current = self.run(run_id, conn)
            if current is None:
                raise StoreUnavailableError("finished run projection is missing")
            return current, False

    def observations_for_run(self, run_id: str) -> list[dict[str, Any]]:
        with self.read_connection() as conn:
            rows = conn.execute(
                "SELECT data_json FROM observations WHERE run_id = ? ORDER BY recorded_at, observation_id",
                (run_id,),
            ).fetchall()
            return [json_value(row["data_json"]) for row in rows]

    def latest_checkpoint(self, run_id: str) -> dict[str, Any] | None:
        with self.read_connection() as conn:
            row = conn.execute(
                """SELECT event_id, recorded_at, payload_json FROM events
                   WHERE run_id = ? AND kind = 'checkpoint'
                   ORDER BY recorded_at DESC, rowid DESC LIMIT 1""",
                (run_id,),
            ).fetchone()
            if row is None:
                return None
            payload = json_value(row["payload_json"])
            return {"event_id": row["event_id"], "recorded_at": row["recorded_at"], **payload}

    def all_patterns(self) -> list[dict[str, Any]]:
        with self.read_connection() as conn:
            rows = conn.execute("SELECT data_json FROM patterns").fetchall()
            return [json_value(row["data_json"]) for row in rows]

    def import_patterns(
        self, patterns: list[dict[str, Any]], now: str, event_ids: list[str]
    ) -> tuple[list[dict[str, Any]], int]:
        """Upsert validated patterns while retaining each private disposition."""

        changed: list[dict[str, Any]] = []
        with self.transaction() as conn:
            for requested, event_id in zip(patterns, event_ids, strict=True):
                row = conn.execute(
                    "SELECT data_json FROM patterns WHERE pattern_key = ?", (requested["pattern_key"],)
                ).fetchone()
                stored = json_value(row["data_json"]) if row else None
                candidate = dict(requested)
                candidate["updated_at"] = now
                if stored is not None:
                    candidate["disposition"] = stored["disposition"]
                    candidate["reason"] = stored["reason"]
                    if "disposition_evidence" in stored:
                        candidate["disposition_evidence"] = stored["disposition_evidence"]
                    if _pattern_equivalent(stored, candidate):
                        continue
                conn.execute(
                    """INSERT INTO patterns (pattern_key, data_json, updated_at) VALUES (?, ?, ?)
                       ON CONFLICT(pattern_key) DO UPDATE SET data_json = excluded.data_json,
                       updated_at = excluded.updated_at""",
                    (candidate["pattern_key"], json_text(candidate), now),
                )
                conn.execute(
                    "INSERT INTO events (event_id, run_id, recorded_at, kind, payload_json) VALUES (?, NULL, ?, 'pattern-import', ?)",
                    (event_id, now, json_text(candidate)),
                )
                changed.append(candidate)
        return changed, len(changed)

    def revise_pattern(
        self,
        key: str,
        disposition: str,
        reason: str,
        evidence_id: str | None,
        now: str,
        event_id: str,
    ) -> dict[str, Any]:
        """Revise one private pattern disposition and append its event."""

        with self.transaction() as conn:
            row = conn.execute(
                "SELECT data_json FROM patterns WHERE pattern_key = ?", (key,)
            ).fetchone()
            if row is None:
                raise RequestError("unknown pattern_key")
            if evidence_id:
                evidence = conn.execute(
                    "SELECT observation_id FROM observations WHERE observation_id = ?", (evidence_id,)
                ).fetchone()
                if evidence is None:
                    raise RequestError("--evidence must name an existing observation")
            pattern = json_value(row["data_json"])
            if (
                pattern["disposition"] == disposition
                and pattern["reason"] == reason
                and pattern.get("disposition_evidence") == evidence_id
            ):
                return pattern
            pattern["disposition"] = disposition
            pattern["reason"] = reason
            pattern["disposition_evidence"] = evidence_id
            pattern["updated_at"] = now
            conn.execute(
                "UPDATE patterns SET data_json = ?, updated_at = ? WHERE pattern_key = ?",
                (json_text(pattern), now, key),
            )
            conn.execute(
                "INSERT INTO events (event_id, run_id, recorded_at, kind, payload_json) VALUES (?, NULL, ?, 'pattern-disposition', ?)",
                (event_id, now, json_text(pattern)),
            )
            return pattern

    def prepare_evidence_directory(self) -> None:
        """Ensure the private evidence directory remains private and writable.

        Pending excerpts belong to the process that staged them.  In
        particular, this must not glob and delete another process's pending
        file while that process is waiting on SQLite's write lock.
        """

        try:
            _make_private_directory(self.evidence_dir)
        except OSError as error:
            raise StoreUnavailableError(
                f"cannot prepare private evidence directory: {error}"
            ) from error

    def _publish_evidence_copies(self, prepared: list[tuple[Path, str]]) -> list[Path]:
        published: list[Path] = []
        try:
            for source, filename in prepared:
                target = self.evidence_dir / filename
                # A hard interruption after a previous publish but before its
                # SQLite commit can leave this unreferenced target behind.
                # This transaction has already established that no observation
                # owns the identifier, so replacing that orphan makes the
                # retry recoverable without touching any other observation.
                os.replace(source, target)
                published.append(target)
                _restrict_private_file(target)
        except OSError as error:
            _remove_private_files(published, suppress_errors=True)
            raise StoreUnavailableError(f"cannot save private evidence: {error}") from error
        except BaseException:
            _remove_private_files(published, suppress_errors=True)
            raise
        return published


def _run_from_row(row: sqlite3.Row) -> dict[str, Any]:
    spec = json_value(row["spec_json"])
    return {
        "run_id": row["run_id"],
        "project_path": row["project_path"],
        "goal": spec["goal"],
        "acceptance": spec["acceptance"],
        "non_goals": spec["non_goals"],
        "models": json_value(row["models_json"]),
        "created_at": row["created_at"],
        "state": row["state"],
        "last_checkpoint_at": row["last_checkpoint_at"],
        "next_check_at": row["next_check_at"],
        "deadline_at": row["deadline_at"],
        "outcome": row["outcome"],
        "summary": row["summary"],
    }


def _pattern_equivalent(stored: dict[str, Any], candidate: dict[str, Any]) -> bool:
    """Ignore helper timestamps when deciding whether an import is a replay."""

    left = dict(stored)
    right = dict(candidate)
    left.pop("updated_at", None)
    right.pop("updated_at", None)
    return json_text(left) == json_text(right)


def _has_version_one_schema(conn: sqlite3.Connection) -> bool:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {row[0] for row in rows} == {"runs", "events", "observations", "patterns"}


def _database_error(error: sqlite3.DatabaseError, message: str) -> AdvocateError:
    if isinstance(error, sqlite3.OperationalError) and _is_locked(error):
        return ContentionError("store is busy; retry this operation")
    return StoreUnavailableError(message)


def _is_locked(error: sqlite3.Error) -> bool:
    message = str(error).lower()
    return "locked" in message or "busy" in message


def _make_private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "nt":
        _restrict_windows_path(path, directory=True)
    else:
        path.chmod(0o700)


def _restrict_private_file(path: Path) -> None:
    if os.name == "nt":
        _restrict_windows_path(path, directory=False)
    else:
        path.chmod(0o600)


def _restrict_windows_path(path: Path, directory: bool) -> None:
    """Replace the complete DACL with one full-control current-user ACE."""

    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    token = wintypes.HANDLE()
    security_descriptor = ctypes.c_void_p()
    try:
        advapi32.OpenProcessToken.argtypes = (
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.HANDLE),
        )
        advapi32.OpenProcessToken.restype = wintypes.BOOL
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle.restype = wintypes.BOOL
        kernel32.LocalFree.argtypes = (ctypes.c_void_p,)
        kernel32.LocalFree.restype = ctypes.c_void_p
        if not advapi32.OpenProcessToken(
            kernel32.GetCurrentProcess(), 0x0008, ctypes.byref(token)
        ):
            raise ctypes.WinError(ctypes.get_last_error())

        required = wintypes.DWORD()
        advapi32.GetTokenInformation.argtypes = (
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        )
        advapi32.GetTokenInformation.restype = wintypes.BOOL
        advapi32.GetTokenInformation(token, 1, None, 0, ctypes.byref(required))
        if not required.value:
            raise ctypes.WinError(ctypes.get_last_error())
        token_info = ctypes.create_string_buffer(required.value)
        if not advapi32.GetTokenInformation(
            token, 1, token_info, required, ctypes.byref(required)
        ):
            raise ctypes.WinError(ctypes.get_last_error())

        class SidAndAttributes(ctypes.Structure):
            _fields_ = [("sid", ctypes.c_void_p), ("attributes", wintypes.DWORD)]

        user = ctypes.cast(token_info, ctypes.POINTER(SidAndAttributes)).contents
        sid_text = wintypes.LPWSTR()
        advapi32.ConvertSidToStringSidW.argtypes = (
            ctypes.c_void_p,
            ctypes.POINTER(wintypes.LPWSTR),
        )
        advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
        if not advapi32.ConvertSidToStringSidW(user.sid, ctypes.byref(sid_text)):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            inheritance = "OICI" if directory else ""
            sddl = f"D:P(A;{inheritance};FA;;;{sid_text.value})"
        finally:
            kernel32.LocalFree(sid_text)

        advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = (
            wintypes.LPCWSTR,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(wintypes.DWORD),
        )
        if not advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            sddl, 1, ctypes.byref(security_descriptor), None
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        dacl_present = wintypes.BOOL()
        dacl_defaulted = wintypes.BOOL()
        dacl = ctypes.c_void_p()
        advapi32.GetSecurityDescriptorDacl.argtypes = (
            ctypes.c_void_p,
            ctypes.POINTER(wintypes.BOOL),
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(wintypes.BOOL),
        )
        advapi32.GetSecurityDescriptorDacl.restype = wintypes.BOOL
        if not advapi32.GetSecurityDescriptorDacl(
            security_descriptor,
            ctypes.byref(dacl_present),
            ctypes.byref(dacl),
            ctypes.byref(dacl_defaulted),
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        if not dacl_present:
            raise OSError("generated private DACL is absent")
        advapi32.SetNamedSecurityInfoW.argtypes = (
            wintypes.LPWSTR,
            ctypes.c_int,
            wintypes.DWORD,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
        )
        advapi32.SetNamedSecurityInfoW.restype = wintypes.DWORD
        result = advapi32.SetNamedSecurityInfoW(
            str(path),
            1,
            0x00000004 | 0x80000000,
            None,
            None,
            dacl,
            None,
        )
        if result:
            raise ctypes.WinError(result)
    except (OSError, ValueError) as error:
        raise OSError(f"cannot restrict Windows ACL for {path}: {error}") from error
    finally:
        if security_descriptor:
            kernel32.LocalFree(security_descriptor)
        if token:
            kernel32.CloseHandle(token)


def _remove_private_files(paths: list[Path], *, suppress_errors: bool = False) -> None:
    failures: list[OSError] = []
    for path in paths:
        try:
            path.unlink()
        except FileNotFoundError:
            continue
        except OSError as error:
            failures.append(error)
    if failures and not suppress_errors:
        raise StoreUnavailableError(f"cannot remove private evidence: {failures[0]}") from failures[0]


def _rollback_if_needed(conn: sqlite3.Connection, started: bool) -> None:
    if started and conn.in_transaction:
        with contextlib.suppress(sqlite3.Error):
            conn.execute("ROLLBACK")


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _timestamp_not_before(left: str, right: str) -> bool:
    return parse_utc_timestamp(left) >= parse_utc_timestamp(right)


def _timestamp_after(left: str, right: str) -> bool:
    return parse_utc_timestamp(left) > parse_utc_timestamp(right)


def _validate_checkpoint_expectations(
    payload: dict[str, Any], current: dict[str, Any], now: str
) -> None:
    if payload["state"] != "paused" and not _timestamp_after(
        payload["next_check_at"], now
    ):
        raise RequestError("next_check_at must be in the future")
    change = payload["deadline_change"]
    if change == "preserve":
        return
    if change != current["deadline_at"] and not payload["deadline_reason"]:
        raise RequestError("deadline replacement or removal requires deadline_reason")
    if change is not None and not _timestamp_after(change, now):
        raise RequestError("deadline_at must be in the future")


def parse_utc_timestamp(value: str) -> datetime:
    """Parse the single UTC timestamp wire format used by the store and service."""

    if not isinstance(value, str) or "T" not in value or not value.endswith("Z"):
        raise ValueError("timestamp must be an RFC3339 UTC timestamp ending in Z")
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError("timestamp must be an RFC3339 UTC timestamp ending in Z")
    return parsed.astimezone(UTC)
