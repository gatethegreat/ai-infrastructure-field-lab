"""Run the OpenEnv v0.4.1 official Echo reset/step quick start.

Adapted from Hugging Face OpenEnv commit 65c506ef94bb1f7279cb4359673b3ef81031d01f.
The upstream example is BSD-3-Clause; see THIRD_PARTY_NOTICES.md.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import fields, is_dataclass
from datetime import UTC, datetime
from importlib import metadata
import json
from pathlib import Path

from echo_env import CallToolAction, EchoEnv


def _as_json(value):
    if hasattr(value, "model_dump"):
        return _as_json(value.model_dump(mode="json"))
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _as_json(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, dict):
        return {str(key): _as_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_as_json(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


async def run(base_url: str) -> dict:
    async with EchoEnv(base_url=base_url) as client:
        reset_result = await client.reset()
        step_result = await client.step(
            CallToolAction(
                tool_name="echo_message",
                arguments={"message": "Hello, World!"},
            )
        )
    return {
        "evidence_version": "1.0",
        "recorded_at": datetime.now(UTC).isoformat(),
        "openenv_version": metadata.version("openenv"),
        "echo_client_version": metadata.version("openenv-echo-env"),
        "base_url": base_url,
        "reset_result": _as_json(reset_result),
        "step_result": _as_json(step_result),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url", default="https://openenv-echo-env.hf.space"
    )
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    evidence = asyncio.run(run(args.base_url))
    rendered = json.dumps(evidence, indent=2, sort_keys=True) + "\n"
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
