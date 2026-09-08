from __future__ import annotations

import unittest

from run_local_experiment import aggregate, percentile, response_document


class LocalGatewayExperimentTests(unittest.TestCase):
    def test_percentile_interpolates_small_samples(self) -> None:
        self.assertEqual(2.5, percentile([1.0, 2.0, 3.0, 4.0], 0.5))

    def test_aggregate_uses_expected_public_fields(self) -> None:
        self.assertEqual(
            {"samples": 3, "p50_ms": 2.0, "p95_ms": 2.9, "min_ms": 1.0, "max_ms": 3.0},
            aggregate([1.0, 2.0, 3.0]),
        )

    def test_synthetic_response_preserves_continuation(self) -> None:
        document = response_document(
            {"model": "synthetic-codex", "previous_response_id": "resp_previous"}
        )
        self.assertEqual("resp_previous", document["previous_response_id"])
        self.assertEqual("completed", document["status"])

    def test_synthetic_tool_response_has_no_business_authority(self) -> None:
        document = response_document(
            {
                "model": "synthetic-codex",
                "tools": [{"type": "function", "name": "inspect_service"}],
            }
        )
        output = document["output"]
        self.assertEqual("function_call", output[0]["type"])
        self.assertEqual("inspect_service", output[0]["name"])


if __name__ == "__main__":
    unittest.main()
