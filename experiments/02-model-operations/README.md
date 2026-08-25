# Experiment 02 — Model Operations Necessity

Status: Deferred at the necessity gate; no gateway installed

## Hypothesis

The current direct provider adapter may be sufficient for one agent and one
provider. A maintained gateway should be adopted only if it measurably removes
required routing, fallback, credential, budget, policy, or observability work.

## Comparison

```text
Control:   bounded agent -> direct provider adapter -> model
Candidate: bounded agent -> LiteLLM gateway -> model provider
```

LiteLLM is the first candidate because it is an actively released,
self-hostable OpenAI-compatible gateway with provider normalization, routing,
fallbacks, usage tracking, budgets, authentication, and logging hooks.

Portkey is retained as a managed gateway alternative. Langfuse and Phoenix are
observability/evaluation systems, not automatic requirements for this gateway
test. TensorZero is excluded because its official project is no longer
maintained.

## Entry gate

Decision on 2026-08-21: stop before installation. The current system has one
agent and one provider. Provider fallback will likely matter in a future
production requirement, but it is not required or requested now.

When explicitly reopened:

1. Measure the existing direct OpenAI smoke: services, latency, usage evidence,
   provider-specific code, and missing operational controls.
2. Pin LiteLLM's version, image digest or source revision, license, and primary
   documentation.
3. Run LiteLLM's official minimal gateway example before adapting the shared
   scenario.
4. Start without PostgreSQL, a UI, or another observability service.

## Bounded tests

- same schema-valid model/tool result through direct and gateway paths;
- application changes required to insert or remove the gateway;
- one controlled provider failure and fallback, if a compatible second model
  is available and separately approved for paid usage;
- latency, usage/cost visibility, error shape, and teardown; and
- gateway outage behavior without granting it business-action authority.

## Adoption gate

Retain a gateway only if the evidence demonstrates at least one current need:

- two or more providers or deployments;
- tested fallback or load balancing;
- centralized credentials, budgets, rate limits, or access policy;
- shared model-call records across applications; or
- lower application coupling that outweighs another deployed service.

Otherwise keep direct provider calls and revisit when one of these triggers
becomes real.

## Current result

- `PROVEN`: the existing bounded model smoke can call its provider directly.
- `ABSENT`: a present requirement for multi-provider routing, centralized
  gateway policy, or cross-application model operations.
- `NOT TESTED`: LiteLLM, Portkey, provider fallback, gateway outage behavior,
  gateway latency, or persisted gateway observability.

No package, image, process, port, database, credential, paid request, or cloud
resource was created for Experiment 02. The experiment may be reopened only on
explicit request when fallback or another adoption trigger becomes concrete.

## Initial storage

None for the direct control or routing-only gateway. Add tool-native persistence
only for a separately named observability, feedback, or evaluation question.

## Primary sources

Research date: 2026-08-21.

- [LiteLLM documentation](https://docs.litellm.ai/)
- [LiteLLM release notes](https://github.com/BerriAI/litellm-docs/blob/main/release_notes/index.md)
- [Portkey AI Gateway](https://portkey.ai/docs/product/ai-gateway)
- [Langfuse observability](https://langfuse.com/docs/observability/overview)
- [TensorZero maintenance status](https://www.tensorzero.com/)
