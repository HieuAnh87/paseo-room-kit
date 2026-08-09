#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import stat
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


EXPORT = load_module("export_public_kit_test", ROOT / "scripts/export_public_kit.py")
SCANNER = load_module(
    "check_public_artifact_test", ROOT / "scripts/check_public_artifact.py"
)


# Independent review baseline: this is deliberately not derived from the
# exporter at runtime.  The data allowlist and generated manifest must agree
# with this exact candidate set.
EXPECTED_PAYLOADS = {
    ".gitignore",
    ".github/workflows/validate.yml",
    ".public-export/allowlist.json",
    "MIGRATION.md",
    "README.md",
    "SECURITY.md",
    "versions.lock.json",
    "bin/claude-room",
    "bin/codex-room",
    "bin/codex-room-sync",
    "bin/opencode-paseo-peer",
    "bin/opencode-paseo-room",
    "bin/paseo-room-deny",
    "bin/paseo-room-mcp",
    "config/claude/lead.instructions.md.tmpl",
    "config/claude/lead.mcp.json.tmpl",
    "config/claude/lead.settings.json.tmpl",
    "config/claude/supervisor.instructions.md.tmpl",
    "config/claude/supervisor.mcp.json.tmpl",
    "config/claude/supervisor.settings.json.tmpl",
    "config/codex/lead.config.toml.tmpl",
    "config/codex/model-instructions.md",
    "config/codex/peer.config.toml.tmpl",
    "config/codex/supervisor.config.toml.tmpl",
    "config/opencode/paseo-lead.instructions.md.tmpl",
    "config/opencode/paseo-lead.json.tmpl",
    "config/opencode/paseo-peer.json",
    "config/opencode/paseo-supervisor.instructions.md.tmpl",
    "config/opencode/paseo-supervisor.json.tmpl",
    "config/paseo/config.json.tmpl",
    "config/paseo/orchestration-preferences.json",
    "docs/architecture.md",
    "docs/workflow.md",
    "hooks/room-role-guard.py",
    "hooks/test-room-role-guard.py",
    "protocols/DISSENT_PROTOCOL.md",
    "protocols/WORKFLOW_PROTOCOL.md",
    "scripts/check_public_artifact.py",
    "scripts/doctor.sh",
    "scripts/export_public_kit.py",
    "scripts/install-antigravity-acp.sh",
    "scripts/install.sh",
    "scripts/render_template.py",
    "templates/SUPERVISOR_NOTEBOOK.md",
    "templates/codex-config.minimal.toml",
    "templates/lead-leases.empty.json",
    "tests/test_portability.py",
    "tests/test_proxy_handback.py",
    "tests/test_public_export.py",
}

EXCLUDED_SOURCE_PATHS = {
    "docs/00-status-and-scope.md",
    "docs/10-troubleshooting-and-trace.md",
    "docs/12-decision-log.md",
    "docs/13-" + "history-and-legacy.md",
    "docs/14-session-" + "audit-2026-08-03.md",
    "docs/references/command-cheatsheet.md",
    "docs/references/mcp-" + "inventory.md",
    "docs/references/runtime-" + "inventory.md",
    "docs/references/source-of-truth.md",
    "docs/references/uploaded-materials.md",
}


class PublicExportTest(unittest.TestCase):
    def test_allowlist_matches_exact_review_baseline(self) -> None:
        allowlist_path = ROOT / "public-export/allowlist.json"
        if not allowlist_path.is_file():
            allowlist_path = ROOT / ".public-export/allowlist.json"
        allowlist = json.loads(
            allowlist_path.read_text(encoding="utf-8")
        )
        destinations = {entry["destination"] for entry in allowlist["files"]}
        self.assertEqual(destinations, EXPECTED_PAYLOADS)
        self.assertEqual(
            {entry["destination"] for entry in allowlist["generated"]},
            {EXPORT.MANIFEST_NAME},
        )
        self.assertEqual(
            {entry.destination for entry in EXPORT.PUBLIC_ALLOWLIST},
            EXPECTED_PAYLOADS,
        )
        self.assertEqual(len(EXPORT.PUBLIC_ALLOWLIST), len(EXPECTED_PAYLOADS))

    def test_export_has_exact_candidate_list_and_preserves_modes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifact = pathlib.Path(directory) / "public-kit"
            result = EXPORT.export_public_kit(artifact)

            self.assertEqual(result, artifact)
            files = {
                path.relative_to(artifact).as_posix()
                for path in artifact.rglob("*")
                if path.is_file()
            }
            self.assertEqual(files, EXPECTED_PAYLOADS | {EXPORT.MANIFEST_NAME})

            manifest = json.loads(
                (artifact / EXPORT.MANIFEST_NAME).read_text(encoding="utf-8")
            )
            self.assertEqual(
                {entry["path"] for entry in manifest["files"]},
                EXPECTED_PAYLOADS | {EXPORT.MANIFEST_NAME},
            )
            self.assertEqual(len(manifest["files"]), len(EXPECTED_PAYLOADS) + 1)
            self.assertEqual(SCANNER.scan_public_artifact(artifact), [])

            for entry in EXPORT.PUBLIC_ALLOWLIST:
                source = ROOT / entry.source
                if not source.exists() and not source.is_symlink():
                    source = ROOT / entry.destination
                destination = artifact / entry.destination
                self.assertEqual(
                    stat.S_IMODE(source.stat().st_mode),
                    stat.S_IMODE(destination.stat().st_mode),
                    entry.destination,
                )

    def test_excluded_source_material_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifact = EXPORT.export_public_kit(pathlib.Path(directory) / "public-kit")
            files = {
                path.relative_to(artifact).as_posix()
                for path in artifact.rglob("*")
                if path.is_file()
            }
            self.assertTrue(EXCLUDED_SOURCE_PATHS.isdisjoint(files))
            self.assertFalse(any(path.startswith(".serena/") for path in files))
            self.assertFalse(any(path.startswith("docs/references/") for path in files))
            self.assertNotIn("docs/01-architecture.md", files)
            self.assertNotIn("docs/08-provider-integrations.md", files)

    def test_public_docs_reference_commands_present_in_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifact = EXPORT.export_public_kit(pathlib.Path(directory) / "public-kit")
            readme = (artifact / "README.md").read_text(encoding="utf-8")
            migration = (artifact / "MIGRATION.md").read_text(encoding="utf-8")
            for command_path in (
                "scripts/export_public_kit.py",
                "scripts/check_public_artifact.py",
                "scripts/doctor.sh",
                "tests/test_public_export.py",
            ):
                self.assertTrue((artifact / command_path).is_file(), command_path)
                self.assertIn(command_path, readme + migration)
            for command in (
                "./scripts/doctor.sh --repo",
                "python3 tests/test_public_export.py",
                "python3 scripts/check_public_artifact.py",
                "git init",
                "git commit",
            ):
                self.assertIn(command, migration)

    def test_artifact_local_commands_run_from_exported_root(self) -> None:
        # The artifact runs this same test through doctor; avoid recursive
        # doctor/export subprocesses once the test itself is inside the output.
        if not (ROOT / "public-export").is_dir():
            return
        with tempfile.TemporaryDirectory() as directory:
            parent = pathlib.Path(directory)
            artifact = EXPORT.export_public_kit(parent / "public-kit")

            def run(*command: str) -> subprocess.CompletedProcess[str]:
                environment = os.environ.copy()
                environment["PYTHONDONTWRITEBYTECODE"] = "1"
                return subprocess.run(
                    command,
                    cwd=artifact,
                    check=True,
                    capture_output=True,
                    env=environment,
                    text=True,
                )

            run("./scripts/doctor.sh", "--repo")
            run(sys.executable, "tests/test_public_export.py")
            run(sys.executable, "scripts/check_public_artifact.py", ".")
            round_trip = parent / "round-trip"
            run(sys.executable, "scripts/export_public_kit.py", str(round_trip))
            run(sys.executable, "scripts/check_public_artifact.py", str(round_trip))

    def test_export_is_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = pathlib.Path(directory)
            first = EXPORT.export_public_kit(parent / "first")
            second = EXPORT.export_public_kit(parent / "second")
            first_bytes = {
                path.relative_to(first).as_posix(): path.read_bytes()
                for path in first.rglob("*")
                if path.is_file()
            }
            second_bytes = {
                path.relative_to(second).as_posix(): path.read_bytes()
                for path in second.rglob("*")
                if path.is_file()
            }
            self.assertEqual(first_bytes, second_bytes)

    def test_export_accepts_an_existing_empty_directory_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = pathlib.Path(directory) / "empty"
            destination.mkdir()
            self.assertEqual(EXPORT.export_public_kit(destination), destination)

            nonempty = pathlib.Path(directory) / "nonempty"
            nonempty.mkdir()
            (nonempty / ".keep").write_text("not empty\n")
            with self.assertRaises(EXPORT.ExportError):
                EXPORT.export_public_kit(nonempty)

    def test_allowlist_rejects_traversal_duplicates_missing_directories_and_binaries(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory) / "source"
            root.mkdir()
            (root / "good.txt").write_text("safe\n")
            (root / "binary.dat").write_bytes(b"\x00\x01binary")
            (root / "folder").mkdir()
            destination = pathlib.Path(directory) / "artifact"

            invalid_entries = (
                (EXPORT.ExportSpec("../good.txt", "good.txt"),),
                (EXPORT.ExportSpec("good.txt", "../escape.txt"),),
                (
                    EXPORT.ExportSpec("good.txt", "same.txt"),
                    EXPORT.ExportSpec("good.txt", "same.txt"),
                ),
                (EXPORT.ExportSpec("missing.txt", "missing.txt"),),
                (EXPORT.ExportSpec("folder", "folder"),),
                (EXPORT.ExportSpec("binary.dat", "binary.dat"),),
            )
            for entries in invalid_entries:
                with self.subTest(entries=entries):
                    with self.assertRaises(EXPORT.ExportError):
                        EXPORT.export_public_kit(
                            destination,
                            repo_root=root,
                            entries=entries,
                        )

    def test_export_rejects_symlink_sources_and_unsafe_destinations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = pathlib.Path(directory)
            root = parent / "source"
            root.mkdir()
            (root / "good.txt").write_text("safe\n")
            outside = parent / "outside.txt"
            outside.write_text("outside\n")
            os.symlink(outside, root / "link.txt")

            with self.assertRaises(EXPORT.ExportError):
                EXPORT.export_public_kit(
                    parent / "artifact",
                    repo_root=root,
                    entries=(EXPORT.ExportSpec("link.txt", "link.txt"),),
                )

            destination_link_target = parent / "target"
            destination_link_target.mkdir()
            os.symlink(destination_link_target, parent / "destination-link")
            with self.assertRaises(EXPORT.ExportError):
                EXPORT.export_public_kit(
                    parent / "destination-link",
                    repo_root=root,
                    entries=(EXPORT.ExportSpec("good.txt", "good.txt"),),
                )

            with self.assertRaises(EXPORT.ExportError):
                EXPORT.export_public_kit(
                    ROOT / "public-export" / "unsafe-output",
                    entries=EXPORT.PUBLIC_ALLOWLIST,
                )

    def test_scanner_rejects_manifest_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifact = EXPORT.export_public_kit(pathlib.Path(directory) / "artifact")
            (artifact / "extra.txt").write_text("unlisted\n")
            findings = SCANNER.scan_public_artifact(artifact)
            self.assertTrue(any(finding.rule == "manifest" for finding in findings))

    def test_scanner_binds_manifest_to_allowlist_and_rejects_vcs_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifact = EXPORT.export_public_kit(pathlib.Path(directory) / "artifact")
            manifest_path = artifact / EXPORT.MANIFEST_NAME
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            extra = artifact / "notes/organization-plan.md"
            extra.parent.mkdir()
            extra.write_text("self-listed but not allowlisted\n", encoding="utf-8")
            import hashlib

            data = extra.read_bytes()
            manifest["files"].append(
                {
                    "bytes": len(data),
                    "kind": "payload",
                    "mode": "0644",
                    "path": "notes/organization-plan.md",
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "source": "notes/organization-plan.md",
                }
            )
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            findings = SCANNER.scan_public_artifact(artifact)
            self.assertTrue(any(finding.rule == "allowlist" for finding in findings))

            vcs = artifact / ".git/config"
            vcs.parent.mkdir()
            vcs.write_text("[remote \"origin\"]\n", encoding="utf-8")
            findings = SCANNER.scan_public_artifact(artifact)
            self.assertTrue(any(finding.rule == "vcs-metadata" for finding in findings))

    def test_scanner_rejects_binary_and_symlink_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifact = EXPORT.export_public_kit(pathlib.Path(directory) / "artifact")
            (artifact / "extra.bin").write_bytes(b"\x00binary\n")
            os.symlink(artifact / "README.md", artifact / "extra-link")
            findings = SCANNER.scan_public_artifact(artifact)
            self.assertTrue(any(finding.rule == "binary" for finding in findings))
            self.assertTrue(any(finding.rule == "symlink" for finding in findings))

    def test_scanner_rejects_representative_forbidden_fixtures(self) -> None:
        fixtures = {
            "private-name": ("MO" + "SA", "private-name"),
            "unix-home": ("/" + "Users" + "/alice/projects/kit", "unix-home"),
            "windows-home": ("C:" + chr(92) + "Users" + chr(92) + "Alice", "windows-home"),
            "root-home": ("/" + "root/private/project", "unix-home"),
            "tilde-workspace": ("~/" + "Documents/client/project", "unix-home"),
            "unc-path": (chr(92) * 2 + "fileserver" + chr(92) + "team", "windows-home"),
            "uuid": ("123e4567-" + "e89b-12d3-a456-426614174000", "uuid"),
            "runtime-id": ("agent" + "_01J8ABCDEF1234567890", "runtime-id"),
            "corporate-email": ("owner" + "@corp.example.org", "corporate-email"),
            "credential": ("api" + "_key = \"live-looking-value-123456789\"", "credential"),
            "env-credential": ("OPENAI_" + "API" + "_KEY=live-looking-value", "credential"),
            "client-secret": ("client_" + "sec" + "ret: live-looking-value", "credential"),
            "refresh-token": ("refresh_" + "to" + "ken: live-looking-value", "credential"),
            "cookie": ("Cookie" + ": session=live-looking-value", "credential"),
            "private-key": ("-----BEGIN " + "PRIVATE KEY-----", "private-key"),
            "token": (
                "Authorization" + ": Bearer "
                + "eyJ" + "hbGciOiJub25lIn0" + ".xxxxxxxxxxxx.yyyyyyyyyyyy",
                "token",
            ),
            "database-uri": (
                "postgres" + "ql://name:password@db.internal.example/app",
                "database-uri",
            ),
            "driver-database-uri": (
                "postgres" + "ql+psycopg://name:password@db.example/app",
                "database-uri",
            ),
            "pgp-private-key": (
                "-----BEGIN " + "PGP PRIVATE KEY BLOCK-----",
                "private-key",
            ),
            "internal-domain": ("https" + "://api." + "corp.example/v1", "internal-endpoint"),
            "private-ip": ("http" + "://10." + "23.4.5:6767/mcp", "internal-endpoint"),
            "crafted-runtime": ("workspace_" + "id=workspace-" + "private123", "runtime-id"),
            "source-metadata": (
                "runtime" + " " + "inventory: source-only record",
                "source-metadata",
            ),
            "source-metadata-generic": (
                "source-only " + "inventory record",
                "source-metadata",
            ),
        }
        for name, (content, expected_rule) in fixtures.items():
            with self.subTest(name=name):
                findings = self._scan_fixture(content, "fixture.txt")
                self.assertTrue(
                    any(finding.rule == expected_rule for finding in findings),
                    findings,
                )

        findings = self._scan_fixture("field: value\n", "runtime-" + "inventory.md")
        self.assertTrue(any(finding.rule == "source-metadata" for finding in findings))

    def test_scanner_allows_synthetic_values_and_public_urls(self) -> None:
        content = """\
token: <TOKEN>
email: test@example.com
home: $HOME/example-project
runtime: PASEO_AGENT_ID=<runtime-id>
uuid: 00000000-0000-0000-0000-000000000000
local: http://127.0.0.1:6767/health
docs: https://paseo.sh/docs/example
upstream: https://github.com/example/upstream
"""
        self.assertEqual(self._scan_fixture(content, "fixture.txt"), [])

    def _scan_fixture(self, content: str, destination: str):
        with tempfile.TemporaryDirectory() as directory:
            parent = pathlib.Path(directory)
            source = parent / "source"
            source.mkdir()
            (source / "fixture.txt").write_text(content)
            allowlist_path = source / "allowlist.json"
            allowlist = {
                "format": 1,
                "manifest": EXPORT.MANIFEST_NAME,
                "generated": [{"destination": EXPORT.MANIFEST_NAME, "mode": "0644"}],
                "files": [
                    {"source": "fixture.txt", "destination": destination},
                    {
                        "source": "allowlist.json",
                        "destination": SCANNER.ALLOWLIST_NAME,
                    },
                ],
            }
            allowlist_path.write_text(json.dumps(allowlist), encoding="utf-8")
            artifact = parent / "artifact"
            EXPORT.export_public_kit(
                artifact,
                repo_root=source,
                entries=(
                    EXPORT.ExportSpec("fixture.txt", destination),
                    EXPORT.ExportSpec("allowlist.json", SCANNER.ALLOWLIST_NAME),
                ),
            )
            return SCANNER.scan_public_artifact(artifact)


if __name__ == "__main__":
    unittest.main()
