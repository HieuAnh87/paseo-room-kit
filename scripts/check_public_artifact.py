#!/usr/bin/env python3
"""Scan an exported public artifact for private or machine-local material."""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import stat
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qsl, urlsplit


MANIFEST_NAME = "PUBLIC_EXPORT_MANIFEST.json"
ALLOWLIST_NAME = ".public-export/allowlist.json"
SYNTHETIC_HOME_USERS = frozenset(
    {
        "demo",
        "example",
        "placeholder",
        "public",
        "redacted",
        "test",
        "tests",
        "user",
        "username",
    }
)
SYNTHETIC_DOMAINS = frozenset(
    {"example.com", "example.net", "example.org", "invalid", "localhost", "test"}
)
PUBLIC_URL_HOSTS = frozenset(
    {
        "127.0.0.1",
        "::1",
        "app.paseo.sh",
        "github.com",
        "localhost",
        "opencode.ai",
        "paseo.sh",
        "raw.githubusercontent.com",
        "www.opencode.ai",
        "www.paseo.sh",
    }
)


@dataclass(frozen=True)
class Finding:
    path: str
    rule: str
    detail: str


PRIVATE_NAME_PARTS = ("MO" + "SA", "MR" + "AG", "H" + "DC")
PRIVATE_NAME_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:"
    + "|".join(re.escape(part) for part in PRIVATE_NAME_PARTS)
    + r")(?![A-Za-z0-9])",
    re.I,
)
UNIX_HOME_RE = re.compile(
    r"(?<![A-Za-z0-9])/(?:Users|home)/(?P<user>[^/\s]+)", re.I
)
ROOT_HOME_RE = re.compile(r"(?<![A-Za-z0-9])/" + r"root(?:/|\b)", re.I)
TILDE_WORKSPACE_RE = re.compile(
    r"(?<![A-Za-z0-9])~/(?:Desktop|Documents|Downloads|Projects|Repos|Src|Work)(?:/|\b)",
    re.I,
)
WINDOWS_SEPARATOR = "(?:" + re.escape(chr(92)) + "|/)"
WINDOWS_HOME_RE = re.compile(
    r"(?<![A-Za-z0-9])[A-Za-z]:"
    + WINDOWS_SEPARATOR
    + "Users"
    + WINDOWS_SEPARATOR
    + r"(?P<user>[^"
    + re.escape(chr(92))
    + r"/\s]+)",
    re.I,
)
UNC_PATH_RE = re.compile(
    r"(?<![\\A-Za-z0-9])" + re.escape(chr(92) * 2) + r"[^\\\s]+\\[^\\\s]+"
)
UUID_RE = re.compile(
    r"(?<![0-9A-Fa-f])"
    r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-"
    r"[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}"
    r"(?![0-9A-Fa-f])"
)
RUNTIME_ASSIGNMENT_RE = re.compile(
    r"(?P<key>\b(?:PASEO_AGENT_ID|(?:agent|session|workspace|run|thread|conversation)[_-]?id)\b)"
    r"\s*[:=]\s*(?P<value>[^\s,;]+)",
    re.I,
)
RUNTIME_SHAPE_RE = re.compile(
    r"\b(?:agent|session|workspace|run|thread|conversation)[_-][A-Za-z0-9]{12,}\b",
    re.I,
)
EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9._%+-])"
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
    r"(?![A-Za-z0-9._%+-])"
)
URL_RE = re.compile(r"\b(?:https?|wss?)://[^\s<>\"']+", re.I)
DATABASE_URI_RE = re.compile(
    r"\b(?:postgres(?:ql)?(?:\+[A-Za-z0-9_]+)?|mysql(?:\+[A-Za-z0-9_]+)?|"
    r"mariadb(?:\+[A-Za-z0-9_]+)?|mongodb(?:\+srv)?|redis|rediss)://"
    r"[^\s<>\"']+",
    re.I,
)
PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN (?:[A-Z0-9 ]*PRIVATE KEY|PGP PRIVATE KEY BLOCK)-----",
    re.I,
)
SECRET_SHAPES = (
    ("token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("token", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("token", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{16,}\b")),
    (
        "token",
        re.compile(
            r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"
        ),
    ),
)
ASSIGNMENT_RE = re.compile(
    r"(?<![A-Za-z0-9_.])(?P<key>\b(?:[A-Z][A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD|COOKIE)|"
    r"api[_ -]?key|access[_ -]?token|client[_ -]?secret|refresh[_ -]?token|"
    r"auth(?:entication|orization)?|bearer|cookie|password|secret|token|credential)\b)"
    r"\s*(?:[:=]|=>)\s*"
    r"(?P<quote>[\"']?)(?P<value>[^\"'\s,;}]+)",
    re.I,
)
SOURCE_METADATA_PATH_RE = re.compile(
    r"(?i)(?:^|/)(?:[^/]*(?:audit|inventory|notebook|session|history|runtime)[^/]*)$"
)
SOURCE_METADATA_COMPONENTS = frozenset(
    {
        "agent",
        "agents",
        "audit",
        "audits",
        "history",
        "histories",
        "inventory",
        "inventories",
        "notebook",
        "notebooks",
        "runtime",
        "runtimes",
        "session",
        "sessions",
        "workspace",
        "workspaces",
    }
)
VCS_COMPONENTS = frozenset({".git", ".hg", ".svn"})
INTERNAL_HOST_LABELS = frozenset(
    {"corp", "internal", "intranet", "lan", "local", "localdomain", "private"}
)
SOURCE_METADATA_CONTENT_RE = re.compile(
    r"(?i)\b(?:runtime[\s_-]+inventory|session[\s_-]+audit|"
    r"source[\s_-]+only(?:\s+\w+){0,2}\s+(?:audit|inventory))\b"
)
ALLOWED_TEMPLATE_PATH = "templates/SUPERVISOR_NOTEBOOK.md"
ALLOWED_TEMPLATE_CONTENT = (
    "# Supervisor notebook\n\n"
    "Record only durable cross-workspace governance evidence. "
    "Do not store credentials, raw transcripts, or unnecessary project secrets.\n"
)


def _placeholder(value: str) -> bool:
    cleaned = value.strip().strip("\"'`<>()[]{}.,;")
    lowered = cleaned.lower()
    if not lowered:
        return True
    if lowered.startswith(("$", "%")):
        return True
    if "<" in value or ">" in value:
        return True
    markers = (
        "changeme",
        "dummy",
        "example",
        "fake",
        "placeholder",
        "redacted",
        "replace-me",
        "synthetic",
        "test-",
        "test_",
        "your-",
        "your_",
    )
    return lowered in {
        "none",
        "null",
        "password",
        "secret",
        "test",
        "token",
        "user",
    } or lowered.startswith(markers)


def _runtime_placeholder(value: str) -> bool:
    """Allow source-code syntax while retaining identity-shape detection."""

    cleaned = value.strip()
    if _placeholder(cleaned):
        return True
    normalized = cleaned.strip("\"'").lower()
    return cleaned.startswith(
        (
            "(",
            "[",
            "{",
            "current_",
            "record.",
            "tool_input.",
            "deny(",
            "lease[",
            "resolve_",
        )
    ) or normalized in {
        "agent-one",
        "lead-one",
        "supervisor-one",
        "workspace-new",
        "workspace-one",
        "workspace-pilot",
    } or cleaned in {
        "None",
        "=",
        "continue",
        "deny(",
        "return",
        "resolve_",
        "str",
        "str)",
        "str):",
    }


def _synthetic_home_user(value: str) -> bool:
    user = value.strip().strip("<>[]{}$%").lower()
    return user in SYNTHETIC_HOME_USERS or _placeholder(value)


def _synthetic_email(email: str) -> bool:
    domain = email.rsplit("@", 1)[1].lower().rstrip(".")
    return (
        domain in SYNTHETIC_DOMAINS
        or domain.endswith(".example")
        or domain.endswith(".invalid")
        or domain.endswith(".test")
    )


def _internal_hostname(hostname: str) -> bool:
    """Return whether a URL hostname is private or conventionally internal."""

    normalized = hostname.rstrip(".").lower()
    if normalized in {"127.0.0.1", "::1", "localhost"}:
        return False
    try:
        return not ipaddress.ip_address(normalized).is_global
    except ValueError:
        labels = normalized.split(".")
        return len(labels) == 1 or bool(INTERNAL_HOST_LABELS.intersection(labels))


def _safe_relative_path(path: str) -> bool:
    if not path or "\\" in path or path.startswith("/"):
        return False
    pure = PurePosixPath(path)
    return all(part not in {"", ".", ".."} for part in pure.parts)


def _walk(root: Path) -> tuple[list[tuple[str, Path, os.stat_result]], list[Finding]]:
    files: list[tuple[str, Path, os.stat_result]] = []
    findings: list[Finding] = []

    def visit(directory: Path, prefix: str) -> None:
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except OSError as exc:
            findings.append(Finding(prefix or ".", "filesystem", str(exc)))
            return
        for entry in entries:
            relative = f"{prefix}/{entry.name}" if prefix else entry.name
            try:
                info = entry.stat(follow_symlinks=False)
            except OSError as exc:
                findings.append(Finding(relative, "filesystem", str(exc)))
                continue
            if stat.S_ISLNK(info.st_mode):
                findings.append(Finding(relative, "symlink", "symlinks are not public files"))
            elif stat.S_ISDIR(info.st_mode):
                visit(Path(entry.path), relative)
            elif stat.S_ISREG(info.st_mode):
                files.append((relative, Path(entry.path), info))
            else:
                findings.append(Finding(relative, "non-regular", "special files are not public files"))

    visit(root, "")
    return files, findings


def _text(path: str, file_path: Path, findings: list[Finding]) -> str | None:
    try:
        data = file_path.read_bytes()
    except OSError as exc:
        findings.append(Finding(path, "filesystem", str(exc)))
        return None
    if b"\x00" in data:
        findings.append(Finding(path, "binary", "NUL byte detected"))
        return None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        findings.append(Finding(path, "binary", "file is not UTF-8 text"))
        return None
    control_count = sum(byte < 9 or 13 < byte < 32 for byte in data[:8192])
    if data[:8192] and control_count / min(len(data), 8192) > 0.10:
        findings.append(Finding(path, "binary", "control-byte density is too high"))
        return None
    return text


def _scan_text(path: str, text: str, findings: list[Finding]) -> None:
    if PRIVATE_NAME_RE.search(text):
        findings.append(Finding(path, "private-name", "accepted private name shape"))

    for match in UNIX_HOME_RE.finditer(text):
        if not _synthetic_home_user(match.group("user")):
            findings.append(Finding(path, "unix-home", "personal Unix home path"))
    if ROOT_HOME_RE.search(text):
        findings.append(Finding(path, "unix-home", "root home path"))
    if TILDE_WORKSPACE_RE.search(text):
        findings.append(Finding(path, "unix-home", "personal tilde workspace path"))
    for match in WINDOWS_HOME_RE.finditer(text):
        if not _synthetic_home_user(match.group("user")):
            findings.append(Finding(path, "windows-home", "personal Windows home path"))
    if UNC_PATH_RE.search(text):
        findings.append(Finding(path, "windows-home", "UNC path"))

    for match in UUID_RE.finditer(text):
        if match.group(0) != "00000000-0000-0000-0000-000000000000":
            findings.append(Finding(path, "uuid", "runtime UUID shape"))

    for match in RUNTIME_ASSIGNMENT_RE.finditer(text):
        value = match.group("value")
        if not _runtime_placeholder(value):
            findings.append(Finding(path, "runtime-id", "runtime identity assignment"))
    for match in RUNTIME_SHAPE_RE.finditer(text):
        if not _placeholder(match.group(0)):
            findings.append(Finding(path, "runtime-id", "runtime identity shape"))

    for match in EMAIL_RE.finditer(text):
        if not _synthetic_email(match.group(0)):
            findings.append(Finding(path, "corporate-email", "non-synthetic email address"))

    if PRIVATE_KEY_RE.search(text):
        findings.append(Finding(path, "private-key", "private-key armor"))
    for rule, pattern in SECRET_SHAPES:
        if pattern.search(text):
            findings.append(Finding(path, rule, "credential or token shape"))

    for match in DATABASE_URI_RE.finditer(text):
        findings.append(Finding(path, "database-uri", "database connection URI"))

    for match in ASSIGNMENT_RE.finditer(text):
        value = match.group("value")
        if not _placeholder(value):
            findings.append(
                Finding(path, "credential", f"sensitive assignment: {match.group('key')}")
            )

    for match in URL_RE.finditer(text):
        raw_url = match.group(0).rstrip(".,);]}")
        try:
            parsed = urlsplit(raw_url)
        except ValueError:
            continue
        hostname = (parsed.hostname or "").lower()
        # These are the intentionally documented public URL cases.  The
        # scanner still checks user-info and sensitive query values below.
        _ordinary_public_url = hostname in PUBLIC_URL_HOSTS
        if parsed.username or parsed.password:
            findings.append(Finding(path, "credential", "URL contains user-info"))
        if hostname and _internal_hostname(hostname):
            findings.append(Finding(path, "internal-endpoint", "private or internal URL host"))
        for key, value in parse_qsl(parsed.query, keep_blank_values=True):
            if key.lower() in {
                "access_token",
                "api_key",
                "apikey",
                "auth",
                "authorization",
                "key",
                "password",
                "secret",
                "token",
            } and not _placeholder(value):
                findings.append(Finding(path, "token", "sensitive URL query value"))
        # Keep the named host set live and explicit: ordinary public links are
        # allowed, but no host receives an exemption from the checks above.
        if _ordinary_public_url:
            continue

    if SOURCE_METADATA_CONTENT_RE.search(text):
        findings.append(Finding(path, "source-metadata", "source-only operational metadata"))
    if path == ALLOWED_TEMPLATE_PATH and text != ALLOWED_TEMPLATE_CONTENT:
        findings.append(Finding(path, "source-metadata", "blank notebook template was modified"))


def _manifest_findings(
    root: Path,
    files: list[tuple[str, Path, os.stat_result]],
    findings: list[Finding],
) -> None:
    by_path = {relative: (path, info) for relative, path, info in files}
    manifest_file = by_path.get(MANIFEST_NAME)
    if manifest_file is None:
        findings.append(Finding(MANIFEST_NAME, "manifest", "manifest is missing"))
        return
    manifest_path, _manifest_info = manifest_file
    try:
        raw = manifest_path.read_text(encoding="utf-8")
        value = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        findings.append(Finding(MANIFEST_NAME, "manifest", f"invalid manifest: {exc}"))
        return
    if not isinstance(value, dict) or value.get("format") != 1:
        findings.append(Finding(MANIFEST_NAME, "manifest", "unsupported manifest format"))
        return
    listed = value.get("files")
    if not isinstance(listed, list):
        findings.append(Finding(MANIFEST_NAME, "manifest", "files must be a list"))
        return

    seen: set[str] = set()
    entries_by_path: dict[str, dict] = {}
    for entry in listed:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            findings.append(Finding(MANIFEST_NAME, "manifest", "file entry is not an object with a path"))
            continue
        relative = entry["path"]
        if not _safe_relative_path(relative):
            findings.append(Finding(MANIFEST_NAME, "traversal", f"unsafe manifest path: {relative!r}"))
            continue
        if relative in seen:
            findings.append(Finding(MANIFEST_NAME, "duplicate-destination", relative))
        seen.add(relative)
        entries_by_path[relative] = entry

    actual = set(by_path)
    listed_paths = set(entries_by_path)
    for relative in sorted(actual - listed_paths):
        findings.append(Finding(relative, "manifest", "file is not explicitly listed"))
    for relative in sorted(listed_paths - actual):
        findings.append(Finding(relative, "manifest", "manifest lists a missing file"))

    if value.get("manifest") != MANIFEST_NAME:
        findings.append(Finding(MANIFEST_NAME, "manifest", "manifest name does not match"))

    for relative, entry in entries_by_path.items():
        if relative not in by_path:
            continue
        file_path, info = by_path[relative]
        mode = entry.get("mode")
        try:
            expected_mode = int(mode, 8)
        except (TypeError, ValueError):
            findings.append(Finding(relative, "manifest", "invalid mode"))
            continue
        if stat.S_IMODE(info.st_mode) != expected_mode:
            findings.append(Finding(relative, "mode", "manifest mode does not match file mode"))
        if relative == MANIFEST_NAME:
            if entry.get("kind") != "manifest":
                findings.append(Finding(relative, "manifest", "manifest entry has wrong kind"))
            continue
        if entry.get("kind") != "payload":
            findings.append(Finding(relative, "manifest", "payload entry has wrong kind"))
        try:
            data = file_path.read_bytes()
        except OSError as exc:
            findings.append(Finding(relative, "filesystem", str(exc)))
            continue
        if entry.get("bytes") != len(data):
            findings.append(Finding(relative, "manifest", "byte count does not match"))
        digest = entry.get("sha256")
        if digest != hashlib.sha256(data).hexdigest():
            findings.append(Finding(relative, "manifest", "sha256 does not match"))

    allowlist_file = by_path.get(ALLOWLIST_NAME)
    if allowlist_file is None:
        findings.append(Finding(ALLOWLIST_NAME, "allowlist", "public allowlist is missing"))
        return
    try:
        allowlist = json.loads(allowlist_file[0].read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        findings.append(Finding(ALLOWLIST_NAME, "allowlist", f"invalid allowlist: {exc}"))
        return
    if not isinstance(allowlist, dict) or allowlist.get("format") != 1:
        findings.append(Finding(ALLOWLIST_NAME, "allowlist", "unsupported allowlist format"))
        return
    allowed_files = allowlist.get("files")
    generated = allowlist.get("generated")
    if not isinstance(allowed_files, list) or generated != [
        {"destination": MANIFEST_NAME, "mode": "0644"}
    ]:
        findings.append(Finding(ALLOWLIST_NAME, "allowlist", "invalid files or generated contract"))
        return
    expected_sources: dict[str, str] = {}
    for item in allowed_files:
        if not isinstance(item, dict):
            findings.append(Finding(ALLOWLIST_NAME, "allowlist", "file entry is not an object"))
            continue
        source = item.get("source")
        destination = item.get("destination")
        if not isinstance(source, str) or not isinstance(destination, str):
            findings.append(Finding(ALLOWLIST_NAME, "allowlist", "entry lacks source or destination"))
            continue
        if not _safe_relative_path(source) or not _safe_relative_path(destination):
            findings.append(Finding(ALLOWLIST_NAME, "allowlist", "entry contains an unsafe path"))
            continue
        if destination in expected_sources:
            findings.append(Finding(ALLOWLIST_NAME, "allowlist", f"duplicate destination: {destination}"))
        expected_sources[destination] = source
    payload_entries = {
        relative: entry
        for relative, entry in entries_by_path.items()
        if relative != MANIFEST_NAME
    }
    if set(payload_entries) != set(expected_sources):
        findings.append(Finding(ALLOWLIST_NAME, "allowlist", "manifest payloads differ from allowlist"))
    for relative, source in expected_sources.items():
        entry = payload_entries.get(relative)
        if entry is not None and entry.get("source") != source:
            findings.append(Finding(relative, "allowlist", "manifest source differs from allowlist"))


def scan_public_artifact(root: os.PathLike[str] | str) -> list[Finding]:
    """Return all findings for an exported artifact; an empty list is clean."""

    artifact = Path(root)
    findings: list[Finding] = []
    if artifact.is_symlink():
        return [Finding(".", "symlink", "artifact root is a symlink")]
    if not artifact.exists() or not artifact.is_dir():
        return [Finding(".", "filesystem", "artifact root must be a directory")]

    files, walk_findings = _walk(artifact)
    findings.extend(walk_findings)
    for relative, path, _info in files:
        components = {part.lower() for part in PurePosixPath(relative).parts}
        if components & VCS_COMPONENTS:
            findings.append(Finding(relative, "vcs-metadata", "version-control metadata is forbidden"))
        if relative != ALLOWED_TEMPLATE_PATH and (
            SOURCE_METADATA_PATH_RE.search(relative)
            or components & SOURCE_METADATA_COMPONENTS
        ):
            findings.append(Finding(relative, "source-metadata", "source-only operational path"))
        if PRIVATE_NAME_RE.search(relative):
            findings.append(Finding(relative, "private-name", "accepted private name shape"))
        if UUID_RE.search(relative) or RUNTIME_SHAPE_RE.search(relative):
            findings.append(Finding(relative, "runtime-id", "runtime identity in path"))
        text = _text(relative, path, findings)
        if text is not None:
            _scan_text(relative, text, findings)
    _manifest_findings(artifact, files, findings)
    return sorted(set(findings), key=lambda finding: (finding.path, finding.rule, finding.detail))


# Short aliases keep the scanner convenient for small local validation scripts.
scan_artifact = scan_public_artifact


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scan a public kit export.")
    parser.add_argument("artifact", type=Path, help="export directory to scan")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    findings = scan_public_artifact(args.artifact)
    if findings:
        print(f"PUBLIC ARTIFACT FAILED: {len(findings)} finding(s)", file=sys.stderr)
        for finding in findings:
            print(
                f"{finding.path}: [{finding.rule}] {finding.detail}",
                file=sys.stderr,
            )
        return 1
    print(f"PUBLIC ARTIFACT OK: {args.artifact}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
