"""A one-tool, one-proposal agent loop with a fixed authority boundary."""

from __future__ import annotations

from typing import Any

from shared.agent.models import AgentRunResult, ModelSession, ToolDefinition
from shared.contracts import Incident, Proposal
from shared.contracts.models import stable_id
from shared.tools import FixtureRepository, IncidentContextTool


PROPOSAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {"type": "string"},
        "target": {"type": "string"},
        "parameters": {
            "type": "object",
            "properties": {"reason": {"type": "string"}},
            "required": ["reason"],
            "additionalProperties": False,
        },
        "rationale": {"type": "string"},
    },
    "required": ["action", "target", "parameters", "rationale"],
    "additionalProperties": False,
}


def validate_model_proposal(
    incident: Incident,
    draft: dict[str, Any],
    tool_output: dict[str, Any],
) -> Proposal:
    if set(draft) != {"action", "target", "parameters", "rationale"}:
        raise ValueError("model proposal does not match the shared contract")
    if not all(
        isinstance(draft[field], str) and draft[field].strip()
        for field in ("action", "target", "rationale")
    ):
        raise ValueError("model proposal contains an invalid string field")
    parameters = draft["parameters"]
    if not isinstance(parameters, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in parameters.items()
    ):
        raise ValueError("model proposal parameters must be string pairs")
    permitted = tool_output["permitted_remediation"]
    expected = (permitted["action"], permitted["target"], permitted["parameters"])
    proposed = (draft["action"], draft["target"], parameters)
    if proposed != expected:
        raise PermissionError("model proposal exceeds the permitted remediation")
    content = {
        "incident_id": incident.incident_id,
        "action": draft["action"],
        "target": draft["target"],
        "parameters": parameters,
    }
    return Proposal(
        proposal_id=stable_id("prop", content),
        incident_id=incident.incident_id,
        action=draft["action"],
        target=draft["target"],
        parameters=dict(parameters),
        rationale=draft["rationale"].strip(),
    )


class BoundedIncidentAgent:
    """Allow one read-only call, then require one typed permitted proposal."""

    def __init__(self, repository: FixtureRepository, model: ModelSession) -> None:
        self._repository = repository
        self._model = model

    def run(self, incident: Incident) -> AgentRunResult:
        context_tool = IncidentContextTool(self._repository, incident)
        definition = ToolDefinition(
            context_tool.name, context_tool.description, context_tool.parameters
        )
        tool_turn = self._model.request_tool(incident, definition)
        if tool_turn.invocation.name != definition.name:
            raise PermissionError("model requested an unavailable tool")
        tool_output = context_tool.execute(tool_turn.invocation.arguments)
        proposal_turn = self._model.request_proposal(
            tool_turn.invocation, tool_output, PROPOSAL_SCHEMA
        )
        proposal = validate_model_proposal(
            incident, proposal_turn.proposal, tool_output
        )
        return AgentRunResult(
            proposal=proposal,
            provider=self._model.provider,
            model=self._model.model,
            response_ids=(tool_turn.response_id, proposal_turn.response_id),
            invocation=tool_turn.invocation,
            tool_output=tool_output,
            usage=tool_turn.usage + proposal_turn.usage,
        )
