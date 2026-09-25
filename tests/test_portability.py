#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import pathlib
import plistlib
import re
import stat
import struct
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
    excluded = {".git", ".serena", "__pycache__", "node_modules"}
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
        internal_slp_providers = {
            "claude-supervisor",
            "codex-supervisor",
            "codex-lead",
            "claude-lead",
            "claude-reviewer",
            "claude-watcher",
            "codex-peer",
            "opencode-peer",
            "opencode-supervisor",
            "opencode-lead",
            "gemini-ui",
        }
        self.assertEqual(
            {
                name
                for name, provider in value["agents"]["providers"].items()
                if provider.get("paseoTools") == {"enabled": False}
            },
            internal_slp_providers,
        )
        claude_supervisor = value["agents"]["providers"]["claude-supervisor"]
        self.assertEqual(claude_supervisor["extends"], "claude")
        self.assertEqual(
            claude_supervisor["models"][0]["id"],
            "claude-opus-5-5",
        )
        self.assertEqual(
            claude_supervisor["models"][0]["thinkingOptions"],
            [{"id": "xhigh", "label": "XHigh", "isDefault": True}],
        )
        self.assertEqual(
            claude_supervisor["env"]["CLAUDE_CODE_AUTO_COMPACT_WINDOW"],
            "300000",
        )
        self.assertIn("Agent", claude_supervisor["disallowedTools"])
        claude_lead = value["agents"]["providers"]["claude-lead"]
        self.assertEqual(claude_lead["extends"], "claude")
        self.assertEqual(
            claude_lead["models"][0]["id"],
            "claude-opus-5-5",
        )
        self.assertEqual(
            claude_lead["env"]["CLAUDE_CODE_AUTO_COMPACT_WINDOW"],
            "300000",
        )
        self.assertEqual(
            claude_lead["models"][0]["thinkingOptions"][0]["id"],
            "xhigh",
        )
        self.assertIn("Agent", claude_lead["disallowedTools"])

        reviewer = value["agents"]["providers"]["claude-reviewer"]
        self.assertEqual(reviewer["models"][0]["id"], "claude-opus-5-5")
        self.assertEqual(reviewer["models"][0]["thinkingOptions"][0]["id"], "high")
        watcher = value["agents"]["providers"]["claude-watcher"]
        self.assertEqual(watcher["models"][0]["id"], "claude-sonnet-5")
        self.assertEqual(watcher["models"][0]["thinkingOptions"][0]["id"], "medium")
        peer = value["agents"]["providers"]["codex-peer"]
        self.assertEqual([item["id"] for item in peer["models"]], ["gpt-6-luna"])

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

    def test_installed_paseo_08_provider_policy_schema_when_available(self) -> None:
        app = pathlib.Path(
            os.environ.get("PASEO_APP_PATH", "/Applications/Paseo.app")
        )
        plist_path = app / "Contents/Info.plist"
        asar_path = app / "Contents/Resources/app.asar"
        if not plist_path.is_file() or not asar_path.is_file():
            self.skipTest("installed Paseo application bundle is unavailable")
        with plist_path.open("rb") as stream:
            version = plistlib.load(stream)["CFBundleShortVersionString"]
        expected = json.loads((ROOT / "versions.lock.json").read_text())["paseo"]
        self.assertEqual(version, expected)
        self.assertEqual(version, "0.9.1")

        data = asar_path.read_bytes()
        header_length = struct.unpack("<I", data[12:16])[0]
        header = json.loads(data[16 : 16 + header_length])
        data_offset = 8 + struct.unpack("<I", data[4:8])[0]

        def asar_text(relative: str) -> str:
            node = header
            for component in relative.split("/"):
                node = node["files"][component]
            offset = data_offset + int(node["offset"])
            return data[offset : offset + node["size"]].decode()

        schema = asar_text(
            "node_modules/@getpaseo/protocol/dist/provider-config.js"
        )
        policy = asar_text(
            "node_modules/@getpaseo/server/dist/server/server/agent/"
            "paseo-tool-policy.js"
        )
        manager = asar_text(
            "node_modules/@getpaseo/server/dist/server/server/agent/"
            "agent-manager.js"
        )
        bootstrap = asar_text(
            "node_modules/@getpaseo/server/dist/server/server/bootstrap.js"
        )
        paseo_tools = asar_text(
            "node_modules/@getpaseo/server/dist/server/server/agent/tools/"
            "paseo-tools.js"
        )
        self.assertIn("paseoTools: ProviderPaseoToolsPolicySchema.optional()", schema)
        self.assertIn("enabled: z.boolean().optional()", schema)
        self.assertIn("policy?.enabled !== false", policy)
        self.assertGreaterEqual(manager.count("isPaseoToolPolicyEnabled"), 3)
        self.assertGreaterEqual(manager.count("withRuntimePaseoMcpServer"), 2)
        self.assertIn("agentManager.getPaseoToolPolicy(callerAgentId)", bootstrap)
        self.assertIn(
            "if (!isPaseoToolEnabled(options.paseoToolPolicy, name))",
            paseo_tools,
        )

    def test_runtime_state_templates_are_empty(self) -> None:
        leases = json.loads((ROOT / "templates/lead-leases.empty.json").read_text())
        self.assertEqual(leases, {"version": 2, "leases": {}})

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
