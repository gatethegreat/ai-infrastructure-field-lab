# Managed AgentCore runner

This runner is for the separately approved AWS evidence boundary. Merely
running local tests does not contact AWS. The managed CLI refuses proof mode
unless the stack says `PolicyEngineMode=ENFORCE`, the policy parameter says
`ACTIVE`, and live control-plane reads report a `READY` Gateway plus `ACTIVE`
engine and policies.

## Dependencies

- Python `3.12.10` (exact pin)
- AWS CLI v2 (the exact installed build is captured in private run evidence)
- no pip packages; HTTP, SigV4, JSONL, CSV, and concurrency use Python's
  standard library

The client performs one HTTP attempt per trajectory request. Redirects, SDK
retries, and CLI retries are not used for Gateway calls.

## Approved proof command

```powershell
python experiments\06-strands-agentcore\run_agentcore_managed.py proof `
  --region <approved-region> `
  --repetitions 10 `
  --inter-step-delay-seconds 0.5 `
  --execute-managed-proof
```

For the budget-bounded corrected retry proof, select only S08:

```powershell
python experiments\06-strands-agentcore\run_agentcore_managed.py proof `
  --region <approved-region> `
  --scenario-id S08 `
  --repetitions 10 `
  --delay 1 `
  --execute-managed-proof
```

`--scenario-id` accepts S01-S11 and may be repeated. The runner still performs
the complete enforcement readiness gate, then executes one warmup plus the
requested repetitions only for the selected scenarios. Selected IDs and the
recomputed candidate-request budget are recorded in plan and summary output.

It reads the main stack outputs, assumes both synthetic caller roles into
memory, runs S01-S11 from `fixtures/scenarios-v1.json`, and queries available
`TemporalLatency` metrics and `aws/spans` after the default 60-second metric
settling interval. Raw headers, bodies, session IDs, role/control-plane data,
and observability results stay under ignored `evidence/cloud/private/`.
Committed-safe aggregate files are written under `evidence/cloud/redacted/`.
Each execution uses a unique batch subdirectory beneath both roots and refuses
to overwrite an existing batch. `--inter-step-delay-seconds` is bounded from 0
through 2 seconds, is recorded in the summary, and paces only sequential
S01-S11 calls. It is never applied to the concurrent S12 burst.

An allowed MCP request may still return a declared domain failure. Structured
`execute_write` output with `status: FAILED` is a retryable tool error and is
not counted as a completed call. Only `status: SUCCEEDED` is a successful write.
Policy denial, session validation, throttling, and transport errors remain
separate outcomes.

Per-request determining-policy spans were not configured for this lab. Managed
events, run rows, comparisons, and summaries therefore record
`added_authorization_latency_ms: null` and `policy_responsible: null`, each with
an explicit unavailable reason. `configured_policy_hint` is retained only as a
non-authoritative expectation and must not be reported as the policy that made
the decision. End-to-end request latency remains measured per call, and the
available CloudWatch minute-average `TemporalLatency` metric remains a separate
aggregate measurement.

## Separate S12 command

Deploy and verify the separate rate-limit stack first. Then run:

```powershell
python experiments\06-strands-agentcore\run_agentcore_managed.py rate-limit `
  --region <approved-region> `
  --execute-rate-limit
```

The runner requires a `READY` Gateway plus `CREATE_COMPLETE` state for the
separate rate-limit stack and exactly one
`AWS::BedrockAgentCore::GatewayRateLimit` resource. It
does not use the unavailable `list-gateway-rate-limits` CLI operation. After
the CloudFormation checks it waits 30 seconds for documented data-plane
propagation and sends the six S12 lookup requests concurrently. Use
`--rate-stack-name` when the approved stack does not use the default name.
This evidence is labeled throttling and is never counted as authorization.

Never commit the private evidence directory. Review aggregate outputs and the
existing redaction rules before adding managed evidence to version control.
