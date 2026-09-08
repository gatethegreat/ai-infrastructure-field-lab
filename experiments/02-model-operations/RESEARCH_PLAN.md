# Research and Test Plan

## Claim under test

An AI gateway is worth operating for a Codex team only when centralized hard
controls and shared attribution solve a current organizational problem that is
more expensive or risky than the gateway itself.

## Audience and angle

Lead with the business tradeoff: control versus another production dependency.
Use the build to make the tradeoff tangible, but keep implementation detail in
evidence sections. A business owner should understand what problem each layer
solves, who operates it, what happens when it fails, and why direct access may
still be the better answer.

## Questions

1. Which controls exist in direct Bedrock access through IAM Identity Center?
2. Which missing controls does LiteLLM actually enforce rather than merely
   report?
3. What latency and failure surface does the proxy add?
4. Does the gateway preserve Codex's Responses API behavior, including
   streaming, continuation, and tool calls?
5. Can spend and requests be attributed to a synthetic person or team without
   storing prompts or exposing credentials?
6. What must the platform team patch, scale, back up, restore, monitor, and
   troubleshoot?
7. At what team size or governance requirement does the extra system become
   rational?

## Evidence matrix

| Claim | Local synthetic | AWS managed | Publication state |
| --- | --- | --- | --- |
| Responses contract survives proxy | Passed | Required | Partial: local only |
| Incremental proxy latency | Passed | Required | Partial: local only |
| Gateway outage is a new failure boundary | Passed | Required | Partial: local only |
| Budget/rate limits reject excess use | Not sufficient | Required | Not tested |
| Per-user/team cost attribution | Not sufficient | Required | Not tested |
| Direct IAM path is operationally simpler | Architecture evidence | Required | Partially supported by AWS reference |
| Exact monthly cost and operator burden | Not sufficient | Required | Not tested |
| Clean teardown | Passed for local processes | Required | Partial: local only |

## Local acceptance criteria

- LiteLLM `1.100.0` starts from the pinned requirements file.
- Direct and gateway paths both pass text, streaming, continuation, forced tool,
  and controlled-error cases against one deterministic provider.
- Aggregate p50/p95 measurements are recorded without prompts or identifiers.
- After LiteLLM stops, its path fails while the direct provider still succeeds.
- Re-running the harness replaces only deterministic aggregate evidence.

## Managed acceptance criteria

- Use only synthetic identities, prompts, repositories, and task data.
- Record direct and gateway p50/p95 across the same request sequence and sample
  count.
- Cross a disposable budget threshold and verify the next request is rejected.
- Verify one model restriction and one RPM/TPM restriction.
- Capture request, token, cost, model, and synthetic identity attribution.
- Test a gateway outage and recovery without creating business-side effects.
- Record CloudFormation resources, configuration differences, setup time,
  monthly estimate, operational responsibilities, and complete teardown.
- Publish only redacted aggregates and screenshots that exclude prompts,
  responses, raw keys, account IDs, request IDs, and employee identities.

## Stop conditions

- AWS authentication or model access is unavailable.
- The reference requires a source patch rather than configuration.
- A control cannot be tested without real client or production data.
- Cost or blast radius exceeds the reviewed bound.
- The result would only reproduce the AWS tutorial without adding comparative
  evidence.

## Article decision gate

Do not draft the conclusion until the managed phase either completes or fails
in a way that is itself decision-relevant. A valid outcome may be "use direct
Bedrock until hard multi-user controls become necessary."
