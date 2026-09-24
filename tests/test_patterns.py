from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
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


def write_json(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def future(minutes: int = 10) -> str:
    return (datetime.now(UTC) + timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")


def observation(
    statement: str,
    *,
    pattern_key: str = "required-review-unavailable",
    supersedes: str | None = None,
    source: str = "synthetic://host-receipt",
) -> dict[str, object]:
    return {
        "observation_id": str(uuid.uuid4()),
        "statement": statement,
        "basis": "measured",
        "evidence": [
            {
                "kind": "host-result" if source.startswith("synthetic://") else "public-url",
                "locator": source,
                "captured_at": future(),
                "excerpt": None,
                "sha256": None,
            }
        ],
        "pattern_key": pattern_key,
        "recommendation": "Use the owning repair; do not infer availability.",
        "analysis_kind": "coordinator",
        "assessor_id": None,
        "supersedes": supersedes,
    }


def test_seed_replay_brief_and_synthetic_capability_records_use_the_production_cli(
    tmp_path: Path,
) -> None:
    project = tmp_path / "synthetic-project"
    project.mkdir()
    private = tmp_path / "private"

    initialized = invoke(private, "init")
    assert initialized.returncode == 0, initialized.stderr
    assert json.loads(initialized.stdout)["seed_patterns_imported"] == 6
    with sqlite3.connect(private / "advocate.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM events WHERE kind = 'pattern-import'").fetchone()[0] == 6

    run_file = write_json(
        tmp_path / "run.json",
        {
            "project_path": str(project),
            "goal": "Persist synthetic capability observations",
            "acceptance": ["Unknown and unavailable remain distinct"],
            "non_goals": ["Live host acceptance"],
            "models": [
                {
                    "role": "reviewer",
                    "requested_model": "synthetic-reviewer",
                    "observed_model": None,
                    "effort": None,
                    "host": "synthetic-host",
                }
            ],
            "next_check_at": future(),
            "deadline_at": None,
        },
    )
    started = invoke(private, "start", "--file", str(run_file))
    assert started.returncode == 0, started.stderr
    run_id = json.loads(started.stdout)["run_id"]

    unavailable_file = write_json(
        tmp_path / "unavailable.json",
        observation(
            "capability route=native-agent status=unavailable; reason=synthetic host has no fresh dispatch; owner=host adapter"
        ),
    )
    unavailable = invoke(private, "observe", run_id, "--file", str(unavailable_file))
    assert unavailable.returncode == 0, unavailable.stderr
    unavailable_record = json.loads(unavailable.stdout)["observation"]

    missing_fix_evidence = invoke(
        private,
        "pattern",
        "required-review-unavailable",
        "--disposition",
        "fix-applied",
        "--reason",
        "A correction must supply a receipt.",
    )
    assert missing_fix_evidence.returncode == 2 and missing_fix_evidence.stdout == ""
    assert json.loads(missing_fix_evidence.stderr) == {
        "error": "request_error",
        "message": "fix-applied disposition requires --evidence naming a correction observation",
    }

    unlinked_fix_evidence = invoke(
        private,
        "pattern",
        "required-review-unavailable",
        "--disposition",
        "fix-applied",
        "--reason",
        "An original observation is not a correction receipt.",
        "--evidence",
        unavailable_record["observation_id"],
    )
    assert unlinked_fix_evidence.returncode == 2 and unlinked_fix_evidence.stdout == ""
    assert json.loads(unlinked_fix_evidence.stderr) == {
        "error": "request_error",
        "message": "fix-applied --evidence must name a correction observation",
    }

    missing_observation_evidence = invoke(
        private,
        "pattern",
        "required-review-unavailable",
        "--disposition",
        "fix-applied",
        "--reason",
        "A missing observation cannot prove a correction.",
        "--evidence",
        str(uuid.uuid4()),
    )
    assert missing_observation_evidence.returncode == 2 and missing_observation_evidence.stdout == ""
    assert json.loads(missing_observation_evidence.stderr) == {
        "error": "request_error",
        "message": "--evidence must name an existing observation",
    }

    unknown_file = write_json(
        tmp_path / "unknown.json",
        observation(
            "capability route=web-research status=unknown; reason=synthetic probe was not performed; owner=host adapter"
        ),
    )
    unknown = invoke(private, "observe", run_id, "--file", str(unknown_file))
    assert unknown.returncode == 0, unknown.stderr

    correction_file = write_json(
        tmp_path / "correction.json",
        observation(
            "synthetic correction: native-agent route is available after a named repair; benefit remains unobserved",
            supersedes=unavailable_record["observation_id"],
            source="https://example.invalid/synthetic-repair-receipt",
        ),
    )
    correction = invoke(private, "observe", run_id, "--file", str(correction_file))
    assert correction.returncode == 0, correction.stderr
    correction_record = json.loads(correction.stdout)["observation"]

    revised = invoke(
        private,
        "pattern",
        "required-review-unavailable",
        "--disposition",
        "fix-applied",
        "--reason",
        "Synthetic repair was applied; no outcome benefit is claimed.",
        "--evidence",
        correction_record["observation_id"],
    )
    assert revised.returncode == 0, revised.stderr
    assert json.loads(revised.stdout)["pattern"]["disposition"] == "fix-applied"

    replayed_init = invoke(private, "init")
    assert replayed_init.returncode == 0, replayed_init.stderr
    assert json.loads(replayed_init.stdout)["seed_patterns_imported"] == 0
    with sqlite3.connect(private / "advocate.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM events WHERE kind = 'pattern-import'").fetchone()[0] == 6

    briefed = invoke(private, "brief", run_id)
    assert briefed.returncode == 0, briefed.stderr
    selected = json.loads(briefed.stdout)["patterns"]
    assert len(selected) == 5
    assert any(item["disposition"] == "candidate" for item in selected)
    required_review = next(
        item for item in selected if item["pattern_key"] == "required-review-unavailable"
    )
    assert required_review["disposition"] == "fix-applied"
    assert required_review["reason"] == "Synthetic repair was applied; no outcome benefit is claimed."
    assert required_review["disposition_evidence"] == correction_record["observation_id"]

    finished = invoke(
        private,
        "finish",
        run_id,
        "--outcome",
        "completed",
        "--summary",
        "Synthetic work completed; a later benefit observation is still required.",
    )
    assert finished.returncode == 0, finished.stderr
    assert json.loads(finished.stdout)["run"]["outcome"] == "completed"

    fresh_status = invoke(private, "status", run_id)
    assert fresh_status.returncode == 0, fresh_status.stderr
    observations = json.loads(fresh_status.stdout)["observations"]
    statuses = {item["statement"].split(" status=")[1].split(";")[0] for item in observations[:2]}
    assert statuses == {"unavailable", "unknown"}
    stored_correction = next(item for item in observations if item["observation_id"] == correction_record["observation_id"])
    assert stored_correction["supersedes"] == unavailable_record["observation_id"]
    assert stored_correction["evidence"][0]["locator"] == "https://example.invalid/synthetic-repair-receipt"


def test_fix_applied_requires_same_pattern_correction_provenance_through_cli(
    tmp_path: Path,
) -> None:
    project = tmp_path / "synthetic-project"
    project.mkdir()
    private = tmp_path / "private"
    assert invoke(private, "init").returncode == 0

    run_file = write_json(
        tmp_path / "run.json",
        {
            "project_path": str(project),
            "goal": "Reject mismatched correction provenance",
            "acceptance": ["Fix-applied remains tied to its observed pattern"],
            "non_goals": [],
            "models": [],
            "next_check_at": future(),
            "deadline_at": None,
        },
    )
    started = invoke(private, "start", "--file", str(run_file))
    assert started.returncode == 0, started.stderr
    run_id = json.loads(started.stdout)["run_id"]

    target_original_file = write_json(
        tmp_path / "target-original.json",
        observation("Synthetic original for the target pattern."),
    )
    target_original = invoke(private, "observe", run_id, "--file", str(target_original_file))
    assert target_original.returncode == 0, target_original.stderr
    target_original_id = json.loads(target_original.stdout)["observation_id"]

    other_pattern = "review-churn-without-new-evidence"
    other_original_file = write_json(
        tmp_path / "other-original.json",
        observation("Synthetic original for a different pattern.", pattern_key=other_pattern),
    )
    other_original = invoke(private, "observe", run_id, "--file", str(other_original_file))
    assert other_original.returncode == 0, other_original.stderr
    other_original_id = json.loads(other_original.stdout)["observation_id"]

    other_pattern_correction_file = write_json(
        tmp_path / "other-pattern-correction.json",
        observation(
            "Synthetic correction for a different pattern.",
            pattern_key=other_pattern,
            supersedes=other_original_id,
        ),
    )
    other_pattern_correction = invoke(
        private, "observe", run_id, "--file", str(other_pattern_correction_file)
    )
    assert other_pattern_correction.returncode == 0, other_pattern_correction.stderr
    wrong_pattern = invoke(
        private,
        "pattern",
        "required-review-unavailable",
        "--disposition",
        "fix-applied",
        "--reason",
        "A correction for another pattern cannot prove this fix.",
        "--evidence",
        json.loads(other_pattern_correction.stdout)["observation_id"],
    )
    assert wrong_pattern.returncode == 2 and wrong_pattern.stdout == ""
    assert json.loads(wrong_pattern.stderr) == {
        "error": "request_error",
        "message": "fix-applied correction observation must use the pattern_key",
    }

    wrong_original_correction_file = write_json(
        tmp_path / "wrong-original-correction.json",
        observation(
            "Synthetic correction that links to another pattern's original.",
            supersedes=other_original_id,
        ),
    )
    wrong_original_correction = invoke(
        private, "observe", run_id, "--file", str(wrong_original_correction_file)
    )
    assert wrong_original_correction.returncode == 0, wrong_original_correction.stderr
    wrong_original = invoke(
        private,
        "pattern",
        "required-review-unavailable",
        "--disposition",
        "fix-applied",
        "--reason",
        "A correction cannot supersede a different pattern's original.",
        "--evidence",
        json.loads(wrong_original_correction.stdout)["observation_id"],
    )
    assert wrong_original.returncode == 2 and wrong_original.stdout == ""
    assert json.loads(wrong_original.stderr) == {
        "error": "request_error",
        "message": "fix-applied correction must supersede an observation for the pattern_key",
    }

    empty_evidence_correction = observation(
        "Synthetic correction without a receipt.", supersedes=target_original_id
    )
    empty_evidence_correction["evidence"] = []
    empty_evidence_file = write_json(
        tmp_path / "empty-evidence-correction.json", empty_evidence_correction
    )
    empty_evidence = invoke(private, "observe", run_id, "--file", str(empty_evidence_file))
    assert empty_evidence.returncode == 0, empty_evidence.stderr
    no_receipt = invoke(
        private,
        "pattern",
        "required-review-unavailable",
        "--disposition",
        "fix-applied",
        "--reason",
        "An unevidenced correction cannot prove a fix.",
        "--evidence",
        json.loads(empty_evidence.stdout)["observation_id"],
    )
    assert no_receipt.returncode == 2 and no_receipt.stdout == ""
    assert json.loads(no_receipt.stderr) == {
        "error": "request_error",
        "message": "fix-applied correction observation must include evidence",
    }
