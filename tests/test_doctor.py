#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class DoctorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tempdir.name)
        self.fake_bin = self.root / "bin"
        self.fake_bin.mkdir()
        self.home = self.root / "home"
        (self.home / ".paseo").mkdir(parents=True)
        (self.home / ".codex-runtime/supervisor").mkdir(parents=True)
        (self.home / ".codex-runtime/lead").mkdir(parents=True)
        (self.home / ".codex-runtime/peer").mkdir(parents=True)
        rendered_config = (
            (ROOT / "config/paseo/config.json.tmpl")
            .read_text(encoding="utf-8")
            .replace("{{HOME}}", str(self.home))
            .replace(
                "{{ANTIGRAVITY_ACP_BINARY}}",
                str(self.home / ".local/share/antigravity-acp/dist/agy-acp-test"),
            )
        )
        (self.home / ".paseo/config.json").write_text(
            rendered_config,
            encoding="utf-8",
        )
        for role in ("supervisor", "lead"):
            (self.home / f".codex-runtime/{role}/config.toml").write_text(
                "[mcp_servers.paseo]\n", encoding="utf-8"
            )
        (self.home / ".codex-runtime/peer/config.toml").write_text(
            "[other]\nvalue = true\n", encoding="utf-8"
        )
        for source, destination in (
            ("bin/paseo-room-mcp", ".local/bin/paseo-room-mcp"),
            ("bin/paseo-room-workflow", ".local/bin/paseo-room-workflow"),
            ("bin/room_workflow.py", ".local/bin/room_workflow.py"),
            ("bin/room_attention.py", ".local/bin/room_attention.py"),
            ("bin/room_land.py", ".local/bin/room_land.py"),
            ("hooks/room-role-guard.py", ".codex/hooks/room-role-guard.py"),
            ("hooks/test-room-role-guard.py", ".codex/hooks/test-room-role-guard.py"),
            (
                "protocols/WORKFLOW_PROTOCOL.md",
                ".config/room-workflow/WORKFLOW_PROTOCOL.md",
            ),
        ):
            target = self.home / destination
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / source).read_bytes())
        for role in ("supervisor", "lead"):
            self._render(
                ROOT / f"config/codex/{role}.config.toml.tmpl",
                self.home / f".codex/{role}.config.toml",
            )
            for asset in ("instructions.md", "settings.json", "mcp.json"):
                self._render(
                    ROOT / f"config/claude/{role}.{asset}.tmpl",
                    self.home / f".config/claude-room/{role}/{asset}",
                )
            for asset in ("json", "instructions.md"):
                self._render(
                    ROOT / f"config/opencode/paseo-{role}.{asset}.tmpl",
                    self.home / f".config/opencode/paseo-{role}.{asset}",
                )
        for role in ("peer", "watcher"):
            for asset in ("instructions.md", "settings.json", "mcp.json"):
                self._render(
                    ROOT / f"config/claude/{role}.{asset}.tmpl",
                    self.home / f".config/claude-room/{role}/{asset}",
                )
        (self.home / ".zshrc").write_text("# unchanged\n", encoding="utf-8")

        self._write_executable(
            "paseo",
            """#!/usr/bin/env bash
set -eu
if [[ -n "${FAKE_PASEO_CALLED:-}" ]]; then
  touch "$FAKE_PASEO_CALLED"
fi
if [[ \"${1:-}\" == \"--version\" ]]; then
  printf '%s\\n' \"${FAKE_PASEO_CLI_VERSION:?}\"
elif [[ \"${1:-}\" == \"daemon\" && \"${2:-}\" == \"status\" && \"${3:-}\" == \"--json\" ]]; then
  printf '%s\\n' \"${FAKE_PASEO_STATUS_JSON:?}\"
else
  exit 64
fi
""",
        )
        for command in ("claude", "codex"):
            self._write_executable(command, "#!/usr/bin/env bash\nexit 0\n")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _write_executable(self, name: str, contents: str) -> None:
        path = self.fake_bin / name
        path.write_text(contents, encoding="utf-8")
        path.chmod(0o755)

    def _render(self, source: pathlib.Path, destination: pathlib.Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "python3",
                str(ROOT / "scripts/render_template.py"),
                str(source),
                str(destination),
                "--home",
                str(self.home),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

    def run_doctor(
        self,
        mode: str,
        *,
        cli_version: str = "0.9.1",
        status_json: str = '{"daemonVersion":"0.9.1"}',
        role: str | None = None,
        wrapper_active: bool = False,
        wrapper_contents: bytes | None = None,
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["HOME"] = str(self.home)
        environment["PASEO_KIT_HOME"] = str(self.home)
        environment["PASEO_APP_PATH"] = str(self.root / "no-paseo-app")
        path_entries = [self.fake_bin]
        if wrapper_active:
            wrapper_dir = self.home / ".local/share/paseo-room-bin"
            wrapper_dir.mkdir(parents=True, exist_ok=True)
            (wrapper_dir / "called").unlink(missing_ok=True)
            wrapper = wrapper_dir / "paseo"
            wrapper.write_bytes(
                wrapper_contents
                if wrapper_contents is not None
                else (ROOT / "bin/paseo-room-deny").read_bytes()
            )
            wrapper.chmod(0o755)
            path_entries.insert(0, wrapper_dir)
        environment["PATH"] = os.pathsep.join(
            [str(path) for path in path_entries]
            + [environment.get("PATH", "")]
        )
        environment["FAKE_PASEO_CLI_VERSION"] = cli_version
        environment["FAKE_PASEO_STATUS_JSON"] = status_json
        called = self.root / "paseo-called"
        called.unlink(missing_ok=True)
        environment["FAKE_PASEO_CALLED"] = str(called)
        if role is None:
            environment.pop("PASEO_ROOM_ROLE", None)
        else:
            environment["PASEO_ROOM_ROLE"] = role
        return subprocess.run(
            [str(ROOT / "scripts/doctor.sh"), mode],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
        )

    def test_preflight_requires_effective_cli_version_pin(self) -> None:
        result = self.run_doctor("--preflight")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Paseo CLI version matches pin 0.9.1", result.stdout)

        result = self.run_doctor("--preflight", cli_version="0.7.9")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Paseo CLI version mismatch", result.stdout + result.stderr)

    def test_live_requires_parseable_matching_daemon_version(self) -> None:
        result = self.run_doctor(
            "--live",
            status_json='{"connectedDaemon":"reachable","daemonVersion":"0.9.1"}',
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Paseo daemon version matches pin 0.9.1", result.stdout)

        for status_json, message in (
            ("not-json", "invalid or missing string daemonVersion"),
            ('{"daemonVersion":"0.7.9"}', "Paseo daemon version mismatch"),
            ('{"daemonVersion":null}', "invalid or missing string daemonVersion"),
        ):
            with self.subTest(status_json=status_json):
                result = self.run_doctor("--live", status_json=status_json)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stdout + result.stderr)

    def test_live_requires_internal_provider_native_tool_denial(self) -> None:
        config_path = self.home / ".paseo/config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["agents"]["providers"]["codex-peer"].pop("paseoTools")
        config_path.write_text(json.dumps(config), encoding="utf-8")
        result = self.run_doctor("--live")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "installed provider policy does not defensively disable native Paseo tools",
            result.stdout + result.stderr,
        )

    def test_role_wrapper_mismatch_fails_without_editing_shell_config(self) -> None:
        shell_config = self.home / ".zshrc"
        before = shell_config.read_bytes()
        result = self.run_doctor("--preflight", role="peer")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "not the exact executable room deny wrapper",
            result.stdout + result.stderr,
        )
        self.assertIn(
            "doctor will not modify shell config",
            result.stdout + result.stderr,
        )
        self.assertFalse((self.root / "paseo-called").exists())
        self.assertEqual(shell_config.read_bytes(), before)

    def test_active_room_wrapper_fails_closed_without_calling_wrapper(self) -> None:
        result = self.run_doctor(
            "--live",
            role="peer",
            wrapper_active=True,
            status_json='{"daemonVersion":"not-used"}',
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CLI version cannot be verified", result.stdout + result.stderr)
        self.assertIn("daemon version cannot be verified", result.stdout + result.stderr)
        self.assertFalse((self.root / "paseo-called").exists())

    def test_role_wrapper_content_mismatch_fails_closed(self) -> None:
        result = self.run_doctor(
            "--preflight",
            role="peer",
            wrapper_active=True,
            wrapper_contents=b"#!/bin/sh\nexit 77\n",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "not the exact executable room deny wrapper",
            result.stdout + result.stderr,
        )


if __name__ == "__main__":
    unittest.main()
