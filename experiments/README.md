# Experiments

Run experiments in numeric order. Every primary experiment adapts the shared
scenario and records evidence without changing its business meaning.

Each experiment README must maintain:

1. status and bounded hypothesis;
2. responsibility being tested;
3. exact versions and primary sources;
4. architecture and storage decision;
5. setup, verification, failure injection, and teardown;
6. evidence index;
7. findings, limitations, and untested claims; and
8. exit-gate decision.

Do not start the next experiment until the current exit gate is recorded.
