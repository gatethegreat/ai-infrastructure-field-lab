"""Disposable synthetic state with deterministic identifiers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .contracts import Change, stable_id


@dataclass(frozen=True, slots=True)
class ApprovalRecord:
    record_id: str
    approval_id: str
    expires_at: str
    approved_by: str


@dataclass(frozen=True, slots=True)
class OperationRecord:
    operation_id: str
    record_id: str
    change_id: str
    approval_id: str
    status: str


class SyntheticStore:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.records: dict[str, dict[str, Any]] = {
            f"record-{letter}": {"version": 1, "value": f"synthetic-{letter}"}
            for letter in ("a", "b", "c", "d", "e")
        }
        self.approvals: list[ApprovalRecord] = []
        self.operations: list[OperationRecord] = []
        self._operations_by_change: dict[tuple[str, str], OperationRecord] = {}

    def append_approval(self, approval: ApprovalRecord) -> None:
        self.approvals.append(approval)

    def apply_change(self, record_id: str, change: Change) -> tuple[OperationRecord, bool]:
        key = (record_id, change.change_id)
        existing = self._operations_by_change.get(key)
        if existing is not None:
            return existing, True
        current = self.records[record_id]
        current["version"] += 1
        current["value"] = change.value
        operation = OperationRecord(
            operation_id=stable_id(
                "op", [self.run_id, record_id, change.change_id]
            ),
            record_id=record_id,
            change_id=change.change_id,
            approval_id=change.approval_id,
            status="SUCCEEDED",
        )
        self.operations.append(operation)
        self._operations_by_change[key] = operation
        return operation, False

    def record_failed_change(
        self, record_id: str, change: Change
    ) -> tuple[OperationRecord, bool]:
        """Record a declared failure without mutating the synthetic record."""
        key = (record_id, change.change_id)
        existing = self._operations_by_change.get(key)
        if existing is not None:
            return existing, True
        operation = OperationRecord(
            operation_id=stable_id(
                "op", [self.run_id, record_id, change.change_id]
            ),
            record_id=record_id,
            change_id=change.change_id,
            approval_id=change.approval_id,
            status="FAILED",
        )
        self.operations.append(operation)
        self._operations_by_change[key] = operation
        return operation, False

    def operation(self, operation_id: str) -> dict[str, Any]:
        for operation in self.operations:
            if operation.operation_id == operation_id:
                return asdict(operation)
        raise LookupError("unknown operation_id")
