# Shared Scenario

This folder will contain the tool-neutral synthetic incident assistant used by
every applicable experiment.

```text
Incident input
  -> validation
  -> runbook retrieval
  -> read-only inspection
  -> remediation proposal
  -> approval boundary
  -> idempotent simulated action
  -> correlated result
```

- `contracts/` owns versioned input, tool, proposal, approval, action, and result
  schemas.
- `tools/` owns the reusable synthetic read-only context tool and simulated
  idempotent executor.
- `agent/` owns the provider-neutral bounded live-model port and authority rules.
- `fixtures/` owns synthetic incidents, runbooks, tool results, and expected
  transitions.
- `verification/` owns reusable black-box checks and evidence helpers.

Framework-specific models and adapters do not belong here.
