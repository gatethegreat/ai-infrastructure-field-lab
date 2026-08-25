"""Version 1 business contracts with no framework-owned types."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from hashlib import sha256
import json
from typing import Any


CONTRACT_VERSION = "1.0"


def _required(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def stable_id(prefix: str, value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return f"{prefix}_{sha256(encoded).hexdigest()[:16]}"


class ApprovalDecision(StrEnum):
    APPROVE = "approve"
    DENY = "deny"
    REVISE = "revise"
    EXPIRE = "expire"


@dataclass(frozen=True, slots=True)
class Incident:
    incident_id: str
    delivery_id: str
    service: str
    symptom: str
    observed_at: str
    untrusted_notes: str = ""
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Incident:
        if not isinstance(data, dict):
            raise ValueError("incident must be an object")
        return cls(
            incident_id=_required(data.get("incident_id"), "incident_id"),
            delivery_id=_required(data.get("delivery_id"), "delivery_id"),
            service=_required(data.get("service"), "service"),
            symptom=_required(data.get("symptom"), "symptom"),
            observed_at=_required(data.get("observed_at"), "observed_at"),
            untrusted_notes=str(data.get("untrusted_notes", "")),
        )


@dataclass(frozen=True, slots=True)
class InspectionResult:
    service: str
    status: str
    error_rate_percent: float
    source: str


@dataclass(frozen=True, slots=True)
class Proposal:
    proposal_id: str
    incident_id: str
    action: str
    target: str
    parameters: dict[str, str]
    rationale: str

    @property
    def fingerprint(self) -> str:
        return stable_id("proposal", asdict(self))


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    proposal_id: str
    proposal_fingerprint: str
    allowed_decisions: tuple[ApprovalDecision, ...]


@dataclass(frozen=True, slots=True)
class ActionRequest:
    action: str
    target: str
    parameters: dict[str, str]
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class ActionResult:
    action_id: str
    idempotency_key: str
    outcome: str
    simulated: bool
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class FinalResult:
    correlation_id: str
    status: str
    proposal_id: str
    action_result: ActionResult | None


@dataclass(frozen=True, slots=True)
class TimelineEvent:
    sequence: int
    correlation_id: str
    event_type: str
    data: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
