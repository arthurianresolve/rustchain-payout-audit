"""Locate the exact upstream scripts used by the offline reproductions."""
from __future__ import annotations

import hashlib
from pathlib import Path

PINNED_COMMIT = "b1a9d98eb2ceedeeadc746568977262eb76464cf"
UPSTREAM_BLOBS = {
    "pr_review_gate.py": "d94de135a8765656e04fc94d42122f82ec231336",
    "bounty_payout.py": "fbbfbf23ba5f31a8b9c98072d2bfde5dc351cf9d",
    "pr_review_gate_backfill.py": "7df53b78ce33090709d9642c1cdc616260ff4109",
}


def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data, usedforsecurity=False).hexdigest()


def scripts_dir() -> Path:
    root = Path(__file__).resolve().parent
    candidates = (
        root / "upstream" / "scripts",
        root.parent / "sources" / "rustchain-bounties" / "scripts",
    )
    for candidate in candidates:
        if all((candidate / filename).is_file() for filename in UPSTREAM_BLOBS):
            for filename, expected_sha in UPSTREAM_BLOBS.items():
                actual_sha = git_blob_sha((candidate / filename).read_bytes())
                if actual_sha != expected_sha:
                    raise SystemExit(
                        f"{candidate / filename}: expected Git blob {expected_sha}, "
                        f"got {actual_sha}. Run `python prepare_source.py` to "
                        "restore the pinned sources."
                    )
            return candidate
    raise SystemExit(
        "Pinned upstream scripts are missing. Run `python prepare_source.py` "
        "from the audit artifact directory first."
    )
