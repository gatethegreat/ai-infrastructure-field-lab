# Experiment 07 — LangGraph

Status: Planned graph-runtime comparison

## Hypothesis

LangGraph can make agent state, tool loops, checkpoints, interrupts, and resume
behavior explicit enough to improve recovery and modification without pulling
the shared business contracts into framework-specific objects.

## Initial storage

Use the official local checkpointer first. PostgreSQL, Redis, LangSmith, and a
managed deployment are separate requirements and must not be assumed from the
local result.

## Entry gate

- Run the official local tool-calling example unchanged.
- Run the official checkpoint, interrupt, and resume path unchanged.
- Pin LangGraph, Python, provider, and checkpointer versions.
- Distinguish LangGraph runtime behavior from optional LangChain integrations.
- Stop if a core local path requires a source patch or compatibility shim.

## Primary sources

- [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview)
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)

Candidate added 2026-08-21. This is a planned experiment, not an adoption
decision or a production-readiness claim.
