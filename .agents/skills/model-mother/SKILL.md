---
name: model-mother
description: Research an explicitly named model or refresh an explicit stock model list with dated, scoped public evidence and uncertainty.
---

Use this skill only for an explicit model research request or explicit stock-list
refresh. Read the [shared contract](../../../documentation/skill-contract.md)
and the [stock model families](../../../data/model-families.json) first.
Before any CLI request, resolve this physical `SKILL.md` upward to its
`<resolved-checkout>` and use `uv run --project <resolved-checkout> --locked agent-advocate ...`.
When reached through an installed wrapper, require its manifest and source
digest validation in the shared contract before proceeding.

1. Prefer an exact requested model ID recorded in the run. The stock labels are
   user-editable families, not model/version claims.
2. Use the host's native web capability to read current official sources when it
   is actually available. Preserve the source URL, date, model/version scope,
   and uncertainty in a scoped pattern or observation. Community reports remain
   candidates.
3. If web capability is absent, record `unavailable` with the owning host
   repair, retain dated prior guidance, and say that no refresh occurred. Do not
   invent research, use a Python model client, or automatically change routing
   or settings.

Return a concise change report. Public seed cautions are not evidence about a
private run.
