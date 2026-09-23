# Build handoff: Agent Advocate v0

**Paused by the operator on 2026-09-23.** The shared Skill Mesh repair was implemented and independently reviewed, but its full test run was stopped before completion because validation was taking too long. The reviewed candidate is preserved on [paused/cd155-operator-stop-20260923](https://github.com/aberson/skill-mesh/tree/paused/cd155-operator-stop-20260923). Installed-host qualification and profile refresh have not run. Agent Advocate's existing candidate remains preserved. Resume only when the operator asks to continue; this handoff does not authorize an automatic test or build restart.

The operator approved this v0 and public repository on 2026-09-22, then requested the recurring review-capability blocker be addressed first on 2026-09-23. Scope is settled in [plan.md](../plan.md); do not reopen routine stack, privacy, timer or host choices. Step 1 now has a preserved unmerged implementation and review history. This is a resume handoff, not a request to start it again.

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

## Resolve the prerequisite before dispatch

Read the actual installed `review-deep` adapter and its helper files. The current Codex adapter deliberately refuses isolated lens dispatch; having a child-spawn tool alone does not override it. The owning fix is the amended [Skill Mesh Phase CD plan](https://github.com/aberson/skill-mesh/blob/main/documentation/codex-deep-review-unblock-plan.md), existing [#222](https://github.com/aberson/skill-mesh/issues/222) and [#223](https://github.com/aberson/skill-mesh/issues/223). Its scope includes packaged code-lane helpers, capacity-aware independent reviewer batches, capability-conditioned mapping, installed-host proof and normal profile refresh. Keep this project's deep review flags intact.

That repair runs in the **Skill Mesh checkout**, using its own instructions and plan. It does not resume the rest of that repository's backlog. Do not hand-edit a generated consumer skill or add a project-local copy of the shared engine. A source change, a passing static test or an unactivated disposable install is not a working review route. Reuse a valid capability receipt only for the unchanged host/session/package; otherwise qualify the actual route.

Reconcile issue #1 and the existing worktree's latest developer/reviewer receipts. Later Claude/Opus review rounds exist after the first blocked report. Preserve their candidate, unresolved findings and consumed retry budget; coordinate with the current builder before taking ownership. A qualified, separately authorized Claude route does not qualify Codex, and this handoff does not silently switch models or hosts.

Once the required route is demonstrably available and build ownership is settled, resume in the **Agent Advocate checkout**:

```text
/build-phase --plan plan.md --steps 1,2,3 --resume 1
```

This is a host skill invocation, not a PowerShell executable. Resolve the installed `build-phase` skill through the host's available skill mechanism and follow it. Public contributors without that workflow can implement the same three steps directly from the canonical plan and linked issues; the Python product does not depend on that external workflow.

Apply plan.md section 11's bounded resume defaults: 90 minutes total for this
invocation, at most five minutes of cumulative testing per step, and checkpoint
then stop on either bound. These are coordinator-selected limits responding to
the operator's testing-overrun concern, not promised completion times. Reconcile
and independently review the preserved iteration 4 candidate first; its latest
developer receipt reports 26 tests passed in 34.70 seconds. Preserve the actual
consumed rounds and resolved retry limit. A new cycle must address a named changed
input or unresolved acceptance defect. Do not launch Skill Mesh's root suite from
this consumer build or expand acceptance with optional reviewer preferences.

## Deliver the approved behavior

1. Persist an advocated run, checkpoints, evidence and cautions using a private SQLite store and a real CLI.
2. Add the five project-owned Codex skills: `assign-advocate`, `status-inquisition`, `coordination-cowbell`, `model-mother`, `advocate-wrap`. Before assignment, compare required gates with loaded adapters, packaged helpers and actual host capabilities, recording available/unavailable/unknown through existing observations. Use actual native agents and web tools when invoked; record unavailable capability honestly.
3. Add the configurable 60-second foreground watcher with persistent, deduplicated overdue alerts and the exact live acceptance procedure.

Keep the timer deterministic: it does not launch models or stop builds. The advocate advises; the coordinator retains authority over work. Run records and evidence stay outside Git. The shared prerequisite repair above is separate from this product's three code steps. No dashboard, daemon, API client, automatic model routing or duplicate skill installer belongs to this product.

Step 1's original baseline had no runtime suite; its preserved candidate now has package, lock and tests. Read their current state and run the appropriate actual gate rather than re-creating the project or reporting the old baseline as current. Steps 1 and 3 use deep review for persistence and timer boundaries; Step 2 uses ordinary code review. Use the preserved isolated worktree and declared workflow.

Complete each step's observable acceptance. Use the narrowest useful checks while fixing a defect and the full project suite at completion. Cite an already completed integrated-state run only when source, tests, dependencies, configuration and generated inputs are unchanged. Do not expand acceptance for optional reviewer preferences, test-count growth or imagined future architecture. Repeated repair attempts should trigger the existing workflow's diagnosis path, preserving its authorized retry budget.

## Finish the code span, then observe

After Steps 1-3, report changed behavior, real validation receipts, merged commits, issue/status updates and remaining limitations. Hand off **Please run M1 next** with `documentation/acceptance.md`. M1 uses a fresh Codex session to demonstrate all five skills, real independent assessment, real public-source research, and the timer across two normal intervals plus a short overdue case. Mechanical tests alone cannot mark it complete.

Use existing useful work for acceptance; do not invent a benchmark project. Demonstrate the early capability check on a real route and one clearly synthetic unavailable-adapter example. Keep detailed receipts private while publishing sanitized outcomes. Once v0 is accepted, use it during separately selected v1 work, then resume the broader separately approved Skill Mesh improvements. That later work is not authorized by this handoff alone.
