# Tool Map

Research baseline date: 2026-08-21

Tools are grouped by the responsibility they own. Products in different rows
usually complement one another; products in the same row are more likely to
overlap.

| Layer | Primary candidates | Responsibility |
|---|---|---|
| Agent runtime | PydanticAI, Strands Agents, LangGraph, Microsoft Agent Framework, Vercel AI SDK | Model loop, tools, structured outputs, agent-local behavior |
| Durable execution | DBOS, Restate, Temporal, Vercel Workflow | Steps, retries, pause/resume, recovery, long waits |
| Model gateway and operations | Direct provider API, LiteLLM, Portkey, Vercel AI Gateway | Provider access, routing, fallback, usage, model-level controls |
| Tool and agent gateway | Agentgateway, MCP gateways | Authentication, authorization, routing, policy, MCP/A2A traffic |
| Temporal authorization | Dogwood semantics, AgentCore Policy | Prerequisite actions, value correlation, approval freshness/reuse, cumulative and retry limits within an authenticated session |
| Gateway throttling | AgentCore Gateway rate limits and comparable gateway controls | Request, token, and connection consumption limits; not an authorization decision |
| AI observability | OpenTelemetry, Phoenix, Langfuse, Portkey | Model/tool traces, datasets, feedback, experiments, debugging |
| Evaluation and red teaming | Promptfoo, Phoenix, Langfuse | Regression tests, scoring, adversarial testing, comparisons |
| Agent environments | OpenEnv | Actions, observations, state, rewards, isolated environments |
| Application state | Tool-native workflow state; database when required | Business records, search, reporting, cross-workflow history |
| Infrastructure telemetry | OpenTelemetry and compatible backends | Service traces, metrics, logs, and cross-service correlation |
| Deployment | Docker, Vercel, cloud container services; Kubernetes when justified | Packaging, hosting, scaling, release, rollback |

## Planned combinations

### Managed integrated

```text
Vercel API or UI
  -> Vercel Workflow
  -> Vercel AI SDK
  -> Vercel AI Gateway
  -> model and tools
```

Initial storage: Vercel Workflow managed state. Do not add PostgreSQL unless a
separate application-data requirement is documented.

### AWS-native managed

```text
API
  -> Strands Agents
  -> selected model and tools
  -> AgentCore Runtime
  -> only justified AgentCore services
```

Run Strands locally first. AgentCore is modular: Runtime, Memory, Gateway,
Identity, Observability, and Evaluations are separate capabilities, not one
mandatory bundle. Every AWS resource remains a separate approval boundary.

### Open-source integrated

```text
API
  -> Microsoft Agent Framework workflow
  -> agent, tools, checkpoints, and approval
  -> file checkpoint storage locally
  -> production checkpoint provider only when tested
  -> model and tools
```

Microsoft Agent Framework replaces Dapr Agents in the active integrated
comparison. Its production distributed checkpoint path still requires a
storage provider such as Cosmos DB or the Durable Task extension, which is a
separate test and approval boundary rather than an assumed benefit.

### Open-source modular

```text
FastAPI
  -> DBOS workflow and queue
  -> PydanticAI
  -> optional justified model gateway
  -> model and tools
```

DBOS requires PostgreSQL for durable execution. Model-call persistence remains
separate and is enabled only for a documented observability or evaluation test.

### Graph-oriented runtime

```text
API
  -> LangGraph state graph
  -> tools, checkpoints, interrupts, and resume
  -> local checkpointer first
  -> production Agent Server only when separately justified
```

LangGraph is the relevant runtime candidate; LangChain is the broader component
and integration ecosystem. Production PostgreSQL and Redis requirements must be
measured separately from the local runtime.

### Separate environment track

```text
Shared scenario
  -> OpenEnv environment
  -> typed actions, observations, state, and rewards
```

OpenEnv is not treated as production hosting or durable business orchestration.

## Targeted tools

Use these only after a primary experiment records a specific unresolved need:

| Tool | Trigger |
|---|---|
| Agentgateway | Central MCP, A2A, API, or LLM traffic security needs proof |
| Promptfoo | A repeatable red-team or CI evaluation question exists |
| Phoenix versus Langfuse | Native traces cannot answer an observability or review question |
| LiteLLM | Self-hosted provider fallback, routing, or centralized model operations is explicitly required |
| Portkey | A managed gateway comparison against LiteLLM is justified |
| Temporal | The workflow needs complex distributed coordination that DBOS, Restate, or the selected framework does not handle cleanly |

Restate is a conditional planned experiment rather than a general default. Run
it only when a preferred agent SDK still needs a lightweight durable-execution
layer.

## Primary sources

- [OpenEnv](https://github.com/huggingface/OpenEnv)
- [LiteLLM](https://docs.litellm.ai/)
- [Portkey AI Gateway](https://portkey.ai/docs/product/ai-gateway)
- [Dapr Agents](https://docs.dapr.io/developing-ai/dapr-agents/)
- [Strands Agents](https://github.com/strands-agents/sdk-python)
- [Amazon Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)
- [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)
- [Microsoft Agent Framework checkpoints](https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints)
- [Vercel AI agent stack](https://vercel.com/kb/guide/ai-gateway-and-ai-sdk)
- [PydanticAI durable execution](https://pydantic.dev/docs/ai/capabilities/durable_execution/overview/)
- [DBOS](https://docs.dbos.dev/)
- [Temporal](https://docs.temporal.io/)
- [LangGraph](https://docs.langchain.com/oss/python/langgraph/overview)
- [Restate workflows](https://docs.restate.dev/tour/workflows)
- [Agentgateway](https://agentgateway.dev/docs/standalone/latest/about/introduction/)
- [Phoenix](https://github.com/Arize-ai/phoenix)
- [Langfuse](https://langfuse.com/docs)
- [Promptfoo](https://www.promptfoo.dev/docs/intro/)

## Retired candidates

- [TensorZero](https://www.tensorzero.com/) was removed from the active plan on
  2026-08-21 because its official project is no longer maintained and its
  repository is archived. Preserve it only as historical comparison evidence.
- [Dapr Agents](https://github.com/dapr/dapr-agents) was removed from the active
  production comparison on 2026-08-21. Version `1.0.5` required a compatibility
  shim for its official durable trigger, and its Echo path did not produce a
  valid tool-calling proof. The underlying graduated Dapr core project is not
  classified as unmaintained; it is simply outside the remaining agent-runtime
  question.

Exact versions, licenses, and source revisions must be recorded at the start of
each experiment rather than assumed from this planning map.
