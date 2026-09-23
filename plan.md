# Agent Advocate v0

## 1. What This Is

**Objective:** help a coding coordinator finish useful work by surfacing evidenced delivery problems before work, at normal checkpoints, and after work, with a simple timer that makes overdue expectations visible.

**Status:** APPROVED SCOPE; planning/public repository setup only. Every implementation step is TODO. The operator approved the five-skill v0, SQLite, a configurable 60-second timer, Codex first, and skill-invoked model diagnosis on 2026-09-22 (operator local date). Public publication and private runtime storage were authorized on the same date. No additional scope approval is needed to execute this plan.

**Release sequence:** finish this v0; use it during selected v1 work; then resume the separately approved Skill Mesh improvements. Agent Advocate has no runtime or build prerequisite on Skill Mesh, Switchboard, or an observatory. A larger future framework is acceptable when real use justifies its cost; no broad v1 build is authorized by this v0 plan.

Proposal: [documentation/v0-proposal.html](documentation/v0-proposal.html)

The product is five project-owned skill packages over one local command-line interface (CLI) and private SQLite store. Skills use the active host's existing agent and web tools. The watchdog does cheap deterministic checks and never needs a continuously running model.

## 2. Stack

| Layer | Decision | Why |
|---|---|---|
| Runtime | Python 3.12+, standard library only | Small local utility; built-in SQLite, JSON, UUID, process and clock support |
| Environment | uv, committed `uv.lock`, setuptools build backend | Reproducible development and an actual `agent-advocate` console entry point |
| Development checks | pytest in the development dependency group; `git diff --check` | Test behavior and process boundaries without introducing a lint/type system |
| Storage | SQLite plus bounded private evidence files | Transactions for simultaneous skill/watcher writes; evidence survives temporary source removal |
| Agent host | Codex, project-local skill discovery | First supported and demonstrated host; no new API credentials or SDK |
| Interface | CLI output, JSON command results, one watch terminal | Usable v0 without a web server or dashboard |
| First platform | Windows; standard-library portable data-directory fallback | Matches the initial deployment while keeping ordinary CLI code portable |

No third-party runtime packages, vector database, background model service, or automatic source-code writer are included. Build dependency versions are resolved into the lock in Step 1, rather than guessed in this plan.

| Developer operation | Command / disposition after Step 1 |
|---|---|
| Install | `uv sync --locked` (initial lock creation: `uv sync`) |
| Develop | `uv run --locked agent-advocate --help` and the commands in section 6 |
| Build distribution | `uv build` |
| Test | `uv run --locked python -m pytest` |
| Lint / typecheck | Not configured by design; do not claim either passed |
| Whitespace | `git diff --check` |

## 3. Data Store and Privacy

### Location and ownership

Global `--data-dir PATH` overrides `AGENT_ADVOCATE_DATA_DIR`, then the default. Windows defaults to `%LOCALAPPDATA%/agent-advocate`; if LOCALAPPDATA is absent, use `~/AppData/Local/agent-advocate`. Other platforms use `$XDG_DATA_HOME/agent-advocate` when set or `~/.local/share/agent-advocate` otherwise. Resolve paths and show the selected directory on initialization/watch startup.

`init` explicitly creates `advocate.sqlite3`, `evidence/`, and `logs/`. Other commands fail with a named setup error if the store does not exist; they must not silently initialize a different empty store. Refuse a data directory inside a Git working tree, including the tool checkout or monitored project, after resolving links. Tests use temporary paths outside their fixture repository.

The public repository contains code, documentation, synthetic examples, and generalized seed cautions with public citations. Private contents include run goals, absolute project paths, model/session records, local evidence excerpts, and diagnostics. No runtime export to public GitHub is implemented in v0. A runtime warning/observation is not permission to publish its evidence or mutate a monitored project. Public acceptance reports contain only sanitized case outcomes; detailed receipts remain in the private store.

### Entities

All entity IDs except pattern keys are lowercase canonical UUIDv4 strings generated with `uuid.uuid4()`. Times are timezone-aware RFC3339 UTC strings with `Z`. Inputs may supply a run/event/observation UUID for retry; absent IDs are generated and returned. Skills generate and retain these IDs before invoking a mutation and reuse them on retry. Stable pattern keys use lowercase kebab-case (for example `repeated-validation`). A repository is identified by its resolved existing absolute directory; no automatic workspace scan or remote access is needed to register it.

| Entity | Required fields and meaning |
|---|---|
| Run | `run_id`, `project_path`, `goal`, `acceptance` (nonempty string array), `non_goals` (string array), `models` (ModelRole array), `created_at`, `state`, `last_checkpoint_at`, `next_check_at`, `deadline_at` (nullable), `outcome` (nullable), `summary` (nullable) |
| ModelRole | `role`, `requested_model` (nullable exact identifier), `observed_model` (nullable), `effort` (nullable), `host`; null means unknown, never a resolved-model claim |
| Event | `event_id`, `run_id` (nullable only for global pattern import/disposition events; required valid run foreign key for run-scoped events), `recorded_at` (helper clock), `kind`, `payload` (validated JSON); an append-only record of run state, checkpoint, alert and disposition changes |
| Observation | `observation_id`, `run_id`, `recorded_at`, `statement`, `basis` (`measured`, `reported`, `inferred`), `evidence` (EvidenceRef array), `pattern_key` (nullable), `recommendation` (nullable), `analysis_kind` (`independent`, `coordinator`, `none`), `assessor_id` (nullable actual host-returned identity), `supersedes` (nullable observation UUID) |
| EvidenceRef | `kind` (`local`, `public-url`, `host-result`), `locator`, `captured_at`, `excerpt` (nullable, at most 8 KiB), `sha256` (nullable); local excerpts are copied into private evidence files, full transcripts are not collected |
| Pattern | `pattern_key`, `summary`, `trigger`, `scope` (roles/models/hosts/tags arrays; empty means unrestricted for that dimension), `basis` (`local-observation`, `official-guidance`, `community-report`), `sources` (EvidenceRef array), `owner`, `action`, `disposition`, `updated_at`, `review_after` (nullable date), `reason` |
| Alert | `alert_id`, `run_id`, `kind`, `expectation_at` (the triggering UTC deadline), `first_seen_at`, `last_seen_at`, `disposition`, `reason` (nullable), `snoozed_until` (nullable), `notified_at` (nullable); unique condition is `(run_id, kind, expectation_at)` |

Pattern dispositions: `candidate`, `monitoring`, `fix-applied`, `retired`, `dismissed`. Alert dispositions: `open`, `acknowledged`, `snoozed`, `dismissed`, `resolved`. A pattern marked fix-applied remains available for follow-up; it is not evidence of improved behavior. Retirement needs a reason and evidence reference or explicit owner judgment, preserved in an event.

Keep current projections in SQLite and append the corresponding event in the same transaction. Enable foreign keys, use short transactions and a bounded 5-second lock wait. Contention returns a visible retriable error without an invented success. Identical event/observation ID and normalized input payload is idempotent; changed payload for an existing ID fails. A repeated start with the same run ID and original normalized RunSpec returns the existing current run without rewinding its state; conflicting RunSpec fails. Compare retry payloads before validating time expectations against the new clock. Corrections create linked observations rather than overwriting originals. No queue service, general migration framework, or transcript index is required; use schema version 1 and fail clearly on unsupported versions.

For a corrupt or unsupported store, stop its watchers/writers, preserve the entire private directory for diagnosis, and explicitly initialize a different external `--data-dir` if monitoring must resume. Do not silently reset or overwrite evidence. This is a documented recovery procedure, not a migration/repair feature.

## 4. Skill Behavior and Timer

### Five skills

| Skill | Trigger and required behavior | Persisted result |
|---|---|---|
| `assign-advocate` | Start/resume advocacy for explicitly named work. Register/reuse a run, capture observable acceptance and exclusions, expected checkpoint/deadline, model roles and relevant cautions. Obtain one fresh independent read-only assessment using actual host capability and primary plan/evidence, not just coordinator narration. | Run + observation with actual analysis provenance; visible unavailable result if independence is unavailable |
| `status-inquisition` | Routine checkpoint/status request. Compare claimed progress with actual receipts and current acceptance; distinguish completed work, checks, waiting, uncertainty and next action. Inspect supporting files only as needed. | Checkpoint + bounded assessment; can raise a cowbell if evidence warrants |
| `coordination-cowbell` | User escalation or watchdog alert. Investigate the named condition, plausible workflow/model/environment causes, and an actionable next move. An overdue expectation is a reason to investigate, not proof of defective work. | Evidence-backed observation and alert disposition; no automatic build stop, rollback, gate override or scope expansion |
| `model-mother` | Explicit research request or explicit model-list refresh. Read exact supplied model roles or the stock list, use host web tools, prefer current official sources, and preserve dates, versions, scope and uncertainty. Community reports remain candidates. | Scoped private pattern updates and a concise change report; no automatic routing/settings changes |
| `advocate-wrap` | Completed, stopped, or abandoned work. Reconcile observed problems and advice; classify new rule gap, existing rule missed, rule conflict/obsolete rule, environmental failure, task-specific correction, or unsupported hypothesis. Identify owner and dispositions; distinguish fix applied from later benefit. | Run outcome + observations/pattern dispositions; carry useful cautions and retire superseded ones |

`status-inquisition` starts neutral; `coordination-cowbell` starts escalated. Their output may discover a more serious issue regardless of entry point. Advising a correction does not execute it; separate existing user authorization governs actions by the coordinator.

Independent assessment is implemented in the skill through native host tools, not a Python model client. If unavailable, preserve a limited/coordinator assessment without labeling it independent. Missing web capability similarly leaves a model refresh unavailable; retain dated prior guidance rather than inventing fresh research. No fallback API credential or substitute host is introduced.

Each skill reads only the short shared contract and records relevant to its run. `brief` retrieves at most five applicable patterns, excluding retired and dismissed patterns, prioritizing exact model/role matches and confirmed local observations, then updated time and key for deterministic ties. Scope dimensions combine with AND, values within a dimension with OR; an empty dimension matches any run, a nonempty dimension without matching known run data does not match. Runs have no tag field in v0, so nonempty tag scopes cannot match. Candidates remain labeled; never load every historical caution. The stock list names Astra, Terra, Sol, Fable and Opus as user-editable family labels, not resolved version claims. Requested exact model IDs from a real run take precedence for research.

Seed five generalized workflow cautions: repeated validation; review churn without new evidence; scope growth beyond acceptance; environment/resource failure mistaken for code failure; and high-effort behavior requiring model-specific assessment. Seed only public-source guidance or explicitly labeled hypotheses. Do not copy private historical build facts into the public seeds.

### State and expectations

Run states are `active`, `checking`, `waiting`, `paused`, `unknown`, `finished`. Start requires a future `next_check_at`; `deadline_at` is optional. A checkpoint explicitly updates state and next expected visibility. For `waiting`, a nonempty checkpoint `summary` gives the reason, with a future next check; `paused` suppresses alerts. Resume is a checkpoint to a nonpaused state with an explicit next check; it does not silently extend the overall deadline. `finish` sets outcome `completed`, `stopped`, or `abandoned`, records a summary and stops monitoring. No file timestamp or absence of errors marks a run complete.

The watchdog evaluates `checkpoint-overdue` when now is past `next_check_at`, and `deadline-overdue` when an overall deadline exists and has passed. Checking/waiting work may legitimately be long; use its declared next check rather than assuming all silence is idle. Paused and finished runs create no new overdue alerts. Resuming with an expired overall deadline alerts normally unless that deadline was explicitly revised with a reason. Show wall-clock age and recorded state segments; do not label them measured model compute time.

Deduplicate on the alert condition key. Polling an unchanged condition changes only last-seen; it does not repeatedly print or ring. Acknowledgment suppresses repeated notifications for that condition without clearing the problem. Dismissal requires a reason. Snooze requires a future UTC time; notify once when it expires if the condition remains. A new expectation creates a new condition; resolve old checkpoint alerts when that expectation changes and old deadline alerts when the deadline is replaced or removed, in the checkpoint transaction. Resolve applicable alerts on finish. Preserve history. Pause suppresses notification without erasing it; re-evaluate on resume. Database uniqueness/transactional notification claiming prevent two watchers from ringing for the same condition in normal concurrent operation; a crash between persistence and console output may leave a saved alert unprinted, and startup/status must show open alerts.

`watch` is a foreground process in an explicitly opened watch terminal. Default interval is 60 seconds; accept positive fractional seconds for short tests. Persist every alert and flush output immediately. Ctrl+C stops only this watcher, preserving the run and evidence. Restart attaches to the same run and original expectations. `--once` performs one evaluation for diagnostics; `--bell` adds a terminal bell on a new notification, without claiming a Windows desktop notification. No daemon installation, OS scheduler, background LLM dispatch, or autonomous fix is included in v0.

## 5. Modules

| Planned file/module | Responsibility |
|---|---|
| `src/agent_advocate/cli.py` | argparse commands, JSON file inputs, stable output/errors and exit status |
| `src/agent_advocate/store.py` | Private path selection, schema, transactions and idempotent records |
| `src/agent_advocate/service.py` | Run/checkpoint/observation/pattern lifecycle and brief selection |
| `src/agent_advocate/watch.py` | Pure due-condition evaluation plus foreground polling/notification |
| `.agents/skills/<skill-name>/SKILL.md` | One of the five host-invoked workflows; normal Codex discovery |
| `documentation/skill-contract.md` | Short shared instructions, schemas/CLI pointers and evidence boundaries |
| `data/seed-patterns.json`, `data/model-families.json` | Generalized public seeds and editable stock model families |
| `tests/` | Behavior, CLI/process integration, privacy and timer cases |
| `documentation/acceptance.md` | Exact prepared live-host/timer observation procedure, authored in Step 3 |

Combine adjacent Python modules if implementation remains clearer; do not add abstraction layers merely to match this table. Dependencies point from CLI/watch to service/store; persistence owns the schema once.

## 6. CLI Contract

All commands accept global `--data-dir PATH` before the subcommand. Machine-readable commands return one JSON object to stdout; warnings/errors go to stderr. Exit 0 means the operation succeeded, not that a build is healthy. Exit 2 means invalid request/setup, 3 means unavailable/corrupt/unsupported store, 4 means bounded contention (retryable). Watch prints timestamped human-readable updates; Ctrl+C exits cleanly. `status`/`brief` explicitly show overdue/unknown state and unresolved alerts despite exit 0.

| Command after `agent-advocate` | Input / output |
|---|---|
| `init` | Create the private store and idempotently import public seeds; return path and schema version |
| `start --file PATH` | JSON RunSpec: optional `run_id`, `project_path`, `goal`, `acceptance`, `non_goals`, `models`, `next_check_at`, nullable `deadline_at`; return run UUID and persisted run |
| `checkpoint RUN_ID --file PATH` | JSON CheckpointSpec: optional `event_id`, `state`, `summary`, `next_check_at`, optional revised `deadline_at` plus `deadline_reason`; omitted deadline preserves it, null removes it, replacement/removal requires reason. Store event and return current run. Future next-check required for nonpaused/nonfinished states; use finish for terminal state. |
| `status RUN_ID` | Current run, timestamps, latest checkpoint, open/snoozed alerts and evidence availability; read-only |
| `brief RUN_ID` | Run acceptance/scope, at most five relevant cautions with source/basis/disposition, and current alerts; read-only |
| `observe RUN_ID --file PATH` | JSON ObservationSpec matching Observation fields other than helper-assigned run/time; verify cited local evidence exists, copy bounded excerpt, return observation UUID |
| `patterns import --file PATH` | JSON array of Pattern records without helper timestamps. Validate the entire request before transaction. Upsert by stable key, record revisions; exact content replay makes no new event. Public seed import must not reset private dispositions. |
| `pattern PATTERN_KEY --disposition VALUE --reason TEXT` | Update an existing pattern, with `--evidence OBSERVATION_ID` for supported local dispositions; return revised pattern |
| `alert ALERT_ID --action acknowledge|dismiss|snooze --reason TEXT [--until UTC]` | Persist response to an existing alert; snooze requires future `--until` |
| `watch RUN_ID [--interval 60] [--once] [--bell]` | Observe one known run in foreground; no model calls or monitored-project writes |
| `finish RUN_ID --outcome completed|stopped|abandoned --summary TEXT` | Persist outcome and finish state; repeated identical finish is idempotent; conflicting terminal rewrite fails |

There is no HTTP API. Do not build a general schema/plugin framework to validate these few inputs. JSON files are UTF-8 and emitted to private/temp locations by the skills. Request size is bounded at 256 KiB; evidence excerpts at 8 KiB each. Missing or stale evidence is visible rather than silently treated as verification. Reads do not update cursors or reset timers.

## 7. Project Structure and Skill Discovery

The scaffold initially contains only plan/instruction/privacy files and review/proposal/handoff documents. All source, runtime fixtures, skills and commands above are **planned outputs**, not references to already working files.

```text
agent-advocate/
  AGENTS.md, CLAUDE.md, README.md, plan.md
  pyproject.toml, uv.lock                 # Step 1
  src/agent_advocate/                    # Steps 1, 3
  tests/                                # Steps 1-3
  .agents/skills/<five named skills>/    # Step 2
  data/                                 # Step 2
  documentation/                        # planning now; acceptance in Step 3
```

Open Codex in this repository (or a child directory) to discover its `.agents/skills` packages. Each SKILL.md derives this checkout from its own location and uses `uv run --project <resolved-checkout> --locked agent-advocate ...`, so executing a command after a cwd change does not select another project. These are first-party product skills, not generated Skill Mesh catalog entries. No global skill installation, external profile overwrite, or Skill Mesh build is necessary. The monitored repository is always the explicit `project_path` of the run and may be elsewhere.

External producer basis: official Codex skill documentation describes a `SKILL.md` directory with YAML `name` and `description` and project discovery under `.agents/skills`. Source read 2026-09-23: https://learn.chatgpt.com/docs/build-skills . Native discovery and actual tool capability are demonstrated separately in M1; documentation is not runtime proof. Web/agent calls use tools available in that Codex session; do not prescribe a nonexistent CLI agent flag.

## 8. Key Design Decisions

- **Advisory authority:** advocate reports evidence and recommendations. It is not a new merge gate, model router, or autonomous fixer.
- **Explicit visibility:** skills submit checkpoints; v0 does not parse every host transcript or infer real work from token output. Unknown visibility remains unknown.
- **Private by default:** external store and private receipts; only synthetic fixtures and public-source generalized cautions are committed.
- **One shared store:** the five entry points reuse the same schema and helper. Observation, inference, recommendation, and verified outcome stay distinguishable.
- **Independent review:** actual independent assessment is a product behavior and cannot be satisfied by printing a prompt. It runs on skill invocation, not on the watchdog's timer.
- **Time proportionality:** short real process observations verify the timer. No multi-hour soak, productivity benchmark, or fixed quota of build sessions is required for v0.
- **Local gate reuse:** keep the full project suite. An already completed integrated-state run can satisfy an immediately enclosing checkpoint only while its source/tests/dependencies/config/generated inputs are identical. Candidate-only results do not replace validation of a changed integrated state. No other project gate is changed here.

## 9. Risks and Deferred Work

| Risk / boundary | v0 response |
|---|---|
| Self-reported progress can be wrong | Independent assessment checks primary evidence; checkpoints retain basis/source |
| Missing checkpoint mistaken for failure | Alert says visibility overdue; diagnostic skill determines implications |
| Memory of every incident slows later work | Retrieve a few relevant patterns; wrap retires or dismisses unhelpful cautions |
| A model report becomes a universal rule | Scope by exact model/role/host where known, retain source/date and hypothesis status |
| Private data reaches public Git | External store, ignore defense, synthetic fixtures and explicit publication review; no automatic runtime exporter |
| Concurrent writer or watcher failure | SQLite transactions/uniqueness, bounded timeout, visible errors; no silent lost update |
| No browser or independent agents in a host | Mark actual capability unavailable; do not claim all skills accepted |

v1 candidates: Claude qualification; automatic watchdog-to-diagnostic dispatch; richer review-loop/test-receipt ingestion; Switchboard inventory read; optional existing-observatory summary artifact; and wider skill installation. No v1 issue is an implicit v0 acceptance requirement. No license grant is invented during public setup; a distribution license is a separate owner decision, not a v0 build blocker.

## 10. How to Run (after the named build step)

Prerequisites: Git, Python 3.12+, uv; for the five skills, a Codex host with project discovery, independent agents and web search. The Python utility itself needs neither an account nor API keys. Commands below are the Step 1/3 target contract, not runnable in the planning-only scaffold.

```powershell
# From this checkout, after Step 1 has created pyproject.toml and uv.lock:
uv sync --locked
uv run --locked agent-advocate init
uv run --locked agent-advocate --help
uv run --locked python -m pytest
```

In a fresh Codex session at the checkout, invoke `$assign-advocate` and name the project, outcome, acceptance and expected next check. The skill writes the private RunSpec and returns the real run UUID. It may infer routine scope defaults from the supplied plan; missing time expectations must be explicitly chosen/reported, never invented as historical measurements.

```powershell
# Copy the actual run UUID printed by assign-advocate:
$advocateRun = 'REPLACE_WITH_RETURNED_RUN_UUID'
uv run --locked agent-advocate status $advocateRun
uv run --locked agent-advocate watch $advocateRun --interval 60 --bell
```

Open that watcher in a terminal you can see. Ctrl+C stops monitoring without stopping the build. Invoke `$status-inquisition` at meaningful checkpoints; `$coordination-cowbell` when alerted; `$model-mother` for a deliberate research refresh; `$advocate-wrap` at completion/stop. Each invocation names the run rather than guessing the newest unrelated session.

## 11. Development Process

The public repository is prepared through plan-review, plan-redline, plan-wrap and repo-init. The build handoff then runs the three code steps in order in isolated worktrees. Stakes-aware routing uses `--reviewers deep` for Step 1's persistent schema and Step 3's timer/store producer-consumer boundary; Step 2 uses `--reviewers code`. These are bounded reviews of the named step, not a Skill Mesh-wide review or a model-tier escalation. GitHub issues are derived from these steps; repository identity is checked before mutations.

Before Step 1, no runtime suite exists: record the baseline as **not yet created**, never as zero passing tests. Step 1 creates the smallest meaningful suite. Thereafter `uv run --locked python -m pytest` is the full gate. Do not write tests asserting prose headings or test-count growth. Run narrowly during repairs, broaden at completion or when shared behavior changes. Code-step reports include evidence and remaining limitations; M1 alone qualifies actual host behavior.

### Automated Steps

### Step 1: Persist an advocated run and its evidence

- **Problem:** A coordinator needs one durable place to register work, checkpoints, observations and cautions without exposing private evidence.
- **Type:** code
- **Status:** TODO
- **Issue:** #1
- **Flags:** --reviewers deep --isolation worktree
- **Files:** `.gitignore`; `pyproject.toml`; `uv.lock`; `src/agent_advocate/__init__.py`; `src/agent_advocate/cli.py`; `src/agent_advocate/store.py`; `src/agent_advocate/service.py`; `tests/test_store.py`; `tests/test_cli.py`; `tests/test_privacy.py`; `README.md`; `CLAUDE.md`; `plan.md` (status/evidence only).
- **Produces:** installable console entry point; schema version 1; run/checkpoint/observation/pattern/brief/status/finish commands; private store initialization; focused tests; runnable quickstart. `init` handles an absent seed file before Step 2 as an empty initial pattern set.
- **Done when:** a real CLI subprocess creates a private store, registers a temporary repository, persists a checkpoint/observation, reads it from a fresh process and finishes the same run; identical event retries are idempotent and conflicting payloads fail; two writers preserve their events or report bounded contention; a data directory inside a Git tree is refused; missing/stale local evidence is visible; wrong-cwd invocation through `uv --project` works; `uv run --locked python -m pytest` and `git diff --check` pass. No model call is needed for this step.
- **Depends on:** none

### Step 2: Deliver the five advocate skills

- **Problem:** Persisted records need actual host-invoked advocacy, research and closeout workflows.
- **Type:** code
- **Status:** TODO
- **Issue:** #2
- **Flags:** --reviewers code --isolation worktree
- **Files:** `.agents/skills/assign-advocate/SKILL.md`; `.agents/skills/status-inquisition/SKILL.md`; `.agents/skills/coordination-cowbell/SKILL.md`; `.agents/skills/model-mother/SKILL.md`; `.agents/skills/advocate-wrap/SKILL.md`; `documentation/skill-contract.md`; `data/seed-patterns.json`; `data/model-families.json`; `src/agent_advocate/service.py`; `src/agent_advocate/cli.py`; `tests/test_patterns.py`; `tests/test_skill_resources.py`; `README.md`; `plan.md` (status/evidence only).
- **Produces:** five concise discoverable packages using the same CLI and shared contract; sourced public cautions; stock model families; deterministic brief retrieval and pattern dispositions; public synthetic input examples in the shared contract.
- **Done when:** package frontmatter identifies the five names and every local resource reference resolves; seed imports preserve private dispositions and do not duplicate identical content; brief selection returns at most five applicable patterns with candidates visibly labeled; corrections/wrap preserve source provenance and distinguish fix-applied from improved outcome; missing native agent/web capability instructions produce explicit unavailable behavior; full project tests and diff check pass. These checks certify package/mechanical behavior only; live skill execution remains M1.
- **Depends on:** 1

### Step 3: Raise persistent overdue alerts with a real watchdog

- **Problem:** A user needs an unattended timer that notices overdue expectations without turning every poll into a model call or repeated alarm.
- **Type:** code
- **Status:** TODO
- **Issue:** #3
- **Flags:** --reviewers deep --isolation worktree
- **Files:** `src/agent_advocate/watch.py`; `src/agent_advocate/cli.py`; `src/agent_advocate/service.py`; `src/agent_advocate/store.py`; `tests/test_watch.py`; `tests/test_watch_process.py`; `documentation/acceptance.md`; `README.md`; `CLAUDE.md`; `plan.md` (status/evidence only).
- **Produces:** default-60-second foreground watcher, persistent/deduplicated alert notifications, acknowledgment/dismissal/snooze and pause/resume behavior; short real subprocess smoke; exact live-host acceptance recipe with all example request files authored before M1.
- **Done when:** an actual watcher process notices a due checkpoint and persists/prints one alert; a second process updates/checks the same run; unchanged polls and a competing watcher do not duplicate normal notification; snooze expiry re-notifies once, pause suppresses, resume preserves the deadline, and finish ends monitoring; restart retains run/deadline/alert identity; store errors exit visibly; Ctrl+C leaves the run intact; pure clock tests cover deadlines without long sleeps; full project tests and diff check pass. Prepare M1 instructions for two normal 60-second poll intervals plus a short configured overdue demonstration; no multi-hour soak.
- **Depends on:** 1, 2

### Manual Steps

### Step M1: Observe the five skills and timer in a fresh Codex session

- **Problem:** Mechanical tests cannot prove native skill discovery, actual independent assessment, live research, and visible watcher behavior.
- **Type:** operator
- **Status:** TODO
- **Issue:** #4
- **Files:** `documentation/acceptance.md` (read-only procedure), `plan.md` (acceptance status only).
- **Produces:** observed verdict, sanitized result summary and private evidence references only; no source/config/runbook authorship.
- **Done when:** follow the already-authored procedure in a fresh Codex session: discover all five skills; assign advocacy to a real bounded task and obtain an actual independent assessment; persist a checkpoint and retrieve it in a fresh invocation; research at least one exact named model through a real public source and persist a scoped caution; observe the real watchdog across two default poll intervals and one short overdue case; invoke cowbell to diagnose/dispose the alert; wrap with a real outcome and retrieve its relevant pattern later. Missing agent/web capabilities or unobserved skill execution make acceptance incomplete. Record mechanisms demonstrated separately from any unproven long-term productivity benefit. No live profile or monitored-project change is necessary.
- **Depends on:** 1, 2, 3
- **Commands:**

  ```powershell
  # The complete exact requests and checks are prepared by Step 3:
  Get-Content documentation/acceptance.md
  uv run --locked agent-advocate --help
  ```

- **What to look for:**

  | Check | Expected outcome |
  |---|---|
  | Native skills and independent assessment | Actual loaded packages and separate host-returned reviewer evidence |
  | Checkpoint and research persistence | Fresh invocation reads the correct run; source/model scope is explicit |
  | Watch terminal | One visible alarm per due condition; records survive restart |
  | Cowbell and wrap | Evidence, recommendation and disposition remain distinct; false alarms may be dismissed |
  | Privacy | Runtime evidence stays external; public outcome contains no local paths or private excerpts |

After Steps 1-3, hand off **Please run M1 next**. Do not mark v0 fully accepted from code-step success alone.

## 12. Appendix

### Decision Inventory

| ID | P/D | choice | status |
|---|---|---|---|
| P1 | P | Agent Advocate before-work/checkpoint/after-work structure | approved 2026-09-22 |
| P2 | P | Five named skills, including advocate-wrap | approved 2026-09-22 |
| P3 | P | SQLite and a configurable 60-second timer in v0 | approved 2026-09-22 |
| P4 | P | Codex first; model-assisted diagnosis through invoked skills | approved 2026-09-22 |
| P5 | P | v0 first, use it for v1, then resume Skill Mesh work | approved 2026-09-22 |
| P6 | P | Public repository; private data may be kept private | approved 2026-09-22 |
| P7 | P | Previously accepted build/plan/review/effort remedies remain future Skill Mesh work | approved 2026-09-22 |
| D1 | D | Standard-library Python runtime, uv, pytest dev, setuptools console entry | selected for small local build; implementation detail |
| D2 | D | External per-user store; no public runtime exporter | selected to enforce private evidence boundary |
| D3 | D | Project-local Codex skills; monitor targets through explicit run paths | selected to avoid installer/catalog dependencies in v0 |
| D4 | D | Three code slices plus one short live acceptance | selected for useful slices and bounded proof |
| D5 | D | Explicit checkpoints; timer never launches models or fixes | selected to keep watchdog predictable and cheap |
| D6 | D | At most five relevant cautions; candidates remain hypotheses | selected to limit irrelevant context; tune after real use |

### Public source seeds

- OpenAI, [Rethinking skills and prompts for GPT-6 Astra](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra), 2026-09-11: legacy prompt scaffolding can cause unnecessary testing; guidance is model-specific.
- Anthropic, [Prompting Claude Fable 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5), checked 2026-09-23: high-effort routine work can overexplore; progress claims should cite actual evidence.
- OpenAI, [Build skills](https://learn.chatgpt.com/docs/build-skills), checked 2026-09-23: package discovery/metadata guidance; live availability remains an acceptance observation.

No local project history, private session transcript, or user-specific absolute path is included in these sources or future public seed fixtures.
