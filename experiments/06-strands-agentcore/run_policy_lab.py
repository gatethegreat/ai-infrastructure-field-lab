"""Run the three local comparison models and write reproducible evidence files."""

from __future__ import annotations

import argparse
import csv
from datetime import date
import json
from pathlib import Path
from statistics import median
from typing import Callable

from policy_lab import (
    DeterministicRunner,
    LocalTemporalSpecificationAuthorizer,
    LogicalClock,
    PromptOnlyAuthorizer,
    StatelessAuthorizer,
    load_scenarios,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=10)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent / "evidence" / "local-policy-lab",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.repetitions < 1:
        raise SystemExit("--repetitions must be positive")
    scenarios = tuple(
        scenario for scenario in load_scenarios(clock=LogicalClock())
        if scenario.scope == "authorization"
    )
    factories: tuple[tuple[str, str, Callable[[], object]], ...] = (
        ("prompt_only", "local", PromptOnlyAuthorizer),
        ("stateless_auth", "local", StatelessAuthorizer),
        (
            "temporal_policy",
            "local_spec",
            LocalTemporalSpecificationAuthorizer,
        ),
    )

    summaries = []
    events = []
    for _, execution_layer, factory in factories:
        for scenario in scenarios:
            DeterministicRunner(
                factory(), clock=LogicalClock(), execution_layer=execution_layer
            ).run(scenario, repetition=1)  # excluded warm-up
            for repetition in range(1, args.repetitions + 1):
                summary, evidence, _ = DeterministicRunner(
                    factory(),
                    clock=LogicalClock(),
                    execution_layer=execution_layer,
                ).run(scenario, repetition=repetition)
                summaries.append(summary)
                events.extend(evidence.events)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = args.output_dir / "events.jsonl"
    jsonl_path.write_text(
        "".join(
            json.dumps(event.as_dict(), sort_keys=True) + "\n" for event in events
        ),
        encoding="utf-8",
    )
    rows = [summary.as_dict() for summary in summaries]
    csv_path = args.output_dir / "runs.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    event_latency_by_key: dict[tuple[str, str], list[float]] = {}
    for event in events:
        event_latency_by_key.setdefault(
            (event.control_model, event.scenario_id), []
        ).append(float(event.authorization["latency_ms"]))
    run_groups: dict[tuple[str, str], list[object]] = {}
    for run_summary in summaries:
        run_groups.setdefault(
            (run_summary.control_model, run_summary.scenario_id), []
        ).append(run_summary)
    comparison = []
    for key, group in sorted(run_groups.items()):
        latencies = event_latency_by_key[key]
        expected = {item.expected_result for item in group}
        actual = {item.actual_result for item in group}
        comparison.append({
            "control_model": key[0],
            "scenario_id": key[1],
            "expected_result": next(iter(expected)) if len(expected) == 1 else "mixed",
            "actual_result": next(iter(actual)) if len(actual) == 1 else "mixed",
            "repetitions": len(group),
            "expectation_mismatches": sum(
                item.expected_result != item.actual_result for item in group
            ),
            "false_allows": sum(item.false_allow for item in group),
            "false_denials": sum(item.false_denial for item in group),
            "median_authorization_latency_ms": median(latencies),
            "min_authorization_latency_ms": min(latencies),
            "max_authorization_latency_ms": max(latencies),
            "median_tool_calls_completed": median(
                item.tool_calls_completed for item in group
            ),
            "median_retries_executed": median(
                item.retries_executed for item in group
            ),
        })
    comparison_path = args.output_dir / "comparison.csv"
    with comparison_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(comparison[0]))
        writer.writeheader()
        writer.writerows(comparison)

    latency_groups: dict[str, list[float]] = {}
    for event in events:
        key = f"{event.control_model}:{event.scenario_id}"
        latency_groups.setdefault(key, []).append(
            float(event.authorization["latency_ms"])
        )
    latency = {
        key: {
            "samples": len(values),
            "median_ms": median(values),
            "min_ms": min(values),
            "max_ms": max(values),
        }
        for key, values in sorted(latency_groups.items())
    }
    summary_path = args.output_dir / "summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "test_date": date.today().isoformat(),
                "warmups_per_model_scenario": 1,
                "measured_repetitions": args.repetitions,
                "scenario_ids": [scenario.scenario_id for scenario in scenarios],
                "control_models": [item[0] for item in factories],
                "local_temporal_disclaimer": (
                    "local temporal specification only; not Dogwood or "
                    "Amazon Bedrock AgentCore enforcement evidence"
                ),
                "runs": len(summaries),
                "events": len(events),
                "authorization_latency": latency,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "events": str(jsonl_path),
        "runs": str(csv_path),
        "comparison": str(comparison_path),
        "summary": str(summary_path),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
