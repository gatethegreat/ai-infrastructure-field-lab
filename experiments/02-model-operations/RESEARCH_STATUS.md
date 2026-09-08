# Research status: not yet ready for the final article

Updated 2026-09-08. Reader: business owners and team leads. This is evidence
inventory, not an article draft or a deployment recommendation.

## What the evidence supports

- **Real-provider API compatibility: PROVEN for five narrow cases.** Direct
  Bedrock and a local LiteLLM gateway completed text, streaming, meaningful
  continuation, forced tool invocation, and tool-result continuation against
  the same model and endpoint. See [Stage A](AWS_STAGE_A_RESULT.md).
- **Local restrictions: PROVEN for the tested configuration.** An unauthorized
  model returned 403. A one-request-per-minute key returned 200 then 429.
  Provider counters did not increase for the rejected requests.
- **Budget precision: PARTIAL.** Two synthetic $0.013 calls crossed a $0.02
  key budget to $0.026; the following call returned 429 without reaching the
  provider. The already-persisted block survived restart. Do not call this a
  never-exceed billing cap. These dollar values are deliberately artificial.
- **Per-key attribution: PARTIAL.** Successful rows reconcile to 10 input and
  3 output tokens and $0.013 synthetic cost each. Keys are labeled team-a and
  team-b but no team membership, SSO, or organizational hierarchy was tested.
  Some failed-call rows contain estimated prompt tokens despite zero spend;
  aggregate logged tokens are not automatically provider-billed usage.
- **Recovery: PARTIAL.** Stopping the provider returned 500; a new request
  succeeded after restart. This does not prove automatic task resumption,
  failover, managed availability, or absence of retries inside every layer.
- **Logging: limited observation.** The prompt canary was absent from the
  inspected spend-log rows and gateway console for this configuration. This
  is not a privacy certification, proof of every log sink, or a redaction test.

Primary local evidence:
[policy controls](evidence/policy-controls-20260908T151953Z.json).

## Findings that must not be hidden

### Restart accounting discrepancy

In the immediate-restart run, recent successful rows for the rate and burst
keys showed $0.013 each, while their key-level counters remained zero after a
75-second post-recovery wait. Team-b subsequently reconciled; team-a's already
persisted $0.026 remained. A burst-key request was allowed after restart.
That request alone is not proof of a bypass: the true prior $0.013 was still
below its $0.02 budget. The mismatched counters are the actual observation.

The [settle-before-restart control](evidence/policy-controls-20260908T152542Z.json)
waited 75 seconds before restart. All four key counters then matched their
request-log costs, and those values survived restart. This supports a
timing-dependent persistence gap in the tested configuration; it does not
establish the internal cause or behavior of a replicated managed deployment.

The concurrent burst allowed one request and rejected three. Requests had no
explicit output cap, so this is not a clean production concurrency or
overspend benchmark. Investigate reservation behavior and accounting flush
separately before explaining a cause or drawing a broad durability conclusion.

### Actual Codex client is not yet end-to-end proven

Tested Codex CLI 0.153.4 in a separate container with only a synthetic incident
file mounted. The task was to read it and explain failure rates to an owner.

- Initial streamed responses reported that web search was unsupported. The
  model client had advertised that feature even though the task did not need
  it. Disabling web search restored model responses.
- Three model calls then completed, but the nested shell sandbox prevented
  reading the fixture. Exit code zero did not mean the requested task passed;
  the harness correctly kept its status stopped.
- A revised externally isolated read-only container removed the nested-shell
  dependency. Its first model request instead reported on-demand capacity
  exceeded (429 inside the SSE body). No completed task is claimed.
- One later bounded retry reproduced the same capacity error, so live model
  attempts stopped. [Retry evidence](evidence/codex-task-20260908T152719Z.json).
  A credential-refresh preflight also exposed a missing explicit region;
  export commands now specify us-east-1. That preflight made no model call.

The relay buffers streams and caps requests at four and output at 256 tokens
per request. This is intentionally not a latency benchmark. It does not alter
the provider response. No host project, user config, AWS credential, or client
data is mounted in the Codex container. The only writable container paths are
temporary Codex state and /tmp; the lab fixture and root filesystem are read-only.

Evidence: [unsupported feature](evidence/codex-task-20260908T152123Z.json),
[sandbox failure despite completed responses](evidence/codex-task-20260908T152244Z.json),
[capacity failure](evidence/codex-task-20260908T152337Z.json).
Error interpretation was checked against private synthetic response bodies;
these bodies are excluded from Git because they include provider response IDs.

## Cost and remaining work

Across all Stage A and Codex runs: **19 attempted provider requests**, with
14 completed responses and five attempts lacking returned usage. Known-usage
conservative estimate is **$0.00493812**; the separate unknown-usage reserve
is **$0.25**. Neither is a reconciled AWS bill. Both together remain below the
approved $5 inference allowance, and 21 of the original 40 requests remain.
Do not count HTTP 200 SSE envelopes as successful model responses.

See [cost worksheet](COST_WORKSHEET.md). Its roughly $100/month subtotal covers
only two compute tasks, one base load balancer and one small database instance.
It is deliberately not represented as the full deployment cost.

Before calling research ready:

1. Finish the real Codex file-read task once provider capacity permits; compare
   the same task directly if a gateway task succeeds. Keep all failed attempts.
2. Investigate the demonstrated immediate-versus-settled restart discrepancy
   if making stronger budget-durability claims; the paired control is complete.
3. Finish the topology-specific cost estimate and managed-service comparison.
4. Obtain separate cloud-resource and HTTPS/DNS approval before any managed
   gateway test. Existing $5 permission covers inference only.
5. Audit the resulting claim-to-evidence inventory and privacy before drafting.

Potential business angle, still provisional: a gateway can enforce useful
rules, but someone must own compatibility, accounting accuracy and recovery.
The story should help readers decide when those responsibilities are worth it,
not imply that another service automatically makes AI cheaper or safer.
