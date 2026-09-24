---
name: assign-advocate
description: Start or resume Agent Advocate coordination for explicitly named coding work, from before-work assessment through checkpoints and closeout.
---

This is the reusable coordinator entry point. Use it when the user asks to set
up or run explicitly named work with Agent Advocate. Read the
[shared contract](../../../documentation/skill-contract.md) first.
Before any CLI request, resolve this physical `SKILL.md` upward to its
`<resolved-checkout>` and use `uv run --project <resolved-checkout> --locked agent-advocate ...`.
The monitored project's path comes from the named run, not from the current
working directory or the skill checkout.

1. Identify the named work, target project, acceptance, exclusions, and whether
   the user wants setup only or execution now. Reuse a matching existing run;
   otherwise create its request files and private store outside every Git
   worktree before invoking the CLI. Keep a private run pointer for resumption,
   and retrieve the bounded brief. If the user asks to resume but the pointer
   cannot be located, ask for it instead of creating a duplicate run. Ask for
   a missing work item or target rather than choosing one silently.
2. Inspect the named required review route against actual loaded adapters,
   referenced helpers, and host capabilities. Check fresh dispatch, observable
   role/model availability, required parent-only authority, helpers, and
   permitted capacity. Save a capability observation as `available`,
   `unavailable`, or `unknown`, with evidence, reason, owner, and next action.
3. If the native host can create a fresh, read-only independent assessor, obtain
   one using the primary named plan/evidence and save its returned identity and
   provenance. Otherwise save a coordinator assessment and explicitly state
   that independent assessment is unavailable; do not label it independent.
4. Save a checkpoint naming what is ready, what remains unverified, and the next
   check. If the user asked only for setup, leave the run waiting and give the
   short future invocation: `$assign-advocate for <named work>`. If execution
   was requested and required gates are ready, dispatch the named work through
   its existing build route and acceptance contract. The build route owns its
   reviews and source changes; this skill does not replace those gates.
5. During work, use `status-inquisition` at meaningful checkpoints. Run the
   foreground watcher when monitoring is requested and preserve its visible
   output; ask the user for firsthand terminal observations when acceptance
   requires them. Route a real alert or repeated route failure to
   `coordination-cowbell` for diagnosis. Use `model-mother` when exact named
   model research is needed. The timer never dispatches these skills itself.
6. At completion, stop, or abandonment, use `advocate-wrap` to record the actual
   outcome, unresolved owners, and later-useful cautions. Keep detailed receipts
   private and publish only a sanitized result.

Do not infer readiness from this file, a model label, or a source test. Do not
launch a full review as a readiness probe, retry failed dispatches merely to
manufacture a result, add a model client, or downgrade a required gate. Do not
mark a build or live acceptance DONE from discovery or green tests alone. M1
remains a separate live acceptance gate.
