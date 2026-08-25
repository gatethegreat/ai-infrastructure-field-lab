# Comparison Scorecard

Allowed statuses: `PROVEN`, `PARTIAL`, `ABSENT`, `NOT TESTED`.

Every non-`NOT TESTED` status must link to experiment evidence. Capture measured
values such as minutes, services, changed files, and cost where applicable.

| Dimension | Baseline | OpenEnv | Model operations | Dapr Agents | Vercel | PydanticAI + DBOS | Strands + AgentCore | LangGraph | Microsoft Agent Framework | Restate |
|---|---|---|---|---|---|---|---|---|---|---|
| Setup effort | NOT TESTED | [PARTIAL](../experiments/01-openenv/evidence/openenv-environment.json) | NOT TESTED | [PARTIAL](../experiments/03-dapr-agents/evidence/dapr-environment.json) | [PARTIAL](../experiments/04-vercel/evidence/official-minimal.json) | NOT TESTED | [PARTIAL](../experiments/06-strands-agentcore/evidence/local/dogwood/environment.json) | NOT TESTED | NOT TESTED | NOT TESTED |
| Application coupling | NOT TESTED | [PARTIAL](../experiments/01-openenv/README.md#architecture-and-responsibility-boundaries) | NOT TESTED | [PARTIAL](../experiments/03-dapr-agents/README.md#architecture-and-separation) | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED |
| Model portability | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED |
| Local development | NOT TESTED | [PROVEN](../experiments/01-openenv/evidence/verification.txt) | NOT TESTED | [PROVEN](../experiments/03-dapr-agents/evidence/verification.txt) | [PARTIAL](../experiments/04-vercel/README.md#entry-gate-evidence) | NOT TESTED | [PARTIAL](../experiments/06-strands-agentcore/README.md#local-results) | NOT TESTED | NOT TESTED | NOT TESTED |
| Durability and recovery | [ABSENT](../experiments/00-baseline/README.md#initial-storage) | [ABSENT](../experiments/01-openenv/README.md#findings-limitations-and-decision) | NOT TESTED | [PROVEN](../experiments/03-dapr-agents/evidence/recovery-probe.json) | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED |
| Human approval | [PROVEN](../experiments/00-baseline/evidence/verification.txt) | [PROVEN](../experiments/01-openenv/evidence/verification.txt) | NOT TESTED | [PARTIAL](../experiments/03-dapr-agents/evidence/recovery-probe.json) | NOT TESTED | NOT TESTED | [PARTIAL](../experiments/06-strands-agentcore/README.md#limitations-and-untested-claims) | NOT TESTED | NOT TESTED | NOT TESTED |
| State and audit | [PARTIAL](../experiments/00-baseline/evidence/happy-path.jsonl) | [PARTIAL](../experiments/01-openenv/evidence/incident-trajectory.json) | NOT TESTED | [PARTIAL](../experiments/03-dapr-agents/evidence/recovery-probe.json) | [PARTIAL](../experiments/04-vercel/evidence/official-minimal.json) | NOT TESTED | [PARTIAL](../experiments/06-strands-agentcore/evidence/cloud/redacted/accepted-managed-comparison.csv) | NOT TESTED | NOT TESTED | NOT TESTED |
| Observability | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | [PARTIAL](../experiments/06-strands-agentcore/evidence/cloud/redacted/8d21c017f03f/managed_temporal-observability.json) | NOT TESTED | NOT TESTED | NOT TESTED |
| Evaluation | NOT TESTED | [PARTIAL](../experiments/01-openenv/evidence/incident-trajectory.json) | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED |
| Security boundaries | [PARTIAL](../experiments/00-baseline/evidence/verification.txt) | [PARTIAL](../experiments/01-openenv/evidence/verification.txt) | NOT TESTED | [PARTIAL](../experiments/03-dapr-agents/evidence/verification.txt) | NOT TESTED | NOT TESTED | [PARTIAL](../experiments/06-strands-agentcore/evidence/cloud/redacted/accepted-managed-comparison.csv) | NOT TESTED | NOT TESTED | NOT TESTED |
| Deployment and rollback | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | [PROVEN](../experiments/06-strands-agentcore/README.md#cloud-boundary) | NOT TESTED | NOT TESTED | NOT TESTED |
| Data ownership | [PROVEN](../experiments/00-baseline/README.md#architecture) | [PROVEN](../experiments/01-openenv/README.md#architecture-and-responsibility-boundaries) | NOT TESTED | [PROVEN](../experiments/03-dapr-agents/README.md#architecture-and-separation) | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED |
| Cost | [PARTIAL](../experiments/00-baseline/README.md#version-and-primary-sources) | [PARTIAL](../experiments/01-openenv/README.md#versions-and-primary-sources) | NOT TESTED | [PARTIAL](../experiments/03-dapr-agents/evidence/dapr-environment.json) | [PARTIAL](../experiments/04-vercel/evidence/official-minimal.json) | NOT TESTED | [PARTIAL](../experiments/06-strands-agentcore/infrastructure/cost-estimate.template.json) | NOT TESTED | NOT TESTED | NOT TESTED |
| Missing glue | [PARTIAL](../experiments/00-baseline/README.md#findings-and-limitations) | [PARTIAL](../experiments/01-openenv/README.md#findings-limitations-and-decision) | NOT TESTED | [PARTIAL](../experiments/03-dapr-agents/README.md#current-findings-and-limitations) | [PARTIAL](../experiments/04-vercel/README.md#entry-gate-evidence) | NOT TESTED | [PARTIAL](../experiments/06-strands-agentcore/README.md#limitations-and-untested-claims) | NOT TESTED | NOT TESTED | NOT TESTED |

## Measured comparison notes

Add one subsection per experiment with links to its evidence, exact measurements,
and the reasoning behind each status.

### Experiment 00 — Baseline

- Durability is absent by design: state and idempotency do not survive process
  termination.
- Human approval is proven for exact proposal binding and deterministic
  approve/deny/revise/expire behavior.
- State and audit are partial: a correlated timeline exists, but persistence and
  restart recovery are absent.
- Security is partial: untrusted notes do not control the deterministic action,
  but broader prompt-injection behavior is not tested.
- Shared data stays in plain Python records and JSON fixtures. Runtime cost is
  zero third-party services, but developer time and compute were not measured;
  setup uses one local Python process.
- Missing glue includes durable state, cross-process idempotency, timeout and
  retry policy, and telemetry export.

### Experiment 01 — OpenEnv

- The official Echo reset/step path and 6 adapted lifecycle tests passed on
  Windows with Python 3.12.10.
- The isolated environment resolved 111 packages and occupied 371,043,260
  bytes; installation time was not captured, so setup effort remains partial.
- Typed actions, observations, state, history, rewards, approval outcomes, and
  one-effect replay were demonstrated locally.
- State and trajectory evidence are reviewable but in-memory and not an
  authoritative durable audit record.
- The environment adapter still supplies transitions, reward design, approval,
  and effects. Docker, server transport, recovery, deployment, and aggregated
  evaluation were not tested.

### Experiment 03 — Dapr Agents

- The isolated environment resolved 116 packages and occupied 244,481,878
  bytes. Standalone Dapr also required Redis, Placement, Scheduler, and Zipkin
  containers; installation time was not captured.
- The deterministic workflow probe retried a transient failure, persisted an
  approval wait across app and sidecar restart, completed after approval, and
  returned `replayed=true` for a duplicate delivery.
- Approval remains partial because the proven external event belonged to the
  underlying Dapr Workflow probe. The Dapr Agents hook was not exercised with a
  real model.
- Shared contracts remained plain Python and JSON, while framework-specific
  wrappers stayed inside the experiment.
- Dapr Agents was rejected because its official `trigger_agent` durable path
  required a compatibility shim against both locked and stable workflow SDKs.

### Experiment 04 — Vercel entry gate

- The current official-style package line resolved 502 packages and occupied
  270,161,105 bytes in `node_modules`; installation took 50 seconds in the
  recorded run.
- AI SDK `7.0.73`, `@ai-sdk/workflow` `2.0.3`, Workflow `5.0.0-beta.43`, Nitro
  `3.0.260610-beta`, and Vite `8.2.2` compiled one workflow with 19 generated
  steps on Node `24.19.0`.
- The local workflow completed three recorded steps and remained inspectable
  from the file backend after the server stopped. This is partial local state
  evidence, not managed durability or recovery proof.
- The required Workflow 5 line is beta and `npm audit --omit=dev` reported 14
  high-severity findings. Test the stable-compatible package line before
  adapting the shared incident scenario.

### Experiment 06 policy subexperiment — Dogwood and AgentCore

- Local setup is partial: the pinned Dogwood source built reproducibly in
  Docker and all local tests pass. Managed Policy/Gateway testing completed in
  `us-east-1`, but the broader Strands runtime entry gate remains untested.
- Across 330 measured specification runs, prompt-only and stateless controls
  each produced 90 expected temporal false allows; the local temporal
  specification produced zero false allows, zero false denials, and no expected
  outcome mismatches.
- Dogwood validated without findings and nine semantic traces matched their
  expected verdicts across ten measured replays each.
- Accepted managed batches `2ee75ff6e4ec` and `8d21c017f03f` cover S01-S11
  across 110 runs with zero false decisions or expectation mismatches. This is
  managed enforcement evidence, separate from the local Dogwood proof.
- Human approval and security stay partial because arbitrary exact
  `expires_at` enforcement and concurrent approval consumption remain unproven,
  and the broader Strands runtime was not tested.
- Observability is partial: request IDs and CloudWatch policy-latency metrics
  were captured, but no span log group was configured; per-request added
  authorization latency and determining-policy identity are explicitly absent.
  The composite S12
  configuration allowed six concurrent calls at five requests per second. The
  single-dimension rerun was contaminated by a stale policy-session denial on
  request six. Neither transport result is authorization.
- Both CloudFormation stacks, the synthetic Lambda and owned log group,
  generated DynamoDB tables and IAM roles, and experiment policy engines are
  absent; the account Gateway count returned to the pre-test baseline of two.
