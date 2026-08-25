# AgentCore cloud test plan

This directory contains planning assets for the separately approved AgentCore
cloud boundary. Nothing here is deployed by the local test suite.

## Design

`agentcore-policy-lab.yaml` declares only synthetic resources:

- two IAM-authenticated caller roles, trusted by an operator principal supplied
  at deployment time;
- an MCP AgentCore Gateway in `AWS_IAM` mode;
- a Policy Engine attached to the Gateway;
- six single-statement stateless Cedar policy resources covering three tools
  for each of the two exact synthetic caller principals;
- six single-statement Dogwood policy resources: one write permit per caller,
  plus caller-specific session-write and retry forbids. Each permit uses only
  the matching lookup, unused approval, and fresh approval temporal operators;
  each forbid contains only its count and history operator. The managed retry
  guard counts schema-valid same-approval `execute_write::response` events with
  `status: FAILED` and forbids when that prior history reaches the configured
  limit;
- one Lambda target exposing the four synthetic tools, capped at two reserved
  concurrent executions, with schema-valid `FAILED` domain results for injected
  write failures and a stack-owned seven-day log group; and
- one on-demand DynamoDB table required for idempotent operation status.

The default policy and engine modes are observation-only. Change both
`PolicyEngineMode=ENFORCE` and `PolicyEnforcementMode=ACTIVE` only after the
LOG_ONLY evidence has been reviewed.

Each caller-specific forbid explicitly depends on its matching temporal permit
and the Gateway target. This makes CloudFormation create the positive permit
before validating the narrower forbid, while keeping every policy below the
current three-temporal-operator maximum.

The earlier exception-based S08 probe surfaced as MCP `result.isError`; neither
`execute_write::error` nor the tested request-history guard denied candidate
four. That was useful transport diagnostics, but not a robust domain-failure
contract. `force_error` now returns the normal output schema with deterministic
operation, record, change, and approval IDs plus `status: FAILED`; it stores no
successful value effect. The corrected rule correlates
`output.approval_id` and `output.status: "FAILED"` on prior
`execute_write::response` events and forbids at
`sameChangeResponses >= RetryLimit`. Targeted batch `8d21c017f03f` proved the
fourth-denied behavior across 10/10 runs with zero mismatches.

Approval ID is the explicit retry key across the local specification, current
Dogwood replay, and managed policy. Nested historical
`input.change.change_id` correlation failed open in 10/10 measured managed S08
runs. The local Dogwood retry trace deliberately uses distinct change IDs. The
accepted managed S08 trajectory instead held both approval ID and change ID
constant, so it proves the managed retry cap but does not prove independence
from changing change IDs in AWS.

Approval consumption and the session cap separately match only responses with
`output.status: "SUCCEEDED"`, so failed domain results neither consume an
approval nor increment the successful-write boundary.

`agentcore-rate-limit.yaml` uses the official
`AWS::BedrockAgentCore::GatewayRateLimit` resource in a second CloudFormation
stack. `policies/gateway/rate-limit.json` remains the tool-neutral configuration
mirror used by local checks. Rate limiting is deployed only with the separate
`-ApplyRateLimit` switch because it is fail-open by default and is not an
authorization boundary.

The current isolated retry uses one dimension, `toolName`, with wildcard entry
`toolName: "*"` at five requests per second. The first live stack used the
composite dimensions `toolName` and `$.context.iam.principal`; it reached
`CREATE_COMPLETE`, but all six concurrent same-second calls succeeded. Record
that 6/6 result as a fail-open dimension-resolution risk. The subsequent
single-dimension batch completed five calls before an unrelated stale
policy-session denial stopped the sixth. It emitted no rate-limit response but
is inconclusive at the boundary. Neither result is authorization evidence.

The temporal statements are deliberately source-derived and were accepted and
enforced by AgentCore in `us-east-1`. The approval
predicate rejects approvals already expired when recorded and adds a five-minute
freshness window. It does not prove arbitrary `expires_at` deadlines that pass
after approval recording. In particular, the AgentCore run can prove an
already-expired approval is denied, but cannot claim enforcement at the exact
timestamp embedded in a previously valid approval. The one-use rule observes successful write responses,
so concurrent writes issued before that response is recorded remain a named
race to test rather than an atomic-consumption claim.

## Deployment identity prerequisites

The identity running CloudFormation is separate from the two generated test
caller roles. Before deployment, an administrator must approve a least-privilege
policy for that deployment identity covering CloudFormation stack operations;
creation, update, tagging, and deletion of the declared AgentCore Gateway,
Gateway Target, Policy Engine, Policies, and Gateway Rate Limit; IAM role and
inline-policy lifecycle plus `iam:PassRole`; Lambda function and reserved
concurrency lifecycle; DynamoDB table lifecycle; and CloudWatch Logs log-group
lifecycle. Policy validation and persisted-state verification also require the
matching AgentCore read/list actions and `bedrock-agentcore:InvokeGateway` where
the service performs policy validation. The exact action names and resource
scopes must be checked against the current service authorization reference in
the approved Region; this repository intentionally does not ship an
administrator or wildcard deployer policy.

## Local plan and validation

From the repository root:

```powershell
powershell -File experiments\06-strands-agentcore\infrastructure\plan.ps1
python -m unittest experiments/06-strands-agentcore/tests/test_cloud_assets.py -v
```

`plan.ps1` performs local checks and prints the AWS validation command. Add
`-ValidateWithAws` only when read-only access to the selected AWS account and
Region has been approved.

## Approved deployment flow

The scripts are inert unless their explicit switches are supplied:

```powershell
# 1. LOG_ONLY deployment. This creates paid/cloud resources.
powershell -File experiments\06-strands-agentcore\infrastructure\deploy.ps1 `
  -Apply `
  -CallerPrincipalArn '<operator-role-arn>' `
  -Region '<approved-region>'

# 2. Read-only persisted-state verification.
powershell -File experiments\06-strands-agentcore\infrastructure\verify.ps1 `
  -QueryAws `
  -Region '<approved-region>'

# 3. Deploy the separate rate-limit stack only after the policy run is complete.
powershell -File experiments\06-strands-agentcore\infrastructure\deploy.ps1 `
  -ApplyRateLimit `
  -Region '<approved-region>'

# 4. Preview redaction, then write an ignored candidate copy. After manual
#    review, generate a separate public copy with stable aliases and shifted
#    timestamps. Input and output directories must differ.
powershell -File experiments\06-strands-agentcore\infrastructure\redact.ps1
powershell -File experiments\06-strands-agentcore\infrastructure\redact.ps1 -Apply
python experiments\06-strands-agentcore\infrastructure\publicize_evidence.py `
  --input-directory experiments\06-strands-agentcore\evidence\cloud\redacted-candidate `
  --output-directory '<fresh-public-review-directory>'

# 5. Preview teardown, then capture exact IDs, delete the rate-limit stack
#    before the main stack, and verify every captured resource is absent.
powershell -File experiments\06-strands-agentcore\infrastructure\teardown.ps1
powershell -File experiments\06-strands-agentcore\infrastructure\teardown.ps1 `
  -Apply `
  -Region '<approved-region>'
```

`-ApplyRateLimit` is separate from `-Apply`: the authorization experiment must
not accidentally measure gateway throttling.
Rate-limit verification is likewise opt-in with `verify.ps1 -IncludeRateLimit`
and reads the separate stack through CloudFormation; it does not depend on a
version-specific AgentCore rate-limit list command in the AWS CLI.

Teardown also supports partially created `ROLLBACK_COMPLETE` or
`ROLLBACK_FAILED` main stacks. It captures any outputs and physical resource
IDs still available, deletes the stack, proves the stack is absent, and performs
resource-specific absence checks only for identifiers it could actually
recover.

## Values that must be supplied or confirmed

- approved AWS Region with AgentCore temporal-policy support;
- ARN of the operator identity allowed to assume the two synthetic caller roles;
- unique stack name if the default is already used;
- whether LOG_ONLY evidence is acceptable before changing to ENFORCE/ACTIVE;
- desired write-session limit, retry limit, and gateway requests per second;
- current regional prices confirmed against `cost-estimate.us-east-1.json` (or
  a newly approved Region-specific estimate); and
- an evidence destination under an ignored private directory.

Do not place credentials, account IDs, tokens, unredacted ARNs, session IDs, or
raw CloudWatch exports in committed files.

## Primary sources

Researched 2026-08-24:

- https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/AWS_BedrockAgentCore.html
- https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-bedrockagentcore-gateway.html
- https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-bedrockagentcore-gatewaytarget.html
- https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-bedrockagentcore-policyengine.html
- https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-bedrockagentcore-policy.html
- https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-bedrockagentcore-gatewayratelimit.html
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy-temporal-authoring.html
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy-session-based-temporal.html
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy-permissions.html
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-rate-limits.html
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-rate-limits-examples.html
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-add-target-lambda.html
