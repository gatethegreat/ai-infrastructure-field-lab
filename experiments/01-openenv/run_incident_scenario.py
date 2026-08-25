"""Run and record the deterministic shared scenario through OpenEnv."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from environment import (
    DecideApprovalAction,
    ExecuteApprovedAction,
    IncidentEnvironment,
    InspectContextAction,
    SubmitProposalAction,
)
from shared.fixtures import load_scenario


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", required=True, type=Path)
    args = parser.parse_args()
    environment = IncidentEnvironment(load_scenario())
    trajectory = []

    def record(label, observation):
        trajectory.append(
            {
                "label": label,
                "observation": observation.model_dump(mode="json"),
                "state": environment.state.model_dump(mode="json"),
            }
        )

    record("reset", environment.reset(episode_id="episode-openenv-001"))
    record(
        "inspect",
        environment.step(InspectContextAction(service="checkout-api")),
    )
    record(
        "propose",
        environment.step(
            SubmitProposalAction(
                action="restart_replica",
                target="checkout-api/replica-2",
                parameters={"reason": "elevated_503_rate"},
                rationale="Synthetic evidence exceeds the runbook threshold.",
            )
        ),
    )
    fingerprint = environment.state.proposal_fingerprint
    record(
        "approve",
        environment.step(
            DecideApprovalAction(
                decision="approve", proposal_fingerprint=fingerprint
            )
        ),
    )
    record(
        "execute",
        environment.step(
            ExecuteApprovedAction(proposal_fingerprint=fingerprint)
        ),
    )
    record(
        "duplicate_execute",
        environment.step(
            ExecuteApprovedAction(proposal_fingerprint=fingerprint)
        ),
    )
    evidence = {
        "evidence_version": "1.0",
        "recorded_at": datetime.now(UTC).isoformat(),
        "openenv_version": "0.4.1",
        "storage": "in-memory",
        "trajectory": trajectory,
        "final_state": environment.state.model_dump(mode="json"),
    }
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
