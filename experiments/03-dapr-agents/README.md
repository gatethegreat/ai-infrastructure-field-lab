# Experiment 03 — Dapr Agents

Status: Complete; rejected for production selection

## Purpose in plain English

OpenEnv grades an agent inside a test environment. Dapr Agents is aimed at the
other side of the problem: keeping a real agent job alive while it uses tools,
waits for a person, retries temporary failures, and survives an application
restart.

This experiment asks whether Dapr Agents makes that reliability work easier
enough to justify its extra sidecar, workflow engine, and state-store machinery.
It is not a model-quality comparison, model gateway, or evaluation framework.

## Hypothesis

Dapr Agents can provide a portable integrated backend for agent runtime,
workflow, messaging, state, recovery, and approval with acceptable local
operational complexity.

## Bounded questions

- Can a Dapr-backed workflow retry a temporary failure and wait for approval?
- Can it resume the same persisted workflow after the app and sidecar restart?
- Can a real model inspect the shared incident, select only the permitted tool
  arguments, pause before the simulated effect, and complete after approval?
- What infrastructure and framework-specific code does that require locally?
- Do the framework's quickstarts work at the pinned release without patches?

## Architecture and separation

```text
shared fixture and contracts
  -> incident_runtime.py (thin Dapr Agents tool and hook adapter)
  -> DurableAgent + DaprChatClient
  -> Dapr sidecar
       -> conversation.openai for the one live smoke
       -> Redis agent-memory state store
       -> Redis agent-workflow actor state store
  -> external approval event
  -> exact, idempotent simulated action
```

- `shared/` remains the owner of business contracts, fixtures, and synthetic
  tool behavior.
- `incident_runtime.py` owns only Dapr Agents decorators, agent configuration,
  and the approval hook.
- `live_smoke.py` owns orchestration and evidence capture for one paid model run.
- `recovery_probe.py` isolates deterministic retry, external-event, and restart
  behavior from model quality.
- `components/` owns the experiment's local Dapr component configuration.

Redis is used because Dapr Workflow requires an actor state store in standalone
mode. It is native local setup from `dapr init`, not a new application database.
Dapr warns that Redis lacks actor transaction rollbacks and should not be used
as this production actor store without further evaluation.

## Pinned versions and primary sources

Researched 2026-08-21:

- Dapr Agents `1.0.5`, tag commit
  `745bd41e09c1ec3e09d9f592d2385800e2f21864`, Apache-2.0.
- Dapr CLI `1.18.2`; Windows archive SHA-256
  `6c1590186ff6b61f1c0ee46bd04e78e569fd2cc8628968f9bcda6cdedc275d64`.
- Dapr runtime `1.18.3`, commit
  `2dcf2e3548faf3c740b3d29ee300e2132db65cff`, Apache-2.0.
- Dapr Python packages `1.18.0rc0`, matching the Dapr Agents `1.0.5`
  project lockfile. The package metadata permits newer `1.18.x` versions.
- Python `3.12.10`; Docker Engine `29.4.2`.
- [Dapr Agents introduction](https://docs.dapr.io/developing-ai/dapr-agents/dapr-agents-introduction/)
- [Dapr Agents quickstarts](https://docs.dapr.io/developing-ai/dapr-agents/dapr-agents-quickstarts/)
- [Dapr Agents durability guide](https://docs.dapr.io/developing-ai/dapr-agents/dapr-agents-getting-started/)
- [Dapr Agents hooks and approval](https://docs.dapr.io/developing-ai/dapr-agents/dapr-agents-hooks/)
- [Dapr Agents repository](https://github.com/dapr/dapr-agents)
- [Dapr CLI installation](https://docs.dapr.io/getting-started/install-dapr-cli/)
- [Dapr runtime releases](https://github.com/dapr/dapr/releases)

The resolved virtual environment contains 116 packages and occupies
244,481,878 bytes. Dapr standalone also starts Redis, Placement, Scheduler, and
Zipkin containers. This is materially heavier than Experiments 00 and 01.

## Setup

From the repository root, with Docker Desktop running:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r experiments\03-dapr-agents\requirements.txt

# Install the verified Dapr CLI archive under ignored .local-tools first.
.\.local-tools\dapr-1.18.2\dapr.exe init `
  --runtime-version 1.18.3 `
  --runtime-path .\.local-tools\dapr-home
```

No credential is needed for the offline tests or deterministic recovery probe.
The live smoke needs `OPENAI_API_KEY` exported to the Dapr CLI process. Never
commit the value.

## Run and verify

Offline adapter checks:

```powershell
.\.venv\Scripts\python.exe -m unittest discover `
  -s experiments\03-dapr-agents -p 'test_*.py' -v
```

The recovery probe is intentionally two-phase. Start it through Dapr, wait for
`waiting_for_approval`, stop the process, then run `resume` with the same app ID
and instance ID. The exact result is indexed in the evidence.

The paid live path is prepared but remains a separate approval gate:

```powershell
.\.local-tools\dapr-1.18.2\dapr.exe run `
  --runtime-path .\.local-tools\dapr-home `
  --app-id incident-agent `
  --resources-path experiments\03-dapr-agents\components `
  -- .\.venv\Scripts\python.exe `
  experiments\03-dapr-agents\live_smoke.py `
  --decision approve `
  --evidence experiments\03-dapr-agents\evidence\live-agent-smoke.json
```

## Evidence index

- [`evidence/official-smokes.json`](evidence/official-smokes.json) — official
  Echo and DurableAgent quickstart observations.
- [`evidence/recovery-probe.json`](evidence/recovery-probe.json) — persisted
  RUNNING state before approval and COMPLETED state after process restart.
- [`evidence/duplicate-recovery-probe.json`](evidence/duplicate-recovery-probe.json)
  — a second restarted workflow reused the delivery ID and returned
  `replayed=true` instead of applying a second simulated effect.
- [`evidence/verification.txt`](evidence/verification.txt) — offline boundary
  tests and recovery procedure notes.
- [`evidence/dapr-environment.json`](evidence/dapr-environment.json) — resolved
  Python environment and footprint.

## Current findings and limitations

- `PROVEN`: the Dapr conversation client can reach a local component through a
  sidecar.
- `PROVEN`: an activity temporary failure retried, the workflow persisted while
  waiting for an external event, and the same instance completed after the app
  and sidecar restarted.
- `PROVEN`: a second restarted workflow with the same delivery ID reused the
  persisted simulated result instead of recording another effect.
- `PROVEN`: the local adapter enforces the exact shared remediation arguments;
  only the simulated state-changing tool requires approval.
- `PARTIAL`: the official DurableAgent workflow completed only after a temporary
  compatibility shim. `trigger_agent` in Dapr Agents `1.0.5` uses
  `DaprWorkflowClient` as a context manager, but neither the locked `1.18.0rc0`
  nor stable `1.18.3` workflow client implements that protocol.
- `PARTIAL`: the free Echo component proves wiring, not intelligence. Its fake
  tool call was malformed, no tool executed, and summary parsing logged errors.
- `PARTIAL`: the deterministic probe persists its simulated idempotency record
  in Redis, but the live DurableAgent adapter currently uses process-local
  `SimulatedActionExecutor`; cross-process live-agent effect idempotency is not
  yet proven.
- `NOT TESTED`: real model tool choice, Dapr Agents approval round-trip with a
  real model, denial, approval timeout, pub/sub, multi-agent messaging, load,
  Kubernetes, or cloud deployment.

## Decision

Dapr Agents `1.0.5` is not selected for production. The underlying Dapr
Workflow recovery behavior was strong, but the official Dapr Agents durable
trigger failed against both its locked and currently resolved workflow SDKs.
The official Echo path also could not provide a valid tool-calling proof.

The paid model smoke was intentionally not run. A successful provider call
would not remove the framework compatibility defect, and adopting a workaround
would make this lab responsible for unsupported framework behavior.

This rejection applies to Dapr Agents, the agent framework tested here. It is
not a claim that the graduated Dapr core project is unmaintained. Testing Dapr
core as a general distributed-application runtime is outside this lab's current
agent-runtime question.

## Teardown

The Dapr CLI `uninstall --all` command removed the experiment's Redis,
Placement, Scheduler, and Zipkin containers, the scheduler volume, and the
runtime files under the ignored local runtime path. Final Docker state was
re-read and no `dapr_*` containers remained. Unrelated containers were not
modified. The ignored workspace-local `.venv` and `.local-tools` directories
were removed after the evidence and test results were captured.

## Next bounded step

Begin Experiment 04 with Vercel's current `WorkflowAgent` official minimal
example. Do not create a Vercel project, deploy, or incur paid usage without the
separate external-action approval. The remaining sequence compares
PydanticAI + DBOS, Strands + AgentCore, LangGraph, and Microsoft Agent Framework
rather than treating one framework as the sole Dapr Agents replacement.
