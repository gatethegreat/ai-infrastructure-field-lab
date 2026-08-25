from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
CLOUD = ROOT / "experiments" / "06-strands-agentcore" / "evidence" / "cloud" / "redacted"
AWS_REQUEST_ALIAS = re.compile(r"^aws-request-\d{6}$")
MCP_REQUEST_ALIAS = re.compile(r"^mcp-request-\d{6}$")
CLOUD_OPERATION_ALIAS = re.compile(r"^cloud-operation-\d{6}$")
CLOUD_RESOURCE_ALIAS = re.compile(r"^cloud-resource-\d{6}$")
GATEWAY_ALIAS = re.compile(r"^gateway-\d{6}$")
POLICY_ENGINE_ALIAS = re.compile(r"^policy-engine-\d{6}$")
GATEWAY_URL_ALIAS = re.compile(
    r"^https://gateway-\d{6}\.example\.invalid/mcp$"
)
UUID_VALUE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}"
)
ISO_TIMESTAMP = re.compile(
    r"(?P<year>\d{4})-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})"
)


def tracked_files() -> list[Path]:
    output = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
    ).decode("utf-8")
    return [ROOT / item for item in output.split("\0") if item]


class PublicReleaseSafetyTests(unittest.TestCase):
    @staticmethod
    def key_values(value: object):
        if isinstance(value, dict):
            for key, item in value.items():
                yield key, item
                yield from PublicReleaseSafetyTests.key_values(item)
        elif isinstance(value, list):
            for item in value:
                yield from PublicReleaseSafetyTests.key_values(item)

    def test_public_cloud_json_is_valid(self) -> None:
        for path in CLOUD.rglob("*.json"):
            json.loads(path.read_text(encoding="utf-8"))
        for path in CLOUD.rglob("*.jsonl"):
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                with self.subTest(path=path, line=line_number):
                    json.loads(line)

    def test_public_events_use_only_safe_aliases_and_placeholders(self) -> None:
        event_count = 0
        for path in CLOUD.rglob("*events.jsonl"):
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                event_count += 1
                event = json.loads(line)
                self.assertEqual(event["session_id"], "<REDACTED_SESSION>")
                self.assertRegex(event["request_id"], MCP_REQUEST_ALIAS)
                if event.get("aws_request_id") is not None:
                    self.assertRegex(event["aws_request_id"], AWS_REQUEST_ALIAS)

                headers = event.get("response_headers", {})
                session_header = headers.get(
                    "x-amzn-bedrock-agentcore-policy-session-id"
                )
                if session_header is not None:
                    self.assertEqual(session_header, "<REDACTED_SESSION>")
                aws_header = headers.get("x-amzn-requestid")
                if aws_header is not None:
                    self.assertRegex(aws_header, AWS_REQUEST_ALIAS)
                    self.assertEqual(aws_header, event["aws_request_id"])
                self.assertNotIn("date", {key.lower() for key in headers})

                parsed = event.get("parsed_response")
                if parsed is not None:
                    self.assertEqual(
                        json.loads(event["raw_response_body"]), parsed
                    )
                    if isinstance(parsed.get("id"), str):
                        self.assertEqual(parsed["id"], event["request_id"])
                self.assertEqual(
                    event["public_redaction"],
                    {
                        "payload_classification": "synthetic",
                        "timestamp_basis": "synthetic_shift",
                        "version": "1.0",
                    },
                )
        self.assertEqual(event_count, 1155)

    def test_public_cloud_uses_only_synthetic_exact_timestamps(self) -> None:
        for path in CLOUD.rglob("*"):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            for match in ISO_TIMESTAMP.finditer(text):
                with self.subTest(path=path):
                    self.assertEqual(match.group("year"), "2000")

    def test_public_projection_manifest_proves_evidence_invariants(self) -> None:
        manifest = json.loads(
            (CLOUD / "public-redaction-manifest.json").read_text(encoding="utf-8")
        )
        self.assertFalse(manifest["source_values_included"])
        checks = manifest["event_projection_checks"]
        self.assertEqual(len(checks), 5)
        self.assertEqual(sum(item["events"] for item in checks.values()), 1155)
        for item in checks.values():
            self.assertTrue(item["match"])
            self.assertEqual(item["source_sha256"], item["public_sha256"])

        transformations = manifest["transformations"]
        self.assertIn("cloud_operation_identifiers", transformations)
        self.assertIn("cloud_resource_identifiers", transformations)
        self.assertIn("source_commit_identifiers", transformations)
        self.assertIn("gateway_identifiers", transformations)
        self.assertIn("policy_engine_identifiers", transformations)
        self.assertIn("gateway_urls", transformations)

    def test_public_cloud_has_no_raw_managed_correlation_identifiers(self) -> None:
        for path in CLOUD.rglob("*"):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIsNone(UUID_VALUE.search(text))
                self.assertNotIn(".amazonaws.com", text)

            documents: list[object] = []
            if path.suffix == ".json":
                documents.append(json.loads(text))
            elif path.suffix == ".jsonl":
                documents.extend(
                    json.loads(line) for line in text.splitlines() if line.strip()
                )
            for document in documents:
                for key, value in self.key_values(document):
                    if not isinstance(value, str):
                        continue
                    normalized_key = key.lower()
                    with self.subTest(path=path, key=key):
                        if normalized_key == "operationid":
                            self.assertRegex(value, CLOUD_OPERATION_ALIAS)
                        elif normalized_key == "physicalresourceid":
                            self.assertRegex(value, CLOUD_RESOURCE_ALIAS)
                        elif normalized_key == "git_commit":
                            self.assertEqual(value, "<PRIVATE_SOURCE_COMMIT>")
                        elif normalized_key == "gateway_id":
                            self.assertRegex(value, GATEWAY_ALIAS)
                        elif normalized_key == "policy_engine_id":
                            self.assertRegex(value, POLICY_ENGINE_ALIAS)
                        elif normalized_key == "gateway_url":
                            self.assertRegex(value, GATEWAY_URL_ALIAS)

    def test_tracked_text_has_no_local_home_paths_or_private_task_links(self) -> None:
        windows_home = re.compile(
            r"[A-Za-z]:" + re.escape("\\") + "Users" + re.escape("\\")
        )
        posix_homes = ("/" + "home" + "/", "/" + "Users" + "/")
        private_task_host = "app" + ".clickup.com"
        for path in tracked_files():
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            with self.subTest(path=path):
                self.assertIsNone(windows_home.search(text))
                self.assertTrue(all(marker not in text for marker in posix_homes))
                self.assertNotIn(private_task_host, text)


if __name__ == "__main__":
    unittest.main()
