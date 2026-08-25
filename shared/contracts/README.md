# Contracts

Version `1.0` tool-neutral Python contracts are defined in `models.py`.

The initial contract set covers incident input, inspection results, remediation
proposals, approval decisions, simulated actions, final results, and correlated
timeline events. Validation failures use ordinary `ValueError`/`LookupError`
because no cross-runtime failure envelope is yet required.

Later adapters may translate these records, but must not replace the shared
business contracts with framework-owned models.
