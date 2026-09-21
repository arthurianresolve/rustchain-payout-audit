"""Offline reproduction against unmodified, pinned upstream gate/backfill sources.

No GitHub or payout request is made. Only the subprocess/API boundaries are
replaced with deterministic fixtures; both real main() functions execute.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
from unittest.mock import patch

from source_path import scripts_dir

SCRIPTS = scripts_dir()


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reproduce():
    gate = load("upstream_review_gate", "pr_review_gate.py")
    backfill = load("upstream_review_backfill", "pr_review_gate_backfill.py")
    assert backfill.MAX_PER_RUN == 60
    ready_number = 20061
    issues = {
        number: {
            "number": number,
            "title": "PR review claim",
            "body": "The PR reference still needs clarification.",
            "state": "open",
            "user": {"login": f"reviewer-{number}"},
            "labels": [{"name": "needs-human"}, {"name": "gate-processed"}],
        }
        for number in range(20001, ready_number + 1)
    }
    # This previously held claim is now complete and independently adjudicable.
    issues[ready_number]["body"] = "https://github.com/Scottcjn/Rustchain/pull/123"
    attempts = []
    writes = []

    def api(path, method="GET", data=None, strict=False):
        prefix = f"/repos/{gate.REPO}/issues/"
        if path.startswith(prefix):
            tail = path[len(prefix):].split("/")
            number = int(tail[0])
            if method == "GET" and len(tail) == 1:
                return issues[number]
            if method == "POST" and tail[1] == "labels":
                writes.append((number, data["labels"]))
                for label in data["labels"]:
                    if not any(item["name"] == label for item in issues[number]["labels"]):
                        issues[number]["labels"].append({"name": label})
                return issues[number]["labels"]
            if method == "POST" and tail[1] == "comments":
                writes.append((number, "comment"))
                return {"id": 1}
        if path == "/repos/Scottcjn/Rustchain/pulls/123/reviews":
            return [{
                "user": issues[ready_number]["user"],
                "submitted_at": "2026-09-20T10:00:00Z",
                "state": "COMMENTED",
                "body": "Finding in node/rewards.py L120: the settlement loop does not verify the row count before recording the transfer as complete. Check that the recipient row was updated before acknowledging success.",
            }]
        if path == "/repos/Scottcjn/Rustchain/pulls/123/comments?per_page=100":
            return []
        if path.startswith("/search/issues?"):
            return {"total_count": 0, "items": []}
        raise AssertionError(f"unexpected API boundary: {method} {path}")

    def run(args, **kwargs):
        if args[:3] == ["gh", "issue", "list"]:
            # Complete inventory: 61 results, well below the 1,000-item limit.
            return subprocess.CompletedProcess(args, 0, json.dumps(list(issues.values())), "")
        assert Path(args[1]).name == "pr_review_gate.py"
        env = kwargs["env"]
        number = int(env["ISSUE_NUMBER"])
        attempts.append(number)
        with patch.object(gate, "NUM", str(number)), patch.dict(os.environ, env, clear=True):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                gate.main()
        return subprocess.CompletedProcess(args, 0, output.getvalue(), "")

    with (
        patch.object(backfill, "_load_gate", return_value=gate),
        patch.object(backfill.subprocess, "run", side_effect=run),
        patch.object(gate, "api", side_effect=api),
        patch("urllib.request.urlopen", side_effect=AssertionError("network is forbidden")),
    ):
        for sweep in range(1, 4):
            before = len(attempts)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = backfill.main()
            selected = attempts[before:]
            assert code == 0
            assert selected == list(range(20001, 20061))
            assert ready_number not in selected
            assert "adjudicated 60/60" in output.getvalue()
            assert "1 claims still pending" in output.getvalue()
            assert all(labels == ["gate-processed"] for _, labels in writes)
            print(f"sweep={sweep} exit={code} selected=20001..20060 ready_claim_attempted=False terminal_verdicts=0")
        # The only writes reapply an existing label; they do not resolve claims.
        assert all(labels == ["gate-processed"] for _, labels in writes)
        # Control: the skipped claim qualifies with exactly the same API fixture.
        assert backfill.adjudicate(ready_number, retry=True)
        assert any(label["name"] == "bounty-eligible" for label in issues[ready_number]["labels"])
        print("control: direct adjudication of 20061 applies bounty-eligible")
        print("Observed: repeated successful sweeps never reach the adjudicable 61st retry.")


if __name__ == "__main__":
    with patch.dict(os.environ, {"MAX_PER_RUN": "60", "GH_REPO": "Scottcjn/rustchain-bounties", "TARGET_REPO": "Scottcjn/Rustchain", "CAP": "15"}):
        reproduce()
