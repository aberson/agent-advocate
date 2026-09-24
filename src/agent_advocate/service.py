"""Validation and lifecycle operations for the deterministic CLI."""

from __future__ import annotations

from collections.abc import Iterator
import contextlib
from datetime import UTC, date, datetime
import hashlib
from importlib.resources import as_file, files
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any, BinaryIO
import uuid

from .store import (
    FINISHED_RUN_STATE,
    PENDING_EVIDENCE_PREFIX,
    PENDING_EVIDENCE_SUFFIX,
    RequestError,
    SCHEMA_VERSION,
    Store,
    StoreUnavailableError,
    parse_utc_timestamp,
    utc_now,
)


MAX_REQUEST_BYTES = 256 * 1024
MAX_EXCERPT_BYTES = 8 * 1024
# Local evidence is intentionally bounded: at most 8 MiB is read and hashed.
MAX_LOCAL_EVIDENCE_BYTES = 8 * 1024 * 1024
RUN_STATES = {"active", "checking", "waiting", "paused", "unknown", FINISHED_RUN_STATE}
CHECKPOINT_STATES = RUN_STATES - {FINISHED_RUN_STATE}
BASES = {"measured", "reported", "inferred"}
ANALYSIS_KINDS = {"independent", "coordinator", "none"}
EVIDENCE_KINDS = {"local", "public-url", "host-result"}
PATTERN_BASES = {"local-observation", "official-guidance", "community-report"}
PATTERN_DISPOSITIONS = {"candidate", "monitoring", "fix-applied", "retired", "dismissed"}
OUTCOMES = {"completed", "stopped", "abandoned"}
ALERT_ACTIONS = {"acknowledge", "dismiss", "snooze"}
PATTERN_KEY = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def new_uuid() -> str:
    return str(uuid.uuid4())


def read_json_file(path_value: str) -> Any:
    path = Path(path_value).expanduser()
    try:
        size = path.stat().st_size
    except OSError as error:
        raise RequestError(f"cannot read JSON input {path}: {error}") from error
    if size > MAX_REQUEST_BYTES:
        raise RequestError("JSON request exceeds the 256 KiB limit")
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as error:
        raise RequestError(f"JSON input must be a readable UTF-8 file: {error}") from error
    try:
        return json.loads(text, object_pairs_hook=_unique_object)
    except json.JSONDecodeError as error:
        raise RequestError(f"invalid JSON input: {error.msg}") from error
    except RecursionError as error:
        raise RequestError("invalid JSON input: nesting exceeds supported depth") from error


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RequestError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def initialize(store: Store, seed_file: Path | None = None) -> dict[str, Any]:
    store.initialize()
    imported = 0
    if seed_file is None:
        try:
            resource = files("agent_advocate").joinpath("data", "seed-patterns.json")
            if not resource.is_file():
                raise StoreUnavailableError("packaged public seed file is missing")
            with as_file(resource) as packaged_seed_file:
                value = read_json_file(str(packaged_seed_file))
        except (ModuleNotFoundError, OSError) as error:
            raise StoreUnavailableError(f"cannot read packaged public seed file: {error}") from error
    else:
        try:
            seed_exists = seed_file.exists()
        except OSError as error:
            raise StoreUnavailableError(f"cannot inspect public seed file: {error}") from error
        if not seed_exists:
            return {
                "data_dir": str(store.data_dir),
                "schema_version": SCHEMA_VERSION,
                "seed_patterns_imported": imported,
            }
        if not seed_file.is_file():
            raise StoreUnavailableError("public seed path must name a regular file")
        value = read_json_file(str(seed_file))
    patterns = normalize_patterns(value)
    _, imported = store.import_patterns(patterns, utc_now(), [new_uuid() for _ in patterns])
    return {
        "data_dir": str(store.data_dir),
        "schema_version": SCHEMA_VERSION,
        "seed_patterns_imported": imported,
    }


def start(store: Store, value: Any, now: str | None = None) -> tuple[dict[str, Any], bool]:
    spec = normalize_run_spec(value)
    timestamp = now or utc_now()
    existing = store.run(spec["run_id"])
    if existing is None:
        _require_future(spec["next_check_at"], timestamp, "next_check_at")
    return store.insert_run(spec, timestamp, new_uuid())


def checkpoint(
    store: Store, run_id: str, value: Any, now: str | None = None
) -> tuple[dict[str, Any], bool, str]:
    _uuid(run_id, "run_id")
    payload = normalize_checkpoint(value)
    event_id = payload["event_id"]
    run, replay = store.checkpoint(run_id, event_id, payload, now)
    return run, replay, event_id


def observe(
    store: Store, run_id: str, value: Any, now: str | None = None
) -> tuple[dict[str, Any], bool]:
    _uuid(run_id, "run_id")
    request = normalize_observation(value)
    timestamp = now or utc_now()
    existing = _observation_exists(store, request["observation_id"])
    if existing:
        # Exact retry comparison is handled in the short transaction.  Do not
        # re-read evidence that may now be absent or changed.
        return store.insert_observation(
            run_id,
            request["observation_id"],
            request,
            {},
            timestamp,
            new_uuid(),
        )
    current = store.run(run_id)
    if current is None:
        raise RequestError("unknown run_id")
    processed = dict(request)
    processed["run_id"] = run_id
    processed["recorded_at"] = timestamp
    processed["evidence"], pending_copies = _capture_evidence(
        store,
        request["observation_id"],
        request["evidence"],
        current["project_path"],
    )
    return store.insert_observation(
        run_id,
        request["observation_id"],
        request,
        processed,
        timestamp,
        new_uuid(),
        pending_copies,
    )


def status(store: Store, run_id: str) -> dict[str, Any]:
    _uuid(run_id, "run_id")
    run = store.run(run_id)
    if run is None:
        raise RequestError("unknown run_id")
    stored_observations = store.observations_for_run(run_id)
    availability = []
    for observation in stored_observations:
        for evidence in observation["evidence"]:
            if evidence["kind"] == "local":
                availability.append(
                    {
                        "observation_id": observation["observation_id"],
                        "locator": evidence["locator"],
                        "availability": evidence.get("availability", "unknown"),
                    }
                )
    return {
        "run": run,
        "overdue_conditions": _overdue_conditions(run),
        "state_segments": store.state_segments_for_run(run_id),
        "latest_checkpoint": store.latest_checkpoint(run_id),
        "observations": [public_observation(item) for item in stored_observations],
        "evidence_availability": availability,
        "alerts": store.alerts_for_run(run_id),
    }


def finish(
    store: Store, run_id: str, outcome: str, summary: str, now: str | None = None
) -> tuple[dict[str, Any], bool]:
    _uuid(run_id, "run_id")
    if outcome not in OUTCOMES:
        raise RequestError("outcome must be completed, stopped, or abandoned")
    _nonempty(summary, "summary")
    return store.finish(run_id, {"outcome": outcome, "summary": summary}, now, new_uuid())


def evaluate_alerts(
    store: Store, run_id: str, now: str | None = None
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Evaluate one run with a supplied clock, without any model work."""

    _uuid(run_id, "run_id")
    timestamp = now or utc_now()
    try:
        parse_utc_timestamp(timestamp)
    except ValueError as error:
        raise RequestError("watch clock must be an RFC3339 UTC timestamp ending in Z") from error
    run = store.run(run_id)
    if run is None:
        raise RequestError("unknown run_id")
    # Import lazily so watch can call this service function for its foreground
    # loop without a module-import cycle.
    from .watch import due_conditions

    conditions = [condition.as_dict() for condition in due_conditions(run, timestamp)]
    return store.record_due_alerts(run_id, conditions, timestamp)


def revise_alert(
    store: Store,
    alert_id: str,
    action: str,
    reason: str,
    until: str | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    _uuid(alert_id, "alert_id")
    if action not in ALERT_ACTIONS:
        raise RequestError("alert action must be acknowledge, dismiss, or snooze")
    _nonempty(reason, "reason")
    timestamp = now or utc_now()
    if action == "snooze":
        if until is None:
            raise RequestError("snooze requires --until with a future UTC timestamp")
        normalized_until = _timestamp(until, "until")
        _require_future(normalized_until, timestamp, "until")
    else:
        if until is not None:
            raise RequestError("--until is only valid with --action snooze")
        normalized_until = None
    # The store checks the future boundary again after obtaining the write
    # lock. A real request can wait for that lock long enough to expire.
    return store.revise_alert(alert_id, action, reason, normalized_until, now)


def import_patterns(store: Store, value: Any, now: str | None = None) -> tuple[list[dict[str, Any]], int]:
    patterns = normalize_patterns(value)
    return store.import_patterns(patterns, now or utc_now(), [new_uuid() for _ in patterns])


def set_pattern_disposition(
    store: Store,
    key: str,
    disposition: str,
    reason: str,
    evidence_id: str | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    _pattern_key(key)
    if disposition not in PATTERN_DISPOSITIONS:
        raise RequestError("invalid pattern disposition")
    _nonempty(reason, "reason")
    if evidence_id is not None:
        _uuid(evidence_id, "evidence")
    return store.revise_pattern(key, disposition, reason, evidence_id, now or utc_now(), new_uuid())


def brief(store: Store, run_id: str) -> dict[str, Any]:
    _uuid(run_id, "run_id")
    current = store.run(run_id)
    if current is None:
        raise RequestError("unknown run_id")
    role_values = {item["role"] for item in current["models"]}
    model_values = {
        value
        for item in current["models"]
        for value in (item["requested_model"], item["observed_model"])
        if value
    }
    host_values = {item["host"] for item in current["models"]}
    matches: list[tuple[bool, bool, datetime, str, dict[str, Any]]] = []
    for pattern in store.all_patterns():
        if pattern["disposition"] in {"retired", "dismissed"}:
            continue
        scope = pattern["scope"]
        if not _scope_matches(scope, role_values, model_values, host_values):
            continue
        exact = bool(
            (set(scope["roles"]) & role_values) or (set(scope["models"]) & model_values)
        )
        confirmed_local = pattern["basis"] == "local-observation"
        matches.append(
            (
                exact,
                confirmed_local,
                parse_utc_timestamp(pattern["updated_at"]),
                pattern["pattern_key"],
                pattern,
            )
        )
    matches.sort(key=lambda item: (not item[0], not item[1], -item[2].timestamp(), item[3]))
    return {
        "run": current,
        "overdue_conditions": _overdue_conditions(current),
        "patterns": [public_pattern(item[4]) for item in matches[:5]],
        "alerts": store.alerts_for_run(run_id),
    }


def _overdue_conditions(run: dict[str, Any]) -> list[dict[str, str]]:
    """Expose a read-only current timer diagnosis in status and brief."""

    from .watch import due_conditions

    return [condition.as_dict() for condition in due_conditions(run, utc_now())]


def normalize_run_spec(value: Any) -> dict[str, Any]:
    obj = _object(value, "RunSpec")
    _keys(
        obj,
        {
            "run_id",
            "project_path",
            "goal",
            "acceptance",
            "non_goals",
            "models",
            "next_check_at",
            "deadline_at",
        },
        {"project_path", "goal", "acceptance", "non_goals", "models", "next_check_at", "deadline_at"},
        "RunSpec",
    )
    raw_path = _nonempty(obj["project_path"], "project_path")
    path = Path(raw_path).expanduser()
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise RequestError(f"project_path must name an existing directory: {error}") from error
    if not resolved.is_dir():
        raise RequestError("project_path must name an existing directory")
    try:
        home = Path.home().resolve(strict=True)
    except OSError as error:
        raise RequestError(f"cannot resolve user home directory: {error}") from error
    if resolved == resolved.parent or resolved == home:
        raise RequestError("project_path must not be the filesystem root or user home directory")
    return {
        "run_id": _uuid_or_new(obj.get("run_id"), "run_id"),
        "project_path": str(resolved),
        "goal": _nonempty(obj["goal"], "goal"),
        "acceptance": _string_list(obj["acceptance"], "acceptance", nonempty=True),
        "non_goals": _string_list(obj["non_goals"], "non_goals"),
        "models": _models(obj["models"]),
        "next_check_at": _timestamp(obj["next_check_at"], "next_check_at"),
        "deadline_at": _nullable_timestamp(obj["deadline_at"], "deadline_at"),
    }


def normalize_checkpoint(value: Any) -> dict[str, Any]:
    obj = _object(value, "CheckpointSpec")
    _keys(
        obj,
        {"event_id", "state", "summary", "next_check_at", "deadline_at", "deadline_reason"},
        {"state", "summary", "next_check_at"},
        "CheckpointSpec",
    )
    state = obj["state"]
    if state not in CHECKPOINT_STATES:
        raise RequestError("checkpoint state must be active, checking, waiting, paused, or unknown")
    summary = _nullable_string(obj["summary"], "summary") if "summary" in obj else None
    if state == "waiting" and not summary:
        raise RequestError("waiting checkpoint requires a nonempty summary")
    deadline_change: str | None = "preserve"
    if "deadline_at" in obj:
        deadline_change = _nullable_timestamp(obj["deadline_at"], "deadline_at")
    reason = _nullable_string(obj["deadline_reason"], "deadline_reason") if "deadline_reason" in obj else None
    return {
        "event_id": _uuid_or_new(obj.get("event_id"), "event_id"),
        "state": state,
        "summary": summary,
        "next_check_at": _timestamp(obj["next_check_at"], "next_check_at"),
        "deadline_change": deadline_change,
        "deadline_reason": reason,
    }


def normalize_observation(value: Any) -> dict[str, Any]:
    obj = _object(value, "ObservationSpec")
    _keys(
        obj,
        {
            "observation_id",
            "statement",
            "basis",
            "evidence",
            "pattern_key",
            "recommendation",
            "analysis_kind",
            "assessor_id",
            "supersedes",
        },
        {"statement", "basis", "evidence", "analysis_kind"},
        "ObservationSpec",
    )
    basis = obj["basis"]
    if basis not in BASES:
        raise RequestError("basis must be measured, reported, or inferred")
    analysis_kind = obj["analysis_kind"]
    if analysis_kind not in ANALYSIS_KINDS:
        raise RequestError("analysis_kind must be independent, coordinator, or none")
    assessor_id = _nullable_string(obj.get("assessor_id"), "assessor_id")
    if analysis_kind == "independent" and assessor_id is None:
        raise RequestError("independent analysis_kind requires a nonempty assessor_id")
    evidence = _evidence_list(obj["evidence"], "evidence")
    if analysis_kind == "independent" and not any(
        item["kind"] == "host-result" for item in evidence
    ):
        raise RequestError("independent analysis_kind requires a host-result evidence receipt")
    pattern_key = obj.get("pattern_key")
    if pattern_key is not None:
        _pattern_key(pattern_key)
    return {
        "observation_id": _uuid_or_new(obj.get("observation_id"), "observation_id"),
        "statement": _nonempty(obj["statement"], "statement"),
        "basis": basis,
        "evidence": evidence,
        "pattern_key": pattern_key,
        "recommendation": _nullable_string(obj.get("recommendation"), "recommendation"),
        "analysis_kind": analysis_kind,
        "assessor_id": assessor_id,
        "supersedes": _nullable_uuid(obj.get("supersedes"), "supersedes"),
    }


def normalize_patterns(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise RequestError("pattern import must be a JSON array")
    keys: set[str] = set()
    patterns = [normalize_pattern(item) for item in value]
    for pattern in patterns:
        if pattern["pattern_key"] in keys:
            raise RequestError("pattern import contains a duplicate pattern_key")
        keys.add(pattern["pattern_key"])
    return patterns


def normalize_pattern(value: Any) -> dict[str, Any]:
    obj = _object(value, "Pattern")
    _keys(
        obj,
        {
            "pattern_key",
            "summary",
            "trigger",
            "scope",
            "basis",
            "sources",
            "owner",
            "action",
            "disposition",
            "review_after",
            "reason",
        },
        {
            "pattern_key",
            "summary",
            "trigger",
            "scope",
            "basis",
            "sources",
            "owner",
            "action",
            "disposition",
            "review_after",
            "reason",
        },
        "Pattern",
    )
    key = obj["pattern_key"]
    _pattern_key(key)
    basis = obj["basis"]
    if basis not in PATTERN_BASES:
        raise RequestError("invalid pattern basis")
    disposition = obj["disposition"]
    if disposition not in PATTERN_DISPOSITIONS:
        raise RequestError("invalid pattern disposition")
    scope = _object(obj["scope"], "scope")
    _keys(scope, {"roles", "models", "hosts", "tags"}, {"roles", "models", "hosts", "tags"}, "scope")
    review_after = obj["review_after"]
    if review_after is not None:
        if not isinstance(review_after, str):
            raise RequestError("review_after must be an ISO date or null")
        try:
            review_after = date.fromisoformat(review_after).isoformat()
        except ValueError as error:
            raise RequestError("review_after must be an ISO date or null") from error
    return {
        "pattern_key": key,
        "summary": _nonempty(obj["summary"], "summary"),
        "trigger": _nonempty(obj["trigger"], "trigger"),
        "scope": {
            name: _string_list(scope[name], f"scope.{name}")
            for name in ("roles", "models", "hosts", "tags")
        },
        "basis": basis,
        "sources": _evidence_list(obj["sources"], "sources"),
        "owner": _nonempty(obj["owner"], "owner"),
        "action": _nonempty(obj["action"], "action"),
        "disposition": disposition,
        "review_after": review_after,
        "reason": _nonempty(obj["reason"], "reason"),
    }


def _capture_evidence(
    store: Store,
    observation_id: str,
    evidence: list[dict[str, Any]],
    project_path: str,
) -> tuple[list[dict[str, Any]], list[tuple[Path, str]]]:
    store.prepare_evidence_directory()
    captured: list[dict[str, Any]] = []
    pending_copies: list[tuple[Path, str]] = []
    try:
        for index, item in enumerate(evidence):
            result = dict(item)
            if item["kind"] != "local":
                result["availability"] = "not-local"
                captured.append(result)
                continue
            try:
                with _open_local_evidence(
                    item["locator"], project_path
                ) as (handle, opened_stat):
                    if not stat.S_ISREG(opened_stat.st_mode):
                        result["availability"] = "not-regular"
                        captured.append(result)
                        continue
                    if opened_stat.st_size > MAX_LOCAL_EVIDENCE_BYTES:
                        result["availability"] = "too-large"
                        captured.append(result)
                        continue
                    assert handle is not None
                    digest, excerpt, read_status = _file_digest_and_excerpt(
                        handle, opened_stat
                    )
            except FileNotFoundError:
                result["availability"] = "missing"
                captured.append(result)
                continue
            except OSError as error:
                raise StoreUnavailableError(f"cannot read local evidence: {error}") from error
            if read_status != "captured":
                result["availability"] = read_status
                captured.append(result)
                continue
            expected = item["sha256"]
            assert digest is not None
            result["sha256"] = digest
            result["excerpt"] = excerpt.decode("utf-8", errors="replace")
            result["content_status"] = "private-untrusted"
            result["availability"] = "current" if expected in (None, digest) else "stale"
            filename = f"{observation_id}-{index}.evidence"
            temporary = _write_pending_evidence(store, excerpt)
            pending_copies.append((temporary, filename))
            result["private_copy"] = filename
            captured.append(result)
    except BaseException:
        _remove_pending_copies(pending_copies)
        raise
    return captured, pending_copies


def _local_evidence_path(locator: str, project_path: str) -> tuple[Path, Path]:
    try:
        source = Path(os.path.abspath(Path(locator).expanduser()))
        project = Path(project_path).resolve(strict=True)
    except OSError as error:
        raise StoreUnavailableError(f"cannot resolve local evidence path: {error}") from error
    try:
        source.relative_to(project)
    except ValueError as error:
        raise RequestError("local evidence must resolve within the run project_path") from error
    return source, project


@contextlib.contextmanager
def _open_local_evidence(
    locator: str, project_path: str
) -> Iterator[tuple[BinaryIO | None, os.stat_result]]:
    """Open once, then validate the opened object before reading from it."""

    source, project = _local_evidence_path(locator, project_path)
    descriptor = _open_evidence_descriptor(source)
    handle: BinaryIO | None = None
    try:
        opened_stat = os.fstat(descriptor)
        if os.name == "nt":
            final_path = _windows_final_path(descriptor)
            try:
                final_path.relative_to(project)
            except ValueError as error:
                raise RequestError(
                    "local evidence must resolve within the run project_path"
                ) from error
        else:
            final_path = source.resolve(strict=True)
            final_stat = final_path.stat()
            if not os.path.samestat(opened_stat, final_stat):
                raise RequestError("local evidence path changed while opening")
            try:
                final_path.relative_to(project)
            except ValueError as error:
                raise RequestError(
                    "local evidence must resolve within the run project_path"
                ) from error
        if stat.S_ISREG(opened_stat.st_mode):
            handle = os.fdopen(descriptor, "rb")
            descriptor = -1
        yield handle, opened_stat
    finally:
        if handle is not None:
            handle.close()
        if descriptor >= 0:
            os.close(descriptor)


def _open_evidence_descriptor(path: Path) -> int:
    if os.name != "nt":
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
        return os.open(path, flags)

    import ctypes
    from ctypes import wintypes
    import msvcrt

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    kernel32.CreateFileW.restype = wintypes.HANDLE
    raw_handle = kernel32.CreateFileW(
        str(path),
        0x80000000,
        0x00000001 | 0x00000002 | 0x00000004,
        None,
        3,
        0x02000000,
        None,
    )
    if raw_handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        descriptor = msvcrt.open_osfhandle(raw_handle, flags)
    except BaseException:
        kernel32.CloseHandle(raw_handle)
        raise
    return descriptor


def _windows_final_path(descriptor: int) -> Path:
    import ctypes
    from ctypes import wintypes
    import msvcrt

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetFinalPathNameByHandleW.argtypes = (
        wintypes.HANDLE,
        wintypes.LPWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
    )
    kernel32.GetFinalPathNameByHandleW.restype = wintypes.DWORD
    raw_handle = msvcrt.get_osfhandle(descriptor)
    size = kernel32.GetFinalPathNameByHandleW(raw_handle, None, 0, 0)
    if not size:
        raise ctypes.WinError(ctypes.get_last_error())
    buffer = ctypes.create_unicode_buffer(size + 1)
    written = kernel32.GetFinalPathNameByHandleW(raw_handle, buffer, len(buffer), 0)
    if not written or written >= len(buffer):
        raise ctypes.WinError(ctypes.get_last_error())
    value = buffer.value
    if value.startswith("\\\\?\\UNC\\"):
        value = "\\\\" + value[8:]
    elif value.startswith("\\\\?\\"):
        value = value[4:]
    return Path(value)


def _write_pending_evidence(store: Store, excerpt: bytes) -> Path:
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=store.evidence_dir,
            prefix=PENDING_EVIDENCE_PREFIX,
            suffix=PENDING_EVIDENCE_SUFFIX,
            delete=False,
        ) as handle:
            handle.write(excerpt)
            return Path(handle.name)
    except OSError as error:
        raise StoreUnavailableError(f"cannot save private evidence: {error}") from error


def _remove_pending_copies(copies: list[tuple[Path, str]]) -> None:
    for path, _ in copies:
        try:
            path.unlink()
        except FileNotFoundError:
            continue
        except OSError as error:
            raise StoreUnavailableError(f"cannot remove pending private evidence: {error}") from error


def public_observation(observation: dict[str, Any]) -> dict[str, Any]:
    """Return metadata only; retained evidence content never reaches CLI output."""

    result = dict(observation)
    result["evidence"] = [public_evidence(item) for item in observation["evidence"]]
    result["evidence_content"] = "private-untrusted-omitted"
    return result


def public_pattern(pattern: dict[str, Any]) -> dict[str, Any]:
    """Return a pattern without replaying untrusted evidence excerpts."""

    result = dict(pattern)
    result["sources"] = [public_evidence(item) for item in pattern["sources"]]
    return result


def public_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    """Preserve evidence metadata while omitting private, untrusted text."""

    result = dict(evidence)
    if result.get("excerpt") is not None:
        result["content_status"] = "private-untrusted"
    result["excerpt"] = None
    result.pop("private_copy", None)
    return result


def _file_digest_and_excerpt(
    handle: BinaryIO, opened_stat: os.stat_result
) -> tuple[str | None, bytes, str]:
    digest = hashlib.sha256()
    excerpt = bytearray()
    total = 0
    while total < MAX_LOCAL_EVIDENCE_BYTES and (
        block := _read_evidence_block(
            handle, min(64 * 1024, MAX_LOCAL_EVIDENCE_BYTES - total)
        )
    ):
        total += len(block)
        digest.update(block)
        if len(excerpt) < MAX_EXCERPT_BYTES:
            excerpt.extend(block[: MAX_EXCERPT_BYTES - len(excerpt)])
    final_stat = os.fstat(handle.fileno())
    before = (opened_stat.st_size, opened_stat.st_mtime_ns, opened_stat.st_ctime_ns)
    after = (final_stat.st_size, final_stat.st_mtime_ns, final_stat.st_ctime_ns)
    if final_stat.st_size > MAX_LOCAL_EVIDENCE_BYTES:
        return None, b"", "too-large"
    if before != after:
        return None, b"", "changed"
    return digest.hexdigest(), bytes(excerpt), "captured"


def _read_evidence_block(handle: BinaryIO, size: int) -> bytes:
    return handle.read(size)


def _observation_exists(store: Store, observation_id: str) -> bool:
    with store.read_connection() as conn:
        return conn.execute(
            "SELECT 1 FROM observations WHERE observation_id = ?", (observation_id,)
        ).fetchone() is not None


def _scope_matches(scope: dict[str, list[str]], roles: set[str], models: set[str], hosts: set[str]) -> bool:
    dimensions = ((scope["roles"], roles), (scope["models"], models), (scope["hosts"], hosts))
    for required, actual in dimensions:
        if required and not (set(required) & actual):
            return False
    return not scope["tags"]


def _object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RequestError(f"{name} must be a JSON object")
    return value


def _keys(obj: dict[str, Any], allowed: set[str], required: set[str], name: str) -> None:
    unknown = sorted(set(obj) - allowed)
    missing = sorted(required - set(obj))
    if unknown:
        raise RequestError(f"{name} has unknown field(s): {', '.join(unknown)}")
    if missing:
        raise RequestError(f"{name} is missing field(s): {', '.join(missing)}")


def _uuid_or_new(value: Any, name: str) -> str:
    return new_uuid() if value is None else _uuid(value, name)


def _uuid(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise RequestError(f"{name} must be a lowercase UUIDv4 string")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError) as error:
        raise RequestError(f"{name} must be a lowercase UUIDv4 string") from error
    if parsed.version != 4 or str(parsed) != value:
        raise RequestError(f"{name} must be a lowercase UUIDv4 string")
    return value


def _nullable_uuid(value: Any, name: str) -> str | None:
    if value is None:
        return None
    return _uuid(value, name)


def _timestamp(value: Any, name: str) -> str:
    if not isinstance(value, str) or "T" not in value or not value.endswith("Z"):
        raise RequestError(f"{name} must be an RFC3339 UTC timestamp ending in Z")
    try:
        parsed = parse_utc_timestamp(value)
    except ValueError as error:
        raise RequestError(f"{name} must be an RFC3339 UTC timestamp ending in Z") from error
    return parsed.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _nullable_timestamp(value: Any, name: str) -> str | None:
    if value is None:
        return None
    return _timestamp(value, name)


def _require_future(value: str, now: str, name: str) -> None:
    if parse_utc_timestamp(value) <= parse_utc_timestamp(now):
        raise RequestError(f"{name} must be in the future")


def _nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RequestError(f"{name} must be a nonempty string")
    return value


def _nullable_string(value: Any, name: str) -> str | None:
    if value is None:
        return None
    return _nonempty(value, name)


def _string_list(value: Any, name: str, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        requirement = "a nonempty array" if nonempty else "an array"
        raise RequestError(f"{name} must be {requirement} of nonempty strings")
    return [_nonempty(item, name) for item in value]


def _models(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise RequestError("models must be an array")
    models = []
    for item in value:
        obj = _object(item, "ModelRole")
        _keys(
            obj,
            {"role", "requested_model", "observed_model", "effort", "host"},
            {"role", "requested_model", "observed_model", "effort", "host"},
            "ModelRole",
        )
        models.append(
            {
                "role": _nonempty(obj["role"], "models.role"),
                "requested_model": _nullable_string(obj["requested_model"], "models.requested_model"),
                "observed_model": _nullable_string(obj["observed_model"], "models.observed_model"),
                "effort": _nullable_string(obj["effort"], "models.effort"),
                "host": _nonempty(obj["host"], "models.host"),
            }
        )
    return models


def _evidence_list(value: Any, name: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise RequestError(f"{name} must be an array")
    result = []
    for item in value:
        obj = _object(item, "EvidenceRef")
        _keys(
            obj,
            {"kind", "locator", "captured_at", "excerpt", "sha256"},
            {"kind", "locator", "captured_at", "excerpt", "sha256"},
            "EvidenceRef",
        )
        kind = obj["kind"]
        if kind not in EVIDENCE_KINDS:
            raise RequestError("EvidenceRef.kind must be local, public-url, or host-result")
        excerpt = obj["excerpt"]
        if excerpt is not None:
            if (
                not isinstance(excerpt, str)
                or len(excerpt.encode("utf-8")) > MAX_EXCERPT_BYTES
            ):
                raise RequestError("EvidenceRef.excerpt must be null or at most 8 KiB")
        digest = obj["sha256"]
        if digest is not None and (not isinstance(digest, str) or not SHA256.fullmatch(digest)):
            raise RequestError("EvidenceRef.sha256 must be a lowercase SHA-256 digest or null")
        result.append(
            {
                "kind": kind,
                "locator": _nonempty(obj["locator"], "EvidenceRef.locator"),
                "captured_at": _timestamp(obj["captured_at"], "EvidenceRef.captured_at"),
                "excerpt": excerpt,
                "sha256": digest,
            }
        )
    return result


def _pattern_key(value: Any) -> str:
    if not isinstance(value, str) or not PATTERN_KEY.fullmatch(value):
        raise RequestError("pattern_key must be lowercase kebab-case")
    return value
