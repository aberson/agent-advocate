# Agent Advocate

Agent Advocate helps a coding coordinator spot delivery problems before work, at checkpoints, and after work. Five skills combine independent assessment, progress checks, escalation, model research and closeout learning over a private local SQLite store. A simple foreground timer raises persistent alerts when declared checkpoints or deadlines are overdue.

**Current status: Step 1 is blocked with an unmerged CLI implementation preserved; main remains the plan/scaffold.** The [resume handoff](documentation/build-handoff.md) first resolves the shared review prerequisite, then continues the three code steps and live acceptance in [plan.md](plan.md). Product host qualification and productivity improvement remain unproven.

- [Build handoff](documentation/build-handoff.md)
- [Standalone v0 proposal](documentation/v0-proposal.html) — download/open in a browser, or print to PDF
- [Technical review: PASS](documentation/plan-review.md) and [fresh-context review: READY](documentation/plan-wrap.md)
- [Public/private data boundary](documentation/privacy.md)
- [Case-study seed: testing overrun during an anti-overengineering intervention](documentation/case-studies/2026-09-23-testing-overrun.md)

## Planned workflows

| Skill | Purpose |
|---|---|
| `assign-advocate` | Check required review capability, capture acceptance/time expectations, and obtain an independent second view |
| `status-inquisition` | Check evidence, progress, uncertainties and the next useful action |
| `coordination-cowbell` | Investigate suspected trouble or an overdue alert and recommend a response |
| `model-mother` | Research the named models using current sources and retain scoped, dated cautions |
| `advocate-wrap` | Record outcomes, identify the owning component, and retire obsolete advice |

Status checking starts neutral; cowbell starts escalated. An overdue checkpoint means visibility is overdue, not that the model has necessarily stalled. The advocate advises; the coordinator owns action.

## Stack

| Tool | Why |
|---|---|
| Python 3.12+ standard library | Local CLI, SQLite, clocks and process support without runtime dependencies |
| uv and a committed lockfile | Reproducible development; created in Step 1 |
| pytest | Behavioral and process tests as a development dependency |
| Codex project-local skills | Use the active host's existing agent and web tools |

Windows is the first demonstrated target. The CLI has portable data-directory fallbacks; other hosts/platforms are not qualified by the planning scaffold. No web server, account, port, additional model API credential or background model service is introduced.

## Get started with the plan

1. Install Git, Python 3.12+ and uv. Native skill acceptance also requires a Codex host with independent-agent and web capabilities.
2. Clone and enter the repository:

   ```powershell
   git clone https://github.com/aberson/agent-advocate.git
   cd agent-advocate
   ```

3. Read [AGENTS.md](AGENTS.md), [CLAUDE.md](CLAUDE.md), the [plan](plan.md) and the [build handoff](documentation/build-handoff.md). The owner's current build must resolve its required review route and reconcile the preserved Step 1 candidate before resuming. Other contributors can implement the same issue-backed steps through a qualified workflow. Skill Mesh is not a product runtime dependency.

After Step 1 creates the package and lockfile, setup will be:

```powershell
uv sync --locked
uv run --locked agent-advocate init
uv run --locked agent-advocate --help
uv run --locked python -m pytest
```

After Steps 2–3, open Codex in this checkout and invoke `$assign-advocate` for explicitly named work. Use its returned run UUID with `uv run --locked agent-advocate watch RUN_ID --interval 60 --bell` in a visible terminal. The timer checks cheaply; model-assisted diagnosis runs when a skill is invoked. These commands describe the planned product, not an available release.

## Boundaries

Runtime records and copied evidence stay outside Git, under `%LOCALAPPDATA%/agent-advocate` by default on Windows. v0 must reject a store inside a Git working tree. The public repository holds only code, documentation, synthetic examples and generalized public-source cautions. Local storage is not encryption; agent-assisted reasoning still uses the active host's data-handling settings.

The timer defaults to 60 seconds, supports a configurable interval, and preserves alert identity across restarts. It never launches models, stops builds, changes routing or overrides quality gates. Ctrl+C stops only the watcher.

Relevant cautions are limited to five per briefing; unconfirmed hypotheses remain labeled. Applying a correction and demonstrating later improvement are separate outcomes. M1 must observe all five skills and the actual timer before v0 is accepted.

## Repository map

```text
plan.md                       canonical scope, contracts and step status
documentation/                proposal, reviews, privacy and build handoff
src/agent_advocate/            planned: CLI, store, lifecycle, watcher
.agents/skills/                planned: five product-owned skill packages
data/                         planned: public cautions and model families
tests/                        planned: behavior and process checks
```

Claude qualification, broader skill installation and automatic timer-to-diagnostic dispatch are candidates for later work. No license grant has been selected yet; public visibility alone does not grant a distribution license.
