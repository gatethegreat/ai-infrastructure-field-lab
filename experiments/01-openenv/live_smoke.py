"""Run one paid, bounded live-model tool-calling smoke path."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters import OpenAIResponsesSession
from shared.agent import BoundedIncidentAgent
from shared.contracts import ApprovalDecision, ApprovalRequest, Incident
from shared.fixtures import load_scenario
from shared.tools import FixtureRepository, SimulatedActionExecutor


MODEL_PRICES_PER_MILLION = {
    "gpt-5.6-luna": {"input": 0.20, "output": 1.20},
}


def _local_env(name: str) -> str | None:
    value = os.getenv(name)
    if value:
        return value
    path = ROOT / ".env.local"
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, raw = line.partition("=")
        if separator and key.strip() == name:
            return raw.strip().strip('"').strip("'") or None
    return None


def _estimated_cost(model: str, input_tokens: int, output_tokens: int) -> float | None:
    prices = MODEL_PRICES_PER_MILLION.get(model)
    if not prices:
        return None
    return round(
        (input_tokens * prices["input"] + output_tokens * prices["output"])
        / 1_000_000,
        8,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=_local_env("OPENAI_MODEL") or "gpt-5.6-luna")
    parser.add_argument(
        "--base-url",
        default=_local_env("OPENAI_BASE_URL") or "https://api.openai.com/v1",
    )
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    api_key = _local_env("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is required in the environment or .env.local")

    fixture = load_scenario()
    incident = Incident.from_dict(fixture["incident"])
    repository = FixtureRepository(fixture)
    model = OpenAIResponsesSession(
        api_key=api_key,
        model=args.model,
        base_url=args.base_url,
        timeout_seconds=args.timeout_seconds,
    )
    result = BoundedIncidentAgent(repository, model).run(incident)
    approval = ApprovalRequest(
        proposal_id=result.proposal.proposal_id,
        proposal_fingerprint=result.proposal.fingerprint,
        allowed_decisions=tuple(ApprovalDecision),
    )
    executor = SimulatedActionExecutor()
    evidence = {
        "evidence_version": "1.0",
        "recorded_at": datetime.now(UTC).isoformat(),
        "provider": result.provider,
        "model": result.model,
        "response_ids": list(result.response_ids),
        "tool_call": asdict(result.invocation),
        "proposal": asdict(result.proposal),
        "approval": {
            "proposal_id": approval.proposal_id,
            "proposal_fingerprint": approval.proposal_fingerprint,
            "required_before_execution": True,
        },
        "authoritative_effect_count": executor.effect_count,
        "usage": asdict(result.usage),
        "estimated_model_cost_usd": _estimated_cost(
            result.model, result.usage.input_tokens, result.usage.output_tokens
        ),
    }
    rendered = json.dumps(evidence, indent=2, sort_keys=True) + "\n"
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
