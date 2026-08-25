# Experiment 08 — Microsoft Agent Framework

Status: Planned replacement for the rejected Dapr Agents comparison

## Hypothesis

Microsoft Agent Framework can provide an integrated open-source agent,
tool-calling, graph-workflow, checkpoint, and human-approval path without the
release compatibility defect found in Dapr Agents `1.0.5`.

## Initial storage

Use file checkpoint storage for the official local restart path. Treat it as
local evidence only. Do not create Cosmos DB, Azure Durable Task, or another
managed resource without a separate approved test requirement.

## Entry gate

- Run the current official Python agent example.
- Run the official checkpoint plus human-in-the-loop resume example unchanged.
- Pin the framework, Python, provider, and checkpoint-package versions.
- Confirm whether the relevant APIs are GA or preview at the tested versions.
- Stop if an official core path requires a source patch or compatibility shim.

## Primary sources

- [Microsoft Agent Framework repository](https://github.com/microsoft/agent-framework)
- [Workflow checkpoints](https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints)
- [Durable Task extension](https://learn.microsoft.com/en-us/azure/durable-task/sdks/durable-agents-microsoft-agent-framework)

Research candidate selected 2026-08-21. This is a planned experiment, not an
adoption decision or a production-readiness claim.
