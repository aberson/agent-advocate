from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path
import sqlite3
import subprocess
from threading import Barrier
import uuid

import pytest

from agent_advocate.service import (
    checkpoint,
    evaluate_alerts,
    finish,
    initialize,
    revise_alert,
    start,
    status,
)
from agent_advocate.store import RequestError, Store
from agent_advocate.watch import DueCondition, due_conditions, watch_foreground


BASE = datetime(2040, 1, 1, tzinfo=UTC)


def timestamp(seconds: int) -> str:
    return (BASE + timedelta(seconds=seconds)).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def git_project(path: Path) -> Path:
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path


def run_spec(project: Path, *, next_at: int = 10, deadline_at: int | None = None) -> dict[str, object]:
    return {
        "run_id": str(uuid.uuid4()),
        "project_path": str(project),
        "goal": "Exercise deterministic watchdog behavior",
        "acceptance": ["One alert is enough"],
        "non_goals": ["Model calls"],
        "models": [],
        "next_check_at": timestamp(next_at),
        "deadline_at": timestamp(deadline_at) if deadline_at is not None else None,
    }


def prepared_store(tmp_path: Path, **spec_options: int | None) -> tuple[Store, dict[str, object]]:
    store = Store(tmp_path / "private")
    initialize(store)
    run, _ = start(store, run_spec(git_project(tmp_path / "project"), **spec_options), timestamp(0))
    return store, run


def test_pure_due_conditions_are_clock_driven_and_pause_or_finish_suppresses_them() -> None:
    run = {
        "state": "active",
        "next_check_at": timestamp(10),
        "deadline_at": timestamp(20),
    }
    assert due_conditions(run, timestamp(10)) == []
    assert due_conditions(run, timestamp(21)) == [
        DueCondition("checkpoint-overdue", timestamp(10)),
        DueCondition("deadline-overdue", timestamp(20)),
    ]
    for state in ("paused", "finished"):
        run["state"] = state
        assert due_conditions(run, timestamp(21)) == []


def test_due_alert_is_persistent_deduplicated_and_snoozes_then_renotifies_once(tmp_path: Path) -> None:
    store, run = prepared_store(tmp_path)
    first_run, first_notifications = evaluate_alerts(store, run["run_id"], timestamp(11))
    assert first_run["state"] == "active"
    assert len(first_notifications) == 1
    alert_id = first_notifications[0]["alert_id"]
    assert first_notifications[0]["kind"] == "checkpoint-overdue"

    with store.read_connection() as conn:
        event_count = conn.execute("SELECT COUNT(*) FROM events WHERE run_id = ?", (run["run_id"],)).fetchone()[0]
    _, duplicate_notifications = evaluate_alerts(store, run["run_id"], timestamp(12))
    assert duplicate_notifications == []
    with store.read_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM events WHERE run_id = ?", (run["run_id"],)).fetchone()[0] == event_count
    persisted = status(store, run["run_id"])["alerts"]
    assert len(persisted) == 1
    assert persisted[0]["alert_id"] == alert_id
    assert persisted[0]["last_seen_at"] == timestamp(12)

    snoozed = revise_alert(
        store,
        alert_id,
        "snooze",
        "Waiting for the next declared visibility point",
        timestamp(20),
        timestamp(12),
    )
    assert snoozed["disposition"] == "snoozed"
    _, before_expiry = evaluate_alerts(store, run["run_id"], timestamp(19))
    assert before_expiry == []
    _, at_expiry = evaluate_alerts(store, run["run_id"], timestamp(20))
    assert at_expiry and at_expiry[0]["alert_id"] == alert_id
    _, afterwards = evaluate_alerts(store, run["run_id"], timestamp(21))
    assert afterwards == []


def test_snooze_rechecks_future_time_after_waiting_for_write_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, run = prepared_store(tmp_path)
    alert_id = evaluate_alerts(store, run["run_id"], timestamp(11))[1][0]["alert_id"]
    monkeypatch.setattr("agent_advocate.store.utc_now", lambda: timestamp(20))
    with pytest.raises(RequestError, match="future"):
        revise_alert(store, alert_id, "snooze", "Short snooze expired", timestamp(19))
    assert store.alerts_for_run(run["run_id"])[0]["disposition"] == "open"


def test_stale_poll_does_not_move_last_seen_backwards(tmp_path: Path) -> None:
    store, run = prepared_store(tmp_path)
    alert_id = evaluate_alerts(store, run["run_id"], timestamp(11))[1][0]["alert_id"]
    revise_alert(store, alert_id, "acknowledge", "Seen", now=timestamp(20))
    assert evaluate_alerts(store, run["run_id"], timestamp(12))[1] == []
    assert store.alerts_for_run(run["run_id"])[0]["last_seen_at"] == timestamp(20)


def test_competing_watch_evaluations_claim_one_normal_notification(tmp_path: Path) -> None:
    store, run = prepared_store(tmp_path)
    barrier = Barrier(2)

    def evaluate() -> list[dict[str, object]]:
        barrier.wait()
        return evaluate_alerts(store, run["run_id"], timestamp(11))[1]

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: evaluate(), range(2)))
    notifications = [alert for result in results for alert in result]
    assert len(notifications) == 1
    assert len(store.alerts_for_run(run["run_id"], unresolved_only=False)) == 1


def test_acknowledge_and_dismiss_are_persistent_explicit_dispositions(tmp_path: Path) -> None:
    store, run = prepared_store(tmp_path)
    _, notifications = evaluate_alerts(store, run["run_id"], timestamp(11))
    alert_id = notifications[0]["alert_id"]
    acknowledged = revise_alert(
        store, alert_id, "acknowledge", "The coordinator has seen this", now=timestamp(12)
    )
    assert acknowledged["disposition"] == "acknowledged"
    _, after_acknowledgement = evaluate_alerts(store, run["run_id"], timestamp(13))
    assert after_acknowledgement == []
    with pytest.raises(RequestError, match="reason"):
        revise_alert(store, alert_id, "dismiss", "", now=timestamp(14))
    dismissed = revise_alert(
        store, alert_id, "dismiss", "The expectation is intentionally superseded", now=timestamp(14)
    )
    assert dismissed["disposition"] == "dismissed"
    assert status(store, run["run_id"])["alerts"] == []


def test_pause_resume_preserves_deadline_and_finish_resolves_monitoring(tmp_path: Path) -> None:
    store, run = prepared_store(tmp_path, next_at=5, deadline_at=10)
    checkpoint(
        store,
        run["run_id"],
        {
            "event_id": str(uuid.uuid4()),
            "state": "paused",
            "summary": "Operator intentionally paused the work",
            "next_check_at": timestamp(5),
        },
        timestamp(2),
    )
    _, while_paused = evaluate_alerts(store, run["run_id"], timestamp(11))
    assert while_paused == []
    checkpoint(
        store,
        run["run_id"],
        {
            "event_id": str(uuid.uuid4()),
            "state": "active",
            "summary": "Work resumed with a future visibility point",
            "next_check_at": timestamp(100),
        },
        timestamp(11),
    )
    resumed, resumed_notifications = evaluate_alerts(store, run["run_id"], timestamp(12))
    assert resumed["deadline_at"] == timestamp(10)
    assert [item["kind"] for item in resumed_notifications] == ["deadline-overdue"]

    finish(store, run["run_id"], "stopped", "The bounded work was stopped", timestamp(13))
    finished, after_finish = evaluate_alerts(store, run["run_id"], timestamp(14))
    assert finished["state"] == "finished"
    assert after_finish == []
    all_alerts = store.alerts_for_run(run["run_id"], unresolved_only=False)
    assert all_alerts[0]["disposition"] == "resolved"


def test_changed_expectation_resolves_the_old_alert_and_alert_actions_validate(tmp_path: Path) -> None:
    store, run = prepared_store(tmp_path)
    _, notifications = evaluate_alerts(store, run["run_id"], timestamp(11))
    alert_id = notifications[0]["alert_id"]
    checkpoint(
        store,
        run["run_id"],
        {
            "event_id": str(uuid.uuid4()),
            "state": "paused",
            "summary": "Move the recorded expectation while paused",
            "next_check_at": timestamp(100),
        },
        timestamp(12),
    )
    assert status(store, run["run_id"])["alerts"] == []
    assert store.alerts_for_run(run["run_id"], unresolved_only=False)[0]["disposition"] == "resolved"
    _, suppressed = evaluate_alerts(store, run["run_id"], timestamp(13))
    assert suppressed == []
    checkpoint(
        store,
        run["run_id"],
        {
            "event_id": str(uuid.uuid4()),
            "state": "active",
            "summary": "Resume with a replacement visibility expectation",
            "next_check_at": timestamp(100),
        },
        timestamp(14),
    )
    assert status(store, run["run_id"])["alerts"] == []
    assert store.alerts_for_run(run["run_id"], unresolved_only=False)[0]["disposition"] == "resolved"
    with pytest.raises(RequestError, match="resolved"):
        revise_alert(store, alert_id, "acknowledge", "Too late", now=timestamp(13))
    with pytest.raises(RequestError, match="snooze requires"):
        revise_alert(store, str(uuid.uuid4()), "snooze", "Need time", now=timestamp(13))


def test_init_upgrades_existing_version_one_store_without_losing_run(tmp_path: Path) -> None:
    store, run = prepared_store(tmp_path)
    with sqlite3.connect(store.database_path) as conn:
        conn.execute("DROP TABLE alerts")
    store.initialize()
    assert store.run(run["run_id"])["next_check_at"] == timestamp(10)
    assert evaluate_alerts(store, run["run_id"], timestamp(11))[1][0]["kind"] == "checkpoint-overdue"


def test_foreground_interrupt_only_stops_the_watcher_and_keeps_the_run(tmp_path: Path) -> None:
    store, run = prepared_store(tmp_path, next_at=100)
    transcript = StringIO()

    def interrupted_sleep(_: float) -> None:
        raise KeyboardInterrupt

    watch_foreground(
        store,
        run["run_id"],
        interval=0.01,
        clock=lambda: timestamp(1),
        sleep=interrupted_sleep,
        output=transcript,
    )
    assert "Watcher stopped" in transcript.getvalue()
    assert status(store, run["run_id"])["run"]["state"] == "active"


def test_watch_shows_effective_recorded_state_segments(tmp_path: Path) -> None:
    store, run = prepared_store(tmp_path, next_at=5)
    for at, state in ((2, "waiting"), (4, "checking"), (3, "active")):
        checkpoint(
            store,
            run["run_id"],
            {
                "event_id": str(uuid.uuid4()),
                "state": state,
                "summary": f"Recorded {state}",
                "next_check_at": timestamp(5),
            },
            timestamp(at),
        )
    transcript = StringIO()
    watch_foreground(store, run["run_id"], once=True, clock=lambda: timestamp(6), output=transcript)
    segments = status(store, run["run_id"])["state_segments"]
    assert [(item["state"], item["since"]) for item in segments] == [
        ("active", timestamp(0)),
        ("waiting", timestamp(2)),
        ("checking", timestamp(4)),
    ]
    assert "recorded-segments=active@" in transcript.getvalue()
    assert "age=2s" in transcript.getvalue()
    assert "Attached with" not in transcript.getvalue()


def test_watch_escapes_control_characters_in_displayed_data_path(tmp_path: Path) -> None:
    store, run = prepared_store(tmp_path, next_at=100)
    store.data_dir = Path(str(store.data_dir) + "\x1b[31m\n")
    transcript = StringIO()
    watch_foreground(store, run["run_id"], once=True, clock=lambda: timestamp(1), output=transcript)
    assert "\\x1b[31m\\n" in transcript.getvalue()
    assert "\x1b" not in transcript.getvalue()
