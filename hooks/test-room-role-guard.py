#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import tempfile
import unittest


GUARD = pathlib.Path(__file__).with_name("room-role-guard.py")


class RoomRoleGuardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temporary.name)
        self.agents = self.root / "agents"
        self.agents.mkdir()
        self.preferences = self.root / "preferences.json"
        self.preferences.write_text(
            json.dumps(
                {
                    "providers": {
                        "planning": "codex-lead/gpt-5.6-sol",
                        "impl": "opencode-peer/aibox/deepseek-v4-flash",
                        "impl_deep": "codex-peer/gpt-5.6-luna",
                        "search": "codex-peer/gpt-5.6-luna",
                        "ui": "gemini-ui/gemini-3.6-flash-medium",
                        "research": "opencode-peer/aibox/deepseek-v4-flash",
                        "audit": "codex-peer/gpt-5.6-luna",
                    }
                }
            )
        )
        self.leases = self.root / "lead-leases.json"
        self.supervisor_id = "supervisor-1"
        self.lead_id = "lead-1"
        self.write_agent(
            {
                "id": self.supervisor_id,
                "workspaceId": "workspace-control",
                "labels": {"role": "supervisor"},
            }
        )
        self.write_agent(
            {
                "id": self.lead_id,
                "workspaceId": "workspace-project",
                "labels": {
                    "role": "lead",
                    "paseo.parent-agent-id": self.supervisor_id,
                },
            }
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_agent(self, value: dict) -> None:
        path = self.agents / f"{value['id']}.json"
        path.write_text(json.dumps(value))

    def run_guard(self, role: str, payload: dict, agent_id: str) -> dict | None:
        env = {
            **os.environ,
            "PASEO_AGENT_ID": agent_id,
            "ROOM_GUARD_AGENTS_DIR": str(self.agents),
            "ROOM_GUARD_PREFERENCES": str(self.preferences),
            "ROOM_GUARD_LEASES_PATH": str(self.leases),
            "ROOM_GUARD_AUDIT_PATH": str(self.root / "guard-audit.jsonl"),
        }
        result = subprocess.run(
            ["python3", str(GUARD), "--role", role],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            env=env,
            check=True,
        )
        return json.loads(result.stdout) if result.stdout else None

    @staticmethod
    def pre(tool_name: str, tool_input: dict) -> dict:
        return {
            "hook_event_name": "PreToolUse",
            "tool_name": tool_name,
            "tool_input": tool_input,
            "tool_use_id": "tool-1",
        }

    def test_supervisor_rejects_stock_lead(self) -> None:
        result = self.run_guard(
            "supervisor",
            self.pre(
                "mcp__paseo__create_agent",
                {
                    "provider": "codex/gpt-5.4",
                    "workspaceId": "workspace-new",
                    "title": "Lead",
                    "initialPrompt": "Own the objective.",
                },
            ),
            self.supervisor_id,
        )
        self.assertEqual(
            result["hookSpecificOutput"]["permissionDecision"],
            "deny",
        )

    def test_supervisor_rewrites_valid_lead_and_reserves_lease(self) -> None:
        result = self.run_guard(
            "supervisor",
            self.pre(
                "mcp__paseo__create_agent",
                {
                    "provider": "codex-lead/gpt-5.6-sol",
                    "workspaceId": "workspace-new",
                    "title": "Lead",
                    "initialPrompt": "Own the objective.",
                },
            ),
            self.supervisor_id,
        )
        output = result["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "allow")
        self.assertEqual(output["updatedInput"]["labels"]["role"], "lead")
        self.assertEqual(output["updatedInput"]["labels"]["route"], "planning")
        self.assertTrue(output["updatedInput"]["notifyOnFinish"])
        lease = json.loads(self.leases.read_text())["leases"]["workspace-new"]
        self.assertEqual(lease["state"], "pending")

    def test_lead_rewrites_search_thinking(self) -> None:
        result = self.run_guard(
            "lead",
            self.pre(
                "mcp__paseo__create_agent",
                {
                    "provider": "codex-peer/gpt-5.6-luna",
                    "title": "Search",
                    "initialPrompt": "Find the call path.",
                    "labels": {"route": "search"},
                    "settings": {"thinkingOptionId": "max"},
                },
            ),
            self.lead_id,
        )
        updated = result["hookSpecificOutput"]["updatedInput"]
        self.assertEqual(updated["labels"]["role"], "peer")
        self.assertEqual(updated["labels"]["task_state"], "ASSIGNED")
        self.assertEqual(updated["settings"]["thinkingOptionId"], "low")

    def test_lead_rejects_wrong_route_provider(self) -> None:
        result = self.run_guard(
            "lead",
            self.pre(
                "mcp__paseo__create_agent",
                {
                    "provider": "opencode-peer/aibox/deepseek-v4-flash",
                    "title": "Search",
                    "initialPrompt": "Find the call path.",
                    "labels": {"route": "search"},
                },
            ),
            self.lead_id,
        )
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_peer_cannot_use_paseo(self) -> None:
        result = self.run_guard(
            "peer",
            self.pre("mcp__paseo__list_agents", {}),
            "peer-1",
        )
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_peer_cannot_bypass_with_cli(self) -> None:
        result = self.run_guard(
            "peer",
            self.pre("Bash", {"command": "/opt/test-user/bin/paseo agent run task"}),
            "peer-1",
        )
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_lead_cannot_bypass_creation_with_cli(self) -> None:
        result = self.run_guard(
            "lead",
            self.pre("Bash", {"command": "paseo run --provider codex/gpt-5.4 task"}),
            self.lead_id,
        )
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_post_create_activates_lead_lease(self) -> None:
        self.run_guard(
            "supervisor",
            self.pre(
                "mcp__paseo__create_agent",
                {
                    "provider": "codex-lead/gpt-5.6-sol",
                    "workspaceId": "workspace-new",
                    "title": "Lead",
                    "initialPrompt": "Own the objective.",
                },
            ),
            self.supervisor_id,
        )
        result = self.run_guard(
            "supervisor",
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "mcp__paseo__create_agent",
                "tool_input": {"workspaceId": "workspace-new"},
                "tool_use_id": "tool-1",
                "tool_response": {
                    "structuredContent": {
                        "agentId": "lead-new",
                        "workspaceId": "workspace-new",
                    }
                },
            },
            self.supervisor_id,
        )
        self.assertIsNone(result)
        lease = json.loads(self.leases.read_text())["leases"]["workspace-new"]
        self.assertEqual(lease["state"], "active")
        self.assertEqual(lease["lead_agent_id"], "lead-new")

    def test_lead_can_update_only_owned_peer(self) -> None:
        self.write_agent(
            {
                "id": "peer-owned",
                "workspaceId": "workspace-project",
                "labels": {
                    "role": "peer",
                    "paseo.parent-agent-id": self.lead_id,
                },
            }
        )
        allowed = self.run_guard(
            "lead",
            self.pre(
                "mcp__paseo__update_agent",
                {
                    "agentId": "peer-owned",
                    "labels": {"task_state": "ACCEPTED"},
                },
            ),
            self.lead_id,
        )
        denied = self.run_guard(
            "supervisor",
            self.pre(
                "mcp__paseo__update_agent",
                {
                    "agentId": "peer-owned",
                    "labels": {"task_state": "ACCEPTED"},
                },
            ),
            self.supervisor_id,
        )
        self.assertIsNone(allowed)
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_peer_cannot_reach_nested_paseo_tool_through_exec(self) -> None:
        result = self.run_guard(
            "peer",
            self.pre(
                "exec",
                {"input": 'const r=await tools.mcp__paseo__list_agents({});text(r)'},
            ),
            "peer-1",
        )
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_supervisor_nested_exec_rejects_wrong_lead_route(self) -> None:
        source = """
const r=await tools.mcp__paseo__create_agent({
  workspaceId:"workspace-new",
  provider:"codex/gpt-5.4",
  notifyOnFinish:true,
  labels:{role:"lead",route:"planning",task_state:"LEASED"},
  settings:{modeId:"full-access"},
  initialPrompt:`Own the objective.`
});text(r)
"""
        result = self.run_guard(
            "supervisor",
            self.pre("exec", {"input": source}),
            self.supervisor_id,
        )
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_supervisor_nested_exec_reserves_lease(self) -> None:
        source = """
const r=await tools.mcp__paseo__create_agent({
  workspaceId:"workspace-new",
  provider:"codex-lead/gpt-5.6-sol",
  notifyOnFinish:true,
  labels:{role:"lead",route:"planning",task_state:"LEASED"},
  settings:{modeId:"full-access"},
  initialPrompt:`Own the objective.`
});text(r)
"""
        result = self.run_guard(
            "supervisor",
            self.pre("exec", {"input": source}),
            self.supervisor_id,
        )
        self.assertIsNone(result)
        lease = json.loads(self.leases.read_text())["leases"]["workspace-new"]
        self.assertEqual(lease["state"], "pending")

    def test_lead_nested_exec_requires_full_static_route_contract(self) -> None:
        missing_mode = """
const r=await tools.mcp__paseo__create_agent({
  provider:"codex-peer/gpt-5.6-luna",
  notifyOnFinish:true,
  labels:{role:"peer",route:"search",task_state:"ASSIGNED"},
  settings:{thinkingOptionId:"low"},
  initialPrompt:`Search only.`
});text(r)
"""
        denied = self.run_guard(
            "lead",
            self.pre("exec", {"input": missing_mode}),
            self.lead_id,
        )
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")

        valid = missing_mode.replace(
            'settings:{thinkingOptionId:"low"}',
            'settings:{modeId:"full-access",thinkingOptionId:"low"}',
        )
        allowed = self.run_guard(
            "lead",
            self.pre("exec", {"input": valid}),
            self.lead_id,
        )
        self.assertIsNone(allowed)

    def test_post_nested_exec_activates_lead_lease(self) -> None:
        source = """
const r=await tools.mcp__paseo__create_agent({
  workspaceId:"workspace-new",
  provider:"codex-lead/gpt-5.6-sol",
  notifyOnFinish:true,
  labels:{role:"lead",route:"planning",task_state:"LEASED"},
  settings:{modeId:"full-access"},
  initialPrompt:`Own the objective.`
});text(r)
"""
        self.run_guard(
            "supervisor",
            self.pre("exec", {"input": source}),
            self.supervisor_id,
        )
        result = self.run_guard(
            "supervisor",
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "exec",
                "tool_input": {"input": source},
                "tool_use_id": "tool-1",
                "tool_response": '{"structuredContent":{"agentId":"lead-new"}}',
            },
            self.supervisor_id,
        )
        self.assertIsNone(result)
        lease = json.loads(self.leases.read_text())["leases"]["workspace-new"]
        self.assertEqual(lease["state"], "active")
        self.assertEqual(lease["lead_agent_id"], "lead-new")


if __name__ == "__main__":
    unittest.main()
