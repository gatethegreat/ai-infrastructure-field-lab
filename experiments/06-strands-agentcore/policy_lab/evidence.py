"""Append-only evidence records for calls and authorization decisions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

from .contracts import SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class EvidenceEvent:
    run_id: str
    trajectory_hash: str
    scenario_id: str
    repetition: int
    control_model: str
    execution_layer: str
    caller_id: str
    session_id: str | None
    ordinal: int
    step_id: str
    request_id: str
    correlation_id: str
    tool: str
    arguments: dict[str, Any]
    request_at: str
    response_at: str
    latency_ms: float
    authorization: dict[str, Any]
    tool_execution: dict[str, Any]
    trace_id: str | None = None
    span_id: str | None = None
    schema_version: str = SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class EvidenceLog:
    def __init__(self) -> None:
        self._events: list[EvidenceEvent] = []

    @property
    def events(self) -> tuple[EvidenceEvent, ...]:
        return tuple(self._events)

    def append(self, event: EvidenceEvent) -> None:
        self._events.append(event)

    def write_jsonl(self, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = "".join(
            json.dumps(event.as_dict(), sort_keys=True) + "\n"
            for event in self._events
        )
        destination.write_text(payload, encoding="utf-8")
