#!/usr/bin/env python3
from __future__ import annotations

import importlib.machinery
import importlib.util
import datetime as dt
import contextlib
import io
import json
import pathlib
import re
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = pathlib.Path(__file__).resolve().parents[1]
LEAD = "lead-one"
SUPERVISOR = "supervisor-one"
PEER = "peer-one"
WORKSPACE = "workspace-one"


def proxy_module():
    loader = importlib.machinery.SourceFileLoader("attention_proxy_test", str(ROOT / "bin/paseo-room-mcp"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class AttentionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.proxy = proxy_module()
        self.proxy.AGENT_ID_PATTERN = re.compile(r"^[a-z]+(?:-[a-z]+)*$")
        self.proxy.AGENTS_ROOT = self.root / "agents"
        (self.proxy.AGENTS_ROOT / "records").mkdir(parents=True)
        self.proxy.LEASES_PATH = self.root / "leases.json"
        self.proxy.HISTORY_PATH = self.root / "history.jsonl"
        self.proxy.WORKSPACES_PATH = self.root / "workspaces.json"
        self.proxy.WORKSPACES_PATH.write_text(json.dumps([{"workspaceId": WORKSPACE}]))
        self.supervised = True
        self.write_agents()
        self.write_lease()
        self.proxy.LEASES_PATH.with_suffix(".json.lock").touch()
        self.status = "idle"
        self.activity = "A turn that did not return a task outcome."
        self.count = 2
        self.proxy.upstream_call = self.upstream_call

    def tearDown(self):
        self.temp.cleanup()

    def write_agents(self):
        lead_labels = {"role": "lead", "room_kind": "managed_slp", "work_epoch": "1", "task_state": "LEASED"}
        if self.supervised:
            lead_labels["paseo.parent-agent-id"] = SUPERVISOR
        records = [
            {"id": LEAD, "workspaceId": WORKSPACE, "labels": lead_labels, "archivedAt": None},
            {"id": SUPERVISOR, "workspaceId": "control", "labels": {"role": "supervisor"}, "archivedAt": None},
            {"id": PEER, "workspaceId": WORKSPACE,
             "labels": {"role": "peer", "room_kind": "managed_slp", "work_epoch": "1",
                        "task_state": "ASSIGNED", "assignment_id": "assignment-one",
                        "paseo.parent-agent-id": LEAD}, "archivedAt": None},
        ]
        for record in records:
            (self.proxy.AGENTS_ROOT / "records" / f"{record['id']}.json").write_text(json.dumps(record))

    def write_lease(self, **updates):
        lease = {"state": "active", "room_kind": "managed_slp", "workspace_id": WORKSPACE,
                 "lead_agent_id": LEAD, "supervisor_agent_id": SUPERVISOR if self.supervised else None,
                 "authority_mode": "parented" if self.supervised else "direct",
                 "work_epoch": 1, "revision": 1, "decision_state": "WORKING"}
        lease.update(updates)
        self.proxy.LEASES_PATH.write_text(json.dumps({"version": 2, "leases": {WORKSPACE: lease}}))

    def lease(self):
        return json.loads(self.proxy.LEASES_PATH.read_text())["leases"][WORKSPACE]

    def upstream_call(self, agent_id, payload, *, agent_scoped=True):
        name = payload.get("params", {}).get("name")
        if name == "get_agent_status":
            return {"result": {"structuredContent": {"status": self.status,
                      "snapshot": {"pendingPermissions": []}}}}
        if name == "get_agent_activity":
            return {"result": {"structuredContent": {"content": self.activity,
                      "updateCount": self.count}}}
        return {"result": {"structuredContent": {"success": True}}}

    def result(self, response):
        self.assertFalse(response["result"]["isError"], response)
        return json.loads(response["result"]["content"][0]["text"])

    def open(self, ask_id="ask-one", question="What is the scope?", revision=1):
        return self.proxy.open_room_ask(LEAD, "lead", 1, {
            "askId": ask_id, "question": question,
            "expectedWorkEpoch": 1, "expectedRevision": revision,
        })

    def test_lead_ask_is_durable_idempotent_and_bound_to_supervisor(self):
        first = self.result(self.open())
        self.assertEqual(first["ask"]["recipient_agent_id"], SUPERVISOR)
        self.assertEqual(self.lease()["revision"], 2)
        duplicate = self.result(self.open())
        self.assertFalse(duplicate["created"])
        self.assertEqual(self.lease()["revision"], 2)
        with self.assertRaisesRegex(ValueError, "different evidence"):
            self.open(question="Different question")

    def test_supervisor_answers_only_their_ask_and_duplicate_is_safe(self):
        self.result(self.open())
        args = {"leadAgentId": LEAD, "askId": "ask-one", "answer": "Keep current scope.",
                "expectedWorkEpoch": 1, "expectedRevision": 2}
        denied = self.proxy.answer_room_ask(PEER, "peer", 2, args)
        self.assertTrue(denied["result"]["isError"])
        denied = self.proxy.answer_room_ask(LEAD, "lead", 3, args)
        self.assertTrue(denied["result"]["isError"])
        answered = self.result(self.proxy.answer_room_ask(SUPERVISOR, "supervisor", 4, args))
        self.assertTrue(answered["answered"])
        self.assertEqual(self.lease()["revision"], 3)
        duplicate = self.result(self.proxy.answer_room_ask(SUPERVISOR, "supervisor", 5, args))
        self.assertFalse(duplicate["answered"])
        self.assertEqual(self.lease()["revision"], 3)

    def test_direct_lead_ask_targets_human(self):
        self.supervised = False
        self.write_agents()
        self.write_lease()
        self.assertEqual(self.result(self.open())["ask"]["recipient_agent_id"], "human")
        args = {"leadAgentId": LEAD, "askId": "ask-one", "answer": "Use the current scope.",
                "expectedWorkEpoch": 1, "expectedRevision": 2}
        self.assertTrue(self.proxy.answer_room_ask(SUPERVISOR, "supervisor", 1, args)["result"]["isError"])
        self.assertTrue(self.result(self.proxy.answer_room_ask("human", "human", 1, args))["answered"])

    def test_revision_epoch_and_absent_lead_fail_closed(self):
        self.result(self.open())
        stale = self.open("another", revision=1)
        self.assertTrue(stale["result"]["isError"])
        self.write_lease(work_epoch=2, revision=3)
        stale = self.open("another", revision=3)
        self.assertTrue(stale["result"]["isError"])
        (self.proxy.AGENTS_ROOT / "records" / f"{LEAD}.json").unlink()
        denied = self.proxy.list_room_attention(SUPERVISOR, "supervisor", 1, {"leadAgentId": LEAD})
        self.assertTrue(denied["result"]["isError"])

    def test_peer_dependency_report_opens_question_without_peer_mcp(self):
        report = {"version": 1, "reportId": "dependency-one", "peerAgentId": PEER,
                  "parentLeadId": LEAD, "workspaceId": WORKSPACE, "workEpoch": 1,
                  "assignmentId": "assignment-one", "kind": "DEPENDENCY_REQUEST",
                  "payload": {"evidence": "Need product boundary", "question": "May this path change?"}}
        first = self.result(self.proxy.record_peer_report(LEAD, "lead", 1, {"report": report}))
        self.assertEqual(first["ask_id"], "peer:dependency-one")
        self.assertEqual(self.lease()["room_asks"]["peer:dependency-one"]["recipient_agent_id"], LEAD)
        second = self.result(self.proxy.record_peer_report(LEAD, "lead", 2, {"report": report}))
        self.assertEqual(first, second)
        self.assertEqual(self.lease()["revision"], 2)

    def test_read_only_reminder_and_escalation(self):
        self.result(self.open())
        lease = self.lease()
        lease["room_asks"]["ask-one"]["created_at"] = "2020-01-01T00:00:00Z"
        self.write_lease(**lease)
        before = self.proxy.LEASES_PATH.read_bytes()
        data = self.result(self.proxy.list_room_attention(SUPERVISOR, "supervisor", 1, {"leadAgentId": LEAD}))
        self.assertEqual(data["asks"][0]["attention"], "ESCALATE")
        self.assertEqual(data["asks"][0]["escalate_to"], "human")
        self.assertEqual(self.proxy.LEASES_PATH.read_bytes(), before)

    def test_reminder_threshold_and_old_epoch_has_no_current_signal(self):
        self.result(self.open())
        lease = self.lease()
        now = dt.datetime.now(dt.UTC)
        lease["room_asks"]["ask-one"]["created_at"] = (now - dt.timedelta(minutes=45)).isoformat()
        self.write_lease(**lease)
        data = self.result(self.proxy.list_room_attention(LEAD, "lead", 1, {"leadAgentId": LEAD}))
        self.assertEqual(data["asks"][0]["attention"], "REMIND")
        self.write_lease(**dict(self.lease(), work_epoch=2, revision=3))
        data = self.result(self.proxy.list_room_attention(LEAD, "lead", 2, {"leadAgentId": LEAD}))
        self.assertFalse(data["asks"][0]["current_epoch"])
        self.assertIsNone(data["asks"][0]["attention"])

    def test_missing_supervisor_cannot_answer_and_human_identity_is_exact(self):
        self.result(self.open())
        args = {"leadAgentId": LEAD, "askId": "ask-one", "answer": "Done",
                "expectedWorkEpoch": 1, "expectedRevision": 2}
        (self.proxy.AGENTS_ROOT / "records" / f"{SUPERVISOR}.json").unlink()
        denied = self.proxy.answer_room_ask(SUPERVISOR, "supervisor", 1, args)
        self.assertTrue(denied["result"]["isError"])
        denied = self.proxy.answer_room_ask("impostor", "human", 2, args)
        self.assertTrue(denied["result"]["isError"])

    def test_ask_queue_is_bounded(self):
        with self.proxy.locked_leases() as registry:
            lease = registry["leases"][WORKSPACE]
            for index in range(64):
                self.proxy.attention.open_ask(
                    lease, ask_id=f"ask-{index}", question="Question", sender=LEAD,
                    sender_role="lead", recipient=SUPERVISOR, work_epoch=1,
                    created_at="2026-01-01T00:00:00Z",
                )
        with self.assertRaisesRegex(ValueError, "capacity"):
            self.open("overflow")
        self.assertEqual(len(self.lease()["room_asks"]), 64)

    def test_peer_stall_is_diagnostic_and_ignores_stale_or_missing_peer(self):
        before = self.proxy.LEASES_PATH.read_bytes()
        scan = self.result(self.proxy.inspect_peer_attention(LEAD, "lead", 1, {}))
        self.assertEqual(scan["signals"][0]["signal"], "POSSIBLE_MISSING_HANDBACK")
        self.assertEqual(self.lease()["revision"], 1)
        self.assertEqual(self.proxy.LEASES_PATH.read_bytes(), before)
        self.activity = "Task outcome: DONE\nWork completed."
        scan = self.result(self.proxy.inspect_peer_attention(LEAD, "lead", 2, {}))
        self.assertEqual(scan["signals"], [])
        path = self.proxy.AGENTS_ROOT / "records" / f"{PEER}.json"
        peer = json.loads(path.read_text())
        peer["labels"]["work_epoch"] = "0"
        path.write_text(json.dumps(peer))
        scan = self.result(self.proxy.inspect_peer_attention(LEAD, "lead", 3, {}))
        self.assertEqual(scan["signals"], [])
        path.unlink()
        scan = self.result(self.proxy.inspect_peer_attention(LEAD, "lead", 4, {}))
        self.assertEqual(scan["signals"], [])

    def test_peer_permission_signal_never_updates_task_state(self):
        original = self.lease()
        self.status = "running"
        old_call = self.proxy.upstream_call
        def pending_call(agent_id, payload, *, agent_scoped=True):
            if payload.get("params", {}).get("name") == "get_agent_status":
                return {"result": {"structuredContent": {
                    "status": "running", "snapshot": {"pendingPermissions": [{"id": "p1"}]},
                }}}
            return old_call(agent_id, payload, agent_scoped=agent_scoped)
        self.proxy.upstream_call = pending_call
        scan = self.result(self.proxy.inspect_peer_attention(LEAD, "lead", 1, {}))
        self.assertEqual(scan["signals"][0]["signal"], "PENDING_PERMISSION")
        self.assertEqual(self.lease(), original)
        peer = json.loads((self.proxy.AGENTS_ROOT / "records" / f"{PEER}.json").read_text())
        self.assertEqual(peer["labels"]["task_state"], "ASSIGNED")

    def test_read_only_registry_rejects_legacy_without_rewriting(self):
        legacy = {"version": 1, "leases": {WORKSPACE: self.lease()}}
        self.proxy.LEASES_PATH.write_text(json.dumps(legacy, separators=(",", ":")))
        before = self.proxy.LEASES_PATH.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "version 2"):
            self.proxy.list_room_attention(LEAD, "lead", 1, {"leadAgentId": LEAD})
        self.assertEqual(self.proxy.LEASES_PATH.read_bytes(), before)

    def test_read_only_registry_requires_existing_lock_file(self):
        self.proxy.LEASES_PATH.with_suffix(".json.lock").unlink()
        before = self.proxy.LEASES_PATH.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "unreadable"):
            self.proxy.inspect_peer_attention(LEAD, "lead", 1, {})
        self.assertEqual(self.proxy.LEASES_PATH.read_bytes(), before)

    def test_owner_cli_lists_and_answers_direct_ask_only_on_apply(self):
        self.supervised = False
        self.write_agents()
        self.write_lease()
        self.result(self.open())
        loader = importlib.machinery.SourceFileLoader("attention_workflow_cli_test", str(ROOT / "bin/paseo-room-workflow"))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        cli = importlib.util.module_from_spec(spec)
        loader.exec_module(cli)
        cli.proxy_module = lambda: self.proxy

        def command(*arguments):
            output = io.StringIO()
            with patch.object(sys, "argv", ["paseo-room-workflow", *arguments]), contextlib.redirect_stdout(output):
                self.assertEqual(cli.main(), 0)
            return json.loads(output.getvalue())

        listed = command("asks", "--lead-id", LEAD)
        self.assertEqual(json.loads(listed["result"]["content"][0]["text"])["asks"][0]["ask_id"], "ask-one")
        request = self.root / "answer.json"
        request.write_text(json.dumps({"leadAgentId": LEAD, "askId": "ask-one", "answer": "Stay in scope.",
                                       "expectedWorkEpoch": 1, "expectedRevision": 2}))
        self.assertFalse(command("answer-ask", str(request))["applied"])
        self.assertEqual(self.lease()["room_asks"]["ask-one"]["status"], "OPEN")
        applied = command("answer-ask", str(request), "--apply")
        self.assertTrue(json.loads(applied["result"]["content"][0]["text"])["answered"])
        self.assertEqual(self.lease()["room_asks"]["ask-one"]["status"], "ANSWERED")


if __name__ == "__main__":
    unittest.main()
