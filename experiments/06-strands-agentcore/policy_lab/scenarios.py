"""Load and resolve the versioned deterministic trajectory catalog."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .clock import LogicalClock
from .contracts import Scenario


DEFAULT_CATALOG = Path(__file__).parents[1] / "fixtures" / "scenarios-v1.json"


def _resolve(value: Any, clock: LogicalClock) -> Any:
    replacements = {
        "{{valid_expires_at}}": clock.relative_iso(minutes=15),
        "{{expired_expires_at}}": clock.relative_iso(seconds=-1),
    }
    if isinstance(value, str):
        return replacements.get(value, value)
    if isinstance(value, list):
        return [_resolve(item, clock) for item in value]
    if isinstance(value, dict):
        return {key: _resolve(item, clock) for key, item in value.items()}
    return value


def load_scenarios(
    path: Path | None = None, clock: LogicalClock | None = None
) -> tuple[Scenario, ...]:
    catalog_path = path or DEFAULT_CATALOG
    raw = json.loads(catalog_path.read_text(encoding="utf-8"))
    if raw.get("schema_version") != "1.0":
        raise ValueError("unsupported scenario catalog version")
    active_clock = clock or LogicalClock()
    scenarios = tuple(
        Scenario.from_dict(_resolve(item, active_clock)) for item in raw["scenarios"]
    )
    ids = [scenario.scenario_id for scenario in scenarios]
    if len(ids) != len(set(ids)):
        raise ValueError("scenario IDs must be unique")
    return scenarios
