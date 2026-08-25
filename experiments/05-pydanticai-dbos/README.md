# Experiment 05 — PydanticAI + DBOS

Status: Blocked by Experiment 04

## Hypothesis

A modular stack can match the important behavior sought from integrated agent
frameworks and Vercel while keeping responsibilities independently replaceable.

## Planned responsibilities

- PydanticAI: typed agent runtime and tools.
- DBOS: PostgreSQL-backed workflow, queues, and recovery.
- Experiment 02 selection, if any: model gateway and model-call operations.

## Initial storage

PostgreSQL is required for DBOS durable execution. Keep DBOS workflow data and
any model observability data logically separated.

## Primary sources

- [PydanticAI durable execution](https://pydantic.dev/docs/ai/capabilities/durable_execution/overview/)
- [DBOS documentation](https://docs.dbos.dev/)
