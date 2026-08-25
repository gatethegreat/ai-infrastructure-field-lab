"""Load the versioned synthetic scenario fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_scenario() -> dict[str, Any]:
    path = Path(__file__).with_name("scenario-v1.json")
    return json.loads(path.read_text(encoding="utf-8"))
