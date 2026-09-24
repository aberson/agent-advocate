from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess

from agent_advocate.service import normalize_patterns
from agent_advocate.skill_install import SKILL_NAMES as INSTALLED_NAMES


ROOT = Path(__file__).resolve().parents[1]
SKILL_NAMES = (
    "assign-advocate",
    "status-inquisition",
    "coordination-cowbell",
    "model-mother",
    "advocate-wrap",
)
LOCAL_LINK = re.compile(r"\[[^]]+\]\(([^)]+)\)")
PINNED_CLI = "uv run --project <resolved-checkout> --locked agent-advocate"


def _frontmatter(path: Path) -> dict[str, str]:
    content = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n", content, re.DOTALL)
    assert match, f"{path} must start with YAML frontmatter"
    result: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, separator, value = line.partition(":")
        assert separator and key and value.strip(), f"invalid frontmatter line in {path}: {line}"
        result[key] = value.strip().strip('"')
    return result


def _assert_local_links_resolve(path: Path) -> None:
    for target in LOCAL_LINK.findall(path.read_text(encoding="utf-8")):
        target = target.split(maxsplit=1)[0]
        if target.startswith(("https://", "http://", "#", "mailto:")):
            continue
        destination = (path.parent / target.split("#", maxsplit=1)[0]).resolve()
        assert destination.is_relative_to(ROOT), f"resource escapes repository: {path} -> {target}"
        assert destination.exists(), f"missing resource: {path} -> {target}"


def test_five_discoverable_skill_manifests_and_local_resources_resolve() -> None:
    assert INSTALLED_NAMES == SKILL_NAMES
    skill_root = ROOT / ".agents" / "skills"
    manifests = [skill_root / name / "SKILL.md" for name in SKILL_NAMES]
    assert sorted(path.parent.name for path in skill_root.glob("*/SKILL.md")) == sorted(SKILL_NAMES)
    for path, name in zip(manifests, SKILL_NAMES, strict=True):
        metadata = _frontmatter(path)
        assert metadata["name"] == name
        assert metadata["description"]
        instructions = path.read_text(encoding="utf-8")
        assert "resolve this physical `SKILL.md` upward" in instructions
        assert PINNED_CLI in instructions
        assert "installed wrapper" in instructions
        _assert_local_links_resolve(path)
    contract = ROOT / "documentation" / "skill-contract.md"
    _assert_local_links_resolve(contract)
    contract_text = contract.read_text(encoding="utf-8")
    assert "resolve the physical `SKILL.md` path and walk upward" in contract_text
    assert PINNED_CLI in contract_text
    assert "Do not use a bare or PATH-resolved CLI." in contract_text
    assert "agent-advocate-install.json" in contract_text
    assert "source_sha256" in contract_text


def test_public_seed_and_model_resources_are_valid_and_generalized() -> None:
    seeds = json.loads((ROOT / "data" / "seed-patterns.json").read_text(encoding="utf-8"))
    normalized = normalize_patterns(seeds)
    assert [pattern["pattern_key"] for pattern in normalized] == [
        "repeated-validation",
        "review-churn-without-new-evidence",
        "scope-growth-beyond-acceptance",
        "environment-resource-failure",
        "high-effort-needs-model-specific-assessment",
        "required-review-unavailable",
    ]
    assert all(pattern["sources"] and pattern["sources"][0]["kind"] == "public-url" for pattern in normalized)
    assert "C:\\" not in (ROOT / "data" / "seed-patterns.json").read_text(encoding="utf-8")
    packaged_seeds = json.loads(
        (ROOT / "src" / "agent_advocate" / "data" / "seed-patterns.json").read_text(encoding="utf-8")
    )
    assert packaged_seeds == seeds

    families = json.loads((ROOT / "data" / "model-families.json").read_text(encoding="utf-8"))
    assert families["schema_version"] == 1
    assert [item["label"] for item in families["families"]] == ["Astra", "Terra", "Sol", "Fable", "Opus"]
    assert all(item["kind"] == "user-editable-family-label" for item in families["families"])


def test_shared_contract_has_executable_synthetic_start_and_checkpoint_sequence() -> None:
    contract = (ROOT / "documentation" / "skill-contract.md").read_text(encoding="utf-8")
    json_templates = [json.loads(block) for block in re.findall(r"```json\r?\n(.*?)\r?\n```", contract, re.DOTALL)]
    run_spec = next(template for template in json_templates if "project_path" in template)
    checkpoint_spec = next(template for template in json_templates if "event_id" in template)
    assert {
        "run_id",
        "project_path",
        "goal",
        "acceptance",
        "non_goals",
        "models",
        "next_check_at",
        "deadline_at",
    } <= set(run_spec)
    assert {"event_id", "state", "summary", "next_check_at"} <= set(checkpoint_spec)
    expected_commands = (
        "uv sync --project <resolved-checkout> --locked",
        f"{PINNED_CLI} --data-dir <private-data-dir> init",
        f"{PINNED_CLI} --data-dir <private-data-dir> start --file <private-data-dir>/run-spec.json",
        f"{PINNED_CLI} --data-dir <private-data-dir> checkpoint <returned-run-id> --file <private-data-dir>/checkpoint-spec.json",
    )
    positions = [contract.index(command) for command in expected_commands]
    assert positions == sorted(positions)
    assert "Read the `run_id` returned by `start`" in contract


def test_installed_wheel_initialization_discovers_packaged_public_seeds(tmp_path: Path) -> None:
    wheel_dir = tmp_path / "wheel"
    built = subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(wheel_dir)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert built.returncode == 0, built.stderr
    wheel = next(wheel_dir.glob("agent_advocate-*.whl"))
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    initialized = subprocess.run(
        [
            "uv",
            "run",
            "--isolated",
            "--no-project",
            "--no-index",
            "--with",
            str(wheel),
            "agent-advocate",
            "--data-dir",
            str(tmp_path / "private"),
            "init",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert initialized.returncode == 0, initialized.stderr
    assert json.loads(initialized.stdout)["seed_patterns_imported"] == 6
