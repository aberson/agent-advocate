# Build handoff: Agent Advocate v0

The operator approved this v0 and public repository on 2026-09-22. Scope is settled in [plan.md](../plan.md); build it without reopening routine stack, privacy, timer or host choices. This document starts the build; it does not claim implementation is complete.

Build issues: [Step 1 — persistence](https://github.com/aberson/agent-advocate/issues/1), [Step 2 — skills](https://github.com/aberson/agent-advocate/issues/2), [Step 3 — watchdog](https://github.com/aberson/agent-advocate/issues/3). Separate live acceptance: [M1](https://github.com/aberson/agent-advocate/issues/4).

## Start in this repository

Verify the checkout identity and current state before acting:

```powershell
git rev-parse --show-toplevel
git remote get-url origin
git log --oneline -5
git rev-parse HEAD
git status --short
git worktree list
```

Expected remote: `https://github.com/aberson/agent-advocate.git` (an SSH equivalent is also valid). Read `AGENTS.md`, `CLAUDE.md`, `plan.md` and the latest plan-review/plan-wrap reports. Reconcile any work that landed after this handoff with Git and issue state; do not overwrite another session or restart a completed step.

For the owner's skill-enabled workspace, run:

```text
/build-phase --plan plan.md --steps 1,2,3
```

This is a host skill invocation, not a PowerShell executable. Resolve the installed `build-phase` skill through the host's available skill mechanism and follow it. Public contributors without that workflow can implement the same three steps directly from the canonical plan and linked issues; the Python product does not depend on that external workflow.

## Deliver the approved behavior

1. Persist an advocated run, checkpoints, evidence and cautions using a private SQLite store and a real CLI.
2. Add the five project-owned Codex skills: `assign-advocate`, `status-inquisition`, `coordination-cowbell`, `model-mother`, `advocate-wrap`. Use actual native independent agents and web tools when invoked; record unavailable capability honestly.
3. Add the configurable 60-second foreground watcher with persistent, deduplicated overdue alerts and the exact live acceptance procedure.

Keep the timer deterministic: it does not launch models or stop builds. The advocate advises; the coordinator retains authority over work. Run records and evidence stay outside Git. No installer, dashboard, daemon, API client, automatic model routing or Skill Mesh change belongs to this v0.

Step 1 creates `pyproject.toml`, `uv.lock` and the first tests; the current baseline is **not yet created**, never a fictitious passing test count. Use `uv sync` once to establish the lock, then the plan's locked commands. Steps 1 and 3 use deep review for their persistence and timer boundaries; Step 2 uses ordinary code review. Use isolated worktrees as declared in the plan.

Complete each step's observable acceptance. Use the narrowest useful checks while fixing a defect and the full project suite at completion. Cite an already completed integrated-state run only when source, tests, dependencies, configuration and generated inputs are unchanged. Do not expand acceptance for optional reviewer preferences, test-count growth or imagined future architecture. Repeated repair attempts should trigger the existing workflow's diagnosis path, preserving its authorized retry budget.

## Finish the code span, then observe

After Steps 1-3, report changed behavior, real validation receipts, merged commits, issue/status updates and remaining limitations. Hand off **Please run M1 next** with `documentation/acceptance.md`. M1 uses a fresh Codex session to demonstrate all five skills, real independent assessment, real public-source research, and the timer across two normal intervals plus a short overdue case. Mechanical tests alone cannot mark it complete.

Use existing useful work for acceptance; do not invent a benchmark project. Keep the build and detailed receipts private while publishing only sanitized outcomes. Once v0 is accepted, use it during separately selected v1 work, then resume the separately approved Skill Mesh improvements. That later work is not authorized by this build handoff alone.
