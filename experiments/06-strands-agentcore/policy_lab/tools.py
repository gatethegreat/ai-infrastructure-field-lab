"""Four trusted synthetic tools used by every control model."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, Callable

from .contracts import Change, require_string
from .store import ApprovalRecord, SyntheticStore


TOOL_NAMES = (
    "lookup_record",
    "record_human_approval",
    "execute_write",
    "get_operation_status",
)


class SyntheticTools:
    def __init__(self, store: SyntheticStore) -> None:
        self.store = store
        self._handlers: dict[str, Callable[..., dict[str, Any]]] = {
            "lookup_record": self.lookup_record,
            "record_human_approval": self.record_human_approval,
            "execute_write": self.execute_write,
            "get_operation_status": self.get_operation_status,
        }

    def invoke(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            handler = self._handlers[tool]
        except KeyError as error:
            raise LookupError(f"unknown tool: {tool}") from error
        if not isinstance(arguments, dict):
            raise ValueError("tool arguments must be an object")
        return handler(**arguments)

    def lookup_record(self, record_id: str) -> dict[str, Any]:
        record_id = require_string(record_id, "record_id")
        try:
            record = self.store.records[record_id]
        except KeyError as error:
            raise LookupError("unknown record_id") from error
        return {"record_id": record_id, "found": True, **record}

    def record_human_approval(
        self, record_id: str, approval_id: str, expires_at: str
    ) -> dict[str, Any]:
        record_id = require_string(record_id, "record_id")
        approval_id = require_string(approval_id, "approval_id")
        expires_at = require_string(expires_at, "expires_at")
        if record_id not in self.store.records:
            raise LookupError("unknown record_id")
        try:
            parsed_expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("expires_at must be ISO-8601") from error
        if parsed_expiry.tzinfo is None:
            raise ValueError("expires_at must include a timezone")
        approval = ApprovalRecord(
            record_id=record_id,
            approval_id=approval_id,
            expires_at=expires_at,
            approved_by="synthetic-human-approver",
        )
        self.store.append_approval(approval)
        return {**asdict(approval), "approved": True}

    def execute_write(self, record_id: str, change: dict[str, Any]) -> dict[str, Any]:
        record_id = require_string(record_id, "record_id")
        if record_id not in self.store.records:
            raise LookupError("unknown record_id")
        parsed = Change.from_dict(change)
        if parsed.force_error:
            operation, replayed = self.store.record_failed_change(record_id, parsed)
        else:
            operation, replayed = self.store.apply_change(record_id, parsed)
        return {**asdict(operation), "replayed": replayed}

    def get_operation_status(self, operation_id: str) -> dict[str, Any]:
        operation_id = require_string(operation_id, "operation_id")
        return self.store.operation(operation_id)
