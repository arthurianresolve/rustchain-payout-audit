# Candidate report: successful backfill sweeps can permanently starve later retries

Status: reproduced locally; not submitted, accepted, or paid. Maintainer novelty
and payout eligibility are unconfirmed. Prepared for bounty #16471.

Claimant/payout identity: `@arthurianresolve` (hosted handle requested).
Codex assisted with source review, duplicate checks, and the reproduction.

## Summary

The PR-review backfill always chooses the oldest `MAX_PER_RUN` unresolved claims.
Claims that still need human input remain in that same oldest group. If that
group fills the budget, an otherwise resolvable later retry is never attempted,
however often the sweep runs. Each run returns zero and says the remaining claim
will process on the next run. There is no cursor, retry cooldown, or rotation to
make that promise true.

This is a scheduling failure in `scripts/pr_review_gate_backfill.py`, at upstream
commit `b1a9d98eb2ceedeeadc746568977262eb76464cf`:

- `list_unprocessed()` appends every `needs-human` issue to `stranded` and sorts
  the result by issue number.
- `main()` selects `stranded[:MAX_PER_RUN - len(batch_new)]` on every run.
- `pr_review_gate.main()` with `RETRY_NEEDS_HUMAN=1` returns normally when an
  already-held issue still has no PR reference. It reapplies `gate-processed`
  but leaves the issue unresolved.
- `adjudicate()` counts that normal exit as success; `main()` returns zero and
  prints “they process on the next run” for the unselected remainder.

Revalidated on September 21, 2026 against current `main` commit
`0d7accb199bb5e6f77f5a537ef4440d15ed7a098`. The backfill blob
`7df53b78ce33090709d9642c1cdc616260ff4109` is identical to the pinned source,
and the three-sweep reproduction passed again without modification.

The active workflow sets `MAX_PER_RUN=60`. With 60 older unresolved retries and
one later complete retry, the complete retry stays outside every batch.

## Reproduction

From the workspace root:

```text
python audit-16471/reproduce_backfill_starvation.py
```

The script executes both unmodified upstream `main()` functions from the pinned
source snapshot. Only GitHub/CLI boundaries are replaced. The issue inventory
contains all 61 issues, so no API page or 1,000-issue limit truncates the input.
The first 60 claims lack a PR reference and are already marked `needs-human`.
The final claim supplies a valid review and passes a direct control adjudication.
All input issues and reviews are synthetic. No production issue was created,
edited, labelled, or paid; the harness forbids outbound HTTP.

Observed on Python 3.14.6, Windows:

```text
sweep=1 exit=0 selected=20001..20060 ready_claim_attempted=False terminal_verdicts=0
sweep=2 exit=0 selected=20001..20060 ready_claim_attempted=False terminal_verdicts=0
sweep=3 exit=0 selected=20001..20060 ready_claim_attempted=False terminal_verdicts=0
control: direct adjudication of 20061 applies bounty-eligible
Observed: repeated successful sweeps never reach the adjudicable 61st retry.
```

Expected: a bounded retry sweep eventually attempts every unresolved claim, or
explicitly reports that later claims require intervention rather than promising
automatic processing on the next run.

Actual: each run selects the same 60 unresolved claims and leaves the complete
61st claim untouched, indefinitely while the older claims remain unresolved.

## Current deployment and limits

On September 21, 2026, GitHub reported workflow `329428656`
(`pr-review-gate-backfill.yml`) as **active**. Recent completed run
[35531017784](https://github.com/Scottcjn/rustchain-bounties/actions/runs/35531017784)
was successful. This establishes that the workflow is active; it does not show
that this failure occurred in that run.

The current public issue inventory had four open `needs-human` issues and **zero**
that matched the review-claim classifier without a `bounty-eligible` label.
Therefore this report does **not** claim that 61 real contributors are currently
stalled or that a real payout was lost. It proves the concrete failure under a
complete, valid backlog fixture using the configured batch size.

## Duplicate check

Reviewed all 141 comments on #16471 and the linked 19-item canonical audit index,
plus focused issue searches for backfill starvation/oldest retries. No public
report of this exact retry-batch selection path was identified. Private reports
and linked material outside that bounded review may still overlap.

Closest prior findings:

- Canonical item 10: the backfill's `--limit 1000` omits inventory. Here all 61
  records have already been read successfully; no inventory truncation occurs.
- Canonical item 16: the **docstring** scheduled sweep starves behind 60 held
  claims. This candidate is in the separate Python **PR-review backfill**, whose
  retry selection and recovery would need their own fix. The shared starvation
  pattern is a material duplication risk for maintainer adjudication.
- Paid initial issue-fetch failure: a failed read exits zero, but a later run can
  recover. Here no API request fails, and the later claim is never attempted.

## Suggested remedy

Persist a retry cursor or next-attempt timestamp so permanently unresolved claims
cannot occupy every batch forever. Keep newly filed claims prioritized without
starving retries indefinitely. Count attempted, unresolved, and terminal outcomes
separately. A regression should run consecutive sweeps over more than one batch
and prove that the complete later claim is eventually adjudicated while earlier
unresolved claims remain open.

## References

- [Bounty #16471](https://github.com/Scottcjn/rustchain-bounties/issues/16471)
- [Pinned backfill source](https://github.com/Scottcjn/rustchain-bounties/blob/b1a9d98eb2ceedeeadc746568977262eb76464cf/scripts/pr_review_gate_backfill.py)
- [Pinned review gate](https://github.com/Scottcjn/rustchain-bounties/blob/b1a9d98eb2ceedeeadc746568977262eb76464cf/scripts/pr_review_gate.py)
- [Pinned driving workflow](https://github.com/Scottcjn/rustchain-bounties/blob/b1a9d98eb2ceedeeadc746568977262eb76464cf/.github/workflows/pr-review-gate-backfill.yml)
- [Earlier canonical index](https://github.com/prins1bap-ui/rustchain-bounty-work/blob/main/16471-CANONICAL-INDEX.md)
