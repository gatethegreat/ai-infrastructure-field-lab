"""Execute the approved managed AgentCore proof or separate rate-limit burst."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import subprocess

from policy_lab.managed import (
    MAX_REPETITIONS,
    PROOF_SCENARIO_IDS,
    AwsCliControl,
    ManagedTrajectoryRunner,
    UrllibTransport,
)
from policy_lab import LogicalClock, load_scenarios


EXPERIMENT = Path(__file__).resolve().parent
PINNED_PYTHON = "3.12.10"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("proof", "rate-limit"))
    parser.add_argument("--region", required=True)
    parser.add_argument("--stack-name", default="agentcore-policy-field-lab")
    parser.add_argument(
        "--rate-stack-name", default="agentcore-policy-field-lab-rate-limit"
    )
    parser.add_argument("--repetitions", type=int, default=10)
    parser.add_argument(
        "--scenario-id", action="append", choices=PROOF_SCENARIO_IDS,
        help="Proof scenario to run; repeat to select more than one (S01-S11).",
    )
    parser.add_argument(
        "--private-output-dir",
        type=Path,
        default=EXPERIMENT / "evidence" / "cloud" / "private",
    )
    parser.add_argument(
        "--redacted-output-dir",
        type=Path,
        default=EXPERIMENT / "evidence" / "cloud" / "redacted",
    )
    parser.add_argument("--metrics-settle-seconds", type=float, default=60.0)
    parser.add_argument("--rate-settle-seconds", type=float, default=30.0)
    parser.add_argument(
        "--inter-step-delay-seconds", "--delay",
        dest="inter_step_delay_seconds", type=float, default=0.0,
    )
    parser.add_argument("--allow-version-drift", action="store_true")
    parser.add_argument("--execute-managed-proof", action="store_true")
    parser.add_argument("--execute-rate-limit", action="store_true")
    return parser.parse_args()


def dependency_environment() -> dict[str, str]:
    completed = subprocess.run(
        ["aws", "--version"], capture_output=True, text=True, check=False, shell=False
    )
    if completed.returncode != 0:
        raise RuntimeError("AWS CLI v2 is required")
    aws_version = (completed.stdout or completed.stderr).strip()
    if not aws_version.startswith("aws-cli/2."):
        raise RuntimeError(f"AWS CLI v2 is required; found {aws_version}")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=EXPERIMENT, capture_output=True,
        text=True, check=False, shell=False,
    )
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=EXPERIMENT, capture_output=True,
        text=True, check=False, shell=False,
    )
    if commit.returncode != 0 or dirty.returncode != 0:
        raise RuntimeError("Git commit and worktree state must be readable")
    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "aws_cli": aws_version,
        "http_client": "python-standard-library-urllib-single-attempt",
        "sigv4": "python-standard-library-hmac-sha256",
        "git_commit": commit.stdout.strip(),
        "git_worktree_dirty": str(bool(dirty.stdout.strip())).lower(),
    }


def plan_summary(args: argparse.Namespace) -> dict[str, object]:
    if args.repetitions < 1 or args.repetitions > MAX_REPETITIONS:
        raise SystemExit(f"--repetitions must be between 1 and {MAX_REPETITIONS}")
    if (
        not math.isfinite(args.inter_step_delay_seconds)
        or args.inter_step_delay_seconds < 0
        or args.inter_step_delay_seconds > 2
    ):
        raise SystemExit("--inter-step-delay-seconds must be between 0 and 2")
    if args.mode == "rate-limit" and args.scenario_id:
        raise SystemExit("--scenario-id is valid only in proof mode")
    scenario_ids = (
        list(dict.fromkeys(args.scenario_id or PROOF_SCENARIO_IDS))
        if args.mode == "proof" else ["S12"]
    )
    scenarios = {
        item.scenario_id: item for item in load_scenarios(clock=LogicalClock())
    }
    request_budget = (
        sum(len(scenarios[item].steps) for item in scenario_ids)
        * (args.repetitions + 1)
        if args.mode == "proof"
        else len(scenarios["S12"].steps)
    )
    return {
        "plan_only": True,
        "mode": args.mode,
        "region": args.region,
        "stack_name": args.stack_name,
        "rate_stack_name": args.rate_stack_name,
        "scenario_ids": scenario_ids,
        "repetitions": args.repetitions if args.mode == "proof" else 1,
        "excluded_warmups": 1 if args.mode == "proof" else 0,
        "maximum_candidate_requests": request_budget,
        "inter_step_delay_seconds": args.inter_step_delay_seconds,
        "private_output": str(args.private_output_dir),
        "redacted_output": str(args.redacted_output_dir),
        "aws_calls_made": False,
    }


def main() -> int:
    args = parse_args()
    if args.mode == "proof" and args.execute_rate_limit:
        raise SystemExit("--execute-rate-limit is valid only in rate-limit mode")
    if args.mode == "rate-limit" and args.execute_managed_proof:
        raise SystemExit("--execute-managed-proof is valid only in proof mode")
    if args.mode == "rate-limit" and args.scenario_id:
        raise SystemExit("--scenario-id is valid only in proof mode")
    execute = (
        args.mode == "proof" and args.execute_managed_proof
    ) or (
        args.mode == "rate-limit" and args.execute_rate_limit
    )
    if not execute:
        print(json.dumps(plan_summary(args), indent=2, sort_keys=True))
        return 0
    environment = dependency_environment()
    if environment["python"] != PINNED_PYTHON and not args.allow_version_drift:
        raise SystemExit(
            f"Python {PINNED_PYTHON} is pinned; found {environment['python']}. "
            "Use --allow-version-drift only when the evidence records the deviation."
        )
    runner = ManagedTrajectoryRunner(
        control=AwsCliControl(),
        transport=UrllibTransport(),
        stack_name=args.stack_name,
        rate_stack_name=args.rate_stack_name,
        region=args.region,
        repetitions=args.repetitions,
        private_output=args.private_output_dir,
        redacted_output=args.redacted_output_dir,
        observability_settle_seconds=args.metrics_settle_seconds,
        inter_step_delay_seconds=args.inter_step_delay_seconds,
        scenario_ids=tuple(args.scenario_id) if args.scenario_id else None,
    )
    result = (
        runner.run_proof()
        if args.mode == "proof"
        else runner.run_rate_limit(settle_seconds=args.rate_settle_seconds)
    )
    runner.private_output.mkdir(parents=True, exist_ok=True)
    (runner.private_output / "managed-environment.json").write_text(
        json.dumps(environment, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    runner.redacted_output.mkdir(parents=True, exist_ok=True)
    (runner.redacted_output / "managed-environment-summary.json").write_text(
        json.dumps(environment, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
