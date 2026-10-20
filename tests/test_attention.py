#!/usr/bin/env python3
from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import subprocess
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
WATCHER = "watcher-one"
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
            {"id": WATCHER, "workspaceId": "watcher-control", "provider": "codex-watcher",
             "labels": {"role": "watcher"}, "archivedAt": None},
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

    def test_unlabeled_canonical_supervisor_can_read_and_answer_bound_ask(self):
        path = self.proxy.AGENTS_ROOT / "records" / f"{SUPERVISOR}.json"
        supervisor = json.loads(path.read_text())
        supervisor["provider"] = "claude-supervisor"
        supervisor["labels"] = {}
        path.write_text(json.dumps(supervisor))

        self.result(self.open())
        listed = self.result(self.proxy.list_room_attention(
            SUPERVISOR, "supervisor", 2, {"leadAgentId": LEAD}
        ))
        self.assertEqual(listed["asks"][0]["ask_id"], "ask-one")
        answered = self.result(self.proxy.answer_room_ask(
            SUPERVISOR, "supervisor", 3,
            {"leadAgentId": LEAD, "askId": "ask-one", "answer": "Keep scope.",
             "expectedWorkEpoch": 1, "expectedRevision": 2},
        ))
        self.assertTrue(answered["answered"])

        supervisor["provider"] = "claude"
        path.write_text(json.dumps(supervisor))
        denied = self.proxy.list_room_attention(
            SUPERVISOR, "supervisor", 4, {"leadAgentId": LEAD}
        )
        self.assertTrue(denied["result"]["isError"])

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

    def test_watcher_reads_attention_without_governance_authority(self):
        self.result(self.open())
        before = self.proxy.LEASES_PATH.read_bytes()
        data = self.result(self.proxy.list_room_attention(
            WATCHER, "watcher", 1, {"leadAgentId": LEAD}))
        self.assertEqual(len(data["asks"]), 1)
        self.assertEqual(self.proxy.LEASES_PATH.read_bytes(), before)
        denied = self.proxy.call_tool(WATCHER, "watcher", 2, {
            "name": "archive_agent", "arguments": {"agentId": LEAD}})
        self.assertTrue(denied["result"]["isError"])
        self.assertTrue(self.proxy.list_room_attention(
            SUPERVISOR, "watcher", 3, {"leadAgentId": LEAD})["result"]["isError"])
        self.assertTrue(self.proxy.call_tool(SUPERVISOR, "watcher", 4, {
            "name": "list_agents", "arguments": {}})["result"]["isError"])

    def test_watcher_tool_catalog_is_read_only(self):
        self.proxy.upstream_call = lambda *_args, **_kwargs: {
            "result": {"tools": [{"name": name} for name in (
                "list_agents", "list_workspaces", "archive_agent", "send_agent_prompt")]}}
        catalog = self.proxy.list_tools(WATCHER, "watcher", 1)
        names = {tool["name"] for tool in catalog["result"]["tools"]}
        self.assertEqual(names, {"list_agents", "list_workspaces", "list_room_attention", "list_room_observations"})

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

    def reopen_report(self, report_id="reopen-one"):
        report = {"version": 1, "reportId": report_id, "peerAgentId": PEER,
                  "parentLeadId": LEAD, "workspaceId": WORKSPACE, "workEpoch": 1,
                  "assignmentId": "assignment-one", "kind": "REOPEN_REQUEST",
                  "payload": {"evidence": "Regression proves packet history and ACK obligation have different lifetimes.",
                              "question": "May we replace the history-only workaround?"}}
        return self.result(self.proxy.record_peer_report(LEAD, "lead", 1, {"report": report}))

    def resolution(self, **updates):
        args = {"reportId": "reopen-one", "outcome": "RESOLVED_BY_LEAD",
                "decision": "Separate ACK obligation from packet history.",
                "evidence": "Inspect replication.py:42; old implementation fails the regression.",
                "nextAction": "Continue with the corrected foundation.", "changesWork": False,
                "expectedWorkEpoch": 1, "expectedRevision": self.lease()["revision"]}
        args.update(updates)
        return self.proxy.resolve_peer_report(LEAD, "lead", 1, args)

    def grant(self, **updates):
        args = {"leadAgentId": LEAD, "peerAgentId": PEER, "assignmentId": "assignment-one",
                "grantId": "grant-one", "humanInstruction": "Ask this Peer to reconsider the foundation.",
                "prompt": "Investigate the failed premise within your current scope and report evidence to Lead.",
                "expectedWorkEpoch": 1, "expectedRevision": self.lease()["revision"]}
        args.update(updates)
        with patch.dict(os.environ, {}, clear=True):
            return self.proxy.authorize_peer_steering(args)

    def steer(self, actor=SUPERVISOR, role="supervisor", **updates):
        args = {"leadAgentId": LEAD, "grantId": "grant-one",
                "expectedWorkEpoch": 1, "expectedRevision": self.lease()["revision"]}
        args.update(updates)
        return self.proxy.steer_room_peer(actor, role, 1, args)

    def transport(self, *, uncertain_target=None, uncorrelated=False):
        self.sends = []
        self.fallbacks = []
        def send(actor, payload, *, agent_scoped=True, allow_unscoped_fallback=True):
            args = payload["params"]["arguments"]
            self.sends.append((actor, agent_scoped, args))
            self.fallbacks.append(allow_unscoped_fallback)
            if args["agentId"] == uncertain_target:
                return None
            return {"id": "wrong-id" if uncorrelated else payload["id"], "result": {"isError": False}}
        self.proxy.upstream_call = send

    def test_reopen_obligation_blocks_handback_until_evidence_backed_disposition(self):
        receipt = self.reopen_report()
        self.assertEqual(receipt["ask_id"], "peer:reopen-one")
        self.assertTrue(self.proxy.handback_to_parent(LEAD, "lead", 1, {"message": "Done"})["result"]["isError"])
        with self.assertRaisesRegex(ValueError, "resolve_peer_report"):
            self.proxy.answer_room_ask(LEAD, "lead", 1, {"leadAgentId": LEAD, "askId": receipt["ask_id"],
                "answer": "ACK", "expectedWorkEpoch": 1, "expectedRevision": self.lease()["revision"]})
        deferred = self.result(self.resolution(outcome="NEEDS_MORE_EVIDENCE", owner=PEER,
                                               checkpoint="After the lost-ACK regression runs"))
        self.assertEqual(deferred["ask"]["status"], "OPEN")
        self.assertTrue(self.proxy.handback_to_parent(LEAD, "lead", 1, {"message": "Done"})["result"]["isError"])
        closed = self.result(self.resolution())
        self.assertEqual(closed["ask"]["status"], "ANSWERED")
        self.assertFalse(self.proxy.handback_to_parent(LEAD, "lead", 1, {"message": "Corrected foundation; limits stated."})["result"]["isError"])

    def test_legacy_reopen_receipt_remains_pending_and_resolves_after_peer_archive(self):
        receipt = self.reopen_report()
        lease = self.lease()
        lease.pop("room_asks")
        lease["peer_reports"]["reopen-one"].pop("ask_id")
        self.write_lease(**lease)
        view = self.result(self.proxy.list_room_observations(WATCHER, "watcher", 1, {"leadAgentId": LEAD}))
        self.assertEqual(view["observations"][0]["handling"], "PENDING")
        self.assertTrue(self.proxy.handback_to_parent(LEAD, "lead", 1, {"message": "Done"})["result"]["isError"])
        self.assertTrue(self.resolution(expectedRevision=1)["result"]["isError"])
        self.assertNotIn("room_asks", self.lease())
        peer_path = self.proxy.AGENTS_ROOT / "records" / f"{PEER}.json"
        peer = json.loads(peer_path.read_text()); peer["archivedAt"] = "2026-09-27T00:00:00Z"
        peer_path.write_text(json.dumps(peer))
        resolved = self.result(self.resolution())
        self.assertEqual(resolved["ask"]["status"], "ANSWERED")
        self.assertEqual(self.lease()["peer_reports"]["reopen-one"]["digest"], receipt["digest"])

    def test_duplicate_legacy_report_backfills_once_without_replacing_evidence(self):
        receipt = self.reopen_report()
        lease = self.lease()
        lease.pop("room_asks")
        lease["peer_reports"]["reopen-one"].pop("ask_id")
        self.write_lease(**lease)
        args = {"report": receipt["report"]}
        first = self.result(self.proxy.record_peer_report(LEAD, "lead", 1, args))
        revision = self.lease()["revision"]
        self.assertEqual(first["ask_id"], "peer:reopen-one")
        self.result(self.proxy.record_peer_report(LEAD, "lead", 2, args))
        self.assertEqual(self.lease()["revision"], revision)

    def test_large_report_evidence_is_retained_with_a_bounded_question(self):
        receipt = self.reopen_report()
        report = dict(receipt["report"], reportId="long-evidence", payload={"evidence": "Observed regression detail. " * 300})
        recorded = self.result(self.proxy.record_peer_report(LEAD, "lead", 1, {"report": report}))
        self.assertEqual(recorded["report"]["payload"]["evidence"], report["payload"]["evidence"])
        ask = self.lease()["room_asks"][recorded["ask_id"]]
        self.assertTrue(ask["question_truncated"])
        self.assertEqual(len(ask["question"]), self.proxy.attention.MAX_QUESTION)
        self.result(self.resolution(reportId="long-evidence"))

    def test_observation_bounds_large_handbacks_and_orders_window_by_time(self):
        receipt = self.reopen_report()
        lease = self.lease()
        lease["peer_reports"] = {}
        for index in range(70):
            report_id = f"report-{69-index:02d}"
            report = dict(receipt["report"], reportId=report_id, payload={"evidence": "x" * 5000})
            timestamp = (dt.datetime(2026, 9, 27, tzinfo=dt.timezone.utc) + dt.timedelta(minutes=index)).isoformat()
            lease["peer_reports"][report_id] = {"report": report, "recorded_at": timestamp, "digest": self.proxy.workflow.digest(report)}
        self.write_lease(**lease)
        view = self.result(self.proxy.list_room_observations(WATCHER, "watcher", 1, {"leadAgentId": LEAD}))
        self.assertEqual(view["omitted_reports"], 6)
        self.assertEqual(len(view["observations"]), 64)
        self.assertEqual(view["observations"][0]["report_id"], "report-63")
        self.assertTrue(view["observations"][0]["handback_truncated"])
        self.assertIsNone(view["observations"][0]["handback"])
        self.assertEqual(len(view["observations"][0]["handback_excerpt"]), 4000)

    def test_escalated_reopen_stays_visible_in_the_actual_final_report(self):
        self.reopen_report()
        self.result(self.resolution(outcome="ESCALATED_TO_HUMAN", owner="human", checkpoint="Owner decides the product boundary"))
        self.assertFalse(self.proxy.handback_to_parent(LEAD, "lead", 1, {"message": "Engineering completed within scope."})["result"]["isError"])
        self.assertIn("Unresolved owner decisions", self.lease()["handback_message"])
        self.assertIn("reopen-one", self.lease()["handback_message"])
        self.assertIn("Separate ACK obligation", self.lease()["handback_message"])

    def test_resolution_rejects_stale_identity_missing_evidence_and_silent_override(self):
        self.reopen_report()
        for updates in ({"reportId": "missing"}, {"expectedWorkEpoch": True}, {"expectedRevision": 1}):
            self.assertTrue(self.resolution(**updates)["result"]["isError"])
        with self.assertRaises(ValueError):
            self.resolution(evidence="")
        self.result(self.resolution())
        duplicate = self.result(self.resolution(expectedRevision=2))
        self.assertFalse(duplicate["changed"])
        self.assertTrue(self.resolution(decision="Keep the workaround without explanation")["result"]["isError"])

    def test_candidate_change_requires_reverification_of_changed_dissent_work(self):
        repo = self.root / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / "code.txt").write_text("new ACK lifetime\n")
        protocol = repo / ".orchestration"
        protocol.mkdir()
        (protocol / "workspace-protocol.md").write_text("Human-approved foundation tactics\n")
        (protocol / "workflow.json").write_text(json.dumps(self.proxy.workflow.default_policy()))
        path = self.proxy.AGENTS_ROOT / "records" / f"{LEAD}.json"
        lead = json.loads(path.read_text()); lead["cwd"] = str(repo); path.write_text(json.dumps(lead))
        self.write_lease(task_class="tiny")
        self.reopen_report()
        digest = self.proxy.workflow.snapshot(repo)["digest"]
        self.assertTrue(self.resolution(changesWork=True, candidateDigest="sha256:wrong")["result"]["isError"])
        self.result(self.resolution(changesWork=True, candidateDigest=digest, evidence="Regression now passes on this candidate."))
        (repo / "code.txt").write_text("later integration changed ACK behavior\n")
        current = self.proxy.workflow.snapshot(repo)["digest"]
        self.assertTrue(self.proxy.handback_to_parent(LEAD, "lead", 1, {"message": "Done", "candidateDigest": current})["result"]["isError"])
        self.result(self.resolution(changesWork=True, candidateDigest=current, evidence="Regression rerun after integration passes."))
        self.assertFalse(self.proxy.handback_to_parent(LEAD, "lead", 1, {"message": "Verified integrated candidate", "candidateDigest": current})["result"]["isError"])

    def test_observer_joins_correlated_evidence_and_never_mutates_or_infers_verdict(self):
        self.reopen_report()
        before = self.proxy.LEASES_PATH.read_bytes()
        result = self.result(self.proxy.list_room_observations(WATCHER, "watcher", 1, {"leadAgentId": LEAD}))
        observation = result["observations"][0]
        self.assertEqual(observation["brief_visibility"], "UNKNOWN")
        self.assertEqual(observation["handling"], "PENDING")
        self.assertNotIn("verdict", observation)
        self.assertEqual(self.proxy.LEASES_PATH.read_bytes(), before)
        self.assertTrue(self.proxy.list_room_observations(PEER, "peer", 1, {"leadAgentId": LEAD})["result"]["isError"])
        self.result(self.resolution())
        result = self.result(self.proxy.list_room_observations(SUPERVISOR, "supervisor", 1, {"leadAgentId": LEAD}))
        self.assertEqual(result["observations"][0]["handling"], "RESOLVED_BY_LEAD")
        lease = self.lease(); lease["peer_briefs"] = {PEER: {"assignment_id": "other", "work_epoch": 1, "excerpt": "stale brief"}}
        self.write_lease(**lease)
        result = self.result(self.proxy.list_room_observations(LEAD, "lead", 1, {"leadAgentId": LEAD}))
        self.assertIsNone(result["observations"][0]["brief"])

    def test_lead_observation_through_mcp_dispatch_does_not_rewrite_or_pin_registry(self):
        before = self.proxy.LEASES_PATH.read_bytes()
        modified = self.proxy.LEASES_PATH.stat().st_mtime_ns
        view = self.result(self.proxy.call_tool(LEAD, "lead", 1, {
            "name": "list_room_observations", "arguments": {"leadAgentId": LEAD}}))
        self.assertEqual(view["observations"], [])
        self.assertEqual(self.proxy.LEASES_PATH.read_bytes(), before)
        self.assertEqual(self.proxy.LEASES_PATH.stat().st_mtime_ns, modified)
        self.assertNotIn("workflow_digest", self.lease())

    def test_changed_work_resolution_rechecks_candidate_even_without_repo_policy(self):
        repo = self.root / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / "code.txt").write_text("corrected foundation\n")
        path = self.proxy.AGENTS_ROOT / "records" / f"{LEAD}.json"
        lead = json.loads(path.read_text()); lead["cwd"] = str(repo); path.write_text(json.dumps(lead))
        self.reopen_report()
        digest = self.proxy.workflow.snapshot(repo)["digest"]
        self.result(self.resolution(changesWork=True, candidateDigest=digest))
        (repo / "code.txt").write_text("later integration invalidates correction\n")
        denied = self.proxy.handback_to_parent(LEAD, "lead", 1, {"message": "Done"})
        self.assertTrue(denied["result"]["isError"])

    def test_steering_requires_exact_human_grant_and_lead_is_notified_first(self):
        self.transport()
        self.assertTrue(self.steer()["result"]["isError"])
        grant = self.grant()
        self.assertEqual(grant["grant"]["authorized_by"], "human")
        self.assertFalse(self.grant()["created"])
        self.assertTrue(self.steer(actor="foreign-supervisor")["result"]["isError"])
        self.assertEqual(self.sends, [])
        self.result(self.steer())
        self.assertEqual([args["agentId"] for _, _, args in self.sends], [LEAD, PEER])
        self.assertEqual(self.sends[1][0], LEAD)
        self.assertTrue(self.sends[1][2]["notifyOnFinish"])
        self.assertFalse(self.sends[0][2]["notifyOnFinish"])
        self.assertIn("does not widen write scope", self.sends[1][2]["prompt"])
        self.assertEqual([args["activeTurnBehavior"] for _, _, args in self.sends], ["steer", "steer"])
        self.result(self.steer())
        self.assertEqual(len(self.sends), 2)
        self.assertEqual(self.fallbacks, [True, False])

    def test_strict_scoped_transport_never_drops_lead_callback_context_on_missing_method(self):
        payload = {"jsonrpc": "2.0", "id": "request-one", "method": "tools/call",
                   "params": {"name": "send_agent_prompt", "arguments": {"agentId": PEER, "notifyOnFinish": True}}}
        response = {"jsonrpc": "2.0", "id": "request-one", "error": {"code": -32601, "message": "Method not found"}}
        class HTTPResponse:
            headers = {"content-type": "application/json"}
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return json.dumps(response).encode()
        with patch.object(self.proxy.urllib.request, "urlopen", return_value=HTTPResponse()) as opener:
            result = proxy_module().upstream_call(LEAD, payload, allow_unscoped_fallback=False)
        self.assertEqual(result, response)
        self.assertEqual(opener.call_count, 1)
        self.assertIn("callerAgentId=" + LEAD, opener.call_args.args[0].full_url)

    def test_steering_rejects_room_revision_and_assignment_drift(self):
        self.transport()
        self.grant()
        self.result(self.open(revision=self.lease()["revision"]))
        self.assertTrue(self.steer()["result"]["isError"])
        self.assertEqual(self.sends, [])
        path = self.proxy.AGENTS_ROOT / "records" / f"{PEER}.json"
        peer = json.loads(path.read_text()); peer["labels"]["assignment_id"] = "different"; path.write_text(json.dumps(peer))
        with self.assertRaisesRegex(ValueError, "drifted"):
            self.steer()

    def test_steering_rejects_modified_grant_evidence(self):
        self.grant()
        self.transport()
        lease = self.lease()
        lease["peer_steering"]["grant-one"]["prompt"] = "A different operation without Human authorization"
        self.write_lease(**lease)
        with self.assertRaisesRegex(ValueError, "digest"):
            self.steer()
        self.assertEqual(self.sends, [])

    def test_steering_rejects_runtime_or_lead_epoch_drift_before_delivery(self):
        self.grant()
        self.transport()
        path = self.proxy.AGENTS_ROOT / "records" / f"{LEAD}.json"
        lead = json.loads(path.read_text()); lead["model"] = "different-model"; path.write_text(json.dumps(lead))
        with self.assertRaisesRegex(ValueError, "drifted"):
            self.steer()
        lead.pop("model"); lead["labels"]["work_epoch"] = "2"; path.write_text(json.dumps(lead))
        with self.assertRaisesRegex(ValueError, "epoch authority"):
            self.steer()
        self.assertEqual(self.sends, [])

    def test_owner_steering_cli_previews_and_applies_without_live_transport(self):
        loader = importlib.machinery.SourceFileLoader("steering_cli_test", str(ROOT / "bin/paseo-room-workflow"))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        cli = importlib.util.module_from_spec(spec); loader.exec_module(cli)
        cli.proxy_module = lambda: self.proxy
        request = self.root / "steering.json"
        args = {"leadAgentId": LEAD, "peerAgentId": PEER, "assignmentId": "assignment-one",
                "grantId": "grant-one", "humanInstruction": "Reconsider the premise", "prompt": "Investigate with evidence",
                "expectedWorkEpoch": 1, "expectedRevision": 1}
        request.write_text(json.dumps(args))
        def command(*arguments):
            output = io.StringIO()
            with patch.dict(os.environ, {}, clear=True), patch.object(sys, "argv", ["paseo-room-workflow", *arguments]), contextlib.redirect_stdout(output):
                self.assertEqual(cli.main(), 0)
            return json.loads(output.getvalue())
        before = self.proxy.LEASES_PATH.read_bytes()
        self.assertFalse(command("authorize-peer-steering", str(request))["applied"])
        self.assertEqual(self.proxy.LEASES_PATH.read_bytes(), before)
        self.assertTrue(command("authorize-peer-steering", str(request), "--apply")["created"])
        request.write_text(json.dumps({"leadAgentId": LEAD, "grantId": "grant-one",
                                      "expectedWorkEpoch": 1, "expectedRevision": self.lease()["revision"]}))
        self.transport()
        self.assertFalse(command("steer-peer", str(request))["applied"])
        self.assertEqual(self.sends, [])
        self.result(command("steer-peer", str(request), "--apply"))
        self.assertEqual([args["agentId"] for _, _, args in self.sends], [LEAD, PEER])
        observed = command("observations", "--lead-id", LEAD)
        self.assertEqual(self.result(observed)["steering"][0]["state"], "DELIVERED")

    def test_uncertain_notice_never_contacts_peer_or_automatically_retries(self):
        self.transport(uncertain_target=LEAD)
        self.grant()
        self.assertTrue(self.steer()["result"]["isError"])
        self.assertEqual(self.lease()["peer_steering"]["grant-one"]["state"], "UNCERTAIN")
        self.assertEqual(len(self.sends), 1)
        self.assertTrue(self.steer()["result"]["isError"])
        self.assertEqual(len(self.sends), 1)
        with patch.dict(os.environ, {}, clear=True):
            self.proxy.resolve_peer_steering({"leadAgentId": LEAD, "grantId": "grant-one", "resolution": "DELIVERED",
                "evidence": "Human inspected the exact Lead timeline message.", "expectedWorkEpoch": 1, "expectedRevision": self.lease()["revision"]})
        self.assertEqual(len(self.sends), 1)
        self.transport()
        self.result(self.steer())
        self.assertEqual([args["agentId"] for _, _, args in self.sends], [PEER])

    def test_uncertain_peer_delivery_blocks_handback_until_human_resolution(self):
        self.transport(uncertain_target=PEER)
        self.grant()
        self.assertTrue(self.steer()["result"]["isError"])
        self.assertTrue(self.proxy.handback_to_parent(LEAD, "lead", 1, {"message": "Done"})["result"]["isError"])
        with patch.dict(os.environ, {}, clear=True):
            self.proxy.resolve_peer_steering({"leadAgentId": LEAD, "grantId": "grant-one", "resolution": "NOT_DELIVERED",
                "evidence": "Human verified no Peer message was delivered.", "expectedWorkEpoch": 1, "expectedRevision": self.lease()["revision"]})
        self.assertEqual(self.lease()["peer_steering"]["grant-one"]["state"], "REJECTED")

    def test_uncorrelated_delivery_is_unknown_and_pending_grant_can_be_cancelled(self):
        self.transport(uncorrelated=True)
        self.grant()
        self.assertTrue(self.steer()["result"]["isError"])
        self.assertEqual(self.lease()["peer_steering"]["grant-one"]["state"], "UNCERTAIN")
        self.assertEqual(len(self.sends), 1)

    def test_direct_human_steering_preserves_lead_callback_and_role_cannot_authorize(self):
        self.supervised = False; self.write_agents(); self.write_lease()
        self.transport()
        self.grant()
        self.assertTrue(self.steer()["result"]["isError"])
        self.result(self.steer(actor="human", role="human"))
        self.assertEqual(self.sends[0][0:2], ("human", False))
        self.assertEqual(self.sends[1][0:2], (LEAD, True))
        with patch.dict(os.environ, {"PASEO_ROOM_ROLE": "supervisor"}):
            with self.assertRaisesRegex(ValueError, "owner shell"):
                self.proxy.authorize_peer_steering({})

    def test_pending_authorization_can_be_cancelled_without_any_prompt(self):
        self.transport()
        self.grant()
        self.assertTrue(self.proxy.handback_to_parent(LEAD, "lead", 1, {"message": "Done"})["result"]["isError"])
        with patch.dict(os.environ, {}, clear=True):
            self.proxy.resolve_peer_steering({"leadAgentId": LEAD, "grantId": "grant-one", "resolution": "CANCELLED",
                "evidence": "Human withdrew the planned intervention.", "expectedWorkEpoch": 1, "expectedRevision": self.lease()["revision"]})
        self.assertEqual(self.sends, [])


if __name__ == "__main__":
    unittest.main()
