from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch


EXPERIMENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT))

from policy_lab.managed import (  # noqa: E402
    AwsCliControl,
    EphemeralCredentials,
    GatewayClient,
    HttpResponse,
    ManagedTrajectoryRunner,
    SESSION_HEADER,
    StackConfiguration,
    classify_response,
)
import run_agentcore_managed  # noqa: E402


def mcp_success(request_id: str, value: dict) -> HttpResponse:
    return HttpResponse(
        200,
        {"content-type": "application/json", "x-amzn-requestid": f"aws-{request_id}"},
        json.dumps({
            "jsonrpc": "2.0", "id": request_id,
            "result": {"structuredContent": value},
        }).encode(),
    )


class MockControl:
    def __init__(self, *, enforced: bool = True, rate_active: bool = True) -> None:
        self.enforced = enforced
        self.rate_active = rate_active
        self.assumed: list[str] = []
        self.observability_calls = 0

    def resolve_stack(self, stack_name, region):
        return StackConfiguration(
            "https://gateway.example.test/mcp", "gateway-1", "engine-1",
            "arn:aws:iam::<ACCOUNT_ID>:role/primary",
            "arn:aws:iam::<ACCOUNT_ID>:role/secondary",
            "ENFORCE", "ACTIVE",
        )

    def assume_role(self, role_arn, session_name, region):
        self.assumed.append(role_arn)
        caller = "A" if role_arn.endswith("primary") else "B"
        return EphemeralCredentials(
            f"AKID{caller}", f"SECRET{caller}", f"TOKEN{caller}",
            "2026-08-24T23:00:00Z",
        )

    def confirm_enforcement(self, config, region):
        if not self.enforced:
            raise RuntimeError("managed proof requires active enforcement")
        return {
            "gateway": {"status": "READY"},
            "engine": {"status": "ACTIVE"},
            "policies": [{"status": "ACTIVE"}],
        }

    def confirm_rate_limit(self, config, region, rate_stack_name):
        if not self.rate_active:
            raise RuntimeError("rate limit is not ACTIVE")
        return {
            "rate_stack": {"Stacks": [{"StackStatus": "CREATE_COMPLETE"}]},
            "rate_resources": {"StackResources": [{
                "LogicalResourceId": "SyntheticPerToolLimit",
                "ResourceType": "AWS::BedrockAgentCore::GatewayRateLimit",
                "ResourceStatus": "CREATE_COMPLETE",
            }]},
        }

    def collect_observability(self, config, region, start, end):
        self.observability_calls += 1
        return {
            "metric_queries": [{"Datapoints": [{"Average": 1.25}]}],
            "spans": {"events": []}, "errors": [],
        }


class StatefulMockGateway:
    """Small fake remote boundary used only to test managed orchestration."""

    def __init__(
        self, *, throttle_after: int | None = None,
        deny_after: int | None = None,
    ) -> None:
        self.history: dict[tuple[str, str], list[dict]] = {}
        self.requests: list[dict] = []
        self.throttle_after = throttle_after
        self.deny_after = deny_after
        self._count = 0
        self._lock = threading.Lock()

    @staticmethod
    def _caller(headers: dict[str, str]) -> str:
        authorization = headers["authorization"]
        return "caller-a" if "Credential=AKIDA/" in authorization else "caller-b"

    def send(self, url, headers, body):
        request = json.loads(body)
        tool = request["params"]["name"].split("___", 1)[-1]
        arguments = request["params"]["arguments"]
        request_id = request["id"]
        session = headers.get(SESSION_HEADER)
        caller = self._caller(headers)
        self.requests.append({
            "tool": tool, "arguments": arguments, "session": session,
            "caller": caller, "headers": dict(headers),
        })
        with self._lock:
            self._count += 1
            count = self._count
        if self.throttle_after is not None and count > self.throttle_after:
            return HttpResponse(
                429, {"content-type": "application/json"},
                b'{"error":"rate limit exceeded"}',
            )
        if self.deny_after is not None and count > self.deny_after:
            return HttpResponse(
                403, {"content-type": "application/json"},
                b'{"error":"policy denied"}',
            )
        if session is None or not session.replace("-", "").isalnum():
            return HttpResponse(
                400, {"content-type": "application/json"},
                b'{"error":"validation error: malformed policy session"}',
            )
        events = self.history.setdefault((caller, session), [])
        if tool == "lookup_record":
            value = {"record_id": arguments["record_id"], "value": "synthetic"}
            events.append({"tool": tool, "outcome": "success", "response": value})
            return mcp_success(request_id, value)
        if tool == "record_human_approval":
            expiry = datetime.fromisoformat(arguments["expires_at"].replace("Z", "+00:00"))
            value = {
                **arguments, "valid": expiry > datetime.now(timezone.utc),
            }
            events.append({"tool": tool, "outcome": "success", "response": value})
            return mcp_success(request_id, value)
        if tool == "execute_write":
            record_id = arguments["record_id"]
            change = arguments["change"]
            looked_up = any(
                item["tool"] == "lookup_record"
                and item["response"]["record_id"] == record_id
                for item in events
            )
            approved = any(
                item["tool"] == "record_human_approval"
                and item["response"]["record_id"] == record_id
                and item["response"]["approval_id"] == change["approval_id"]
                and item["response"]["valid"]
                for item in events
            )
            consumed = any(
                item["tool"] == "execute_write"
                and item["outcome"] == "success"
                and item["arguments"]["change"]["approval_id"] == change["approval_id"]
                for item in events
            )
            successes = sum(
                item["tool"] == "execute_write" and item["outcome"] == "success"
                for item in events
            )
            failures = sum(
                item["tool"] == "execute_write"
                and item["outcome"] == "error"
                and item["arguments"]["change"]["change_id"] == change["change_id"]
                for item in events
            )
            if not looked_up or not approved or consumed or successes >= 3 or failures >= 3:
                return HttpResponse(
                    403, {"content-type": "application/json"},
                    b'{"error":"authorization denied by policy"}',
                )
            if change.get("force_error"):
                events.append({
                    "tool": tool, "outcome": "error", "arguments": arguments,
                })
                return mcp_success(request_id, {
                    "operation_id": f"op-{change['change_id']}",
                    "record_id": record_id,
                    "change_id": change["change_id"],
                    "approval_id": change["approval_id"],
                    "status": "FAILED",
                })
            value = {
                "operation_id": f"op-{change['change_id']}",
                "record_id": record_id, "change_id": change["change_id"],
                "approval_id": change["approval_id"], "status": "SUCCEEDED",
            }
            events.append({
                "tool": tool, "outcome": "success", "arguments": arguments,
                "response": value,
            })
            return mcp_success(request_id, value)
        raise AssertionError(f"unexpected mock tool {tool}")


class ManagedRunnerTests(unittest.TestCase):
    @staticmethod
    def active_policy_items():
        return [
            {
                "name": f"AgentCorePolicyLab_{base}{caller}",
                "status": "ACTIVE",
                "enforcementMode": "ACTIVE",
            }
            for base in (
                "Lookup", "Approval", "Status", "Write", "SessionCap", "RetryCap"
            )
            for caller in ("Primary", "Secondary")
        ]

    def make_runner(
        self, root: Path, control, transport, repetitions=1, *,
        batch_id="mockbatch", inter_step_delay_seconds=0.0,
        scenario_ids=None,
    ):
        return ManagedTrajectoryRunner(
            control=control, transport=transport, stack_name="stack",
            region="us-east-1", repetitions=repetitions,
            private_output=root / "private", redacted_output=root / "redacted",
            batch_id=batch_id, observability_settle_seconds=0,
            inter_step_delay_seconds=inter_step_delay_seconds,
            scenario_ids=scenario_ids,
        )

    def test_sigv4_session_headers_are_exactly_controlled(self) -> None:
        gateway = StatefulMockGateway()
        client = GatewayClient(
            "https://gateway.example.test/mcp", "us-east-1", gateway
        )
        credentials = EphemeralCredentials("AKIDA", "SECRETA", "TOKENA", "later")
        now = datetime(2026, 8, 24, 16, 0, tzinfo=timezone.utc)
        client.call(
            credentials=credentials, request_id="one", tool="lookup_record",
            arguments={"record_id": "record-a"}, session_id="valid-session", now=now,
        )
        client.call(
            credentials=credentials, request_id="two", tool="lookup_record",
            arguments={"record_id": "record-a"}, session_id=None, now=now,
        )
        self.assertEqual("valid-session", gateway.requests[0]["session"])
        self.assertNotIn(SESSION_HEADER, gateway.requests[1]["headers"])
        self.assertIn("authorization", gateway.requests[0]["headers"])
        self.assertEqual("TOKENA", gateway.requests[0]["headers"]["x-amz-security-token"])
        self.assertEqual("2025-06-18", gateway.requests[0]["headers"]["mcp-protocol-version"])

    def test_managed_proof_runs_s01_to_s11_with_two_ephemeral_callers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            control = MockControl()
            gateway = StatefulMockGateway()
            result = self.make_runner(root, control, gateway).run_proof()
            self.assertEqual(11, result["runs"])
            self.assertEqual(0, result["expectation_mismatches"])
            self.assertEqual(0, result["false_allows"])
            self.assertEqual(0, result["false_denials"])
            self.assertEqual(2, len(control.assumed))
            self.assertEqual(1, control.observability_calls)

            comparison_path = (
                root / "redacted" / "mockbatch" /
                "managed_temporal-comparison.csv"
            )
            with comparison_path.open(encoding="utf-8", newline="") as handle:
                comparison = list(csv.DictReader(handle))
            self.assertEqual(
                [f"S{index:02d}" for index in range(1, 12)],
                [row["scenario_id"] for row in comparison],
            )
            self.assertTrue(all(
                row["added_authorization_latency_ms"] == ""
                and "determining-policy spans were not configured"
                in row["added_authorization_latency_reason"]
                and row["policy_responsible"] == ""
                and "no determining-policy span was available"
                in row["policy_responsible_reason"]
                for row in comparison
            ))
            events_text = (
                root / "private" / "mockbatch" /
                "managed_temporal-events.jsonl"
            ).read_text(encoding="utf-8")
            events = [json.loads(line) for line in events_text.splitlines()]
            self.assertTrue(all(
                event["added_authorization_latency_ms"] is None
                and "determining-policy spans were not configured"
                in event["added_authorization_latency_reason"]
                and event["policy_responsible"] is None
                and "no determining-policy span was available"
                in event["policy_responsible_reason"]
                and event["authorization"][
                    "configured_policy_hint_authoritative"
                ] is False
                for event in events
            ))
            with (
                root / "private" / "mockbatch" /
                "managed_temporal-runs.csv"
            ).open(encoding="utf-8", newline="") as handle:
                runs = list(csv.DictReader(handle))
            self.assertTrue(all(
                row["added_authorization_latency_ms"] == ""
                and "determining-policy spans were not configured"
                in row["added_authorization_latency_reason"]
                and row["policy_responsible"] == ""
                and "no determining-policy span was available"
                in row["policy_responsible_reason"]
                for row in runs
            ))
            s10 = [event for event in events if event["scenario_id"] == "S10"]
            self.assertEqual({"caller-a", "caller-b"}, {event["caller_id"] for event in s10})
            shared = {event["session_id"] for event in s10}
            self.assertEqual(1, len(shared))
            s11 = [event for event in events if event["scenario_id"] == "S11"]
            self.assertEqual(["missing", "malformed"], [event["session_mode"] for event in s11])
            self.assertTrue(all(event["outcome"] == "validation_error" for event in s11))
            self.assertNotIn("SECRETA", events_text)
            redacted = (
                root / "redacted" / "mockbatch" /
                "managed_temporal-summary.json"
            ).read_text()
            self.assertNotIn("session_id", redacted)
            self.assertNotIn("gateway.example", redacted)
            self.assertNotIn("gateway-1", redacted)
            redacted_summary = json.loads(redacted)
            self.assertIsNone(
                redacted_summary["added_authorization_latency_ms"]
            )
            self.assertIsNone(redacted_summary["policy_responsible"])
            self.assertEqual(1.25, redacted_summary[
                "temporal_latency_average_ms"
            ]["median"])

    def test_managed_proof_can_target_one_scenario_with_warmup_and_repetitions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            control = MockControl()
            gateway = StatefulMockGateway()
            result = self.make_runner(
                root, control, gateway, repetitions=10,
                batch_id="target-s08", inter_step_delay_seconds=1.0,
                scenario_ids=("S08",),
            )
            with patch("policy_lab.managed.sleep"):
                result = result.run_proof()
            self.assertEqual(["S08"], result["scenario_ids"])
            self.assertEqual(10, result["runs"])
            self.assertEqual(66, len(gateway.requests))
            self.assertEqual(2, len(control.assumed))
            with (
                root / "redacted" / "target-s08" /
                "managed_temporal-comparison.csv"
            ).open(encoding="utf-8", newline="") as handle:
                comparison = list(csv.DictReader(handle))
            self.assertEqual(["S08"], [row["scenario_id"] for row in comparison])

    def test_run_namespaces_approval_change_and_session_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            gateway = StatefulMockGateway()
            self.make_runner(Path(temp), MockControl(), gateway).run_proof()
            approvals = [
                item["arguments"]["approval_id"] for item in gateway.requests
                if item["tool"] == "record_human_approval"
            ]
            changes = [
                item["arguments"]["change"]["change_id"] for item in gateway.requests
                if item["tool"] == "execute_write"
            ]
            self.assertTrue(all("mockbatch" in value for value in approvals))
            self.assertTrue(all("mockbatch" in value for value in changes))
            self.assertTrue(all(
                item["session"] is None or item["session"] == "bad_session!"
                or item["session"].startswith("plab-mockbatch-")
                for item in gateway.requests
            ))

    def test_each_batch_has_stable_non_overwriting_evidence_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = self.make_runner(
                root, MockControl(), StatefulMockGateway(), batch_id="batch-one"
            )
            first.run_proof()
            first_summary = (
                root / "redacted" / "batch-one" /
                "managed_temporal-summary.json"
            ).read_bytes()

            second = self.make_runner(
                root, MockControl(), StatefulMockGateway(), batch_id="batch-two"
            )
            second.run_proof()
            self.assertTrue((
                root / "redacted" / "batch-two" /
                "managed_temporal-summary.json"
            ).is_file())
            self.assertEqual(first_summary, (
                root / "redacted" / "batch-one" /
                "managed_temporal-summary.json"
            ).read_bytes())

            duplicate_gateway = StatefulMockGateway()
            duplicate = self.make_runner(
                root, MockControl(), duplicate_gateway, batch_id="batch-one"
            )
            with self.assertRaisesRegex(RuntimeError, "refusing to overwrite"):
                duplicate.run_proof()
            self.assertEqual([], duplicate_gateway.requests)

    def test_inter_step_delay_applies_only_to_sequential_proof_calls(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runner = self.make_runner(
                root, MockControl(), StatefulMockGateway(),
                batch_id="paced", inter_step_delay_seconds=0.5,
            )
            with patch("policy_lab.managed.sleep") as managed_sleep:
                result = runner.run_proof()
            self.assertTrue(managed_sleep.called)
            self.assertTrue(all(
                call.args == (0.5,) for call in managed_sleep.call_args_list
            ))
            self.assertEqual(0.5, result["inter_step_delay_seconds"])
            self.assertTrue(result["inter_step_delay_applied"])
            event = json.loads((
                root / "private" / "paced" /
                "managed_temporal-events.jsonl"
            ).read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(0.5, event["inter_step_delay_seconds"])

            rate_runner = self.make_runner(
                root, MockControl(), StatefulMockGateway(throttle_after=5),
                batch_id="burst", inter_step_delay_seconds=0.5,
            )
            with patch("policy_lab.managed.sleep") as rate_sleep:
                rate_result = rate_runner.run_rate_limit(settle_seconds=0)
            rate_sleep.assert_not_called()
            self.assertEqual(0.5, rate_result["inter_step_delay_seconds"])
            self.assertFalse(rate_result["inter_step_delay_applied"])

    def test_inter_step_delay_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            for invalid in (-0.1, 2.1, float("inf"), float("nan")):
                with self.subTest(invalid=invalid), self.assertRaisesRegex(
                    ValueError, "between 0 and 2"
                ):
                    self.make_runner(
                        Path(temp), MockControl(), StatefulMockGateway(),
                        inter_step_delay_seconds=invalid,
                    )

    def test_enforcement_gate_stops_before_role_assumption_or_http(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            control = MockControl(enforced=False)
            gateway = StatefulMockGateway()
            with self.assertRaisesRegex(RuntimeError, "active enforcement"):
                self.make_runner(Path(temp), control, gateway).run_proof()
            self.assertEqual([], control.assumed)
            self.assertEqual([], gateway.requests)

    def test_separate_rate_limit_mode_records_throttle(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            control = MockControl()
            gateway = StatefulMockGateway(throttle_after=5)
            result = self.make_runner(Path(temp), control, gateway).run_rate_limit(
                settle_seconds=0
            )
            self.assertEqual(["S12"], result["scenario_ids"])
            self.assertEqual(0, result["expectation_mismatches"])
            events = (
                Path(temp) / "private" / "mockbatch" /
                "gateway_rate_limit-events.jsonl"
            ).read_text(encoding="utf-8")
            self.assertIn('"outcome": "rate_limited"', events)
            rate_events = [json.loads(line) for line in events.splitlines()]
            self.assertTrue(all(
                event["added_authorization_latency_ms"] is None
                and event["policy_responsible"] is None
                for event in rate_events
            ))

    def test_rate_limit_burst_with_denial_is_inconclusive_not_throttled(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            gateway = StatefulMockGateway(deny_after=5)
            result = self.make_runner(
                root, MockControl(), gateway
            ).run_rate_limit(settle_seconds=0)
            self.assertEqual(1, result["expectation_mismatches"])
            with (
                root / "private" / "mockbatch" /
                "gateway_rate_limit-runs.csv"
            ).open(encoding="utf-8", newline="") as handle:
                run = next(csv.DictReader(handle))
            self.assertEqual("inconclusive", run["actual_result"])
            self.assertEqual("False", run["expectation_match"])
            self.assertEqual("5", run["tool_calls_completed"])
            self.assertEqual(
                "concurrent_burst_contaminated:deny", run["stopped_at"]
            )
            events = [json.loads(line) for line in (
                root / "private" / "mockbatch" /
                "gateway_rate_limit-events.jsonl"
            ).read_text(encoding="utf-8").splitlines()]
            self.assertEqual(5, sum(
                event["outcome"] == "success" for event in events
            ))
            self.assertEqual(1, sum(
                event["outcome"] == "deny" for event in events
            ))

    def test_rate_limit_burst_all_success_is_allow_and_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = self.make_runner(
                root, MockControl(), StatefulMockGateway()
            ).run_rate_limit(settle_seconds=0)
            self.assertEqual(1, result["expectation_mismatches"])
            with (
                root / "private" / "mockbatch" /
                "gateway_rate_limit-runs.csv"
            ).open(encoding="utf-8", newline="") as handle:
                run = next(csv.DictReader(handle))
            self.assertEqual("allow", run["actual_result"])
            self.assertEqual("6", run["tool_calls_completed"])

    def test_response_classifier_keeps_throttle_separate_from_denial(self) -> None:
        throttled = HttpResponse(
            429, {"content-type": "application/json"}, b'{"error":"throttled"}'
        )
        denied = HttpResponse(
            403, {"content-type": "application/json"}, b'{"error":"policy denied"}'
        )
        self.assertEqual("rate_limited", classify_response(throttled)[0])
        self.assertEqual("deny", classify_response(denied)[0])

    def test_response_classifier_matches_live_agentcore_json_rpc_shapes(self) -> None:
        policy_denied = HttpResponse(
            200, {"content-type": "application/json"}, json.dumps({
                "jsonrpc": "2.0", "id": "deny",
                "error": {
                    "code": -32002,
                    "message": (
                        "Tool Execution Denied: Tool call not allowed due to "
                        "policy enforcement [No policy applies...]"
                    ),
                },
            }).encode(),
        )
        missing_session = HttpResponse(
            200, {"content-type": "application/json"}, json.dumps({
                "jsonrpc": "2.0", "id": "missing",
                "error": {
                    "code": -32006,
                    "message": (
                        "Tool Execution Denied: Policy Evaluation rejected the "
                        "request as invalid [sessionId is required...]"
                    ),
                },
            }).encode(),
        )
        tool_error = HttpResponse(
            200, {"content-type": "application/json"}, json.dumps({
                "jsonrpc": "2.0", "id": "tool",
                "result": {
                    "isError": True,
                    "content": [{
                        "type": "text", "text": "An internal error occurred",
                    }],
                },
            }).encode(),
        )
        unknown_error = HttpResponse(
            200, {"content-type": "application/json"}, json.dumps({
                "jsonrpc": "2.0", "id": "unknown",
                "error": {"code": -32000, "message": "unexpected gateway error"},
            }).encode(),
        )
        declared_failure = mcp_success("failed", {
            "operation_id": "op-failed",
            "record_id": "record-a",
            "change_id": "change-failed",
            "approval_id": "approval-failed",
            "status": "FAILED",
        })

        self.assertEqual("deny", classify_response(policy_denied)[0])
        self.assertEqual("validation_error", classify_response(missing_session)[0])
        self.assertEqual("tool_error", classify_response(tool_error)[0])
        failure_outcome, _, failure_response = classify_response(declared_failure)
        self.assertEqual("tool_error", failure_outcome)
        self.assertEqual("FAILED", failure_response["status"])
        self.assertEqual("transport_error", classify_response(unknown_error)[0])

    def test_transport_error_cannot_be_reported_as_allow(self) -> None:
        class UnknownErrorGateway:
            def send(self, url, headers, body):
                request_id = json.loads(body)["id"]
                return HttpResponse(
                    200, {"content-type": "application/json"}, json.dumps({
                        "jsonrpc": "2.0", "id": request_id,
                        "error": {
                            "code": -32000,
                            "message": "unexpected gateway error",
                        },
                    }).encode(),
                )

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = self.make_runner(
                root, MockControl(), UnknownErrorGateway()
            ).run_proof()
            self.assertGreater(result["expectation_mismatches"], 0)
            with (
                root / "redacted" / "mockbatch" /
                "managed_temporal-comparison.csv"
            ).open(encoding="utf-8", newline="") as handle:
                comparison = list(csv.DictReader(handle))
            self.assertTrue(comparison)
            self.assertTrue(all(
                row["actual_results"] == "transport_error" for row in comparison
            ))

    def test_hard_repetition_limit_is_ten(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "between 1 and 10"):
                self.make_runner(
                    Path(temp), MockControl(), StatefulMockGateway(), repetitions=11
                )

    def test_cli_defaults_to_plan_without_any_aws_process(self) -> None:
        argv = [
            "run_agentcore_managed.py", "proof", "--region", "us-east-1",
            "--repetitions", "10", "--inter-step-delay-seconds", "0.5",
        ]
        with patch.object(sys, "argv", argv), patch(
            "run_agentcore_managed.subprocess.run"
        ) as subprocess_run, patch("builtins.print") as output:
            self.assertEqual(0, run_agentcore_managed.main())
        subprocess_run.assert_not_called()
        plan = json.loads(output.call_args.args[0])
        self.assertEqual(0.5, plan["inter_step_delay_seconds"])

    def test_cli_plan_targets_s08_and_recomputes_request_budget(self) -> None:
        argv = [
            "run_agentcore_managed.py", "proof", "--region", "us-east-1",
            "--scenario-id", "S08", "--repetitions", "10", "--delay", "1",
        ]
        with patch.object(sys, "argv", argv), patch(
            "run_agentcore_managed.subprocess.run"
        ) as subprocess_run, patch("builtins.print") as output:
            self.assertEqual(0, run_agentcore_managed.main())
        subprocess_run.assert_not_called()
        plan = json.loads(output.call_args.args[0])
        self.assertEqual(["S08"], plan["scenario_ids"])
        self.assertEqual(66, plan["maximum_candidate_requests"])
        self.assertEqual(1.0, plan["inter_step_delay_seconds"])

    def test_scenario_filter_is_proof_only_and_runner_rejects_nonproof_ids(self) -> None:
        argv = [
            "run_agentcore_managed.py", "rate-limit", "--region", "us-east-1",
            "--scenario-id", "S08",
        ]
        with patch.object(sys, "argv", argv), self.assertRaisesRegex(
            SystemExit, "valid only in proof mode"
        ):
            run_agentcore_managed.main()
        with tempfile.TemporaryDirectory() as temp, self.assertRaisesRegex(
            ValueError, "within S01-S11"
        ):
            self.make_runner(
                Path(temp), MockControl(), StatefulMockGateway(),
                scenario_ids=("S12",),
            )

    def test_aws_cli_control_resolves_outputs_and_keeps_credentials_ephemeral(self) -> None:
        stack = {
            "Stacks": [{
                "Outputs": [
                    {"OutputKey": "GatewayUrl", "OutputValue": "https://g/mcp"},
                    {"OutputKey": "GatewayIdentifier", "OutputValue": "gw"},
                    {"OutputKey": "PolicyEngineId", "OutputValue": "engine"},
                    {"OutputKey": "PrimaryCallerRoleArn", "OutputValue": "arn:primary"},
                    {"OutputKey": "SecondaryCallerRoleArn", "OutputValue": "arn:secondary"},
                ],
                "Parameters": [
                    {"ParameterKey": "PolicyEngineMode", "ParameterValue": "ENFORCE"},
                    {"ParameterKey": "PolicyEnforcementMode", "ParameterValue": "ACTIVE"},
                ],
            }]
        }
        assumed = {
            "Credentials": {
                "AccessKeyId": "access", "SecretAccessKey": "secret",
                "SessionToken": "token", "Expiration": "later",
            }
        }
        control = AwsCliControl()
        with patch.object(control, "_json", side_effect=[stack, assumed]) as aws_json:
            config = control.resolve_stack("stack", "us-east-1")
            credentials = control.assume_role("arn:primary", "session", "us-east-1")
        self.assertEqual("https://g/mcp", config.gateway_url)
        self.assertEqual("ENFORCE", config.engine_mode)
        self.assertNotIn("secret", repr(credentials))
        self.assertEqual(2, aws_json.call_count)

    def test_rate_readiness_uses_cloudformation_not_unsupported_control_command(self) -> None:
        control = AwsCliControl()
        config = MockControl().resolve_stack("stack", "us-east-1")
        responses = [
            {"status": "READY"},
            {"Stacks": [{"StackStatus": "CREATE_COMPLETE"}]},
            {"StackResources": [{
                "LogicalResourceId": "SyntheticPerToolLimit",
                "ResourceType": "AWS::BedrockAgentCore::GatewayRateLimit",
                "ResourceStatus": "CREATE_COMPLETE",
            }]},
        ]
        with patch.object(control, "_json", side_effect=responses) as aws_json:
            state = control.confirm_rate_limit(
                config, "us-east-1", "custom-rate-stack"
            )
        calls = [item.args[0] for item in aws_json.call_args_list]
        serialized = json.dumps(calls)
        self.assertNotIn("list-gateway-rate-limits", serialized)
        self.assertIn("describe-stacks", serialized)
        self.assertIn("describe-stack-resources", serialized)
        self.assertEqual(
            "CREATE_COMPLETE",
            state["rate_resources"]["StackResources"][0]["ResourceStatus"],
        )

    def test_rate_readiness_accepts_update_complete_stack_and_resource(self) -> None:
        control = AwsCliControl()
        config = MockControl().resolve_stack("stack", "us-east-1")
        responses = [
            {"status": "READY"},
            {"Stacks": [{"StackStatus": "UPDATE_COMPLETE"}]},
            {"StackResources": [{
                "LogicalResourceId": "AnyLogicalIdIsAccepted",
                "ResourceType": "AWS::BedrockAgentCore::GatewayRateLimit",
                "ResourceStatus": "UPDATE_COMPLETE",
            }]},
        ]
        with patch.object(control, "_json", side_effect=responses):
            state = control.confirm_rate_limit(
                config, "us-east-1", "custom-rate-stack"
            )
        self.assertEqual(
            "UPDATE_COMPLETE", state["rate_stack"]["Stacks"][0]["StackStatus"]
        )

    def test_rate_readiness_rejects_in_progress_and_rollback_states(self) -> None:
        config = MockControl().resolve_stack("stack", "us-east-1")
        for stack_status in ("UPDATE_IN_PROGRESS", "UPDATE_ROLLBACK_COMPLETE"):
            with self.subTest(stack_status=stack_status):
                control = AwsCliControl()
                with patch.object(control, "_json", side_effect=[
                    {"status": "READY"},
                    {"Stacks": [{"StackStatus": stack_status}]},
                ]), self.assertRaisesRegex(
                    RuntimeError, "CREATE_COMPLETE or UPDATE_COMPLETE"
                ):
                    control.confirm_rate_limit(
                        config, "us-east-1", "custom-rate-stack"
                    )

    def test_rate_readiness_requires_exactly_one_gateway_rate_limit_resource(self) -> None:
        config = MockControl().resolve_stack("stack", "us-east-1")
        valid = {
            "LogicalResourceId": "SyntheticPerToolLimit",
            "ResourceType": "AWS::BedrockAgentCore::GatewayRateLimit",
            "ResourceStatus": "UPDATE_COMPLETE",
        }
        resource_sets = (
            [],
            [valid, {**valid, "LogicalResourceId": "SecondRateLimit"}],
            [{
                "LogicalResourceId": "UnrelatedResource",
                "ResourceType": "AWS::DynamoDB::Table",
                "ResourceStatus": "CREATE_COMPLETE",
            }],
        )
        for resources in resource_sets:
            with self.subTest(resources=resources):
                control = AwsCliControl()
                with patch.object(control, "_json", side_effect=[
                    {"status": "READY"},
                    {"Stacks": [{"StackStatus": "UPDATE_COMPLETE"}]},
                    {"StackResources": resources},
                ]), self.assertRaisesRegex(
                    RuntimeError, "exactly one stable"
                ):
                    control.confirm_rate_limit(
                        config, "us-east-1", "custom-rate-stack"
                    )
        for resource_status in (
            "UPDATE_IN_PROGRESS", "UPDATE_ROLLBACK_COMPLETE"
        ):
            with self.subTest(resource_status=resource_status):
                control = AwsCliControl()
                with patch.object(control, "_json", side_effect=[
                    {"status": "READY"},
                    {"Stacks": [{"StackStatus": "UPDATE_COMPLETE"}]},
                    {"StackResources": [{
                        "LogicalResourceId": "SyntheticPerToolLimit",
                        "ResourceType": "AWS::BedrockAgentCore::GatewayRateLimit",
                        "ResourceStatus": resource_status,
                    }]},
                ]), self.assertRaisesRegex(
                    RuntimeError, "CREATE_COMPLETE or UPDATE_COMPLETE"
                ):
                    control.confirm_rate_limit(
                        config, "us-east-1", "custom-rate-stack"
                    )

    def test_live_enforcement_gate_requires_complete_active_policy_inventory(self) -> None:
        control = AwsCliControl()
        config = MockControl().resolve_stack("stack", "us-east-1")
        responses = [
            {
                "status": "READY",
                "policyEngineConfiguration": {"mode": "ENFORCE"},
            },
            {"status": "ACTIVE"},
            {"policySummaries": self.active_policy_items()},
        ]
        with patch.object(control, "_json", side_effect=responses):
            state = control.confirm_enforcement(config, "us-east-1")
        self.assertEqual(12, len(state["policies"]["policySummaries"]))

    def test_live_enforcement_gate_rejects_missing_policy(self) -> None:
        control = AwsCliControl()
        config = MockControl().resolve_stack("stack", "us-east-1")
        responses = [
            {"status": "READY", "policyEngineConfiguration": {"mode": "ENFORCE"}},
            {"status": "ACTIVE"},
            {"policySummaries": self.active_policy_items()[:-1]},
        ]
        with patch.object(control, "_json", side_effect=responses):
            with self.assertRaisesRegex(RuntimeError, "missing expected policies"):
                control.confirm_enforcement(config, "us-east-1")

    def test_live_enforcement_gate_rejects_stale_or_mixed_policy_mode(self) -> None:
        control = AwsCliControl()
        config = MockControl().resolve_stack("stack", "us-east-1")
        policies = self.active_policy_items()
        policies[3] = {**policies[3], "status": "UPDATING"}
        policies[4] = {**policies[4], "enforcementMode": "LOG_ONLY"}
        responses = [
            {"status": "READY", "policyEngineConfiguration": {"mode": "ENFORCE"}},
            {"status": "ACTIVE"},
            {"policySummaries": policies},
        ]
        with patch.object(control, "_json", side_effect=responses):
            with self.assertRaisesRegex(RuntimeError, "every returned policy ACTIVE"):
                control.confirm_enforcement(config, "us-east-1")

    def test_live_enforcement_gate_rejects_gateway_log_only_or_stale_engine(self) -> None:
        control = AwsCliControl()
        config = MockControl().resolve_stack("stack", "us-east-1")
        with patch.object(control, "_json", side_effect=[
            {"status": "READY", "policyEngineConfiguration": {"mode": "LOG_ONLY"}},
            {"status": "ACTIVE"},
            {"policySummaries": self.active_policy_items()},
        ]):
            with self.assertRaisesRegex(RuntimeError, "Gateway policy mode ENFORCE"):
                control.confirm_enforcement(config, "us-east-1")
        with patch.object(control, "_json", side_effect=[
            {"status": "READY", "policyEngineConfiguration": {"mode": "ENFORCE"}},
            {"status": "UPDATING"},
            {"policySummaries": self.active_policy_items()},
        ]):
            with self.assertRaisesRegex(RuntimeError, "Policy Engine status ACTIVE"):
                control.confirm_enforcement(config, "us-east-1")


if __name__ == "__main__":
    unittest.main()
