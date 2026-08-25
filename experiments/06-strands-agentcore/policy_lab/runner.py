"""Deterministic runner shared by local and future managed adapters."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from time import perf_counter_ns
from typing import Any

from .clock import LogicalClock
from .contracts import (
    ControlModel,
    DecisionKind,
    ExpectedOutcome,
    Scenario,
    stable_id,
)
from .evidence import EvidenceEvent, EvidenceLog
from .policies import Authorizer
from .store import SyntheticStore
from .tools import SyntheticTools


@dataclass(frozen=True, slots=True)
class RunSummary:
    run_id: str
    scenario_id: str
    control_model: str
    trajectory_hash: str
    expected_result: str
    actual_result: str
    false_allow: bool
    false_denial: bool
    stopped_at: str | None
    tool_calls_completed: int
    retries_presented: int
    retries_executed: int
    session_behavior: str
    event_count: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class DeterministicRunner:
    def __init__(
        self,
        authorizer: Authorizer,
        *,
        clock: LogicalClock | None = None,
        execution_layer: str = "local",
    ) -> None:
        self.authorizer = authorizer
        self.clock = clock or LogicalClock()
        self.execution_layer = execution_layer

    def run(self, scenario: Scenario, repetition: int = 1) -> tuple[RunSummary, EvidenceLog, SyntheticStore]:
        if repetition < 1:
            raise ValueError("repetition must be positive")
        expectation = scenario.expectations[self.authorizer.control_model]
        run_id = stable_id(
            "run",
            [scenario.scenario_id, repetition, self.authorizer.control_model.value],
        )
        evidence = EvidenceLog()
        store = SyntheticStore(run_id)
        tools = SyntheticTools(store)
        self.authorizer.reset()
        if scenario.scope not in self.authorizer.supported_scopes:
            summary = RunSummary(
                run_id,
                scenario.scenario_id,
                self.authorizer.control_model.value,
                scenario.trajectory_hash,
                expectation.outcome.value,
                ExpectedOutcome.NOT_APPLICABLE.value,
                False,
                False,
                None,
                0,
                0,
                0,
                "not_applicable",
                0,
            )
            return summary, evidence, store

        completed = 0
        retries_presented = 0
        retries_executed = 0
        denied_steps: set[str] = set()
        allowed_steps: set[str] = set()
        tool_errors = 0
        authorization_errors: list[str] = []
        stopped_at: str | None = None
        previous_change_id: str | None = None

        for ordinal, step in enumerate(scenario.steps, start=1):
            request_started = perf_counter_ns()
            current_change = step.arguments.get("change", {})
            current_change_id = (
                current_change.get("change_id")
                if step.tool == "execute_write" and isinstance(current_change, dict)
                else None
            )
            is_retry = (
                current_change_id is not None
                and current_change_id == previous_change_id
            )
            if is_retry:
                retries_presented += 1
            request_at = self.clock.iso_now()
            request_id = stable_id("req", [run_id, ordinal, step.step_id])
            correlation_id = stable_id("corr", [run_id, scenario.scenario_id])
            authorization_started = perf_counter_ns()
            decision = self.authorizer.authorize(
                caller_id=step.caller_id,
                session_id=step.session_id,
                tool=step.tool,
                arguments=step.arguments,
                now=self.clock.now,
            )
            authorization_latency_ms = (
                perf_counter_ns() - authorization_started
            ) / 1_000_000
            decision = replace(decision, latency_ms=authorization_latency_ms)
            invoked = False
            response: dict[str, Any] | None = None
            error_code: str | None = decision.error_code
            error_message: str | None = None
            outcome = "not_started"
            tool_latency_ms: float | None = None

            if decision.allowed:
                allowed_steps.add(step.step_id)
                invoked = True
                if is_retry:
                    retries_executed += 1
                tool_started = perf_counter_ns()
                try:
                    response = tools.invoke(step.tool, step.arguments)
                    if step.tool == "execute_write":
                        write_status = response.get("status")
                        if write_status == "SUCCEEDED":
                            outcome = "success"
                            completed += 1
                        else:
                            outcome = "error"
                            error_code = (
                                "DECLARED_TOOL_FAILURE"
                                if write_status == "FAILED"
                                else "INVALID_TOOL_RESPONSE"
                            )
                            error_message = (
                                f"execute_write returned status {write_status!r}"
                            )
                            tool_errors += 1
                    else:
                        outcome = "success"
                        completed += 1
                except Exception as error:  # captured as experiment evidence
                    outcome = "error"
                    error_code = type(error).__name__
                    error_message = str(error)
                    tool_errors += 1
                tool_latency_ms = (perf_counter_ns() - tool_started) / 1_000_000
                self.authorizer.observe(
                    caller_id=step.caller_id,
                    session_id=step.session_id,
                    tool=step.tool,
                    arguments=step.arguments,
                    outcome=outcome,
                    response=response,
                    error_code=error_code,
                )
                self.clock.advance(1.0)
            elif decision.kind == DecisionKind.DENY:
                denied_steps.add(step.step_id)
                error_code = error_code or "AUTHORIZATION_DENIED"
                error_message = decision.reason
            else:
                error_code = error_code or "AUTHORIZATION_ERROR"
                error_message = decision.reason
                authorization_errors.append(error_code)

            response_at = self.clock.iso_now()
            request_latency_ms = (perf_counter_ns() - request_started) / 1_000_000
            evidence.append(
                EvidenceEvent(
                    run_id=run_id,
                    trajectory_hash=scenario.trajectory_hash,
                    scenario_id=scenario.scenario_id,
                    repetition=repetition,
                    control_model=self.authorizer.control_model.value,
                    execution_layer=self.execution_layer,
                    caller_id=step.caller_id,
                    session_id=step.session_id,
                    ordinal=ordinal,
                    step_id=step.step_id,
                    request_id=request_id,
                    correlation_id=correlation_id,
                    tool=step.tool,
                    arguments=step.arguments,
                    request_at=request_at,
                    response_at=response_at,
                    latency_ms=request_latency_ms,
                    authorization={
                        "decision": decision.kind.value,
                        "policy_id": decision.policy_id,
                        "reason": decision.reason,
                        "latency_ms": decision.latency_ms,
                        "error_code": decision.error_code,
                    },
                    tool_execution={
                        "invoked": invoked,
                        "outcome": outcome,
                        "response": response,
                        "latency_ms": tool_latency_ms,
                        "error_code": error_code,
                        "error_message": error_message,
                    },
                )
            )
            previous_change_id = current_change_id
            should_continue = (
                (decision.kind == DecisionKind.DENY and step.continue_on_deny)
                or (decision.kind == DecisionKind.ERROR and step.continue_on_error)
                or (outcome == "error" and step.continue_on_error)
            )
            if (decision.kind != DecisionKind.ALLOW or outcome == "error") and not should_continue:
                stopped_at = step.step_id
                break

        false_allow = bool(set(scenario.safety_violation_steps) & allowed_steps)
        expected_denies = set(expectation.deny_steps)
        false_denial = bool(denied_steps - expected_denies)
        continued_denial = any(
            step.step_id in denied_steps and step.continue_on_deny
            for step in scenario.steps
        )
        if authorization_errors and any(
            code in {"RATE_LIMITED", "THROTTLED", "ThrottlingException"}
            for code in authorization_errors
        ):
            actual = ExpectedOutcome.RATE_LIMITED
        elif authorization_errors:
            actual = ExpectedOutcome.VALIDATION_ERROR
        elif denied_steps and (tool_errors or continued_denial):
            actual = ExpectedOutcome.MIXED
        elif denied_steps:
            actual = ExpectedOutcome.DENY
        elif tool_errors:
            actual = ExpectedOutcome.TOOL_ERROR
        else:
            actual = ExpectedOutcome.ALLOW
        sessions = {step.session_id for step in scenario.steps}
        callers = {step.caller_id for step in scenario.steps}
        session_behavior = (
            "multiple_callers" if len(callers) > 1 else
            "rotated" if len(sessions) > 1 else
            "single_session"
        )
        summary = RunSummary(
            run_id=run_id,
            scenario_id=scenario.scenario_id,
            control_model=self.authorizer.control_model.value,
            trajectory_hash=scenario.trajectory_hash,
            expected_result=expectation.outcome.value,
            actual_result=actual.value,
            false_allow=false_allow,
            false_denial=false_denial,
            stopped_at=stopped_at,
            tool_calls_completed=completed,
            retries_presented=retries_presented,
            retries_executed=retries_executed,
            session_behavior=session_behavior,
            event_count=len(evidence.events),
        )
        return summary, evidence, store
