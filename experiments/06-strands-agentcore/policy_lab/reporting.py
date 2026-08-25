"""Small reporting hooks used by CLI/cloud orchestration layers."""

from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Iterable

from .evidence import EvidenceEvent
from .runner import RunSummary


def latency_summary(events: Iterable[EvidenceEvent]) -> dict[str, dict[str, float]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for event in events:
        grouped[event.tool].append(event.latency_ms)
    return {
        tool: {"median_ms": median(values), "min_ms": min(values), "max_ms": max(values)}
        for tool, values in sorted(grouped.items())
    }


def comparison_rows(summaries: Iterable[RunSummary]) -> list[dict[str, object]]:
    return [summary.as_dict() for summary in summaries]
