# Fixtures

`scenario-v1.json` is the version `1.0` synthetic incident, runbook, and
inspection state. No production or sensitive data belongs here.

The same incident supports happy path, invalid-input mutations, duplicate
delivery, approve/deny/revise/expire, and an untrusted-notes boundary. Failure
fixtures will be added only when a tested runtime makes timeout or recovery
semantics meaningful.
