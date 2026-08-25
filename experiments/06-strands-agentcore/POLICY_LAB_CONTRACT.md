# AgentCore temporal-policy lab contract

Status: implementation contract, 2026-08-24

## Scope

This bounded subexperiment compares three enforcement models around one
deterministic synthetic tool trajectory:

1. `prompt_only`: authenticated and schema-valid calls receive advisory prompt
   instructions, but no authorization enforcement.
2. `stateless_auth`: each call is authorized from caller identity, tool
   permission, and current request fields only.
3. `temporal_policy`: the stateless checks plus sequence and cumulative-history
   rules, evaluated with the local Dogwood reference interpreter and, only
   after the separate cloud approval gate, Amazon Bedrock AgentCore Policy.

The runner never asks an LLM to select the next tool. This experiment therefore
does not measure prompt-following quality. It uses prompt-only as the deliberate
no-enforcement baseline.

Gateway rate limiting is a separate throttling test. It is not a fourth
authorization model and is not reported as an authorization decision.

## Synthetic identities and permissions

`caller-a` is the primary authenticated synthetic caller for all ordinary
scenarios. `caller-b` has the same permissions and is used only for the caller
isolation scenario. Both callers may invoke all four tools; this is intentional
so the stateless model exposes failures that only history-aware policy can see.

The tools are:

- `lookup_record(record_id)`
- `record_human_approval(record_id, approval_id, expires_at)`
- `execute_write(record_id, change)`
- `get_operation_status(operation_id)`

`change` contains a deterministic `change_id`, opaque `approval_id`, synthetic
value, and optional `force_error`. Recording an approval is a trusted synthetic
fixture event; it does not claim to reproduce a real human authentication flow.
`execute_write` always returns a schema-valid operation whose status is
`SUCCEEDED` or `FAILED`. `force_error=true` produces `FAILED` without changing
the synthetic record. Only `SUCCEEDED` is a completed success or consumes an
approval; `FAILED` is preserved as a retryable tool error.

## Temporal rules

A write is allowed only when all of these are true in the authenticated
caller's policy session:

- a successful lookup response exists for the same record within 10 minutes;
- a successful approval response exists for the same record and approval ID
  within the configured approval window;
- no successful write response has consumed that approval ID;
- fewer than three successful writes exist in the session; and
- fewer than three failed writes exist for the same approval ID retry key.

An approval is consumed by a successful write response, not by authorization or
by a failed target invocation. The initial failing attempt and two retries may
reach the tool; the fourth candidate call must be denied before tool execution.
The fourth otherwise-valid successful write in one session must also be denied.

The local specification, current Dogwood replay, and managed policy all
correlate failed write history on approval ID. The local Dogwood retry trace
deliberately uses distinct change IDs, proving that its approval-scoped key—not
accidental change-ID reuse—drives the fourth-candidate denial. The accepted
managed S08 trajectory instead held both approval ID and change ID constant
within each repetition. It proves the managed retry cap, but does not prove in
AWS that the cap is independent of changing change IDs. Live managed S08
previously showed Lambda exceptions arrive as completed MCP `result.isError`
responses, while temporal `execute_write::error` and request-history guards did
not deny candidate four. That exception-based probe is diagnostic only: its
transport error did not satisfy the declared successful tool-output schema.
The managed contract now represents an injected domain failure as a
schema-valid `execute_write` response with deterministic identifiers and
`status: FAILED`, persists only failed operation status, and applies no success
value. Nested historical `input.change.change_id` correlation then failed open
in 10/10 measured S08 runs. The managed redesign deliberately uses approval ID
as its retry key because it is a proven response field held constant across the
retry trajectory. It counts prior `execute_write::response` events whose
`output.approval_id` matches the candidate approval and whose output status is
`FAILED`, forbidding when that count reaches three. This supported-field
redesign was proven in corrected targeted batch `8d21c017f03f`: 10/10 S08 runs
matched the fourth-denied expectation with zero false decisions.

The local, Dogwood, and managed paths share that output contract. The local
runner classifies the returned `FAILED` operation as an error while retaining
its structured response in evidence. Dogwood consumes schema-valid failed
responses, and the managed runner applies the same classification when a
successful MCP envelope contains structured `status: FAILED`.

Local Dogwood evidence uses a fixed approval window. The public reference
documentation does not establish enforcement of an arbitrary `expires_at`
value from an earlier event with the requested tool signature. Managed
AgentCore testing must verify that behavior before the lab claims it.

## Expected outcomes

| ID | Trajectory | Prompt-only | Stateless | Temporal |
|---|---|---|---|---|
| S01 | Lookup A, approve A, write A | allow | allow | allow |
| S02 | Write A without lookup | false allow | false allow | deny |
| S03 | Lookup A, write A without approval | false allow | false allow | deny |
| S04 | Lookup A, approve A, write B | false allow | false allow | deny |
| S05 | Lookup A, expired approval A, write A | false allow | false allow | deny |
| S06 | Reuse one approval for two writes | second false allow | second false allow | second deny |
| S07 | Four independently valid writes in one session | fourth false allow | fourth false allow | fourth deny |
| S08 | Failing write plus three retry candidates | fourth reaches tool | fourth reaches tool | fourth deny |
| S09 | Fill S1, rotate to S2, direct write, then valid S2 chain | session ignored | session ignored | direct deny, fresh chain allow |
| S10 | Caller B reuses caller A's visible session ID | caller history ignored | caller history ignored | histories isolated |
| S11a | Missing or empty session ID | session ignored | session ignored | live behavior recorded |
| S11b | Malformed session ID | session ignored | session ignored | reject before tool |
| S12 | Burst allowed lookups past a gateway rate limit | not applicable | not applicable | throttle separately |

The first managed S12 stack used composite dimensions `toolName` plus
`$.context.iam.principal`. Although the stack reached `CREATE_COMPLETE`, all six
concurrent same-second requests succeeded against a five-per-second setting.
That 6/6 fail-open observation is consistent with dimension-resolution risk; it
is not authorization evidence. In the isolated `toolName: "*"` retry, five
requests succeeded and the sixth was denied by an unrelated stale policy
session. No rate-limit response was observed, but the policy denial contaminated
the boundary, so that second run is inconclusive rather than a second proof of
non-enforcement.

AWS documentation currently conflicts on whether an omitted temporal session
header is rejected or generated by the gateway. S11a is a contract-drift test,
not a result to normalize after execution.

## Evidence and repetition

Every request records its canonical trajectory hash, caller, session, request
and response, authorization decision and determining policy when available,
timestamps, end-to-end and authorization latency, tool outcome, error, retry
ordinal, effect ID, and trace/log identifiers.

Each ordinary scenario receives one excluded warm-up followed by ten measured
runs per applicable model and execution layer. Results report median, minimum,
and maximum latency. Local Dogwood and managed AgentCore results remain
separate datasets. Denied writes must show both zero tool invocation and zero
persisted effect.

## Authority boundary

Local implementation, Docker images, synthetic tests, and committed synthetic
evidence are authorized by the user request. Creating AgentCore, IAM, Lambda,
CloudWatch, or other AWS resources and incurring cloud usage remains the
repository's separate cloud approval gate. Cloud templates and validation may
be prepared before that gate; deployment may not run.
