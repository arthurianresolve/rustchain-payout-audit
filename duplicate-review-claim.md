# Candidate report: two claim issues can queue two payments for one PR review

Status: reproduced locally against the pinned public source; not submitted,
accepted, or paid. Maintainer novelty and payout eligibility are unconfirmed.
Prepared for bounty #16471.

Claimant/payout identity: hosted GitHub handle `@arthurianresolve` requested.
Codex assisted with source review, duplicate checks, and the reproduction.
Requested tier: **10 RTC for one confirmed new defect**. This does not request
the 35 RTC full-audit base. Maintainer adjudications on #16471 consistently use
the 10 RTC tier for standalone findings.

## Summary

The PR-review gate verifies that a claim's author is the first substantive
reviewer of the referenced PR, but it never verifies that the same review or
PR already has another eligible claim. The payout worker uses the claim issue
number, rather than the review or PR identity, in its idempotency key. Two claim
issues from the same reviewer for one review can therefore both pass the gate
and create distinct pending RTC transfer records. Every simulated API operation
succeeds and both scripts return success, despite scheduling the same work twice
under #73's “one bounty per PR” rule. Settlement is not exercised by this fixture.

At upstream commit `b1a9d98eb2ceedeeadc746568977262eb76464cf`:

- [`pr_review_gate.py`](https://github.com/Scottcjn/rustchain-bounties/blob/b1a9d98eb2ceedeeadc746568977262eb76464cf/scripts/pr_review_gate.py#L306)
  loads only the current claim issue and the referenced PR's review evidence.
- The gate selects the first substantive reviewer's **login** at lines 410–413.
  It does not retain or claim a unique review ID, and it does not search for an
  earlier claim for the same target PR/reviewer.
- Its cap query at line 429 counts the author's eligible claim issues. A second
  duplicate merely increments that count; while the count is below 15, the gate
  labels the duplicate `bounty-eligible` at line 450.
- [`bounty_payout.py`](https://github.com/Scottcjn/rustchain-bounties/blob/b1a9d98eb2ceedeeadc746568977262eb76464cf/scripts/bounty_payout.py#L377)
  sets `idempotency_key` to `bounty73-claim-<issue number>`. Different claim
  issues for the same review therefore have different node idempotency keys.
- The payer transfers and increments its successful-payment count at lines
  400–402. It has no PR/review-level duplicate check before transfer.

Revalidated on September 21, 2026 against current `main` commit
`0d7accb199bb5e6f77f5a537ef4440d15ed7a098`. The gate blob
`d94de135a8765656e04fc94d42122f82ec231336` and payout blob
`fbbfbf23ba5f31a8b9c98072d2bfde5dc351cf9d` are identical to the pinned
source, and the offline reproduction passed again without modification.

## Reproduction

From the root of this repository:

```text
python prepare_source.py
python reproduce_duplicate_review_claim.py
```

The harness executes the unmodified pinned gate and payout scripts. It replaces
only their GitHub API, GitHub CLI, node-transfer, sleep, and environment
boundaries with deterministic fixtures. Both synthetic claim issues reference
the same PR and the same review ID and are authored by the same reviewer. Node
idempotency is modeled as working correctly. No outbound request, production
issue mutation, credential use, or RTC transfer occurs.

Observed on Python 3.14.6, Windows:

```text
claim=21001 gate_exit=0 eligible=True review_id=123456
claim=21002 gate_exit=0 eligible=True review_id=123456
simulated_transfer key=bounty73-claim-21001 amount=3
simulated_transfer key=bounty73-claim-21002 amount=3
payer_exit=0 distinct_pending_records=2 total_simulated_RTC=6
control: same-claim retry reuses pending_id=90000; record_count=2
Observed: two claim numbers for one review bypass business-level deduplication.
No real network request, issue mutation, or RTC transfer occurred.
```

The control matters: retrying claim 21001 with its original idempotency key
returns the same pending record. The fixture models node retry protection as
functioning; it does not test the live node.
The extra transfer exists only because claim 21002 receives another issue-based
key for the same underlying review.

Expected: after one eligible claim represents a PR's first substantive review,
another claim for that same PR/review must be rejected or linked to the original
payment record without creating a second transfer.

Actual: both claim issues are labelled eligible and the payer creates a separate
pending transfer for each, while reporting two paid claims and exiting zero.

## Public-state check and limits

Bounty #73 explicitly says “One bounty per PR” and that later reviews of the
same PR are ineligible. Its machine-readable spec now says the bounty is
retired. On September 21, 2026, GitHub reported the event-driven PR-review gate
and its scheduled backfill as active; the latest backfill run at the pinned
commit completed successfully. The separate `bounty-payout.yml` workflow was
`disabled_manually`. The active gate can still make the duplicate eligibility
decision, while the demonstrated downstream transfer requires the payout worker
to be invoked or re-enabled. That deployment state limits current exposure but
does not change the source-level wrong decision in an explicitly in-scope path.

Public issues #10797, #10798, and #10799 show that duplicate claim issues for
one review can occur in practice. The claimant noticed and closed #10798 and
#10799 as duplicates, so those issues are **not** evidence that this defect paid
twice. This report does not claim current exploitation, a real duplicate RTC
transfer, or access to the live node.

## Duplicate check

I reviewed all 141 public comments on #16471, the linked 19-item canonical audit
index, and focused issue searches for duplicate review claims and “one bounty
per PR.” I did not identify a prior report of this exact end-to-end path. Private
reports and text outside that bounded review may still overlap.

The refresh at current `main` still found 141 comments; the newest remained
September 19, 2026. The canonical index blob was
`a9adaf107ebaedf0cff4fd2db1dd790b3dc95142`. No new matching public report was
found.

Closest earlier findings are materially different:

- The untrusted `RTC-AutoPay-Confirmed` finding lets a comment suppress an
  unpaid claim. This candidate creates two legitimate-looking eligible claims
  and two distinct pending transfer records.
- Reports about retrying a claim after its confirmation comment fails reuse the
  **same** issue-based key. The maintainer confirmed that the node returns the
  existing pending record. This candidate uses two issue numbers, so the keys
  differ; the control reproduces both outcomes.
- Canonical-index items 7 and 9 concern associating inline evidence with the
  wrong review/body. Here review evidence is complete and unambiguous; the same
  valid review is accepted twice.
- The duplicate canonical-wallet-row finding selects the wrong destination.
  This candidate concerns missing uniqueness for the payable work itself.

## Suggested remedy

Give every payable review a canonical identity, preferably target repository +
PR number + first substantive review ID/reviewer, and record that identity in a
durable claim ledger with a uniqueness constraint. The gate should fail closed
or link to the existing claim when that identity is already claimed. Derive the
node idempotency key from the canonical work identity rather than solely from
the claim issue number, and have the payer reject multiple eligible issues that
resolve to one identity. Add a regression that runs two different claim issues
for one review and proves only the first can become payable.

## References

- [Bounty #16471](https://github.com/Scottcjn/rustchain-bounties/issues/16471)
- [Bounty #73 terms](https://github.com/Scottcjn/rustchain-bounties/issues/73)
- [Pinned PR-review gate](https://github.com/Scottcjn/rustchain-bounties/blob/b1a9d98eb2ceedeeadc746568977262eb76464cf/scripts/pr_review_gate.py)
- [Pinned payout worker](https://github.com/Scottcjn/rustchain-bounties/blob/b1a9d98eb2ceedeeadc746568977262eb76464cf/scripts/bounty_payout.py)
- [Earlier canonical index](https://github.com/prins1bap-ui/rustchain-bounty-work/blob/main/16471-CANONICAL-INDEX.md)
- [Example claimant-closed duplicate #10798](https://github.com/Scottcjn/rustchain-bounties/issues/10798)
- [Example claimant-closed duplicate #10799](https://github.com/Scottcjn/rustchain-bounties/issues/10799)
