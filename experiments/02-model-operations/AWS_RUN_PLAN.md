# AWS experiment run plan

Prepared 2026-09-08. Status: Stage A inference approved up to USD 5.
The owner also approved a conservative allowance for failed requests without
returned usage. Reserve USD 0.05 per such bounded request; retain the original
40-request total limit and all failed evidence. Stage B is still pending.

## Confirmed preflight

- The dedicated lab profile authenticates successfully in us-east-1.
- Bedrock model and inference-profile discovery are permitted.
- US and Global OpenAI GPT-5.6 Luna, Terra, and Sol profiles appear ACTIVE.
- Stage A invocation and five-case direct/gateway compatibility now passed;
  see AWS_STAGE_A_RESULT.md. Discovery alone was not invocation proof.
- There are zero public Route 53 hosted zones in this account and zero issued
  ACM certificates visible in us-east-1. The reference HTTPS endpoint cannot
  be configured from an existing account certificate or hosted zone.

## Stage A: real provider, local gateway

Recommend this first. Use GPT-5.6 Luna for short synthetic requests, provided
the direct and gateway endpoints both support the same model. Pin endpoint,
model ID, region, inference geography, CLI and gateway versions in the results.
Different inference endpoints are a confounder: report them explicitly and do
not attribute their latency difference entirely to LiteLLM.

1. Verify current model prices before the first request. Stop if the bounded
   workload cannot fit the approved inference allowance.
2. Run one direct Responses smoke, then the same request through local LiteLLM.
3. Check output text, streaming completion, real continuation semantics, and
   a read-only tool call followed by its tool result and final answer.
4. Use at most 40 requests total, including retries, with bounded synthetic
   input and at most 256 output tokens per request. Disable automatic retries
   where possible; count all underlying provider attempts.
5. Stop at a conservatively estimated USD 5 of inference. This is an operational
   stop threshold, not an AWS-enforced billing cap. Record token usage as calls
   finish. Stop on unknown pricing. Reserve failed-request usage as approved
   above and stop if known cost plus reservations approaches the allowance.
6. Stop the local gateway and verify its processes and listening ports close.

Stage A creates no ECS, RDS, load balancer, NAT gateway, hosted zone, or cloud
gateway. Existing local synthetic tests do not establish this stage's outcome.
Local master-key configuration also does not prove per-user budgets or policy.

## Stage B: customer-operated AWS gateway

After Stage A succeeds, supply a dedicated test hostname with DNS control and
a matching regional ACM certificate. Prepare and review the full regional cost
estimate before deploying. Use the pinned reference in SOURCE_PINS.md, with
the exact image identity verified independently from the local Python wheel.

Proposed resources: dedicated networking, ECS Fargate service (two 1-vCPU,
2-GiB tasks for replacement/recovery testing), ALB, RDS PostgreSQL, WAF,
Secrets Manager, KMS, ECR, and CloudWatch. Use synthetic scoped keys and restrict
ingress. Record any reduced-availability lab settings as such. Do not repurpose
website infrastructure.

Price the chosen topology, including NAT gateways, public IPv4 addresses,
database storage/backups, logs, secrets and retained resources. Hourly examples
are not a complete quote. Sources:

- https://aws.amazon.com/fargate/pricing/
- https://aws.amazon.com/elasticloadbalancing/pricing/
- https://aws.amazon.com/rds/postgresql/pricing/
- https://aws.amazon.com/vpc/pricing/
- https://aws.amazon.com/waf/pricing/

Required proof: budget threshold rejection, forbidden model rejection, measured
rate limit, synthetic identity/cost attribution, prompt logging behavior,
service failure and recovery, representative Codex task, and paired latency.

## Cleanup requirement

The reference uses Retain and Snapshot deletion policies. Deleting its stacks
alone is insufficient. Inventory resource identifiers privately before cleanup.
Remove only lab-owned resources, including retained logs, image artifacts,
secrets and database snapshots when no longer needed. Schedule lab KMS-key
deletion where immediate deletion is unavailable and report its pending state.
Verify service, database, ALB, NAT, network and retained-resource state afterward.

## Approval decision

Approve Stage A only with an inference allowance of USD 5. Stage B needs a
separate complete cost estimate and endpoint choice after compatibility proof.
No managed gateway deployment has been performed. Stage A paid inference has
run within the approved allowance; see AWS_STAGE_A_RESULT.md for the ledger.
