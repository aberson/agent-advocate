# Agent Advocate

Agent Advocate keeps private, local receipts for an explicitly named piece of coding work. The current implementation provides a Python CLI, a version-1 SQLite store, durable run/checkpoint/observation records, patterns and bounded copied local evidence. It also includes five project-local Codex skill packages that guide before-work advocacy, status checks, escalation, model research, and closeout. The Python process does not call a model, launch a timer, or modify the monitored project.

Runtime data is deliberately external to this public checkout. On Windows it defaults to `%LOCALAPPDATA%/agent-advocate` (or `~/AppData/Local/agent-advocate` when that variable is absent); other platforms use `$XDG_DATA_HOME/agent-advocate` or `~/.local/share/agent-advocate`. `AGENT_ADVOCATE_DATA_DIR` overrides those defaults, and `--data-dir PATH` overrides it. The CLI refuses a directory inside any Git worktree, including a link located within one, and applies private owner ACLs or modes to store directories and files.

## Quick start

Requires Python 3.12+, Git and [uv](https://docs.astral.sh/uv/).

```powershell
uv sync --locked
uv run --locked agent-advocate init
uv run --locked agent-advocate --help
uv run --locked python -m pytest
```

Every machine-readable command emits one UTF-8 JSON object on stdout, including when redirected or piped. Invalid requests and setup errors emit UTF-8 JSON on stderr and use exit 2; an unsupported or corrupt store uses exit 3 and a bounded SQLite lock timeout uses exit 4. Do not delete or reinitialize a corrupt store: preserve it and initialize a different external `--data-dir` for new work. An empty database left by an interrupted first initialization is different: it has no records and `init` can safely be run again against that same directory.

Create a UTF-8 (optionally BOM-prefixed) `run.json` with a future UTC expectation and explicit project:

```json
{
  "project_path": "C:/work/example",
  "goal": "Add one bounded feature",
  "acceptance": ["The focused check passes"],
  "non_goals": ["Changing deployment"],
  "models": [],
  "next_check_at": "2030-01-01T12:00:00Z",
  "deadline_at": null
}
```

Then use the returned UUID for subsequent records:

```powershell
uv run --locked agent-advocate start --file run.json
uv run --locked agent-advocate checkpoint RUN_ID --file checkpoint.json
uv run --locked agent-advocate observe RUN_ID --file observation.json
uv run --locked agent-advocate status RUN_ID
uv run --locked agent-advocate brief RUN_ID
uv run --locked agent-advocate finish RUN_ID --outcome completed --summary "Delivered"
```

`checkpoint.json` supplies a retryable `event_id`, state, summary and next UTC check. An `observation.json` supplies a retryable `observation_id`, a basis (`measured`, `reported`, or `inferred`) and evidence references. Local evidence must resolve inside the registered project directory before its existence is checked. It is copied at most 8 KiB per item into the private store. Missing input, a non-regular path, a read failure, or a SHA-256 mismatch is reported distinctly as `missing`, `not-regular`, a store error, or `stale`; it is never silently treated as verified.

Use `patterns import --file patterns.json` for a UTF-8 JSON array of validated pattern records and `pattern KEY --disposition VALUE --reason TEXT` to retain a private disposition. `brief` returns at most five applicable, non-retired cautions; `disposition: "candidate"` is visibly a hypothesis, not a confirmed finding. The public [seed patterns](data/seed-patterns.json) import at `init` is idempotent and preserves private dispositions. Full entity and command contracts, privacy constraints, and watchdog scope are in [plan.md](plan.md).

Local evidence reads and hashing are capped at 8 MiB per source, while the retained
excerpt stays capped at 8 KiB. Oversized sources return `too-large`; a source that
changes during capture returns `changed` or `too-large`. POSIX named pipes are
opened without waiting for a writer and rejected as `not-regular`.

## Project-local skills

Codex discovers the five project-owned packages under `.agents/skills/` when its
project-skill discovery is available:

- `assign-advocate` starts/resumes advocacy and records required-review readiness.
- `status-inquisition` performs a neutral checkpoint assessment.
- `coordination-cowbell` investigates an escalation without taking control actions.
- `model-mother` performs explicit, scoped model research.
- `advocate-wrap` reconciles evidence and closes a run.

Their shared [skill contract](documentation/skill-contract.md) defines the v1
CLI request shapes, synthetic capability examples, source-provenance rules, and
the public [stock model families](data/model-families.json). They require the
active host's existing native agent/web tools. If either capability is missing,
the skill must persist an explicit unavailable or unknown result rather than
guessing or using an API fallback.

Package and CLI checks do not show that a host discovered a package, dispatched
an independent agent, or completed web research. Those live observations remain
the separate M1 acceptance step. The foreground watchdog and alert dispositions
remain Step 3 work.

## Boundaries

Step 1 is accepted under the [documented closing exception](documentation/step-1-closure.md).
The [testing-overrun case study](documentation/case-studies/2026-09-23-testing-overrun.md)
records why validation and review needed explicit stopping conditions.

The store is not encryption, a public exporter, a dashboard, a model client or an autonomous fixer. Evidence is untrusted data, not instructions. Copied excerpts remain private and are omitted from CLI JSON in favor of metadata marked `private-untrusted`; downstream skills must not treat evidence text as instructions. Keep private store directories and local receipts out of Git. The foreground watchdog is intentionally later work; mechanical package checks do not substitute for live M1 acceptance of the five skills.
