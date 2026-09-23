#!/usr/bin/env python3
"""Render portable room templates without exposing machine-local secrets."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import platform
import tempfile
from collections.abc import Sequence


def antigravity_binary(home: pathlib.Path) -> pathlib.Path:
    system = platform.system()
    machine = platform.machine().lower()
    if system == "Darwin":
        suffix = "darwin-arm64" if machine in {"arm64", "aarch64"} else "darwin-x64"
    elif system == "Linux":
        suffix = "linux-arm64" if machine in {"arm64", "aarch64"} else "linux-x64"
    else:
        raise SystemExit(f"unsupported Antigravity ACP platform: {system}/{machine}")
    return home / ".local/share/antigravity-acp/dist" / f"agy-acp-{suffix}"


def render(
    source: pathlib.Path,
    destination: pathlib.Path,
    home: pathlib.Path,
    *,
    preserve_existing_json_keys: Sequence[str] = (),
    preserve_json_from: pathlib.Path | None = None,
) -> None:
    text = source.read_text()
    replacements = {
        "{{HOME}}": str(home),
        "{{ANTIGRAVITY_ACP_BINARY}}": str(antigravity_binary(home)),
    }
    for marker, value in replacements.items():
        text = text.replace(marker, value)
    if "{{" in text or "}}" in text:
        raise SystemExit(f"unresolved template marker in {source}")

    if preserve_existing_json_keys:
        existing_path = preserve_json_from or destination
        rendered_value = json.loads(text)
        if not isinstance(rendered_value, dict):
            raise SystemExit("preserved JSON template must render to an object")
        if existing_path.exists():
            existing_value = json.loads(existing_path.read_text())
            if not isinstance(existing_value, dict):
                raise SystemExit("existing preserved JSON must be an object")
            for key in preserve_existing_json_keys:
                if key in existing_value and key not in rendered_value:
                    rendered_value[key] = existing_value[key]
        text = json.dumps(rendered_value, indent=2) + "\n"

    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        dir=destination.parent,
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(text)
        os.replace(temporary_name, destination)
    except Exception:
        pathlib.Path(temporary_name).unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=pathlib.Path)
    parser.add_argument("destination", type=pathlib.Path)
    parser.add_argument("--home", type=pathlib.Path, default=pathlib.Path.home())
    parser.add_argument(
        "--preserve-existing-json-key",
        action="append",
        default=[],
        help="preserve an existing top-level JSON key omitted by the template",
    )
    parser.add_argument(
        "--preserve-json-from",
        type=pathlib.Path,
        help="read preserved JSON keys from this path instead of the destination",
    )
    arguments = parser.parse_args()
    render(
        arguments.source.resolve(),
        arguments.destination,
        arguments.home.expanduser().resolve(),
        preserve_existing_json_keys=arguments.preserve_existing_json_key,
        preserve_json_from=arguments.preserve_json_from,
    )


if __name__ == "__main__":
    main()
