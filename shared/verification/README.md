# Verification

`invariants.py` provides a tool-neutral black-box check for a completed,
approval-gated, simulated timeline. Experiment-specific tests additionally
verify validation order, exact proposal fingerprinting, non-approval safety,
and authoritative-effect deduplication.

Later experiments can call the shared invariant without importing the baseline
orchestration. A broader adapter protocol will be extracted only after a second
implementation proves the necessary interface.
