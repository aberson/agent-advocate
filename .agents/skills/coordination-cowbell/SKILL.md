---
name: coordination-cowbell
description: Investigate an escalation, repeated review-route failure, or later watchdog alert and record an evidence-backed next action without changing work automatically.
---

Use this skill when a user escalates a condition, a required review route keeps
failing, or a watchdog alert exists. Read the
[shared contract](../../../documentation/skill-contract.md) first.
Before any CLI request, resolve this physical `SKILL.md` upward to its
`<resolved-checkout>` and use `uv run --project <resolved-checkout> --locked agent-advocate ...`.

1. Name the condition and inspect its supplied receipts. Separate unsupported
   adapter, missing resource, capacity mismatch, service failure, and actual
   code defect; an overdue expectation is a prompt to investigate, not proof of
   defective work.
2. Save an evidence-backed observation with the condition, owner, and smallest
   actionable next move. Link a correction to the original observation instead
   of replacing it.
3. Preserve gate authority: do not stop or roll back a build, alter scope, or
   approve a workaround. If native independent-agent capability is absent,
   state the limitation rather than implying an independent diagnosis.

Step 2 has no alert-disposition CLI yet. Record the investigation only; do not
claim an alert was acknowledged, dismissed, or resolved until Step 3 exists.
