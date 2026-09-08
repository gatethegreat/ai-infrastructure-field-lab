"""Run the no-cloud direct-provider versus LiteLLM comparison."""

from __future__ import annotations

import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import version
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
DIRECT_URL = "http://127.0.0.1:4010/v1/responses"
GATEWAY_URL = "http://127.0.0.1:4000/v1/responses"
GATEWAY_HEALTH_URL = "http://127.0.0.1:4000/health/liveliness"
GATEWAY_KEY = "local-synthetic-gateway-only"
SAMPLE_COUNT = 20
STREAM_SAMPLE_COUNT = 10


def percentile(values: list[float], percent: float) -> float:
    if not values:
        raise ValueError("values must not be empty")
    ordered = sorted(values)
    rank = (len(ordered) - 1) * percent
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = rank - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def aggregate(values: list[float]) -> dict[str, float | int]:
    return {
        "samples": len(values),
        "p50_ms": round(statistics.median(values), 3),
        "p95_ms": round(percentile(values, 0.95), 3),
        "min_ms": round(min(values), 3),
        "max_ms": round(max(values), 3),
    }


def response_document(payload: dict[str, object]) -> dict[str, object]:
    request_model = str(payload.get("model", "synthetic-codex"))
    previous_id = payload.get("previous_response_id")
    tools = payload.get("tools")
    output: list[dict[str, object]]
    if isinstance(tools, list) and tools:
        first_tool = tools[0]
        tool_name = "inspect_service"
        if isinstance(first_tool, dict):
            tool_name = str(first_tool.get("name", tool_name))
        output = [
            {
                "type": "function_call",
                "id": "fc_synthetic_001",
                "call_id": "call_synthetic_001",
                "name": tool_name,
                "arguments": '{"service":"checkout-api"}',
                "status": "completed",
            }
        ]
    else:
        output = [
            {
                "type": "message",
                "id": "msg_synthetic_001",
                "status": "completed",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": "SYNTHETIC_OK",
                        "annotations": [],
                    }
                ],
            }
        ]
    return {
        "id": "resp_synthetic_001",
        "object": "response",
        "created_at": 1_788_844_800,
        "status": "completed",
        "error": None,
        "incomplete_details": None,
        "instructions": None,
        "max_output_tokens": None,
        "model": request_model,
        "output": output,
        "parallel_tool_calls": True,
        "previous_response_id": previous_id,
        "reasoning": {"effort": None, "summary": None},
        "store": True,
        "temperature": 1.0,
        "text": {"format": {"type": "text"}},
        "tool_choice": "auto",
        "tools": tools if isinstance(tools, list) else [],
        "top_p": 1.0,
        "truncation": "disabled",
        "usage": {
            "input_tokens": 10,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens": 3,
            "output_tokens_details": {"reasoning_tokens": 0},
            "total_tokens": 13,
        },
        "metadata": {},
    }


class SyntheticProviderHandler(BaseHTTPRequestHandler):
    server_version = "SyntheticResponsesProvider/1.0"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/health", "/v1/models"):
            self._write_json(200, {"status": "ok"})
        else:
            self._write_json(404, {"error": {"message": "not found"}})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/responses":
            self._write_json(404, {"error": {"message": "not found"}})
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        metadata = payload.get("metadata", {})
        if isinstance(metadata, dict) and metadata.get("synthetic_case") == "upstream_error":
            self._write_json(
                429,
                {
                    "error": {
                        "message": "synthetic upstream rate limit",
                        "type": "rate_limit_error",
                        "code": "synthetic_rate_limit",
                    }
                },
            )
            return
        document = response_document(payload)
        if payload.get("stream") is True:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            events = [
                {"type": "response.created", "response": document},
                {
                    "type": "response.output_text.delta",
                    "item_id": "msg_synthetic_001",
                    "output_index": 0,
                    "content_index": 0,
                    "delta": "SYNTHETIC_OK",
                },
                {"type": "response.completed", "response": document},
            ]
            for event in events:
                self.wfile.write(f"data: {json.dumps(event)}\n\n".encode())
                self.wfile.flush()
                time.sleep(0.005)
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            return
        self._write_json(200, document)

    def _write_json(self, status: int, document: dict[str, object]) -> None:
        encoded = json.dumps(document).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def request_json(
    url: str,
    payload: dict[str, object],
    bearer: str,
    expected_status: int = 200,
) -> tuple[dict[str, object], float, int]:
    request = Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {bearer}", "Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=15) as response:
            status = response.status
            document = json.loads(response.read())
    except HTTPError as exc:
        status = exc.code
        document = json.loads(exc.read())
    elapsed_ms = (time.perf_counter() - started) * 1000
    if status != expected_status:
        raise AssertionError(f"expected HTTP {expected_status}, got {status}: {document}")
    return document, elapsed_ms, status


def request_stream(url: str, bearer: str) -> tuple[float, float, list[str]]:
    payload = {"model": "synthetic-codex", "input": "synthetic stream", "stream": True}
    request = Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {bearer}", "Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    first_event_ms: float | None = None
    event_types: list[str] = []
    with urlopen(request, timeout=15) as response:
        if response.status != 200:
            raise AssertionError(f"expected HTTP 200, got {response.status}")
        for raw_line in response:
            line = raw_line.decode().strip()
            if not line.startswith("data: ") or line == "data: [DONE]":
                continue
            if first_event_ms is None:
                first_event_ms = (time.perf_counter() - started) * 1000
            event = json.loads(line[6:])
            event_types.append(str(event.get("type")))
    total_ms = (time.perf_counter() - started) * 1000
    if first_event_ms is None:
        raise AssertionError("stream produced no data events")
    return first_event_ms, total_ms, event_types


def wait_for_gateway(process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"LiteLLM exited during startup with code {process.returncode}")
        try:
            with urlopen(GATEWAY_HEALTH_URL, timeout=1) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError):
            time.sleep(0.25)
    raise TimeoutError("LiteLLM did not become healthy within 60 seconds")


def validate_text(document: dict[str, object]) -> None:
    if document.get("status") != "completed" or not document.get("output"):
        raise AssertionError(f"invalid completed response: {document}")


def validate_tool(document: dict[str, object]) -> None:
    output = document.get("output")
    if not isinstance(output, list) or not output:
        raise AssertionError("tool response has no output")
    first = output[0]
    if not isinstance(first, dict) or first.get("type") != "function_call":
        raise AssertionError(f"expected function_call output, got {first}")
    if first.get("name") != "inspect_service":
        raise AssertionError(f"unexpected tool name: {first.get('name')}")


def run_path(url: str, bearer: str) -> dict[str, object]:
    text_latencies: list[float] = []
    for _ in range(SAMPLE_COUNT):
        document, elapsed, _ = request_json(
            url,
            {"model": "synthetic-codex", "input": "synthetic text"},
            bearer,
        )
        validate_text(document)
        text_latencies.append(elapsed)

    stream_first: list[float] = []
    stream_total: list[float] = []
    final_event_types: list[str] = []
    for _ in range(STREAM_SAMPLE_COUNT):
        first, total, event_types = request_stream(url, bearer)
        stream_first.append(first)
        stream_total.append(total)
        final_event_types = event_types

    first, _, _ = request_json(
        url,
        {"model": "synthetic-codex", "input": "synthetic first turn"},
        bearer,
    )
    continuation, _, _ = request_json(
        url,
        {
            "model": "synthetic-codex",
            "input": "synthetic continuation",
            "previous_response_id": first["id"],
        },
        bearer,
    )
    if not continuation.get("previous_response_id"):
        raise AssertionError(
            "previous_response_id was not forwarded to the synthetic provider"
        )
    validate_text(continuation)

    tool, _, _ = request_json(
        url,
        {
            "model": "synthetic-codex",
            "input": "inspect the synthetic service",
            "tools": [
                {
                    "type": "function",
                    "name": "inspect_service",
                    "description": "Read synthetic service status",
                    "parameters": {
                        "type": "object",
                        "properties": {"service": {"type": "string"}},
                        "required": ["service"],
                        "additionalProperties": False,
                    },
                    "strict": True,
                }
            ],
            "tool_choice": {"type": "function", "name": "inspect_service"},
        },
        bearer,
    )
    validate_tool(tool)

    error, _, status = request_json(
        url,
        {
            "model": "synthetic-codex",
            "input": "synthetic error",
            "metadata": {"synthetic_case": "upstream_error"},
        },
        bearer,
        expected_status=429,
    )
    if not isinstance(error.get("error"), dict):
        raise AssertionError("error response was not normalized")

    return {
        "text_total_latency": aggregate(text_latencies),
        "stream_time_to_first_event": aggregate(stream_first),
        "stream_total_latency": aggregate(stream_total),
        "stream_event_types": final_event_types,
        "continuation_succeeded": True,
        "previous_response_id_forwarded": True,
        "forced_tool_call_preserved": True,
        "controlled_error_status": status,
    }


def main() -> int:
    if version("litellm") != "1.100.0":
        raise RuntimeError(f"expected LiteLLM 1.100.0, found {version('litellm')}")

    private_dir = ROOT / "evidence" / "private"
    private_dir.mkdir(parents=True, exist_ok=True)
    public_path = ROOT / "evidence" / "local-summary.json"
    provider = ThreadingHTTPServer(("127.0.0.1", 4010), SyntheticProviderHandler)
    provider_thread = threading.Thread(target=provider.serve_forever, daemon=True)
    provider_thread.start()

    environment = os.environ.copy()
    environment["LITELLM_MASTER_KEY"] = GATEWAY_KEY
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTHONUTF8"] = "1"
    litellm_executable = ROOT / ".venv" / "Scripts" / "litellm.exe"
    if not litellm_executable.exists():
        raise RuntimeError("LiteLLM environment is missing; follow the README setup")

    with (private_dir / "litellm.stdout.log").open("w", encoding="utf-8") as stdout_log, (
        private_dir / "litellm.stderr.log"
    ).open("w", encoding="utf-8") as stderr_log:
        process = subprocess.Popen(
            [
                str(litellm_executable),
                "--config",
                str(ROOT / "litellm.local.yaml"),
                "--host",
                "127.0.0.1",
                "--port",
                "4000",
            ],
            cwd=ROOT,
            env=environment,
            stdout=stdout_log,
            stderr=stderr_log,
            text=True,
        )
        result: dict[str, object] = {
            "schema_version": "1.0",
            "experiment": "02-model-operations-local",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "synthetic_only": True,
            "litellm_version": version("litellm"),
            "sample_count": SAMPLE_COUNT,
            "stream_sample_count": STREAM_SAMPLE_COUNT,
        }
        try:
            wait_for_gateway(process)
            for _ in range(3):
                request_json(
                    DIRECT_URL,
                    {"model": "synthetic-codex", "input": "warmup"},
                    "local-synthetic-provider-key",
                )
                request_json(
                    GATEWAY_URL,
                    {"model": "synthetic-codex", "input": "warmup"},
                    GATEWAY_KEY,
                )
            direct = run_path(DIRECT_URL, "local-synthetic-provider-key")
            gateway = run_path(GATEWAY_URL, GATEWAY_KEY)
            result["direct"] = direct
            result["gateway"] = gateway
            result["gateway_incremental_p50_ms"] = round(
                float(gateway["text_total_latency"]["p50_ms"])
                - float(direct["text_total_latency"]["p50_ms"]),
                3,
            )

            process.terminate()
            process.wait(timeout=15)
            try:
                request_json(
                    GATEWAY_URL,
                    {"model": "synthetic-codex", "input": "outage"},
                    GATEWAY_KEY,
                )
                raise AssertionError("gateway request unexpectedly succeeded after shutdown")
            except (URLError, ConnectionError, OSError):
                result["gateway_outage_failed_closed"] = True
            direct_after, _, _ = request_json(
                DIRECT_URL,
                {"model": "synthetic-codex", "input": "direct after gateway outage"},
                "local-synthetic-provider-key",
            )
            validate_text(direct_after)
            result["direct_survived_gateway_outage"] = True
            result["status"] = "passed"
        except Exception as exc:
            result["status"] = "failed"
            result["failure_type"] = type(exc).__name__
            result["failure"] = str(exc)[:500]
            raise
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            provider.shutdown()
            provider.server_close()
            public_path.parent.mkdir(parents=True, exist_ok=True)
            public_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
