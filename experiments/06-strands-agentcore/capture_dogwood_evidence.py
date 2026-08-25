"""Capture local Dogwood validation and replay evidence from the pinned image."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import platform
from statistics import median
import subprocess
from time import perf_counter_ns


EXPERIMENT = Path(__file__).resolve().parent
POLICIES = EXPERIMENT / "policies" / "dogwood"
DEFAULT_OUTPUT = EXPERIMENT / "evidence" / "local" / "dogwood"
DEFAULT_IMAGE = "ai-field-lab-dogwood:1.0.0-c6237c8"


def docker_mount(path: Path) -> str:
    return f"{path.resolve()}:/lab:ro"


def run_dogwood(image: str, arguments: list[str]) -> dict[str, object]:
    command = [
        "docker",
        "run",
        "--rm",
        "--volume",
        docker_mount(POLICIES),
        image,
        *arguments,
        "--format",
        "json",
    ]
    completed = subprocess.run(
        command, capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Dogwood exited {completed.returncode}: {completed.stderr.strip()}"
        )
    return json.loads(completed.stdout)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--repetitions", type=int, default=10)
    args = parser.parse_args()
    if args.repetitions < 1:
        raise SystemExit("--repetitions must be positive")

    common = [
        "/lab/policies.dw",
        "--policy-schema",
        "/lab/schema.cedarschema",
        "--event-schema",
        "/lab/events.dwschema",
    ]
    validation = run_dogwood(args.image, ["validate", *common])
    expected = json.loads((POLICIES / "expected_verdicts.json").read_text())
    replays: dict[str, object] = {}
    raw_runs: list[dict[str, object]] = []
    for trace_name, expected_verdicts in sorted(expected.items()):
        run_dogwood(
            args.image,
            ["replay", *common, "--trace", f"/lab/traces/{trace_name}"],
        )  # excluded warm-up
        latencies: list[float] = []
        last_result: dict[str, object] | None = None
        for repetition in range(1, args.repetitions + 1):
            started = perf_counter_ns()
            result = run_dogwood(
                args.image,
                ["replay", *common, "--trace", f"/lab/traces/{trace_name}"],
            )
            latency_ms = (perf_counter_ns() - started) / 1_000_000
            actual = [item["verdict"] for item in result["verdicts"]]
            if actual != expected_verdicts:
                raise AssertionError(
                    f"{trace_name}: expected {expected_verdicts}, got {actual}"
                )
            latencies.append(latency_ms)
            last_result = result
            raw_runs.append({
                "schema_version": "1.0",
                "trace": trace_name,
                "repetition": repetition,
                "expected": expected_verdicts,
                "actual": actual,
                "matched": True,
                "end_to_end_replay_latency_ms": latency_ms,
                "execution_layer": "local_dogwood_reference_interpreter_cli",
            })
        assert last_result is not None
        replays[trace_name] = {
            "expected": expected_verdicts,
            "actual": raw_runs[-1]["actual"],
            "matched": True,
            "details": last_result["verdicts"],
            "latency_note": (
                "end-to-end Docker CLI replay latency; not isolated policy-engine latency"
            ),
            "latency_ms": {
                "samples": len(latencies),
                "median": median(latencies),
                "min": min(latencies),
                "max": max(latencies),
            },
        }

    inspect = subprocess.run(
        ["docker", "image", "inspect", args.image],
        capture_output=True,
        text=True,
        check=True,
    )
    image = json.loads(inspect.stdout)[0]
    environment = {
        "schema_version": "1.0",
        "test_date": date.today().isoformat(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "dogwood_commit": (POLICIES / "DOGWOOD_SHA").read_text().strip(),
        "dogwood_cli_version": "1.0.0",
        "image_tag": args.image,
        "image_id": image["Id"],
        "policy_sha256": sha256(POLICIES / "policies.dw"),
        "schema_sha256": sha256(POLICIES / "schema.cedarschema"),
        "event_schema_sha256": sha256(POLICIES / "events.dwschema"),
        "execution_layer": "local_dogwood_reference_interpreter",
        "production_enforcement": False,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "validation.json").write_text(
        json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.output_dir / "replays.json").write_text(
        json.dumps(replays, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.output_dir / "runs.jsonl").write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in raw_runs),
        encoding="utf-8",
    )
    (args.output_dir / "environment.json").write_text(
        json.dumps(environment, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "validation_passed": validation.get("passed"),
                "replays_matched": len(replays),
                "measured_repetitions_per_trace": args.repetitions,
                "output_dir": str(args.output_dir),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
