# Blogger handoff — Why Per-Tool Permissions Aren't Enough for AI Agents

Use this file as the editorial entrypoint. The surrounding folder contains the
reproducible lab, policies, tests, infrastructure, and redacted evidence behind
the article. Start with the result and link to technical details only where they
help the reader.

The private editorial task is intentionally omitted from this public handoff.

## Plain-English thesis

An AI agent can make several individually permitted tool calls and still produce
an unsafe overall result. Per-tool permissions answer, "May this caller use this
tool?" Temporal policies also ask, "Did the required steps happen, in the right
order, with matching values, inside the same caller session and safety budget?"

## Verified headline result

The same deterministic synthetic trajectories were compared under prompt-only
instructions, stateless per-tool authorization, and temporal enforcement.

| Control | Measured authorization runs | False allows | False denials |
|---|---:|---:|---:|
| Prompt-only | 110 | 90 | 0 |
| Stateless per-tool authorization | 110 | 90 | 0 |
| Local temporal specification | 110 | 0 | 0 |
| Managed AgentCore temporal enforcement | 110 | 0 | 0 |

The pinned Dogwood interpreter also matched nine semantic trace oracles across
ten measured replays each. Managed AgentCore verified ordering, identifier and
approval matching, freshness, one-use approval, cumulative and retry limits,
session rotation, caller isolation, and malformed-session behavior.

## Recommended article structure

1. Open with a simple example: every door badge swipe is permitted, but the
   sequence of rooms entered can still violate policy.
2. Explain the gap between prompt advice, permission to call one tool, and
   permission for a complete multi-step trajectory.
3. Introduce the four synthetic tools and the three control models.
4. Show three representative failures: write without prerequisites, mismatched
   identifiers, and cumulative/retry limits.
5. Present the compact results table.
6. Explain what failed during implementation and what had to change.
7. Separate authorization, rate limiting, application idempotency, and human
   approval as four different controls.
8. End with the vendor-aware pattern, not an AWS product recommendation.

## Important honest findings

- AgentCore accepted one statement per policy resource and no more than three
  temporal operators per policy, requiring the final policy to be split.
- Lambda exceptions did not populate the temporal error history needed by the
  retry rule. Schema-valid domain failures plus approval-ID correlation worked.
- A composite-dimension Gateway rate-limit test allowed six concurrent calls at
  a configured five-per-second boundary. This is transport-control
  non-enforcement, not an authorization failure.
- A second single-dimension rate-limit run was inconclusive because a stale
  policy-session denial contaminated request six.
- Per-request added authorization latency and the exact determining policy were
  unavailable because determining-policy spans were not configured. Use the
  captured request latency and CloudWatch minute-average policy latency only as
  their correctly labeled measurements.
- Local Dogwood execution is semantic evidence, not managed enforcement or a
  production authorization engine.

## Claims to avoid

- Do not say both Gateway rate-limit configurations failed open.
- Do not present total request latency as isolated authorization latency.
- Do not claim arbitrary dynamic approval-expiry enforcement or atomic
  concurrent approval consumption.
- Do not present this as proof that the broader Strands runtime is production
  ready.
- Do not include client names, production identifiers, prompts, credentials, or
  proprietary policies.

## Evidence links

- [Experiment README](README.md)
- [Exact policy and scenario contract](POLICY_LAB_CONTRACT.md)
- [Compact managed comparison](evidence/cloud/redacted/accepted-managed-comparison.csv)
- [Corrected S08 public event evidence](evidence/cloud/redacted/8d21c017f03f/managed_temporal-events.jsonl)
- [Accepted-run measurement availability](evidence/cloud/redacted/accepted-managed-measurement-availability.csv)
- [Dogwood limitations](policies/dogwood/LIMITATIONS.md)
- [Cloud setup, verification, cost, and cleanup](infrastructure/README.md)

## Reproduction facts

- Region: `us-east-1`
- Test date: 2026-08-24 America/New_York / 2026-08-25 UTC
- Python: `3.12.10`
- AWS CLI: `2.36.4`
- Dogwood source: `c6237c88099b3f492ecc5fcee42df06a19224b97`
- Private research snapshot: source history intentionally not published
- Managed authorization: 110 accepted runs, zero false decisions
- Automated verification: 78 Experiment 06 tests plus 7 baseline tests
- Direct AgentCore reproduction estimate: approximately `$0.045`, plus small
  Lambda, DynamoDB, and CloudWatch charges within the documented safety ceiling
- Cleanup: both stacks and all bounded experiment resources verified absent
