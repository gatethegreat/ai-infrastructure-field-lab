# Experiment 01 — OpenEnv

Status: Complete for the bounded environment-modeling question

## Hypothesis and bounded questions

OpenEnv can express the shared scenario as useful typed actions, observations,
state, and rewards without beginning reinforcement-learning training.

- Can its native reset/step interface model the incident lifecycle?
- Can approval remain bound to one exact proposal?
- Can deterministic trajectories expose state, rewards, and side effects?
- What does OpenEnv provide, and what application behavior remains custom?

Training, Docker isolation, durable recovery, remote deployment, and production
runtime suitability are outside this experiment.

## Architecture and responsibility boundaries

```text
synthetic fixture + shared contracts/tools
  -> IncidentEnvironment (OpenEnv Environment)
  -> typed Inspect / Submit / Decide / Execute actions
  -> typed observations + episode state + deterministic rewards
  -> shared approval fingerprint + simulated idempotent executor
  -> captured trajectory
```

OpenEnv supplies the environment interface and typed base models. The adapter
still owns every business transition, validation rule, approval decision,
reward, history entry, and effect boundary. State is in memory; no database,
container, local server, or cloud resource was added.

The separately invoked live reference path remains provider-neutral in
`shared/agent/`, with the OpenAI transport isolated in
`adapters/openai_responses.py`. The model receives one strict read-only tool and
can only propose; it never receives execution authority.

## Versions and primary sources

Research date: 2026-08-21.

- OpenEnv [`v0.4.1`](https://github.com/huggingface/OpenEnv/releases/tag/v0.4.1),
  tag commit `65c506ef94bb1f7279cb4359673b3ef81031d01f`, BSD-3-Clause.
- Official Echo client `openenv-echo-env==0.1.0`, installed from the same tag.
- Python `3.12.10` in an isolated `.venv`.
- OpenAI live reference: `gpt-5.6-luna` through `POST /v1/responses`; no dated
  snapshot identifier was available to pin.

The official remote Echo reset/step quick start was run before the shared
adapter. The resolved environment contained 111 packages and occupied
371,043,260 bytes (about 354 MiB). Exact resolved versions are captured in
[`evidence/openenv-environment.json`](evidence/openenv-environment.json).

## Setup and verification

The evidence run used:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install openenv==0.4.1
.\.venv\Scripts\python.exe -m pip install "git+https://github.com/huggingface/OpenEnv.git@65c506ef94bb1f7279cb4359673b3ef81031d01f#subdirectory=envs/echo_env"
.\.venv\Scripts\python.exe experiments/01-openenv/official_echo_smoke.py --evidence experiments/01-openenv/evidence/official-echo-smoke.json
.\.venv\Scripts\python.exe -m unittest discover -s experiments/01-openenv -p 'test_*.py' -v
.\.venv\Scripts\python.exe experiments/01-openenv/run_incident_scenario.py --evidence experiments/01-openenv/evidence/incident-trajectory.json
```

The deterministic suites are free. The optional `live_smoke.py` request is a
separate paid model smoke and loads `OPENAI_API_KEY` from the process or ignored
`.env.local`.

## Evidence index

- [`evidence/official-echo-smoke.json`](evidence/official-echo-smoke.json) — the
  official remote reset and typed `echo_message` step returned `Hello, World!`.
- [`evidence/openenv-environment.json`](evidence/openenv-environment.json) —
  Python, platform, footprint, and all resolved package versions.
- [`evidence/verification.txt`](evidence/verification.txt) — 19 deterministic
  baseline, model-boundary, adapter, and OpenEnv lifecycle checks.
- [`evidence/incident-trajectory.json`](evidence/incident-trajectory.json) —
  reset through duplicate execution, with final phase `completed`, cumulative
  reward `1.5`, and exactly one authoritative effect.
- [`evidence/live-agent-smoke.json`](evidence/live-agent-smoke.json) — one real
  two-turn model/tool interaction that stopped at approval with zero effects.
- [`evidence/teardown.txt`](evidence/teardown.txt) — removed virtual environment
  and verified final local resource state.

## Findings, limitations, and decision

- `PROVEN`: OpenEnv can represent this workflow with typed actions,
  observations, episode state, history, completion, and deterministic rewards.
- `PROVEN`: exact-proposal approval, deny, revise, expiry, and process-local
  idempotent replay remain enforceable through the adapter.
- `PARTIAL`: OpenEnv makes trajectories suitable for repeatable agent
  evaluation, but the reward function is custom and no evaluation runner,
  benchmark aggregation, or training was tested.
- `PARTIAL`: hostile text cannot expand authority in these bounded tests; this
  is not broad red-team evidence.
- `ABSENT`: native durable application state and cross-process recovery in this
  in-memory implementation.
- `NOT TESTED`: Docker isolation, local/remote OpenEnv server transport, crash
  recovery, model/tool timeouts, post-training, or production deployment.

Decision: retain OpenEnv as a specialized environment/evaluation option when a
repeatable reset/step trajectory or training-compatible interface is needed.
It does not replace the agent runtime, workflow durability, model gateway, or
business-state layer. Do not begin post-training without a separate objective.

## Teardown

The isolated `.venv` was removed and its absence re-read; it is ignored and
reproducible from the pinned commands above. The official Echo server was a
maintained remote example, not a resource created by this lab. No database,
container, process, cloud resource, or OpenEnv credential remains. The ignored
`.env.local` is retained for later approved model experiments and is not an
OpenEnv resource.

## Next bounded step

Experiment 02 closed at its necessity gate without installing a gateway because
the current one-provider scope does not require one. Begin Experiment 03 with
Dapr Agents; revisit gateway and fallback testing only on explicit request for
a concrete redundancy or centralized-operations requirement.
