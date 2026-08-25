# Experiment 00 — Baseline

Status: Deterministic baseline complete

## Hypothesis

A small tool-neutral implementation can establish the contracts and evidence
needed to compare later tools without introducing a framework, database, or
cloud platform.

## Bounded questions

- What contracts are required before an agent framework is introduced?
- Can approval bind to one exact proposal and prevent all other effects?
- Can duplicate delivery avoid a duplicate authoritative effect?
- Is a correlated execution reconstructable without a telemetry product?

The baseline deliberately excludes agent frameworks, workflow engines,
databases, cloud resources, and candidate-tool dependencies.

## Architecture

```text
versioned JSON fixture
  -> Incident validation
  -> FixtureRepository (read only)
  -> DeterministicFakeModel
  -> ApprovalRequest bound to proposal fingerprint
  -> SimulatedActionExecutor (in-memory idempotency)
  -> FinalResult + correlated JSONL timeline
```

Business contracts live in `shared/contracts`; synthetic input and read-only
state live in `shared/fixtures`. The ordinary orchestration and its unit tests
remain in this experiment.

## Initial storage

All state is in memory. The committed JSONL file is test evidence, not runtime
storage. Idempotency therefore applies only while the executor process lives;
restart recovery is intentionally absent.

## Version and primary sources

- Python `3.12.10`, observed locally on 2026-08-21.
- Python Software Foundation License; source revision not applicable because the
  preinstalled interpreter and standard library were used without vendoring.
- Standard-library [`dataclasses`](https://docs.python.org/3.12/library/dataclasses.html)
  for typed records.
- Standard-library [`unittest`](https://docs.python.org/3.12/library/unittest.html)
  for deterministic checks.

No third-party package, image, provider, credential, service, or port is used.
Implementation elapsed time was not captured. The repeatable setup is one local
Python process, zero installed dependencies, zero services, zero ports, zero
credentials, and zero provider usage.

## Run and verify

From the repository root:

```powershell
python -m unittest discover -s experiments/00-baseline -p 'test_*.py' -v
python experiments/00-baseline/run.py --evidence experiments/00-baseline/evidence/happy-path.jsonl
```

The checks cover typed validation, happy path, exact-proposal approval,
approve/deny/revise/expire outcomes, duplicate delivery, and the boundary for
untrusted incident notes.

## Evidence index

- [`evidence/verification.txt`](evidence/verification.txt) — captured test run.
- [`evidence/happy-path.jsonl`](evidence/happy-path.jsonl) — ordered correlated
  timeline from accepted input through the simulated effect and final result.

## Findings and limitations

- `PROVEN`: deterministic happy path, exact approval binding, non-approval safe
  outcomes, process-local idempotency, and correlated reconstruction.
- `PARTIAL`: untrusted notes cannot select an action because only trusted fixture
  data feeds the deterministic proposal; this is not a general prompt-injection
  defense.
- `ABSENT`: durable recovery and cross-process idempotency.
- `NOT TESTED`: live-model schema response, model/tool timeouts, telemetry outage,
  provider change, deployment, cost under load, or persisted approval waits.

The optional live-model smoke was not run during Experiment 00 because the
shared-contract gate did not require a provider. A bounded reference path was
later added as the [Experiment 01 live reference path](../01-openenv/README.md#architecture-and-responsibility-boundaries);
it does not change Experiment 00's deterministic evidence.

## Teardown

There are no processes, containers, databases, cloud resources, credentials, or
paid services to remove. Delete regenerated local evidence only if a clean
working tree is desired; the committed evidence is intentionally retained. The
final state was re-read after the runner exited: only repository files remain.

## Exit gate

Met for the deterministic baseline: tests pass, the action boundary is
approval-gated and process-locally idempotent, and the contracts contain no
framework-owned business models. Durable behavior remains explicitly absent.

## Next bounded step

Keep contract version `1.0` fixed and use it as the entry boundary for
Experiment 01. Do not start OpenEnv until that experiment is explicitly begun.
