"""Pure overdue decisions and the foreground Agent Advocate watcher."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import math
import sys
import time
from typing import Any, TextIO

from .service import _uuid, evaluate_alerts
from .store import FINISHED_RUN_STATE, RequestError, Store, parse_utc_timestamp, utc_now


DEFAULT_INTERVAL_SECONDS = 60.0


@dataclass(frozen=True)
class DueCondition:
    """One stable alert identity derived from a run's current expectations."""

    kind: str
    expectation_at: str

    def as_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "expectation_at": self.expectation_at}


def due_conditions(run: Mapping[str, Any], now: str) -> list[DueCondition]:
    """Return overdue conditions for a clock value without reading or writing state."""

    if run["state"] in {"paused", FINISHED_RUN_STATE}:
        return []
    observed_at = parse_utc_timestamp(now)
    conditions: list[DueCondition] = []
    next_check_at = run["next_check_at"]
    if observed_at > parse_utc_timestamp(next_check_at):
        conditions.append(DueCondition("checkpoint-overdue", next_check_at))
    deadline_at = run["deadline_at"]
    if deadline_at is not None and observed_at > parse_utc_timestamp(deadline_at):
        conditions.append(DueCondition("deadline-overdue", deadline_at))
    return conditions


def positive_interval(value: str) -> float:
    """Argparse converter for the configurable watch poll interval."""

    try:
        interval = float(value)
    except ValueError as error:
        raise RequestError("watch interval must be a positive number of seconds") from error
    if not math.isfinite(interval) or interval <= 0:
        raise RequestError("watch interval must be a positive number of seconds")
    return interval


def watch_foreground(
    store: Store,
    run_id: str,
    interval: float = DEFAULT_INTERVAL_SECONDS,
    *,
    once: bool = False,
    bell: bool = False,
    clock: Callable[[], str] = utc_now,
    sleep: Callable[[float], None] = time.sleep,
    output: TextIO | None = None,
) -> None:
    """Attach one terminal to a run until stopped, finished, or interrupted.

    This deliberately makes no project, host, or model call.  Each invocation
    has its own foreground loop; SQLite owns notification claiming across them.
    """

    if not isinstance(interval, (int, float)) or not math.isfinite(interval) or interval <= 0:
        raise RequestError("watch interval must be a positive number of seconds")
    _uuid(run_id, "run_id")
    stream = output or sys.stdout
    _write(
        stream,
        f"Watching {run_id} in {str(store.data_dir)!r} every {_interval_label(float(interval))}. Ctrl+C stops this watcher only.",
    )
    announced_existing = False
    try:
        while True:
            if not announced_existing:
                existing = store.alerts_for_run(run_id)
                if existing:
                    _write(stream, f"Attached with {len(existing)} unresolved persisted alert(s); use status to inspect them.")
                announced_existing = True
            current, notifications = evaluate_alerts(store, run_id, clock())
            segments = store.state_segments_for_run(run_id) if notifications else []
            for alert in notifications:
                _write(stream, _format_alert(alert, current, segments) + ("\a" if bell else ""))
            if current["state"] == FINISHED_RUN_STATE:
                _write(stream, f"Run {run_id} is finished; watcher stopped.")
                return
            if once:
                return
            sleep(float(interval))
    except KeyboardInterrupt:
        _write(stream, f"Watcher stopped for {run_id}; the run and its private evidence were left intact.")


def _format_alert(
    alert: Mapping[str, Any], run: Mapping[str, Any], segments: list[dict[str, str]]
) -> str:
    now = parse_utc_timestamp(alert["last_seen_at"])
    current_segment = segments[-1] if segments and segments[-1]["state"] == run["state"] else None
    state_since_at = current_segment["since"] if current_segment else run["last_checkpoint_at"]
    state_since = parse_utc_timestamp(state_since_at)
    state_age = _duration_label(max(0.0, (now - state_since).total_seconds()))
    recorded_segments = ",".join(f"{item['state']}@{item['since']}" for item in segments)
    return (
        f"ALERT {alert['kind']} for {alert['run_id']}: expectation {alert['expectation_at']} is overdue; "
        f"state={run['state']} recorded-since={state_since_at} age={state_age}; "
        f"recorded-segments={recorded_segments}; "
        f"alert_id={alert['alert_id']}"
    )


def _duration_label(seconds: float) -> str:
    whole = int(seconds)
    minutes, seconds_part = divmod(whole, 60)
    hours, minutes_part = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes_part}m {seconds_part}s"
    if minutes:
        return f"{minutes}m {seconds_part}s"
    return f"{seconds_part}s"


def _interval_label(interval: float) -> str:
    if interval.is_integer():
        return f"{int(interval)} seconds"
    return f"{interval:g} seconds"


def _write(stream: TextIO, message: str) -> None:
    line = f"[{utc_now()}] {message}\n"
    try:
        stream.write(line)
    except UnicodeEncodeError:
        # A redirected Windows console may still use a legacy encoding. Keep
        # the selected path visible as escapes and continue watching.
        encoding = getattr(stream, "encoding", None) or "utf-8"
        stream.write(line.encode(encoding, errors="backslashreplace").decode(encoding))
    stream.flush()
