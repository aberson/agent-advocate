from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import subprocess
import sys
from threading import Barrier
import time
import uuid

import pytest

from agent_advocate.service import (
    brief,
    checkpoint,
    finish,
    import_patterns,
    initialize,
    observe,
    set_pattern_disposition,
    start,
    status,
)
from agent_advocate.store import (
    ConflictError,
    PENDING_EVIDENCE_PREFIX,
    PENDING_EVIDENCE_SUFFIX,
    RequestError,
    Store,
)


def future() -> str:
    return (datetime.now(UTC) + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")


def git_project(path: Path) -> Path:
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path


def run_spec(project: Path, run_id: str | None = None) -> dict[str, object]:
    return {
        "run_id": run_id or str(uuid.uuid4()),
        "project_path": str(project),
        "goal": "Persist a bounded run",
        "acceptance": ["A durable receipt exists"],
        "non_goals": ["Model calls"],
        "models": [
            {
                "role": "coordinator",
                "requested_model": None,
                "observed_model": None,
                "effort": None,
                "host": "codex",
            }
        ],
        "next_check_at": future(),
        "deadline_at": None,
    }


def checkpoint_spec(event_id: str | None = None) -> dict[str, object]:
    return {
        "event_id": event_id or str(uuid.uuid4()),
        "state": "checking",
        "summary": "Receipt is being checked",
        "next_check_at": future(),
    }


def observation_spec(observation_id: str, evidence: list[dict[str, object]]) -> dict[str, object]:
    return {
        "observation_id": observation_id,
        "statement": "A source was supplied",
        "basis": "measured",
        "evidence": evidence,
        "pattern_key": None,
        "recommendation": None,
        "analysis_kind": "none",
        "assessor_id": None,
        "supersedes": None,
    }


def evidence(path: Path, digest: str | None = None) -> dict[str, object]:
    return {
        "kind": "local",
        "locator": str(path),
        "captured_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "excerpt": None,
        "sha256": digest,
    }


def test_run_checkpoint_observation_finish_and_exact_replays(tmp_path: Path) -> None:
    project = git_project(tmp_path / "project")
    store = Store(tmp_path / "private")
    initialize(store)
    spec = run_spec(project)
    first, replay = start(store, spec)
    assert not replay
    again, replay = start(store, spec)
    assert replay and again["created_at"] == first["created_at"]

    event_id = str(uuid.uuid4())
    request = checkpoint_spec(event_id)
    changed, replay, _ = checkpoint(store, first["run_id"], request)
    retry, replay, _ = checkpoint(store, first["run_id"], request)
    assert changed["state"] == "checking"
    assert changed["next_check_at"] == request["next_check_at"]
    assert replay and retry["last_checkpoint_at"] == changed["last_checkpoint_at"]
    conflicting = dict(request)
    conflicting["state"] = "waiting"
    conflicting["summary"] = "Waiting for a receipt"
    with pytest.raises(ConflictError):
        checkpoint(store, first["run_id"], conflicting)

    source = project / "receipt.txt"
    source.write_text("checked", encoding="utf-8")
    observation_id = str(uuid.uuid4())
    observation_request = observation_spec(observation_id, [evidence(source)])
    saved, replay = observe(store, first["run_id"], observation_request)
    assert not replay and saved["evidence"][0]["availability"] == "current"
    saved_retry, replay = observe(store, first["run_id"], observation_request)
    assert replay and saved_retry == saved

    completed, replay = finish(store, first["run_id"], "completed", "Delivered")
    assert not replay and completed["state"] == "finished"
    completed_retry, replay = finish(store, first["run_id"], "completed", "Delivered")
    assert replay and completed_retry == completed
    with pytest.raises(ConflictError):
        finish(store, first["run_id"], "stopped", "Different outcome")
    with pytest.raises(RequestError, match="finished run"):
        checkpoint(store, first["run_id"], checkpoint_spec())
    assert status(store, first["run_id"])["run"]["state"] == "finished"


def test_conflicting_start_and_foreign_observation_are_rejected(tmp_path: Path) -> None:
    project = git_project(tmp_path / "project")
    store = Store(tmp_path / "private")
    initialize(store)
    spec = run_spec(project)
    first, _ = start(store, spec)
    second, _ = start(store, run_spec(project))
    conflicting = dict(spec)
    conflicting["goal"] = "Different goal"
    with pytest.raises(ConflictError):
        start(store, conflicting)
    with pytest.raises(RequestError):
        observe(store, str(uuid.uuid4()), observation_spec(str(uuid.uuid4()), []))
    source = project / "receipt.txt"
    source.write_text("private receipt", encoding="utf-8")
    request = observation_spec(str(uuid.uuid4()), [evidence(source)])
    observe(store, first["run_id"], request)
    linked_request = observation_spec(str(uuid.uuid4()), [])
    linked_request["supersedes"] = request["observation_id"]
    linked, replay = observe(store, first["run_id"], linked_request)
    assert not replay and linked["supersedes"] == request["observation_id"]
    foreign_supersedes = observation_spec(str(uuid.uuid4()), [])
    foreign_supersedes["supersedes"] = request["observation_id"]
    with pytest.raises(RequestError, match="supersedes"):
        observe(store, second["run_id"], foreign_supersedes)
    with pytest.raises(ConflictError, match="different run"):
        observe(store, second["run_id"], request)
    assert status(store, second["run_id"])["observations"] == []


def test_concurrent_writers_preserve_checkpoints_and_publish_one_evidence_copy(
    tmp_path: Path,
) -> None:
    project = git_project(tmp_path / "project")
    store = Store(tmp_path / "private")
    initialize(store)
    run, _ = start(store, run_spec(project))
    requests = [checkpoint_spec(str(uuid.uuid4())), checkpoint_spec(str(uuid.uuid4()))]
    barrier = Barrier(2)

    def write(request: dict[str, object]) -> tuple[dict[str, object], bool, str]:
        barrier.wait()
        return checkpoint(store, run["run_id"], request)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(write, requests))
    with store.read_connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM events WHERE run_id = ? AND kind = 'checkpoint'", (run["run_id"],)
        ).fetchone()[0]
    assert count == 2
    record = status(store, run["run_id"])
    assert record["latest_checkpoint"] is not None
    assert record["run"]["next_check_at"] in {
        request["next_check_at"] for request in requests
    }

    source = project / "concurrent-receipt.txt"
    source.write_text("one retained copy", encoding="utf-8")
    request = observation_spec(str(uuid.uuid4()), [evidence(source)])
    observation_barrier = Barrier(2)

    def write_observation() -> tuple[dict[str, object], bool]:
        observation_barrier.wait()
        return observe(store, run["run_id"], request)

    with ThreadPoolExecutor(max_workers=2) as executor:
        observation_results = list(executor.map(lambda _: write_observation(), range(2)))
    assert sorted(result[1] for result in observation_results) == [False, True]
    assert len(list((store.evidence_dir).glob("*.evidence"))) == 1
    assert len(status(store, run["run_id"])["observations"]) == 1


def test_real_cli_concurrent_initialization_is_idempotent(tmp_path: Path) -> None:
    private = tmp_path / "private"
    command = [
        sys.executable,
        "-m",
        "agent_advocate.cli",
        "--data-dir",
        str(private),
        "init",
    ]
    processes = [
        subprocess.Popen(
            command,
            cwd=Path(__file__).resolve().parents[1],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(6)
    ]
    results = [process.communicate(timeout=10) for process in processes]
    assert all(process.returncode == 0 for process in processes), results
    assert all(
        json.loads(stdout)["schema_version"] == 1 and stderr == ""
        for stdout, stderr in results
    )
    Store(private).require_ready()


def test_real_cli_concurrent_observations_preserve_every_evidence_copy(tmp_path: Path) -> None:
    project = git_project(tmp_path / "project")
    private = tmp_path / "private"
    store = Store(private)
    initialize(store)
    run, _ = start(store, run_spec(project))
    source = project / "receipt.txt"
    source.write_text("private concurrent receipt", encoding="utf-8")
    request_files = []
    observation_count = 8
    copies_per_observation = 6
    for _ in range(observation_count):
        request = observation_spec(
            str(uuid.uuid4()),
            [evidence(source) for _ in range(copies_per_observation)],
        )
        request_file = tmp_path / f"{request['observation_id']}.json"
        request_file.write_text(json.dumps(request), encoding="utf-8")
        request_files.append(request_file)
    locker = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import sqlite3, sys, time; "
            "connection = sqlite3.connect(sys.argv[1], timeout=0); "
            "connection.execute('BEGIN IMMEDIATE'); "
            "print('locked', flush=True); "
            "time.sleep(20)",
            str(store.database_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    observers: list[subprocess.Popen[str]] = []

    def pending_count() -> int:
        return len(
            list(store.evidence_dir.glob(f"{PENDING_EVIDENCE_PREFIX}*{PENDING_EVIDENCE_SUFFIX}"))
        )

    try:
        assert locker.stdout is not None
        assert locker.stdout.readline().strip() == "locked"
        observers = [
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "agent_advocate.cli",
                    "--data-dir",
                    str(private),
                    "observe",
                    run["run_id"],
                    "--file",
                    str(request_file),
                ],
                cwd=Path(__file__).resolve().parents[1],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for request_file in request_files
        ]
        expected_pending = observation_count * copies_per_observation
        deadline = time.monotonic() + 5
        while pending_count() < expected_pending and time.monotonic() < deadline:
            time.sleep(0.02)
        assert pending_count() == expected_pending
    finally:
        if locker.poll() is None:
            locker.terminate()
        locker.communicate(timeout=3)
    results = [observer.communicate(timeout=10) for observer in observers]
    assert all(observer.returncode == 0 for observer in observers), results
    assert all(
        json.loads(stdout)["idempotent"] is False and stderr == ""
        for stdout, stderr in results
    )
    assert len(status(store, run["run_id"])["observations"]) == observation_count
    with store.read_connection() as conn:
        event_count = conn.execute(
            "SELECT COUNT(*) FROM events WHERE run_id = ? AND kind = 'observation'",
            (run["run_id"],),
        ).fetchone()[0]
    assert event_count == observation_count
    assert len(list(store.evidence_dir.glob("*.evidence"))) == expected_pending


def test_orphaned_uncommitted_evidence_target_is_replaced_on_retry(tmp_path: Path) -> None:
    project = git_project(tmp_path / "project")
    store = Store(tmp_path / "private")
    initialize(store)
    run, _ = start(store, run_spec(project))
    source = project / "receipt.txt"
    source.write_text("replacement evidence", encoding="utf-8")
    observation_id = str(uuid.uuid4())
    target = store.evidence_dir / f"{observation_id}-0.evidence"
    target.write_text("orphaned interrupted evidence", encoding="utf-8")
    request = observation_spec(observation_id, [evidence(source)])
    saved, replay = observe(store, run["run_id"], request)
    assert not replay and saved["observation_id"] == observation_id
    assert target.read_text(encoding="utf-8") == "replacement evidence"
    retried, replay = observe(store, run["run_id"], request)
    assert replay and retried == saved


def test_cross_process_exclusive_lock_reports_bounded_contention_for_init_read_and_write(tmp_path: Path) -> None:
    project = git_project(tmp_path / "project")
    private = tmp_path / "private"
    store = Store(private)
    initialize(store)
    run, _ = start(store, run_spec(project))
    checkpoint_file = tmp_path / "checkpoint.json"
    checkpoint_file.write_text(json.dumps(checkpoint_spec()), encoding="utf-8")
    locker_code = (
        "import sqlite3, sys, time; "
        "connection = sqlite3.connect(sys.argv[1], timeout=0); "
        "connection.execute('BEGIN EXCLUSIVE'); "
        "print('locked', flush=True); "
        "time.sleep(9)"
    )

    def assert_contention(*arguments: str) -> None:
        locker = subprocess.Popen(
            [sys.executable, "-c", locker_code, str(store.database_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            assert locker.stdout is not None
            assert locker.stdout.readline().strip() == "locked"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agent_advocate.cli",
                    "--data-dir",
                    str(private),
                    *arguments,
                ],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
                check=False,
            )
            assert result.returncode == 4 and result.stdout == ""
            assert json.loads(result.stderr) == {
                "error": "contention",
                "message": "store is busy; retry this operation",
            }
        finally:
            if locker.poll() is None:
                locker.terminate()
            locker.communicate(timeout=3)

    assert_contention("init")
    assert_contention("status", run["run_id"])
    assert_contention("checkpoint", run["run_id"], "--file", str(checkpoint_file))


def test_stale_checkpoint_cannot_regress_projection_or_bypass_deadline_reason(
    tmp_path: Path,
) -> None:
    project = git_project(tmp_path / "project")
    store = Store(tmp_path / "private")
    initialize(store)
    run, _ = start(store, run_spec(project))
    base = datetime.now(UTC) + timedelta(hours=1)
    later_now = base.isoformat().replace("+00:00", "Z")
    later_next = (base + timedelta(minutes=30)).isoformat().replace("+00:00", "Z")
    newer_request = {
        "event_id": str(uuid.uuid4()),
        "state": "checking",
        "summary": "Newer checkpoint",
        "next_check_at": later_next,
    }
    newer, _, newer_event = checkpoint(store, run["run_id"], newer_request, later_now)

    earlier = base - timedelta(minutes=1)
    stale_request = {
        "event_id": str(uuid.uuid4()),
        "state": "waiting",
        "summary": "Writer waited for the lock",
        "next_check_at": (earlier + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
    }
    stale, replay, _ = checkpoint(
        store,
        run["run_id"],
        stale_request,
        earlier.isoformat().replace("+00:00", "Z"),
    )
    assert not replay
    assert stale["last_checkpoint_at"] == newer["last_checkpoint_at"]
    assert stale["next_check_at"] == newer["next_check_at"]
    assert status(store, run["run_id"])["latest_checkpoint"]["event_id"] == newer_event

    deadline = (base + timedelta(hours=2)).isoformat().replace("+00:00", "Z")
    checkpoint(
        store,
        run["run_id"],
        {
            "event_id": str(uuid.uuid4()),
            "state": "active",
            "summary": "Set an overall deadline",
            "next_check_at": (base + timedelta(minutes=45)).isoformat().replace("+00:00", "Z"),
            "deadline_at": deadline,
            "deadline_reason": "Coordinator committed a deadline",
        },
        (base + timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
    )
    with pytest.raises(RequestError, match="deadline replacement"):
        checkpoint(
            store,
            run["run_id"],
            {
                "event_id": str(uuid.uuid4()),
                "state": "active",
                "summary": "Attempt an unreasoned deadline change",
                "next_check_at": (base + timedelta(minutes=50)).isoformat().replace("+00:00", "Z"),
                "deadline_at": None,
            },
            (base + timedelta(minutes=2)).isoformat().replace("+00:00", "Z"),
        )


def test_pattern_import_preserves_private_disposition_and_brief_is_bounded(tmp_path: Path) -> None:
    project = git_project(tmp_path / "project")
    store = Store(tmp_path / "private")
    initialize(store)
    run, _ = start(store, run_spec(project))
    patterns = [
        {
            "pattern_key": f"pattern-{number}",
            "summary": f"Pattern {number}",
            "trigger": "A visible trigger",
            "scope": {"roles": [], "models": [], "hosts": [], "tags": []},
            "basis": "official-guidance",
            "sources": [],
            "owner": "coordinator",
            "action": "Check the receipt",
            "disposition": "candidate",
            "review_after": None,
            "reason": "Imported public guidance",
        }
        for number in range(8)
    ]
    patterns[0]["scope"] = {"roles": ["coordinator"], "models": [], "hosts": [], "tags": []}
    patterns[1]["scope"] = {"roles": ["reviewer"], "models": [], "hosts": [], "tags": []}
    patterns[2]["scope"] = {"roles": [], "models": [], "hosts": [], "tags": ["unavailable"]}
    changed, count = import_patterns(store, patterns)
    assert count == 8
    assert len(changed) == 8
    revised = set_pattern_disposition(store, "pattern-0", "fix-applied", "Private receipt")
    assert revised["disposition"] == "fix-applied"
    changed, count = import_patterns(store, patterns)
    assert count == 0
    assert changed == []
    result = brief(store, run["run_id"])
    assert len(result["patterns"]) == 5
    assert result["patterns"][0]["disposition"] == "fix-applied"
    keys = {pattern["pattern_key"] for pattern in result["patterns"]}
    assert "pattern-0" in keys
    assert "pattern-1" not in keys
    assert "pattern-2" not in keys
