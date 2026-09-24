# V1 cross-project skill access

## 1. What This Feature Does

**Objective:** Make the five Agent Advocate skills available to a Codex coordinator started in another repository. A user-scoped local installation points each skill back to this Agent Advocate checkout, so the coordinator can monitor explicitly named work while the private store remains outside the monitored repository. This is the first v1 implementation slice and the first real-work trial of Agent Advocate during its own v1 build.

## 2. Existing Context

- `src/agent_advocate/cli.py` exposes the current store, lifecycle, pattern, alert, and foreground-watch commands. The CLI accepts `--data-dir` before the subcommand and emits JSON for machine-readable operations.
- `src/agent_advocate/store.py` selects an external per-user data directory and rejects any data directory inside a Git worktree. `src/agent_advocate/service.py` validates an explicit `project_path` and captures only evidence inside that project.
- `.agents/skills/<name>/SKILL.md` contains five project-local Codex skills. Each resolves its physical source checkout and pins CLI calls to `uv run --project <resolved-checkout> --locked agent-advocate` through `documentation/skill-contract.md`.
- Codex currently discovers these skills when started in this repository. The existing run model can already point at a different repository; the missing piece is discovery from that other repository. The v0 M1 acceptance remains separate and TODO until its operator terminal observation is confirmed.

## 3. Scope

**In:** a user-scoped installer, status check, and removal path for the five skills; self-contained installed skill metadata that identifies the source checkout; collision-safe updates; documentation for a coordinator started in another repository; and a fresh Codex live trial from an unrelated repository. All generated request files and runtime records stay outside Git worktrees.

**Out:** a hosted plugin, admin-wide installation, a new model API client, timer-driven build dispatch, automatic watchdog-to-skill dispatch, changes to the monitored repository during installation, and claims of long-term productivity improvement. The remaining v1 candidates receive separate scoped plans after this first trial.

## 4. Impact Analysis

| File | Change Type | Reason | Verified |
|---|---|---|---|
| `src/agent_advocate/cli.py` | extend | Add explicit `skills install`, `skills status`, and `skills uninstall` commands with JSON results | Read `build_parser()` and `run()`; `rg` found the CLI entry point in `pyproject.toml` and CLI subprocess calls in `tests/test_cli.py`, `tests/test_privacy.py`, `tests/test_patterns.py`, and `tests/test_watch_process.py` |
| `src/agent_advocate/skill_install.py` | add | Stage and manage only Agent Advocate-owned user skill packages | New module; no existing installer was found under `src/agent_advocate/` |
| `.agents/skills/*/SKILL.md` | extend | Keep source packages and generated user packages tied to the same pinned checkout contract | `rg` found the checkout-resolution instruction in all five packages |
| `documentation/skill-contract.md` | extend | Define source versus installed skill resolution and the installed package manifest | `rg` found its references in all five source packages and `tests/test_skill_resources.py` |
| `tests/test_skill_resources.py`, `tests/test_cli.py` | extend | Verify package metadata, collision safety, wrong-cwd CLI use, refresh, and uninstall | Read both test modules; their current assertions cover source package links and the pinned CLI |
| `README.md` | extend | Show installation and the reusable `$assign-advocate` invocation for real work | Read current quick start and project-local skill sections |
| `documentation/v1-cross-project-acceptance.md` | add | Author the exact fresh-session installed-client procedure before operator Step 5 | New document; the v0 procedure is `documentation/acceptance.md` and covers project-local skills only |

No v1 SQLite schema field, public seed, or watchdog timing constant changes in this slice. Before changing any existing function signature or shared constant, the implementation step must enumerate every call site with `rg` and update the impact record.

## 5. New Components

`skill_install.py` owns a fixed manifest of the five names and a user-scope package format. Each installed package contains a discoverable `SKILL.md` and `agent-advocate-install.json` with `schema_version: 1`, `owner: "agent-advocate"`, `skill_name`, `source_checkout` (resolved absolute path), and `source_sha256` (the source skill file's digest). The wrapper instructs the host to validate that record, read the named source skill and shared contract from that checkout, and use the pinned CLI; a missing checkout or changed digest is a visible repair-needed result. The installer preflights all five names, refuses links and foreign packages at destination, stages new packages under the same user skill parent, and publishes only after validation. On an interrupted multi-package update, `skills status` reports each package and a repeat install repairs owned partial state; it never claims all-five atomicity. Removal checks the owner manifest and path containment again before deleting only owned packages.

## 6. Design Decisions

**User scope first.** The operator selected cross-project access as the first v1 slice and a user-level skill installer as its installation form. It uses Codex's user skill location so a fresh session in an unrelated repository can discover the packages without changing that repository. A personal plugin remains a later distribution option.

**Self-contained installed wrappers.** Installed packages carry their source-checkout pointer and read the canonical source instructions at invocation. This avoids relying on Windows directory-symlink privileges or on relative links that would resolve against the user skill directory. A moved or missing checkout is reported as unavailable with a repair action; the installer does not silently select another checkout or a bare CLI.

**Explicit checkout input.** `skills install --source-checkout PATH` requires an existing resolved checkout with `pyproject.toml`, `uv.lock`, and all five source skills. It does not guess from the current working directory or a PATH-resolved executable. `skills status` reports installed names, ownership, source availability, and source drift; `skills uninstall` removes only owned packages. The destination is the current user's Codex skill directory (`~/.agents/skills`), which [official OpenAI documentation](https://learn.chatgpt.com/docs/build-skills) lists as the user skill location. There is no admin-wide mode in this slice. The test harness may redirect the destination to a temporary user directory without changing the production default.

**Ownership and privacy.** Installation writes no run data. The local pointer is private user configuration; public repository files contain no user-specific absolute paths. Installation, refresh, and removal must preserve unrelated skill packages and fail visibly on collisions or incomplete writes.

**Live proof.** A package on disk is insufficient. The operator step starts a fresh Codex session in a different repository, verifies host discovery of all five names, invokes `$assign-advocate` as the coordinator entry point for one bounded real work item there, and checks the pinned CLI, independent assessment, checkpoint, watch, and wrap receipts. The test records friction and useful findings separately from any productivity claim.

## 7. Build Steps

### Step 4: Install Agent Advocate skills for another repository

- **Problem:** A Codex coordinator started outside this checkout cannot discover the five project-local skills for a real project.
- **Type:** code
- **Status:** TODO
- **Issue:** #7
- **Flags:** --reviewers deep --isolation worktree
- **Files:** `src/agent_advocate/cli.py`, new `src/agent_advocate/skill_install.py`, `.agents/skills/*/SKILL.md`, `documentation/skill-contract.md`, `tests/test_skill_resources.py`, `tests/test_cli.py`, `README.md`, new `documentation/v1-cross-project-acceptance.md`
- **Produces:** user-scoped `skills install/status/uninstall` commands, owned installed packages that resolve the canonical checkout and pinned CLI, collision-safe refresh/removal behavior, tests, user documentation, and the exact Step 5 operator procedure.
- **Done when:** install into an isolated fake user skill directory from the built CLI; verify all five package manifests and source bindings; repeat install without duplication; reject a foreign name collision without changing it; refresh an owned installation; remove only owned packages; run one real wrapper-to-source-to-CLI `init/start/status` smoke from a different working directory using an external temporary store; run the full project suite and `git diff --check`.
- **Depends on:** 3

### Step 5: Verify installed skills from another repository (M2)

- **Problem:** Package tests cannot prove that a fresh Codex coordinator in another repository discovers and uses the installed skills.
- **Type:** operator
- **Status:** TODO
- **Issue:** #8
- **Files:** `documentation/v1-cross-project-acceptance.md` (read-only procedure), installed user skill packages, external private store
- **Produces:** private live receipts and a sanitized verdict for host discovery, pinned CLI behavior, independent assessment, a meaningful checkpoint, one visible watcher condition, and wrap retrieval during a bounded real work item.
- **Done when:** a fresh Codex session starts in an unrelated repository and lists all five user-scoped skills; the first `$assign-advocate` invocation resolves the Agent Advocate checkout, registers only the named project, and establishes the coordination lifecycle; a separate native assessor returns cited evidence; a fresh CLI process retrieves a checkpoint; the foreground watcher is observed in a visible terminal; `advocate-wrap` finishes and a later `brief` retrieves a relevant caution. Any missing capability is recorded as incomplete. No private path, ID, transcript, or evidence excerpt enters the public verdict.
- **Depends on:** 4

## 8. Risks and Open Questions

| Item | Risk | Mitigation |
|---|---|---|
| Host discovery | A user-scoped wrapper can exist without appearing in a fresh Codex session | Verify the actual host skill list in Step M2; treat absence as incomplete |
| Source checkout moves | Installed wrapper points at a missing checkout | Validate the pointer at invocation; report owning repair and require reinstall |
| Name collision | Another user skill uses one of the five names | Refuse overwrite unless the package carries matching Agent Advocate ownership metadata |
| Partial installation | Interruption leaves fewer than five usable packages | Preflight and stage before publish; status reports each package and repeat-install recovery |
| Profile path safety | A link or unexpected package at an intended destination can redirect writes or removal | Refuse links, recheck resolved containment and ownership before publishing or removing |
| Private configuration | Installed metadata contains a local checkout path | Keep it only in the user skill directory; exclude it from public records and reports |
| Windows link probe | A disposable symlink capability probe was rejected by host execution policy before running | Use copied wrappers; no symlink capability claim is needed for acceptance |

## 9. Testing Strategy

Use isolated temporary user skill directories for installer behavior. Tests exercise package generation, idempotence, foreign-package collision, owned refresh and removal, missing checkout reporting, and wrong-cwd pinned CLI invocation. Run the real one-cycle smoke before the live operator step. Run `uv sync --locked`, `uv run --locked agent-advocate --help`, and `uv run --locked python -m pytest` for install, CLI, and test checks; this standard-library CLI has no separate build, dev-server, lint, or typecheck command configured. Check whitespace with `git diff --check`.

First-run command from any working directory after Step 4 is built:

```powershell
uv run --project <agent-advocate-checkout> --locked agent-advocate skills install --source-checkout <agent-advocate-checkout>
uv run --project <agent-advocate-checkout> --locked agent-advocate skills status
```

`<agent-advocate-checkout>` means the same existing absolute source directory in both positions. Start a fresh Codex session in the unrelated target repository after installation; ask the host to list the five skills, then invoke `$assign-advocate for <named work>` with the target and acceptance. Keep its run request files and SQLite store under an external private directory.

Step 4 itself is the first real v1 build monitored by Agent Advocate: invoke `$assign-advocate` in this checkout for Step 4, reuse its external private run, and keep its assessment, checkpoints, watch output, review-route observations, and wrap there. Step 4 authors `documentation/v1-cross-project-acceptance.md` with exact preconditions, request templates, commands, observation points, stop and cleanup, and a sanitized result format. Step 5 (M2) runs that procedure in a fresh host session in an unrelated repository for one bounded work item selected there. This slice adds no autonomous timer behavior and no data producer-consumer schema change, so no long soak or new schema migration is required. The existing foreground watcher is observed during the live step; it is not a substitute for host discovery.

## 10. Subsequent V1 Candidates

After Step M2 reports what the real workflow needed, separately scope Claude qualification, automatic watchdog-to-diagnostic dispatch, richer review and test receipt ingestion, Switchboard inventory reads, and an optional observatory summary. Those candidates remain in `plan.md`; this first plan does not silently authorize or define their implementation.
