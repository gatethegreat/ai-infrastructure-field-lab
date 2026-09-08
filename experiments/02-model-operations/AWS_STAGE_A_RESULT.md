# Stage A result

This page covers the earlier API compatibility stage only. Later policy and
Codex results and the cumulative budget ledger are in [RESEARCH_STATUS.md](RESEARCH_STATUS.md).

## Updated outcome: compatibility passed

After approval to reserve unreported failed-request usage, the bounded rerun
passed text, semantic continuation, streaming, forced read-only tool selection,
and tool-result continuation on both direct and local LiteLLM paths. Ten
requests completed using the same model and Bedrock Runtime endpoint. Evidence:
evidence/bedrock-comparison-20260908T145732Z.json.

Across Stage A attempts only: 11 successful requests with approximately USD
0.000294525 estimated token cost, plus one earlier 503 with unknown billing.
USD 0.05 is reserved for that failed request, not reported as spend. Twelve
provider requests have been attempted; the original limit is 40. The gateway
process stopped after the run. No cloud infrastructure was deployed.

Observed times vary substantially. This small sequential sample cannot isolate
gateway overhead or justify representative latency percentiles. This stage
did not test budgets, attribution, logging, Codex task execution or managed
recovery; subsequent local tests are described in RESEARCH_STATUS.md.

## Earlier attempt, preserved

Historical account below: the failed-request reservation was later approved
and the bounded compatibility rerun above passed. This is not an active gate.

The approved Stage A attempt produced one successful direct Bedrock Responses
call and then stopped at an upstream HTTP 503 on the comparison's first direct
request. This is not evidence of a LiteLLM failure: no request passed through
the gateway in the comparison.

The successful smoke used us.openai.gpt-5.6-luna in us-east-1, returned the
expected synthetic text, and reported 12 input and 6 output tokens. At a
conservative input allowance of USD 0.275/million and output price of USD
1.32/million, that call is estimated at USD 0.00001122. The failed request did
not return usage. Its billing is unknown, not proven zero.

Two provider requests were attempted across both scripts. Automatic retries
were disabled. The approved plan requires stopping on unaccounted usage, so
the streaming, continuation and tool-round-trip cases remain NOT TESTED with
Bedrock. The local proxy process was stopped. No cloud infrastructure was
created. The USD 5 authorization has not been revoked, but does not override
the agreed stop condition.

Evidence: evidence/bedrock-smoke.json and evidence/bedrock-comparison.json.
Next: reconcile failed-request usage if available, or agree a conservative
failed-request allowance within the existing USD 5 total before a bounded retry.
