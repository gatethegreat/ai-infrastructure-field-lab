# Experiment 02 — Does Codex Need an AI Gateway?

Status: Local contract and overhead test passed; managed AWS phase gated

## Business question

When does a central AI gateway give a team enough control to justify another
production service? The test compares direct provider access with Codex routed
through LiteLLM. It does not assume that the more elaborate architecture wins.

```text
Control:   Codex workload -> provider
Candidate: Codex workload -> LiteLLM -> provider
```

The practical decision is whether hard budgets, model policy, identity-based
attribution, shared telemetry, and routing are worth the gateway's latency,
infrastructure cost, outage surface, upgrades, and operational ownership.

## Why the experiment was reopened

The original 2026-08-21 necessity gate found no current gateway requirement.
On 2026-09-08, the repository owner explicitly requested the gateway test after
AWS published a Codex + LiteLLM + Amazon Bedrock reference architecture. That
creates a real, bounded question: compare the lowest-complexity direct AWS path
with the customer-operated control point rather than discussing gateways in the
abstract.

## Evidence layers

1. **Local synthetic control:** a deterministic OpenAI Responses-compatible
   provider is called directly and through the real LiteLLM proxy. This can
   prove contract preservation, incremental overhead, mapped errors, and outage
   behavior without credentials or paid inference.
2. **AWS account preflight:** verify authentication and model access without
   printing account identifiers, credentials, or private configuration.
3. **Managed comparison:** direct Amazon Bedrock through IAM Identity Center vs.
   the pinned LiteLLM-on-ECS reference. This is required to prove budgets,
   per-user attribution, real model latency, availability, cost, and teardown.

Local results cannot be promoted into managed claims. Cloud deployment and paid
model usage require a separate explicit approval.

## Fixed workload

Both paths receive the same synthetic workload:

- a non-streaming text response;
- an SSE streaming response with time to first event;
- a successful continuation using `previous_response_id`;
- a forced read-only function call; and
- a controlled upstream error.

The local runner also stops the proxy, confirms that the gateway path fails,
and confirms that the direct path remains available. No business-action tool is
exposed.

## Measurements

- p50 and p95 total latency for direct and gateway paths;
- p50 and p95 time to first SSE event;
- success count and contract assertions;
- gateway outage behavior;
- exact package, source, and reference-image pins; and
- resources, setup effort, operational responsibilities, estimated AWS cost,
  and teardown proof for the later managed phase.

Latency from the local deterministic provider measures proxy overhead only. It
is not representative of Bedrock model latency or internet conditions.

## Local result

On 2026-09-08, LiteLLM `1.100.0` passed the fixed workload against the same
synthetic provider used by the direct control:

- direct text latency: 0.749 ms p50 and 15.295 ms p95 across 20 requests;
- gateway text latency: 23.965 ms p50 and 31.524 ms p95 across 20 requests;
- incremental local gateway latency: 23.216 ms at p50;
- direct streaming time to first event: 0.932 ms p50 across 10 requests;
- gateway streaming time to first event: 17.614 ms p50 across 10 requests;
- both paths passed continuation, forced read-only tool-call, and mapped 429
  cases; and
- after the proxy stopped, the gateway path failed while the direct path still
  completed.

The full aggregate is [evidence/local-summary.json](evidence/local-summary.json).
The AWS preflight found the required tools but no authenticated AWS session, so
no Bedrock model-access query or cloud deployment ran.

## Run the local phase

Python 3.12 is the recorded local runtime. The environment is ignored by Git.

```powershell
python -m venv experiments/02-model-operations/.venv
experiments/02-model-operations/.venv/Scripts/python.exe -m pip install `
  -r experiments/02-model-operations/requirements.txt
experiments/02-model-operations/.venv/Scripts/python.exe `
  experiments/02-model-operations/run_local_experiment.py
python -m unittest discover experiments/02-model-operations -p "test_*.py"
```

The runner writes only aggregate, synthetic evidence to
`evidence/local-summary.json`. Process logs stay under the ignored
`evidence/private/` directory.

## Managed phase gate

Do not create AWS resources until all of these are true:

- AWS CLI authentication succeeds;
- the selected Bedrock model and source region are confirmed in the target
  account;
- the expected billable resources and a teardown owner are reviewed;
- direct and gateway configurations use synthetic identities and prompts; and
- explicit approval is given for the deployment and paid calls.

The AWS reference creates billable infrastructure including ECS Fargate, an
Application Load Balancer, RDS PostgreSQL, networking, WAF, CloudWatch, ECR,
Secrets Manager, KMS, and model inference. Its own documentation says direct
IAM Identity Center is the lowest-complexity path when native AWS identity and
audit controls are enough.

## Adoption gate

Recommend the gateway only if the managed evidence proves at least one current
requirement that the direct path cannot meet acceptably:

- enforceable per-user or per-team budgets and rate limits;
- centralized credentials or model access policy;
- shared model-call attribution across applications;
- tested routing or fallback; or
- lower application coupling that outweighs the added service.

Otherwise recommend direct Bedrock access and document the trigger that should
cause a future reevaluation.

## Source pins and primary sources

Research date: 2026-09-08. See [SOURCE_PINS.md](SOURCE_PINS.md) for immutable
revisions and license boundaries.

- [AWS reference article](https://aws.amazon.com/blogs/machine-learning/set-up-openai-chatgpt-codex-with-litellm-on-amazon-ecs-and-amazon-bedrock/)
- [AWS/OpenAI Codex guidance](https://github.com/openai-on-aws/guidance-codex)
- [LiteLLM gateway quick start](https://docs.litellm.ai/)
- [LiteLLM v1.100.0 release](https://github.com/BerriAI/litellm/releases/tag/v1.100.0)
- [Codex on Amazon Bedrock](https://learn.chatgpt.com/docs/amazon-bedrock)
- [Codex custom provider configuration](https://learn.chatgpt.com/docs/config-file/config-advanced)
