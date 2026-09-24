---
name: status-inquisition
description: Check an advocated run at a normal checkpoint by comparing claimed progress with named receipts and current acceptance.
---

Use this skill for a routine, neutral status request. Read the
[shared contract](../../../documentation/skill-contract.md) first.
Before any CLI request, resolve this physical `SKILL.md` upward to its
`<resolved-checkout>` and use `uv run --project <resolved-checkout> --locked agent-advocate ...`.
When reached through an installed wrapper, require its manifest and source
digest validation in the shared contract before proceeding.

1. Read the run, its latest checkpoint, and its bounded brief. Inspect only the
   specifically supplied receipts needed to compare the claim with acceptance.
2. State separately what is completed, what was checked, what is waiting, what
   is uncertain, and the next visible action. Record a checkpoint and a bounded
   observation when assessment is useful.
3. If a claim needs correction, record a new sourced observation linked through
   `supersedes`; never overwrite the original claim. Escalate to
   `coordination-cowbell` only when the evidence warrants investigation.

Missing native agent capability leaves an explicit limited coordinator
assessment. Do not treat quiet time, a missing receipt, or a completed check as
proof that the run is complete.
