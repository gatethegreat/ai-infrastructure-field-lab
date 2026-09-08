# Business-focused gateway study

## Reader and central question

Write for an owner or team leader introducing AI tools at work. Assume no
knowledge of AWS, gateways or model APIs. The working question is: When does
putting a shared checkpoint in front of your team's AI usage pay for itself?

Use a comparison/field report. Explain spending, accountability, interruptions
and ownership first. Introduce product names only after explaining their job.
The conclusion must be allowed to favor direct access.

## Tests tied to reader decisions

| Reader question | Test or research | Evidence needed |
| --- | --- | --- |
| Will my tools still work? | Same real model and endpoint directly and via LiteLLM; text, streaming, remembered nonce, tool result | Correct outputs, usage, status and request count; actual Codex task separately |
| Can I stop excessive spending? | Small disposable key budget; cross threshold and retry; check concurrent requests | Allowed and rejected calls, actual overshoot, accounting delay; distinguish alert from enforcement |
| Can different teams have different rules? | Two synthetic identities, model allowlist and rate restriction | Attribution and cross-identity isolation; prove rejected call never reaches provider |
| Can I see who spent what? | Reconcile gateway records with returned provider usage | Tokens and cost by synthetic team; investigate missing records and price assumptions |
| Does this slow work down? | Alternate direct/gateway order; identical short task and model; retain failures | Per-request measurements and completed-task time; enough samples before reporting percentiles |
| What happens when it breaks? | Separately interrupt gateway and provider; restore each | User-visible error, recovery time, extra requests and whether a read-only task resumes |
| What will it actually cost? | Itemize idle infrastructure, inference, storage, logs and maintenance | Monthly estimate with region/date; engineering hours as explicit scenarios, not invented measurements |
| Who has to look after it? | Record installation, troubleshooting, updates, backup and cleanup steps | Measured hands-on time going forward; historical unmeasured time stays unknown |
| Does it expose more information? | Inspect request/response logging with harmless canary text | Actual retained fields and tested logging configuration; no broad compliance claim |

## Execution order

1. Finish bounded real-provider compatibility. Preserve upstream failures and
   distinguish them from gateway failures. Stage A now passed the five-case
   direct and gateway comparison. Retain the earlier direct 503 separately;
   this small sequential sample does not establish a latency advantage.
2. Test policy locally using real LiteLLM and its required persistence, with
   synthetic upstream responses where supported. These results establish the
   local configuration only. Do not invent policy behavior in a fake gateway.
3. Prepare the managed deployment and full estimate after compatibility passes.
   Resolve HTTPS/DNS and validate container tooling. Managed infrastructure
   remains outside the existing inference-only approval.
4. On approved infrastructure, repeat compatibility, policy, attribution,
   failure/recovery and logging tests. Capture a real read-only Codex task.
5. Calculate three transparent scenarios: solo operator, small team and multiple
   teams. Label assumed users, traffic and hourly labor rate. Identify which
   requirement, rather than arbitrary headcount, changes the recommendation.
6. Compare direct access, self-operated gateway and a managed gateway option.
   Verify current features, prices and licensing with primary sources; label
   alternatives researched but not personally tested.
7. Build the evidence inventory, then outline, draft, and final review. Check
   every headline number against its source and recheck current prices.

## Inference budget and failure handling

The owner approved USD 5 total inference and subsequently allowed conservative
reservations for requests without returned usage. Reserve USD 0.05 for each
such short request; this is not measured spend. Keep all attempts across runs
within the original 40-request limit, bounded input and 256 output tokens.
Record automatic retries as disabled. Stop repeated errors for diagnosis;
do not keep sending calls to collect a success. Reconcile known usage plus
reservations before more calls. Reserve remaining budget before each batch.
This is an operational allowance, not a service-enforced billing cap.

## Article shape after evidence exists

Working title: Does Your Team Need an AI Gateway?

- Begin with the practical dilemma of giving a team AI access while keeping
  spending and responsibility understandable.
- Explain the checkpoint in one short paragraph and one simple illustration.
- Show what the experiment changed for spending, visibility and interruptions.
- Show the full operating cost, including the person's time maintaining it.
- End with specific conditions for staying direct, operating a gateway or
  choosing a managed service. Include limitations beside the relevant claims.

Put commands, raw latency tables and architecture details in the public lab.
Use two or three useful evidence visuals in the article: a cost comparison,
one real restriction result and a simple direct-versus-gateway flow. Screenshots
must come from actual synthetic runs. Do not claim that a gateway prevents all
data leaks, guarantees availability or improves model intelligence.

## Minimum bar before drafting

Require one complete real task, one demonstrated useful control, one measured
failure/recovery outcome and an honest cost/ownership comparison. If these
cannot be established, keep research notes and explain what remains unproven.
No article is ready solely because a proxy returned HTTP 200.
