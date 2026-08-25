"""Run the deterministic happy path and write reviewable JSONL evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.contracts import ApprovalDecision
from shared.fixtures import load_scenario

from baseline import BaselineExecution


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    fixture = load_scenario()
    execution = BaselineExecution(fixture)
    approval = execution.start(fixture["incident"])
    execution.decide(ApprovalDecision.APPROVE, approval.proposal_fingerprint)
    lines = [json.dumps(event.as_dict(), sort_keys=True) for event in execution.events]
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        print("\n".join(lines))


if __name__ == "__main__":
    main()
