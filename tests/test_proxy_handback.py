#!/usr/bin/env python3
from __future__ import annotations

import importlib.machinery
import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
PROXY = ROOT / "bin/paseo-room-mcp"


def load_proxy():
    loader = importlib.machinery.SourceFileLoader("paseo_room_mcp_test", str(PROXY))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class HandbackTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_proxy()
        self.lead = {
            "id": "lead-one",
            "labels": {
                "role": "lead",
                "route": "planning",
                "task_state": "LEASED",
                "paseo.parent-agent-id": "supervisor-one",
            },
            "archivedAt": None,
        }
        self.parent = {
            "id": "supervisor-one",
            "provider": "codex-supervisor",
            "labels": {},
            "archivedAt": None,
        }
        self.module.load_agent_record = self.load_agent
        self.calls: list[dict] = []
        self.module.upstream_call = self.upstream_call

    def load_agent(self, agent_id: str):
        return self.lead if agent_id == "lead-one" else self.parent

    def upstream_call(self, _agent_id: str, payload: dict):
        self.calls.append(payload["params"])
        return {"result": {"content": [{"type": "text", "text": "ok"}], "isError": False}}

    def test_success_marks_handback_ready_and_preserves_parent_label(self) -> None:
        result = self.module.handback_to_parent(
            "lead-one",
            "lead",
            1,
            {"message": "validated outcome"},
        )
        self.assertFalse(result["result"]["isError"])
        self.assertEqual(self.calls[0]["name"], "send_agent_prompt")
        self.assertEqual(self.calls[1]["name"], "update_agent")
        labels = self.calls[1]["arguments"]["labels"]
        self.assertEqual(labels["task_state"], "HANDBACK_READY")
        self.assertEqual(labels["paseo.parent-agent-id"], "supervisor-one")

    def test_duplicate_handback_is_rejected(self) -> None:
        self.lead["labels"]["task_state"] = "HANDBACK_READY"
        result = self.module.handback_to_parent(
            "lead-one",
            "lead",
            2,
            {"message": "duplicate"},
        )
        self.assertTrue(result["result"]["isError"])
        self.assertEqual(self.calls, [])

    def test_budget_supervisor_is_accepted_as_canonical_parent(self) -> None:
        self.parent["provider"] = "opencode-supervisor"
        result = self.module.handback_to_parent(
            "lead-one",
            "lead",
            3,
            {"message": "budget stack validated outcome"},
        )
        self.assertFalse(result["result"]["isError"])
        self.assertEqual(self.calls[0]["name"], "send_agent_prompt")


if __name__ == "__main__":
    unittest.main()
