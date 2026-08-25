"""Typed, framework-neutral contracts for the policy comparison lab."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from hashlib import sha256
import json
from typing import Any


SCHEMA_VERSION = "1.0"


def stable_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return sha256(encoded).hexdigest()


def stable_id(prefix: str, value: object) -> str:
    return f"{prefix}_{stable_hash(value)[:16]}"


def require_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


class ControlModel(StrEnum):
    PROMPT_ONLY = "prompt_only"
    STATELESS = "stateless_auth"
    TEMPORAL = "temporal_policy"
    GATEWAY_RATE_LIMIT = "gateway_rate_limit"


class DecisionKind(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    ERROR = "error"
    NOT_EVALUATED = "not_evaluated"


class ExpectedOutcome(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    TOOL_ERROR = "tool_error"
    VALIDATION_ERROR = "validation_error"
    TRANSPORT_ERROR = "transport_error"
    MIXED = "mixed"
    RATE_LIMITED = "rate_limited"
    INCONCLUSIVE = "inconclusive"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class Change:
    change_id: str
    approval_id: str
    value: str
    force_error: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Change:
        if not isinstance(data, dict):
            raise ValueError("change must be an object")
        allowed = {"change_id", "approval_id", "value", "force_error"}
        if set(data) - allowed:
            raise ValueError("change contains unsupported fields")
        force_error = data.get("force_error", False)
        if not isinstance(force_error, bool):
            raise ValueError("change.force_error must be boolean")
        return cls(
            change_id=require_string(data.get("change_id"), "change.change_id"),
            approval_id=require_string(
                data.get("approval_id"), "change.approval_id"
            ),
            value=require_string(data.get("value"), "change.value"),
            force_error=force_error,
        )


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    kind: DecisionKind
    policy_id: str
    reason: str
    latency_ms: float = 0.0
    error_code: str | None = None

    @property
    def allowed(self) -> bool:
        return self.kind == DecisionKind.ALLOW


@dataclass(frozen=True, slots=True)
class ScenarioStep:
    step_id: str
    tool: str
    arguments: dict[str, Any]
    caller_id: str = "caller-a"
    session_id: str | None = "session-main"
    continue_on_error: bool = False
    continue_on_deny: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScenarioStep:
        if not isinstance(data, dict):
            raise ValueError("scenario step must be an object")
        arguments = data.get("arguments")
        if not isinstance(arguments, dict):
            raise ValueError("step.arguments must be an object")
        session_id = data.get("session_id", "session-main")
        if session_id is not None and not isinstance(session_id, str):
            raise ValueError("step.session_id must be a string or null")
        return cls(
            step_id=require_string(data.get("step_id"), "step.step_id"),
            tool=require_string(data.get("tool"), "step.tool"),
            arguments=arguments,
            caller_id=require_string(data.get("caller_id", "caller-a"), "caller_id"),
            session_id=session_id,
            continue_on_error=bool(data.get("continue_on_error", False)),
            continue_on_deny=bool(data.get("continue_on_deny", False)),
        )


@dataclass(frozen=True, slots=True)
class ScenarioExpectation:
    outcome: ExpectedOutcome
    deny_steps: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScenarioExpectation:
        if not isinstance(data, dict):
            raise ValueError("scenario expectation must be an object")
        deny_steps = data.get("deny_steps", [])
        if not isinstance(deny_steps, list) or not all(
            isinstance(item, str) for item in deny_steps
        ):
            raise ValueError("expectation.deny_steps must be a string list")
        return cls(ExpectedOutcome(data["outcome"]), tuple(deny_steps))


@dataclass(frozen=True, slots=True)
class Scenario:
    scenario_id: str
    name: str
    scope: str
    steps: tuple[ScenarioStep, ...]
    safety_violation_steps: tuple[str, ...]
    expectations: dict[ControlModel, ScenarioExpectation]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Scenario:
        if not isinstance(data, dict):
            raise ValueError("scenario must be an object")
        steps = tuple(ScenarioStep.from_dict(item) for item in data.get("steps", []))
        if not steps:
            raise ValueError("scenario must contain at least one step")
        step_ids = [step.step_id for step in steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("scenario step IDs must be unique")
        safety = data.get("safety_violation_steps", [])
        if not isinstance(safety, list) or not set(safety).issubset(step_ids):
            raise ValueError("safety violation steps must reference scenario steps")
        raw_expectations = data.get("expectations")
        if not isinstance(raw_expectations, dict):
            raise ValueError("scenario expectations must be an object")
        expectations = {
            ControlModel(model): ScenarioExpectation.from_dict(expectation)
            for model, expectation in raw_expectations.items()
        }
        for expectation in expectations.values():
            if not set(expectation.deny_steps).issubset(step_ids):
                raise ValueError("expected deny step does not exist")
        return cls(
            scenario_id=require_string(data.get("scenario_id"), "scenario_id"),
            name=require_string(data.get("name"), "scenario.name"),
            scope=require_string(data.get("scope"), "scenario.scope"),
            steps=steps,
            safety_violation_steps=tuple(safety),
            expectations=expectations,
        )

    @property
    def trajectory_hash(self) -> str:
        canonical = {
            "scenario_id": self.scenario_id,
            "scope": self.scope,
            "steps": [asdict(step) for step in self.steps],
        }
        return stable_hash(canonical)
