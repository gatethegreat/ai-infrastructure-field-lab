from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path
import re
import sys
import unittest


EXPERIMENT = Path(__file__).resolve().parents[1]
INFRA = EXPERIMENT / "infrastructure"
TEMPLATE = INFRA / "agentcore-policy-lab.yaml"
RATE_LIMIT_TEMPLATE = INFRA / "agentcore-rate-limit.yaml"
sys.path.insert(0, str(EXPERIMENT))

from policy_lab.contracts import Change  # noqa: E402


class CloudPlanningAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.template = TEMPLATE.read_text(encoding="utf-8")
        cls.rate_limit_template = RATE_LIMIT_TEMPLATE.read_text(encoding="utf-8")

    def test_cloudformation_uses_supported_resource_types(self) -> None:
        required = {
            "AWS::BedrockAgentCore::Gateway",
            "AWS::BedrockAgentCore::GatewayTarget",
            "AWS::BedrockAgentCore::PolicyEngine",
            "AWS::BedrockAgentCore::Policy",
            "AWS::Lambda::Function",
        }
        for resource_type in required:
            self.assertIn(resource_type, self.template)
        self.assertNotIn("terraform", self.template.lower())

    def test_gateway_is_authenticated_and_defaults_to_observation(self) -> None:
        self.assertIn("AuthorizerType: AWS_IAM", self.template)
        self.assertRegex(
            self.template,
            r"PolicyEngineMode:\s+Type: String\s+Default: LOG_ONLY",
        )
        self.assertRegex(
            self.template,
            r"PolicyEnforcementMode:\s+Type: String\s+Default: LOG_ONLY",
        )

    def test_all_synthetic_tools_are_in_lambda_schema(self) -> None:
        for name in (
            "lookup_record",
            "record_human_approval",
            "execute_write",
            "get_operation_status",
        ):
            self.assertIn(f"Name: {name}", self.template)
            self.assertIn(f'if tool == "{name}"', self.template)

    def test_cloud_records_match_lowercase_local_fixture_boundary(self) -> None:
        for letter in "abcd":
            self.assertIn(
                f'"record-{letter}": {{"record_id": "record-{letter}", "value": "synthetic-{letter}"}}',
                self.template,
            )
            self.assertNotIn(f'"record-{letter.upper()}"', self.template)

    def test_lambda_has_bounded_concurrency_and_owned_logs(self) -> None:
        self.assertIn("ReservedConcurrentExecutions: 2", self.template)
        self.assertIn("Type: AWS::Logs::LogGroup", self.template)
        self.assertIn("LogGroupName: !Sub /aws/lambda/${SyntheticToolsFunction}", self.template)
        self.assertIn("RetentionInDays: 7", self.template)

    def test_lambda_returns_schema_valid_domain_failure_without_success_effect(self) -> None:
        self.assertIn(
            'status = "FAILED" if change.get("force_error", False) else "SUCCEEDED"',
            self.template,
        )
        self.assertNotIn('raise RuntimeError("injected synthetic write failure")', self.template)
        self.assertIn('if status == "SUCCEEDED":', self.template)
        self.assertIn('operation["value"] = change["value"]', self.template)
        self.assertIn('TABLE.put_item(Item=operation)', self.template)
        self.assertGreaterEqual(self.template.count('"status": status'), 2)

    def test_temporal_policy_has_required_boundaries(self) -> None:
        self.assertIn("when temporal", self.template)
        self.assertIn('formerly within 10m AgentCore::Action::"SyntheticTools___lookup_record"::response', self.template)
        self.assertIn("output.record_id: context.input.record_id", self.template)
        self.assertIn(
            "input.approval_id: context.input.change.approval_id", self.template
        )
        self.assertIn(
            "output.approval_id: context.input.change.approval_id", self.template
        )
        self.assertIn("output.valid: true", self.template)
        self.assertIn("since within 5m", self.template)
        self.assertEqual(4, self.template.count('output.status: "SUCCEEDED"'))
        self.assertEqual(2, self.template.count('output.status: "FAILED"'))
        self.assertNotIn(
            "input.change.change_id: context.input.change.change_id", self.template
        )
        self.assertIn("${SessionWriteLimit}", self.template)
        self.assertIn("${RetryLimit}", self.template)
        self.assertEqual(2, self.template.count("successfulWrites >= ${SessionWriteLimit}"))
        self.assertEqual(2, self.template.count("sameChangeResponses >= ${RetryLimit}"))
        self.assertNotIn('SyntheticTools___execute_write"::request{', self.template)
        self.assertNotIn('SyntheticTools___execute_write"::error{', self.template)
        self.assertEqual(4, self.template.count("forbid ("))
        self.assertNotRegex(
            self.template,
            r"permit \([^;]+SyntheticTools___execute_write[^;]+\);",
        )

    def test_every_permit_is_scoped_to_one_generated_caller_role(self) -> None:
        primary = (
            'principal == AgentCore::IamEntity::"arn:${AWS::Partition}:sts::'
            '${AWS::AccountId}:assumed-role/${PrimaryCallerRole}"'
        )
        secondary = (
            'principal == AgentCore::IamEntity::"arn:${AWS::Partition}:sts::'
            '${AWS::AccountId}:assumed-role/${SecondaryCallerRole}"'
        )
        self.assertEqual(6, self.template.count(primary))
        self.assertEqual(6, self.template.count(secondary))
        permit_blocks = re.findall(r"permit \((.*?)\)\s*(?:when temporal \{.*?\})?;", self.template, re.DOTALL)
        self.assertEqual(8, len(permit_blocks))
        for block in permit_blocks:
            self.assertTrue(primary in block or secondary in block)
            self.assertNotIn("principal is AgentCore::IamEntity", block)

    def test_each_agentcore_policy_resource_has_exactly_one_statement(self) -> None:
        resources = re.findall(
            r"^  ([A-Za-z0-9]+):\n(.*?)(?=^  [A-Za-z0-9]+:|^Outputs:)",
            self.template,
            re.MULTILINE | re.DOTALL,
        )
        policy_resources = {
            name: body
            for name, body in resources
            if "Type: AWS::BedrockAgentCore::Policy\n" in body
        }
        self.assertEqual(
            {
                "LookupPrimaryPolicy",
                "LookupSecondaryPolicy",
                "ApprovalPrimaryPolicy",
                "ApprovalSecondaryPolicy",
                "StatusPrimaryPolicy",
                "StatusSecondaryPolicy",
                "TemporalWritePrimaryPolicy",
                "TemporalWriteSecondaryPolicy",
                "SessionWriteLimitPrimaryPolicy",
                "SessionWriteLimitSecondaryPolicy",
                "RetryLimitPrimaryPolicy",
                "RetryLimitSecondaryPolicy",
            },
            set(policy_resources),
        )
        for name, body in policy_resources.items():
            statements = re.findall(r"^\s+(?:permit|forbid) \(", body, re.MULTILINE)
            self.assertEqual(1, len(statements), name)
            self.assertEqual(1, body.count("Statement: !Sub |"), name)
            self.assertIn("SyntheticToolsTarget", body, name)
            self.assertIn("ValidationMode: FAIL_ON_ANY_FINDINGS", body, name)

    def test_caller_forbids_are_ordered_after_matching_temporal_permit(self) -> None:
        resources = dict(
            re.findall(
                r"^  ([A-Za-z0-9]+):\n(.*?)(?=^  [A-Za-z0-9]+:|^Outputs:)",
                self.template,
                re.MULTILINE | re.DOTALL,
            )
        )
        for caller in ("Primary", "Secondary"):
            for boundary in ("SessionWriteLimit", "RetryLimit"):
                body = resources[f"{boundary}{caller}Policy"]
                self.assertIn("- SyntheticToolsTarget", body)
                self.assertIn(f"- TemporalWrite{caller}Policy", body)
                self.assertIn(
                    f"assumed-role/${{{caller}CallerRole}}", body
                )

            retry = resources[f"RetryLimit{caller}Policy"]
            self.assertEqual(1, retry.count("count for"))
            self.assertEqual(1, retry.count("formerly within 1h"))
            self.assertEqual(1, retry.count('execute_write"::response'))
            self.assertIn(
                "output.approval_id: context.input.change.approval_id", retry
            )
            self.assertIn('output.status: "FAILED"', retry)
            self.assertIn("sameChangeResponses >= ${RetryLimit}", retry)
            self.assertNotIn('execute_write"::request', retry)
            self.assertNotIn('execute_write"::error', retry)

        for caller in ("Primary", "Secondary"):
            permit = resources[f"TemporalWrite{caller}Policy"]
            self.assertEqual(1, permit.count("formerly within 10m"))
            self.assertEqual(1, permit.count("since within 5m"))
            self.assertEqual(1, permit.count('execute_write"::response'))
            self.assertIn('output.status: "SUCCEEDED"', permit)
            self.assertNotIn("count for", permit)

            session_cap = resources[f"SessionWriteLimit{caller}Policy"]
            self.assertIn('output.status: "SUCCEEDED"', session_cap)
            self.assertNotIn('output.status: "FAILED"', session_cap)

    def test_cloud_schema_matches_local_change_contract(self) -> None:
        expected_fields = {field.name for field in fields(Change)}
        self.assertEqual(
            {"change_id", "approval_id", "value", "force_error"}, expected_fields
        )
        change_schema = re.search(
            r"change:\s+Type: object\s+Properties:(.*?)Required: \[change_id, approval_id, value\]",
            self.template,
            re.DOTALL,
        )
        self.assertIsNotNone(change_schema)
        assert change_schema is not None
        cloud_fields = set(re.findall(r"^\s{26}([a-z_]+):", change_schema.group(1), re.MULTILINE))
        self.assertEqual(expected_fields, cloud_fields)

    def test_rate_limit_is_separate_cloudformation_stack_and_matches_mirror(self) -> None:
        path = EXPERIMENT / "policies" / "gateway" / "rate-limit.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(1, len(payload))
        self.assertEqual(["toolName"], payload[0]["dimensionKeys"])
        entry = payload[0]["entries"][0]
        self.assertEqual(set(payload[0]["dimensionKeys"]), set(entry["dimensions"]))
        self.assertGreater(entry["requests"][0]["rate"], 0)
        self.assertNotIn("AWS::BedrockAgentCore::GatewayRateLimit", self.template)
        self.assertIn(
            "Type: AWS::BedrockAgentCore::GatewayRateLimit",
            self.rate_limit_template,
        )
        for dimension in payload[0]["dimensionKeys"]:
            self.assertIn(dimension, self.rate_limit_template)
        self.assertIn("Period: second", self.rate_limit_template)
        self.assertNotIn("$.context.iam.principal", self.rate_limit_template)
        self.assertNotIn("$.context.iam.principal", path.read_text(encoding="utf-8"))

    def test_scripts_require_explicit_mutation_switches(self) -> None:
        deploy = (INFRA / "deploy.ps1").read_text(encoding="utf-8")
        teardown = (INFRA / "teardown.ps1").read_text(encoding="utf-8")
        verify = (INFRA / "verify.ps1").read_text(encoding="utf-8")
        redact = (INFRA / "redact.ps1").read_text(encoding="utf-8")
        publicize = (INFRA / "publicize_evidence.py").read_text(encoding="utf-8")
        self.assertIn("[switch]$Apply", deploy)
        self.assertIn("[switch]$ApplyRateLimit", deploy)
        self.assertIn("if (-not $Apply -and -not $ApplyRateLimit)", deploy)
        self.assertIn("agentcore-rate-limit.yaml", deploy)
        self.assertNotIn("batch-put-gateway-rate-limits", deploy)
        self.assertIn("if (-not $Apply)", teardown)
        self.assertIn("'delete-stack', '--stack-name', $RateLimitStackName", teardown)
        self.assertIn("function Invoke-AwsChecked", verify)
        self.assertEqual(1, len(re.findall(r"& aws", verify)))
        self.assertIn("Required GatewayIdentifier or PolicyEngineId output is missing", verify)
        self.assertNotIn("list-gateway-rate-limits", verify)
        rate_limit_verify = re.search(
            r"if \(\$IncludeRateLimit\) \{(.*?)\n\}", verify, re.DOTALL
        )
        self.assertIsNotNone(rate_limit_verify)
        assert rate_limit_verify is not None
        self.assertIn("'cloudformation', 'describe-stacks'", rate_limit_verify.group(1))
        self.assertIn(
            "'cloudformation', 'describe-stack-resources'",
            rate_limit_verify.group(1),
        )
        self.assertNotIn("bedrock-agentcore-control", rate_limit_verify.group(1))
        self.assertIn("function Assert-AwsNotFound", teardown)
        self.assertIn("SyntheticToolsFunctionName", teardown)
        self.assertIn("SyntheticToolsLogGroupName", teardown)
        self.assertIn("get-gateway", teardown)
        self.assertIn("get-policy-engine", teardown)
        self.assertIn("get-function", teardown)
        self.assertIn("describe-table", teardown)
        self.assertIn("get-role", teardown)
        self.assertIn("describe-stack-resources", teardown)
        self.assertIn("PhysicalResourceId", teardown)
        self.assertIn("$captured.ContainsKey", teardown)
        self.assertIn("$captured.PolicyEngineId -match '^arn:'", teardown)
        self.assertIn(".Split('/')[-1]", teardown)
        self.assertNotIn("Required teardown output is missing", teardown)
        self.assertNotIn("list-gateways", teardown)
        self.assertIn("if (-not $Apply)", redact)
        self.assertIn("evidence\\cloud\\redacted-candidate", redact)
        self.assertIn("input and output directories must differ", publicize)
        self.assertIn("session_replacements", publicize)
        self.assertIn("identifier categories overlap", publicize)
        self.assertIn("source_values_included", publicize)

    def test_committed_assets_contain_no_account_ids_or_credentials(self) -> None:
        account_id = re.compile(r"(?<![0-9])[0-9]{12}(?![0-9])")
        access_key = re.compile(r"(?:AKIA|ASIA)[A-Z0-9]{16}")
        for path in [*INFRA.rglob("*"), EXPERIMENT / "policies/gateway/rate-limit.json"]:
            if not path.is_file() or path.suffix not in {".md", ".yaml", ".json", ".ps1"}:
                continue
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(account_id.search(text), path)
            self.assertIsNone(access_key.search(text), path)

    def test_redaction_rules_cover_sensitive_managed_evidence(self) -> None:
        rules = json.loads(
            (INFRA / "redaction-rules.json").read_text(encoding="utf-8")
        )
        names = {item["name"] for item in rules["patterns"]}
        self.assertTrue(
            {
                "aws-account-id",
                "aws-arn",
                "authorization-header",
                "security-token",
                "access-key-id",
                "policy-session-header-json",
                "policy-session-header",
                "mcp-session-header",
                "generic-session-json",
                "generic-session-field",
                "workload-access-token",
            }.issubset(names)
        )
        by_name = {item["name"]: item["regex"] for item in rules["patterns"]}
        self.assertRegex("mcp-session-id: mcp-session-123", by_name["mcp-session-header"])
        self.assertRegex(
            '{"sessionId":"generic-session-123"}', by_name["generic-session-json"]
        )
        self.assertRegex(
            "policy_session_id=generic-session-456", by_name["generic-session-field"]
        )

    def test_cost_template_requires_current_values(self) -> None:
        estimate = json.loads(
            (INFRA / "cost-estimate.template.json").read_text(encoding="utf-8")
        )
        self.assertEqual("<APPROVED_REGION>", estimate["region"])
        self.assertGreaterEqual(len(estimate["line_items"]), 5)
        self.assertIn("<SUM_LINE_ITEMS>", estimate["estimated_total"])


if __name__ == "__main__":
    unittest.main()
