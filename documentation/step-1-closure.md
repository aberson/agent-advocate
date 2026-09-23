# Step 1 acceptance: bounded closing exception

Step 1 is accepted for code commit `27e1ce1990932c777813070062dca05acbc98e50`.
The operator approved one narrow repair and independent closing review, then
confirmed this coordinator owned Step 1 while other project work remained separate.
The plan records this one-time exception as P10.

The existing sixth developer repair was preserved rather than rewritten. POSIX
evidence descriptors now open with `O_NONBLOCK` before regular-file classification,
so an unwritten FIFO returns `not-regular` without waiting for a writer. Reads and
hashing stop at exactly 8 MiB, and final descriptor metadata reports oversized or
changed input. The prior one-byte sentinel is no longer used. Both changes stay
within the existing evidence-ingestion functions; no dependency or schema changed.

## Evidence

| Check | Result | Disposition |
|---|---|---|
| `uv run --locked python -m pytest` on Windows | 30 passed, 1 skipped; 47.08 seconds | Reused the existing developer receipt for the preserved repair; the skipped test requires POSIX |
| `uv run --locked python -m pytest tests/test_privacy.py -q` on Windows | 14 passed, 1 skipped; 7.68 seconds | Existing developer receipt; not repeated |
| FIFO CLI regression on WSL Ubuntu, Python 3.12.3 | 1 passed; 0.39 seconds, 0.70-second process wall time | Newly executed against the frozen candidate |
| Independent closing review | PASS; no material correctness or privacy defect in the narrow delta | One fresh reviewer; no further six-lens campaign |
| `git diff --check` | PASS | Whitespace only; no configured lint/typecheck claim |

The Linux selection was
`python -m pytest tests/test_privacy.py::test_posix_fifo_evidence_is_rejected_without_blocking_the_cli -q`,
using the candidate's `src` on `PYTHONPATH`, Linux temporary fixtures and a bounded
process timeout. A temporary Linux virtual environment installed pytest only and
was removed afterward; the Windows environment was unchanged. This demonstrates
that regression on Linux, not the complete Linux suite. The temporary pytest
version was not recorded. Detailed command and execution receipts remain private.

The Linux run and closing review bound the same source bytes:

- `src/agent_advocate/service.py`: SHA-256 `812f36d3160a1d0a83af7aa40decd8adea7e49d77fcb9a72c2ad6a674c442e2b`.
- `tests/test_privacy.py`: SHA-256 `b9dc89bac229c3fe0aa3d2047feb4235af110a7618aae9871c704b49ba3b7e39`.

Only status and acceptance documentation changed afterward. Identical source,
tests, dependencies and configuration allow reuse at the enclosing integration
checkpoint under the project's existing rule.

## Authority and limits

Historical round 5 still says `NEEDS-WORK`, and its authenticated workflow record
still says `BLOCKED`. Neither was rewritten. This acceptance uses the expressly
approved closing exception; it is not a fresh `review-deep` PASS or authenticated
workflow ADVANCE. Earlier candidate and retry history remain preserved.

The closing attempt was bounded to 30 minutes, beginning 2026-09-23 23:48:38 UTC.
Only the previously skipped FIFO test needed new execution. There was no repeated
full suite, shared Skill Mesh test run or change to the installed review engine.

Steps 2 and 3 and live acceptance M1 remain TODO. The exception applies to Step 1
only; Step 3's declared deep review remains required.
