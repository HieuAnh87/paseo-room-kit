#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))
import room_workflow as workflow
import test_proxy_handback as fixtures


def init_repo(root: pathlib.Path) -> None:
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    (root / "code.txt").write_text("initial\n")


class CandidateContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name) / "repo"
        init_repo(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_candidate_covers_unborn_head_index_untracked_modes_and_symlinks(self) -> None:
        before = workflow.snapshot(self.root)
        self.assertIsNone(before["head"])
        subprocess.run(["git", "-C", str(self.root), "add", "code.txt"], check=True)
        staged = workflow.snapshot(self.root)
        self.assertNotEqual(before["digest"], staged["digest"])
        (self.root / "code.txt").chmod(0o755)
        executable = workflow.snapshot(self.root)
        self.assertNotEqual(staged["digest"], executable["digest"])
        (self.root / "link").symlink_to("code.txt")
        linked = workflow.snapshot(self.root)
        self.assertNotEqual(executable["digest"], linked["digest"])
        (self.root / "link").unlink()
        (self.root / "link").symlink_to("missing.txt")
        self.assertNotEqual(linked["digest"], workflow.snapshot(self.root)["digest"])
        (self.root / "code.txt").unlink()
        self.assertTrue(any(entry.get("deleted") for entry in workflow.snapshot(self.root)["files"]))

    def test_init_preserves_tactics_and_dry_run_does_not_mutate(self) -> None:
        cli = ROOT / "bin/paseo-room-workflow"
        environment = {key: value for key, value in os.environ.items() if key != "PASEO_ROOM_ROLE"}
        subprocess.run([sys.executable, str(cli), "init", str(self.root)], check=True, capture_output=True, env=environment)
        self.assertFalse((self.root / ".orchestration").exists())
        subprocess.run([sys.executable, str(cli), "init", str(self.root), "--apply"], check=True, capture_output=True, env=environment)
        path = self.root / ".orchestration/workspace-protocol.md"
        path.write_text("Human project choices\n")
        subprocess.run([sys.executable, str(cli), "init", str(self.root), "--apply"], check=True, capture_output=True, env=environment)
        self.assertEqual(path.read_text(), "Human project choices\n")
        self.assertTrue(workflow.load_policy(self.root))

    def test_policy_is_optional_but_malformed_or_symlink_policy_fails_closed(self) -> None:
        self.assertIsNone(workflow.load_policy(self.root))
        (self.root / ".orchestration").mkdir()
        path = self.root / ".orchestration/workflow.json"
        path.write_text("not json")
        with self.assertRaises(workflow.WorkflowError):
            workflow.load_policy(self.root)
        path.unlink()
        path.symlink_to("missing.json")
        with self.assertRaises(workflow.WorkflowError):
            workflow.load_policy(self.root)


class WorkflowAuthorityTest(unittest.TestCase):
    # Reuse the existing durable Paseo/lease fixture, not its test cases.
    setUp = fixtures.ManagedLifecycleTest.setUp
    tearDown = fixtures.ManagedLifecycleTest.tearDown
    write_agent = fixtures.ManagedLifecycleTest.write_agent
    write_workspace = fixtures.ManagedLifecycleTest.write_workspace
    base_lease = fixtures.ManagedLifecycleTest.base_lease
    write_lease = fixtures.ManagedLifecycleTest.write_lease
    read_lease = fixtures.ManagedLifecycleTest.read_lease
    upstream_call = fixtures.ManagedLifecycleTest.upstream_call
    text = staticmethod(fixtures.ManagedLifecycleTest.text)

    def root_binding(self, *, observer: bool = False, policy: bool = False, task_class: str = "tiny") -> None:
        self.module.LEASES_PATH.unlink()
        self.lead["labels"].pop("paseo.parent-agent-id")
        self.repo = self.root / "repo"
        init_repo(self.repo)
        self.lead["cwd"] = str(self.repo)
        self.write_agent(self.lead)
        if policy:
            directory = self.repo / ".orchestration"
            directory.mkdir()
            (directory / "workspace-protocol.md").write_text("Human-approved repo tactics\n")
            (directory / "workflow.json").write_text(json.dumps(workflow.default_policy()))
        self.module.bind_root_lead(fixtures.LEAD_ID, fixtures.SUPERVISOR_ID if observer else None, task_class, apply=True)

    def test_root_binding_dry_run_neither_writes_registry_nor_reparents(self) -> None:
        self.module.LEASES_PATH.unlink()
        self.lead["labels"].pop("paseo.parent-agent-id")
        self.write_agent(self.lead)
        result = self.module.bind_root_lead(fixtures.LEAD_ID, None, "tiny")
        self.assertFalse(result["applied"])
        self.assertFalse(self.module.LEASES_PATH.exists())
        self.assertEqual(self.calls, [])
        self.assertNotIn("paseo.parent-agent-id", self.module.load_agent_record(fixtures.LEAD_ID)["labels"])

    def test_binding_rejects_another_active_binding_for_the_same_lead(self) -> None:
        self.module.LEASES_PATH.unlink()
        self.lead["labels"].pop("paseo.parent-agent-id")
        self.write_agent(self.lead)
        lease = self.base_lease()
        lease["workspace_id"] = "another-workspace"
        self.module.LEASES_PATH.write_text(json.dumps({"version": 2, "leases": {"another-workspace": lease}}))
        with self.assertRaises(workflow.WorkflowError):
            self.module.bind_root_lead(fixtures.LEAD_ID, None, "tiny", apply=True)
        self.assertEqual(self.calls, [])

    def test_direct_handback_is_durable_deduplicated_and_human_can_accept(self) -> None:
        self.root_binding()
        self.calls.clear()
        result = self.module.handback_to_parent(fixtures.LEAD_ID, "lead", 1, {"message": "Direct outcome, exact checks and limits."})
        self.assertFalse(result["result"]["isError"], self.text(result))
        self.assertFalse(any(name == "send_agent_prompt" for _, name, _ in self.calls))
        lease = self.read_lease()
        self.assertEqual(lease["decision_state"], "HANDBACK_READY")
        result = self.module.handback_to_parent(fixtures.LEAD_ID, "lead", 2, {"message": "retry"})
        self.assertTrue(result["result"]["isError"])
        queue = self.module.list_slp_decisions("human", "human", 3, {})
        self.assertEqual(json.loads(self.text(queue))["pending"][0]["authority_mode"], "direct")
        result = self.module.record_slp_decision("human", "human", 4, {
            "agentId": fixtures.LEAD_ID, "decision": "ACCEPTED", "evidenceDigest": lease["evidence_digest"],
            "expectedWorkEpoch": 1, "expectedRevision": lease["revision"],
        })
        self.assertFalse(result["result"]["isError"], self.text(result))

    def test_observer_receives_root_lead_report_and_foreign_observer_cannot_decide(self) -> None:
        self.root_binding(observer=True)
        result = self.module.handback_to_parent(fixtures.LEAD_ID, "lead", 1, {"message": "Observed root outcome."})
        self.assertFalse(result["result"]["isError"], self.text(result))
        self.assertTrue(any(name == "send_agent_prompt" and arguments["agentId"] == fixtures.SUPERVISOR_ID for _, name, arguments in self.calls))
        lease = self.read_lease()
        result = self.module.record_slp_decision("foreign-supervisor", "supervisor", 2, {
            "agentId": fixtures.LEAD_ID, "decision": "ACCEPTED", "evidenceDigest": lease["evidence_digest"],
            "expectedWorkEpoch": 1, "expectedRevision": lease["revision"],
        })
        self.assertTrue(result["result"]["isError"])

    def test_sensitive_review_correlates_candidate_and_drift_invalidates_acceptance(self) -> None:
        self.root_binding(policy=True, task_class="sensitive")
        candidate = workflow.snapshot(self.repo)["digest"]
        with self.assertRaises(workflow.WorkflowError):
            self.module.handback_to_parent(fixtures.LEAD_ID, "lead", 1, {"message": "premature", "candidateDigest": candidate})
        self.assertEqual(self.read_lease()["decision_state"], "WORKING")
        peer = {"id": fixtures.PEER_ID, "workspaceId": fixtures.WORKSPACE_ID,
                "labels": {"role": "peer", "disposition": "reviewer", "write_mode": "read_only", "room_kind": "managed_slp", "work_epoch": "1",
                           "assignment_id": "assignment-one", "paseo.parent-agent-id": fixtures.LEAD_ID}}
        self.write_agent(peer)
        report = {"version": 1, "reportId": "report-one", "peerAgentId": fixtures.PEER_ID,
                  "parentLeadId": fixtures.LEAD_ID, "workspaceId": fixtures.WORKSPACE_ID,
                  "workEpoch": 1, "assignmentId": "assignment-one", "kind": "REVIEW",
                  "payload": {"verdict": "APPROVE", "candidateDigest": candidate, "evidence": "Independent checks and limitations."}}
        wrong = copy.deepcopy(report)
        wrong["assignmentId"] = "another-assignment"
        with self.assertRaises(workflow.WorkflowError):
            self.module.record_peer_report(fixtures.LEAD_ID, "lead", 2, {"report": wrong})
        result = self.module.record_peer_report(fixtures.LEAD_ID, "lead", 3, {"report": report})
        duplicate = self.module.record_peer_report(fixtures.LEAD_ID, "lead", 4, {"report": report})
        self.assertEqual(self.text(result), self.text(duplicate))
        altered = copy.deepcopy(report)
        altered["payload"]["evidence"] = "different evidence"
        result = self.module.record_peer_report(fixtures.LEAD_ID, "lead", 5, {"report": altered})
        self.assertTrue(result["result"]["isError"])
        result = self.module.handback_to_parent(fixtures.LEAD_ID, "lead", 6, {"message": "Reviewed candidate.", "candidateDigest": candidate})
        self.assertFalse(result["result"]["isError"], self.text(result))
        lease = self.read_lease()
        (self.repo / "code.txt").write_text("changed after review\n")
        with self.assertRaises(workflow.WorkflowError):
            self.module.record_slp_decision("human", "human", 7, {
                "agentId": fixtures.LEAD_ID, "decision": "ACCEPTED", "evidenceDigest": lease["evidence_digest"],
                "expectedWorkEpoch": 1, "expectedRevision": lease["revision"],
            })
        self.assertNotIn("human_decision", self.read_lease())

    def test_report_rejects_wrong_epoch_and_engineer_review(self) -> None:
        peer = {"id": "peer-one", "workspaceId": "workspace-one", "labels": {
            "role": "peer", "paseo.parent-agent-id": "lead-one", "room_kind": "managed_slp",
            "work_epoch": "1", "assignment_id": "assignment-one", "disposition": "engineer"}}
        lead = {"id": "lead-one"}
        report = {"version": 1, "reportId": "report-one", "peerAgentId": "peer-one",
            "parentLeadId": "lead-one", "workspaceId": "workspace-one", "workEpoch": 1,
            "assignmentId": "assignment-one", "kind": "REVIEW", "payload": {
                "evidence": "Checks", "candidateDigest": "sha256:candidate", "verdict": "APPROVE"}}
        with self.assertRaises(workflow.WorkflowError):
            workflow.validate_report(report, peer, lead, 1)
        peer["labels"]["disposition"] = "reviewer"
        peer["labels"]["write_mode"] = "read_only"
        self.assertEqual(workflow.validate_report(report, peer, lead, 1), report)
        with self.assertRaises(workflow.WorkflowError):
            workflow.validate_report(report, peer, lead, 2)

    def test_findings_block_handback_even_with_another_approval(self) -> None:
        self.root_binding(policy=True, task_class="sensitive")
        candidate = workflow.snapshot(self.repo)["digest"]
        lease = self.read_lease()
        lease["candidate_reviews"] = {
            "reviewer-one": {"verdict": "APPROVE", "candidate_digest": candidate, "work_epoch": 1},
            "reviewer-two": {"verdict": "FINDINGS", "candidate_digest": candidate, "work_epoch": 1}}
        self.write_lease(lease)
        with self.assertRaisesRegex(workflow.WorkflowError, "Unresolved"):
            self.module.handback_to_parent(fixtures.LEAD_ID, "lead", 1, {"message": "outcome", "candidateDigest": candidate})
        self.assertEqual(self.read_lease()["decision_state"], "WORKING")

    def test_observed_reopen_invalidates_candidate_and_rejection_restores_proof(self) -> None:
        self.root_binding(observer=True, policy=True)
        candidate = workflow.snapshot(self.repo)["digest"]
        self.module.handback_to_parent(fixtures.LEAD_ID, "lead", 1, {"message": "Outcome", "candidateDigest": candidate})
        lease = self.read_lease()
        self.module.upstream_call = lambda actor, payload: {"result": {"isError": True, "content": []}}
        result = self.module.reopen_work_epoch(fixtures.SUPERVISOR_ID, "supervisor", 2, {
            "agentId": fixtures.LEAD_ID, "prompt": "Bounded follow-up", "expectedWorkEpoch": 1, "expectedRevision": lease["revision"]})
        self.assertTrue(result["result"]["isError"])
        restored = self.read_lease()
        self.assertEqual(restored["work_epoch"], 1)
        self.assertEqual(restored["candidate_digest"], candidate)
        self.module.upstream_call = self.upstream_call
        result = self.module.reopen_work_epoch(fixtures.SUPERVISOR_ID, "supervisor", 3, {
            "agentId": fixtures.LEAD_ID, "prompt": "Bounded follow-up", "expectedWorkEpoch": 1, "expectedRevision": restored["revision"]})
        self.assertFalse(result["result"]["isError"], self.text(result))
        self.assertEqual(self.read_lease()["work_epoch"], 2)
        self.assertNotIn("candidate_digest", self.read_lease())

    def test_withdraw_rejects_unsettled_descendants(self) -> None:
        self.root_binding()
        self.write_agent({"id": fixtures.PEER_ID, "workspaceId": fixtures.WORKSPACE_ID,
            "labels": {"role": "peer", "paseo.parent-agent-id": fixtures.LEAD_ID}})
        with self.assertRaises(workflow.WorkflowError):
            self.module.withdraw_binding({"agentId": fixtures.LEAD_ID, "expectedWorkEpoch": 1,
                "expectedRevision": 1, "settlementEvidence": "Checkpoint"}, apply=True)
        self.assertEqual(self.read_lease()["state"], "active")

    def test_protocol_and_provider_drift_fail_closed(self) -> None:
        self.root_binding(policy=True)
        (self.repo / ".orchestration/workspace-protocol.md").write_text("changed tactics")
        with self.assertRaises(workflow.WorkflowError):
            self.module.inspect_work_context(fixtures.LEAD_ID, "lead", 1, {})
        (self.repo / ".orchestration/workspace-protocol.md").write_text("Human-approved repo tactics\n")
        self.lead["provider"] = "another-lead"
        self.write_agent(self.lead)
        with self.assertRaises(workflow.WorkflowError):
            self.module.inspect_work_context(fixtures.LEAD_ID, "lead", 2, {})

    def test_withdraw_and_rebind_advance_epoch_instead_of_reusing_correlation(self) -> None:
        self.root_binding()
        request = {"agentId": fixtures.LEAD_ID, "expectedWorkEpoch": 1, "expectedRevision": 1, "settlementEvidence": "Descendants settled; Human withdrew old work."}
        self.module.withdraw_binding(request, apply=True)
        self.module.bind_root_lead(fixtures.LEAD_ID, None, "tiny", apply=True)
        self.assertEqual(self.read_lease()["work_epoch"], 2)
        self.assertEqual(self.read_lease()["decision_state"], "WORKING")


if __name__ == "__main__":
    unittest.main()
