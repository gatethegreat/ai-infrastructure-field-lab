# AI Infrastructure Field Lab

A hands-on lab for understanding how modern AI infrastructure tools work alone
and together. The lab compares integrated platforms, modular open-source
components, and managed services using the same small synthetic agent.

The goal is evidence, not forced novelty. The work may lead to an existing
stack recommendation, an upstream contribution, a reusable integration, or a
new product hypothesis only when repeated tests demonstrate a meaningful gap.

This is a synthetic research lab, not production software or a certification
that any tested stack is production-ready.

## Research question

What is the smallest practical combination of tools that can support a
reliable, observable, portable AI-agent application, and what important work
remains difficult after those tools are combined?

## Shared system

```text
Synthetic incident
      |
Typed validation
      |
Runbook retrieval and read-only inspection
      |
Typed remediation proposal
      |
Approval for a simulated consequential action
      |
Idempotent simulated execution
      |
Correlated result and evidence
```

## Experiment order

| Order | Experiment | Main question |
|---|---|---|
| 00 | Baseline | What does the application require before a framework is added? |
| 01 | OpenEnv | How useful are typed environments, observations, actions, and rewards? |
| 02 | Model operations decision | Is a gateway required now, or should routing and fallback research remain deferred? |
| 03 | Dapr Agents | Rejected: did the integrated backend work without release workarounds? |
| 04 | Vercel | How much does a managed AI application platform remove, and what becomes platform-dependent? |
| 05 | PydanticAI + DBOS | Can a lightweight modular stack match the integrated platforms with less infrastructure? |
| 06 | Strands Agents + Bedrock AgentCore | How much does an AWS-native agent stack provide without locking the agent logic to one model or framework? |
| 07 | LangGraph | Does a graph-oriented runtime provide clearer state, recovery, and approval control than the other agent frameworks? |
| 08 | Microsoft Agent Framework | Can a maintained open-source integrated framework replace the rejected Dapr Agents candidate? |
| 09 | Restate, conditional | Does a selected agent SDK still need a lighter durable-execution layer than DBOS or Temporal? |
| Later | Targeted tools | Which specific questions remain about security, evaluation, observability, or gateways? |

## Recommended candidate list

```text
Managed integrated        = Vercel AI SDK + Gateway + Workflow
AWS-native managed        = Strands Agents + Amazon Bedrock AgentCore
Portable modular          = PydanticAI + DBOS
Graph-oriented runtime    = LangGraph
Open-source integrated    = Microsoft Agent Framework
Conditional durability    = Restate around the best otherwise non-durable agent SDK
Heavy workflow fallback   = Temporal only for proven complex coordination needs
Separate evaluation track = OpenEnv
```

LangGraph is the relevant LangChain-family candidate for this lab because it
owns stateful agent and workflow execution. LangChain's broader components and
integrations may be used by an experiment, but are not a separate runtime
comparison.

## Storage principle

There is no universal PostgreSQL requirement.

- OpenEnv starts with environment state only.
- Vercel starts with Workflow's managed state and event log.
- Strands starts locally without AgentCore resources. AgentCore Runtime,
  Memory, Gateway, and Observability are separate managed test boundaries.
- LangGraph starts with a local checkpointer; PostgreSQL and Redis are not
  assumed until a distributed production test requires them.
- Microsoft Agent Framework starts with local file checkpoints; production
  checkpoint storage is added only for a separate durability requirement.
- Model operations begin with direct provider calls and no database. A gateway
  or observability store is added only for a proven routing or review need.
- DBOS uses PostgreSQL as part of its durable-execution design.

Add an application database only when the experiment requires durable records
across workflows, independent retention, reporting, search, uniqueness, or an
authoritative audit history.

## Documentation

- [`docs/RESEARCH_PLAN.md`](docs/RESEARCH_PLAN.md) — questions, test process,
  experiment gates, and evidence requirements
- [`docs/TOOL_MAP.md`](docs/TOOL_MAP.md) — responsibilities, overlap, and planned
  combinations
- [`docs/DECISION_LOG.md`](docs/DECISION_LOG.md) — decisions made from evidence
- [`docs/PUBLIC_RELEASE.md`](docs/PUBLIC_RELEASE.md) — public-repository safety
  contract, audit gates, and copy-ready release-session prompt
- [`experiments/06-strands-agentcore/BLOGGER_HANDOFF.md`](experiments/06-strands-agentcore/BLOGGER_HANDOFF.md)
  — editorial entrypoint for the completed temporal-policy subexperiment
- [`results/SCORECARD.md`](results/SCORECARD.md) — cross-tool comparison
- [`results/FINDINGS.md`](results/FINDINGS.md) — accumulated findings and gaps
- [`SECURITY.md`](SECURITY.md) — private vulnerability-reporting instructions
- [`LICENSE`](LICENSE) and [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)
  — project license and third-party provenance

## Current status

Experiments 00 and 01 are complete. OpenEnv `v0.4.1` modeled the shared scenario
as a typed, deterministic trajectory and is retained as a specialized
environment/evaluation option—not selected as the production runtime. No cloud
resource was created and no production-readiness claim exists. TensorZero was
retired from the active plan after its official project became unmaintained.
Experiment 02 concluded that no gateway is required for the current one-provider
scope. LiteLLM, Portkey, and fallback testing are deferred until explicitly
requested for a real redundancy or centralized-operations requirement. Dapr
Agents `1.0.5` was rejected after its official durable trigger required a
compatibility shim, although the underlying Dapr Workflow recovery probe
succeeded. Vercel's current official Workflow 5 entry gate compiled and ran
locally, but its production dependency tree reported 14 high-severity findings.
The next bounded task is the documented stable-compatible Workflow 4 line test
before adapting the shared scenario. Microsoft Agent Framework remains the
planned open-source integrated comparison, and the expanded plan also includes
Strands plus AgentCore, LangGraph, and a conditional Restate test. Temporal is
active and maintained, but stays a targeted heavier workflow fallback rather
than an automatic experiment.

On 2026-08-24 an explicitly requested policy subexperiment inside Experiment 06
completed without starting the broader Strands runtime work.
Prompt-only and stateless controls produced the expected temporal false allows;
the local temporal specification and nine pinned Dogwood replay oracles matched
their expectations. Managed AgentCore enforcement then matched all eleven
authorization scenarios across 110 accepted runs in `us-east-1`. The separate
Gateway rate-limit probe produced one non-enforcing composite-dimension result
and one session-contaminated inconclusive result. All approved cloud resources
were torn down and verified absent.
