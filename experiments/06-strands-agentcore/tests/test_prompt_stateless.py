from __future__ import annotations

import unittest

from policy_lab import (
    DeterministicRunner,
    LogicalClock,
    PromptOnlyAuthorizer,
    StatelessAuthorizer,
)
from policy_lab.scenarios import load_scenarios


class PromptAndStatelessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scenarios = {
            item.scenario_id: item
            for item in load_scenarios(clock=LogicalClock())
        }

    def test_both_baselines_allow_temporal_violations(self) -> None:
        for authorizer in (PromptOnlyAuthorizer(), StatelessAuthorizer()):
            for scenario_id in ("S02", "S03", "S04", "S05", "S06", "S07"):
                with self.subTest(
                    model=authorizer.control_model, scenario=scenario_id
                ):
                    summary, _, _ = DeterministicRunner(
                        authorizer, clock=LogicalClock()
                    ).run(self.scenarios[scenario_id])
                    self.assertEqual("allow", summary.actual_result)
                    self.assertTrue(summary.false_allow)

    def test_prompt_is_advisory_but_requires_authenticated_caller(self) -> None:
        authorizer = PromptOnlyAuthorizer()
        decision = authorizer.authorize(
            caller_id="unknown",
            session_id=None,
            tool="execute_write",
            arguments={},
            now=LogicalClock().now,
        )
        self.assertFalse(decision.allowed)
        known = authorizer.authorize(
            caller_id="caller-a",
            session_id=None,
            tool="execute_write",
            arguments={},
            now=LogicalClock().now,
        )
        self.assertTrue(known.allowed)
        self.assertIn("advisory", known.reason)

    def test_stateless_permissions_deny_unknown_caller(self) -> None:
        decision = StatelessAuthorizer().authorize(
            caller_id="unknown",
            session_id="any-session",
            tool="lookup_record",
            arguments={"record_id": "record-a"},
            now=LogicalClock().now,
        )
        self.assertFalse(decision.allowed)
        self.assertIn("lacks permission", decision.reason)

    def test_session_and_caller_cases_remain_false_allows_in_baselines(self) -> None:
        for authorizer in (PromptOnlyAuthorizer(), StatelessAuthorizer()):
            for scenario_id in ("S09", "S10"):
                summary, _, _ = DeterministicRunner(
                    authorizer, clock=LogicalClock()
                ).run(self.scenarios[scenario_id])
                self.assertTrue(summary.false_allow)
                self.assertEqual("allow", summary.actual_result)


if __name__ == "__main__":
    unittest.main()
