from __future__ import annotations

import unittest

from policy_lab import DeterministicRunner, LogicalClock, PromptOnlyAuthorizer
from policy_lab.contracts import (
    AuthorizationDecision,
    ControlModel,
    DecisionKind,
)
from policy_lab.scenarios import load_scenarios
from policy_lab.policies import StatelessAuthorizer


class SessionValidationAuthorizer:
    control_model = ControlModel.TEMPORAL
    supported_scopes = frozenset({"authorization"})

    def authorize(self, **kwargs):
        return AuthorizationDecision(
            DecisionKind.ERROR,
            "session-header-validation",
            "invalid policy session ID",
            error_code="VALIDATION_ERROR",
        )

    def reset(self):
        return None

    def observe(self, **kwargs):
        return None


class RunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scenarios = {
            item.scenario_id: item
            for item in load_scenarios(clock=LogicalClock())
        }

    def test_run_ids_and_evidence_are_deterministic(self) -> None:
        first = DeterministicRunner(
            PromptOnlyAuthorizer(), clock=LogicalClock()
        ).run(self.scenarios["S01"])
        second = DeterministicRunner(
            PromptOnlyAuthorizer(), clock=LogicalClock()
        ).run(self.scenarios["S01"])
        first_summary, first_evidence, _ = first
        second_summary, second_evidence, _ = second
        self.assertEqual(first_summary, second_summary)
        self.assertEqual(
            [event.request_id for event in first_evidence.events],
            [event.request_id for event in second_evidence.events],
        )
        self.assertEqual(
            [event.tool_execution["response"] for event in first_evidence.events],
            [event.tool_execution["response"] for event in second_evidence.events],
        )
        self.assertEqual(3, first_summary.tool_calls_completed)
        self.assertEqual(3, first_summary.event_count)

    def test_control_models_receive_the_same_trajectory_hash(self) -> None:
        prompt, _, _ = DeterministicRunner(
            PromptOnlyAuthorizer(), clock=LogicalClock()
        ).run(self.scenarios["S04"])
        stateless, _, _ = DeterministicRunner(
            StatelessAuthorizer(), clock=LogicalClock()
        ).run(self.scenarios["S04"])
        self.assertEqual(prompt.trajectory_hash, stateless.trajectory_hash)

    def test_every_request_records_required_evidence(self) -> None:
        summary, evidence, _ = DeterministicRunner(
            PromptOnlyAuthorizer(), clock=LogicalClock()
        ).run(self.scenarios["S04"])
        self.assertEqual(3, summary.event_count)
        for ordinal, event in enumerate(evidence.events, start=1):
            self.assertEqual(ordinal, event.ordinal)
            self.assertTrue(event.request_id)
            self.assertTrue(event.correlation_id)
            self.assertTrue(event.request_at.endswith("Z"))
            self.assertTrue(event.response_at.endswith("Z"))
            self.assertIn("decision", event.authorization)
            self.assertIn("invoked", event.tool_execution)

    def test_rate_limit_scenario_is_not_folded_into_authorization(self) -> None:
        summary, evidence, _ = DeterministicRunner(
            PromptOnlyAuthorizer(), clock=LogicalClock()
        ).run(self.scenarios["S12"])
        self.assertEqual("not_applicable", summary.actual_result)
        self.assertEqual(0, summary.event_count)
        self.assertEqual((), evidence.events)

    def test_retry_counts_candidate_and_executed_retries(self) -> None:
        summary, evidence, store = DeterministicRunner(
            PromptOnlyAuthorizer(), clock=LogicalClock()
        ).run(self.scenarios["S08"])
        self.assertEqual("tool_error", summary.actual_result)
        self.assertEqual(3, summary.retries_presented)
        self.assertEqual(3, summary.retries_executed)
        self.assertTrue(store.operations)
        self.assertTrue(all(
            operation.status == "FAILED" for operation in store.operations
        ))
        self.assertEqual(1, store.records["record-a"]["version"])
        writes = [event for event in evidence.events if event.tool == "execute_write"]
        self.assertTrue(all(
            event.tool_execution["outcome"] == "error"
            and event.tool_execution["response"]["status"] == "FAILED"
            and event.tool_execution["error_code"] == "DECLARED_TOOL_FAILURE"
            for event in writes
        ))
        self.assertEqual(2, summary.tool_calls_completed)
        self.assertEqual(6, len(evidence.events))

    def test_distinct_consecutive_writes_are_not_retries(self) -> None:
        summary, _, _ = DeterministicRunner(
            PromptOnlyAuthorizer(), clock=LogicalClock()
        ).run(self.scenarios["S06"])
        self.assertEqual(0, summary.retries_presented)
        self.assertEqual(0, summary.retries_executed)

    def test_authorization_errors_are_not_misreported_as_allows(self) -> None:
        summary, evidence, _ = DeterministicRunner(
            SessionValidationAuthorizer(), clock=LogicalClock()
        ).run(self.scenarios["S11"])
        self.assertEqual("validation_error", summary.actual_result)
        self.assertEqual(2, len(evidence.events))
        self.assertTrue(
            all(not event.tool_execution["invoked"] for event in evidence.events)
        )


if __name__ == "__main__":
    unittest.main()
