"""Trusted synthetic tools for the shared incident scenario."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from shared.contracts import ActionRequest, ActionResult, Incident, InspectionResult
from shared.contracts.models import stable_id


class FixtureRepository:
    """Read-only access to synthetic runbooks and observations."""

    def __init__(self, fixture: dict[str, Any]) -> None:
        self._fixture = fixture

    def runbook_for(self, service: str) -> dict[str, Any]:
        try:
            return dict(self._fixture["runbooks"][service])
        except KeyError as error:
            raise LookupError(f"no runbook for {service}") from error

    def inspect(self, service: str) -> InspectionResult:
        try:
            value = self._fixture["inspections"][service]
        except KeyError as error:
            raise LookupError(f"no inspection fixture for {service}") from error
        return InspectionResult(service=service, **value)


class IncidentContextTool:
    """Expose trusted inspection and permitted remediation data read-only."""

    name = "inspect_incident_context"
    description = (
        "Read synthetic inspection evidence and the permitted runbook remediation "
        "for one service. This tool never changes state."
    )
    parameters = {
        "type": "object",
        "properties": {
            "service": {
                "type": "string",
                "description": "Exact service identifier from the incident.",
            }
        },
        "required": ["service"],
        "additionalProperties": False,
    }

    def __init__(self, repository: FixtureRepository, incident: Incident) -> None:
        self._repository = repository
        self._incident = incident

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if set(arguments) != {"service"}:
            raise ValueError("inspection requires exactly the service argument")
        service = arguments["service"]
        if service != self._incident.service:
            raise PermissionError("tool call cannot inspect a different service")
        runbook = self._repository.runbook_for(service)
        inspection = self._repository.inspect(service)
        return {
            "inspection": asdict(inspection),
            "permitted_remediation": {
                "runbook_id": runbook["runbook_id"],
                "threshold_percent": runbook["threshold_percent"],
                "action": runbook["action"],
                "target": runbook["target"],
                "parameters": dict(runbook["parameters"]),
            },
        }


class SimulatedActionExecutor:
    """Keep authoritative simulated effects idempotent for this process."""

    def __init__(self) -> None:
        self._results: dict[str, ActionResult] = {}

    @property
    def effect_count(self) -> int:
        return len(self._results)

    def execute(self, request: ActionRequest) -> ActionResult:
        existing = self._results.get(request.idempotency_key)
        if existing:
            return ActionResult(**{**asdict(existing), "replayed": True})
        result = ActionResult(
            action_id=stable_id("action", asdict(request)),
            idempotency_key=request.idempotency_key,
            outcome=f"simulated {request.action} on {request.target}",
            simulated=True,
        )
        self._results[request.idempotency_key] = result
        return result
