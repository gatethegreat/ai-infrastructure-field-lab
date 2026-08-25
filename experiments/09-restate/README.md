# Experiment 09 — Restate

Status: Conditional; run only for a named remaining durability gap

## Hypothesis

Restate can add durable steps, retries, timers, events, and approval waits around
an otherwise preferred agent SDK with less weight than a general-purpose
workflow platform.

## Initial storage

Use the local Restate server and its native journal. Do not add an application
database or managed Restate deployment without a separate requirement.

## Entry gate

- Name the durability behavior missing from Experiments 05 through 08.
- Run the official local workflow example unchanged.
- Pin the Restate server image or binary and the selected SDK version.
- Prove the named gap locally before adapting the full shared scenario.
- Skip the experiment if the preceding candidates already answer the question.

## Primary sources

- [Restate workflows](https://docs.restate.dev/tour/workflows)
- [Restate AI agents](https://docs.restate.dev/tour/ai-agents)

Candidate added conditionally on 2026-08-21. This is not an adoption decision
or a production-readiness claim.
