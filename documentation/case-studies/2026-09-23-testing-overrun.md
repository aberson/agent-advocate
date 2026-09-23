# Case-study seed: excessive testing during an excessive-testing intervention

- **Case:** AA-CS-001
- **Date:** 2026-09-23
- **Disposition:** observed coordination failure; proposed interventions remain unvalidated.

**Purpose:** a concrete learning example for Agent Advocate. This document adds no build step, automated gate, runtime pattern import, or permission to resume paused work.

The coordinator was helping address builds delayed by excessive engineering and testing. During that same work, it allowed a known expensive validation requirement to dominate delivery. The operator had to raise the concern again and then explicitly stop execution. The central failure was inadequate control of validation cost, even after duplicate validation had been curtailed.

## Intended outcome and observed result

The operator wanted a small Agent Advocate v0 and first requested a repair for a shared Codex review route that prevented builds from starting. The repair belonged in Skill Mesh. Its plan required focused checks during development, independent review, one final repository-root test suite, and a later installed-host proof before activation.

The repair reached a reviewed candidate. Independent review identified a real defect, a repair was made, and the final independent code review and focused checks passed. This established useful evidence, while leaving the full integration and installed-host requirements unresolved.

The final root test run was stopped at the operator's request after **101.7 minutes**. Its last flushed progress was **27%**; output was buffered, so this does not establish its actual stopping percentage or remaining runtime. No failing-test verdict was reported. The run was incomplete and cannot be called a pass. Historical root-suite runs already documented costs of multiple hours, including one approximately **3.5-hour** run.

The reviewed candidate was preserved separately, both projects' pause records were published, and owned test processes and the private review service were closed. Installed-host qualification and profile refresh did not run. The repair remained unaccepted and uninstalled; Agent Advocate's existing implementation remained preserved.

## Where coordination failed

The following is the coordinator's retrospective interpretation of the observed sequence, rather than a controlled causal experiment.

1. **A frequency limit became a substitute for a cost decision.** Running a full gate once prevents some repetition. It says nothing about whether that gate's cost fits the requested outcome. The coordinator did not translate known historical runtime into an explicit delivery tradeoff before committing to the route.
2. **The workflow requirement dominated prioritization.** The full suite was an approved completion requirement, so starting it was consistent with the plan. That requirement explains the command selected; it does not remove the coordinator's responsibility to surface the conflict with fast delivery. The coordinator could preserve an honestly incomplete candidate and propose a change to scope, sequencing, or the owning validation policy.
3. **Process health was used as reassurance about continued investment.** Changing worker processes showed activity. They did not establish that waiting remained the best next action. Repeated reports of activity and no reported failures did not answer what uncertainty remained or how much more delivery time to spend on it.
4. **Budget-setting happened after escalation.** When the operator asked whether testing would continue endlessly, the coordinator proposed a four-hour total cap and a further bounded installed-host check. A cap was an improvement over no cap, but it arrived late and still failed to respond adequately to the operator's concern about time already consumed.
5. **The user remained the effective watchdog.** The work stopped only after a direct wind-down instruction. The coordinator remembered the anti-overengineering objective in its commentary but failed to turn it into decisions that governed execution.

This case does not show that every check was unnecessary: review found a real defect. It does not show that the full suite could safely be replaced by the focused checks, or that any particular newer model caused the behavior. There is no controlled model comparison or measured counterfactual completion time.

## What an advocate should notice

| Moment | Evidence to consider | Useful intervention |
|---|---|---|
| Before selecting the repair route | Required gates, historical runtime, requested outcome, already available evidence | State the expected validation cost and its effect on delivery. Flag a mismatch before execution. |
| After focused checks and independent review | A stable reviewed candidate; remaining full-suite and host uncertainties | Name exactly what remains unproved and why the next check is worth its cost. Avoid repeating completed checks solely because another workflow layer asks. |
| At a normal checkpoint | Elapsed time, original budget, current activity, unchanged deliverable state | Reassess the continuation decision. A live worker is only one input. |
| When the operator questions testing duration | Explicit dissatisfaction with the current cost | Recommend a concrete bounded action using work already preserved. Do not respond only by granting the process a larger time allowance. |
| On a stop instruction | Operator has ended execution | Stop owned work, preserve evidence, report incomplete status accurately, and prevent automatic restart. |

A useful checkpoint asks: **What uncertainty would the next unit of validation resolve, and is that worth the remaining time under the operator's current priorities?** The answer should distinguish completed evidence, remaining uncertainty, likely cost, and the proposed action. It need not trigger another reviewer or another test.

## Implications for the five skills

| Skill | Lesson from this case |
|---|---|
| `assign-advocate` | Readiness includes the practical cost of required gates. Capture an expected validation window and a meaningful decision point alongside capability availability. |
| `status-inquisition` | Compare activity with movement toward the observable outcome. Fresh checkpoints alone do not establish good progress. |
| `coordination-cowbell` | Diagnose whether delay comes from justified validation, repeated work, a disproportionate standing rule, or an unavailable capability. Recommend action without granting a gate waiver. |
| `model-mother` | Keep this observation scoped to the demonstrated workflow. Model-specific attribution requires additional evidence; no web research is needed to document this case. |
| `advocate-wrap` | Record that duplicate-run control was insufficient and that budget-setting was late. Distinguish preserving work and stopping processes from fixing the underlying validation policy. |

The planned timer can miss this pattern: a coordinator can keep moving `next_check_at` forward while reporting the same active gate. If no overall deadline was set, checkpoint-overdue alerts alone may never fire. The existing overall deadline and diagnostic skills provide places to address this; this case does not justify a new daemon, database entity, or automatic process-killing mechanism. Deadlines should not be silently extended by routine heartbeats.

## Candidate caution and ownership

- **Candidate pattern:** `validation-cost-without-decision`
- **Scope:** coordination of builds with expensive required checks; model-independent pending contrary evidence.
- **Signal:** substantial validation time with no clear continuation decision, especially when the requested outcome was explicitly bounded or fast.
- **Recommendation:** use current evidence to propose continuing within a meaningful bound, parking the reviewed candidate, or changing the owning scope/policy through its normal authority. Preserve incomplete status until the applicable requirements are actually satisfied.

The coordinator owns prioritization and enforcement of the operator's stop. Skill Mesh owns its required validation policy and test-suite cost. Agent Advocate owns observation and advice; it must not become another approval gate or silently waive an existing one.

Avoid a universal minute limit. Set expectations from the task's risks, known gate costs, and operator priorities. Also avoid requiring an elaborate validation plan for every small edit: a short statement of remaining evidence, likely cost, and stop/decision condition is enough.

Treat the caution as provisional guidance for future real work. Evidence of improvement would be an earlier, useful decision about expensive validation without concealing uncertainty or weakening acceptance. No synthetic benchmark, repeated full suite, or fixed quota of build sessions is required to learn from this seed. The paused build stays paused until the operator requests continuation.

## Public evidence and limits

This is a sanitized narrative. Raw logs, local paths, process identities, session records, and verifier material remain private. No user transcript or private receipt is copied into the repository.

- [Approved repair plan at `3646dc5`](https://github.com/aberson/skill-mesh/blob/3646dc551afa409db93a0d7d6b46122ee14474fd/documentation/codex-deep-review-unblock-plan.md): focused checks and one final full-root gate, followed by separate installed-host qualification.
- [Repository instructions at `3646dc5`](https://github.com/aberson/skill-mesh/blob/3646dc551afa409db93a0d7d6b46122ee14474fd/CLAUDE.md): the root-suite completion requirement and known test cost.
- [Skill Mesh status at `80459e8`](https://github.com/aberson/skill-mesh/blob/80459e8f62f2d7ad1ecedb2b01487b017a4c92d7/plan.md): operator stop, preserved reviewed candidate, incomplete acceptance, and the separately dated 12,612.58-second historical root gate.
- [Reviewed source candidate `4a967f0`](https://github.com/aberson/skill-mesh/commit/4a967f0705fdbde98694d9eaf4808b66169345af): implementation preserved without an acceptance claim.
- [Stop checkpoint on issue #222](https://github.com/aberson/skill-mesh/issues/222#issuecomment-5801865782) and [Agent Advocate pause handoff at `cc13ce9`](https://github.com/aberson/agent-advocate/blob/cc13ce95736128798ab45392417b6cc3edf33859/documentation/build-handoff.md): closeout and no automatic restart.

The public records support the outcome and gate requirements. The causal interpretation and proposed advocate interventions are a retrospective, not proof of future productivity gains. One bounded independent critique checked the analysis for overclaiming; no code tests or build resumption were needed to write this document.

## Bounded-resume follow-up

The later bounded resume stayed within its testing limit and produced a candidate
with a green full suite, but the final required review still blocked it. One finding
was a real POSIX FIFO blocking-open defect. A second finding treated a one-byte,
non-hashed growth sentinel as violating an exact 8 MiB comment even though the plan
required bounded ingestion. This illustrates another decision point: preserve a
reviewer's raw verdict while separately recording a coordinator's severity or
contract disagreement. Passing tests do not override review, and a disputed review
finding should not silently create an unlimited repair loop.

The operator subsequently approved a one-time closing exception. The coordinator
reused an existing repair and its Windows test receipt, ran the missing Linux FIFO
regression in 0.39 seconds, and obtained one independent closing review of the
affected behavior. Step 1 was accepted with the original deep verdict preserved;
the [closure record](../step-1-closure.md) distinguishes these authorities. This
is one observed completion, not proof of long-term productivity improvement.
