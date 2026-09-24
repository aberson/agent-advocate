from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid


ROOT = Path(__file__).resolve().parents[1]


def invoke(data_dir: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "agent_advocate.cli", "--data-dir", str(data_dir), *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def git_project(path: Path) -> Path:
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path


def test_real_watch_process_persists_one_alert_across_competing_watchers_and_restart(
    tmp_path: Path,
) -> None:
    private = tmp_path / "private"
    project = git_project(tmp_path / "project")
    assert invoke(private, "init").returncode == 0
    run_id = str(uuid.uuid4())
    due_at = (datetime.now(UTC) + timedelta(seconds=5)).isoformat().replace("+00:00", "Z")
    request = tmp_path / "run.json"
    request.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "project_path": str(project),
                "goal": "Short real watchdog smoke",
                "acceptance": ["A due checkpoint is visible once"],
                "non_goals": ["A daemon"],
                "models": [],
                "next_check_at": due_at,
                "deadline_at": None,
            }
        ),
        encoding="utf-8",
    )
    started = invoke(private, "start", "--file", str(request))
    assert started.returncode == 0, started.stderr

    # Start both foreground loops before the expectation is due. Their later
    # polls must compete for one notification, and finish must stop both.
    command = [
        sys.executable,
        "-m",
        "agent_advocate.cli",
        "--data-dir",
        str(private),
        "watch",
        run_id,
        "--interval",
        "0.1",
    ]
    watchers = [
        subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(2)
    ]
    try:
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            fresh_status = invoke(private, "status", run_id)
            assert fresh_status.returncode == 0, fresh_status.stderr
            alerts = json.loads(fresh_status.stdout)["alerts"]
            if alerts:
                break
            time.sleep(0.05)
        assert len(alerts) == 1
        alert_id = alerts[0]["alert_id"]

        # A fresh process reads the shared store, and a restarted watcher does
        # not reprint the unchanged condition.
        restarted = invoke(private, "watch", run_id, "--interval", "0.1", "--once")
        assert restarted.returncode == 0, restarted.stderr
        assert "ALERT checkpoint-overdue" not in restarted.stdout
        retained = json.loads(invoke(private, "status", run_id).stdout)["alerts"]
        assert retained[0]["alert_id"] == alert_id

        finished = invoke(private, "finish", run_id, "--outcome", "completed", "--summary", "Smoke finished")
        assert finished.returncode == 0, finished.stderr
        results = [watcher.communicate(timeout=10) for watcher in watchers]
        assert all(watcher.returncode == 0 for watcher in watchers), results
        assert sum(stdout.count("ALERT checkpoint-overdue") for stdout, _ in results) == 1
        assert all(stderr == "" for _, stderr in results)
        assert all("watcher stopped" in stdout for stdout, _ in results)
    finally:
        for watcher in watchers:
            if watcher.poll() is None:
                watcher.kill()
                watcher.communicate(timeout=10)


def test_watch_missing_store_exits_with_a_visible_setup_error(tmp_path: Path) -> None:
    result = invoke(tmp_path / "missing-private", "watch", str(uuid.uuid4()), "--once")
    assert result.returncode == 2 and " Watching " in result.stdout
    error = json.loads(result.stderr)
    assert error["error"] == "setup_error"
    assert "not initialized" in error["message"]


def test_watch_with_legacy_stdout_encoding_keeps_running(tmp_path: Path) -> None:
    private = tmp_path / "private-\U0001f600"
    assert invoke(private, "init").returncode == 0
    result = subprocess.run(
        [
            sys.executable, "-m", "agent_advocate.cli", "--data-dir", str(private),
            "watch", str(uuid.uuid4()), "--once",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONIOENCODING": "ascii:strict"},
        check=False,
    )
    assert result.returncode == 2
    assert "Watching " in result.stdout
    assert "\\U0001f600" in result.stdout
    assert json.loads(result.stderr)["error"] == "request_error"


def test_watch_rejects_control_characters_before_terminal_output(tmp_path: Path) -> None:
    private = tmp_path / "private"
    assert invoke(private, "init").returncode == 0
    result = invoke(private, "watch", "\x1b[31mnot-a-run", "--once")
    assert result.returncode == 2
    assert result.stdout == ""
    assert json.loads(result.stderr)["error"] == "request_error"
