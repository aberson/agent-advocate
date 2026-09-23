from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import uuid

import pytest

import agent_advocate.store as store_module
import agent_advocate.service as service_module
from agent_advocate.service import (
    MAX_LOCAL_EVIDENCE_BYTES,
    initialize,
    observe,
    start,
    status,
)
from agent_advocate.store import (
    PENDING_EVIDENCE_PREFIX,
    PENDING_EVIDENCE_SUFFIX,
    SetupError,
    Store,
)


ROOT = Path(__file__).resolve().parents[1]


def invoke(
    data_dir: Path, *arguments: str, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "agent_advocate.cli", "--data-dir", str(data_dir), *arguments],
        cwd=cwd or ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def git_project(path: Path) -> Path:
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path


def future() -> str:
    return (datetime.now(UTC) + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")


def windows_system_binary(name: str) -> Path:
    system_root = Path(os.environ["SystemRoot"]).resolve(strict=True)
    return (system_root / "System32" / name).resolve(strict=True)


def windows_current_account() -> str:
    result = subprocess.run(
        [str(windows_system_binary("whoami.exe"))],
        capture_output=True,
        check=True,
        text=True,
    )
    return result.stdout.strip().casefold()


def windows_acl_grants(path: Path) -> list[tuple[str, str]]:
    result = subprocess.run(
        [str(windows_system_binary("icacls.exe")), str(path)],
        capture_output=True,
        check=True,
        text=True,
    )
    grants: list[tuple[str, str]] = []
    path_text = str(path)
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if line.casefold().startswith(path_text.casefold()):
            line = line[len(path_text):].strip()
        if not line or ":" not in line or line.startswith("Successfully processed"):
            continue
        principal, permissions = line.split(":", 1)
        grants.append((principal.strip().casefold(), permissions))
    return grants


def assert_private_permissions(paths: tuple[Path, ...]) -> None:
    if os.name == "nt":
        account = windows_current_account()
        for path in paths:
            grants = windows_acl_grants(path)
            assert {principal for principal, _ in grants} == {account}
            assert all("(i)" not in permissions.casefold() for _, permissions in grants)
        return
    for path in paths:
        assert path.stat().st_mode & 0o077 == 0


def test_data_directory_inside_any_git_worktree_is_refused(tmp_path: Path) -> None:
    project = git_project(tmp_path / "project")
    with pytest.raises(SetupError, match="Git worktree"):
        initialize(Store(project / ".private"))
    result = invoke(project / ".private", "init")
    assert result.returncode == 2 and result.stdout == ""
    assert json.loads(result.stderr)["error"] == "setup_error"


def test_missing_and_stale_evidence_are_persisted_visibly_and_bounded(tmp_path: Path) -> None:
    project = git_project(tmp_path / "project")
    private = tmp_path / "private"
    store = Store(private)
    initialize(store)
    run, _ = start(
        store,
        {
            "project_path": str(project),
            "goal": "Check evidence",
            "acceptance": ["Evidence state is explicit"],
            "non_goals": [],
            "models": [],
            "next_check_at": future(),
            "deadline_at": None,
        },
    )
    source = project / "large-receipt.txt"
    source.write_text("x" * 9000, encoding="utf-8")
    captured_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    observation, _ = observe(
        store,
        run["run_id"],
        {
            "observation_id": str(uuid.uuid4()),
            "statement": "One evidence source changed and one is absent",
            "basis": "measured",
            "evidence": [
                {"kind": "local", "locator": str(source), "captured_at": captured_at, "excerpt": None, "sha256": "0" * 64},
            ],
            "pattern_key": None,
            "recommendation": None,
            "analysis_kind": "none",
            "assessor_id": None,
            "supersedes": None,
        },
    )
    directory = project / "not-a-receipt"
    directory.mkdir()
    observation, _ = observe(
        store,
        run["run_id"],
        {
            "observation_id": str(uuid.uuid4()),
            "statement": "A source is missing and a path is not a regular file",
            "basis": "measured",
            "evidence": [
                {"kind": "local", "locator": str(project / "missing.txt"), "captured_at": captured_at, "excerpt": None, "sha256": None},
                {"kind": "local", "locator": str(directory), "captured_at": captured_at, "excerpt": None, "sha256": None},
            ],
            "pattern_key": None,
            "recommendation": None,
            "analysis_kind": "none",
            "assessor_id": None,
            "supersedes": None,
        },
    )
    assert [item["availability"] for item in observation["evidence"]] == ["missing", "not-regular"]
    copies = list((private / "evidence").glob("*.evidence"))
    assert len(copies) == 1 and copies[0].stat().st_size == 8192
    assert_private_permissions((copies[0],))
    availability = status(store, run["run_id"])["evidence_availability"]
    assert [item["availability"] for item in availability] == ["stale", "missing", "not-regular"]


def test_out_of_project_local_evidence_is_refused_without_a_private_copy(tmp_path: Path) -> None:
    project = git_project(tmp_path / "project")
    private = tmp_path / "private"
    store = Store(private)
    initialize(store)
    run, _ = start(
        store,
        {
            "project_path": str(project),
            "goal": "Keep evidence within the project",
            "acceptance": ["Outside files are not read"],
            "non_goals": [],
            "models": [],
            "next_check_at": future(),
            "deadline_at": None,
        },
    )
    outside = tmp_path / "operator-secret.txt"
    outside.write_text("never ingest this", encoding="utf-8")
    request = {
        "observation_id": str(uuid.uuid4()),
        "statement": "Untrusted agent named an outside path",
        "basis": "reported",
        "evidence": [
            {
                "kind": "local",
                "locator": str(outside),
                "captured_at": future(),
                "excerpt": None,
                "sha256": None,
            }
        ],
        "pattern_key": None,
        "recommendation": None,
        "analysis_kind": "none",
        "assessor_id": None,
        "supersedes": None,
    }
    request_file = tmp_path / "outside-observation.json"
    request_file.write_text(json.dumps(request), encoding="utf-8")
    result = invoke(private, "observe", run["run_id"], "--file", str(request_file))
    assert result.returncode == 2 and result.stdout == ""
    assert json.loads(result.stderr)["error"] == "request_error"
    assert "within the run project_path" in json.loads(result.stderr)["message"]
    assert list((private / "evidence").glob("*.evidence")) == []
    missing_outside = dict(request)
    missing_outside["observation_id"] = str(uuid.uuid4())
    missing_outside["evidence"] = [
        {
            **request["evidence"][0],
            "locator": str(tmp_path / "absent-operator-secret.txt"),
        }
    ]
    missing_request_file = tmp_path / "missing-outside-observation.json"
    missing_request_file.write_text(json.dumps(missing_outside), encoding="utf-8")
    missing_result = invoke(private, "observe", run["run_id"], "--file", str(missing_request_file))
    assert missing_result.returncode == 2 and missing_result.stdout == ""
    assert json.loads(missing_result.stderr)["error"] == "request_error"
    assert list((private / "evidence").glob("*.evidence")) == []


def test_opened_evidence_handle_rejects_a_path_reparse_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = git_project(tmp_path / "project")
    private = tmp_path / "private"
    store = Store(private)
    initialize(store)
    run, _ = start(
        store,
        {
            "project_path": str(project),
            "goal": "Capture only the validated opened object",
            "acceptance": ["A mutable path cannot redirect evidence reads"],
            "non_goals": [],
            "models": [],
            "next_check_at": future(),
            "deadline_at": None,
        },
    )
    source_parent = project / "receipts"
    source_parent.mkdir()
    source = source_parent / "receipt.txt"
    source.write_bytes(b"validated in-project evidence")
    outside_parent = tmp_path / "outside-receipts"
    outside_parent.mkdir()
    (outside_parent / source.name).write_bytes(b"outside private secret")
    original_open = service_module._open_evidence_descriptor
    swapped = False

    def swap_path_then_open(path):
        nonlocal swapped
        if not swapped:
            displaced = project / "original-receipts"
            source_parent.rename(displaced)
            if os.name == "nt":
                subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(source_parent), str(outside_parent)],
                    capture_output=True,
                    check=True,
                    text=True,
                )
            else:
                source_parent.symlink_to(outside_parent, target_is_directory=True)
            swapped = True
        return original_open(path)

    monkeypatch.setattr(service_module, "_open_evidence_descriptor", swap_path_then_open)
    with pytest.raises(service_module.RequestError, match="within the run project_path"):
        observe(
            store,
            run["run_id"],
            {
                "observation_id": str(uuid.uuid4()),
                "statement": "Reject a path redirected outside after validation",
                "basis": "measured",
                "evidence": [
                    {
                        "kind": "local",
                        "locator": str(source),
                        "captured_at": future(),
                        "excerpt": None,
                        "sha256": None,
                    }
                ],
                "pattern_key": None,
                "recommendation": None,
                "analysis_kind": "none",
                "assessor_id": None,
                "supersedes": None,
            },
        )
    assert swapped
    assert list((private / "evidence").glob("*.evidence")) == []


def test_oversized_local_evidence_is_visible_without_reading_or_copying(tmp_path: Path) -> None:
    project = git_project(tmp_path / "project")
    private = tmp_path / "private"
    store = Store(private)
    initialize(store)
    run, _ = start(
        store,
        {
            "project_path": str(project),
            "goal": "Bound evidence reads",
            "acceptance": ["Oversized sources are visible"],
            "non_goals": [],
            "models": [],
            "next_check_at": future(),
            "deadline_at": None,
        },
    )
    source = project / "oversized.bin"
    with source.open("wb") as handle:
        handle.truncate(MAX_LOCAL_EVIDENCE_BYTES + 1)
    observation, _ = observe(
        store,
        run["run_id"],
        {
            "observation_id": str(uuid.uuid4()),
            "statement": "Do not hash an oversized source",
            "basis": "measured",
            "evidence": [{"kind": "local", "locator": str(source), "captured_at": future(), "excerpt": None, "sha256": None}],
            "pattern_key": None,
            "recommendation": None,
            "analysis_kind": "none",
            "assessor_id": None,
            "supersedes": None,
        },
    )
    assert observation["evidence"][0]["availability"] == "too-large"
    assert list((private / "evidence").glob("*.evidence")) == []


def test_local_evidence_that_grows_during_hashing_is_not_captured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = git_project(tmp_path / "project")
    private = tmp_path / "private"
    store = Store(private)
    initialize(store)
    run, _ = start(
        store,
        {
            "project_path": str(project),
            "goal": "Reject changing evidence",
            "acceptance": ["A changing source has no digest or private copy"],
            "non_goals": [],
            "models": [],
            "next_check_at": future(),
            "deadline_at": None,
        },
    )
    source = project / "growing.bin"
    source.write_bytes(b"a" * (128 * 1024))
    original_read = service_module._read_evidence_block
    grew = False

    def grow_after_first_read(handle, size):
        nonlocal grew
        block = original_read(handle, size)
        if block and not grew:
            with source.open("ab") as writer:
                writer.write(b"growth")
            grew = True
        return block

    monkeypatch.setattr(service_module, "_read_evidence_block", grow_after_first_read)
    observation, _ = observe(
        store,
        run["run_id"],
        {
            "observation_id": str(uuid.uuid4()),
            "statement": "Do not retain a moving source",
            "basis": "measured",
            "evidence": [{"kind": "local", "locator": str(source), "captured_at": future(), "excerpt": None, "sha256": None}],
            "pattern_key": None,
            "recommendation": None,
            "analysis_kind": "none",
            "assessor_id": None,
            "supersedes": None,
        },
    )
    assert grew
    assert observation["evidence"][0]["availability"] == "changed"
    assert list((private / "evidence").glob("*.evidence")) == []


def test_home_and_filesystem_root_cannot_be_registered_as_projects(tmp_path: Path) -> None:
    private = tmp_path / "private"
    assert invoke(private, "init").returncode == 0
    for label, path in (("home", Path.home()), ("root", Path(Path.home().anchor))):
        request = tmp_path / f"{label}-run.json"
        request.write_text(
            json.dumps(
                {
                    "project_path": str(path),
                    "goal": "Reject a broad evidence boundary",
                    "acceptance": ["The request error is explicit"],
                    "non_goals": [],
                    "models": [],
                    "next_check_at": future(),
                    "deadline_at": None,
                }
            ),
            encoding="utf-8",
        )
        result = invoke(private, "start", "--file", str(request))
        assert result.returncode == 2 and result.stdout == ""
        error = json.loads(result.stderr)
        assert error["error"] == "request_error"
        assert "filesystem root or user home" in error["message"]


def test_private_store_permissions_and_incomplete_initialization_are_explicit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private = tmp_path / "private"
    private.mkdir()
    store = Store(private)
    initialize(store)
    assert_private_permissions((private, private / "evidence", private / "logs", private / "advocate.sqlite3"))

    if os.name == "nt":
        arbitrary = tmp_path / "arbitrary-explicit-grant"
        arbitrary.mkdir()
        subprocess.run(
            [
                str(windows_system_binary("icacls.exe")),
                str(arbitrary),
                "/grant:r",
                "*S-1-5-32-546:(OI)(CI)(F)",
            ],
            capture_output=True,
            check=True,
            text=True,
        )
        initialize(Store(arbitrary))
        assert_private_permissions(
            (arbitrary, arbitrary / "evidence", arbitrary / "logs", arbitrary / "advocate.sqlite3")
        )

        insecure = tmp_path / "insecure"
        insecure.mkdir()
        subprocess.run(
            [
                str(windows_system_binary("icacls.exe")),
                str(insecure),
                "/grant:r",
                "*S-1-1-0:(OI)(CI)(F)",
            ],
            capture_output=True,
            check=True,
            text=True,
        )
        monkeypatch.setattr(store_module, "_restrict_windows_path", lambda path, directory: None)
        initialize(Store(insecure))
        with pytest.raises(AssertionError):
            assert_private_permissions(
                (insecure, insecure / "evidence", insecure / "logs", insecure / "advocate.sqlite3")
            )
        monkeypatch.undo()

    incomplete = tmp_path / "incomplete"
    incomplete.mkdir()
    (incomplete / "advocate.sqlite3").write_bytes(b"")
    interrupted = Store(incomplete)
    with pytest.raises(SetupError, match="initialization is incomplete"):
        interrupted.require_ready()
    initialize(interrupted)
    interrupted.require_ready()


def test_missing_public_seed_and_another_process_pending_evidence_are_handled_safely(
    tmp_path: Path,
) -> None:
    private = tmp_path / "private"
    store = Store(private)
    initialized = initialize(store, tmp_path / "data" / "seed-patterns.json")
    assert initialized["seed_patterns_imported"] == 0
    stranded = store.evidence_dir / f"{PENDING_EVIDENCE_PREFIX}interrupted{PENDING_EVIDENCE_SUFFIX}"
    stranded.write_bytes(b"private partial excerpt")
    Store(private).prepare_evidence_directory()
    assert stranded.exists()
    stranded.unlink()


def test_windows_acl_setup_ignores_a_planted_whoami_executable(tmp_path: Path) -> None:
    if os.name != "nt":
        return
    project = git_project(tmp_path / "project")
    private = tmp_path / "private"
    shutil.copyfile(windows_system_binary("hostname.exe"), project / "whoami.exe")
    initialized = invoke(private, "init", cwd=project)
    assert initialized.returncode == 0, initialized.stderr
    assert json.loads(initialized.stdout)["data_dir"] == str(private.resolve())


def test_lexical_git_worktree_path_is_refused_when_a_link_points_outside(tmp_path: Path) -> None:
    project = git_project(tmp_path / "project")
    outside = tmp_path / "outside"
    outside.mkdir()
    linked = project / "linked-private"
    if os.name == "nt":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(linked), str(outside)],
            check=True,
            capture_output=True,
            text=True,
        )
    else:
        linked.symlink_to(outside, target_is_directory=True)
    with pytest.raises(SetupError, match="Git worktree"):
        initialize(Store(linked / "store"))


def test_evidence_and_database_failures_return_structured_cli_errors(tmp_path: Path) -> None:
    project = git_project(tmp_path / "project")
    private = tmp_path / "private"
    assert invoke(private, "init").returncode == 0
    run_file = tmp_path / "run.json"
    run_file.write_text(
        json.dumps(
            {
                "project_path": str(project),
                "goal": "Exercise private-store errors",
                "acceptance": ["Errors are JSON"],
                "non_goals": [],
                "models": [],
                "next_check_at": future(),
                "deadline_at": None,
            }
        ),
        encoding="utf-8",
    )
    started = invoke(private, "start", "--file", str(run_file))
    run_id = json.loads(started.stdout)["run_id"]
    source = project / "receipt.txt"
    source.write_text("receipt", encoding="utf-8")
    observation_file = tmp_path / "observation.json"
    observation_file.write_text(
        json.dumps(
            {
                "observation_id": str(uuid.uuid4()),
                "statement": "Store evidence safely",
                "basis": "measured",
                "evidence": [
                    {
                        "kind": "local",
                        "locator": str(source),
                        "captured_at": future(),
                        "excerpt": None,
                        "sha256": None,
                    }
                ],
                "pattern_key": None,
                "recommendation": None,
                "analysis_kind": "none",
                "assessor_id": None,
                "supersedes": None,
            }
        ),
        encoding="utf-8",
    )
    (private / "evidence").rmdir()
    (private / "evidence").write_text("not a directory", encoding="utf-8")
    evidence_failure = invoke(private, "observe", run_id, "--file", str(observation_file))
    assert evidence_failure.returncode == 3 and evidence_failure.stdout == ""
    assert json.loads(evidence_failure.stderr)["error"] == "store_unavailable"

    database = private / "advocate.sqlite3"
    database.write_text("not a database", encoding="utf-8")
    database_failure = invoke(private, "status", run_id)
    assert database_failure.returncode == 3 and database_failure.stdout == ""
    assert json.loads(database_failure.stderr)["error"] == "store_unavailable"


def test_row_corruption_returns_a_fixed_private_safe_error(tmp_path: Path) -> None:
    project = git_project(tmp_path / "project")
    private = tmp_path / "private"
    assert invoke(private, "init").returncode == 0
    run_file = tmp_path / "run.json"
    run_file.write_text(
        json.dumps(
            {
                "project_path": str(project),
                "goal": "Exercise row corruption",
                "acceptance": ["No traceback leaks private data"],
                "non_goals": [],
                "models": [],
                "next_check_at": future(),
                "deadline_at": None,
            }
        ),
        encoding="utf-8",
    )
    run_id = json.loads(invoke(private, "start", "--file", str(run_file)).stdout)["run_id"]
    with sqlite3.connect(private / "advocate.sqlite3") as connection:
        connection.execute("UPDATE runs SET spec_json = ? WHERE run_id = ?", ('{"goal":"SECRET-ROW"', run_id))
    corrupted = invoke(private, "status", run_id)
    assert corrupted.returncode == 3 and corrupted.stdout == ""
    error = json.loads(corrupted.stderr)
    assert error == {
        "error": "store_unavailable",
        "message": "private store operation failed; preserve this directory for diagnosis",
    }
