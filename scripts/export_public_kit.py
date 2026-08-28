#!/usr/bin/env python3
"""Export the explicitly allowlisted public room-kit overlays.

The exporter is deliberately source-oriented: it never walks the repository
to discover files to copy.  The public overlay is checked for unlisted files so
an accidental addition cannot become an implicit publication decision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, Sequence


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_NAME = "PUBLIC_EXPORT_MANIFEST.json"
MANIFEST_MODE = 0o644
SOURCE_ALLOWLIST = "public-export/allowlist.json"
ARTIFACT_ALLOWLIST = ".public-export/allowlist.json"


class ExportError(ValueError):
    """Raised when an export would violate the publication boundary."""


@dataclass(frozen=True)
class ExportSpec:
    source: str
    destination: str


def _relative_path(value: str, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ExportError(f"{label} must be a non-empty relative path")
    if "\x00" in value:
        raise ExportError(f"{label} contains NUL")
    if "\\" in value:
        raise ExportError(f"{label} must use POSIX separators")
    if value.startswith("/") or PurePosixPath(value).is_absolute():
        raise ExportError(f"{label} must be relative: {value!r}")
    if len(value) >= 2 and value[1] == ":" and value[0].isalpha():
        raise ExportError(f"{label} must not be a Windows absolute path")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ExportError(f"{label} contains traversal or empty components: {value!r}")
    return value


def _load_public_allowlist() -> tuple[ExportSpec, ...]:
    candidates = (ROOT / SOURCE_ALLOWLIST, ROOT / ARTIFACT_ALLOWLIST)
    allowlist_path = next((path for path in candidates if path.is_file()), None)
    if allowlist_path is None:
        raise ExportError("public allowlist data file is missing")
    try:
        value = json.loads(allowlist_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExportError(f"invalid public allowlist: {exc}") from exc
    if not isinstance(value, dict) or value.get("format") != 1:
        raise ExportError("unsupported public allowlist format")
    files = value.get("files")
    if not isinstance(files, list) or not files:
        raise ExportError("public allowlist files must be a non-empty list")
    if value.get("generated") != [
        {"destination": MANIFEST_NAME, "mode": f"{MANIFEST_MODE:04o}"}
    ]:
        raise ExportError("public allowlist must explicitly describe the generated manifest")

    entries: list[ExportSpec] = []
    destinations: set[str] = set()
    for item in files:
        if not isinstance(item, dict):
            raise ExportError("public allowlist entry must be an object")
        source = _relative_path(item.get("source"), label="source")
        destination = _relative_path(item.get("destination"), label="destination")
        if destination == MANIFEST_NAME:
            raise ExportError(f"allowlist destination is reserved: {MANIFEST_NAME}")
        if destination in destinations:
            raise ExportError(f"duplicate allowlist destination: {destination}")
        destinations.add(destination)
        entries.append(ExportSpec(source, destination))
    return tuple(entries)


PUBLIC_ALLOWLIST = _load_public_allowlist()
PUBLIC_FILES = PUBLIC_ALLOWLIST
PUBLIC_DESTINATIONS = tuple(entry.destination for entry in PUBLIC_ALLOWLIST)


def _is_binary(data: bytes) -> bool:
    """Reject binary or undecodable data before it reaches the artifact."""

    if b"\x00" in data:
        return True
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return True
    sample = data[:8192]
    if not sample:
        return False
    control_count = sum(
        byte < 9 or 13 < byte < 32
        for byte in sample
    )
    return control_count / len(sample) > 0.10


def _lstat(path: Path, *, label: str) -> os.stat_result:
    try:
        return path.lstat()
    except FileNotFoundError as exc:
        raise ExportError(f"missing {label}: {path}") from exc
    except OSError as exc:
        raise ExportError(f"cannot inspect {label}: {path}: {exc}") from exc


def _source_bytes(repo_root: Path, relative: str) -> tuple[bytes, int]:
    current = repo_root
    parts = relative.split("/")
    for part in parts:
        current = current / part
        info = _lstat(current, label="source")
        if stat.S_ISLNK(info.st_mode):
            raise ExportError(f"refusing symlink source: {relative}")
    info = _lstat(current, label="source")
    if not stat.S_ISREG(info.st_mode):
        raise ExportError(f"source is not a regular file: {relative}")
    try:
        data = current.read_bytes()
    except OSError as exc:
        raise ExportError(f"cannot read source: {relative}: {exc}") from exc
    if _is_binary(data):
        raise ExportError(f"refusing binary source: {relative}")
    return data, stat.S_IMODE(info.st_mode)


def _is_exported_artifact(repo_root: Path) -> bool:
    return (
        (repo_root / ARTIFACT_ALLOWLIST).is_file()
        and not (repo_root / "public-export").is_dir()
    )


def _source_for_entry(repo_root: Path, entry: ExportSpec) -> str:
    source = repo_root / Path(entry.source)
    if source.exists() or source.is_symlink():
        return entry.source
    if _is_exported_artifact(repo_root):
        destination = repo_root / Path(entry.destination)
        if destination.exists() or destination.is_symlink():
            # Public overlays are flattened into their reviewed destinations;
            # this fallback lets the exported tree re-export itself without
            # carrying the private source overlay directory.
            return entry.destination
    return entry.source


def _validate_overlay(repo_root: Path, entries: Sequence[ExportSpec]) -> None:
    """Ensure the checked-in public overlay has no unlisted regular files."""

    overlay = repo_root / "public-export"
    if not overlay.exists():
        return
    listed = {spec.source for spec in entries}
    for path in sorted(overlay.rglob("*")):
        relative = path.relative_to(repo_root).as_posix()
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise ExportError(f"refusing symlink in public overlay: {relative}")
        if stat.S_ISREG(info.st_mode) and relative not in listed:
            raise ExportError(f"unlisted public overlay file: {relative}")


def _validate_entries(
    repo_root: Path,
    entries: Iterable[ExportSpec],
) -> list[tuple[ExportSpec, bytes, int]]:
    normalized: list[ExportSpec] = []
    destinations: set[str] = set()
    sources: set[str] = set()
    for entry in entries:
        if not isinstance(entry, ExportSpec):
            raise ExportError("allowlist entries must be ExportSpec values")
        source = _relative_path(entry.source, label="source")
        destination = _relative_path(entry.destination, label="destination")
        if destination == MANIFEST_NAME:
            raise ExportError(f"destination is reserved: {MANIFEST_NAME}")
        if source in sources:
            raise ExportError(f"duplicate source in allowlist: {source}")
        if destination in destinations:
            raise ExportError(f"duplicate destination in allowlist: {destination}")
        sources.add(source)
        destinations.add(destination)
        normalized.append(ExportSpec(source, destination))

    _validate_overlay(repo_root, normalized)
    validated: list[tuple[ExportSpec, bytes, int]] = []
    for entry in normalized:
        data, mode = _source_bytes(repo_root, _source_for_entry(repo_root, entry))
        validated.append((entry, data, mode))
    return validated


def _destination_path(destination: os.PathLike[str] | str, repo_root: Path) -> Path:
    try:
        raw = os.fspath(destination)
    except TypeError as exc:
        raise ExportError("destination must be a filesystem path") from exc
    if not isinstance(raw, str) or not raw or "\x00" in raw:
        raise ExportError("destination must be a non-empty filesystem path")

    lexical = Path(raw)
    if any(part in {".", ".."} for part in lexical.parts):
        raise ExportError(f"destination contains traversal: {raw!r}")
    if not lexical.is_absolute():
        lexical = Path.cwd() / lexical
    path = Path(os.path.abspath(lexical))
    resolved = path.resolve(strict=False)
    source_root = repo_root.resolve()
    if resolved == source_root or source_root in resolved.parents:
        raise ExportError("destination must be outside the source checkout")
    if resolved == Path(resolved.anchor):
        raise ExportError("refusing filesystem root as destination")

    # A final symlink is never an acceptable output directory.  Existing parent
    # aliases such as macOS /tmp are resolved above; the caller still controls
    # the resulting directory and no symlink is copied into the artifact.
    if path.exists() or path.is_symlink():
        info = _lstat(path, label="destination")
        if stat.S_ISLNK(info.st_mode):
            raise ExportError("destination must not be a symlink")
        if not stat.S_ISDIR(info.st_mode):
            raise ExportError("destination must be a directory")
        try:
            if next(path.iterdir(), None) is not None:
                raise ExportError("destination must be new or empty")
        except OSError as exc:
            raise ExportError(f"cannot inspect destination: {path}: {exc}") from exc
    else:
        parent = path.parent
        # macOS exposes /tmp as a stable system alias to the private temp
        # directory.  Resolve that alias, while still rejecting arbitrary
        # caller-created symlink parents as unsafe destinations.
        if parent.is_symlink() and parent != Path("/tmp"):
            raise ExportError("destination parent must not be a symlink")
        resolved_parent = resolved.parent
        if not resolved_parent.exists() or not resolved_parent.is_dir():
            raise ExportError("destination parent must be an existing regular directory")
    return path


def _mkdir_output_parent(path: Path) -> None:
    current = path
    missing: list[Path] = []
    while not current.exists():
        missing.append(current)
        current = current.parent
    if current.is_symlink() or not current.is_dir():
        raise ExportError(f"output parent is not a directory: {current}")
    for item in reversed(missing):
        item.mkdir(mode=0o755)


def _write_new_file(path: Path, data: bytes, mode: int) -> None:
    _mkdir_output_parent(path.parent)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags | nofollow, mode)
    except FileExistsError as exc:
        raise ExportError(f"output appeared during export: {path}") from exc
    except OSError as exc:
        raise ExportError(f"cannot create output file: {path}: {exc}") from exc
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
        os.chmod(path, mode)
    except OSError as exc:
        raise ExportError(f"cannot write output file: {path}: {exc}") from exc


def _manifest_bytes(
    files: Sequence[tuple[ExportSpec, bytes, int]],
) -> bytes:
    entries = [
        {
            "bytes": len(data),
            "kind": "payload",
            "mode": f"{mode:04o}",
            "path": spec.destination,
            "sha256": hashlib.sha256(data).hexdigest(),
            "source": spec.source,
        }
        for spec, data, mode in files
    ]
    entries.append(
        {
            "kind": "manifest",
            "mode": f"{MANIFEST_MODE:04o}",
            "path": MANIFEST_NAME,
        }
    )
    entries.sort(key=lambda item: item["path"])
    manifest = {
        "format": 1,
        "files": entries,
        "manifest": MANIFEST_NAME,
    }
    return (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")


def export_public_kit(
    destination: os.PathLike[str] | str,
    *,
    repo_root: os.PathLike[str] | str = ROOT,
    entries: Iterable[ExportSpec] = PUBLIC_ALLOWLIST,
) -> Path:
    """Export the allowlist to a new or empty directory and return its path."""

    source_root = Path(repo_root)
    if not source_root.exists() or not source_root.is_dir() or source_root.is_symlink():
        raise ExportError("repo_root must be an existing non-symlink directory")
    source_root = source_root.resolve()
    entry_list = tuple(entries)
    validated = _validate_entries(source_root, entry_list)
    output = _destination_path(destination, source_root)

    created = False
    if not output.exists():
        try:
            output.mkdir(mode=0o755)
            created = True
        except FileExistsError as exc:
            raise ExportError("destination appeared during export") from exc
        except OSError as exc:
            raise ExportError(f"cannot create destination: {output}: {exc}") from exc

    try:
        for spec, data, mode in sorted(validated, key=lambda item: item[0].destination):
            _write_new_file(output / Path(spec.destination), data, mode)
        _write_new_file(
            output / MANIFEST_NAME,
            _manifest_bytes(validated),
            MANIFEST_MODE,
        )
    except Exception:
        # A directory created by this call is disposable, but an existing empty
        # caller-owned directory is left intact for inspection after failure.
        if created:
            for path in sorted(output.rglob("*"), reverse=True):
                if path.is_file() or path.is_symlink():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()
            output.rmdir()
        raise
    return output


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export the explicit public room-kit allowlist."
    )
    parser.add_argument(
        "destination",
        type=Path,
        help="new or empty directory outside the source checkout",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        output = export_public_kit(args.destination)
    except ExportError as exc:
        print(f"export failed: {exc}", file=sys.stderr)
        return 1
    print(f"exported public kit to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
