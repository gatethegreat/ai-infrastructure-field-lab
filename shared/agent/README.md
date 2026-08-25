# Shared Agent Boundary

This package is a provider-neutral port for one bounded live-model smoke path.
It does not own business contracts, provider transport, approval persistence, or
execution.

`BoundedIncidentAgent` permits exactly one named read-only context call and then
validates the typed proposal against the trusted runbook output. A provider
adapter implements `ModelSession`; later experiments can replace that adapter
without changing the authority checks.
