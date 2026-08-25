from __future__ import annotations

import unittest

from policy_lab.clock import LogicalClock
from policy_lab.contracts import Change, ControlModel
from policy_lab.scenarios import load_scenarios


class ContractTests(unittest.TestCase):
    def test_change_is_typed_and_rejects_extra_fields(self) -> None:
        change = Change.from_dict(
            {"change_id": "c-1", "approval_id": "a-1", "value": "synthetic"}
        )
        self.assertEqual("c-1", change.change_id)
        with self.assertRaisesRegex(ValueError, "unsupported"):
            Change.from_dict(
                {
                    "change_id": "c-1",
                    "approval_id": "a-1",
                    "value": "synthetic",
                    "secret": "not-allowed",
                }
            )

    def test_catalog_contains_twelve_unique_scenarios_and_full_matrix(self) -> None:
        scenarios = load_scenarios(clock=LogicalClock())
        self.assertEqual(12, len(scenarios))
        self.assertEqual(12, len({item.scenario_id for item in scenarios}))
        expected_models = set(ControlModel)
        for scenario in scenarios:
            self.assertEqual(expected_models, set(scenario.expectations))
            self.assertEqual(64, len(scenario.trajectory_hash))

    def test_catalog_resolution_is_reproducible(self) -> None:
        first = load_scenarios(clock=LogicalClock())
        second = load_scenarios(clock=LogicalClock())
        self.assertEqual(
            [scenario.trajectory_hash for scenario in first],
            [scenario.trajectory_hash for scenario in second],
        )


if __name__ == "__main__":
    unittest.main()
