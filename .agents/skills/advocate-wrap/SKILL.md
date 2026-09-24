---
name: advocate-wrap
description: Close completed, stopped, or abandoned advocacy work while reconciling observations, owners, pattern dispositions, and later evidence of benefit.
---

Use this skill when an advocated run is completed, stopped, or abandoned. Read
the [shared contract](../../../documentation/skill-contract.md) first.
Before any CLI request, resolve this physical `SKILL.md` upward to its
`<resolved-checkout>` and use `uv run --project <resolved-checkout> --locked agent-advocate ...`.
When reached through an installed wrapper, require its manifest and source
digest validation in the shared contract before proceeding.

1. Reconcile advice and observations into one of: new rule gap, existing rule
   missed, rule conflict or obsolete rule, environmental failure, task-specific
   correction, or unsupported hypothesis. Identify the owner and preserve each
   source reference.
2. For a correction, create a new sourced observation that `supersedes` the
   original. Mark a relevant pattern `fix-applied` only after the fix is applied
   and cite that correction. Do not call it improved behavior until a later
   independent or measured observation supports that outcome.
3. Finish the run with its actual outcome and summary. Retire a pattern only
   with owner judgment or evidence, and keep useful cautions available for
   future briefs.

Do not erase evidence, publish private data, or treat an outcome as proof that a
required review route or model behavior improved.
