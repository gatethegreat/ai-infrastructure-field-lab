import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DOGWOOD = ROOT / "experiments" / "06-strands-agentcore" / "policies" / "dogwood"
DOCKERFILE = ROOT / "experiments" / "06-strands-agentcore" / "docker" / "Dockerfile.dogwood"
EXPECTED_SHA = "c6237c88099b3f492ecc5fcee42df06a19224b97"


class DogwoodAssetTests(unittest.TestCase):
    def test_dogwood_source_and_images_are_immutable(self):
        self.assertEqual((DOGWOOD / "DOGWOOD_SHA").read_text().strip(), EXPECTED_SHA)
        dockerfile = DOCKERFILE.read_text()
        self.assertIn(f"ARG DOGWOOD_SHA={EXPECTED_SHA}", dockerfile)
        self.assertIn("/usr/share/licenses/dogwood/LICENSE", dockerfile)
        self.assertIn("/usr/share/licenses/dogwood/NOTICE", dockerfile)
        from_lines = [line for line in dockerfile.splitlines() if line.startswith("FROM ")]
        self.assertEqual(len(from_lines), 2)
        for line in from_lines:
            self.assertRegex(line, r"@sha256:[0-9a-f]{64}(?: AS builder)?$")

    def test_manifest_has_exact_synthetic_tool_contract(self):
        manifest = json.loads((DOGWOOD / "tools.json").read_text())
        self.assertEqual(
            [tool["name"] for tool in manifest],
            [
                "lookup_record",
                "record_human_approval",
                "execute_write",
                "get_operation_status",
            ],
        )
        for tool in manifest:
            self.assertFalse(tool["inputSchema"]["additionalProperties"])
            self.assertFalse(tool["outputSchema"]["additionalProperties"])
        write_tool = next(tool for tool in manifest if tool["name"] == "execute_write")
        change = write_tool["inputSchema"]["properties"]["change"]
        self.assertEqual(change["type"], "object")
        self.assertEqual(change["required"], ["change_id", "approval_id", "value"])
        self.assertFalse(change["additionalProperties"])
        self.assertEqual(
            write_tool["outputSchema"]["required"],
            ["operation_id", "record_id", "change_id", "approval_id", "status"],
        )

    def test_event_history_is_pinned_to_caller_and_session(self):
        schema = (DOGWOOD / "events.dwschema").read_text()
        self.assertEqual(schema.count("pin callerPrincipal"), 3)
        self.assertEqual(schema.count("pin sessionId"), 3)
        self.assertIn("= principal", schema)
        self.assertIn("= context.sessionId", schema)

    def test_temporal_controls_are_explicit(self):
        policy = (DOGWOOD / "policies.dw").read_text()
        self.assertIn('formerly within 10m Drupe::Action::"lookup_record"::response', policy)
        self.assertIn('record_human_approval"::response', policy)
        self.assertIn("output.record_id: context.input.record_id", policy)
        self.assertIn("output.approval_id: context.input.change.approval_id", policy)
        self.assertIn("input.change.approval_id: context.input.change.approval_id", policy)
        self.assertIn("formerly within 5m", policy)
        self.assertIn("since within 5m", policy)
        self.assertNotIn('execute_write"::error', policy)
        self.assertNotIn("input.change.change_id: context.input.change.change_id", policy)
        self.assertGreaterEqual(
            policy.count("output.approval_id: context.input.change.approval_id"), 3
        )
        self.assertEqual(policy.count('output.status: "SUCCEEDED"'), 2)
        self.assertEqual(policy.count('output.status: "FAILED"'), 1)
        self.assertGreaterEqual(policy.count("n >= 3"), 2)
        self.assertNotIn("n >= 2", policy)

    def test_every_trace_has_an_expected_verdict_sequence(self):
        expected = json.loads((DOGWOOD / "expected_verdicts.json").read_text())
        traces = sorted(path.name for path in (DOGWOOD / "traces").glob("*.log"))
        self.assertEqual(sorted(expected), traces)
        self.assertEqual(expected["06_retry_cap.log"], ["allow", "allow", "allow", "deny"])
        self.assertEqual(expected["09_wrong_approval_id.log"], ["deny"])
        for verdicts in expected.values():
            self.assertTrue(verdicts)
            self.assertTrue(set(verdicts) <= {"allow", "deny"})

    def test_retry_trace_uses_declared_domain_failure_responses(self):
        trace = (DOGWOOD / "traces" / "06_retry_cap.log").read_text()
        self.assertEqual(trace.count('execute_write"::response'), 3)
        self.assertEqual(trace.count('status: "FAILED"'), 3)
        for change_id in ("change-initial", "change-retry-1", "change-retry-2", "change-retry-3"):
            self.assertIn(f'change_id: "{change_id}"', trace)
        self.assertEqual(trace.count('approval_id: "approval-001"'), 16)
        self.assertNotIn('execute_write"::error', trace)

        success_traces = "\n".join(
            (DOGWOOD / "traces" / name).read_text()
            for name in ("01_happy_and_single_use.log", "07_success_cap.log")
        )
        self.assertEqual(success_traces.count('status: "SUCCEEDED"'), 4)

    def test_assets_contain_no_account_numbers_or_secret_material(self):
        forbidden = [
            re.compile(r"\b\d{12}\b"),
            re.compile(r"AKIA[0-9A-Z]{16}"),
            re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        ]
        for path in DOGWOOD.rglob("*"):
            if not path.is_file():
                continue
            text = path.read_text(errors="ignore")
            for pattern in forbidden:
                self.assertIsNone(pattern.search(text), f"sensitive pattern in {path}")


if __name__ == "__main__":
    unittest.main()
