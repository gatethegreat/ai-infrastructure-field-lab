"""Local prompt-only and stateless authorization comparison adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any, Protocol

from .contracts import AuthorizationDecision, ControlModel, DecisionKind
from .tools import TOOL_NAMES


class Authorizer(Protocol):
    control_model: ControlModel
    supported_scopes: frozenset[str]

    def authorize(
        self,
        *,
        caller_id: str,
        session_id: str | None,
        tool: str,
        arguments: dict[str, Any],
        now: datetime,
    ) -> AuthorizationDecision: ...

    def reset(self) -> None: ...

    def observe(
        self,
        *,
        caller_id: str,
        session_id: str | None,
        tool: str,
        arguments: dict[str, Any],
        outcome: str,
        response: dict[str, Any] | None,
        error_code: str | None,
    ) -> None: ...


class _NoHistoryMixin:
    def reset(self) -> None:
        return None

    def observe(self, **_: Any) -> None:
        return None


@dataclass(frozen=True, slots=True)
class PromptOnlyAuthorizer(_NoHistoryMixin):
    """Advisory prompt artifact; deliberately supplies no enforcement."""

    prompt: str = (
        "Look up a record and obtain a fresh matching human approval before "
        "writing. Never reuse approvals or exceed session and retry limits."
    )
    control_model: ControlModel = ControlModel.PROMPT_ONLY
    supported_scopes: frozenset[str] = frozenset({"authorization"})
    known_callers: frozenset[str] = frozenset({"caller-a", "caller-b"})

    def authorize(
        self,
        *,
        caller_id: str,
        session_id: str | None,
        tool: str,
        arguments: dict[str, Any],
        now: datetime,
    ) -> AuthorizationDecision:
        if caller_id not in self.known_callers:
            return AuthorizationDecision(
                DecisionKind.DENY,
                "prompt-authentication-boundary-v1",
                f"{caller_id} is not an authenticated synthetic caller",
            )
        return AuthorizationDecision(
            DecisionKind.ALLOW,
            "prompt-advice-baseline-v1",
            "prompt instructions are advisory and are not evaluated here",
        )


class StatelessAuthorizer(_NoHistoryMixin):
    control_model = ControlModel.STATELESS
    supported_scopes = frozenset({"authorization"})

    def __init__(self, permissions: dict[str, set[str]] | None = None) -> None:
        all_tools = set(TOOL_NAMES)
        self.permissions = permissions or {
            "caller-a": set(all_tools),
            "caller-b": set(all_tools),
        }

    def authorize(
        self,
        *,
        caller_id: str,
        session_id: str | None,
        tool: str,
        arguments: dict[str, Any],
        now: datetime,
    ) -> AuthorizationDecision:
        if tool in self.permissions.get(caller_id, set()):
            return AuthorizationDecision(
                DecisionKind.ALLOW,
                "stateless-tool-permissions-v1",
                f"{caller_id} has permission for {tool}",
            )
        return AuthorizationDecision(
            DecisionKind.DENY,
            "stateless-tool-permissions-v1",
            f"{caller_id} lacks permission for {tool}",
        )


@dataclass(frozen=True, slots=True)
class ObservedToolEvent:
    tool: str
    arguments: dict[str, Any]
    outcome: str
    response: dict[str, Any] | None
    error_code: str | None


class LocalTemporalSpecificationAuthorizer:
    """Executable local specification; not Dogwood or AgentCore enforcement."""

    control_model = ControlModel.TEMPORAL
    supported_scopes = frozenset({"authorization"})
    policy_id = "local-temporal-specification-v1"
    _session_pattern = re.compile(r"^[A-Za-z0-9-]{1,128}$")

    def __init__(self, permissions: dict[str, set[str]] | None = None) -> None:
        all_tools = set(TOOL_NAMES)
        self.permissions = permissions or {
            "caller-a": set(all_tools),
            "caller-b": set(all_tools),
        }
        self._history: dict[tuple[str, str], list[ObservedToolEvent]] = {}

    def reset(self) -> None:
        self._history.clear()

    def _deny(self, reason: str) -> AuthorizationDecision:
        return AuthorizationDecision(DecisionKind.DENY, self.policy_id, reason)

    def _events(self, caller_id: str, session_id: str) -> list[ObservedToolEvent]:
        return self._history.setdefault((caller_id, session_id), [])

    def authorize(
        self,
        *,
        caller_id: str,
        session_id: str | None,
        tool: str,
        arguments: dict[str, Any],
        now: datetime,
    ) -> AuthorizationDecision:
        if tool not in self.permissions.get(caller_id, set()):
            return self._deny(f"{caller_id} lacks permission for {tool}")
        if session_id is None or not self._session_pattern.fullmatch(session_id):
            return AuthorizationDecision(
                DecisionKind.ERROR,
                self.policy_id,
                "policy session ID must match [A-Za-z0-9-]{1,128}",
                error_code="VALIDATION_ERROR",
            )
        if tool != "execute_write":
            return AuthorizationDecision(
                DecisionKind.ALLOW, self.policy_id, "specification prerequisite"
            )

        record_id = arguments.get("record_id")
        change = arguments.get("change")
        if not isinstance(record_id, str) or not isinstance(change, dict):
            return self._deny("write input is not schema-valid")
        approval_id = change.get("approval_id")
        change_id = change.get("change_id")
        if not isinstance(approval_id, str) or not isinstance(change_id, str):
            return self._deny("write lacks approval_id or change_id")
        events = self._events(caller_id, session_id)

        looked_up = any(
            event.tool == "lookup_record"
            and event.outcome == "success"
            and event.response is not None
            and event.response.get("record_id") == record_id
            for event in events
        )
        if not looked_up:
            return self._deny("no successful same-record lookup in this session")

        matching_approval: ObservedToolEvent | None = None
        for event in reversed(events):
            if (
                event.tool == "record_human_approval"
                and event.outcome == "success"
                and event.response is not None
                and event.response.get("record_id") == record_id
                and event.response.get("approval_id") == approval_id
                and event.response.get("approved") is True
            ):
                matching_approval = event
                break
        if matching_approval is None:
            return self._deny("no successful matching approval in this session")
        expires_at = matching_approval.response.get("expires_at")  # type: ignore[union-attr]
        try:
            expiry = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        except ValueError:
            return self._deny("matching approval has an invalid expiry")
        if expiry.tzinfo is None or expiry <= now:
            return self._deny("matching approval is expired")

        consumed = any(
            event.tool == "execute_write"
            and event.outcome == "success"
            and isinstance(event.arguments.get("change"), dict)
            and event.arguments["change"].get("approval_id") == approval_id
            for event in events
        )
        if consumed:
            return self._deny("approval was consumed by a successful write")

        successful_writes = sum(
            event.tool == "execute_write" and event.outcome == "success"
            for event in events
        )
        if successful_writes >= 3:
            return self._deny("session successful-write limit is three")

        failed_attempts = sum(
            event.tool == "execute_write"
            and event.outcome == "error"
            and isinstance(event.arguments.get("change"), dict)
            and event.arguments["change"].get("approval_id") == approval_id
            for event in events
        )
        if failed_attempts >= 3:
            return self._deny("approval failure limit is three attempts")

        return AuthorizationDecision(
            DecisionKind.ALLOW,
            self.policy_id,
            "local temporal specification prerequisites satisfied",
        )

    def observe(
        self,
        *,
        caller_id: str,
        session_id: str | None,
        tool: str,
        arguments: dict[str, Any],
        outcome: str,
        response: dict[str, Any] | None,
        error_code: str | None,
    ) -> None:
        if session_id is None or not self._session_pattern.fullmatch(session_id):
            return
        self._events(caller_id, session_id).append(
            ObservedToolEvent(tool, arguments, outcome, response, error_code)
        )
