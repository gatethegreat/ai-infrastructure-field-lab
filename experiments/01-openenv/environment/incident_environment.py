"""OpenEnv v0.4.1 episode adapter for the shared incident contracts."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Literal, TypeAlias

from openenv.core.env_server import Action, Environment, Observation, State
from pydantic import Field

from shared.agent import validate_model_proposal
from shared.contracts import (
    ActionRequest,
    ApprovalDecision,
    ApprovalRequest,
    Incident,
    Proposal,
)
from shared.contracts.models import stable_id
from shared.tools import (
    FixtureRepository,
    IncidentContextTool,
    SimulatedActionExecutor,
)


Phase: TypeAlias = Literal[
    "awaiting_inspection",
    "awaiting_proposal",
    "awaiting_approval",
    "approved",
    "denied",
    "expired",
    "completed",
]


class InspectContextAction(Action):
    service: str


class SubmitProposalAction(Action):
    action: str
    target: str
    parameters: dict[str, str]
    rationale: str


class DecideApprovalAction(Action):
    decision: Literal["approve", "deny", "revise", "expire"]
    proposal_fingerprint: str


class ExecuteApprovedAction(Action):
    proposal_fingerprint: str


IncidentAction: TypeAlias = (
    InspectContextAction
    | SubmitProposalAction
    | DecideApprovalAction
    | ExecuteApprovedAction
)


class IncidentObservation(Observation):
    phase: Phase
    message: str
    incident: dict[str, Any] | None = None
    context: dict[str, Any] | None = None
    proposal: dict[str, Any] | None = None
    approval_required: bool = False
    action_result: dict[str, Any] | None = None


class IncidentState(State):
    phase: Phase = "awaiting_inspection"
    incident_id: str
    proposal_id: str | None = None
    proposal_fingerprint: str | None = None
    decision: str | None = None
    cumulative_reward: float = 0.0
    authoritative_effect_count: int = 0
    history: list[str] = Field(default_factory=list)


class IncidentEnvironment(
    Environment[IncidentAction, IncidentObservation, IncidentState]
):
    """Model the incident as a local OpenEnv episode with no database."""

    def __init__(
        self,
        fixture: dict[str, Any],
        executor: SimulatedActionExecutor | None = None,
    ) -> None:
        super().__init__()
        self._fixture = fixture
        self._incident = Incident.from_dict(fixture["incident"])
        self._repository = FixtureRepository(fixture)
        self._executor = executor or SimulatedActionExecutor()
        self._context: dict[str, Any] | None = None
        self._proposal: Proposal | None = None
        self._approval: ApprovalRequest | None = None
        self._reset_count = 0
        self._state = IncidentState(incident_id=self._incident.incident_id)

    @property
    def state(self) -> IncidentState:
        return self._state

    def reset(
        self,
        seed: int | None = None,
        episode_id: str | None = None,
        **kwargs: Any,
    ) -> IncidentObservation:
        del seed, kwargs
        self._reset_count += 1
        self._context = None
        self._proposal = None
        self._approval = None
        self._state = IncidentState(
            episode_id=episode_id
            or stable_id(
                "episode", [self._incident.delivery_id, self._reset_count]
            ),
            incident_id=self._incident.incident_id,
            authoritative_effect_count=self._executor.effect_count,
            history=["reset"],
        )
        return self._observe(
            "incident ready for inspection",
            reward=0.0,
            incident=asdict(self._incident),
        )

    def _observe(
        self,
        message: str,
        reward: float,
        *,
        done: bool = False,
        incident: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        proposal: dict[str, Any] | None = None,
        approval_required: bool = False,
        action_result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> IncidentObservation:
        self._state.cumulative_reward += reward
        self._state.authoritative_effect_count = self._executor.effect_count
        metadata = {"error": error} if error else {}
        return IncidentObservation(
            phase=self._state.phase,
            message=message,
            incident=incident,
            context=context,
            proposal=proposal,
            approval_required=approval_required,
            action_result=action_result,
            reward=reward,
            done=done,
            metadata=metadata,
        )

    def _reject(self, message: str) -> IncidentObservation:
        self._state.history.append(f"rejected:{message}")
        return self._observe(message, reward=-1.0, error=message)

    def step(
        self,
        action: IncidentAction,
        timeout_s: float | None = None,
        **kwargs: Any,
    ) -> IncidentObservation:
        del timeout_s, kwargs
        self._state.step_count += 1
        try:
            if isinstance(action, InspectContextAction):
                return self._inspect(action)
            if isinstance(action, SubmitProposalAction):
                return self._submit(action)
            if isinstance(action, DecideApprovalAction):
                return self._decide(action)
            if isinstance(action, ExecuteApprovedAction):
                return self._execute(action)
            return self._reject("unsupported action type")
        except (LookupError, PermissionError, RuntimeError, ValueError) as error:
            return self._reject(str(error))

    def _inspect(self, action: InspectContextAction) -> IncidentObservation:
        if self._state.phase != "awaiting_inspection":
            raise RuntimeError("inspection is not allowed in the current phase")
        tool = IncidentContextTool(self._repository, self._incident)
        self._context = tool.execute({"service": action.service})
        self._state.phase = "awaiting_proposal"
        self._state.history.append("context_inspected")
        return self._observe(
            "trusted context inspected", reward=0.1, context=self._context
        )

    def _submit(self, action: SubmitProposalAction) -> IncidentObservation:
        if self._state.phase != "awaiting_proposal" or self._context is None:
            raise RuntimeError("proposal is not allowed in the current phase")
        draft = action.model_dump(exclude={"metadata"})
        self._proposal = validate_model_proposal(
            self._incident, draft, self._context
        )
        self._approval = ApprovalRequest(
            proposal_id=self._proposal.proposal_id,
            proposal_fingerprint=self._proposal.fingerprint,
            allowed_decisions=tuple(ApprovalDecision),
        )
        self._state.phase = "awaiting_approval"
        self._state.proposal_id = self._proposal.proposal_id
        self._state.proposal_fingerprint = self._proposal.fingerprint
        self._state.history.append("proposal_submitted")
        return self._observe(
            "proposal requires approval",
            reward=0.2,
            proposal=asdict(self._proposal),
            approval_required=True,
        )

    def _decide(self, action: DecideApprovalAction) -> IncidentObservation:
        if self._state.phase != "awaiting_approval" or self._approval is None:
            raise RuntimeError("approval decision is not allowed in the current phase")
        if action.proposal_fingerprint != self._approval.proposal_fingerprint:
            raise PermissionError("approval does not match the exact proposal")
        decision = ApprovalDecision(action.decision)
        self._state.decision = decision.value
        self._state.history.append(f"approval:{decision.value}")
        if decision == ApprovalDecision.APPROVE:
            self._state.phase = "approved"
            return self._observe("proposal approved", reward=0.2)
        if decision == ApprovalDecision.REVISE:
            self._proposal = None
            self._approval = None
            self._state.proposal_id = None
            self._state.proposal_fingerprint = None
            self._state.phase = "awaiting_proposal"
            return self._observe("proposal revision requested", reward=0.0)
        self._state.phase = (
            "denied" if decision == ApprovalDecision.DENY else "expired"
        )
        return self._observe(
            f"proposal {self._state.phase}", reward=0.5, done=True
        )

    def _execute(self, action: ExecuteApprovedAction) -> IncidentObservation:
        if self._state.phase not in {"approved", "completed"}:
            raise RuntimeError("execution requires approval")
        if self._proposal is None or self._approval is None:
            raise RuntimeError("approved proposal is unavailable")
        if action.proposal_fingerprint != self._approval.proposal_fingerprint:
            raise PermissionError("execution does not match the approved proposal")
        request = ActionRequest(
            action=self._proposal.action,
            target=self._proposal.target,
            parameters=self._proposal.parameters,
            idempotency_key=stable_id(
                "idem",
                [self._incident.delivery_id, self._proposal.fingerprint],
            ),
        )
        result = self._executor.execute(request)
        self._state.phase = "completed"
        self._state.history.append(
            "execution_replayed" if result.replayed else "execution_completed"
        )
        return self._observe(
            (
                "simulated action replayed"
                if result.replayed
                else "simulated action completed"
            ),
            reward=0.0 if result.replayed else 1.0,
            done=True,
            action_result=asdict(result),
        )
