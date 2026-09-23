# Build handoff: Agent Advocate after Step 1

**Step 1 is accepted under the operator-approved P10 closing exception.** The
implementation is code commit `27e1ce1`; the [acceptance receipt](step-1-closure.md)
records the reused Windows suite, actual Linux FIFO test and independent closing
review. The old deep `NEEDS-WORK` and authenticated `BLOCKED` records remain
historical evidence, not the current acceptance decision. Do not restart Step 1.

Steps 2 (five skills), 3 (foreground watchdog) and M1 (live acceptance) remain TODO.
This closing session ends at Step 1; the operator owns the next project work.

## Resume the remaining work

Verify current Git state and read the current project instructions and plan:

```powershell
git rev-parse --show-toplevel
git remote get-url origin
git status --short
git log --oneline -5
```

Expected remote: `https://github.com/aberson/agent-advocate.git`. Preserve any
concurrent changes. The remaining host skill invocation is:

```text
/build-phase --plan plan.md --steps 2,3
```

This is a host skill invocation, not a PowerShell executable. Step 2 uses ordinary
code review; Step 3 retains its required deep review. P10 is a completed exception
for Step 1 and grants no standing waiver for another step. Set and record the
remaining run's bounds before dispatch; do not reset or replay earlier attempts.

The installed nested Codex route is qualified on the demonstrated collaboration
host; [Skill Mesh's receipt](https://github.com/aberson/skill-mesh/blob/110d916/documentation/findings/codex-deep-review-bounded-resumption-2026-09-23.md)
records the proof and its limits. A fresh session checks its actual required
capabilities. It does not rerun Skill Mesh qualification or the deferred Skill Mesh
root suite, and it does not hand-edit generated skills.

## Preserve the scope and evidence

Step 1 supplies the CLI, private SQLite store and lifecycle records. Step 2 supplies
five project-local skills using existing native agent/web tools. Step 3 supplies
the deterministic timer and the exact live acceptance procedure. Runtime storage
and detailed evidence stay outside public Git. No dashboard, daemon, model client,
shared skill installer or workflow redesign is part of these steps.

Use focused checks during a named repair and the project suite at completion.
Reuse a completed integrated-state receipt while source, tests, dependencies,
configuration and generated inputs are unchanged. Optional reviewer preferences
must not expand acceptance or start an unlimited cycle.

After Steps 2 and 3, hand off **Please run M1 next**. A fresh Codex session must
actually exercise the skills, independent assessment, public-source research and
watcher behavior. Code tests do not establish that live acceptance.

Issues: [Step 1](https://github.com/aberson/agent-advocate/issues/1),
[Step 2](https://github.com/aberson/agent-advocate/issues/2),
[Step 3](https://github.com/aberson/agent-advocate/issues/3),
[M1](https://github.com/aberson/agent-advocate/issues/4).