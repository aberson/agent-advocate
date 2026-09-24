"""The Agent Advocate command-line interface."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from typing import Any, TextIO

from . import __version__
from .skill_install import install_skills, skills_status, uninstall_skills
from .service import (
    brief,
    checkpoint,
    finish,
    import_patterns,
    initialize,
    observe,
    public_observation,
    public_pattern,
    read_json_file,
    revise_alert,
    set_pattern_disposition,
    start,
    status,
)
from .store import AdvocateError, RequestError, Store, resolve_data_dir
from .watch import DEFAULT_INTERVAL_SECONDS, positive_interval, watch_foreground


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise RequestError(message)


def build_parser() -> argparse.ArgumentParser:
    parser = JsonArgumentParser(prog="agent-advocate", description="Private Agent Advocate store")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--data-dir", metavar="PATH", help="private store directory")
    commands = parser.add_subparsers(dest="command", required=True)
    skills_parser = commands.add_parser("skills", help="manage user-scoped Codex skills")
    skill_commands = skills_parser.add_subparsers(dest="skills_command", required=True)
    install_parser = skill_commands.add_parser("install", help="install or refresh all five skills")
    install_parser.add_argument("--source-checkout", required=True, metavar="PATH")
    skill_commands.add_parser("status", help="check ownership and source bindings")
    skill_commands.add_parser("uninstall", help="remove owned skills")
    commands.add_parser("init", help="create the private store")
    start_parser = commands.add_parser("start", help="register an advocated run")
    start_parser.add_argument("--file", required=True, metavar="PATH")
    checkpoint_parser = commands.add_parser("checkpoint", help="record a checkpoint")
    checkpoint_parser.add_argument("run_id")
    checkpoint_parser.add_argument("--file", required=True, metavar="PATH")
    status_parser = commands.add_parser("status", help="read a run")
    status_parser.add_argument("run_id")
    brief_parser = commands.add_parser("brief", help="read relevant cautions")
    brief_parser.add_argument("run_id")
    observe_parser = commands.add_parser("observe", help="record an observation")
    observe_parser.add_argument("run_id")
    observe_parser.add_argument("--file", required=True, metavar="PATH")
    patterns_parser = commands.add_parser("patterns", help="manage patterns")
    pattern_commands = patterns_parser.add_subparsers(dest="patterns_command", required=True)
    import_parser = pattern_commands.add_parser("import", help="import pattern records")
    import_parser.add_argument("--file", required=True, metavar="PATH")
    pattern_parser = commands.add_parser("pattern", help="change a pattern disposition")
    pattern_parser.add_argument("pattern_key")
    pattern_parser.add_argument("--disposition", required=True)
    pattern_parser.add_argument("--reason", required=True)
    pattern_parser.add_argument("--evidence", metavar="OBSERVATION_ID")
    finish_parser = commands.add_parser("finish", help="finish a run")
    finish_parser.add_argument("run_id")
    finish_parser.add_argument("--outcome", required=True)
    finish_parser.add_argument("--summary", required=True)
    alert_parser = commands.add_parser("alert", help="acknowledge, dismiss, or snooze an alert")
    alert_parser.add_argument("alert_id")
    alert_parser.add_argument("--action", required=True, choices=("acknowledge", "dismiss", "snooze"))
    alert_parser.add_argument("--reason", required=True)
    alert_parser.add_argument("--until", metavar="UTC")
    watch_parser = commands.add_parser("watch", help="watch one run in the foreground")
    watch_parser.add_argument("run_id")
    watch_parser.add_argument(
        "--interval",
        type=positive_interval,
        default=DEFAULT_INTERVAL_SECONDS,
        metavar="SECONDS",
        help="positive poll interval in seconds (default: 60)",
    )
    watch_parser.add_argument("--once", action="store_true", help="evaluate once and exit")
    watch_parser.add_argument("--bell", action="store_true", help="ring the terminal bell for a new alert")
    return parser


def _emit(value: Any, stream: TextIO | None = None) -> None:
    """Write JSON as UTF-8 even when a Windows console stream is redirected."""

    target = stream or sys.stdout
    encoded = (json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    binary = getattr(target, "buffer", None)
    if binary is not None:
        binary.write(encoded)
        binary.flush()
        return
    target.write(encoded.decode("utf-8"))
    target.flush()


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "skills":
        if args.skills_command == "install":
            return install_skills(args.source_checkout)
        if args.skills_command == "status":
            return skills_status()
        if args.skills_command == "uninstall":
            return uninstall_skills()
        raise RequestError("unknown skills command")
    store = Store(resolve_data_dir(args.data_dir))
    if args.command == "init":
        return initialize(store)
    if args.command == "start":
        current, replay = start(store, read_json_file(args.file))
        return {"run_id": current["run_id"], "run": current, "idempotent": replay}
    if args.command == "checkpoint":
        current, replay, event_id = checkpoint(store, args.run_id, read_json_file(args.file))
        return {"event_id": event_id, "run": current, "idempotent": replay}
    if args.command == "status":
        return status(store, args.run_id)
    if args.command == "brief":
        return brief(store, args.run_id)
    if args.command == "observe":
        current, replay = observe(store, args.run_id, read_json_file(args.file))
        observation = public_observation(current)
        return {
            "observation_id": observation["observation_id"],
            "observation": observation,
            "evidence_availability": [
                {
                    "locator": item["locator"],
                    "availability": item.get("availability", "unknown"),
                }
                for item in observation["evidence"]
                if item["kind"] == "local"
            ],
            "idempotent": replay,
        }
    if args.command == "patterns" and args.patterns_command == "import":
        changed, count = import_patterns(store, read_json_file(args.file))
        return {"patterns": [public_pattern(item) for item in changed], "changed": count}
    if args.command == "pattern":
        pattern = set_pattern_disposition(
            store, args.pattern_key, args.disposition, args.reason, args.evidence
        )
        return {"pattern": public_pattern(pattern)}
    if args.command == "finish":
        current, replay = finish(store, args.run_id, args.outcome, args.summary)
        return {"run": current, "idempotent": replay}
    if args.command == "alert":
        return {
            "alert": revise_alert(
                store, args.alert_id, args.action, args.reason, args.until
            )
        }
    raise RequestError("unknown command")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        if args.command == "watch":
            store = Store(resolve_data_dir(args.data_dir))
            watch_foreground(
                store,
                args.run_id,
                args.interval,
                once=args.once,
                bell=args.bell,
            )
            return 0
        _emit(run(args))
        return 0
    except AdvocateError as error:
        _emit({"error": error.error_type, "message": str(error)}, sys.stderr)
        return error.exit_code
    except OSError as error:
        if args.command == "skills":
            _emit(
                {"error": "setup_error", "message": f"skill filesystem operation failed: {error}"},
                sys.stderr,
            )
            return 2
        _emit(
            {
                "error": "store_unavailable",
                "message": "private store operation failed; preserve this directory for diagnosis",
            },
            sys.stderr,
        )
        return 3
    except (ValueError, sqlite3.DatabaseError):
        _emit(
            {
                "error": "store_unavailable",
                "message": "private store operation failed; preserve this directory for diagnosis",
            },
            sys.stderr,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
