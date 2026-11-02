#!/usr/bin/env python3
"""Check a delivered handover: walk its steps and list every receipt.

    python3 check_delivery.py https://zambo.dev/handover/<id>
    python3 check_delivery.py <id>

Fetches the handover's public JSON twin, prints its status, its
recipient, and every step in order with the step's receipt link, then
confirms each receipt link answers. This is the dispute move, turned
into one command: when someone asks what was delivered, when, and
whether the record moved, this prints the pack.

A receipt proves the saved result was not changed since it was saved,
never that the work was right. Judgment stays with the reader; this
tool makes sure the reader is judging the real record.

No API key, no signup, standard library only.
"""

import http.client
import json
import sys
import time
import urllib.request

VERIFY = "https://zambo.dev/verify/"


def fetch_json(url):
    """Fetch JSON with retries: a truncated read is retried, never
    parsed half-way. Read-only, so retrying is always safe."""
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                url,
                headers={"Accept": "application/json", "Connection": "close"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode())
        except (http.client.IncompleteRead, ConnectionError, TimeoutError) as exc:
            last = exc
            time.sleep(1 + attempt)
    raise RuntimeError(f"could not fetch {url} after 3 attempts: {last}")


def answers(url):
    for attempt in range(2):
        try:
            req = urllib.request.Request(
                url, method="GET", headers={"Connection": "close"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp.read(512)
                return resp.status
        except Exception as exc:  # noqa: BLE001
            if attempt == 1:
                return f"FAILED ({exc})"
            time.sleep(1)
    return "FAILED"


def main():
    if len(sys.argv) != 2:
        print("usage: python3 check_delivery.py <handover url or id>")
        return 2
    target = sys.argv[1].rstrip("/")
    handover_id = target.rsplit("/", 1)[-1].removesuffix(".json")
    page_url = f"https://zambo.dev/handover/{handover_id}"
    data = fetch_json(f"{page_url}.json")

    print(f"Handover: {page_url}")
    print(f"Status:   {data.get('status')}")
    print(f"To:       {data.get('recipient')}")
    goal = data.get("goal")
    if goal:
        print(f"Goal:     {goal}")
    workflow_receipt = data.get("workflow_receipt_id") or data.get(
        "workflow_receipt"
    )
    if workflow_receipt:
        print(f"Wrap receipt: https://zambo.dev/run/{workflow_receipt}")

    steps = data.get("steps") or []
    print(f"\nSteps ({len(steps)}), in order:")
    bad = 0
    for i, step in enumerate(steps, 1):
        receipt = step.get("receipt_url") or ""
        status = answers(receipt) if receipt else "no receipt"
        if status != 200:
            bad += 1
        who = step.get("ai") or step.get("caller") or "?"
        print(
            f"  {i}. [{step.get('timestamp', '?')}] {who} / "
            f"{step.get('tool', '?')} -> {receipt} (HTTP {status})"
        )
    print(
        f"\nCheck any receipt yourself at {VERIFY}. "
        "A receipt proves the saved result was not changed."
    )
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
