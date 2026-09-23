Reviewing as: greenfield plan. Sections 17–21 skipped.

The conventions check in §19 and step-sizing check in §21 still apply. Review mode: read-only plan review; the author applies corrections. No implementation, runtime test, or GitHub operation was performed.

Reviewed plan SHA256: `44A0FEB103F1011C7F3C129AA3F6CD261B7137804F6BE829D901AEE3F98C56F2`.

Verdict: **PASS**. Open findings: 0 blockers, 0 significant gaps, 0 missing items, 1 reminder. The author corrected the six initial findings; the affected contracts and new changes were rechecked. This verdict concerns planning readiness, not product acceptance.

## Blockers

None.

## Significant gaps

None.

## Missing items

None.

## Nice-to-haves

Reminder: all four Issue fields are blank, which is expected before repository setup/issue synchronization. Fill them before invoking build-phase. No observatory or port work is required.

## Verified corrections

| Initial finding | Resolution in reviewed plan |
|---|---|
| Global pattern event ownership | §3, line 56: only global pattern events may have null `run_id`; run-scoped events retain a required foreign key. |
| Run/observation retry identity | §§3/6, lines 50, 64, 121: skills retain supplied IDs; exact start replay returns current state without rewinding; conflicting content fails; observations share exact retry semantics. Replay comparison precedes current-clock validation. |
| Deadline replacement and waiting reason | §§4/6: waiting uses nonempty summary; expectation replacement resolves obsolete alerts transactionally; omitted/null/revised deadline semantics and reason are explicit. |
| Stakes-aware review routing | §11 and Steps 1/3, lines 202, 214, 238: deep code review with worktree isolation. Step 2 retains ordinary code review; no model-tier change or workspace-wide audit. |
| Toolchain enumeration | §2, lines 29–36: install, develop, packaging, tests, lint/typecheck disposition, and whitespace checks are all named. |
| Store recovery | §3, line 66: stop writers, preserve the private directory and explicitly initialize another external store; no destructive reset or invented migration feature. |

The accompanying retrieval clarification (§4, line 84) excludes dismissed/retired cautions and defines matching for absent dimensions, including v0's absent tags. It closes ambiguity without adding a field or command. The initial review snapshot was `963A47A6BABD041C3CFAA73209E52E2E2F8BFB66F58AF2643165C40624200BD6`; corrections were applied by the author, not by this reviewer.

## Numbered checklist

| Check | Result and evidence |
|---|---|
| 1. Data persistence | Pass after correction. SQLite owns projections; event ownership, transactional updates, version 1, bounded contention and non-destructive recovery are explicit (§3). Evidence-copy interruption remains an implementation detail to review with storage code. |
| 2. External dependencies/integrations | Pass. Existing host supplies agents and web; unavailable capability is visible; no additional service, credentials, or scraper is planned (§§2/4). |
| 3. Authentication/secrets | Pass for scope. No new authentication. Runtime evidence is external and private; no automatic exporter (§3). |
| 4. Async/concurrency | Pass. Separate foreground watcher, short transactions, five-second contention bound, unique alert key and transactional notification claim (§§3/4). Crash-before-console-output limitation is explicit. |
| 5. Error handling/feedback | Pass. CLI exit classes and stderr contract are defined; unknown evidence and unavailable capabilities remain visible (§§4/6). |
| 6. Build/toolchain | Pass after correction. All six operations have a command or an explicit unconfigured disposition (§2). |
| 7. Unresolved decisions | Pass. No architecture TBD. Placeholder/alternative inventory appears below; review routing is now selected. |
| 8. Setup documentation | Pass. Python, uv, Git, host requirements, external data-dir precedence and initialization are specified (§§3/10; CLAUDE.md). |
| 9. Deduplication/idempotency | Pass after correction. Run/event/observation retry identity, pattern/finish replay and alert uniqueness are defined (§§3/4/6). |
| 10. Integration seams | Pass after correction. Entity shapes, global event ownership, deadline updates, CLI inputs, module ownership and direction are inline (§§3/5/6). No circular dependency is planned. |
| 11. Scope/over-engineering | Pass. Five approved skills, one private store, deterministic timer; no framework, automatic router, daemon installer, or new API client (§§1/8/9). |
| 12. Security | Pass for planning. Resolved paths must stay outside Git stores; input and excerpt bounds apply. CLAUDE.md states external evidence is data, not instructions, and permits only explicit evidence paths. Implementation must exercise the declared refusal, not merely print guidance (§3; Step 1). |
| 13. Testing strategy | Pass. Meaningful CLI subprocess/storage/privacy tests, concurrent writer/watcher tests, pure clock cases and separate live-host acceptance (§11). No production suite yet exists. |
| 14. Operations | Pass after correction. Foreground start/stop/restart, timer interval and non-destructive store recovery are explicit (§§3/4). |
| 15. End-to-end observation | Pass. M1 uses a bounded real task, actual host assessment, research and two default poll intervals plus one overdue case. This is proportionate to v0 claims; no multi-hour soak is required. |
| 15.5. Producer/consumer smoke | Pass. Step 1 wires real CLI/store across processes; Step 3 observes real watcher plus concurrent update. New version-1 schema has no legacy migration to perform. |
| 16. Clean-context readiness | Pass after correction. Schemas, UUID format, state names, CLI shapes, quickstart, complete toolchain and development process are inline. Plan-wrap follows this review and redline. |
| 17. Existing-code validation | Not applicable: greenfield. Planned files are explicitly identified as future outputs (§7). Existing workflow contracts were checked separately below. |
| 18. Feature impact completeness | Not applicable: greenfield; no existing product interfaces are changed. |
| 19. Conflicts/conventions | Greenfield carve-out passed. Read project AGENTS.md and CLAUDE.md. The project expressly owns `.agents/skills`; no external catalog mutation is needed. Other feature-plan checks do not apply. |
| 20. Existing architecture context | Not applicable: greenfield. |
| 21. Scope/step sizing | Greenfield carve-out passed. Persistence lifecycle, skill workflows, and timer are coherent bounded slices with real production callers; M1 observes them. No extra infrastructure slice is required. |
| 22. Operator/code split | Pass. Steps 1–3 author artifacts; M1 only executes the Step-3-authored acceptance procedure and records outcomes. |
| 23. Conditional predicates | Not applicable. No conditional steps. |
| 24. Runtime reviewer prerequisites | Pass. No runtime/full review flags require an app URL or start command. Deep code review would not introduce that requirement. |
| 25. Build-phase format | Pass. Numeric headings 1–3 carry Problem/Type/Issue, Files and falsifiable Done-when. M1 is an explicitly separate manual acceptance item, not an additional numeric code step. Blank issue numbers are expected pre-sync. |
| 26. Live substrate smoke | Pass. M1 separately demonstrates actual skill discovery, native independent agents, public research and a visible watchdog. Package tests alone do not qualify it. |
| 27. Stakes-aware routing | Pass after correction. Owner paragraph read; Steps 1/3 route to deep code review; Step 2 retains ordinary code review. No further model-tier choice is required. |

## Placeholder and alternatives inventory

The search found no `TBD` and no unresolved architecture choice. Literal angle-bracket instances are `.agents/skills/<skill-name>/SKILL.md`, `.agents/skills/<five named skills>/`, and `uv run --project <resolved-checkout> --locked agent-advocate ...`; all are explained by the five-name table and checkout-resolution instruction. `REPLACE_WITH_RETURNED_RUN_UUID` is an explicitly instructed copy-from-assign placeholder, not an undefined ID format. The four blank Issue fields are workflow placeholders.

The decision-like alternatives are resolved rules: data directory fallback uses the OS/environment, absent IDs are generated, retirement accepts evidence or explicit owner judgment, modules may be combined for clarity, and outcome enumerations select completed/stopped/abandoned. References to optional/deferred v1 work do not create v0 choices. No alternative database, host, API, queue, authentication system, or installation mechanism remains open.

## Producer verification and limits

- `rg --files --hidden` initially listed only plan.md, CLAUDE.md, AGENTS.md, .gitignore and .gitattributes. Source, skills, fixtures and runtime tests are planned outputs. The author is concurrently preparing the other planning documents; their temporary absence is not a runtime defect.
- The local installed build-phase contract documents numbered headings, ordinary/deep code review, isolated worktrees and deferred manual observation. The local build-step argument table accepts `code` and `deep`; deep does not require a running UI. No CLI agent flag or independent assessment capability was invented.
- [Official OpenAI Build skills documentation](https://learn.chatgpt.com/docs/build-skills) was opened: `SKILL.md` requires name/description, and repository discovery scans `.agents/skills` from cwd toward the repository root. This verifies the documented producer contract, not discovery of the still-unwritten product packages.
- The canonical plan location, objective heading and TODO step markers are observer-readable. No port is declared, so port collision checks do not apply.
- Commands used were read-only `Get-Content`, `rg`, `Get-FileHash`, and local `git rev-parse`/`git log`; official documentation was searched/opened. No test pass, build pass, product skill execution, live host acceptance, repository creation, or remote mutation is claimed by this review.

No operator decision remains for this review. Next is plan-redline, then plan-wrap; publication and issue bookkeeping follow under the existing authorization. Later issue-number-only edits do not claim new design review, and this hash identifies the exact reviewed design snapshot.

Auto-applied 0 fixes. Plan is ready for `/plan-wrap` and `/repo-sync`.
