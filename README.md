# RustChain bounty #16471 reproductions

Deterministic reproductions for two candidate silent-success findings in
`Scottcjn/rustchain-bounties`. The primary candidate shows two claim issues for
one PR review becoming two pending payments. The secondary candidate shows a
bounded retry sweep repeatedly starving a later resolvable claim.

No real GitHub issue, label, comment, credential, wallet, node request, or RTC
transfer is used. The reproductions replace every external boundary with local
fixtures and execute the unmodified upstream gate and payout scripts.

## Run

Python 3.11 or newer is sufficient; no third-party package is required.

```text
python prepare_source.py
python reproduce_duplicate_review_claim.py
python reproduce_backfill_starvation.py
```

`prepare_source.py` downloads three scripts from pinned upstream commit
`b1a9d98eb2ceedeeadc746568977262eb76464cf` and verifies their Git blob hashes
before saving them under the ignored `upstream/` directory. The reproduction
steps themselves then run offline.

The primary report is [`duplicate-review-claim.md`](duplicate-review-claim.md).
The secondary report is [`backfill-starvation.md`](backfill-starvation.md).

## Scope

The primary candidate is prepared as one standalone 10 RTC defect submission.
The secondary candidate has a higher duplicate-reward risk because the canonical
index already contains a similar starvation finding in the docstring workflow;
it is retained as evidence but excluded from the primary claim.

