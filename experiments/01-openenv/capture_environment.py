"""Capture the resolved isolated Python environment without secrets."""

from __future__ import annotations

import argparse
from importlib import metadata
import json
from pathlib import Path
import platform
import sys


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    packages = {
        distribution.metadata["Name"]: distribution.version
        for distribution in metadata.distributions()
        if distribution.metadata["Name"]
    }
    environment_bytes = sum(
        path.stat().st_size
        for path in Path(sys.prefix).rglob("*")
        if path.is_file()
    )
    evidence = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "executable_is_venv": sys.prefix != sys.base_prefix,
        "package_count": len(packages),
        "environment_bytes": environment_bytes,
        "packages": dict(sorted(packages.items(), key=lambda item: item[0].lower())),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
