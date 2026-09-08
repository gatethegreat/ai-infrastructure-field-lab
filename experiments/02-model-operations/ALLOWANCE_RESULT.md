# Can a team member have an AI spending allowance?

Observed 2026-09-08. Research evidence, not an article or production recommendation.

## Answer

**The tested gateway stopped further consumption on one key without blocking
the other key, but it did not enforce an exact never-exceed ceiling.**

Three fresh-key trials produced the same result. Each key had a deliberately
artificial $0.05 hourly budget. Each successful synthetic response cost $0.013.

| Per-trial worker | Bare direct completions | Gateway completions | Gateway budget rejections | Gateway synthetic spend |
| --- | --- | --- | --- | --- |
| Ordinary, 3 planned calls | 3 | 3 | 0 | $0.039 |
| Repetitive, 8 planned calls | 8 | 4 | 4 | $0.052 |

Across the three trials, all 12 budget-denied requests had zero additional
provider calls. All nine ordinary requests completed, including one after the
other key had been blocked in each trial. All six key counters reconciled with
their request-log spend after persistence polling. Failure rows were present
but had zero spend: request-log row count is not completed-call count.

The threshold was exceeded by $0.002, or 4% of this artificial allowance.
That percentage is specific to these chosen amounts; it is not a general
overshoot guarantee. There was no actual provider charge or demonstrated
customer saving. Do not headline a 50% savings claim from a scripted workload.

## Method and reproducibility

- Actual LiteLLM enforcement and PostgreSQL, with a deterministic synthetic
  provider. Exact image digest is stored in the evidence and runner.
- Six freshly generated keys across three trials in one gateway deployment;
  not three independent deployments and not concurrent load testing.
- Sequential schedule per path: ordinary, four repetitive, ordinary, four
  repetitive, ordinary. Direct path ran first. Input and output ceilings were
  matched; maximum output was explicitly 16 tokens.
- The bare direct control deliberately had no per-key spending policy. It
  does not represent every control available from AWS or other providers.
- Repetition was scripted, not an autonomous agent deciding to loop. The
  gateway enforced a consumption rule; it did not recognize waste or assess
  whether an employee's work was valuable.
- Raw local logs stay ignored. Only synthetic summaries are public.
- All three containers and the experiment network were removed. No paid
  inference or AWS infrastructure was used; the prior provider ledger is unchanged.

Run `python experiments/02-model-operations/run_allowance_scenario.py` with
Docker running and port 4003 free. Existing matching container names cause a
safe stop. This starts disposable local containers, not an AWS deployment.

Proof: [recorded trial and accounting evidence](evidence/allowance-20260908T154817Z.json),
[runner](run_allowance_scenario.py), and
[offline evidence regression tests](test_research_evidence.py).

## Business interpretation and limits

An allowance can be useful even when it is not a precise billing guarantee.
Ask how excess consumption is stopped, what happens to the other users, and
whether the accounting survives the operational lifecycle.

This scenario establishes local isolation and threshold behavior only. It
does not establish real-provider invoice accuracy, completed Codex work,
employee identity, concurrent overshoot bounds, durability, or bypass resistance.
The earlier restart discrepancy remains unresolved; it was not retested here.
Fresh-key repeats strengthen this narrow observation, not production reliability.

Editorial recommendation: enough evidence for a scoped business article about
the distinction between spending visibility, consumption control, and a hard
ceiling. Not enough for a Codex adoption recommendation, ROI comparison, or
managed AWS deployment endorsement. See RESEARCH_STATUS.md for broader gaps.
