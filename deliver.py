#!/usr/bin/env python3
"""Client delivery proof, worker and client: do the work inside one
job, wrap it as a handover the client can open and check, and let the
client's pickup stand as the sign-off record.

Two phases, because the client acts between them:

    python3 deliver.py work     # worker: save the job's steps inside
                                # one shared job id, wrap the delivery
                                # handover addressed to the client
    # ... send the client the handover link ...
    python3 deliver.py accept   # client: pick the handover up (always
                                # free), read its steps, save a sign-off
                                # step naming the handover

The delivery pack is the handover itself: every step of the job, in
order, each opening to its own receipt. When a client later asks "did
you actually deliver that, and is this what you delivered?", the
answer is the link, not an argument. A receipt proves the saved result
was not changed, never that the answer was right.

Defaults are a fictional sample job, labeled SAMPLE in every record:
landing page copy for Harbor Lane Bakery, a fictional sample client,
job reference SAMPLE-2043. Set ZAMBO_CLIENT_NAME, ZAMBO_JOB_REF, and
the ZAMBO_STEP_* variables to run a real job.

Two endpoint rules this code is built around, both learned from real
refusals: memory_remember caps a fact at 500 characters, so every
step text below is kept short; and a refused call still returns a
receipt, so this code checks the result's ok flag after every call
instead of treating a receipt link as proof the step saved.

Cost: the worker spends 4 counted calls (the job brief plus the
research, draft, and revision steps) plus its free daily wrap-up. The
client's pickup is free and its sign-off save is 1 counted call. No
API key, no signup. Every call returns an AER-1 receipt link,
including a refused one, which is why the ok checks below exist.

The pattern, taught end to end with a real run and its receipts:
https://rambozambodotdev.gitlab.io/aer1-hub/delivery-proof-package.html
"""

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

MCP_URL = os.environ.get("ZAMBO_MCP_URL", "https://zambo.dev/mcp")
JOB_ID = os.environ.get("ZAMBO_SESSION_ID", "delivery-proof-sample-2043")
CLIENT_NAME = os.environ.get(
    "ZAMBO_CLIENT_NAME", "Harbor Lane Bakery (fictional sample client)"
)
JOB_REF = os.environ.get("ZAMBO_JOB_REF", "SAMPLE-2043")
WORKER_ID = os.environ.get("ZAMBO_WORKER_ID", "delivery-worker")
WORKER_NAME = os.environ.get("ZAMBO_WORKER_NAME", "Delivery Worker")
CLIENT_ID = os.environ.get("ZAMBO_CLIENT_ID", "delivery-client")
CLIENT_AGENT_NAME = os.environ.get("ZAMBO_CLIENT_AGENT_NAME", "Delivery Client")

# The job's opening brief and steps. Defaults are the fictional
# sample: every text is labeled SAMPLE inside the record itself, so
# the pack can never be mistaken for a real client's work. Keep every
# text under 500 characters: memory_remember refuses longer facts,
# receipted, before executing.
BRIEF_TEXT = os.environ.get(
    "ZAMBO_STEP_BRIEF",
    f"SAMPLE job {JOB_REF} opened. Client: {CLIENT_NAME}. One job, "
    "worked in the open: research note, draft v1, revision v2, then "
    "the delivery wrapped as a handover to the client. Every step "
    "receipted; the client checks the delivery from the handover link.",
)
STEP_TEXTS = [
    (
        "research",
        os.environ.get(
            "ZAMBO_STEP_RESEARCH",
            f"SAMPLE job {JOB_REF}, {CLIENT_NAME}. Research note for "
            "landing page copy. Audience: neighbors ordering ahead for "
            "morning pickup. Invented sample facts: sourdough out at "
            "6am daily, cardamom buns Saturdays only, preorders close "
            "8pm the night before. Tone: warm, plain, no hype. All "
            "facts in this job are invented for the sample.",
        ),
    ),
    (
        "draft",
        os.environ.get(
            "ZAMBO_STEP_DRAFT",
            f"SAMPLE job {JOB_REF}, {CLIENT_NAME}. Landing page copy, "
            "DRAFT v1. Headline: 'Bread worth waking up for.' Subhead: "
            "'Sourdough fresh every morning at 6, ready when you are.' "
            "Body: 'Order by 8pm, pick up on your way. Saturdays come "
            "early: cardamom morning buns, while they last.' Call to "
            "action: 'Order tonight, pick up tomorrow.'",
        ),
    ),
    (
        "revision",
        os.environ.get(
            "ZAMBO_STEP_REVISION",
            f"SAMPLE job {JOB_REF}, {CLIENT_NAME}. Landing page copy, "
            "REVISION v2, supersedes draft v1. Headline tightened to "
            "'Warm bread at 6am. Yours by 7.' Saturday bun line moved "
            "into the subhead. Call to action now carries the "
            "deadline: 'Order by 8pm, pick up tomorrow morning.' Body "
            "otherwise as draft v1. This revision is the delivery.",
        ),
    ),
]

HERE = Path(__file__).parent
NOTE_FILE = HERE / "delivery-note.json"

RUN_URL_RE = re.compile(r"https://zambo\.dev/run/[0-9a-f-]{36}")


class ZamboClient:
    """Minimal MCP client over streamable HTTP, standard library only."""

    def __init__(self, agent_id, agent_name):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.session_id = None
        self.state_file = HERE / f"identity-{agent_id}.json"
        self.caller_handle = self._load_saved_handle()
        self.quota_handle = None
        self._next_id = 0

    def _load_saved_handle(self):
        try:
            data = json.loads(self.state_file.read_text())
            return data.get("caller_handle")
        except Exception:
            return None

    def _save_handle(self):
        if self.caller_handle:
            self.state_file.write_text(
                json.dumps(
                    {
                        "agent_id": self.agent_id,
                        "agent_name": self.agent_name,
                        "caller_handle": self.caller_handle,
                    },
                    indent=2,
                )
            )

    def _post(self, payload, expect_response=True):
        body = json.dumps(payload).encode()
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "X-Agent-Id": self.agent_id,
            "X-Agent-Name": self.agent_name,
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        req = urllib.request.Request(MCP_URL, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            if self.session_id is None:
                self.session_id = resp.headers.get("Mcp-Session-Id")
            header_handle = resp.headers.get("X-Zambo-Caller-Handle")
            raw = resp.read().decode()
        if header_handle and not self.caller_handle:
            self.caller_handle = header_handle
        if not expect_response:
            return None
        return self._parse_rpc(raw)

    @staticmethod
    def _parse_rpc(raw):
        message = None
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                try:
                    message = json.loads(line[5:])
                except Exception:
                    pass
        if message is None:
            message = json.loads(raw)
        if "error" in message:
            raise RuntimeError(f"MCP error: {message['error']}")
        return message.get("result", {})

    def initialize(self):
        result = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": self.agent_name, "version": "0.1.0"},
                },
            }
        )
        meta = result.get("_meta", {})
        if not self.caller_handle:
            self.caller_handle = meta.get("caller_handle")
        self.quota_handle = meta.get("quota_handle")
        self._save_handle()
        self._post(
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            expect_response=False,
        )
        return result

    def call_tool(self, name, arguments):
        args = dict(arguments)
        if self.caller_handle:
            args["_caller_handle"] = self.caller_handle
        args.setdefault("_caller_label", self.agent_id)
        params = {"name": name, "arguments": args}
        if self.quota_handle:
            params["_meta"] = {"quota_handle": self.quota_handle}
        result = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._id(),
                "method": "tools/call",
                "params": params,
            }
        )
        handle = (result.get("structuredContent") or {}).get("caller_handle")
        if handle and not self.caller_handle:
            self.caller_handle = handle
            self._save_handle()
        return result

    def _id(self):
        self._next_id += 1
        return self._next_id


def receipt_link(result):
    structured = result.get("structuredContent") or {}
    for key in ("receipt_url", "run_url", "url"):
        value = structured.get(key)
        if isinstance(value, str) and "/run/" in value:
            return value
    match = RUN_URL_RE.search(json.dumps(result))
    return match.group(0) if match else None


def require_ok(result, what):
    """A refused call still returns a receipt. Never read a receipt
    link as success: check the ok flag, and stop on a refusal."""
    structured = result.get("structuredContent") or {}
    if structured.get("ok") is False or structured.get("rejection"):
        message = structured.get("message") or structured.get("human_line")
        raise RuntimeError(f"{what} was refused by the endpoint: {message}")
    return result


def do_work():
    client = ZamboClient(WORKER_ID, WORKER_NAME)
    client.initialize()
    print(f"worker session open; caller handle bound for '{WORKER_ID}'")

    # Open the job with its brief, then save every step of the work
    # inside the ONE shared job id, each under the worker's own
    # handle, each receipted. The receipts are collected as the
    # delivery's evidence, not reconstructed later.
    result = client.call_tool(
        "memory_remember",
        {"fact": BRIEF_TEXT, "agent_name": WORKER_NAME, "_session_id": JOB_ID},
    )
    require_ok(result, "The job brief save")
    print(f"[brief] job {JOB_ID} opened: {receipt_link(result)}")
    step_receipts = []
    for label, text in STEP_TEXTS:
        result = client.call_tool(
            "memory_remember",
            {"fact": text, "agent_name": WORKER_NAME, "_session_id": JOB_ID},
        )
        require_ok(result, f"The {label} step save")
        link = receipt_link(result)
        step_receipts.append((label, link))
        print(f"[step] {label}: {link}")

    # Wrap the delivery: one handover addressed to the client. The
    # summary names the job and each step with its receipt, and the
    # wrap's proof loop binds the job's own steps into the handover.
    # Do not pass receipt_ids of your own picking here: a wrap holds
    # only its own job's complete record, and a partial or foreign
    # selection is refused, receipted, with nothing published.
    summary = (
        f"Delivery for {CLIENT_NAME}, job {JOB_REF}: landing page "
        "copy, research note, draft v1, and revision v2 (the "
        "delivered version), all worked inside one job on Zambo. "
        + " ".join(
            f"Step {label}: receipt {link}."
            for label, link in step_receipts
            if link
        )
        + " Open the handover to read each step in order and check "
        "any receipt at https://zambo.dev/verify/."
    )
    result = client.call_tool(
        "handover",
        {
            "summary": summary,
            "goal": f"Deliver job {JOB_REF} as one checkable record: "
            "the client opens one link and verifies every step.",
            "recipient": CLIENT_NAME,
            "recipient_type": "human",
            "next_steps": [
                "Open the handover link and read the steps in order: "
                "research, draft, revision.",
                "Check any step's receipt at https://zambo.dev/verify/ "
                "before relying on it.",
                "Sign off by picking the handover up: the pickup is "
                "the acceptance record.",
            ],
            "_session_id": JOB_ID,
        },
    )
    require_ok(result, "The delivery wrap")
    structured = result.get("structuredContent") or {}
    handover_id = structured.get("handover_id") or (
        structured.get("ids") or {}
    ).get("handover_id")
    wrap_receipt = receipt_link(result)
    print(f"[deliver] handover: https://zambo.dev/handover/{handover_id}")
    print(f"[deliver] wrap receipt: {wrap_receipt}")
    NOTE_FILE.write_text(
        json.dumps(
            {
                "job_id": JOB_ID,
                "job_ref": JOB_REF,
                "client": CLIENT_NAME,
                "handover_id": handover_id,
                "handover_url": f"https://zambo.dev/handover/{handover_id}",
                "wrap_receipt": wrap_receipt,
                "steps": [
                    {"label": label, "receipt": link}
                    for label, link in step_receipts
                ],
            },
            indent=2,
        )
    )
    print(f"[deliver] note saved to {NOTE_FILE.name}; send the client the link.")
    return 0


def do_accept():
    if not NOTE_FILE.exists():
        print("no delivery note found: run `python3 deliver.py work` first")
        return 1
    note = json.loads(NOTE_FILE.read_text())
    client = ZamboClient(CLIENT_ID, CLIENT_AGENT_NAME)
    client.initialize()
    print(f"client session open; caller handle bound for '{CLIENT_ID}'")

    # Pick the delivery up. Pickup is always free, and the accept
    # returns the worker's saved steps and receipts: the client reads
    # the record itself, not the worker's summary of it.
    result = client.call_tool(
        "handover_accept",
        {
            "handover_id": note["handover_id"],
            "agent_name": CLIENT_AGENT_NAME,
            "_session_id": JOB_ID,
        },
    )
    blob = json.dumps(result)
    seen = {
        label: (receipt.rsplit("/", 1)[-1] in blob)
        for label, receipt in (
            (s["label"], s["receipt"]) for s in note["steps"]
        )
    }
    for label, ok in seen.items():
        print(f"[pickup] step {label} receipt in the record: {ok}")

    # The sign-off: a memory step under the client's own handle, in
    # the same job, naming the handover. Pickup plus this step is the
    # acceptance record the delivery pack points to in a dispute.
    signoff = (
        f"Sign-off, job {JOB_REF} ({CLIENT_NAME}): the client picked "
        f"up delivery handover {note['handover_id']}, read its steps "
        "(research note, draft v1, revision v2) from the record, and "
        "accepts the delivery. Pickup and this step together are the "
        "sign-off record."
    )
    result = client.call_tool(
        "memory_remember",
        {"fact": signoff, "agent_name": CLIENT_AGENT_NAME, "_session_id": JOB_ID},
    )
    require_ok(result, "The sign-off save")
    print(f"[sign-off] receipt: {receipt_link(result)}")
    print("client done: pickup read, sign-off saved.")
    return 0


def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else ""
    if phase == "work":
        return do_work()
    if phase == "accept":
        return do_accept()
    print("usage: python3 deliver.py work|accept")
    return 2


if __name__ == "__main__":
    sys.exit(main())
