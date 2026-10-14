#!/usr/bin/env python3
"""Manage the room PATH guards in a user's zsh startup files."""

from __future__ import annotations

import argparse
import os
import stat
import sys
import tempfile
from pathlib import Path


LEGACY_BEGIN_MARKER = "# >>> paseo-room-kit managed PATH guard >>>"
LEGACY_END_MARKER = "# <<< paseo-room-kit managed PATH guard <<<"
TARGETS = {
    "zshenv": {
        "begin": "# >>> paseo-room-kit managed zshenv PATH guard >>>",
        "end": "# <<< paseo-room-kit managed zshenv PATH guard <<<",
    },
    "zprofile": {
        "begin": "# >>> paseo-room-kit managed zprofile PATH guard >>>",
        "end": "# <<< paseo-room-kit managed zprofile PATH guard <<<",
    },
    "zshrc": {
        "begin": "# >>> paseo-room-kit managed zshrc PATH guard >>>",
        "end": "# <<< paseo-room-kit managed zshrc PATH guard <<<",
    },
}


class MarkerStructureError(ValueError):
    """Raised when managed markers could make unrelated shell text ambiguous."""


def _fragment(target: str) -> str:
    markers = TARGETS[target]
    if target in {"zshenv", "zprofile"}:
        body = """if [[ -n "${PASEO_ROOM_ROLE:-}" ]]; then
  _paseo_room_kit_path_guard() {
    [[ -n "${PASEO_ROOM_ROLE:-}" ]] || return 0
    local paseo_room_bin="${HOME}/.local/share/paseo-room-bin"
    path=("$paseo_room_bin" "${path[@]:#$paseo_room_bin}")
    export PATH
  }
  _paseo_room_kit_path_guard
fi
"""
    else:
        body = """if [[ -n "${PASEO_ROOM_ROLE:-}" ]]; then
  _paseo_room_kit_path_guard() {
    [[ -n "${PASEO_ROOM_ROLE:-}" ]] || return 0
    local paseo_room_bin="${HOME}/.local/share/paseo-room-bin"
    path=("$paseo_room_bin" "${path[@]:#$paseo_room_bin}")
    export PATH
  }
  _paseo_room_kit_path_guard
  typeset -ga preexec_functions chpwd_functions
  if (( ${preexec_functions[(I)_paseo_room_kit_path_guard]} == 0 )); then
    preexec_functions+=(_paseo_room_kit_path_guard)
  fi
  if (( ${chpwd_functions[(I)_paseo_room_kit_path_guard]} == 0 )); then
    chpwd_functions+=(_paseo_room_kit_path_guard)
  fi
fi
"""
    return f"{markers['begin']}\n{body}{markers['end']}\n"


def _without_managed_blocks(text: str) -> str:
    """Remove balanced managed blocks and reject ambiguous marker structure."""

    begin_to_end = {
        LEGACY_BEGIN_MARKER: LEGACY_END_MARKER,
        **{
            markers["begin"]: markers["end"] for markers in TARGETS.values()
        },
    }
    end_markers = {
        LEGACY_END_MARKER,
        *(markers["end"] for markers in TARGETS.values()),
    }
    kept: list[str] = []
    active_end: str | None = None
    for line in text.splitlines(keepends=True):
        marker = line.rstrip("\r\n")
        if active_end is None and marker in begin_to_end:
            active_end = begin_to_end[marker]
            continue
        if active_end is not None:
            if marker in begin_to_end:
                raise MarkerStructureError("nested managed begin marker")
            if marker in end_markers:
                if marker != active_end:
                    raise MarkerStructureError("mismatched managed end marker")
                active_end = None
            continue
        if marker in end_markers:
            raise MarkerStructureError("orphaned managed end marker")
        kept.append(line)
    if active_end is not None:
        raise MarkerStructureError("unmatched managed begin marker")
    return "".join(kept)


def merged_contents(text: str, target: str) -> str:
    """Return the canonical file contents with exactly one block at the end."""

    without_block = _without_managed_blocks(text)
    if without_block and not without_block.endswith(("\n", "\r")):
        without_block += "\n"
    return without_block + _fragment(target)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _write(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    destination = path.resolve(strict=True) if path.is_symlink() else path
    destination.parent.mkdir(parents=True, exist_ok=True)
    mode = (
        stat.S_IMODE(destination.stat().st_mode)
        if destination.exists()
        else 0o644
    )
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(contents)
        os.chmod(temporary, mode)
        os.replace(temporary, destination)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check or apply a managed Paseo room zsh PATH guard."
    )
    parser.add_argument("path", type=Path)
    parser.add_argument("--target", choices=tuple(TARGETS), required=True)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--check", action="store_true")
    actions.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    current = _read(args.path)
    try:
        desired = merged_contents(current, args.target)
    except MarkerStructureError as exc:
        print(f"{args.path}: refusing unsafe managed marker structure: {exc}", file=sys.stderr)
        return 2
    changed = desired != current
    if args.apply and changed:
        _write(args.path, desired)
    print("changed" if changed else "unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
