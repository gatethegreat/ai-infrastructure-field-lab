# Research Plan

Status: Experiments in progress
Baseline date: 2026-08-21

## Purpose

Test existing AI infrastructure through bounded, repeatable experiments before
deciding whether to build a product. Learn what each tool solves, where tools
overlap, how they compose, and what important work still requires custom code
or operations.

Valid outcomes are:

- adopt and document an existing combination;
- contribute a fix or missing capability upstream;
- create a reusable adapter, recipe, or starter kit;
- validate a new product hypothesis from a repeated gap; or
- publish the field lab itself as portfolio evidence.

## Research questions

1. Which responsibilities belong to the agent runtime, durable workflow, model
   gateway, tool gateway, observability, evaluation, storage, and deployment
   layers?
2. Do integrated platforms reduce meaningful work compared with modular tools?
3. Can components be replaced without redefining the business contracts?
4. What survives duplicate delivery, timeouts, crashes, delayed approval, and
   dependency outages?
5. Can workflow state, business data, audit history, and diagnostic telemetry
   remain clearly separated?
6. What is required locally, when is cloud deployment useful, and what creates
   avoidable cost or platform dependence?
7. Which missing pieces recur across multiple stacks and therefore deserve an
   integration or product investigation?

## Non-goals

- Perfecting the model's wording or domain accuracy.
- Benchmarking every available framework.
- Claiming production readiness from a demo.
- Adding databases, Kubernetes, cloud resources, or paid products by default.
- Building a new control platform before repeated evidence supports it.

## Shared scenario

Every applicable experiment uses one synthetic incident assistant:

```text
Receive incident
  -> validate typed input
  -> retrieve synthetic runbook
  -> inspect evidence with a read-only tool
  -> produce typed remediation proposal
  -> pause before simulated consequential action
  -> approve, deny, revise, or expire
  -> execute an idempotent simulated action when authorized
  -> record correlated result and evidence
```

Shared assets will include versioned schemas, synthetic fixtures, one read-only
tool, one simulated action, a deterministic fake model, one optional live-model
smoke path, correlation identifiers, and reusable verification helpers.

## Storage rule

Start with the storage native to the tested capability.

| Experiment | Initial storage |
|---|---|
| Baseline | In-memory or disposable fixtures |
| OpenEnv | Environment episode state and artifacts |
| Model operations | None for direct calls or routing-only; add a tool-native store only for a persisted observability test |
| Dapr Agents | The state-store component required by Dapr Workflow |
| Vercel | Workflow managed state and event log |
| PydanticAI + DBOS | PostgreSQL because DBOS uses it for durability |
| Strands Agents + AgentCore | Local process state first; each managed AgentCore service requires its own approved test |
| LangGraph | Local checkpointer first; PostgreSQL and Redis only for a demonstrated distributed-runtime requirement |
| Microsoft Agent Framework | File checkpoints locally; production storage only when its durability test requires it |
| Restate, conditional | Local Restate server journal; no separate application database unless the scenario requires one |
| Targeted tools | Only the backend required by the research question |

Workflow state records where an execution stopped. Application state records
durable business objects across executions. Add an application database only
for a documented need such as cross-workflow search, business reporting,
independent retention, application-level uniqueness, knowledge retrieval, or
authoritative audit history.

## Common test catalog

Run only the cases relevant to the claims of the selected tool.

| Test | Proof sought |
|---|---|
| Happy path | Typed input reaches the agent, a required tool runs, and typed output is handled |
| Invalid input | Malformed work is rejected before model or tool execution |
| Duplicate delivery | Repeated input does not duplicate authoritative effects |
| Model timeout | Failure is bounded, visible, and recoverable |
| Tool timeout | Recovery does not silently repeat an effect |
| Process termination | Work resumes from durable state where durability is claimed |
| Approve | Only the exact approved action executes |
| Deny or revise | The decision persists and produces a deterministic next state |
| Approval timeout | Expired work fails safely |
| Telemetry outage | Diagnostic failure does not corrupt business processing |
| Prompt injection | Untrusted content cannot expand tool authority |
| Provider change | Code and configuration changes are measured |
| Teardown | All created resources are identified and final state is verified |

## Experiment sequence

### 00 — Baseline

Build the smallest ordinary typed implementation of the scenario without an
agent framework, workflow engine, database, or cloud platform.

Learn:

- the minimum business contracts and tests;
- how much code later tools remove or add; and
- whether later tools force shared contracts into proprietary objects.

Exit gate:

- deterministic happy path and approval boundary pass;
- the simulated action is idempotent;
- an optional live model returns one schema-valid response; and
- the execution can be reconstructed from the test evidence.

### 01 — OpenEnv

Represent the scenario with OpenEnv actions, observations, state, steps, and
rewards. Do not begin reinforcement-learning training in this experiment.

Learn:

- the effort required to model a business-like environment;
- usefulness for deterministic agent evaluation;
- state, history, reward, and delayed-reward behavior;
- Docker isolation and local development; and
- missing support for production-derived scenarios.

### 02 — Model operations necessity

The necessity gate is complete without installing a gateway. The current lab
has one agent and one provider, and no present requirement for centralized
credentials, budgets, routing policy, or cross-application model records. Keep
the direct provider adapter. Defer LiteLLM, Portkey, and provider-fallback tests
until the user explicitly requests them for a real requirement.

Learn:

- whether a gateway is justified for one agent and one provider;
- gateway configuration, latency, failure modes, and application changes;
- provider switching, fallback, credentials, budgets, and usage records;
- whether direct calls plus application telemetry are already sufficient; and
- which observability or evaluation question, if any, remains afterward.

Reopen this experiment only if evidence demonstrates at least one current need:
two or more providers, centralized credentials or budgets, cross-application
policy, tested fallback, or shared model-call observability. Otherwise retain
direct provider calls and record the no-gateway decision.

### 03 — Dapr Agents

Completed and rejected for production selection. The underlying Dapr Workflow
probe proved retry, persisted approval wait, restart recovery, and durable
duplicate suppression. Dapr Agents `1.0.5` itself failed its official durable
trigger path without a compatibility shim, so the paid model path was not run.

Learn:

- how much runtime, workflow, messaging, state, retry, recovery, approval,
  identity, and telemetry Dapr supplies together;
- crash and approval-wait recovery;
- policy-hook behavior around consequential tools;
- component portability; and
- operational complexity before Kubernetes.

Do not reopen this experiment merely to work around the recorded release defect.
Reconsider only after an upstream release fixes the official path and a current
production requirement specifically favors Dapr Agents.

### 04 — Vercel

Implement the scenario with Vercel AI SDK, AI Gateway, and Workflow. Add
Sandbox only if the scenario includes code execution. Use Workflow managed
state and event logs; do not add PostgreSQL initially.

Learn:

- time from source to a reachable managed application;
- workflow persistence, retries, approval, and developer experience;
- native gateway and observability usefulness;
- what remains portable outside Vercel;
- account, usage, retention, and pricing boundaries; and
- whether a separate application database is actually necessary.

Creating a Vercel project, managed resource, or paid usage requires explicit
approval before action.

### 05 — PydanticAI + DBOS

Build the modular comparison with PydanticAI for typed agent logic, DBOS for
PostgreSQL-backed durable execution and queues, and only the model-operations
component justified by Experiment 02.

Learn:

- whether the modular stack matches integrated platforms with less or more
  complexity;
- separation between runtime logic and workflow state;
- approval, retry, recovery, queue, and observability behavior; and
- missing features that must still be assembled.

Use Temporal only if evidence demonstrates coordination needs that DBOS,
Restate, or the selected framework does not satisfy cleanly.

### 06 — Strands Agents + Amazon Bedrock AgentCore

Run the official Strands agent and tool example locally before using any AWS
managed service. Then, with separate cloud approval, test the same agent in
AgentCore Runtime and add only the AgentCore services required by a named
question, such as Memory, Gateway, Identity, Observability, or Evaluations.

Learn:

- whether agent logic remains portable across model providers and deployment
  targets;
- what AgentCore removes from hosting, identity, tool access, memory, and
  observability operations;
- which AgentCore services are genuinely useful versus convenient bundling;
- AWS resource, IAM, network, retention, pricing, and teardown boundaries; and
- how much code or configuration changes between local Strands and AgentCore.

Do not create AgentCore, Bedrock, IAM, CloudWatch, or other AWS resources
without explicit approval.

Sequence exception recorded 2026-08-24: the user explicitly requested a bounded
AgentCore Policy and Dogwood article experiment before the broader Experiment 06
runtime comparison. Keep this policy work isolated as a subexperiment. Its
local Dogwood evidence does not satisfy the official Strands entry gate, does
not complete Experiment 06, and did not itself authorize AWS resource creation.
A later explicit cloud approval covered the bounded managed policy/rate tests;
those resources were torn down after evidence capture and that approval is not
reusable for the broader experiment.

### 07 — LangGraph

Test LangGraph as the LangChain-family stateful agent and workflow runtime.
Start with its official local tool-calling, checkpoint, interrupt, and resume
paths. Do not treat the broader LangChain integration library as a separate
runtime candidate.

Learn:

- whether explicit graph state makes tool loops and approval transitions easier
  to understand and modify;
- local checkpoint, restart, replay, and idempotency behavior;
- what the production Agent Server adds, including its PostgreSQL and Redis
  requirements;
- framework coupling at the shared-contract boundary; and
- what remains custom for deployment, observability, security, and evaluation.

### 08 — Microsoft Agent Framework

Test Microsoft Agent Framework as the replacement open-source integrated agent
candidate. Start with its official Python agent and checkpoint-plus-approval
examples. Use file checkpoint storage for the local official path; do not create
Cosmos DB, Azure Durable Task resources, or another cloud service without a
separate approved production-durability question.

Learn:

- whether its agent, tool, graph workflow, checkpoint, and approval APIs work
  together without compatibility patches;
- whether file-backed restart recovery is representative enough for local
  comparison and what changes for distributed production storage;
- how much framework-specific state enters the shared business boundary;
- provider portability and observability boundaries; and
- whether it is a credible maintained open-source integrated alternative or
  simply another orchestration layer requiring substantial assembly.

### 09 — Restate, conditional

Run this experiment only if Experiments 05 through 08 leave a specific need for
durable steps, retries, timers, events, or approval waits around an otherwise
preferred agent SDK. Restate is not an agent framework; it is a durable
execution layer that could wrap one.

Learn:

- whether Restate adds the required durability with less operational and code
  weight than DBOS or Temporal;
- crash recovery, duplicate suppression, events, timers, and approval waits;
- the boundary between Restate journal state and application business data; and
- whether the added server is justified by a real gap in the selected runtime.

### Targeted experiments

Run only against a named open question:

- Agentgateway for LLM, MCP, A2A, or API traffic security and policy;
- Promptfoo for red-team or CI evaluation;
- LiteLLM for a self-hosted gateway or provider-fallback requirement;
- Portkey for a managed gateway comparison if LiteLLM leaves a named question;
- Langfuse or Phoenix for unresolved observability and review questions; or
- Temporal for demonstrated complex, long-lived, or distributed coordination
  that the primary candidates and conditional Restate test do not handle
  cleanly.

## Per-experiment process

1. State the bounded hypothesis and exit gate.
2. Record primary sources, licenses, exact versions, and source/image revisions.
3. Run and record the official minimal example.
4. Connect the shared scenario with the smallest adapter.
5. Run the applicable common tests.
6. Capture evidence for state, side effects, traces, and recovery.
7. Measure setup time, changed code, services, cost, and manual work.
8. Record limitations and claims that were not tested.
9. Execute teardown and verify final state.
10. Update the scorecard, findings, and decision log.

## Evidence contract

Every experiment records:

- tool version and research date;
- primary documentation;
- architecture and responsibility boundaries;
- prerequisites, commands, services, ports, and credentials required;
- application changes from the baseline;
- test results and reviewable evidence paths;
- resource and model usage cost;
- storage locations and retention assumptions;
- known limitations and untested claims; and
- teardown commands and confirmed final state.

Record `PROVEN`, `PARTIAL`, `ABSENT`, or `NOT TESTED`. A successful command,
framework trace, or dashboard is not complete-system proof by itself.

## Decision gates

### After baseline

Proceed only when shared contracts are stable enough for meaningful comparison.

### After OpenEnv

Decide whether environment modeling adds value without model training. Continue
into post-training only with a separate approved objective.

### After model operations, Dapr, and Vercel

Compare a combined model-operations layer, an open-source integrated backend,
and a managed integrated application platform. Use the evidence to refine the
modular-stack questions.

Dapr Agents is a recorded rejected result. The remaining plan deliberately
compares a managed integrated platform, a portable modular stack, an AWS-native
managed stack, a graph-oriented runtime, and a maintained open-source integrated
framework instead of forcing one replacement to represent all deployment
choices.

### After the primary candidate set

Choose one result:

- existing stack recommendation;
- upstream contribution;
- reusable integration or operational kit;
- validated new-product discovery; or
- no-build conclusion with published field-lab evidence.

A product gap must recur, matter operationally, and lack a reasonable existing
solution. One unfamiliar or inconvenient tool is not sufficient evidence.

## Next action

Experiments 00 and 01 are complete. Experiment 02 closed at its necessity gate:
retain direct provider calls and defer gateway and fallback testing until
explicitly requested for a real requirement. Experiment 03 proved the
underlying Dapr Workflow recovery behaviors but rejected Dapr Agents `1.0.5`
after its official durable trigger required a compatibility shim. Experiment
04's current Workflow 5 official entry gate compiled and ran locally but exposed
14 high-severity production dependency findings. Test the documented stable-
compatible Workflow 4 line before adapting the shared incident scenario.
Creating a project, deploying, or using paid services remains a separate
approval gate.
