# Client delivery proof run: the proof record

Executed live against https://zambo.dev/mcp on November 2, 2026
(20:49 UTC). Job id (_session_id): `delivery-proof-sample-2043-r3`.
Job reference: SAMPLE-2043. Pattern: one worker identity and one
client identity, each with its own server-issued caller handle, all
work inside one shared job id. The job is a labeled SAMPLE: landing
page copy for Harbor Lane Bakery, a fictional sample client, with
every fact in the records invented for the sample and marked SAMPLE
in the records themselves. Code: `deliver.py` in this package,
executed through a requests transport shim (Python urllib reads
truncate through the build bench's egress proxy; the logic, texts,
and sequence are the shipped file's own).

## Identities (agent names only; handle values live in the identity files)

| Agent | Role | Identity file |
|---|---|---|
| delivery-worker-r3 | Does the work, wraps the delivery | `identity-delivery-worker-r3.json` |
| delivery-client-r3 | Picks the delivery up, signs off | `identity-delivery-client-r3.json` |

## What ran, in order

1. Both identities initialized separately; each was issued its own
   caller handle and saved it before any other call. Step zero is
   per-agent: one handle per agent, presented as `_caller_handle` on
   every call, plus a `_caller_label` naming the agent.
2. The worker opened the job with a brief saved to memory under the
   shared job id.
   Receipt: https://zambo.dev/run/96186fb5-daa6-4175-98ca-9f4fab592ac6
3. The worker saved the job's steps inside the same job id:
   - Research note (audience, invented sample facts, tone):
     https://zambo.dev/run/f4c4621a-da05-4bf2-a5c0-16c5aeba07fd
   - Draft v1 of the landing page copy:
     https://zambo.dev/run/ed36d719-70e3-4519-a9b5-3456a013e786
   - Revision v2, the delivered version (headline tightened,
     Saturday line moved, call to action given the deadline):
     https://zambo.dev/run/de873f15-31ad-4c5f-a08f-b9827fc6d7c9
4. The worker wrapped the delivery as a handover addressed to the
   client identity. The wrap's proof loop bound the job's steps into
   the handover: its step list is the brief, the research note, the
   draft, the revision, and the proof loop's own shield check, in
   order.
   Delivery handover:
   https://zambo.dev/handover/31715914-80eb-438d-b01b-d2307cc4800e
   Wrap receipt: https://zambo.dev/run/7b0cd0bd-f3c6-4c85-882e-9149531c05f7
   Workflow receipt: https://zambo.dev/run/aa466129-e2b6-4858-a7e0-3e52e6cb708e
5. The client picked the handover up with `handover_accept` (free).
   The pickup record contained all three step receipts; the client
   read the steps from the record, not from a summary. The handover
   reads back status `accepted`.
6. The client saved its sign-off as a memory step in the same job,
   naming the handover. Pickup plus this step is the sign-off record.
   Sign-off receipt:
   https://zambo.dev/run/307e0707-0f54-48c0-a135-aa1745d1aac5

## Free-tier accounting, counted from the run's own counters

- Worker: 4 counted calls (brief, research, draft, revision) of its
  20 free daily calls, plus its 1 free daily wrap-up.
- Client: the pickup was free; the sign-off save was 1 counted call
  of its 20 free daily calls.
- Whole delivery: 5 counted calls across two separate allowances,
  zero paid calls. A delivery shaped like this runs free.

## What the build runs taught (both lessons are in the shipped code)

Two earlier iterations of this run failed in instructive ways, and
the package's code now guards against both:

- **A refused call still returns a receipt.** The first wrap attempt
  passed a hand-picked `receipt_ids` list and was refused with
  `receipt_access_denied` ("One or more requested receipts do not
  belong to this job. Nothing has been published."), receipted at
  https://zambo.dev/run/1d25e082-32c6-4677-b29d-9dfc08d57243 . A wrap
  holds only its own job's complete record; the shipped code lets
  the proof loop bind the steps and passes no receipt selection.
- **Facts cap at 500 characters.** The first research text ran long
  and `memory_remember` refused it before execution, receipted at
  https://zambo.dev/run/22ef6c40-5944-426f-b1db-1383c28e5e17
  ("fact exceeds the maximum length of 500"). A naive integration
  that treats any receipt link as a saved step ships a delivery with
  a hole in it. The shipped code checks the result's `ok` flag after
  every call and stops on a refusal, and every step text in the
  package is kept under the cap.

## Verification

Every link above was fetched on 2026-11-02 after the run: all
returned HTTP 200, including the delivery handover page and its JSON
twin, the four step receipts, both wrap receipts, and the sign-off
receipt. The package's own `check_delivery.py` was also run against
the delivery handover: it walked all 5 bound steps in order and
confirmed every step receipt answers.
