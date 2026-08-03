#!/usr/bin/env python3
"""Render portable room templates without exposing machine-local secrets."""

from __future__ import annotations

import argparse
import os
import pathlib
import platform
import tempfile


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


def render(source: pathlib.Path, destination: pathlib.Path, home: pathlib.Path) -> None:
    text = source.read_text()
    replacements = {
        "{{HOME}}": str(home),
        "{{ANTIGRAVITY_ACP_BINARY}}": str(antigravity_binary(home)),
    }
    for marker, value in replacements.items():
        text = text.replace(marker, value)
    if "{{" in text or "}}" in text:
        raise SystemExit(f"unresolved template marker in {source}")

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
    arguments = parser.parse_args()
    render(
        arguments.source.resolve(),
        arguments.destination,
        arguments.home.expanduser().resolve(),
    )


if __name__ == "__main__":
    main()
