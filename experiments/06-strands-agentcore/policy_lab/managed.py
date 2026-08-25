"""Managed AgentCore trajectory client and evidence runner.

This module is inert until called by ``run_agentcore_managed.py``.  It uses only
the Python standard library and the AWS CLI already required by the cloud plan.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
import csv
import hashlib
import hmac
import json
import math
from pathlib import Path
from statistics import median
import subprocess
from threading import Barrier
from time import perf_counter_ns, sleep
from typing import Any, Protocol
from urllib.error import HTTPError
from urllib.parse import parse_qsl, quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4

from .clock import LogicalClock
from .contracts import ControlModel, ExpectedOutcome, Scenario, stable_id
from .scenarios import load_scenarios


SESSION_HEADER = "x-amzn-bedrock-agentcore-policy-session-id"
MCP_VERSION = "2025-06-18"
MAX_REPETITIONS = 10
MAX_REQUEST_BUDGET = 1500
PROOF_SCENARIO_IDS = tuple(f"S{index:02d}" for index in range(1, 12))
AUTHORIZATION_LATENCY_UNAVAILABLE_REASON = (
    "per-request determining-policy spans were not configured"
)
POLICY_RESPONSIBLE_UNAVAILABLE_REASON = (
    "no determining-policy span was available"
)


@dataclass(frozen=True, slots=True)
class EphemeralCredentials:
    access_key_id: str = field(repr=False)
    secret_access_key: str = field(repr=False)
    session_token: str = field(repr=False)
    expiration: str


@dataclass(frozen=True, slots=True)
class StackConfiguration:
    gateway_url: str
    gateway_id: str
    engine_id: str
    primary_role_arn: str
    secondary_role_arn: str
    engine_mode: str
    policy_mode: str


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    headers: dict[str, str]
    body: bytes


class HttpTransport(Protocol):
    def send(self, url: str, headers: dict[str, str], body: bytes) -> HttpResponse: ...


class AwsControl(Protocol):
    def resolve_stack(self, stack_name: str, region: str) -> StackConfiguration: ...
    def assume_role(self, role_arn: str, session_name: str, region: str) -> EphemeralCredentials: ...
    def confirm_enforcement(self, config: StackConfiguration, region: str) -> dict[str, Any]: ...
    def confirm_rate_limit(
        self, config: StackConfiguration, region: str, rate_stack_name: str
    ) -> dict[str, Any]: ...
    def collect_observability(
        self, config: StackConfiguration, region: str, start: datetime, end: datetime
    ) -> dict[str, Any]: ...


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


class UrllibTransport:
    """One HTTP attempt per call; redirects and retries are deliberately disabled."""

    def __init__(self, timeout_seconds: float = 30.0) -> None:
        self.timeout_seconds = timeout_seconds
        self._opener = build_opener(_NoRedirect)

    def send(self, url: str, headers: dict[str, str], body: bytes) -> HttpResponse:
        request = Request(url, data=body, headers=headers, method="POST")
        try:
            with self._opener.open(request, timeout=self.timeout_seconds) as response:
                return HttpResponse(
                    response.status,
                    {key.lower(): value for key, value in response.headers.items()},
                    response.read(),
                )
        except HTTPError as error:
            return HttpResponse(
                error.code,
                {key.lower(): value for key, value in error.headers.items()},
                error.read(),
            )


class AwsCliControl:
    """Read cloud state and request short-lived role credentials through AWS CLI v2."""

    def _json(self, arguments: list[str]) -> dict[str, Any]:
        completed = subprocess.run(
            ["aws", *arguments, "--output", "json", "--no-cli-pager"],
            check=False,
            capture_output=True,
            text=True,
            shell=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"AWS CLI command failed ({arguments[0]}): {completed.stderr.strip()}"
            )
        payload = json.loads(completed.stdout or "{}")
        if not isinstance(payload, dict):
            raise RuntimeError("AWS CLI returned a non-object JSON response")
        return payload

    @staticmethod
    def _mapping(items: list[dict[str, Any]], key: str, value: str) -> dict[str, str]:
        return {str(item[key]): str(item[value]) for item in items}

    @staticmethod
    def _find_value(payload: Any, key: str) -> Any:
        if isinstance(payload, dict):
            if key in payload:
                return payload[key]
            for value in payload.values():
                found = AwsCliControl._find_value(value, key)
                if found is not None:
                    return found
        elif isinstance(payload, list):
            for value in payload:
                found = AwsCliControl._find_value(value, key)
                if found is not None:
                    return found
        return None

    @staticmethod
    def _policy_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
        for key in ("policySummaries", "policies", "items"):
            value = payload.get(key)
            if isinstance(value, list) and all(isinstance(item, dict) for item in value):
                return value
        return []

    def resolve_stack(self, stack_name: str, region: str) -> StackConfiguration:
        payload = self._json([
            "cloudformation", "describe-stacks", "--stack-name", stack_name,
            "--region", region,
        ])
        stacks = payload.get("Stacks", [])
        if len(stacks) != 1:
            raise RuntimeError("expected exactly one deployed policy-lab stack")
        stack = stacks[0]
        outputs = self._mapping(stack.get("Outputs", []), "OutputKey", "OutputValue")
        parameters = self._mapping(
            stack.get("Parameters", []), "ParameterKey", "ParameterValue"
        )
        required = {
            "GatewayUrl", "GatewayIdentifier", "PolicyEngineId",
            "PrimaryCallerRoleArn", "SecondaryCallerRoleArn",
        }
        missing = required - outputs.keys()
        if missing:
            raise RuntimeError(f"stack is missing outputs: {sorted(missing)}")
        return StackConfiguration(
            gateway_url=outputs["GatewayUrl"],
            gateway_id=outputs["GatewayIdentifier"],
            engine_id=outputs["PolicyEngineId"],
            primary_role_arn=outputs["PrimaryCallerRoleArn"],
            secondary_role_arn=outputs["SecondaryCallerRoleArn"],
            engine_mode=parameters.get("PolicyEngineMode", "UNKNOWN"),
            policy_mode=parameters.get("PolicyEnforcementMode", "UNKNOWN"),
        )

    def assume_role(
        self, role_arn: str, session_name: str, region: str
    ) -> EphemeralCredentials:
        payload = self._json([
            "sts", "assume-role", "--role-arn", role_arn,
            "--role-session-name", session_name, "--duration-seconds", "3600",
            "--region", region,
        ])
        credentials = payload.get("Credentials", {})
        try:
            return EphemeralCredentials(
                credentials["AccessKeyId"], credentials["SecretAccessKey"],
                credentials["SessionToken"], credentials["Expiration"],
            )
        except KeyError as error:
            raise RuntimeError("assume-role response omitted credentials") from error

    def confirm_enforcement(
        self, config: StackConfiguration, region: str
    ) -> dict[str, Any]:
        gateway = self._json([
            "bedrock-agentcore-control", "get-gateway",
            "--gateway-identifier", config.gateway_id, "--region", region,
        ])
        engine = self._json([
            "bedrock-agentcore-control", "get-policy-engine",
            "--policy-engine-id", config.engine_id, "--region", region,
        ])
        policies = self._json([
            "bedrock-agentcore-control", "list-policies",
            "--policy-engine-id", config.engine_id, "--region", region,
        ])
        gateway_status = self._find_value(gateway, "status")
        gateway_policy_config = self._find_value(gateway, "policyEngineConfiguration")
        gateway_mode = (
            gateway_policy_config.get("mode")
            if isinstance(gateway_policy_config, dict) else None
        )
        engine_status = self._find_value(engine, "status")
        if gateway_status != "READY":
            raise RuntimeError("managed proof requires Gateway status READY")
        if gateway_mode != "ENFORCE":
            raise RuntimeError("managed proof requires live Gateway policy mode ENFORCE")
        if config.engine_mode != "ENFORCE":
            raise RuntimeError("managed proof requires stack Policy Engine mode ENFORCE")
        if engine_status != "ACTIVE":
            raise RuntimeError("managed proof requires live Policy Engine status ACTIVE")
        if config.policy_mode != "ACTIVE":
            raise RuntimeError("managed proof requires stack policy mode ACTIVE")
        policy_items = self._policy_items(policies)
        expected_suffixes = {
            f"{base}{caller}"
            for base in ("Lookup", "Approval", "Status", "Write", "SessionCap", "RetryCap")
            for caller in ("Primary", "Secondary")
        }
        names = {str(item.get("name", "")) for item in policy_items}
        missing = sorted(
            suffix for suffix in expected_suffixes
            if not any(name.endswith(suffix) for name in names)
        )
        if missing:
            raise RuntimeError(f"managed proof is missing expected policies: {missing}")
        inactive = [
            str(item.get("name", "<unnamed>")) for item in policy_items
            if item.get("status") != "ACTIVE"
            or item.get("enforcementMode") != "ACTIVE"
        ]
        if inactive:
            raise RuntimeError(
                f"managed proof requires every returned policy ACTIVE: {inactive}"
            )
        return {"gateway": gateway, "engine": engine, "policies": policies}

    def confirm_rate_limit(
        self, config: StackConfiguration, region: str, rate_stack_name: str
    ) -> dict[str, Any]:
        gateway = self._json([
            "bedrock-agentcore-control", "get-gateway",
            "--gateway-identifier", config.gateway_id, "--region", region,
        ])
        if "READY" not in json.dumps(gateway).upper():
            raise RuntimeError("rate-limit burst requires Gateway status READY")
        stack = self._json([
            "cloudformation", "describe-stacks", "--stack-name", rate_stack_name,
            "--region", region,
        ])
        stacks = stack.get("Stacks", [])
        ready_states = {"CREATE_COMPLETE", "UPDATE_COMPLETE"}
        if (
            len(stacks) != 1
            or stacks[0].get("StackStatus") not in ready_states
        ):
            raise RuntimeError(
                "rate-limit burst requires rate stack CREATE_COMPLETE or "
                "UPDATE_COMPLETE"
            )
        resources = self._json([
            "cloudformation", "describe-stack-resources", "--stack-name",
            rate_stack_name, "--region", region,
        ])
        matches = [
            item for item in resources.get("StackResources", [])
            if item.get("ResourceType")
            == "AWS::BedrockAgentCore::GatewayRateLimit"
        ]
        if (
            len(matches) != 1
            or matches[0].get("ResourceStatus") not in ready_states
        ):
            raise RuntimeError(
                "rate-limit burst requires exactly one stable "
                "AWS::BedrockAgentCore::GatewayRateLimit resource in "
                "CREATE_COMPLETE or UPDATE_COMPLETE"
            )
        return {"gateway": gateway, "rate_stack": stack, "rate_resources": resources}

    def collect_observability(
        self, config: StackConfiguration, region: str, start: datetime, end: datetime
    ) -> dict[str, Any]:
        result: dict[str, Any] = {"metric_queries": [], "spans": None, "errors": []}
        try:
            metrics = self._json([
                "cloudwatch", "list-metrics", "--namespace", "AWS/Bedrock-AgentCore",
                "--metric-name", "TemporalLatency", "--region", region,
            ])
            for metric in metrics.get("Metrics", []):
                arguments = [
                    "cloudwatch", "get-metric-statistics", "--namespace",
                    "AWS/Bedrock-AgentCore", "--metric-name", "TemporalLatency",
                    "--start-time", start.isoformat(), "--end-time", end.isoformat(),
                    "--period", "60", "--statistics", "SampleCount", "Average",
                    "Minimum", "Maximum", "--region", region,
                ]
                dimensions = metric.get("Dimensions", [])
                if dimensions:
                    arguments.extend([
                        "--dimensions",
                        *[f"Name={item['Name']},Value={item['Value']}" for item in dimensions],
                    ])
                result["metric_queries"].append(self._json(arguments))
        except Exception as error:  # observability is captured without hiding run results
            result["errors"].append(f"TemporalLatency query: {error}")
        try:
            result["spans"] = self._json([
                "logs", "filter-log-events", "--log-group-name", "aws/spans",
                "--start-time", str(int(start.timestamp() * 1000)),
                "--end-time", str(int(end.timestamp() * 1000)),
                "--limit", "100", "--region", region,
            ])
        except Exception as error:
            result["errors"].append(f"aws/spans query: {error}")
        return result


def _sign(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def sigv4_headers(
    *,
    url: str,
    body: bytes,
    credentials: EphemeralCredentials,
    region: str,
    headers: dict[str, str],
    now: datetime,
) -> dict[str, str]:
    """Return an AWS SigV4-signed header set for AgentCore Gateway."""
    parsed = urlsplit(url)
    amz_date = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    date_stamp = amz_date[:8]
    normalized = {key.lower(): " ".join(value.strip().split()) for key, value in headers.items()}
    normalized.update({
        "host": parsed.netloc,
        "x-amz-date": amz_date,
        "x-amz-security-token": credentials.session_token,
    })
    canonical_uri = quote(parsed.path or "/", safe="/-_.~")
    canonical_query = "&".join(
        f"{quote(key, safe='-_.~')}={quote(value, safe='-_.~')}"
        for key, value in sorted(parse_qsl(parsed.query, keep_blank_values=True))
    )
    signed_names = ";".join(sorted(normalized))
    canonical_headers = "".join(
        f"{key}:{normalized[key]}\n" for key in sorted(normalized)
    )
    payload_hash = hashlib.sha256(body).hexdigest()
    canonical_request = "\n".join([
        "POST", canonical_uri, canonical_query, canonical_headers,
        signed_names, payload_hash,
    ])
    scope = f"{date_stamp}/{region}/bedrock-agentcore/aws4_request"
    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256", amz_date, scope,
        hashlib.sha256(canonical_request.encode()).hexdigest(),
    ])
    date_key = _sign(("AWS4" + credentials.secret_access_key).encode(), date_stamp)
    region_key = _sign(date_key, region)
    service_key = _sign(region_key, "bedrock-agentcore")
    signing_key = _sign(service_key, "aws4_request")
    signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()
    normalized["authorization"] = (
        "AWS4-HMAC-SHA256 "
        f"Credential={credentials.access_key_id}/{scope}, "
        f"SignedHeaders={signed_names}, Signature={signature}"
    )
    return normalized


def _decode_payload(body: bytes, content_type: str) -> Any:
    text = body.decode("utf-8", errors="replace")
    if "text/event-stream" in content_type:
        data = [line[5:].strip() for line in text.splitlines() if line.startswith("data:")]
        text = data[-1] if data else text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw_text": text}


def _extract_tool_response(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    result = payload.get("result")
    if isinstance(result, dict):
        if isinstance(result.get("structuredContent"), dict):
            return result["structuredContent"]
        for item in result.get("content", []):
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                try:
                    decoded = json.loads(item["text"])
                    if isinstance(decoded, dict):
                        return decoded
                except json.JSONDecodeError:
                    continue
    return None


def classify_response(response: HttpResponse) -> tuple[str, Any, dict[str, Any] | None]:
    payload = _decode_payload(response.body, response.headers.get("content-type", ""))
    serialized = json.dumps(payload).lower()
    error_code = (
        payload.get("error", {}).get("code")
        if isinstance(payload, dict) and isinstance(payload.get("error"), dict)
        else None
    )
    if response.status == 429 or error_code == -32003 or any(
        marker in serialized for marker in ("throttl", "rate_limit", "rate limit")
    ):
        return "rate_limited", payload, None
    if response.status == 400 or any(
        marker in serialized for marker in (
            "validation", "malformed", "sessionid is required",
            "session id is required", "rejected the request as invalid",
        )
    ):
        return "validation_error", payload, None
    if response.status in {401, 403} or any(
        marker in serialized for marker in (
            "accessdenied", "access denied", "authorization denied",
            "not authorized", "policy denied", "tool execution denied",
            "policy enforcement", "no policy applies",
        )
    ):
        return "deny", payload, None
    if response.status >= 400:
        return "transport_error", payload, None
    result = payload.get("result") if isinstance(payload, dict) else None
    if isinstance(result, dict) and result.get("isError") is True:
        return "tool_error", payload, None
    if isinstance(payload, dict) and "error" in payload:
        return "transport_error", payload, None
    tool_response = _extract_tool_response(payload)
    if isinstance(tool_response, dict) and tool_response.get("status") == "FAILED":
        return "tool_error", payload, tool_response
    return "success", payload, tool_response


class GatewayClient:
    def __init__(self, url: str, region: str, transport: HttpTransport) -> None:
        self.url = url
        self.region = region
        self.transport = transport

    def call(
        self,
        *,
        credentials: EphemeralCredentials,
        request_id: str,
        tool: str,
        arguments: dict[str, Any],
        session_id: str | None,
        now: datetime,
    ) -> tuple[HttpResponse, str, Any, dict[str, Any] | None]:
        body = json.dumps({
            "jsonrpc": "2.0", "id": request_id, "method": "tools/call",
            "params": {"name": f"SyntheticTools___{tool}", "arguments": arguments},
        }, sort_keys=True, separators=(",", ":")).encode()
        headers = {
            "accept": "application/json, text/event-stream",
            "content-type": "application/json",
            "mcp-protocol-version": MCP_VERSION,
        }
        if session_id is not None:
            headers[SESSION_HEADER] = session_id
        signed = sigv4_headers(
            url=self.url, body=body, credentials=credentials, region=self.region,
            headers=headers, now=now,
        )
        response = self.transport.send(self.url, signed, body)
        outcome, payload, tool_response = classify_response(response)
        return response, outcome, payload, tool_response


@dataclass(frozen=True, slots=True)
class ManagedRunSummary:
    run_id: str
    scenario_id: str
    repetition: int
    expected_result: str
    actual_result: str
    expectation_match: bool
    false_allow: bool
    false_denial: bool
    tool_calls_completed: int
    retries_attempted: int
    session_behavior: str
    request_count: int
    stopped_at: str | None
    added_authorization_latency_ms: float | None = None
    added_authorization_latency_reason: str = (
        AUTHORIZATION_LATENCY_UNAVAILABLE_REASON
    )
    policy_responsible: str | None = None
    policy_responsible_reason: str = POLICY_RESPONSIBLE_UNAVAILABLE_REASON


class ManagedTrajectoryRunner:
    """Execute catalog trajectories against an enforced managed Gateway."""

    def __init__(
        self,
        *,
        control: AwsControl,
        transport: HttpTransport,
        stack_name: str,
        rate_stack_name: str = "agentcore-policy-field-lab-rate-limit",
        region: str,
        repetitions: int,
        private_output: Path,
        redacted_output: Path,
        batch_id: str | None = None,
        observability_settle_seconds: float = 60.0,
        inter_step_delay_seconds: float = 0.0,
        scenario_ids: tuple[str, ...] | None = None,
    ) -> None:
        if repetitions < 1 or repetitions > MAX_REPETITIONS:
            raise ValueError(f"repetitions must be between 1 and {MAX_REPETITIONS}")
        self.control = control
        self.transport = transport
        self.stack_name = stack_name
        self.rate_stack_name = rate_stack_name
        self.region = region
        self.repetitions = repetitions
        requested_scenarios = (
            PROOF_SCENARIO_IDS if scenario_ids is None
            else tuple(dict.fromkeys(scenario_ids))
        )
        if not requested_scenarios:
            raise ValueError("scenario_ids must select at least one proof scenario")
        invalid_scenarios = sorted(
            set(requested_scenarios) - set(PROOF_SCENARIO_IDS)
        )
        if invalid_scenarios:
            raise ValueError(
                "managed proof scenario_ids must be within S01-S11: "
                + ", ".join(invalid_scenarios)
            )
        self.scenario_ids = requested_scenarios
        self.batch_id = batch_id or uuid4().hex[:12]
        if (
            not math.isfinite(inter_step_delay_seconds)
            or inter_step_delay_seconds < 0
            or inter_step_delay_seconds > 2
        ):
            raise ValueError("inter_step_delay_seconds must be between 0 and 2")
        # A batch owns immutable evidence paths so a later proof cannot replace
        # an earlier run merely because it uses the same output root.
        self.private_output = private_output / self.batch_id
        self.redacted_output = redacted_output / self.batch_id
        self.observability_settle_seconds = observability_settle_seconds
        self.inter_step_delay_seconds = inter_step_delay_seconds

    def _ensure_new_batch(self) -> None:
        if self.private_output.exists() or self.redacted_output.exists():
            raise RuntimeError(
                f"refusing to overwrite existing evidence batch {self.batch_id}"
            )

    def _credentials(self, config: StackConfiguration) -> dict[str, EphemeralCredentials]:
        return {
            "caller-a": self.control.assume_role(
                config.primary_role_arn, f"policy-lab-a-{self.batch_id}", self.region
            ),
            "caller-b": self.control.assume_role(
                config.secondary_role_arn, f"policy-lab-b-{self.batch_id}", self.region
            ),
        }

    @staticmethod
    def _namespaced_arguments(
        scenario: Scenario, step_id: str, arguments: dict[str, Any], namespace: str,
        now: datetime,
    ) -> dict[str, Any]:
        payload = json.loads(json.dumps(arguments))
        if "approval_id" in payload:
            payload["approval_id"] = f"{payload['approval_id']}-{namespace}"
        change = payload.get("change")
        if isinstance(change, dict):
            change["change_id"] = f"{change['change_id']}-{namespace}"
            change["approval_id"] = f"{change['approval_id']}-{namespace}"
        if "expires_at" in payload:
            expiry = now - timedelta(minutes=1) if scenario.scenario_id == "S05" else now + timedelta(minutes=15)
            payload["expires_at"] = expiry.isoformat().replace("+00:00", "Z")
        return payload

    @staticmethod
    def _session_map(scenario: Scenario, namespace: str) -> dict[str, str]:
        return {
            session: f"plab-{namespace}-{stable_id('s', session)[2:14]}"
            for session in {step.session_id for step in scenario.steps if step.session_id and "!" not in step.session_id}
        }

    def _execute_scenario(
        self,
        scenario: Scenario,
        repetition: int,
        client: GatewayClient,
        credentials: dict[str, EphemeralCredentials],
        warmup: bool,
    ) -> tuple[ManagedRunSummary, list[dict[str, Any]]]:
        namespace = f"{self.batch_id}-{scenario.scenario_id.lower()}-{repetition}-{'w' if warmup else 'm'}"
        run_id = stable_id("managed", namespace)
        sessions = self._session_map(scenario, namespace)
        expectation = scenario.expectations[ControlModel.TEMPORAL]
        events: list[dict[str, Any]] = []
        allowed_safety_steps: set[str] = set()
        denied_steps: set[str] = set()
        tool_errors = 0
        transport_errors = 0
        rate_limit_errors = 0
        completed = 0
        retries = 0
        previous_change_id: str | None = None
        continued_denial = False
        stopped_at: str | None = None
        for ordinal, step in enumerate(scenario.steps, start=1):
            if ordinal > 1 and self.inter_step_delay_seconds:
                sleep(self.inter_step_delay_seconds)
            now = datetime.now(timezone.utc)
            arguments = self._namespaced_arguments(scenario, step.step_id, step.arguments, namespace, now)
            change = arguments.get("change", {})
            change_id = change.get("change_id") if isinstance(change, dict) else None
            if change_id is not None and previous_change_id == change_id:
                retries += 1
            previous_change_id = change_id
            if step.session_id is None:
                session_id = None
                session_mode = "missing"
            elif "!" in step.session_id:
                session_id = step.session_id
                session_mode = "malformed"
            else:
                session_id = sessions[step.session_id]
                session_mode = "supplied"
            request_id = stable_id("mreq", [run_id, ordinal, step.step_id])
            started_at = datetime.now(timezone.utc)
            timer = perf_counter_ns()
            response, outcome, payload, tool_response = client.call(
                credentials=credentials[step.caller_id], request_id=request_id,
                tool=step.tool, arguments=arguments, session_id=session_id, now=now,
            )
            latency_ms = (perf_counter_ns() - timer) / 1_000_000
            ended_at = datetime.now(timezone.utc)
            if outcome == "success":
                completed += 1
            elif outcome == "tool_error":
                tool_errors += 1
            elif outcome == "deny":
                denied_steps.add(step.step_id)
            elif outcome == "transport_error":
                transport_errors += 1
            elif outcome == "rate_limited":
                rate_limit_errors += 1
            if step.step_id in scenario.safety_violation_steps and outcome in {"success", "tool_error"}:
                allowed_safety_steps.add(step.step_id)
            response_headers = dict(response.headers)
            events.append({
                "schema_version": "1.0", "execution_layer": "agentcore_managed",
                "batch_id": self.batch_id, "run_id": run_id,
                "inter_step_delay_seconds": self.inter_step_delay_seconds,
                "scenario_id": scenario.scenario_id, "repetition": repetition,
                "warmup": warmup, "trajectory_hash": scenario.trajectory_hash,
                "ordinal": ordinal, "step_id": step.step_id,
                "caller_id": step.caller_id, "session_mode": session_mode,
                "session_id": session_id, "request_id": request_id,
                "tool": step.tool, "arguments": arguments,
                "request_at": started_at.isoformat(), "response_at": ended_at.isoformat(),
                "latency_ms": latency_ms, "http_status": response.status,
                "added_authorization_latency_ms": None,
                "added_authorization_latency_reason": (
                    AUTHORIZATION_LATENCY_UNAVAILABLE_REASON
                ),
                "policy_responsible": None,
                "policy_responsible_reason": (
                    POLICY_RESPONSIBLE_UNAVAILABLE_REASON
                ),
                "response_headers": response_headers, "outcome": outcome,
                "raw_response_body": response.body.decode("utf-8", errors="replace"),
                "parsed_response": payload, "tool_response": tool_response,
                "aws_request_id": response_headers.get("x-amzn-requestid") or response_headers.get("x-amz-request-id"),
                "trace_id": response_headers.get("x-amzn-trace-id") or response_headers.get("traceparent"),
                "authorization": {
                    "decision": "allow" if outcome in {"success", "tool_error"} else "deny" if outcome == "deny" else "error",
                    "decision_source": "managed_gateway_response",
                    "configured_policy_hint": "TemporalWrite" if step.tool == "execute_write" else "ToolPermissions",
                    "configured_policy_hint_authoritative": False,
                },
            })
            if outcome in {"deny", "validation_error", "transport_error", "rate_limited"}:
                should_continue = step.continue_on_deny or step.continue_on_error
                continued_denial = continued_denial or should_continue
                if not should_continue:
                    stopped_at = step.step_id
                    break
            if outcome == "tool_error" and not step.continue_on_error:
                stopped_at = step.step_id
                break

        if any(event["outcome"] == "validation_error" for event in events):
            actual = ExpectedOutcome.VALIDATION_ERROR
        elif transport_errors:
            actual = ExpectedOutcome.TRANSPORT_ERROR
        elif rate_limit_errors:
            actual = ExpectedOutcome.RATE_LIMITED
        elif denied_steps and (tool_errors or continued_denial):
            actual = ExpectedOutcome.MIXED
        elif denied_steps:
            actual = ExpectedOutcome.DENY
        elif tool_errors:
            actual = ExpectedOutcome.TOOL_ERROR
        else:
            actual = ExpectedOutcome.ALLOW
        false_denial = bool(denied_steps - set(expectation.deny_steps))
        callers = {step.caller_id for step in scenario.steps}
        summary = ManagedRunSummary(
            run_id, scenario.scenario_id, repetition, expectation.outcome.value,
            actual.value, expectation.outcome == actual, bool(allowed_safety_steps),
            false_denial, completed, retries,
            "multiple_callers" if len(callers) > 1 else "rotated" if len(sessions) > 1 else "single_session",
            len(events), stopped_at,
        )
        return summary, events

    def run_proof(self) -> dict[str, Any]:
        self._ensure_new_batch()
        config = self.control.resolve_stack(self.stack_name, self.region)
        control_state = self.control.confirm_enforcement(config, self.region)
        credentials = self._credentials(config)
        client = GatewayClient(config.gateway_url, self.region, self.transport)
        scenarios = tuple(
            item for item in load_scenarios(clock=LogicalClock(datetime.now(timezone.utc)))
            if item.scenario_id in self.scenario_ids
        )
        request_budget = sum(len(item.steps) for item in scenarios) * (
            self.repetitions + 1
        )
        if request_budget > MAX_REQUEST_BUDGET:
            raise RuntimeError(
                f"managed proof request budget {request_budget} exceeds "
                f"hard limit {MAX_REQUEST_BUDGET}"
            )
        started = datetime.now(timezone.utc)
        summaries: list[ManagedRunSummary] = []
        events: list[dict[str, Any]] = []
        for scenario in scenarios:
            self._execute_scenario(scenario, 0, client, credentials, warmup=True)
            for repetition in range(1, self.repetitions + 1):
                summary, run_events = self._execute_scenario(
                    scenario, repetition, client, credentials, warmup=False
                )
                summaries.append(summary)
                events.extend(run_events)
        ended = datetime.now(timezone.utc)
        if self.observability_settle_seconds > 0:
            sleep(self.observability_settle_seconds)
        observability = self.control.collect_observability(
            config, self.region, started, ended
        )
        return self._write_outputs(
            "managed_temporal", config, control_state, summaries, events,
            observability, started, ended,
        )

    def run_rate_limit(self, settle_seconds: float = 30.0) -> dict[str, Any]:
        self._ensure_new_batch()
        config = self.control.resolve_stack(self.stack_name, self.region)
        rate_state = self.control.confirm_rate_limit(
            config, self.region, self.rate_stack_name
        )
        credentials = self._credentials(config)
        if settle_seconds > 0:
            sleep(settle_seconds)
        scenario = next(
            item for item in load_scenarios(clock=LogicalClock(datetime.now(timezone.utc)))
            if item.scenario_id == "S12"
        )
        client = GatewayClient(config.gateway_url, self.region, self.transport)
        namespace = f"{self.batch_id}-s12"
        session = f"plab-{namespace}"
        started = datetime.now(timezone.utc)

        barrier = Barrier(len(scenario.steps))

        def invoke(index: int) -> dict[str, Any]:
            step = scenario.steps[index]
            request_id = stable_id("rate", [namespace, index])
            barrier.wait()
            request_at = datetime.now(timezone.utc)
            timer = perf_counter_ns()
            response, outcome, payload, _ = client.call(
                credentials=credentials["caller-a"], request_id=request_id,
                tool=step.tool, arguments=step.arguments, session_id=session,
                now=datetime.now(timezone.utc),
            )
            return {
                "schema_version": "1.0", "execution_layer": "agentcore_rate_limit",
                "batch_id": self.batch_id, "scenario_id": "S12",
                "ordinal": index + 1, "step_id": step.step_id,
                "caller_id": "caller-a", "session_id": session,
                "request_id": request_id, "tool": step.tool,
                "arguments": step.arguments,
                "request_at": request_at.isoformat(),
                "response_at": datetime.now(timezone.utc).isoformat(),
                "latency_ms": (perf_counter_ns() - timer) / 1_000_000,
                "http_status": response.status, "outcome": outcome,
                "added_authorization_latency_ms": None,
                "added_authorization_latency_reason": (
                    AUTHORIZATION_LATENCY_UNAVAILABLE_REASON
                ),
                "policy_responsible": None,
                "policy_responsible_reason": (
                    POLICY_RESPONSIBLE_UNAVAILABLE_REASON
                ),
                "response_headers": dict(response.headers),
                "raw_response_body": response.body.decode("utf-8", errors="replace"),
                "parsed_response": payload,
                "aws_request_id": response.headers.get("x-amzn-requestid") or response.headers.get("x-amz-request-id"),
                "trace_id": response.headers.get("x-amzn-trace-id") or response.headers.get("traceparent"),
            }

        with ThreadPoolExecutor(max_workers=len(scenario.steps)) as executor:
            events = list(executor.map(invoke, range(len(scenario.steps))))
        ended = datetime.now(timezone.utc)
        throttled = sum(event["outcome"] == "rate_limited" for event in events)
        completed = sum(event["outcome"] == "success" for event in events)
        contaminating_outcomes = sorted(
            {event["outcome"] for event in events}
            - {"success", "rate_limited"}
        )
        if contaminating_outcomes:
            actual_result = ExpectedOutcome.INCONCLUSIVE.value
            expectation_match = False
        elif throttled:
            actual_result = ExpectedOutcome.RATE_LIMITED.value
            expectation_match = True
        else:
            actual_result = ExpectedOutcome.ALLOW.value
            expectation_match = False
        summary = ManagedRunSummary(
            stable_id("managed", namespace), "S12", 1, "rate_limited",
            actual_result, expectation_match, False,
            False, completed, 0,
            "single_session", len(events),
            (
                "concurrent_burst_contaminated:"
                + ",".join(contaminating_outcomes)
                if contaminating_outcomes else None
            ),
        )
        if self.observability_settle_seconds > 0:
            sleep(self.observability_settle_seconds)
        observability = self.control.collect_observability(
            config, self.region, started, ended
        )
        return self._write_outputs(
            "gateway_rate_limit", config, rate_state, [summary], events,
            observability, started, ended,
        )

    def _write_outputs(
        self,
        mode: str,
        config: StackConfiguration,
        control_state: dict[str, Any],
        summaries: list[ManagedRunSummary],
        events: list[dict[str, Any]],
        observability: dict[str, Any],
        started: datetime,
        ended: datetime,
    ) -> dict[str, Any]:
        self._ensure_new_batch()
        self.private_output.mkdir(parents=True, exist_ok=True)
        self.redacted_output.mkdir(parents=True, exist_ok=True)
        (self.private_output / f"{mode}-events.jsonl").write_text(
            "".join(json.dumps(item, sort_keys=True, default=str) + "\n" for item in events),
            encoding="utf-8",
        )
        (self.private_output / f"{mode}-control-plane.json").write_text(
            json.dumps(control_state, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
        (self.private_output / f"{mode}-configuration.json").write_text(
            json.dumps(asdict(config), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (self.private_output / f"{mode}-observability.json").write_text(
            json.dumps(observability, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
        rows = [asdict(item) for item in summaries]
        with (self.private_output / f"{mode}-runs.csv").open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

        grouped: dict[str, list[ManagedRunSummary]] = {}
        for item in summaries:
            grouped.setdefault(item.scenario_id, []).append(item)
        comparison = [{
            "scenario_id": scenario_id,
            "expected_result": group[0].expected_result,
            "actual_results": ",".join(sorted({item.actual_result for item in group})),
            "repetitions": len(group),
            "expectation_mismatches": sum(not item.expectation_match for item in group),
            "false_allows": sum(item.false_allow for item in group),
            "false_denials": sum(item.false_denial for item in group),
            "median_tool_calls_completed": median(item.tool_calls_completed for item in group),
            "median_retries_attempted": median(item.retries_attempted for item in group),
            "added_authorization_latency_ms": None,
            "added_authorization_latency_reason": (
                AUTHORIZATION_LATENCY_UNAVAILABLE_REASON
            ),
            "policy_responsible": None,
            "policy_responsible_reason": (
                POLICY_RESPONSIBLE_UNAVAILABLE_REASON
            ),
            "median_request_latency_ms": median(
                event["latency_ms"] for event in events
                if event["scenario_id"] == scenario_id
            ),
            "min_request_latency_ms": min(
                event["latency_ms"] for event in events
                if event["scenario_id"] == scenario_id
            ),
            "max_request_latency_ms": max(
                event["latency_ms"] for event in events
                if event["scenario_id"] == scenario_id
            ),
        } for scenario_id, group in sorted(grouped.items())]
        temporal_values = [
            float(point["Average"])
            for query in observability.get("metric_queries", [])
            for point in query.get("Datapoints", [])
            if "Average" in point
        ]
        comparison_path = self.redacted_output / f"{mode}-comparison.csv"
        with comparison_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(comparison[0]))
            writer.writeheader()
            writer.writerows(comparison)
        safe_summary = {
            "schema_version": "1.0", "execution_layer": "agentcore_managed",
            "mode": mode, "region": self.region, "batch_id": self.batch_id,
            "inter_step_delay_seconds": self.inter_step_delay_seconds,
            "inter_step_delay_applied": mode == "managed_temporal",
            "started_at": started.isoformat(), "ended_at": ended.isoformat(),
            "warmups_per_scenario": 1 if mode == "managed_temporal" else 0,
            "measured_repetitions": self.repetitions if mode == "managed_temporal" else 1,
            "scenario_ids": sorted(grouped), "runs": len(summaries),
            "events": len(events),
            "expectation_mismatches": sum(not item.expectation_match for item in summaries),
            "false_allows": sum(item.false_allow for item in summaries),
            "false_denials": sum(item.false_denial for item in summaries),
            "request_ids_captured": sum(bool(item.get("aws_request_id")) for item in events),
            "added_authorization_latency_ms": None,
            "added_authorization_latency_reason": (
                AUTHORIZATION_LATENCY_UNAVAILABLE_REASON
            ),
            "policy_responsible": None,
            "policy_responsible_reason": (
                POLICY_RESPONSIBLE_UNAVAILABLE_REASON
            ),
            "temporal_latency_metric_queries": len(observability.get("metric_queries", [])),
            "temporal_latency_average_ms": {
                "samples": len(temporal_values),
                "median": median(temporal_values) if temporal_values else None,
                "min": min(temporal_values) if temporal_values else None,
                "max": max(temporal_values) if temporal_values else None,
            },
            "observability_error_count": len(observability.get("errors", [])),
            "raw_evidence_location": "private ignored directory; not committed",
        }
        redacted_payload = json.dumps(
            {"summary": safe_summary, "comparison": comparison}, sort_keys=True
        )
        forbidden_identifiers = (
            config.gateway_url,
            config.gateway_id,
            config.engine_id,
            config.primary_role_arn,
            config.secondary_role_arn,
        )
        if any(value and value in redacted_payload for value in forbidden_identifiers):
            raise RuntimeError(
                "refusing to write redacted output containing a managed identifier"
            )
        summary_path = self.redacted_output / f"{mode}-summary.json"
        summary_path.write_text(
            json.dumps(safe_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return {
            "summary": str(summary_path), "comparison": str(comparison_path),
            "raw_directory": str(self.private_output), **safe_summary,
        }
