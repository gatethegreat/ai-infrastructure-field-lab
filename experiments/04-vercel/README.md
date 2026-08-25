# Experiment 04 — Vercel

Status: Local entry gate in progress; external deployment still requires approval

## Hypothesis

Vercel AI SDK 7 `WorkflowAgent` and Workflow can deliver the shared scenario
faster than the open-source alternatives while making platform dependence
measurable.

## Purpose in plain English

Test whether Vercel provides the clean integrated experience Dapr Agents did
not: a real agent loop whose tool calls are durable workflow steps, with native
retries and approval suspension, without operating Dapr sidecars and control
containers.

## Entry gate

1. Research and pin the current AI SDK, `@ai-sdk/workflow`, Workflow SDK, Node,
   and provider versions from primary sources.
2. Run the official smallest local `WorkflowAgent` example before adapting the
   shared incident.
3. Determine which durability claims can be proven locally and which require a
   Vercel project before creating anything external.
4. Keep the direct OpenAI provider path unless a Vercel-only feature explicitly
   requires AI Gateway; Experiment 02 did not justify a gateway by default.

## Initial storage

Use Vercel Workflow managed state and event logs. Do not add PostgreSQL unless
a separate application-data requirement is first documented.

## External boundary

Creating a Vercel project, managed integration, deployment, or paid usage
requires explicit approval.

## Primary source

- [Vercel `WorkflowAgent` guide](https://vercel.com/kb/guide/what-is-workflowagent)
- [Vercel agent stack guide](https://vercel.com/kb/guide/ai-gateway-and-ai-sdk)
- [AI SDK 7 release](https://vercel.com/changelog/ai-sdk-7)

Research refreshed 2026-08-21. Exact package versions must be pinned when the
experiment begins rather than inferred from the documentation date.

## Entry-gate evidence

The current official package path was tested first under
[`official-minimal/`](official-minimal/). The exact current releases were AI SDK
`7.0.73`, `@ai-sdk/workflow` `2.0.3`, Workflow `5.0.0-beta.43`, Nitro
`3.0.260610-beta`, and Vite `8.2.2` on Node `24.19.0`.

The official-style local workflow compiled and completed three persisted steps.
Its completed run remained inspectable from `.workflow-data` after the server
stopped. This proves the local compiler, step execution, file backend, and CLI
inspection path—not Vercel-managed durability or production readiness.

The current path also exposed two release risks before scenario adaptation:

- `@ai-sdk/workflow` `2.0.3` requires Workflow 5, which is published under the
  `beta` tag; the CLI labels itself a beta release.
- `npm audit --omit=dev` reported 14 high-severity findings through the required
  Workflow dependency tree. The suggested automatic fix would perform an
  incompatible downgrade and was not applied.

Before adapting the incident scenario, test the last stable-compatible line:
`@ai-sdk/workflow` `1.0.70`, AI SDK `7.0.69`, and Workflow `4.8.4`. Use that
combination for the scenario only if its official local path and production
dependency audit are materially cleaner.

## Evidence index

- [`evidence/official-minimal.json`](evidence/official-minimal.json) — pinned
  versions, installation footprint, build result, persisted run summary, and
  audit result.
