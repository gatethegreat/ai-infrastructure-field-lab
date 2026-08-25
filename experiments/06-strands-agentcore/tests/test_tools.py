from __future__ import annotations

import unittest

from policy_lab.store import SyntheticStore
from policy_lab.tools import SyntheticTools


class SyntheticToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = SyntheticStore("run-test")
        self.tools = SyntheticTools(self.store)

    def test_lookup_and_approval_are_entirely_synthetic(self) -> None:
        lookup = self.tools.lookup_record("record-a")
        approval = self.tools.record_human_approval(
            "record-a", "approval-1", "2026-08-24T16:15:00Z"
        )
        self.assertTrue(lookup["found"])
        self.assertTrue(approval["approved"])
        self.assertEqual("synthetic-human-approver", approval["approved_by"])

    def test_write_is_deterministic_and_idempotent_by_change_id(self) -> None:
        change = {
            "change_id": "change-1",
            "approval_id": "approval-1",
            "value": "new-synthetic-value",
        }
        first = self.tools.execute_write("record-a", change)
        second = self.tools.execute_write("record-a", change)
        self.assertFalse(first["replayed"])
        self.assertTrue(second["replayed"])
        self.assertEqual(first["operation_id"], second["operation_id"])
        self.assertEqual(1, len(self.store.operations))
        status = self.tools.get_operation_status(first["operation_id"])
        self.assertEqual("SUCCEEDED", status["status"])

    def test_injected_failure_has_no_effect(self) -> None:
        before = dict(self.store.records["record-a"])
        result = self.tools.execute_write(
            "record-a",
            {
                "change_id": "change-fail",
                "approval_id": "approval-1",
                "value": "never-written",
                "force_error": True,
            },
        )
        self.assertEqual("FAILED", result["status"])
        self.assertFalse(result["replayed"])
        self.assertEqual(before, self.store.records["record-a"])
        self.assertEqual("FAILED", self.tools.get_operation_status(
            result["operation_id"]
        )["status"])

    def test_approval_expiry_requires_a_timezone(self) -> None:
        with self.assertRaisesRegex(ValueError, "timezone"):
            self.tools.record_human_approval(
                "record-a", "approval-naive", "2026-08-24T16:15:00"
            )


if __name__ == "__main__":
    unittest.main()
