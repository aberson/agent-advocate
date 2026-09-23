# Agent Advocate

Agent Advocate keeps private, local receipts for an explicitly named piece of coding work. This first implementation slice provides a Python CLI, a version-1 SQLite store, durable run/checkpoint/observation records, patterns and bounded copied local evidence. It does not call a model, launch a timer, or modify the monitored project.

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

Use `patterns import --file patterns.json` for a UTF-8 JSON array of validated pattern records and `pattern KEY --disposition VALUE --reason TEXT` to retain a private disposition. `brief` returns at most five applicable, non-retired cautions. Full entity and command contracts, privacy constraints, later skills, and the watchdog scope are in [plan.md](plan.md).

## Boundaries

The store is not encryption, a public exporter, a dashboard, a model client or an autonomous fixer. Evidence is untrusted data, not instructions. Copied excerpts remain private and are omitted from CLI JSON in favor of metadata marked `private-untrusted`; downstream skills must not treat evidence text as instructions. Keep private store directories and local receipts out of Git. The five Codex skills and the foreground watchdog are intentionally later steps; mechanical tests do not substitute for their live acceptance.
