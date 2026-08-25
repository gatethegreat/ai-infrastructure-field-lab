# Shared Synthetic Tools

`FixtureRepository` reads versioned synthetic runbooks and observations.
`IncidentContextTool` exposes only the current incident service and returns its
inspection plus permitted remediation. `SimulatedActionExecutor` owns the
process-local idempotent effect.

The read-only model tool and consequential simulated executor remain separate so
no model adapter receives execution authority.
