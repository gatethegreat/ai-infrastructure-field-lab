# Local Dogwood limitations

- This is semantic test evidence from Dogwood's reference interpreter, not
  proof of managed AgentCore enforcement.
- The approval freshness rule is a fixed five-minute event window. The
  synthetic `expires_at` value is recorded but is not enforced dynamically;
  the documented managed temporal syntax does not demonstrate comparing a
  timestamp stored in an earlier response with the current request time.
- Only an `execute_write::response` whose declared `status` is `SUCCEEDED`
  consumes approval or counts toward the successful-write session cap. The
  approval ID in the approval response and any consuming write is matched to
  `change.approval_id`.
- Failed-attempt history is matched by the response's declared `approval_id`
  against the current request's `change.approval_id`. The initial failure and
  two retries may use distinct change IDs; three prior matching
  `execute_write` responses with declared `status` `FAILED` activate the retry
  cap for the fourth candidate call using that approval.
- The required retry proof uses a schema-valid domain failure response rather
  than an MCP `isError` result. Managed AgentCore did not classify the observed
  HTTP-200 MCP `isError` result as the documented `::error` event, so that
  adapter behavior remains a separate managed diagnostic, not a portable
  Dogwood guarantee.
- Caller and session isolation are modeled with universal symmetric event pins.
  Managed AgentCore binds authenticated identity and policy session itself and
  requires separate cloud evidence.
- Dogwood's MCP schema generator emits a nested JSON object as a Cedar entity,
  which prevents event-leaf correlation. `generate-schema.ps1` deterministically
  changes only `execute_write_Input_change` from an entity declaration to a
  record type alias so the generated schema retains the manifest's object shape.
- Upstream commit `c6237c88099b3f492ecc5fcee42df06a19224b97` does not ship a
  Cargo lock consistent with its manifests. The Docker build records the
  resolved lock hash and fails if resolution drifts, but a fully offline rebuild
  would additionally require vendored crates or a committed corrected lock from
  upstream.
