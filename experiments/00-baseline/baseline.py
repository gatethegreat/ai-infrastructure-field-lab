"""Ordinary Python baseline: no agent framework, workflow engine, or database."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from shared.contracts import (
    ActionRequest,
    ApprovalDecision,
    ApprovalRequest,
    FinalResult,
    Incident,
    Proposal,
    TimelineEvent,
)
from shared.contracts.models import stable_id
from shared.tools import FixtureRepository, SimulatedActionExecutor


class DeterministicFakeModel:
    """Produces one typed proposal from trusted runbook and inspection data."""

    def propose(
        self,
        incident: Incident,
        runbook: dict[str, Any],
        inspection: InspectionResult,
    ) -> Proposal:
        if inspection.error_rate_percent < float(runbook["threshold_percent"]):
            raise ValueError("inspection does not meet the remediation threshold")
        content = {
            "incident_id": incident.incident_id,
            "action": runbook["action"],
            "target": runbook["target"],
            "parameters": runbook["parameters"],
        }
        return Proposal(
            proposal_id=stable_id("prop", content),
            incident_id=incident.incident_id,
            action=runbook["action"],
            target=runbook["target"],
            parameters=dict(runbook["parameters"]),
            rationale=(
                f"{inspection.source} reports {inspection.error_rate_percent}% errors; "
                f"runbook threshold is {runbook['threshold_percent']}%."
            ),
        )


class BaselineExecution:
    def __init__(
        self,
        fixture: dict[str, Any],
        executor: SimulatedActionExecutor | None = None,
    ) -> None:
        self.repository = FixtureRepository(fixture)
        self.model = DeterministicFakeModel()
        self.executor = executor or SimulatedActionExecutor()
        self.events: list[TimelineEvent] = []
        self.incident: Incident | None = None
        self.proposal: Proposal | None = None
        self.approval: ApprovalRequest | None = None
        self.correlation_id = ""

    def _record(self, event_type: str, **data: Any) -> None:
        self.events.append(
            TimelineEvent(len(self.events) + 1, self.correlation_id, event_type, data)
        )

    def start(self, raw_incident: dict[str, Any]) -> ApprovalRequest:
        self.incident = Incident.from_dict(raw_incident)
        self.correlation_id = stable_id("corr", self.incident.delivery_id)
        self._record("incident_validated", incident_id=self.incident.incident_id)
        runbook = self.repository.runbook_for(self.incident.service)
        self._record("runbook_retrieved", runbook_id=runbook["runbook_id"])
        inspection = self.repository.inspect(self.incident.service)
        self._record("inspection_completed", **asdict(inspection))
        self.proposal = self.model.propose(self.incident, runbook, inspection)
        self._record("proposal_created", **asdict(self.proposal))
        self.approval = ApprovalRequest(
            proposal_id=self.proposal.proposal_id,
            proposal_fingerprint=self.proposal.fingerprint,
            allowed_decisions=tuple(ApprovalDecision),
        )
        self._record(
            "approval_requested",
            proposal_id=self.approval.proposal_id,
            proposal_fingerprint=self.approval.proposal_fingerprint,
        )
        return self.approval

    def decide(
        self,
        decision: ApprovalDecision,
        proposal_fingerprint: str,
    ) -> FinalResult:
        if not self.proposal or not self.approval:
            raise RuntimeError("start must be called before decide")
        if proposal_fingerprint != self.approval.proposal_fingerprint:
            raise ValueError("approval does not match the exact proposed action")
        self._record("approval_decided", decision=decision.value)
        if decision != ApprovalDecision.APPROVE:
            status = {
                ApprovalDecision.DENY: "denied",
                ApprovalDecision.REVISE: "revision_requested",
                ApprovalDecision.EXPIRE: "expired",
            }[decision]
            result = FinalResult(
                self.correlation_id, status, self.proposal.proposal_id, None
            )
            self._record("execution_finished", status=status, action_executed=False)
            return result
        action = ActionRequest(
            action=self.proposal.action,
            target=self.proposal.target,
            parameters=self.proposal.parameters,
            idempotency_key=stable_id(
                "idem", [self.incident.delivery_id, self.proposal.fingerprint]
            ),
        )
        action_result = self.executor.execute(action)
        self._record("action_completed", **asdict(action_result))
        result = FinalResult(
            self.correlation_id, "completed", self.proposal.proposal_id, action_result
        )
        self._record("execution_finished", status="completed", action_executed=True)
        return result
