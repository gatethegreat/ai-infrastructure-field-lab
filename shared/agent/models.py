"""Provider-neutral ports used by the bounded live-agent loop."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from shared.contracts import Incident, Proposal


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolInvocation:
    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
            self.total_tokens + other.total_tokens,
        )


@dataclass(frozen=True, slots=True)
class ModelToolTurn:
    response_id: str
    invocation: ToolInvocation
    usage: TokenUsage


@dataclass(frozen=True, slots=True)
class ModelProposalTurn:
    response_id: str
    proposal: dict[str, Any]
    usage: TokenUsage


class ModelSession(Protocol):
    provider: str
    model: str

    def request_tool(
        self, incident: Incident, tool: ToolDefinition
    ) -> ModelToolTurn: ...

    def request_proposal(
        self,
        invocation: ToolInvocation,
        tool_output: dict[str, Any],
        proposal_schema: dict[str, Any],
    ) -> ModelProposalTurn: ...


@dataclass(frozen=True, slots=True)
class AgentRunResult:
    proposal: Proposal
    provider: str
    model: str
    response_ids: tuple[str, str]
    invocation: ToolInvocation
    tool_output: dict[str, Any]
    usage: TokenUsage
