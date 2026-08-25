# Findings

Experiment 00 established the deterministic, tool-neutral baseline.
Experiment 01 showed where an environment interface fits around it.

## Confirmed strengths

- Plain typed contracts and JSON fixtures are sufficient for the shared
  happy path and approval boundary.
- A proposal fingerprint can bind approval to the exact simulated action.
- A correlated ordered timeline reconstructs the in-process happy path.
- A bounded live model can call the strict read-only context tool and return the
  permitted typed proposal without receiving execution authority.
- OpenEnv can express the lifecycle as typed actions, observations, episode
  state, history, completion, and deterministic rewards.
- The Dapr Workflow layer retried a transient activity failure, persisted an
  approval wait across application and sidecar termination, resumed the same
  workflow instance, and suppressed a duplicate simulated effect through a
  persisted idempotency record.
- In the AgentCore policy subexperiment, prompt-only advice and stateless
  per-tool authorization produced all expected temporal false allows, while the
  local temporal specification produced none across 110 measured runs.
- Dogwood at commit `c6237c88099b3f492ecc5fcee42df06a19224b97`
  validated the synthetic policy without findings and matched nine replay
  oracles for prerequisites, identifier correlation, fixed freshness,
  single-use approval, success/retry caps, and caller/session isolation.
- Managed AgentCore enforced S01-S07 and S09-S11 across 100 accepted paced runs
  in batch `2ee75ff6e4ec`, and the corrected approval-key retry rule enforced S08
  across 10 targeted runs in `8d21c017f03f`. The combined 110 managed runs had
  zero false allows, false denials, or expectation mismatches.
- The managed retry result depended on an explicit supported-field redesign:
  schema-valid `status: FAILED` responses and approval-ID response correlation.
  Earlier Lambda exception, temporal error/request-history, and nested input
  change-ID variants failed open and remain documented diagnostic evidence.
- The official-style Vercel Workflow minimal compiled one workflow with 19
  generated steps, completed three recorded local steps, and retained the
  completed run for CLI inspection after the server stopped. This proves the
  local compiler, execution, file backend, and inspection path only.

## Confirmed limitations

- In-memory idempotency does not survive restart and is not durable recovery.
- A local JSONL timeline is evidence, not an authoritative audit store.
- The deterministic untrusted-input boundary is not proof against live-model
  prompt injection.
- One successful live call is not provider reliability, timeout, fallback, or
  broad prompt-injection evidence.
- The OpenEnv adapter still owns business transitions, reward design, approval,
  idempotency, and effects; the library does not add durability to the tested
  in-memory environment.
- TensorZero is no longer maintained, so its former gateway, observability, and
  evaluation combination cannot be treated as a current production candidate.
- A model gateway is not currently required for the lab's one-agent,
  one-provider scope. Provider fallback remains a plausible future requirement,
  not a reason to operate another service before it is requested.
- Dapr Agents `1.0.5` is not acceptable as the production agent framework for
  this lab: its official durable trigger required a compatibility shim against
  both its locked and stable workflow SDKs.
- The free Dapr Echo component proved sidecar wiring but produced malformed
  synthetic tool-call data and did not prove a real agent tool loop.
- Strong underlying infrastructure does not compensate for a broken official
  framework path when the framework itself is the adoption target.
- Dogwood's public interpreter is semantic test tooling, not a production
  authorization engine: event time/authentication, durable bounded history,
  multi-tenant storage, and audit logging remain production responsibilities.
- The local policy proves a fixed approval window, not arbitrary dynamic
  `expires_at` enforcement, and successful-response consumption does not yet
  prove concurrent single-use atomicity.
- Managed S12 composite batch `dc0d1e456314` allowed six concurrent calls at
  five requests per second, proving non-enforcement for that configuration.
  Single-`toolName` batch `e9a8a5293522` completed five calls before a stale
  policy-session denial contaminated request six; it is inconclusive, not a
  second non-enforcement proof. Neither is an authorization decision.
- Managed observability is partial: request IDs and CloudWatch
  `TemporalLatency` metrics were captured, but no CloudWatch span log group was
  configured, so per-request added authorization latency and the actual
  determining policy are absent. The evidence records explicit unavailable
  values instead of treating request latency or configured hints as substitutes.
- Bounded teardown is proven: both CloudFormation stacks, the synthetic Lambda
  and owned log group, generated DynamoDB tables and IAM roles, and experiment
  policy engines are absent; the account Gateway count returned to the
  pre-test baseline of two.
- Vercel's current `@ai-sdk/workflow` `2.0.3` path requires the Workflow 5 beta
  line, and its required production dependency tree produced 14 high-severity
  audit findings. Scenario adaptation is paused until the stable-compatible
  line is tested; no managed durability claim or external deployment exists.

## Repeated integration pain

Durable approval waits and cross-process recovery were absent in the baseline
and OpenEnv but proven in the underlying Dapr Workflow probe. The remaining
question is whether a maintained agent framework supplies those behaviors
cleanly without requiring us to own compatibility patches. Vercel
`WorkflowAgent`, PydanticAI + DBOS, Strands plus AgentCore, LangGraph, and
Microsoft Agent Framework are the planned comparison shapes. Restate is a
conditional durability test; Temporal remains the heavier targeted fallback.

The policy subexperiment also exposed a separate repeated boundary: authenticating
a caller and permitting each tool does not constrain the sequence or cumulative
effect of individually valid calls. Keep temporal authorization, transport rate
limiting, application idempotency, and human approval as distinct controls.

## Candidate contributions

The Dapr Agents `trigger_agent` context-manager mismatch is a plausible upstream
bug report, but no contribution is planned because the candidate was rejected.

## Candidate reusable integrations

None yet.

## Candidate product hypotheses

None yet. A hypothesis enters this section only after the same meaningful gap is
observed in more than one relevant stack and reasonable existing solutions have
been checked.
