import csv
import json
import unittest
from pathlib import Path


EXPERIMENT = Path(__file__).resolve().parents[1]
SPEC = EXPERIMENT / "evidence" / "local" / "specification"
DOGWOOD = EXPERIMENT / "evidence" / "local" / "dogwood"
CLOUD = EXPERIMENT / "evidence" / "cloud" / "redacted"


class LocalEvidenceTests(unittest.TestCase):
    def test_specification_evidence_has_ten_runs_and_no_expectation_drift(self):
        summary = json.loads((SPEC / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["measured_repetitions"], 10)
        self.assertEqual(summary["runs"], 330)
        self.assertEqual(summary["events"], 1650)
        self.assertIn("not Dogwood", summary["local_temporal_disclaimer"])
        with (SPEC / "comparison.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 33)
        self.assertTrue(all(row["expectation_mismatches"] == "0" for row in rows))
        temporal = [row for row in rows if row["control_model"] == "temporal_policy"]
        self.assertTrue(all(row["false_allows"] == "0" for row in temporal))

    def test_dogwood_reference_evidence_matches_all_replay_oracles(self):
        validation = json.loads((DOGWOOD / "validation.json").read_text())
        replays = json.loads((DOGWOOD / "replays.json").read_text())
        environment = json.loads((DOGWOOD / "environment.json").read_text())
        self.assertTrue(validation["passed"])
        self.assertTrue(validation["passed_without_warnings"])
        self.assertEqual(len(replays), 9)
        self.assertTrue(all(item["matched"] for item in replays.values()))
        self.assertTrue(all(item["latency_ms"]["samples"] == 10 for item in replays.values()))
        self.assertFalse(environment["production_enforcement"])
        self.assertEqual(
            environment["dogwood_commit"],
            "c6237c88099b3f492ecc5fcee42df06a19224b97",
        )

    def test_accepted_managed_evidence_keeps_rate_limit_contamination_explicit(self):
        with (CLOUD / "accepted-managed-comparison.csv").open(
            encoding="utf-8", newline=""
        ) as handle:
            comparison = list(csv.DictReader(handle))
        authorization = [
            row for row in comparison if row["layer"] == "agentcore_temporal"
        ]
        self.assertEqual(sum(int(row["repetitions"]) for row in authorization), 110)
        self.assertTrue(all(row["expectation_mismatches"] == "0" for row in authorization))
        single_dimension = next(
            row for row in comparison if row["source_batch"] == "e9a8a5293522"
        )
        self.assertEqual(single_dimension["actual_result"], "inconclusive")
        self.assertIn("contamination", single_dimension["evidence_status"])
        with (
            CLOUD / "e9a8a5293522" / "gateway_rate_limit-runs.csv"
        ).open(encoding="utf-8", newline="") as handle:
            single_dimension_runs = list(csv.DictReader(handle))
        self.assertEqual(single_dimension_runs[0]["actual_result"], "inconclusive")
        self.assertEqual(single_dimension_runs[0]["tool_calls_completed"], "5")

        with (CLOUD / "accepted-managed-measurement-availability.csv").open(
            encoding="utf-8-sig", newline=""
        ) as handle:
            availability = list(csv.DictReader(handle))
        self.assertEqual(len(availability), 110)
        self.assertTrue(all(
            not row["added_authorization_latency_ms"]
            and "not configured" in row["added_authorization_latency_reason"]
            and not row["policy_responsible"]
            and "no determining-policy span" in row["policy_responsible_reason"]
            for row in availability
        ))

    def test_retry_evidence_preserves_managed_and_local_change_id_boundary(self):
        events_path = CLOUD / "8d21c017f03f" / "managed_temporal-events.jsonl"
        managed_events = [
            json.loads(line)
            for line in events_path.read_text(encoding="utf-8").splitlines()
        ]
        writes_by_repetition = {}
        for event in managed_events:
            if event["tool"] == "execute_write":
                writes_by_repetition.setdefault(event["repetition"], []).append(event)

        self.assertEqual(len(writes_by_repetition), 10)
        for writes in writes_by_repetition.values():
            self.assertEqual(len(writes), 4)
            self.assertEqual(
                len({write["arguments"]["change"]["change_id"] for write in writes}),
                1,
            )
            self.assertEqual(
                len({write["arguments"]["change"]["approval_id"] for write in writes}),
                1,
            )
            self.assertEqual(
                [write["authorization"]["decision"] for write in writes],
                ["allow", "allow", "allow", "deny"],
            )

        dogwood_trace = (
            EXPERIMENT / "policies" / "dogwood" / "traces" / "06_retry_cap.log"
        ).read_text(encoding="utf-8")
        for change_id in (
            "change-initial",
            "change-retry-1",
            "change-retry-2",
            "change-retry-3",
        ):
            self.assertIn(f'change_id: "{change_id}"', dogwood_trace)

        infrastructure_readme = (
            EXPERIMENT / "infrastructure" / "README.md"
        ).read_text(encoding="utf-8")
        normalized_infrastructure_readme = " ".join(infrastructure_readme.split())
        self.assertIn(
            "local Dogwood retry trace deliberately uses distinct change IDs",
            normalized_infrastructure_readme,
        )
        self.assertIn(
            "accepted managed S08 trajectory instead held both approval ID and "
            "change ID constant",
            normalized_infrastructure_readme,
        )


if __name__ == "__main__":
    unittest.main()
