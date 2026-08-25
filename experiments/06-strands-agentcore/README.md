# Experiment 06 — Strands Agents + Amazon Bedrock AgentCore

Status: Temporal-policy subexperiment complete; broader Strands runtime experiment planned

Editorial entrypoint: [`BLOGGER_HANDOFF.md`](BLOGGER_HANDOFF.md)

## Hypothesis

Strands Agents can keep the model-driven tool loop understandable and portable,
while selected AgentCore services remove meaningful AWS production operations
without forcing every available service into the stack.

## Initial storage

Start with local process state for the official Strands example. Do not create
AgentCore Runtime, Memory, Gateway, Identity, Observability, Evaluations,
Bedrock, IAM, CloudWatch, or another AWS resource without explicit approval.

## Entry gate

- Run the official Strands agent and tool example locally unchanged.
- Pin Strands, Python, model-provider, and tool dependencies.
- Verify the model-provider boundary before adapting the shared scenario.
- Record which AgentCore capability answers each managed test question.
- Stop before AWS provisioning and request the separate cloud approval.

## Primary sources

- [Strands Agents Python SDK](https://github.com/strands-agents/sdk-python)
- [Amazon Bedrock AgentCore overview](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)

Candidate added 2026-08-21. The broader Strands comparison remains planned;
neither this subexperiment nor the parent experiment is an adoption or
production-readiness claim.

## Bounded temporal-policy subexperiment

On 2026-08-24 the user explicitly prioritized a synthetic policy comparison for
an evidence-backed article. This is an intentional sequence exception isolated
inside Experiment 06. It does not complete the broader Strands and AgentCore
runtime experiment, and it does not skip that experiment's official Strands
entry gate when the main comparison resumes.

The subexperiment compares:

1. prompt-only advice with authentication and schema validation but no temporal
   enforcement;
2. stateless per-tool authorization; and
3. a local temporal specification, with the same semantics separately checked
   using the pinned Dogwood reference interpreter.

The exact contract and expectation matrix are in
[`POLICY_LAB_CONTRACT.md`](POLICY_LAB_CONTRACT.md). Gateway rate limiting is a
separate throttling test and is never reported as authorization.

## Local architecture

```text
versioned trajectory catalog
          |
deterministic runner -- no LLM
          |
control adapter: prompt | stateless | local temporal specification
          |
synthetic dispatcher and store
          |
append-only event evidence + run summaries

Dogwood policy/schema/trace bundle -- separate semantic conformance evidence
AgentCore Gateway/Policy/CloudWatch -- separate approved cloud evidence
```

The policy-domain code stays inside this experiment because the shared incident
contracts do not model policy sessions, approval consumption, caller isolation,
or retry history. Shared contract version 1.0 remains unchanged.

## Pinned local versions

| Component | Pin |
|---|---|
| Python | 3.12.10 |
| Dogwood source | `c6237c88099b3f492ecc5fcee42df06a19224b97` |
| Dogwood CLI | 1.0.0 from the pinned source commit |
| Rust builder | `rust:1.90.0-bookworm` at `sha256:3914072ca0c3b8aad871db9169a651ccfce30cf58303e5d6f2db16d1d8a7e58f` |
| Runtime image | `debian:bookworm-slim` at `sha256:abd67ffcfa541b485a3dff59865ab629aa048a6c613e639d36e7456b0b229241` |

Dogwood has no public tag or release at this research date, so the complete
commit is the authoritative source pin. The public interpreter explicitly says
it is not a production enforcement engine.

## Reproduce the local proof

Prerequisites are Python 3.12 and Docker. From the repository root:

```powershell
pwsh -NoProfile -File experiments\06-strands-agentcore\docker\build-dogwood.ps1
pwsh -NoProfile -File experiments\06-strands-agentcore\policies\dogwood\generate-schema.ps1
pwsh -NoProfile -File experiments\06-strands-agentcore\policies\dogwood\validate.ps1
pwsh -NoProfile -File experiments\06-strands-agentcore\policies\dogwood\verify-replays.ps1

Push-Location experiments\06-strands-agentcore
python -m unittest discover -s tests -p "test_*.py" -v
python run_policy_lab.py --repetitions 10 --output-dir evidence\local\specification
python capture_dogwood_evidence.py --repetitions 10
Pop-Location
```

The generated schema needs one deterministic correction: Dogwood's MCP schema
converter emits the nested `change` JSON object as a Cedar entity. The generation
script converts that declaration to a record alias so the temporal policy can
correlate `change_id` and `approval_id`. The corrected schema validates without
errors or warnings at the pinned commit.

## Local results

The deterministic comparison produced 330 measured runs and 1,650 request
events: ten runs for each of eleven authorization scenarios under all three
models, after one excluded warm-up per scenario/model.

| Model | Runs | False allows | False denials | Expectation mismatches | Median authorization latency |
|---|---:|---:|---:|---:|---:|
| Prompt-only baseline | 110 | 90 | 0 | 0 | 0.0009 ms |
| Stateless per-tool authorization | 110 | 90 | 0 | 0 | 0.0011 ms |
| Local temporal specification | 110 | 0 | 0 | 0 | 0.0024 ms |

The microsecond-scale values are in-process Python measurements and are useful
only for checking measurement plumbing. They are not AgentCore latency and are
not a production benchmark.

The real local Dogwood CLI validated the policy with zero findings. Nine
semantic trace bundles each matched their committed verdict stream across ten
measured replays. The combined end-to-end Docker CLI replay latency was 672.40
ms median with an observed 531.97–746.64 ms range across 90 samples. That number
includes container and CLI startup and must not be compared as isolated policy
evaluation latency.

Locally proven behavior includes:

- matching lookup and approval prerequisites;
- record and opaque approval-ID correlation;
- fixed-window freshness;
- success-only single-use approval consumption;
- three-success session limit;
- initial failure plus two retries, followed by denial of the fourth attempt;
- caller and session history isolation in the reference traces; and
- fail-closed missing/malformed sessions in the local specification adapter.

## Managed AgentCore results

Managed enforcement ran in `us-east-1` on 2026-08-24 America/New_York
(2026-08-25 UTC) with AWS CLI `2.36.4` and Python `3.12.10`. The accepted
authorization result combines two redacted batches rather than hiding the
failed intermediate S08 designs:

| Managed evidence environment | Value |
|---|---|
| Region | `us-east-1` |
| Test date | 2026-08-24 America/New_York / 2026-08-25 UTC |
| AWS CLI | `2.36.4` |
| Python | `3.12.10` |
| Reproducible lab snapshot commit | `40604c7a082f1d87ff1f71148dc2e5c9b42b843b` |
| Cloud capture base commit | `30965d398315dbf26ca79c78f1516eb2c8f23f45` |
| Cloud capture worktree state | dirty; batch environment records preserve this limitation, while the completed code/evidence state is committed above |
| Local Dogwood source | `c6237c88099b3f492ecc5fcee42df06a19224b97` |

| Source batch | Accepted scope | Runs | False allows | False denials | Mismatches |
|---|---|---:|---:|---:|---:|
| `2ee75ff6e4ec` | S01-S07 and S09-S11, paced one second between steps | 100 | 0 | 0 | 0 |
| `8d21c017f03f` | corrected approval-key S08 retry policy | 10 | 0 | 0 | 0 |
| Combined accepted authorization evidence | S01-S11 | 110 | 0 | 0 | 0 |

This proves the bounded managed scenarios: prerequisite order, record and
approval correlation, expired approval denial, single-use approval, cumulative
successful-write cap, corrected failed-response retry cap, policy-session
rotation, caller isolation, and missing/malformed session behavior. It does not
turn the broader Strands runtime into a completed or production-ready result.

CloudWatch `TemporalLatency` minute-average samples were captured, not isolated
per-request authorization spans. Batch `2ee75ff6e4ec` reported a 37.63 ms median
minute average with a 36.44-54.58 ms observed range; targeted S08 batch
`8d21c017f03f` reported 43.25 ms with a 38.94-47.56 ms range. The runner also
captured AWS request IDs for every recorded request in those batches. No
CloudWatch span log group was configured, so span queries correctly remain
absent and request IDs plus metrics are the managed observability evidence.

Gateway rate limiting remained a separate transport experiment. Composite-
dimension batch `dc0d1e456314` allowed all six concurrent requests at a
configured five requests per second, proving non-enforcement for that tested
configuration. Single-`toolName` batch `e9a8a5293522` completed five requests;
the sixth was denied by an unrelated stale policy session. It emitted no
rate-limit response but is inconclusive at the boundary. Neither result is an
authorization decision.

The failed managed designs remain part of the result:

- AgentCore accepted only one policy statement per CloudFormation Policy
  resource, so bundled permits/forbids had to be split.
- A temporal policy allowed at most three temporal operators, so cumulative
  caps had to move into separate caller-scoped policies.
- Standalone broad forbids were rejected as overly restrictive; each final
  forbid names one exact caller and depends on its positive permit.
- Lambda exceptions surfaced as MCP `result.isError` responses and did not
  populate temporal `execute_write::error` history, leading to schema-valid
  domain failure results instead.
- Nested historical input change-ID correlation failed open in 10/10 S08 runs;
  the accepted retry policy uses the approval ID on the proven response surface.

## Evidence index

- [`evidence/local/specification/events.jsonl`](evidence/local/specification/events.jsonl)
  — every deterministic request, decision, response, timing, session, and error.
- [`evidence/local/specification/runs.csv`](evidence/local/specification/runs.csv)
  — one row per measured model/scenario repetition.
- [`evidence/local/specification/comparison.csv`](evidence/local/specification/comparison.csv)
  — compact per-model/per-scenario comparison.
- [`evidence/local/specification/summary.json`](evidence/local/specification/summary.json)
  — repetition and latency summary with the local-specification disclaimer.
- [`evidence/local/dogwood/validation.json`](evidence/local/dogwood/validation.json)
  — actual Dogwood validation result.
- [`evidence/local/dogwood/replays.json`](evidence/local/dogwood/replays.json)
  and [`runs.jsonl`](evidence/local/dogwood/runs.jsonl) — actual replay verdicts,
  oracle matches, and measured CLI latency.
- [`evidence/local/dogwood/environment.json`](evidence/local/dogwood/environment.json)
  — source commit, image ID, schema hashes, platform, and test date.
- [`evidence/cloud/redacted/accepted-managed-comparison.csv`](evidence/cloud/redacted/accepted-managed-comparison.csv)
  — compact accepted managed authorization rows plus the two separately labeled
  rate-limit outcomes, with source batch on every row.
- [`evidence/cloud/redacted/README.md`](evidence/cloud/redacted/README.md) and
  [`public-redaction-manifest.json`](evidence/cloud/redacted/public-redaction-manifest.json)
  — public-evidence classification, non-reversible identifier handling,
  synthetic timestamp basis, and hashes proving non-sensitive event projections
  did not change during publication.
- [`evidence/cloud/redacted/accepted-managed-measurement-availability.csv`](evidence/cloud/redacted/accepted-managed-measurement-availability.csv)
  — all 110 accepted managed run IDs with explicit null/unavailable values for
  per-request added authorization latency and determining policy, plus the
  non-authoritative configured-policy hint.
- [`evidence/cloud/redacted/2ee75ff6e4ec/managed_temporal-comparison.csv`](evidence/cloud/redacted/2ee75ff6e4ec/managed_temporal-comparison.csv)
  and [`summary.json`](evidence/cloud/redacted/2ee75ff6e4ec/managed_temporal-summary.json)
  — full paced batch; its superseded S08 rows remain visible and are not part of
  the accepted combined result.
- [`evidence/cloud/redacted/8d21c017f03f/managed_temporal-comparison.csv`](evidence/cloud/redacted/8d21c017f03f/managed_temporal-comparison.csv),
  [`summary.json`](evidence/cloud/redacted/8d21c017f03f/managed_temporal-summary.json),
  and [`events.jsonl`](evidence/cloud/redacted/8d21c017f03f/managed_temporal-events.jsonl)
  — corrected targeted S08 aggregate and public event evidence.
- [`evidence/cloud/redacted/dc0d1e456314/gateway_rate_limit-comparison.csv`](evidence/cloud/redacted/dc0d1e456314/gateway_rate_limit-comparison.csv)
  and [`evidence/cloud/redacted/e9a8a5293522/gateway_rate_limit-comparison.csv`](evidence/cloud/redacted/e9a8a5293522/gateway_rate_limit-comparison.csv)
  — the composite six-request non-enforcement result and the session-
  contaminated single-dimension result.
- [`evidence/cloud/redacted/managed_temporal-summary.json`](evidence/cloud/redacted/managed_temporal-summary.json)
  — rejected diagnostic batch `99024dcfae45`; zero-delay propagation and the
  superseded retry design produced ten false allows and four false denials. Its
  canonical-looking filenames are retained only so the failed design remains
  auditable and are not part of the accepted result.
- Each batch directory also contains public-redacted configuration,
  control-plane, environment, request/event, run, summary, and observability
  aggregates. Cloud request IDs use non-reversible public aliases, session IDs
  use a non-reversible placeholder, and exact timestamps use a documented
  synthetic shift. Raw
  evidence remains only in the ignored private directory.
- [`evidence/cloud/redacted/teardown-verification.json`](evidence/cloud/redacted/teardown-verification.json)
  — post-teardown stack and exact bounded-resource counts, with identifiers
  intentionally omitted.

## Limitations and untested claims

- `PROVEN` locally: deterministic trajectory reuse, prompt/stateless false-allow
  baseline, local specification behavior, Dogwood syntax/validation, and the nine
  Dogwood replay oracles.
- `PARTIAL`: approval freshness. The local Dogwood rule proves a fixed five-minute
  window and records `expires_at`, but does not dynamically compare an arbitrary
  earlier expiry value with current time.
- `PARTIAL`: approval consumption. A successful response consumes the approval;
  concurrent writes racing before that response are not proven atomic.
- `PROVEN` managed within the synthetic contract: S01-S11 across 110 accepted
  runs with zero false allows, false denials, or expectation mismatches.
- `PROVEN` managed retry boundary for the redesigned approval-ID retry key with
  `change_id` held constant within each measured retry trajectory. Independence
  from changing `change_id` values is proven only by the local Dogwood trace,
  not by the managed AWS run. Earlier exception, request-history, and nested
  input change-ID designs failed; those failures remain evidence rather than
  being normalized away.
- `PARTIAL`: managed observability. AWS request IDs and CloudWatch policy
  latency metrics were captured, but no CloudWatch spans/log group was
  configured and determining-policy spans are absent.
- `ABSENT` in the captured managed evidence: per-request added
  authorization latency and the actual determining policy. The runner and the
  accepted-run availability table record explicit nulls and reasons rather
  than substituting total request latency or a configured-policy hint.
- `ABSENT` in the tested composite-dimension configuration: Gateway rate-limit
  enforcement; six calls passed a five-per-second boundary. The single-
  dimension rerun is `NOT PROVEN` because a stale policy-session denial
  contaminated request six. This does not weaken or strengthen authorization.
- `PROVEN`: bounded cleanup. Both CloudFormation stacks, the synthetic Lambda,
  its owned log group, generated DynamoDB tables and IAM roles, and experiment
  policy engines are absent. The account Gateway count returned to the
  pre-test baseline of two.
- `NOT TESTED`: the broader Strands runtime entry gate and any model call.

Dogwood's reference interpreter accepts caller timestamps, has in-memory
non-durable history, does not authenticate events, and does not emit production
audit logs. Local success is semantic evidence only.

## Cloud boundary

[`infrastructure/`](infrastructure/) contains mutation-guarded CloudFormation,
verification, redaction, cost, and teardown assets. The main authorization stack
defaults to observation-only modes. The rate limit is a separate CloudFormation
stack so throttling cannot contaminate authorization measurements.

The approved managed test used separate authorization and rate-limit stacks.
Teardown is complete: both stacks, the synthetic Lambda and log group, generated
DynamoDB tables and IAM roles, and experiment policy engines are absent, while
the account Gateway count is back at the pre-test baseline of two. A future
rerun must re-enter the separate cloud approval gate and follow the documented
deletion order rather than treating this completed approval as reusable
authority.

The current small-run estimate is pennies for AgentCore requests themselves;
use a $1–$5 safety budget for Lambda, DynamoDB, CloudWatch, setup/retries, and
pricing drift. Replace every placeholder in
[`cost-estimate.template.json`](infrastructure/cost-estimate.template.json)
with current official regional prices before deployment.

## Primary sources

Researched 2026-08-24:

- [Dogwood reference implementation](https://github.com/dogwood-policy/dogwood)
- [AgentCore temporal policy authoring](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy-temporal-authoring.html)
- [AgentCore temporal policy sessions](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy-session-based-temporal.html)
- [AgentCore Gateway rate limits](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-rate-limits.html)
- [AgentCore pricing](https://aws.amazon.com/bedrock/agentcore/pricing/)
- [AgentCore policy metrics](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-policy-metrics.html)
