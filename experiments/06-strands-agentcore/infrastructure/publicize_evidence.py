from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil


ISO_TIMESTAMP = re.compile(
    r"20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})"
)
HTTP_TIMESTAMP = re.compile(
    r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun), \d{2} "
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) "
    r"20\d{2} \d{2}:\d{2}:\d{2} GMT"
)
SESSION_VALUE = re.compile(
    r'"(?:x-amzn-bedrock-agentcore-policy-session-id|mcp-session-id|'
    r'policySessionId|policy_session_id|sessionId|session_id)"\s*:\s*"([^"]+)"',
    re.IGNORECASE,
)
AWS_REQUEST_VALUE = re.compile(
    r'"(?:aws_request_id|x-amzn-requestid)"\s*:\s*"([^"]+)"',
    re.IGNORECASE,
)
MCP_REQUEST_VALUE = re.compile(
    r'"request_id"\s*:\s*"([^"]+)"',
    re.IGNORECASE,
)
CLOUD_OPERATION_VALUE = re.compile(
    r'"OperationId"\s*:\s*"([^"]+)"',
)
CLOUD_RESOURCE_VALUE = re.compile(
    r'"PhysicalResourceId"\s*:\s*"([^"]+)"',
)
SOURCE_COMMIT_VALUE = re.compile(
    r'"git_commit"\s*:\s*"([^"]+)"',
)
GATEWAY_VALUE = re.compile(
    r'"gateway_id"\s*:\s*"([^"]+)"',
)
POLICY_ENGINE_VALUE = re.compile(
    r'"policy_engine_id"\s*:\s*"([^"]+)"',
)
GATEWAY_URL_VALUE = re.compile(
    r'"gateway_url"\s*:\s*"([^"]+)"',
)
PUBLIC_TIMESTAMP_ANCHOR = datetime(2000, 1, 1, tzinfo=timezone.utc)


def parse_timestamp(value: str) -> datetime:
    if value.endswith(" GMT"):
        return datetime.strptime(value, "%a, %d %b %Y %H:%M:%S GMT").replace(
            tzinfo=timezone.utc
        )
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
        timezone.utc
    )


def format_shifted(original: str, shifted: datetime) -> str:
    if original.endswith(" GMT"):
        return shifted.strftime("%a, %d %b %Y %H:%M:%S GMT")
    fraction = re.search(r"\.(\d+)", original)
    timespec = "seconds"
    if fraction:
        timespec = "microseconds" if len(fraction.group(1)) > 3 else "milliseconds"
    rendered = shifted.isoformat(timespec=timespec)
    if original.endswith("Z"):
        return rendered.replace("+00:00", "Z")
    return rendered


def collect_values(
    contents: dict[Path, str],
) -> tuple[
    set[str],
    set[str],
    set[str],
    set[str],
    set[str],
    set[str],
    set[str],
    set[str],
    set[str],
    set[str],
]:
    sessions: set[str] = set()
    aws_requests: set[str] = set()
    mcp_requests: set[str] = set()
    cloud_operations: set[str] = set()
    cloud_resources: set[str] = set()
    source_commits: set[str] = set()
    gateways: set[str] = set()
    policy_engines: set[str] = set()
    gateway_urls: set[str] = set()
    timestamps: set[str] = set()
    for text in contents.values():
        sessions.update(SESSION_VALUE.findall(text))
        aws_requests.update(AWS_REQUEST_VALUE.findall(text))
        mcp_requests.update(MCP_REQUEST_VALUE.findall(text))
        cloud_operations.update(CLOUD_OPERATION_VALUE.findall(text))
        cloud_resources.update(CLOUD_RESOURCE_VALUE.findall(text))
        source_commits.update(SOURCE_COMMIT_VALUE.findall(text))
        gateways.update(GATEWAY_VALUE.findall(text))
        policy_engines.update(POLICY_ENGINE_VALUE.findall(text))
        gateway_urls.update(GATEWAY_URL_VALUE.findall(text))
        timestamps.update(ISO_TIMESTAMP.findall(text))
        timestamps.update(HTTP_TIMESTAMP.findall(text))
    return (
        sessions,
        aws_requests,
        mcp_requests,
        cloud_operations,
        cloud_resources,
        source_commits,
        gateways,
        policy_engines,
        gateway_urls,
        timestamps,
    )


def replace_many(text: str, replacements: dict[str, str]) -> str:
    for source in sorted(replacements, key=len, reverse=True):
        text = text.replace(source, replacements[source])
    return text


def repair_legacy_statement_redaction(text: str) -> str:
    repaired: list[str] = []
    for line in text.splitlines(keepends=True):
        if '"statement": "' in line:
            line = line.replace('<REDACTED>"', '<REDACTED>\\"')
        repaired.append(line)
    return "".join(repaired)


def sanitize_event(
    event: dict[str, object],
    aws_request_aliases: dict[str, str],
    mcp_request_aliases: dict[str, str],
) -> dict[str, object]:
    aws_request_id = event.get("aws_request_id")
    if isinstance(aws_request_id, str):
        event["aws_request_id"] = aws_request_aliases[aws_request_id]
    request_id = event.get("request_id")
    if isinstance(request_id, str):
        event["request_id"] = mcp_request_aliases[request_id]

    headers = event.get("response_headers")
    if isinstance(headers, dict):
        allowed_headers = {
            "connection",
            "content-type",
            "transfer-encoding",
            "x-amzn-bedrock-agentcore-policy-session-id",
            "x-amzn-requestid",
        }
        public_headers = {
            key: value for key, value in headers.items() if key.lower() in allowed_headers
        }
        for key, value in public_headers.items():
            lowered = key.lower()
            if lowered == "x-amzn-requestid" and isinstance(value, str):
                public_headers[key] = aws_request_aliases[value]
            if lowered == "x-amzn-bedrock-agentcore-policy-session-id":
                public_headers[key] = "<REDACTED_SESSION>"
        event["response_headers"] = public_headers

    event["session_id"] = "<REDACTED_SESSION>"
    parsed_response = event.get("parsed_response")
    if isinstance(parsed_response, dict):
        response_id = parsed_response.get("id")
        if isinstance(response_id, str) and response_id in mcp_request_aliases:
            parsed_response["id"] = mcp_request_aliases[response_id]
        error = parsed_response.get("error")
        if isinstance(error, dict) and "message" in error:
            authorization = event.get("authorization")
            denied = (
                isinstance(authorization, dict)
                and authorization.get("decision") == "deny"
            )
            error["message"] = (
                "Request denied by managed authorization policy."
                if denied
                else "Managed request failed; private diagnostic details removed."
            )
        event["raw_response_body"] = json.dumps(
            parsed_response, separators=(",", ":"), ensure_ascii=False
        )

    event["public_redaction"] = {
        "version": "1.0",
        "timestamp_basis": "synthetic_shift",
        "payload_classification": "synthetic",
    }
    return event


def normalize_projection_value(
    value: object, identifier_replacements: dict[str, str]
) -> object:
    if isinstance(value, dict):
        return {
            key: normalize_projection_value(item, identifier_replacements)
            for key, item in sorted(value.items())
        }
    if isinstance(value, list):
        return [
            normalize_projection_value(item, identifier_replacements)
            for item in value
        ]
    if isinstance(value, str):
        value = replace_many(value, identifier_replacements)
        value = ISO_TIMESTAMP.sub("<TIMESTAMP>", value)
        return HTTP_TIMESTAMP.sub("<TIMESTAMP>", value)
    return value


def event_projection(
    event: dict[str, object], identifier_replacements: dict[str, str]
) -> dict[str, object]:
    fields = (
        "arguments",
        "authorization",
        "batch_id",
        "caller_id",
        "execution_layer",
        "http_status",
        "inter_step_delay_seconds",
        "latency_ms",
        "ordinal",
        "outcome",
        "repetition",
        "run_id",
        "scenario_id",
        "session_mode",
        "step_id",
        "tool",
        "tool_response",
        "trajectory_hash",
        "warmup",
    )
    return normalize_projection_value(
        {field: event.get(field) for field in fields}, identifier_replacements
    )


def projection_digest(
    events: list[dict[str, object]], identifier_replacements: dict[str, str]
) -> str:
    payload = json.dumps(
        [event_projection(event, identifier_replacements) for event in events],
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def publicize(input_directory: Path, output_directory: Path) -> dict[str, object]:
    source_root = input_directory.resolve()
    destination_root = output_directory.resolve()
    if source_root == destination_root:
        raise ValueError("input and output directories must differ")
    if destination_root.exists():
        raise FileExistsError(f"output directory already exists: {destination_root}")

    files = sorted(path for path in source_root.rglob("*") if path.is_file())
    contents = {
        path.relative_to(source_root): path.read_text(encoding="utf-8") for path in files
    }
    (
        sessions,
        aws_requests,
        mcp_requests,
        cloud_operations,
        cloud_resources,
        source_commits,
        gateways,
        policy_engines,
        gateway_urls,
        timestamps,
    ) = collect_values(contents)
    identifier_groups = (
        sessions,
        aws_requests,
        mcp_requests,
        cloud_operations,
        cloud_resources,
        source_commits,
        gateways,
        policy_engines,
        gateway_urls,
    )
    seen_identifiers: set[str] = set()
    for group in identifier_groups:
        if seen_identifiers & group:
            raise ValueError("identifier categories overlap; refusing ambiguous redaction")
        seen_identifiers.update(group)

    session_replacements = {
        value: "<REDACTED_SESSION>"
        for value in sessions
        if value != "<REDACTED_SESSION>"
    }
    aws_request_aliases = {
        value: f"aws-request-{index:06d}"
        for index, value in enumerate(sorted(aws_requests), start=1)
    }
    mcp_request_aliases = {
        value: f"mcp-request-{index:06d}"
        for index, value in enumerate(sorted(mcp_requests), start=1)
    }
    cloud_operation_aliases = {
        value: f"cloud-operation-{index:06d}"
        for index, value in enumerate(sorted(cloud_operations), start=1)
    }
    cloud_resource_aliases = {
        value: f"cloud-resource-{index:06d}"
        for index, value in enumerate(sorted(cloud_resources), start=1)
    }
    source_commit_replacements = {
        value: "<PRIVATE_SOURCE_COMMIT>" for value in source_commits
    }
    gateway_aliases = {
        value: f"gateway-{index:06d}"
        for index, value in enumerate(sorted(gateways), start=1)
    }
    policy_engine_aliases = {
        value: f"policy-engine-{index:06d}"
        for index, value in enumerate(sorted(policy_engines), start=1)
    }
    gateway_url_aliases = {
        value: f"https://gateway-{index:06d}.example.invalid/mcp"
        for index, value in enumerate(sorted(gateway_urls), start=1)
    }
    aws_event_aliases = {
        **aws_request_aliases,
        **{alias: alias for alias in aws_request_aliases.values()},
    }
    mcp_event_aliases = {
        **mcp_request_aliases,
        **{alias: alias for alias in mcp_request_aliases.values()},
    }
    identifier_replacements = {
        **session_replacements,
        **aws_request_aliases,
        **mcp_request_aliases,
        **cloud_operation_aliases,
        **cloud_resource_aliases,
        **source_commit_replacements,
        **gateway_aliases,
        **policy_engine_aliases,
        **gateway_url_aliases,
    }
    projection_replacements = {
        **{value: "<SESSION_ID>" for value in sessions},
        "<REDACTED_SESSION>": "<SESSION_ID>",
        **{
            value: "<AWS_REQUEST_ID>"
            for value in (*aws_request_aliases.keys(), *aws_request_aliases.values())
        },
        **{
            value: "<MCP_REQUEST_ID>"
            for value in (*mcp_request_aliases.keys(), *mcp_request_aliases.values())
        },
        **{
            value: "<CLOUD_OPERATION_ID>"
            for value in (
                *cloud_operation_aliases.keys(),
                *cloud_operation_aliases.values(),
            )
        },
        **{
            value: "<CLOUD_RESOURCE_ID>"
            for value in (
                *cloud_resource_aliases.keys(),
                *cloud_resource_aliases.values(),
            )
        },
        **{value: "<SOURCE_COMMIT>" for value in source_commits},
        "<PRIVATE_SOURCE_COMMIT>": "<SOURCE_COMMIT>",
        **{
            value: "<GATEWAY_ID>"
            for value in (*gateway_aliases.keys(), *gateway_aliases.values())
        },
        **{
            value: "<POLICY_ENGINE_ID>"
            for value in (
                *policy_engine_aliases.keys(),
                *policy_engine_aliases.values(),
            )
        },
        **{
            value: "<GATEWAY_URL>"
            for value in (
                *gateway_url_aliases.keys(),
                *gateway_url_aliases.values(),
            )
        },
    }
    timestamp_replacements: dict[str, str] = {}

    parsed_timestamps = {
        value: parse_timestamp(value) for value in timestamps
    }
    if parsed_timestamps:
        earliest = min(parsed_timestamps.values())
        timestamp_replacements.update(
            {
                value: format_shifted(
                    value,
                    PUBLIC_TIMESTAMP_ANCHOR + (parsed - earliest),
                )
                for value, parsed in parsed_timestamps.items()
            }
        )

    projection_checks: dict[str, dict[str, object]] = {}
    for relative, text in contents.items():
        destination = destination_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        public_text = replace_many(
            repair_legacy_statement_redaction(text),
            {
                **timestamp_replacements,
                **identifier_replacements,
            },
        )
        if relative.suffix == ".jsonl" and relative.name.endswith("events.jsonl"):
            source_events = [
                json.loads(line) for line in text.splitlines() if line.strip()
            ]
            events = [
                sanitize_event(
                    json.loads(line), aws_event_aliases, mcp_event_aliases
                )
                for line in public_text.splitlines()
                if line.strip()
            ]
            source_digest = projection_digest(source_events, projection_replacements)
            public_digest = projection_digest(events, projection_replacements)
            if source_digest != public_digest:
                differing_fields: set[str] = set()
                first_difference = -1
                for index, (source_event, public_event) in enumerate(
                    zip(source_events, events, strict=True)
                ):
                    source_projection = event_projection(
                        source_event, projection_replacements
                    )
                    public_projection = event_projection(
                        public_event, projection_replacements
                    )
                    if source_projection != public_projection:
                        if first_difference < 0:
                            first_difference = index
                        differing_fields.update(
                            key
                            for key in source_projection
                            if source_projection[key] != public_projection[key]
                        )
                raise ValueError(
                    "non-sensitive event projection changed: "
                    f"{relative.as_posix()} event={first_difference} "
                    f"fields={sorted(differing_fields)}"
                )
            projection_checks[relative.as_posix()] = {
                "events": len(events),
                "source_sha256": source_digest,
                "public_sha256": public_digest,
                "match": True,
            }
            public_text = "".join(
                json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n"
                for event in events
            )
        destination.write_text(public_text, encoding="utf-8")

    manifest = {
        "schema_version": "1.0",
        "evidence_kind": "public_redacted_managed_execution",
        "payloads": "synthetic",
        "managed_execution": True,
        "files_processed": len(files),
        "transformations": {
            "policy_session_identifiers": "replaced_with_non_reversible_placeholder",
            "aws_request_identifiers": "replaced_with_stable_public_aliases",
            "mcp_request_identifiers": "replaced_with_stable_public_aliases",
            "cloud_operation_identifiers": "replaced_with_stable_public_aliases",
            "cloud_resource_identifiers": "replaced_with_stable_public_aliases",
            "source_commit_identifiers": "replaced_with_private_source_placeholder",
            "gateway_identifiers": "replaced_with_stable_public_aliases",
            "policy_engine_identifiers": "replaced_with_stable_public_aliases",
            "gateway_urls": "replaced_with_non_resolving_example_urls",
            "exact_timestamps": "shifted_to_synthetic_anchor_preserving_intervals",
            "timestamp_anchor": "2000-01-01T00:00:00Z",
        },
        "unchanged_measurements": [
            "authorization_decisions",
            "tool_outcomes",
            "scenario_and_repetition_labels",
            "latency_measurements",
            "aggregate_counts",
        ],
        "event_projection_checks": projection_checks,
        "source_values_included": False,
    }
    (destination_root / "public-redaction-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    shutil.copy2(
        Path(__file__).with_name("PUBLIC_EVIDENCE.md"),
        destination_root / "README.md",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create privacy-safe public copies of redacted managed evidence."
    )
    parser.add_argument("--input-directory", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    manifest = publicize(args.input_directory, args.output_directory)
    print(
        "Public evidence generated: "
        f"{manifest['files_processed']} source files; sensitive values were not printed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
