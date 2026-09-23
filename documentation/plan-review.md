[!] Detected non-blank Issue fields — repo-sync appears to have already run. Findings applied to plan.md will require corresponding `gh issue edit` updates (N+1 rework). See `feedback_plan_review_before_repo_sync.md`.
Reviewing as: greenfield plan. Sections 17–21 skipped.

# Agent Advocate plan review — 2026-09-23

**Verdict: PASS for the amended plan.** Implementation and live acceptance remain incomplete. Sections 19 (project conventions) and 21 (step sizing) run under the greenfield carve-outs.

Reviewed `plan.md` SHA-256 `cd6f86278c3cc020015fca3a1be4b2e86ec520aeb27b189dd79c76693215ec61`, against main HEAD `0803279c7a78f4b956ae4eaf9b3b90044204c854`. This report replaces the earlier scope. Review delegated without plan writes; the coordinating session owns amendments, redline, wrap, issue updates and preserved-work reconciliation.

## Blockers

None.

## Significant gaps

None.

## Missing items

None.

## Nice-to-haves

None.

## Complete checklist

| Check | Assessment |
|---|---|
| 1 Persistence | Pass: section 3 defines SQLite entities, projections/events, transactions, private evidence and corruption recovery. The new readiness assessment uses Observation; no schema/service is added. |
| 2 External dependencies | Pass: standard-library runtime; native host agent/web capabilities remain explicit prerequisites with unavailable outcomes. |
| 3 Auth/secrets | Pass: no new credentials; runtime data and receipts remain private. |
| 4 Async/concurrency | Pass: bounded SQLite contention, watcher deduplication and process boundaries are explicit. |
| 5 Errors/feedback | Pass: named CLI exits, unavailable/unknown readiness and advisory ownership are clear. |
| 6 Toolchain | Pass: install, develop, build, test and whitespace commands are enumerated; absent lint/typecheck are explicit. |
| 7 Decisions/placeholders | Pass: no unresolved architectural choice or TBD. `RUN_ID`, `PATH`, `PATTERN_KEY`, `OBSERVATION_ID`, `REPLACE_WITH_RETURNED_RUN_UUID`, `<skill-name>`, `<five named skills>` and `<resolved-checkout>` are explained command/path metavariables, not undecided outputs. |
| 8 Setup | Pass: sections 2/10 define prerequisites, initial lock creation, private initialization and first invocation. |
| 9 Idempotency | Pass: normalized IDs/payloads, seed import, immutable corrections and alert keys define reruns. |
| 10 Seams | Pass: CLI/skills/store ownership and Observation-based readiness preserve the existing wire shape. |
| 11 Scope | Pass: no capability registry, certification service, extra skill or automatic route change. |
| 12 Security | Pass: explicit evidence paths, fetched evidence as data, private records and no implicit publication or project mutation. |
| 13 Tests | Pass: meaningful subprocess, persistence, privacy, concurrency and timer tests; readiness observation round-trip coverage. |
| 14 Operations | Pass: foreground watch, Ctrl+C, restart and corrupt-store recovery are defined. |
| 15 End-to-end observation | Pass: M1 observes two normal poll intervals and a short overdue case, real skills, research and independent assessment. |
| 15.5 Data smoke | Pass: Step 1 real CLI persistence and Step 3 actual watcher/store process flow precede M1. |
| 16 Clean context | Pass: entities, modules, IDs, command shapes and quickstart are inline; implementation state is qualified. |
| 17 Existing-code validation | Greenfield skip; main file listing confirms declared source/skills are planned outputs, while section 11 explicitly preserves the separate Step 1 candidate. |
| 18 Impact completeness | Greenfield skip; amendment fits the existing Step 2 skills/shared contract/tests and M1. |
| 19 Conflicts/conventions | Pass carve-out: CLAUDE.md/AGENTS.md agree with first-party project skills, private storage, full project gate and preserved blocked work. |
| 20 Architecture context | Greenfield skip; sections 3–7 already describe the planned boundaries. |
| 21 Scope/step size | Pass carve-out: persistence, skills and watcher remain three bounded slices; live observation stays separate. |
| 22 Operator/code split | Pass: M1 executes the Step 3-authored procedure; it authors no source/config/runbook. |
| 23 Conditional predicates | Not applicable: no conditional steps. |
| 24 Reviewer shape | Pass: code/deep only; no missing runtime URL/start command. |
| 25 Build-phase format | Pass: Steps 1–3 have numbered headings and required fields; M1 is explicitly a separate manual step. |
| 26 Substrate smoke | Pass: M1 qualifies actual loaded Codex skills, independent review/web tools and the real watcher. |
| 27 Stakes routing | Pass: Steps 1/3 retain deep; Step 2 has no new schema/timer substrate. Early capability detection remains advisory skill behavior. |
| Observatory hooks | Pass: root plan.md, labeled objective and status-bearing steps; no port is introduced. |

## Evidence and limits

Read the full workspace instructions, project CLAUDE.md/AGENTS.md, installed plan-review wrapper/core, complete amended plan, and the source owners of the referenced shared repair. `git log --oneline -5`, `git rev-parse HEAD`, `git status --short` and `rg --files` established the checked-out scaffold and current edits. No candidate implementation, review receipt or retry budget was changed.

The source repair dependency is independently reviewed in Skill Mesh's Phase CD report. This PASS means the consumer plan clearly requires qualification and preserves its candidate; it does not mean that prerequisite has passed. No tests, native probes, network requests or live skill executions were run for this document review. Public source statements are retained with their existing dated attribution, not newly verified here.

Next: plan-redline, then plan-wrap, followed by synchronization of changed existing issue bodies. No new approval is requested by this review.

Auto-applied 0 fixes. Plan is ready for `/plan-wrap` and `/repo-sync`.

## Bounded resume amendment, 2026-09-23

An independent adversarial follow-up reviewed only section 11's new execution
limits and the matching instructions/handoff. No contradiction or unsafe bypass
was found: both bounds require checkpoint-and-stop, deep/full-project gates stay
required, unchanged-input receipt reuse is conditional, the iteration 4 developer
receipt does not replace independent review, and historical retry limits remain
binding. No tests or new scope were added. Existing review findings for the
unchanged product plan remain applicable. Next: update the existing proposal's
P9/D8 entries, then perform the narrow self-containment check.
