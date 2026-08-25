from __future__ import annotations

import unittest

from policy_lab import (
    DeterministicRunner,
    LocalTemporalSpecificationAuthorizer,
    LogicalClock,
)
from policy_lab.scenarios import load_scenarios


class LocalTemporalSpecificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scenarios = {
            scenario.scenario_id: scenario
            for scenario in load_scenarios(clock=LogicalClock())
        }

    def run_scenario(self, scenario_id: str):
        return DeterministicRunner(
            LocalTemporalSpecificationAuthorizer(),
            clock=LogicalClock(),
            execution_layer="local_spec",
        ).run(self.scenarios[scenario_id])

    def test_all_authorization_scenarios_match_expected_outcomes(self) -> None:
        expected = {
            "S01": "allow",
            "S02": "deny",
            "S03": "deny",
            "S04": "deny",
            "S05": "deny",
            "S06": "deny",
            "S07": "deny",
            "S08": "mixed",
            "S09": "mixed",
            "S10": "mixed",
            "S11": "validation_error",
        }
        for scenario_id, outcome in expected.items():
            with self.subTest(scenario=scenario_id):
                summary, evidence, _ = self.run_scenario(scenario_id)
                self.assertEqual(outcome, summary.expected_result)
                self.assertEqual(outcome, summary.actual_result)
                self.assertFalse(summary.false_allow)
                self.assertFalse(summary.false_denial)
                self.assertTrue(
                    all(event.execution_layer == "local_spec" for event in evidence.events)
                )
                self.assertTrue(
                    all(
                        "specification" in event.authorization["policy_id"]
                        for event in evidence.events
                    )
                )
                self.assertTrue(
                    all(
                        "dogwood" not in event.authorization["policy_id"].lower()
                        for event in evidence.events
                    )
                )

    def test_denials_stop_before_tool_and_effect(self) -> None:
        expected_operations = {
            "S02": 0,
            "S03": 0,
            "S04": 0,
            "S05": 0,
            "S06": 1,
            "S07": 3,
            "S08": 0,
            "S09": 4,
            "S10": 1,
            "S11": 0,
        }
        for scenario_id, operation_count in expected_operations.items():
            with self.subTest(scenario=scenario_id):
                _, evidence, store = self.run_scenario(scenario_id)
                for event in evidence.events:
                    if event.authorization["decision"] != "allow":
                        self.assertFalse(event.tool_execution["invoked"])
                self.assertEqual(operation_count, sum(
                    operation.status == "SUCCEEDED"
                    for operation in store.operations
                ))

    def test_retry_limit_allows_three_failures_then_denies_fourth(self) -> None:
        summary, evidence, _ = self.run_scenario("S08")
        attempts = [
            event for event in evidence.events if event.tool == "execute_write"
        ]
        self.assertEqual([True, True, True, False], [
            event.tool_execution["invoked"] for event in attempts
        ])
        self.assertEqual(3, summary.retries_presented)
        self.assertEqual(2, summary.retries_executed)

    def test_failed_write_does_not_consume_approval_but_success_does(self) -> None:
        authorizer = LocalTemporalSpecificationAuthorizer()
        now = LogicalClock().now
        session = "success-only-consumption"
        authorizer.authorize(
            caller_id="caller-a", session_id=session, tool="lookup_record",
            arguments={"record_id": "record-a"}, now=now
        )
        authorizer.observe(
            caller_id="caller-a", session_id=session, tool="lookup_record",
            arguments={"record_id": "record-a"}, outcome="success",
            response={"record_id": "record-a"}, error_code=None
        )
        authorizer.observe(
            caller_id="caller-a", session_id=session,
            tool="record_human_approval",
            arguments={"record_id": "record-a"}, outcome="success",
            response={
                "record_id": "record-a", "approval_id": "approval-one",
                "approved": True, "expires_at": "2026-08-24T16:15:00Z"
            }, error_code=None
        )
        arguments = {
            "record_id": "record-a",
            "change": {
                "change_id": "change-one", "approval_id": "approval-one",
                "value": "synthetic"
            },
        }
        first = authorizer.authorize(
            caller_id="caller-a", session_id=session, tool="execute_write",
            arguments=arguments, now=now
        )
        self.assertTrue(first.allowed)
        authorizer.observe(
            caller_id="caller-a", session_id=session, tool="execute_write",
            arguments=arguments, outcome="error", response=None,
            error_code="RuntimeError"
        )
        retry = authorizer.authorize(
            caller_id="caller-a", session_id=session, tool="execute_write",
            arguments=arguments, now=now
        )
        self.assertTrue(retry.allowed)
        authorizer.observe(
            caller_id="caller-a", session_id=session, tool="execute_write",
            arguments=arguments, outcome="success",
            response={"operation_id": "op-synthetic"}, error_code=None
        )
        after_success = authorizer.authorize(
            caller_id="caller-a", session_id=session, tool="execute_write",
            arguments={
                "record_id": "record-a",
                "change": {
                    "change_id": "change-two", "approval_id": "approval-one",
                    "value": "synthetic-two"
                },
            },
            now=now,
        )
        self.assertFalse(after_success.allowed)
        self.assertIn("consumed", after_success.reason)

    def test_authorization_latency_is_measured(self) -> None:
        _, evidence, _ = self.run_scenario("S01")
        for event in evidence.events:
            self.assertGreaterEqual(event.authorization["latency_ms"], 0.0)
            self.assertGreaterEqual(event.latency_ms, event.authorization["latency_ms"])

    def test_retry_history_is_correlated_by_approval_id(self) -> None:
        authorizer = LocalTemporalSpecificationAuthorizer()
        now = LogicalClock().now
        session = "approval-retry-key"
        authorizer.authorize(
            caller_id="caller-a", session_id=session, tool="lookup_record",
            arguments={"record_id": "record-a"}, now=now,
        )
        authorizer.observe(
            caller_id="caller-a", session_id=session, tool="lookup_record",
            arguments={"record_id": "record-a"}, outcome="success",
            response={"record_id": "record-a"}, error_code=None,
        )
        authorizer.observe(
            caller_id="caller-a", session_id=session,
            tool="record_human_approval",
            arguments={"record_id": "record-a"}, outcome="success",
            response={
                "record_id": "record-a", "approval_id": "approval-shared",
                "approved": True, "expires_at": "2026-08-24T16:15:00Z",
            }, error_code=None,
        )
        for attempt in range(3):
            arguments = {
                "record_id": "record-a",
                "change": {
                    "change_id": f"change-{attempt}",
                    "approval_id": "approval-shared", "value": "synthetic",
                },
            }
            self.assertTrue(authorizer.authorize(
                caller_id="caller-a", session_id=session,
                tool="execute_write", arguments=arguments, now=now,
            ).allowed)
            authorizer.observe(
                caller_id="caller-a", session_id=session,
                tool="execute_write", arguments=arguments, outcome="error",
                response={"status": "FAILED"},
                error_code="DECLARED_TOOL_FAILURE",
            )
        fourth = authorizer.authorize(
            caller_id="caller-a", session_id=session, tool="execute_write",
            arguments={
                "record_id": "record-a",
                "change": {
                    "change_id": "change-four",
                    "approval_id": "approval-shared", "value": "synthetic",
                },
            }, now=now,
        )
        self.assertFalse(fourth.allowed)
        self.assertIn("approval failure limit", fourth.reason)


if __name__ == "__main__":
    unittest.main()
