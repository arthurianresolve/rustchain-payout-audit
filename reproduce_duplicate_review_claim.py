"""Offline gate/payer reproduction using unmodified pinned upstream scripts.

Only HTTP, GitHub CLI, sleep, and environment boundaries are replaced. All
issues, reviews, credentials, wallets, and node responses are synthetic.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import urllib.parse
from unittest.mock import patch

from source_path import scripts_dir

SCRIPTS = scripts_dir()
REPO = "Scottcjn/rustchain-bounties"
PR_REPO = "Scottcjn/Rustchain"
PR_NUMBER = 123
CLAIMANT = "fixture-reviewer"
WALLET = "RTC" + "0" * 40
BODY = f"https://github.com/{PR_REPO}/pull/{PR_NUMBER}\nWallet: {WALLET}"
REVIEW = {
    "id": 123456,
    "user": {"login": CLAIMANT},
    "submitted_at": "2026-09-20T10:00:00Z",
    "state": "COMMENTED",
    "body": "Finding in node/rewards.py L120: the settlement loop records success "
            "before verifying that the recipient row changed. Check the affected "
            "row count and roll back when the intended account was not updated.",
}


class Fixture:
    def __init__(self):
        self.issues = {
            number: {
                "number": number,
                "title": "PR review claim",
                "body": BODY,
                "state": "open",
                "user": {"login": CLAIMANT},
                "author": {"login": CLAIMANT},
                "labels": [],
                "comments": [],
            }
            for number in (21001, 21002)
        }
        self.node_records = {}
        self.transfer_attempts = []
        self.cap_counts = []

    @staticmethod
    def response(value):
        return io.BytesIO(json.dumps(value).encode())

    def urlopen(self, request, **kwargs):
        url = urllib.parse.urlsplit(request.full_url)
        method = request.get_method()
        data = json.loads(request.data) if request.data else None
        if url.netloc == "fixture-node.invalid":
            assert url.scheme == "https" and url.path == "/wallet/transfer"
            assert method == "POST" and data["to_miner"] == WALLET
            self.transfer_attempts.append(data)
            key = data["idempotency_key"]
            # Working node idempotency: replaying a key returns its existing ID.
            if key not in self.node_records:
                self.node_records[key] = {
                    "ok": True,
                    "phase": "pending",
                    "pending_id": 90000 + len(self.node_records),
                    "confirms_in_hours": 24,
                }
            return self.response(self.node_records[key])
        assert url.netloc == "api.github.com", request.full_url
        prefix = f"/repos/{REPO}/issues/"
        if url.path.startswith(prefix):
            parts = url.path[len(prefix):].split("/")
            issue = self.issues[int(parts[0])]
            if method == "GET" and len(parts) == 1:
                return self.response(issue)
            if method == "POST" and parts[1] == "labels":
                for label in data["labels"]:
                    if not any(item["name"] == label for item in issue["labels"]):
                        issue["labels"].append({"name": label})
                return self.response(issue["labels"])
            if method == "POST" and parts[1] == "comments":
                issue["comments"].append({
                    "author": {"login": "github-actions[bot]"},
                    "body": data["body"],
                })
                return self.response({"id": len(issue["comments"])})
            if method == "PATCH" and len(parts) == 1:
                issue.update(data)
                return self.response(issue)
        if url.path == f"/repos/{PR_REPO}/pulls/{PR_NUMBER}/reviews":
            return self.response([REVIEW])
        if url.path == f"/repos/{PR_REPO}/pulls/{PR_NUMBER}/comments":
            return self.response([])
        if url.path == "/search/issues":
            assert f"author:{CLAIMANT}" in urllib.parse.unquote_plus(url.query)
            count = sum(
                any(label["name"] == "bounty-eligible" for label in issue["labels"])
                for issue in self.issues.values()
            )
            self.cap_counts.append(count)
            return self.response({"total_count": count, "items": []})
        raise AssertionError(f"Unexpected HTTP boundary: {method} {request.full_url}")

    def subprocess_run(self, args, **kwargs):
        assert args[:2] == ["gh", "issue"], args
        action = args[2]
        result = ""
        if action == "list":
            issues = [i for i in self.issues.values() if i["state"] == "open"]
            if "--label" in args:
                label = args[args.index("--label") + 1]
                issues = [i for i in issues if any(l["name"] == label for l in i["labels"])]
            result = json.dumps(issues)
        elif action in {"view", "comment", "close"}:
            issue = self.issues[int(args[3])]
            if action == "view":
                result = json.dumps(issue)
            elif action == "comment":
                issue["comments"].append({
                    "author": {"login": "github-actions[bot]"},
                    "body": args[args.index("--body") + 1],
                })
            else:
                issue["state"] = "closed"
        else:
            raise AssertionError(f"Unexpected CLI boundary: {args}")
        return subprocess.CompletedProcess(args, 0, result, "")


def run_script(filename, **extra_env):
    env = {
        "GITHUB_TOKEN": "synthetic-offline-token",
        "RTC_ADMIN_KEY": "synthetic-offline-key",
        "RTC_VPS_HOST": "fixture-node.invalid",
        "GH_REPO": REPO,
        "TARGET_REPO": PR_REPO,
        "CAP": "15",
        "RATE_RTC": "3",
        "MAX_PER_RUN": "40",
        **extra_env,
    }
    output = io.StringIO()
    # Keep Windows' certificate-store environment available while overriding
    # every application credential/endpoint with synthetic fixture values.
    with patch.dict(os.environ, env, clear=False), contextlib.redirect_stdout(output):
        values = runpy.run_path(str(SCRIPTS / filename), run_name="__main__")
    return values, output.getvalue()


def reproduce():
    fixture = Fixture()
    with (
        patch("urllib.request.urlopen", side_effect=fixture.urlopen),
        patch("subprocess.run", side_effect=fixture.subprocess_run),
        patch("time.sleep"),
    ):
        for number in fixture.issues:
            run_script("pr_review_gate.py", ISSUE_NUMBER=str(number))
            labels = {label["name"] for label in fixture.issues[number]["labels"]}
            assert "bounty-eligible" in labels
            print(f"claim={number} gate_exit=0 eligible=True review_id={REVIEW['id']}")
        assert fixture.cap_counts == [0, 1], fixture.cap_counts

        payer, output = run_script("bounty_payout.py")
        assert "paid 2 claims = 6 RTC this run" in output, output
        assert len(fixture.node_records) == 2
        assert list(fixture.node_records) == ["bounty73-claim-21001", "bounty73-claim-21002"]
        assert all(issue["state"] == "closed" for issue in fixture.issues.values())
        for transfer in fixture.transfer_attempts:
            print(f"simulated_transfer key={transfer['idempotency_key']} amount={transfer['amount_rtc']:g}")
        print("payer_exit=0 distinct_pending_records=2 total_simulated_RTC=6")

        # Control: a retry of the SAME claim does not create another node record.
        first = fixture.transfer_attempts[0]
        ok, response = payer["transfer"](
            first["to_miner"], first["memo"], first["idempotency_key"], first["amount_rtc"]
        )
        assert ok and response["pending_id"] == 90000
        assert len(fixture.node_records) == 2
        print("control: same-claim retry reuses pending_id=90000; record_count=2")
        print("Observed: two claim numbers for one review bypass business-level deduplication.")
        print("No real network request, issue mutation, or RTC transfer occurred.")


if __name__ == "__main__":
    reproduce()
