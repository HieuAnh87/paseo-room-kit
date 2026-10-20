#!/usr/bin/env python3
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import pathlib
import re
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
PROXY = ROOT / "bin/paseo-room-mcp"
SUPERVISOR_ID = "supervisor-one"
LEAD_ID = "lead-one"
PEER_ID = "peer-one"
WORKSPACE_ID = "workspace-project"


def load_proxy():
    loader = importlib.machinery.SourceFileLoader("paseo_room_mcp_test", str(PROXY))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class ManagedLifecycleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temporary.name)
        self.module = load_proxy()
        self.module.AGENT_ID_PATTERN = re.compile(r"^[a-z]+(?:-[a-z]+)*$")
        self.module.AGENTS_ROOT = self.root / "agents"
        self.module.LEASES_PATH = self.root / "lead-leases.json"
        self.module.WORKSPACES_PATH = self.root / "workspaces.json"
        self.module.HISTORY_PATH = self.root / "slp-decision-history.jsonl"
        (self.module.AGENTS_ROOT / "records").mkdir(parents=True)
        self.lead = {
            "id": LEAD_ID,
            "workspaceId": WORKSPACE_ID,
            "provider": "codex-lead",
            "config": {"model": "gpt-6.1-sol", "thinkingOptionId": "xhigh", "modeId": "full-access"},
            "lastStatus": "idle",
            "labels": {
                "role": "lead",
                "route": "planning",
                "room_kind": "managed_slp",
                "work_epoch": "1",
                "task_state": "LEASED",
                "paseo.parent-agent-id": SUPERVISOR_ID,
            },
            "archivedAt": None,
        }
        self.supervisor = {
            "id": SUPERVISOR_ID,
            "workspaceId": "workspace-control",
            "provider": "codex-supervisor",
            "labels": {"role": "supervisor"},
            "archivedAt": None,
        }
        self.write_agent(self.lead)
        self.write_agent(self.supervisor)
        self.write_workspace(archived=False)
        self.write_lease()
        self.calls: list[tuple[bool, str, dict]] = []
        self.activity_content = (
            "Showing 2 of 2 activities\n\n"
            "Task outcome: DONE\n\nInspected the bounded surface.\n"
            "Validation: focused tests pass.\nRemaining uncertainty: none."
        )
        self.activity_update_count = 7
        self.agent_status = "idle"
        self.native_upstream_call = self.module.upstream_call
        self.module.upstream_call = self.upstream_call

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_agent(self, value: dict) -> None:
        path = self.module.AGENTS_ROOT / "records" / f"{value['id']}.json"
        path.write_text(json.dumps(value), encoding="utf-8")

    def write_workspace(self, archived: bool) -> None:
        value = {"workspaceId": WORKSPACE_ID}
        if archived:
            value["archivedAt"] = "2026-09-14T00:00:00Z"
        self.module.WORKSPACES_PATH.write_text(json.dumps([value]), encoding="utf-8")

    def base_lease(self) -> dict:
        return {
            "state": "active",
            "room_kind": "managed_slp",
            "workspace_id": WORKSPACE_ID,
            "lead_agent_id": LEAD_ID,
            "supervisor_agent_id": SUPERVISOR_ID,
            "provider": "codex-lead/gpt-6-sol",
            "work_epoch": 1,
            "handback_epoch": 0,
            "revision": 1,
            "decision_state": "WORKING",
            "runtime_binding_version": 2,
        }

    def write_lease(self, lease: dict | None = None) -> None:
        self.module.LEASES_PATH.write_text(
            json.dumps({"version": 2, "leases": {WORKSPACE_ID: lease or self.base_lease()}}),
            encoding="utf-8",
        )

    def read_lease(self) -> dict:
        return json.loads(self.module.LEASES_PATH.read_text())["leases"][WORKSPACE_ID]

    def upstream_call(self, agent_id: str, payload: dict, *, agent_scoped: bool = True):
        params = payload.get("params", {})
        name = params.get("name", "")
        arguments = params.get("arguments", {})
        self.calls.append((agent_scoped, name, arguments))
        if name == "get_agent_status":
            return {
                "result": {
                    "structuredContent": {
                        "status": self.agent_status,
                        "snapshot": {"status": self.agent_status, "pendingPermissions": []},
                    }
                }
            }
        if name == "get_agent_activity":
            return {
                "result": {
                    "structuredContent": {
                        "agentId": arguments["agentId"],
                        "updateCount": self.activity_update_count,
                        "currentModeId": "full-access",
                        "content": self.activity_content,
                    }
                }
            }
        return {"result": {"content": [], "structuredContent": {"success": True}, "isError": False}}

    @staticmethod
    def text(result: dict) -> str:
        return result["result"]["content"][0]["text"]

    def deliver_handback(self, message: str = "validated outcome") -> dict:
        result = self.module.handback_to_parent(
            LEAD_ID, "lead", 1, {"message": message}
        )
        self.assertFalse(result["result"]["isError"], self.text(result))
        return self.read_lease()

    def test_handback_reserves_epoch_revision_and_evidence_digest(self) -> None:
        lease = self.deliver_handback()
        self.assertEqual(lease["room_kind"], "managed_slp")
        self.assertEqual(lease["work_epoch"], 1)
        self.assertEqual(lease["handback_epoch"], 1)
        self.assertEqual(lease["decision_state"], "HANDBACK_READY")
        self.assertEqual(lease["revision"], 3)
        self.assertEqual(
            lease["evidence_digest"],
            self.module.evidence_digest(1, "validated outcome"),
        )
        self.assertNotIn("delivery_correlation_id", lease)
        events = [json.loads(line) for line in self.module.HISTORY_PATH.read_text().splitlines()]
        self.assertEqual([event["result"] for event in events], ["RESERVED", "DELIVERED"])

    def test_duplicate_handback_for_same_epoch_is_rejected(self) -> None:
        self.deliver_handback()
        result = self.module.handback_to_parent(
            LEAD_ID, "lead", 2, {"message": "duplicate"}
        )
        self.assertTrue(result["result"]["isError"])
        self.assertIn("already delivered", self.text(result))

    def test_reopen_advances_epoch_and_invalidates_prior_evidence(self) -> None:
        ready = self.deliver_handback()
        result = self.module.reopen_work_epoch(
            SUPERVISOR_ID,
            "supervisor",
            3,
            {
                "agentId": LEAD_ID,
                "prompt": "Bounded follow-up.",
                "expectedWorkEpoch": 1,
                "expectedRevision": ready["revision"],
            },
        )
        self.assertFalse(result["result"]["isError"], self.text(result))
        lease = self.read_lease()
        self.assertEqual(lease["work_epoch"], 2)
        self.assertEqual(lease["decision_state"], "WORKING")
        self.assertEqual(lease["handback_epoch"], 1)
        self.assertNotIn("evidence_digest", lease)
        self.assertNotIn("prior_evidence_digest", lease)

    def test_reopen_rejects_stale_revision(self) -> None:
        ready = self.deliver_handback()
        result = self.module.reopen_work_epoch(
            SUPERVISOR_ID,
            "supervisor",
            4,
            {
                "agentId": LEAD_ID,
                "prompt": "Stale follow-up.",
                "expectedWorkEpoch": 1,
                "expectedRevision": ready["revision"] - 1,
            },
        )
        self.assertTrue(result["result"]["isError"])
        self.assertIn("stale", self.text(result))

    def test_room_prompts_pin_active_turn_behavior(self) -> None:
        ready = self.deliver_handback()
        self.module.reopen_work_epoch(SUPERVISOR_ID, "supervisor", 5, {
            "agentId": LEAD_ID, "prompt": "Bounded follow-up.",
            "expectedWorkEpoch": 1, "expectedRevision": ready["revision"],
        })
        handback, reopen = [a for _, name, a in self.calls if name == "send_agent_prompt"]
        self.assertEqual((handback["agentId"], handback["activeTurnBehavior"]), (SUPERVISOR_ID, "steer"))
        self.assertEqual((reopen["agentId"], reopen["activeTurnBehavior"]), (LEAD_ID, "steer"))

    def test_lead_recovery_interrupts_the_stalled_turn(self) -> None:
        result = self.module.recover_working_lead(
            SUPERVISOR_ID, "supervisor", 6, {"agentId": LEAD_ID, "prompt": "Resume."}
        )
        self.assertFalse(result["result"]["isError"], result)
        [recovery] = [a for _, name, a in self.calls if name == "send_agent_prompt"]
        self.assertEqual(recovery["activeTurnBehavior"], "interrupt")

    def test_accept_and_abandon_are_digest_bound_and_one_shot(self) -> None:
        for decision in ("ACCEPTED", "ABANDONED"):
            with self.subTest(decision=decision):
                self.write_lease()
                ready = self.deliver_handback(f"{decision} evidence")
                digest = ready["evidence_digest"]
                result = self.module.record_slp_decision(
                    SUPERVISOR_ID,
                    "supervisor",
                    5,
                    {
                        "agentId": LEAD_ID,
                        "decision": decision,
                        "evidenceDigest": digest,
                        "expectedWorkEpoch": 1,
                        "expectedRevision": ready["revision"],
                    },
                )
                self.assertFalse(result["result"]["isError"], self.text(result))
                decided = self.read_lease()
                self.assertEqual(decided["human_decision"], decision)
                duplicate = self.module.record_slp_decision(
                    SUPERVISOR_ID,
                    "supervisor",
                    6,
                    {
                        "agentId": LEAD_ID,
                        "decision": decision,
                        "evidenceDigest": digest,
                        "expectedWorkEpoch": 1,
                        "expectedRevision": decided["revision"],
                    },
                )
                self.assertTrue(duplicate["result"]["isError"])

    def test_decision_rejects_changed_evidence_digest(self) -> None:
        ready = self.deliver_handback()
        result = self.module.record_slp_decision(
            SUPERVISOR_ID,
            "supervisor",
            7,
            {
                "agentId": LEAD_ID,
                "decision": "ACCEPTED",
                "evidenceDigest": self.module.evidence_digest(1, "other"),
                "expectedWorkEpoch": 1,
                "expectedRevision": ready["revision"],
            },
        )
        self.assertTrue(result["result"]["isError"])

    def test_protected_archive_requires_current_human_decision(self) -> None:
        ready = self.deliver_handback()
        denied = self.module.archive_slp_workspace(
            SUPERVISOR_ID,
            "supervisor",
            8,
            {
                "agentId": LEAD_ID,
                "expectedWorkEpoch": 1,
                "expectedRevision": ready["revision"],
            },
        )
        self.assertTrue(denied["result"]["isError"])
        accepted = self.module.record_slp_decision(
            SUPERVISOR_ID,
            "supervisor",
            9,
            {
                "agentId": LEAD_ID,
                "decision": "ACCEPTED",
                "evidenceDigest": ready["evidence_digest"],
                "expectedWorkEpoch": 1,
                "expectedRevision": ready["revision"],
            },
        )
        self.assertFalse(accepted["result"]["isError"])
        decided = self.read_lease()
        archived = self.module.archive_slp_workspace(
            SUPERVISOR_ID,
            "supervisor",
            10,
            {
                "agentId": LEAD_ID,
                "expectedWorkEpoch": 1,
                "expectedRevision": decided["revision"],
            },
        )
        self.assertFalse(archived["result"]["isError"], self.text(archived))
        lease = self.read_lease()
        self.assertEqual(lease["state"], "released")
        self.assertEqual(lease["decision_state"], "ARCHIVED")

    def test_uncertain_handback_requires_explicit_resolution(self) -> None:
        original = self.module.upstream_call

        def uncertain(agent_id: str, payload: dict, *, agent_scoped: bool = True):
            if payload.get("params", {}).get("name") == "send_agent_prompt":
                return None
            return original(agent_id, payload, agent_scoped=agent_scoped)

        self.module.upstream_call = uncertain
        result = self.module.handback_to_parent(
            LEAD_ID, "lead", 11, {"message": "uncertain evidence"}
        )
        self.assertTrue(result["result"]["isError"])
        lease = self.read_lease()
        self.assertEqual(lease["decision_state"], "HANDBACK_SENDING")
        correlation = lease["delivery_correlation_id"]
        resolved = self.module.resolve_slp_delivery(
            SUPERVISOR_ID,
            "supervisor",
            12,
            {
                "agentId": LEAD_ID,
                "resolution": "NOT_DELIVERED",
                "expectedWorkEpoch": 1,
                "expectedRevision": lease["revision"],
                "correlationId": correlation,
            },
        )
        self.assertFalse(resolved["result"]["isError"], self.text(resolved))
        self.assertEqual(self.read_lease()["decision_state"], "WORKING")

    def test_decision_queue_surfaces_uncertain_delivery(self) -> None:
        lease = self.base_lease()
        lease.update(
            {
                "decision_state": "HANDBACK_SENDING",
                "delivery_correlation_id": "correlation-one",
                "evidence_digest": self.module.evidence_digest(1, "pending"),
                "handback_message": "pending",
                "revision": 2,
            }
        )
        self.write_lease(lease)
        result = self.module.list_slp_decisions(
            SUPERVISOR_ID, "supervisor", 13, {}
        )
        payload = json.loads(self.text(result))
        self.assertEqual(payload["pending"][0]["human_actions"], ["resolve_delivery_uncertainty"])
        self.assertEqual(payload["pending"][0]["correlation_id"], "correlation-one")

    def test_uncertain_handback_can_be_resolved_as_delivered(self) -> None:
        lease = self.base_lease()
        lease.update(
            {
                "decision_state": "HANDBACK_SENDING",
                "delivery_correlation_id": "handback-correlation",
                "evidence_digest": self.module.evidence_digest(1, "pending"),
                "handback_message": "pending",
                "revision": 2,
            }
        )
        self.write_lease(lease)
        result = self.module.resolve_slp_delivery(
            SUPERVISOR_ID,
            "supervisor",
            37,
            {
                "agentId": LEAD_ID,
                "resolution": "DELIVERED",
                "expectedWorkEpoch": 1,
                "expectedRevision": 2,
                "correlationId": "handback-correlation",
            },
        )
        self.assertFalse(result["result"]["isError"], self.text(result))
        resolved = self.read_lease()
        self.assertEqual(resolved["handback_epoch"], 1)
        self.assertEqual(resolved["decision_state"], "HANDBACK_READY")

    def test_uncertain_reopen_resolution_preserves_or_restores_epoch_evidence(self) -> None:
        prior_digest = self.module.evidence_digest(1, "prior")
        for resolution in ("DELIVERED", "NOT_DELIVERED"):
            with self.subTest(resolution=resolution):
                lease = self.base_lease()
                lease.update(
                    {
                        "work_epoch": 2,
                        "handback_epoch": 1,
                        "decision_state": "REOPEN_SENDING",
                        "delivery_correlation_id": "reopen-correlation",
                        "prior_evidence_digest": prior_digest,
                        "revision": 4,
                    }
                )
                self.write_lease(lease)
                result = self.module.resolve_slp_delivery(
                    SUPERVISOR_ID,
                    "supervisor",
                    38,
                    {
                        "agentId": LEAD_ID,
                        "resolution": resolution,
                        "expectedWorkEpoch": 2,
                        "expectedRevision": 4,
                        "correlationId": "reopen-correlation",
                    },
                )
                self.assertFalse(result["result"]["isError"], self.text(result))
                resolved = self.read_lease()
                if resolution == "DELIVERED":
                    self.assertEqual(resolved["work_epoch"], 2)
                    self.assertEqual(resolved["decision_state"], "WORKING")
                    self.assertNotIn("prior_evidence_digest", resolved)
                else:
                    self.assertEqual(resolved["work_epoch"], 1)
                    self.assertEqual(resolved["decision_state"], "HANDBACK_READY")
                    self.assertEqual(resolved["evidence_digest"], prior_digest)

    def test_uncertain_archive_resolution_can_release_workspace_lease(self) -> None:
        lease = self.base_lease()
        lease.update(
            {
                "decision_state": "ARCHIVE_SENDING",
                "delivery_correlation_id": "archive-correlation",
                "revision": 6,
            }
        )
        self.write_lease(lease)
        result = self.module.resolve_slp_delivery(
            SUPERVISOR_ID,
            "supervisor",
            39,
            {
                "agentId": LEAD_ID,
                "resolution": "DELIVERED",
                "expectedWorkEpoch": 1,
                "expectedRevision": 6,
                "correlationId": "archive-correlation",
            },
        )
        self.assertFalse(result["result"]["isError"], self.text(result))
        resolved = self.read_lease()
        self.assertEqual(resolved["state"], "released")
        self.assertEqual(resolved["decision_state"], "ARCHIVED")

    def test_malformed_nested_registry_fails_closed(self) -> None:
        self.module.LEASES_PATH.write_text(
            json.dumps({"version": 2, "leases": {WORKSPACE_ID: []}}),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(RuntimeError, "failing closed"):
            with self.module.locked_leases():
                pass

    def test_anonymous_catalog_probe_exposes_no_control_tools(self) -> None:
        initialized = self.module.handle(
            "", "supervisor", {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        )
        listed = self.module.handle(
            "", "supervisor", {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        )
        self.assertEqual(initialized["result"]["serverInfo"]["name"], "paseo-room-supervisor")
        self.assertEqual(listed["result"]["tools"], [])

    def test_disabled_provider_policy_keeps_guarded_proxy_via_unscoped_fallback(self) -> None:
        calls: list[tuple[bool, str, dict]] = []

        def policy_coupled_upstream(
            agent_id: str, payload: dict, *, agent_scoped: bool = True
        ):
            method = payload.get("method")
            params = payload.get("params", {})
            name = params.get("name", "")
            arguments = params.get("arguments", {})
            calls.append((agent_scoped, name or method, arguments))
            if agent_scoped:
                if method == "tools/list":
                    return {"result": {"tools": []}}
                return {
                    "error": {
                        "code": -32602,
                        "message": f"Tool not found: {name}",
                    }
                }
            if method == "tools/list":
                return {
                    "result": {
                        "tools": [
                            {"name": "create_agent", "inputSchema": {}},
                            {"name": "archive_workspace", "inputSchema": {}},
                        ]
                    }
                }
            return {
                "result": {
                    "content": [],
                    "structuredContent": {"success": True},
                    "isError": False,
                }
            }

        self.module.upstream_call = policy_coupled_upstream
        self.module.run_guard = (
            lambda role, event, agent_id, name, arguments, tool_use_id, response=None:
            (True, None, arguments)
        )
        catalog = self.module.list_tools(LEAD_ID, "lead", 30)
        names = {tool["name"] for tool in catalog["result"]["tools"]}
        self.assertIn("create_agent", names)
        self.assertIn("handback_to_parent", names)
        self.assertNotIn("archive_workspace", names)

        result = self.module.call_tool(
            LEAD_ID,
            "lead",
            31,
            {
                "name": "create_agent",
                "arguments": {
                    "provider": "codex-peer/gpt-5.6-luna",
                    "labels": {"route": "search"},
                    "initialPrompt": "Search only.",
                    "notifyOnFinish": False,
                },
            },
        )
        self.assertFalse(result["result"]["isError"])
        fallback = [
            arguments
            for scoped, name, arguments in calls
            if not scoped and name == "create_agent"
        ][0]
        self.assertEqual(fallback["workspaceId"], WORKSPACE_ID)
        self.assertEqual(
            fallback["labels"]["paseo.parent-agent-id"],
            LEAD_ID,
        )
        self.assertTrue(fallback["background"])
        self.assertFalse(fallback["notifyOnFinish"])

    def test_callback_dispatch_rejects_missing_scoped_catalog_before_admission(self) -> None:
        for name in ("create_agent", "send_agent_prompt"):
            for result in ({"error": {"code": -32601, "message": "Method not found"}},
                           {"result": {"tools": []}}, {"result": None}, None):
                with self.subTest(name=name, result=result):
                    self.module.upstream_call = mock.Mock(return_value=result)
                    self.module.run_guard = mock.Mock(side_effect=AssertionError("must not reserve"))
                    response = self.module.call_tool(LEAD_ID, "lead", 70, {
                        "name": name, "arguments": {"notifyOnFinish": True},
                    })
                    self.assertTrue(response["result"]["isError"])
                    self.assertIn("dispatch was not sent", self.text(response))
                    self.module.run_guard.assert_not_called()
                    self.module.upstream_call.assert_called_once()
                    self.assertFalse(self.module.upstream_call.call_args.kwargs["allow_unscoped_fallback"])

    def test_callback_fallback_never_posts_top_level_in_json_or_sse_transport(self) -> None:
        self.module.upstream_call = self.native_upstream_call
        for name in ("create_agent", "send_agent_prompt"):
            for content_type in ("application/json", "text/event-stream"):
                with self.subTest(name=name, content_type=content_type):
                    error = {"jsonrpc": "2.0", "id": 71,
                             "error": {"code": -32601, "message": "Method not found"}}
                    body = json.dumps(error)
                    if content_type == "text/event-stream":
                        body = "data: " + body + "\n\n"
                    http = mock.MagicMock()
                    http.__enter__.return_value = http
                    http.read.return_value = body.encode()
                    http.headers = {"content-type": content_type}
                    with mock.patch.object(self.module.urllib.request, "urlopen", return_value=http) as post:
                        response = self.module.upstream_call(LEAD_ID, {
                            "jsonrpc": "2.0", "id": 71, "method": "tools/call",
                            "params": {"name": name, "arguments": {}},
                        })
                    self.assertTrue(response["result"]["isError"])
                    self.assertIn("callerAgentId", self.text(response))
                    self.assertEqual(post.call_count, 1)
                    self.assertIn("callerAgentId=", post.call_args.args[0].full_url)

    def test_unscoped_callback_gate_preserves_explicit_no_notification_and_owner_calls(self) -> None:
        for name in ("create_agent", "send_agent_prompt"):
            payload = {"id": 72, "method": "tools/call",
                       "params": {"name": name, "arguments": {"notifyOnFinish": False}}}
            self.assertIsNone(self.module.unscoped_callback_error(LEAD_ID, payload))
            payload["params"]["arguments"] = {"notifyOnFinish": True}
            self.assertIsNone(self.module.unscoped_callback_error("human", payload))
            self.assertTrue(self.module.unscoped_callback_error(LEAD_ID, payload)["result"]["isError"])

    def test_scoped_callback_dispatch_still_uses_native_caller_context(self) -> None:
        calls = []
        def native_upstream(agent_id, payload, *, agent_scoped=True, allow_unscoped_fallback=True):
            calls.append((agent_id, agent_scoped, payload))
            if payload["method"] == "tools/list":
                return {"result": {"tools": [{"name": "create_agent"}]}}
            return {"result": {"isError": False, "structuredContent": {"agentId": PEER_ID}}}
        self.module.upstream_call = native_upstream
        self.module.run_guard = lambda role, event, agent_id, name, arguments, tool_use_id, response=None: (True, None, arguments)
        response = self.module.call_tool(LEAD_ID, "lead", 73, {
            "name": "create_agent", "arguments": {"notifyOnFinish": True},
        })
        self.assertFalse(response["result"]["isError"])
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(agent_id == LEAD_ID and scoped for agent_id, scoped, _ in calls))

    def test_callback_catalog_race_is_denied_without_top_level_dispatch(self) -> None:
        calls, post_responses = [], []
        def upstream(agent_id, payload, *, agent_scoped=True, allow_unscoped_fallback=True):
            calls.append((agent_scoped, payload))
            if payload["method"] == "tools/list":
                return {"result": {"tools": [{"name": "create_agent"}]}}
            return {"error": {"code": -32602, "message": "Tool not found: create_agent"}}
        def guard(role, event, agent_id, name, arguments, tool_use_id, response=None):
            if event == "PostToolUse":
                post_responses.append(response)
            return True, None, arguments
        self.module.upstream_call = upstream
        self.module.run_guard = guard
        response = self.module.call_tool(LEAD_ID, "lead", 74, {
            "name": "create_agent", "arguments": {"notifyOnFinish": True},
        })
        self.assertTrue(response["result"]["isError"])
        self.assertIn("dispatch was not sent", self.text(response))
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(scoped for scoped, _ in calls))
        self.assertEqual(post_responses, [response])

    def test_peer_callback_recovery_fails_closed_without_monotonic_activity_count(self) -> None:
        peer = {
            "id": PEER_ID,
            "workspaceId": WORKSPACE_ID,
            "provider": "codex-peer",
            "labels": {
                "role": "peer",
                "route": "audit",
                "room_kind": "managed_slp",
                "work_epoch": "1",
                "task_state": "ASSIGNED",
                "paseo.parent-agent-id": LEAD_ID,
            },
        }
        self.write_agent(peer)
        self.activity_update_count = None
        result = self.module.recover_peer_callbacks(LEAD_ID, "lead", 32, {})
        self.assertTrue(result["result"]["isError"])
        self.assertIn("update count", self.text(result))

    def test_peer_callback_recovery_is_epoch_fenced_and_digest_deduplicated(self) -> None:
        peer = {
            "id": PEER_ID,
            "workspaceId": WORKSPACE_ID,
            "provider": "codex-peer",
            "labels": {
                "role": "peer",
                "route": "audit",
                "room_kind": "managed_slp",
                "work_epoch": "1",
                "task_state": "ASSIGNED",
                "paseo.parent-agent-id": LEAD_ID,
            },
            "archivedAt": None,
        }
        self.write_agent(peer)
        first = self.module.recover_peer_callbacks(LEAD_ID, "lead", 14, {})
        self.assertFalse(first["result"]["isError"], self.text(first))
        payload = json.loads(self.text(first))
        self.assertEqual(payload["callbacks"][0]["agent_id"], PEER_ID)
        self.assertEqual(payload["callbacks"][0]["outcome"], "DONE")
        self.assertRegex(payload["callbacks"][0]["evidence_digest"], r"^sha256:[0-9a-f]{64}$")
        receipt = self.read_lease()["peer_callbacks"][PEER_ID]
        self.assertEqual(receipt["work_epoch"], 1)
        second = self.module.recover_peer_callbacks(LEAD_ID, "lead", 15, {})
        self.assertFalse(second["result"]["isError"], self.text(second))
        self.assertEqual(json.loads(self.text(second))["callbacks"][0]["evidence_digest"], receipt["evidence_digest"])
        activity_calls = [call for call in self.calls if call[1] == "get_agent_activity"]
        self.assertEqual(len(activity_calls), 1)

    def test_peer_callback_recovery_rejects_cross_epoch_peer(self) -> None:
        peer = {
            "id": PEER_ID,
            "workspaceId": WORKSPACE_ID,
            "provider": "codex-peer",
            "labels": {
                "role": "peer",
                "room_kind": "managed_slp",
                "work_epoch": "2",
                "task_state": "ASSIGNED",
                "paseo.parent-agent-id": LEAD_ID,
            },
        }
        self.write_agent(peer)
        result = self.module.recover_peer_callbacks(LEAD_ID, "lead", 16, {})
        self.assertTrue(result["result"]["isError"])
        self.assertIn("epoch", self.text(result))

    def test_peer_rework_recovery_replaces_receipt_only_for_new_activity(self) -> None:
        peer = {
            "id": PEER_ID,
            "workspaceId": WORKSPACE_ID,
            "provider": "codex-peer",
            "labels": {
                "role": "peer",
                "route": "audit",
                "room_kind": "managed_slp",
                "work_epoch": "1",
                "task_state": "ASSIGNED",
                "paseo.parent-agent-id": LEAD_ID,
            },
        }
        self.write_agent(peer)
        first = json.loads(
            self.text(self.module.recover_peer_callbacks(LEAD_ID, "lead", 33, {}))
        )["callbacks"][0]
        peer["labels"]["task_state"] = "REWORK"
        self.write_agent(peer)
        self.activity_update_count = 11
        self.activity_content = (
            "Showing 2 of 2 activities\n\n"
            "Task outcome: DONE\n\nReworked result with new evidence."
        )
        second = json.loads(
            self.text(self.module.recover_peer_callbacks(LEAD_ID, "lead", 34, {}))
        )["callbacks"][0]
        self.assertNotEqual(first["evidence_digest"], second["evidence_digest"])
        self.assertEqual(self.read_lease()["peer_callbacks"][PEER_ID]["activity_update_count"], 11)

    def test_orphan_inventory_and_retirement_require_authority_digest(self) -> None:
        legacy_id = "legacy-lead"
        legacy = {
            "id": legacy_id,
            "workspaceId": WORKSPACE_ID,
            "provider": "codex-lead",
            "labels": {"paseo.parent-agent-id": SUPERVISOR_ID},
            "archivedAt": None,
        }
        self.write_agent(legacy)
        self.write_lease()
        inventory = self.module.inspect_slp_ownership(
            SUPERVISOR_ID, "supervisor", 17, {}
        )
        self.assertFalse(inventory["result"]["isError"], self.text(inventory))
        candidates = json.loads(self.text(inventory))["candidates"]
        orphan = next(item for item in candidates if item["agent_id"] == legacy_id)
        stale = self.module.retire_legacy_lead(
            SUPERVISOR_ID,
            "supervisor",
            18,
            {
                "agentId": legacy_id,
                "workspaceId": WORKSPACE_ID,
                "authorityDigest": "sha256:" + "0" * 64,
            },
        )
        self.assertTrue(stale["result"]["isError"])
        result = self.module.retire_legacy_lead(
            SUPERVISOR_ID,
            "supervisor",
            19,
            {
                "agentId": legacy_id,
                "workspaceId": WORKSPACE_ID,
                "authorityDigest": orphan["authority_digest"],
            },
        )
        self.assertFalse(result["result"]["isError"], self.text(result))
        archive_calls = [call for call in self.calls if call[1] == "archive_agent"]
        self.assertEqual(archive_calls[-1][2]["agentId"], legacy_id)

    def test_reconciled_legacy_lease_can_retire_and_releases_fence(self) -> None:
        legacy = dict(self.lead)
        legacy["labels"] = {"paseo.parent-agent-id": SUPERVISOR_ID}
        self.write_agent(legacy)
        lease = self.base_lease()
        lease.update(
            {
                "legacy_orphan": True,
                "decision_state": "LEGACY_BLOCKED",
            }
        )
        self.write_lease(lease)
        inventory = self.module.inspect_slp_ownership(
            SUPERVISOR_ID, "supervisor", 35, {}
        )
        candidate = json.loads(self.text(inventory))["candidates"][0]
        self.assertEqual(candidate["classification"], "legacy_orphan")
        result = self.module.retire_legacy_lead(
            SUPERVISOR_ID,
            "supervisor",
            36,
            {
                "agentId": LEAD_ID,
                "workspaceId": WORKSPACE_ID,
                "authorityDigest": candidate["authority_digest"],
            },
        )
        self.assertFalse(result["result"]["isError"], self.text(result))
        retired = self.read_lease()
        self.assertEqual(retired["state"], "released")
        self.assertEqual(retired["decision_state"], "LEGACY_RETIRED")

    def test_orphan_retirement_denies_foreign_parent_and_managed_lead(self) -> None:
        inventory = self.module.inspect_slp_ownership(
            SUPERVISOR_ID, "supervisor", 20, {}
        )
        managed = next(
            item for item in json.loads(self.text(inventory))["candidates"]
            if item["agent_id"] == LEAD_ID
        )
        denied = self.module.retire_legacy_lead(
            SUPERVISOR_ID,
            "supervisor",
            21,
            {
                "agentId": LEAD_ID,
                "workspaceId": WORKSPACE_ID,
                "authorityDigest": managed["authority_digest"],
            },
        )
        self.assertTrue(denied["result"]["isError"])
        self.assertIn("managed", self.text(denied))

    def test_orphan_inventory_surfaces_unparented_without_granting_retirement(self) -> None:
        orphan_id = "unparented-lead"
        self.write_agent(
            {
                "id": orphan_id,
                "workspaceId": WORKSPACE_ID,
                "provider": "codex-lead",
                "labels": {},
                "archivedAt": None,
            }
        )
        inventory = self.module.inspect_slp_ownership(
            SUPERVISOR_ID, "supervisor", 40, {}
        )
        candidate = next(
            item
            for item in json.loads(self.text(inventory))["candidates"]
            if item["agent_id"] == orphan_id
        )
        self.assertEqual(candidate["classification"], "unparented_orphan")
        denied = self.module.retire_legacy_lead(
            SUPERVISOR_ID,
            "supervisor",
            41,
            {
                "agentId": orphan_id,
                "workspaceId": WORKSPACE_ID,
                "authorityDigest": candidate["authority_digest"],
            },
        )
        self.assertTrue(denied["result"]["isError"])
        self.assertIn("parentage", self.text(denied))


if __name__ == "__main__":
    unittest.main()
