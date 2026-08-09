#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
import re
import stat
import tempfile
import tomllib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
UUID4 = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)
SECRET_SHAPES = (
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"postgres(?:ql)?://[^/\s:]+:[^@\s]+@", re.IGNORECASE),
)


def repository_text_files() -> list[pathlib.Path]:
    excluded = {".git", ".serena", "__pycache__"}
    files = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in excluded for part in path.parts):
            continue
        try:
            path.read_text()
        except UnicodeDecodeError:
            continue
        files.append(path)
    return files


class PortabilityTest(unittest.TestCase):
    def test_no_machine_identity_or_runtime_uuid(self) -> None:
        for path in repository_text_files():
            text = path.read_text()
            self.assertNotIn("/" + "Users/", text, path)
            self.assertIsNone(UUID4.search(text), path)

    def test_no_obvious_secret_shape(self) -> None:
        for path in repository_text_files():
            text = path.read_text()
            for pattern in SECRET_SHAPES:
                self.assertIsNone(pattern.search(text), path)

    def test_templates_render_and_parse(self) -> None:
        home = pathlib.Path("/tmp/paseo-kit-test-home")
        paseo = (
            (ROOT / "config/paseo/config.json.tmpl")
            .read_text()
            .replace("{{HOME}}", str(home))
            .replace(
                "{{ANTIGRAVITY_ACP_BINARY}}",
                str(home / ".local/share/antigravity-acp/dist/agy-acp-test"),
            )
        )
        value = json.loads(paseo)
        self.assertTrue(value["daemon"]["mcp"]["enabled"])
        self.assertFalse(value["daemon"]["mcp"]["injectIntoAgents"])
        claude_supervisor = value["agents"]["providers"]["claude-supervisor"]
        self.assertEqual(claude_supervisor["extends"], "claude")
        self.assertEqual(
            claude_supervisor["models"][0]["id"],
            "claude-opus-4-8",
        )
        self.assertIn("Agent", claude_supervisor["disallowedTools"])
        claude_lead = value["agents"]["providers"]["claude-lead"]
        self.assertEqual(claude_lead["extends"], "claude")
        self.assertEqual(
            claude_lead["models"][0]["id"],
            "claude-sonnet-5[1m]",
        )
        self.assertEqual(
            claude_lead["env"]["CLAUDE_CODE_AUTO_COMPACT_WINDOW"],
            "300000",
        )
        self.assertEqual(
            claude_lead["models"][0]["thinkingOptions"][0]["id"],
            "high",
        )
        self.assertIn("Agent", claude_lead["disallowedTools"])

        opencode_supervisor = value["agents"]["providers"]["opencode-supervisor"]
        self.assertEqual(opencode_supervisor["extends"], "acp")
        self.assertEqual(
            opencode_supervisor["models"][0]["id"],
            "aibox/deepseek-v4-flash",
        )
        opencode_lead = value["agents"]["providers"]["opencode-lead"]
        self.assertEqual(opencode_lead["extends"], "acp")
        self.assertEqual(opencode_lead["models"][0]["id"], "aibox/glm-5.2")
        self.assertEqual(
            opencode_lead["models"][0]["thinkingOptions"][0]["id"],
            "max",
        )

        for role in ("supervisor", "lead", "peer"):
            text = (
                ROOT / f"config/codex/{role}.config.toml.tmpl"
            ).read_text().replace("{{HOME}}", str(home))
            self.assertNotIn("{{", text)
            tomllib.loads(text)

        for role in ("supervisor", "lead"):
            for name in ("instructions.md", "settings.json", "mcp.json"):
                text = (
                    ROOT / f"config/claude/{role}.{name}.tmpl"
                ).read_text().replace("{{HOME}}", str(home))
                self.assertNotIn("{{", text)
                if name.endswith(".json"):
                    json.loads(text)

        for role in ("supervisor", "lead"):
            text = (
                ROOT / f"config/opencode/paseo-{role}.json.tmpl"
            ).read_text().replace("{{HOME}}", str(home))
            self.assertNotIn("{{", text)
            opencode = json.loads(text)
            self.assertEqual(opencode["default_agent"], "build")
            self.assertEqual(opencode["permission"]["task"], "deny")
            self.assertEqual(
                opencode["mcp"]["paseo"]["command"][-1],
                role,
            )

            instructions = (
                ROOT / f"config/opencode/paseo-{role}.instructions.md.tmpl"
            ).read_text().replace("{{HOME}}", str(home))
            self.assertNotIn("{{", instructions)

    def test_runtime_state_templates_are_empty(self) -> None:
        leases = json.loads((ROOT / "templates/lead-leases.empty.json").read_text())
        self.assertEqual(leases, {"version": 1, "leases": {}})

    def test_expected_executables_are_marked_executable(self) -> None:
        paths = [
            ROOT / "bin/claude-room",
            ROOT / "bin/codex-room",
            ROOT / "bin/codex-room-sync",
            ROOT / "bin/paseo-room-mcp",
            ROOT / "bin/opencode-paseo-peer",
            ROOT / "bin/opencode-paseo-room",
            ROOT / "bin/paseo-room-deny",
            ROOT / "scripts/install.sh",
            ROOT / "scripts/install-antigravity-acp.sh",
            ROOT / "scripts/doctor.sh",
        ]
        for path in paths:
            self.assertTrue(path.stat().st_mode & stat.S_IXUSR, path)

    def test_render_script_writes_atomically(self) -> None:
        from importlib.util import module_from_spec, spec_from_file_location

        script = ROOT / "scripts/render_template.py"
        spec = spec_from_file_location("render_template", script)
        assert spec and spec.loader
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            source = root / "source"
            target = root / "nested/target"
            source.write_text("home={{HOME}}\n")
            module.render(source, target, root / "home")
            self.assertEqual(target.read_text(), f"home={root / 'home'}\n")


if __name__ == "__main__":
    unittest.main()
