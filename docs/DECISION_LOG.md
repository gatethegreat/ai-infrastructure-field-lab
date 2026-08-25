# Decision Log

Record decisions derived from research evidence. Do not record preferences as
facts or adoption decisions before the applicable experiment completes.

## 2026-08-21 — Use one shared scenario

- **Decision:** Compare tools with one synthetic incident assistant.
- **Reason:** This makes code changes, setup effort, recovery, and responsibility
  boundaries comparable.
- **Consequence:** Shared contracts remain tool-neutral under `shared/`.

## 2026-08-21 — Do not require PostgreSQL universally

- **Decision:** Start each experiment with native storage.
- **Reason:** Workflow state, application data, audit history, and telemetry have
  different purposes. Adding a database everywhere would distort complexity.
- **Consequence:** PostgreSQL appears only when the selected tool or a documented
  application requirement needs it.

## 2026-08-21 — Compare three production shapes

- **Decision:** Compare Vercel, Dapr Agents, and PydanticAI + DBOS + TensorZero.
- **Reason:** They represent managed integrated, open-source integrated, and
  open-source modular approaches.
- **Consequence:** OpenEnv remains a separate environment/evaluation track.

## 2026-08-21 — Defer product selection

- **Decision:** Do not choose or build a product before the experiments.
- **Reason:** Existing tools cover substantial territory and gaps must be proven
  through firsthand use.
- **Consequence:** Contributions, integration kits, recommendations, and a
  no-build result are valid outcomes.

## 2026-08-21 — Freeze baseline contract version 1.0

- **Decision:** Use plain typed Python records plus versioned JSON fixtures
  as the initial shared business boundary.
- **Reason:** Experiment 00 proves the happy path, approval binding, idempotent
  simulated effect, and correlated reconstruction without framework objects.
- **Consequence:** Later experiments adapt to these contracts. Any shared change
  requires evidence that all affected experiments need it.

## 2026-08-21 — Keep deterministic and live agent paths

- **Decision:** Preserve the deterministic baseline as the repeatable control
  and add one separately invoked, paid live-model smoke path.
- **Reason:** Deterministic tests prove business transitions, while a real model
  is necessary to expose tool-schema, tool-argument, structured-output, usage,
  and provider behavior.
- **Consequence:** Live variability cannot make the core suite flaky or become
  the sole evidence for a business invariant.

## 2026-08-21 — Keep execution authority outside the model

- **Decision:** Give the live model one read-only context tool and validate its
  proposal against trusted runbook output. Do not expose the simulated executor.
- **Reason:** Tool calling must be tested without allowing untrusted incident
  text or model output to expand consequential authority.
- **Consequence:** Provider adapters can inspect and propose only. Approval and
  idempotent execution remain deterministic application responsibilities.

## 2026-08-21 — Retain OpenEnv as a specialized evaluation environment

- **Decision:** Use OpenEnv when a repeatable reset/step trajectory or a
  training-compatible environment boundary is specifically required; do not
  treat it as the production agent runtime or durability layer.
- **Reason:** Version `0.4.1` modeled typed actions, observations, state,
  history, completion, and rewards successfully, but the adapter still owned
  all business transitions, approval, reward design, and effects, while state
  remained in memory.
- **Consequence:** Proceed to the model-operations necessity experiment without
  post-training. Revisit OpenEnv only for a bounded evaluation or training
  question.

## 2026-08-21 — Retire TensorZero and test gateway necessity

- **Decision:** Remove [TensorZero](https://www.tensorzero.com/) from the active
  comparison because its official project is no longer maintained. Compare
  direct provider calls with maintained LiteLLM before adopting any model
  gateway.
- **Reason:** A gateway adds another service and failure boundary, and the
  current lab has one agent and one provider. It is justified only by evidence
  for provider portability, fallback, centralized credentials or budgets,
  shared policy, or model-call observability.
- **Consequence:** Experiment 02 becomes a no-gateway-versus-LiteLLM test.
  Portkey is the managed gateway alternative; Langfuse or Phoenix remains a
  separate targeted observability decision. TensorZero remains historical only.

## 2026-08-21 — Defer model gateway and provider fallback

- **Decision:** Keep the direct provider adapter and close Experiment 02 at its
  necessity gate without installing LiteLLM, Portkey, or another gateway.
- **Reason:** Provider fallback will often matter in production, but the current
  lab has one agent and one provider, and the user has not been asked to supply
  redundancy. Operating a gateway now would test infrastructure without a
  current requirement.
- **Consequence:** Reopen the model-operations experiment only on explicit
  request for fallback, multi-provider routing, centralized credentials or
  budgets, shared policy, or cross-application model-call records. Dapr Agents
  becomes the next active experiment without a separate gateway.

## 2026-08-21 — Reject Dapr Agents 1.0.5 for production selection

- **Decision:** Close Experiment 03 without running the paid model smoke and do
  not select Dapr Agents `1.0.5` as the production agent framework.
- **Reason:** The official durable trigger calls `DaprWorkflowClient` as a
  context manager, while neither the Dapr Agents lockfile's `1.18.0rc0` client
  nor stable `1.18.3` implements that protocol. A temporary compatibility shim
  allowed the workflow to complete, but owning that workaround violates the
  requirement for a clean supported production path. The Echo component also
  failed to provide valid model-driven tool-call evidence.
- **Consequence:** Preserve the positive Dapr Workflow recovery evidence and
  the negative framework evidence. Do not test Dapr core separately unless a
  future distributed-application requirement specifically calls for it.

## 2026-08-21 — Replace the integrated candidate with Microsoft Agent Framework

- **Decision:** Keep Vercel as the next managed integrated experiment and add
  Microsoft Agent Framework as the replacement open-source integrated
  comparison after PydanticAI + DBOS.
- **Reason:** Current official Microsoft sources describe a GA Python and .NET
  agent framework with graph workflows, tool approvals, human-in-the-loop, and
  checkpoint/resume support. Its local file checkpoint path can be tested
  without cloud resources, while distributed production storage remains an
  explicit separate boundary. LangGraph and Restate remain targeted fallbacks,
  not additional automatic experiments.
- **Consequence:** Experiment 08 must run the official agent and checkpoint plus
  approval examples unchanged and stop if either needs a source patch or
  compatibility shim. This is a research selection, not an adoption decision.

## 2026-08-21 — Expand the candidate set across deployment shapes

- **Decision:** Keep Vercel and PydanticAI + DBOS, and add Strands Agents plus
  Amazon Bedrock AgentCore, LangGraph, and Microsoft Agent Framework as planned
  comparisons. Keep Restate conditional and Temporal targeted.
- **Reason:** A Microsoft-oriented replacement alone does not answer the user's
  likely AWS and cloud-neutral deployment questions. The expanded list compares
  managed integrated, AWS-native managed, portable modular, graph-oriented, and
  open-source integrated approaches using the same scenario.
- **Consequence:** LangGraph, rather than the broader LangChain library, owns the
  stateful runtime experiment. Restate runs only if a preferred agent SDK still
  lacks needed durability. Temporal is active and maintained; it remains the
  heavier fallback for demonstrated complex coordination. TensorZero—not
  Temporal—is the archived candidate removed from the active plan.

## 2026-08-24 — Isolate the temporal-policy article experiment

- **Decision:** Run the explicitly requested Dogwood and AgentCore Policy study
  as a bounded subexperiment inside Experiment 06 while leaving shared contract
  version 1.0 and the broader Strands entry gate unchanged.
- **Reason:** The article asks a specific sequence-aware authorization question
  that can reuse the lab's synthetic evidence discipline but needs different
  policy-session, caller, approval-consumption, and retry contracts.
- **Consequence:** Local Python specification results and Dogwood replay results
  are separate evidence layers. Neither is managed AgentCore enforcement proof,
  and the main Experiment 06 runtime comparison remains planned.

## 2026-08-24 — Separate temporal authorization from rate limiting

- **Decision:** Compare prompt-only, stateless per-tool authorization, and
  temporal authorization with one deterministic trajectory catalog. Test
  Gateway rate limiting through a separate configuration and evidence run.
- **Reason:** Rate limiting bounds request, token, or connection consumption and
  can fail open; it does not decide whether a sequence of actions is authorized.
- **Consequence:** A throttle is never scored as an authorization denial. The
  rate-limit CloudFormation stack deploys separately after authorization tests.

## 2026-08-24 — Stop the policy study at the AWS gate

- **Decision:** Complete local implementation and evidence, but do not create
  AgentCore, IAM, Lambda, DynamoDB, CloudWatch, or rate-limit resources yet.
- **Reason:** The repository defines cloud deployment and paid usage as a
  separate approval boundary. Local Dogwood validation cannot establish actual
  session headers, managed policy logs, latency, propagation, or teardown.
- **Consequence:** Managed scenarios, redacted CloudWatch evidence, exact cloud
  cost, and final resource-state proof remain `NOT TESTED` until approved.

## 2026-08-24/25 — Accept managed temporal enforcement and close the bounded study

- **Decision:** Accept AgentCore batches `2ee75ff6e4ec` for S01-S07/S09-S11 and
  `8d21c017f03f` for corrected S08 as the managed enforcement evidence for the
  synthetic policy contract. Keep the broader Strands runtime experiment open.
- **Reason:** The combined 110 accepted runs produced zero false allows, false
  denials, or expectation mismatches in `us-east-1`. Local Dogwood validation
  and replay remain a separate semantic specification layer; they are not
  substituted for the managed result.
- **Consequence:** The bounded policy study reaches its authorization decision
  boundary. The result supports AgentCore temporal policy for these tested
  sequences, not a general production-readiness or Strands adoption claim.
  Earlier invalid multi-statement/overly-restrictive/operator-heavy policies,
  MCP exception semantics, and failed nested input correlation remain recorded
  implementation constraints.

## 2026-08-24/25 — Record Gateway rate-limit outcomes separately

- **Decision:** Mark the composite Gateway rate-limit configuration non-
  enforcing, the single-dimension rerun inconclusive, and neither as
  authorization or proof of reliable throttling.
- **Reason:** Composite-dimension batch `dc0d1e456314` allowed six concurrent
  requests at a configured five requests per second. Single-`toolName` batch
  `e9a8a5293522` completed five requests before an unrelated stale policy-
  session denial contaminated request six; no rate-limit response was observed.
- **Consequence:** Preserve both S12 aggregates as transport evidence, labeling
  one non-enforcing and the other session-contaminated/inconclusive.
  Authorization findings come only from the managed temporal batches. Do not
  add application claims that depend on this rate limit without a new bounded
  test and explicit approval.

## 2026-08-24/25 — Close cloud stacks with bounded cleanup evidence

- **Decision:** Treat the bounded cloud teardown as `PROVEN` for the resources
  created by this experiment.
- **Reason:** Both CloudFormation stacks, the synthetic Lambda and owned log
  group, generated DynamoDB tables and IAM roles, and experiment policy engines
  are absent. The account Gateway count returned to its pre-test baseline of
  two.
- **Consequence:** No further AWS action is authorized by this decision. A
  future rerun must pass a new cloud approval gate. Managed observability remains
  request-ID and CloudWatch-metric based because no span log group was configured.

## 2026-08-25 — Pause Vercel adaptation at the package-line boundary

- **Decision:** Preserve the current official-style Vercel Workflow minimal as
  partial local entry-gate evidence, but test the last stable-compatible
  `@ai-sdk/workflow`/Workflow line before adapting the shared incident.
- **Reason:** The current packages compiled one workflow with 19 generated steps,
  completed three recorded runtime steps, and retained the completed run in the
  local file backend after server shutdown. However, `@ai-sdk/workflow` `2.0.3`
  requires Workflow `5.0.0-beta.43`, and `npm audit --omit=dev` reports 14
  high-severity findings in that required production dependency tree.
- **Consequence:** Do not treat the official minimal as managed durability or a
  completed agent loop. Compare the pinned stable-compatible line next; adapt
  the shared scenario only if it is materially cleaner. External Vercel
  resources and paid usage remain behind their separate approval gate.
