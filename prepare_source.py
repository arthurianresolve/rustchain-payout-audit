"""Fetch and verify the exact public upstream scripts used by the reproductions."""
from __future__ import annotations

from pathlib import Path
import urllib.request

from source_path import PINNED_COMMIT, UPSTREAM_BLOBS, git_blob_sha

BASE_URL = (
    "https://raw.githubusercontent.com/Scottcjn/rustchain-bounties/"
    f"{PINNED_COMMIT}/scripts"
)


def main() -> None:
    destination = Path(__file__).resolve().parent / "upstream" / "scripts"
    destination.mkdir(parents=True, exist_ok=True)
    for filename, expected_sha in UPSTREAM_BLOBS.items():
        request = urllib.request.Request(
            f"{BASE_URL}/{filename}",
            headers={"User-Agent": "rustchain-bounty-16471-reproducer"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read()
        actual_sha = git_blob_sha(data)
        if actual_sha != expected_sha:
            raise SystemExit(
                f"{filename}: expected Git blob {expected_sha}, got {actual_sha}"
            )
        (destination / filename).write_bytes(data)
        print(f"verified {filename} {actual_sha}")


if __name__ == "__main__":
    main()
