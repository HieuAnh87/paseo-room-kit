#!/usr/bin/env python3
"""Exact proof and Git ref behavior for the optional owner-shell Land path."""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))
import room_land
import room_workflow as workflow
import test_proxy_handback as fixtures


def git(root: pathlib.Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout.strip()


class LandTest(unittest.TestCase):
    tearDown = fixtures.ManagedLifecycleTest.tearDown
    write_agent = fixtures.ManagedLifecycleTest.write_agent
    write_workspace = fixtures.ManagedLifecycleTest.write_workspace
    write_lease = fixtures.ManagedLifecycleTest.write_lease
    read_lease = fixtures.ManagedLifecycleTest.read_lease
    base_lease = fixtures.ManagedLifecycleTest.base_lease
    upstream_call = fixtures.ManagedLifecycleTest.upstream_call
    text = staticmethod(fixtures.ManagedLifecycleTest.text)

    def setUp(self) -> None:
        fixtures.ManagedLifecycleTest.setUp(self)
        self.base = self.root / "base"
        self.source = self.root / "lane"
        self.base.mkdir()
        git(self.base, "init", "-q", "-b", "main")
        git(self.base, "config", "user.name", "Room Test")
        git(self.base, "config", "user.email", "room@example.test")
        (self.base / ".orchestration").mkdir()
        (self.base / ".orchestration/workflow.json").write_text(json.dumps(workflow.default_policy()))
        (self.base / ".orchestration/workspace-protocol.md").write_text("Project tactics\n")
        (self.base / "code.txt").write_text("base\n")
        git(self.base, "add", ".")
        git(self.base, "commit", "-qm", "Base")
        self.base_sha = git(self.base, "rev-parse", "HEAD")
        git(self.base, "worktree", "add", "-qb", "lane/one", str(self.source))
        (self.source / "code.txt").write_text("landed\n")
        git(self.source, "add", "code.txt")
        git(self.source, "commit", "-qm", "Candidate")
        self.source_sha = git(self.source, "rev-parse", "HEAD")
        self.lead["cwd"] = str(self.source)
        self.write_agent(self.lead)
        lease = self.base_lease()
        lease["task_class"] = "tiny"
        self.write_lease(lease)
        candidate = workflow.snapshot(self.source)["digest"]
        handback = self.module.handback_to_parent(fixtures.LEAD_ID, "lead", 1, {
            "message": "Checks passed; candidate committed and clean.", "candidateDigest": candidate,
        })
        self.assertFalse(handback["result"]["isError"], self.text(handback))
        ready = self.read_lease()
        decision = self.module.record_slp_decision("human", "human", 2, {
            "agentId": fixtures.LEAD_ID, "decision": "ACCEPTED", "evidenceDigest": ready["evidence_digest"],
            "expectedWorkEpoch": 1, "expectedRevision": ready["revision"],
        })
        self.assertFalse(decision["result"]["isError"], self.text(decision))

    def test_prepare_is_read_only_and_checked_out_base_fast_forwards_only_after_exact_approval(self) -> None:
        registry_before = self.module.LEASES_PATH.read_bytes()
        plan = room_land.prepare(self.module, fixtures.LEAD_ID, "main", self.base)
        self.assertEqual(plan["sourceSha"], self.source_sha)
        self.assertEqual(plan["targetSha"], self.base_sha)
        self.assertEqual(plan["candidateDigest"], self.read_lease()["candidate_digest"])
        self.assertEqual(plan["commitsAhead"], 1)
        self.assertEqual(self.module.LEASES_PATH.read_bytes(), registry_before)
        self.assertEqual(git(self.base, "rev-parse", "HEAD"), self.base_sha)
        with self.assertRaisesRegex(workflow.WorkflowError, "approval"):
            room_land.apply(self.module, plan, "sha256:" + "0" * 64)
        self.assertEqual(git(self.base, "rev-parse", "HEAD"), self.base_sha)
        outcome = room_land.apply(self.module, plan, plan["planDigest"])
        self.assertTrue(outcome["applied"])
        self.assertEqual(git(self.base, "rev-parse", "HEAD"), self.source_sha)
        self.assertEqual(git(self.base, "status", "--porcelain"), "")
        self.assertEqual(self.module.LEASES_PATH.read_bytes(), registry_before)

    def test_unchecked_out_local_branch_uses_compare_and_swap(self) -> None:
        git(self.base, "branch", "delivery", self.base_sha)
        plan = room_land.prepare(self.module, fixtures.LEAD_ID, "delivery")
        self.assertIsNone(plan["targetWorktree"])
        result = room_land.apply(self.module, plan, plan["planDigest"])
        self.assertEqual(result["newSha"], self.source_sha)
        self.assertEqual(git(self.base, "rev-parse", "delivery"), self.source_sha)
        self.assertEqual(git(self.base, "rev-parse", "main"), self.base_sha)

    def test_drifted_target_or_candidate_requires_new_plan_and_acceptance(self) -> None:
        plan = room_land.prepare(self.module, fixtures.LEAD_ID, "main", self.base)
        (self.base / "other.txt").write_text("other\n")
        with self.assertRaisesRegex(workflow.WorkflowError, "clean"):
            room_land.apply(self.module, plan, plan["planDigest"])
        (self.base / "other.txt").unlink()
        (self.source / "code.txt").write_text("changed after acceptance\n")
        with self.assertRaisesRegex(workflow.WorkflowError, "candidate changed|Candidate changed|Accepted candidate changed"):
            room_land.apply(self.module, plan, plan["planDigest"])
        self.assertEqual(git(self.base, "rev-parse", "HEAD"), self.base_sha)

    def test_epoch_revision_or_target_ref_drift_rejects_saved_plan(self) -> None:
        plan = room_land.prepare(self.module, fixtures.LEAD_ID, "main", self.base)
        lease = self.read_lease()
        lease["revision"] += 1
        self.write_lease(lease)
        with self.assertRaisesRegex(workflow.WorkflowError, "plan drifted"):
            room_land.apply(self.module, plan, plan["planDigest"])
        lease["revision"] -= 1
        self.write_lease(lease)
        (self.base / "base-only.txt").write_text("parallel base change\n")
        git(self.base, "add", "base-only.txt")
        git(self.base, "commit", "-qm", "Base advanced")
        with self.assertRaisesRegex(workflow.WorkflowError, "fast-forward descendant"):
            room_land.apply(self.module, plan, plan["planDigest"])

    def test_tampered_plan_and_missing_review_fail_closed(self) -> None:
        plan = room_land.prepare(self.module, fixtures.LEAD_ID, "main", self.base)
        tampered = dict(plan, sourceSha=self.base_sha)
        with self.assertRaisesRegex(workflow.WorkflowError, "plan drifted"):
            room_land.apply(self.module, tampered, plan["planDigest"])
        lease = self.read_lease()
        lease["task_class"] = "sensitive"
        self.write_lease(lease)
        with self.assertRaisesRegex(workflow.WorkflowError, "independent review"):
            room_land.prepare(self.module, fixtures.LEAD_ID, "main", self.base)

    def test_active_agent_and_other_room_block_land(self) -> None:
        self.agent_status = "running"
        with self.assertRaisesRegex(workflow.WorkflowError, "pause writers"):
            room_land.prepare(self.module, fixtures.LEAD_ID, "main", self.base)
        self.agent_status = "idle"
        lease = self.read_lease()
        other = {"state": "active", "room_kind": "managed_slp", "repository": str(self.base),
                 "workspace_id": "other", "lead_agent_id": "other-lead", "revision": 1}
        self.module.LEASES_PATH.write_text(json.dumps({"version": 2, "leases": {
            fixtures.WORKSPACE_ID: lease, "other": other}}))
        with self.assertRaisesRegex(workflow.WorkflowError, "Another managed room"):
            room_land.prepare(self.module, fixtures.LEAD_ID, "main", self.base)

    def test_unaccepted_or_unreviewed_candidate_cannot_land(self) -> None:
        lease = self.read_lease()
        lease["human_decision"] = "ABANDONED"
        self.write_lease(lease)
        with self.assertRaisesRegex(workflow.WorkflowError, "ACCEPTED"):
            room_land.prepare(self.module, fixtures.LEAD_ID, "main", self.base)

    def test_checked_out_target_requires_exact_worktree(self) -> None:
        with self.assertRaisesRegex(workflow.WorkflowError, "checked out"):
            room_land.prepare(self.module, fixtures.LEAD_ID, "main")


if __name__ == "__main__":
    import unittest
    unittest.main()
