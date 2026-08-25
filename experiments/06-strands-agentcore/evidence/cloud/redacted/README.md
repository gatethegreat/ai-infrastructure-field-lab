# Public managed evidence

These files preserve the measured outcomes of a real managed AgentCore test
using entirely synthetic callers, records, approvals, and changes. They are
public evidence, not raw cloud exports.

Before publication, the repository's evidence generator:

- replaces policy-session identifiers with a non-reversible placeholder;
- replaces AWS and MCP request identifiers with stable public aliases;
- replaces managed gateway, policy-engine, resource, operation, and private
  source-commit identifiers with aliases or explicit placeholders;
- replaces managed gateway endpoints with non-resolving `example.invalid`
  URLs;
- shifts exact timestamps to a synthetic `2000-01-01` anchor while preserving
  the intervals between events; and
- retains decisions, outcomes, scenario labels, repetitions, latency values,
  aggregate counts, and the accepted-versus-superseded batch boundaries.

The original test date is recorded in the experiment README. The transformation
manifest in this directory describes the public redaction without containing a
mapping back to private source values. Original cloud evidence is not included
in the public repository.
