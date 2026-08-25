from __future__ import annotations

from types import SimpleNamespace
import unittest

from dapr_agents.hooks import Proceed, RequireApproval

from incident_runtime import IncidentToolRuntime, approval_hook


class IncidentToolRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = IncidentToolRuntime()

    def test_inspection_is_limited_to_incident_service(self) -> None:
        result = self.runtime.inspect("checkout-api")
        self.assertEqual("restart_replica", result["permitted_remediation"]["action"])
        with self.assertRaisesRegex(PermissionError, "different service"):
            self.runtime.inspect("billing-db")

    def test_action_must_match_exact_permitted_remediation(self) -> None:
        with self.assertRaisesRegex(PermissionError, "exceed"):
            self.runtime.execute(
                "delete_service",
                "checkout-api",
                "elevated_503_rate",
                "delivery-synthetic-001",
            )

    def test_simulated_action_is_process_idempotent(self) -> None:
        arguments = (
            "restart_replica",
            "checkout-api/replica-2",
            "elevated_503_rate",
            "delivery-synthetic-001",
        )
        first = self.runtime.execute(*arguments)
        second = self.runtime.execute(*arguments)
        self.assertFalse(first["replayed"])
        self.assertTrue(second["replayed"])
        self.assertEqual(1, self.runtime.executor.effect_count)

    def test_only_action_tool_requires_approval(self) -> None:
        action = approval_hook(SimpleNamespace(step_name="ExecuteRemediation"))
        inspection = approval_hook(SimpleNamespace(step_name="InspectIncidentContext"))
        self.assertIsInstance(action, RequireApproval)
        self.assertIsInstance(inspection, Proceed)


if __name__ == "__main__":
    unittest.main()
