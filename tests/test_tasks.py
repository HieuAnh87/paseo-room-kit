from __future__ import annotations

import copy
import json
import os
import pathlib
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))
import room_tasks as tasks
import room_workflow as workflow
import test_proxy_handback as fixtures
import test_workflow as workflow_fixtures


class TaskContractTest(unittest.TestCase):
    tearDown = fixtures.ManagedLifecycleTest.tearDown
    write_agent = fixtures.ManagedLifecycleTest.write_agent
    write_workspace = fixtures.ManagedLifecycleTest.write_workspace
    base_lease = fixtures.ManagedLifecycleTest.base_lease
    write_lease = fixtures.ManagedLifecycleTest.write_lease
    read_lease = fixtures.ManagedLifecycleTest.read_lease
    upstream_call = fixtures.ManagedLifecycleTest.upstream_call
    text = staticmethod(fixtures.ManagedLifecycleTest.text)
    root_binding = workflow_fixtures.WorkflowAuthorityTest.root_binding

    def setUp(self) -> None:
        fixtures.ManagedLifecycleTest.setUp(self)
        self.root_binding(policy=True, task_class="tiny")
        self.recipe = {"argv": [sys.executable, "-c", "print('verified')"], "timeoutSeconds": 2, "maxOutputBytes": 1024}
        self.policy_path = self.repo / ".orchestration/workflow.json"
        policy = workflow.default_policy()
        policy["checks"] = {"verify": self.recipe}
        self.policy_path.write_text(json.dumps(policy))
        # Fixture setup alone may repin the protocol; production requires owner replacement.
        lease = self.read_lease()
        lease.pop("workflow_digest", None)
        self.write_lease(lease)

    def call_task(self, operation: str, **arguments):
        lease = self.read_lease()
        arguments.update(expectedWorkEpoch=lease["work_epoch"], expectedRevision=lease["revision"])
        result = self.module.work_task_operation(fixtures.LEAD_ID, "lead", 1, arguments, operation)
        self.assertFalse(result["result"].get("isError"), self.text(result))
        return json.loads(self.text(result))

    def define(self, name: str, scope=None, dependencies=None, checks=None):
        return self.call_task("define_work_task", taskId=name, objective="Bounded outcome", write=True,
                              scope=scope or ["code.txt"], dependsOn=dependencies or [], requiredChecks=checks or [])

    def dispatch(self, name: str, peer_id=fixtures.PEER_ID):
        lease = self.read_lease()
        registry = {"leases": {fixtures.WORKSPACE_ID: lease}}
        task = tasks.epoch_state(lease)["tasks"][name]
        assignment = "assignment-" + name
        tasks.reserve(registry, lease, name, str(task["revision"]), assignment, "tool-" + name, True, self.repo)
        labels = {"role": "peer", "paseo.parent-agent-id": fixtures.LEAD_ID, "room_kind": "managed_slp",
                  "work_epoch": "1", "assignment_id": assignment, "task_id": name,
                  "task_revision": str(task["revision"]), "disposition": "engineer", "write_mode": "write"}
        self.write_agent({"id": peer_id, "workspaceId": fixtures.WORKSPACE_ID, "labels": labels})
        tasks.bind_peer(lease, name, labels, peer_id)
        self.write_lease(lease)

    def accept(self, name):
        return self.call_task("settle_work_task", taskId=name, decision="ACCEPTED", evidence="Lead inspected exact result and checks",
                              writersQuiescent=True, candidateDigest=workflow.snapshot(self.repo)["digest"])

    def test_task_cas_does_not_mutate_on_stale_revision_or_foreign_authority(self):
        before = self.module.LEASES_PATH.read_bytes()
        args = dict(taskId="one", objective="Work", write=True, scope=["code.txt"], dependsOn=[], requiredChecks=[],
                    expectedWorkEpoch=1, expectedRevision=999)
        with self.assertRaisesRegex(workflow.WorkflowError, "stale"):
            self.module.work_task_operation(fixtures.LEAD_ID, "lead", 1, args, "define_work_task")
        self.assertEqual(before, self.module.LEASES_PATH.read_bytes())
        denied = self.module.work_task_operation(fixtures.SUPERVISOR_ID, "supervisor", 1, args, "define_work_task")
        self.assertTrue(denied["result"]["isError"])

    def test_overlapping_scope_across_worktrees_and_prefix_boundaries(self):
        self.define("one", ["src"])
        self.define("two", ["src/file.py"])
        self.define("three", ["src2"])
        self.dispatch("one")
        lease = self.read_lease()
        second = copy.deepcopy(lease)
        second["workspace_id"] = "another-workspace"
        second["work_tasks"]["epochs"]["1"]["tasks"] = {"two": second["work_tasks"]["epochs"]["1"]["tasks"]["two"]}
        subprocess.run(["git", "-C", str(self.repo), "add", "code.txt"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                        "commit", "-qm", "Fixture"], check=True, capture_output=True)
        other_root = self.root / "other-worktree"
        subprocess.run(["git", "-C", str(self.repo), "worktree", "add", "-q", "-b", "fixture-lane", str(other_root)], check=True, capture_output=True)
        self.assertEqual(tasks.scope_root(self.repo), tasks.scope_root(other_root))
        registry = {"leases": {"one": lease, "two": second}}
        with self.assertRaisesRegex(workflow.WorkflowError, "overlap"):
            tasks.reserve(registry, second, "two", "1", "assignment-two", "tool-two", True, other_root)
        tasks.reserve(registry, lease, "three", "1", "assignment-three", "tool-three", True, self.repo)
        self.assertFalse(tasks.overlaps("src", "src2"))

    def test_prerequisite_reopen_holds_descendants_and_keeps_writer_scope(self):
        self.define("one")
        self.define("two", ["other.txt"], ["one"])
        self.dispatch("one")
        self.accept("one")
        self.dispatch("two", "peer-two")
        self.call_task("reopen_work_task", taskId="one", evidence="The prerequisite premise failed")
        lease = self.read_lease()
        task = tasks.epoch_state(lease)["tasks"]["two"]
        self.assertEqual(task["state"], "HELD")
        self.assertEqual(task["consumed_revisions"], {"one": 1})
        labels = self.module.load_agent_record("peer-two")["labels"]
        with self.assertRaises(workflow.WorkflowError):
            tasks.require_peer_current(lease, labels)
        with self.assertRaises(workflow.WorkflowError):
            self.accept("two")
        with self.assertRaises(workflow.WorkflowError):
            tasks.verify_complete(lease)
        self.call_task("settle_work_task", taskId="two", decision="CANCELLED", evidence="Writer stopped; stale result discarded", writersQuiescent=True)
        self.call_task("reopen_work_task", taskId="two", evidence="Fresh attempt after changed prerequisite")
        self.assertEqual(tasks.epoch_state(self.read_lease())["tasks"]["two"]["revision"], 2)

    def test_acceptance_requires_executor_check_receipt_and_quiescence(self):
        self.define("one", checks=["verify"])
        self.dispatch("one")
        self.agent_status = "running"
        with self.assertRaisesRegex(workflow.WorkflowError, "Quiesce"):
            self.accept("one")
        self.agent_status = "idle"
        with self.assertRaisesRegex(workflow.WorkflowError, "receipt"):
            self.accept("one")
        candidate = workflow.snapshot(self.repo)["digest"]
        checked = self.call_task("run_work_check", taskId="one", recipeId="verify", candidateDigest=candidate)
        receipt = checked["receipt"]
        self.assertEqual(receipt["state"], "PASSED")
        self.assertEqual(receipt["candidate_before"], receipt["candidate_after"])
        self.assertEqual(receipt["exit_code"], 0)
        self.assertEqual(receipt["output"], "verified\n")
        self.accept("one")
        tasks.verify_complete(self.read_lease())

    def test_check_candidate_mutation_cannot_be_used_as_passing_proof(self):
        self.recipe["argv"] = [sys.executable, "-c", "from pathlib import Path; Path('code.txt').write_text('changed')"]
        policy = workflow.default_policy(); policy["checks"] = {"verify": self.recipe}
        self.policy_path.write_text(json.dumps(policy))
        self.define("one", checks=["verify"])
        self.dispatch("one")
        checked = self.call_task("run_work_check", taskId="one", recipeId="verify", candidateDigest=workflow.snapshot(self.repo)["digest"])
        self.assertEqual(checked["receipt"]["state"], "FAILED")
        self.assertNotEqual(checked["receipt"]["candidate_before"], checked["receipt"]["candidate_after"])
        with self.assertRaises(workflow.WorkflowError):
            self.accept("one")

    def test_authority_revision_change_during_check_marks_receipt_stale(self):
        self.define("one", checks=["verify"])
        self.dispatch("one")
        original = tasks.execute_check
        def changed(root, recipe, on_start=None):
            lease = self.read_lease(); lease["revision"] += 1; self.write_lease(lease)
            return original(root, recipe, on_start)
        with patch.object(tasks, "execute_check", side_effect=changed):
            result = self.call_task("run_work_check", taskId="one", recipeId="verify", candidateDigest=workflow.snapshot(self.repo)["digest"])
        self.assertEqual(result["receipt"]["state"], "STALE")

    def test_scope_rejects_traversal_globs_git_and_symlinks(self):
        (self.repo / "alias").symlink_to(self.root)
        for raw in ["../outside", "src/*", ".git", "alias/file", "/absolute", "src//file"]:
            with self.subTest(raw=raw), self.assertRaises(workflow.WorkflowError):
                tasks.normalize_scope(self.repo, [raw], True)

    def test_executor_timeout_and_output_cap_are_bounded(self):
        timed = tasks.execute_check(self.repo, {**self.recipe, "timeoutSeconds": 1,
                                              "argv": [sys.executable, "-c", "import time; time.sleep(5)"]})
        self.assertTrue(timed["timed_out"])
        self.assertFalse(timed["output_hash_complete"])
        flooded = tasks.execute_check(self.repo, {**self.recipe, "argv": [sys.executable, "-c", "print('x'*100000)"]})
        self.assertTrue(flooded["output_limit_exceeded"])
        self.assertLessEqual(len(flooded["output"]), 1024)

    def test_task_inspection_through_dispatch_does_not_rewrite_registry(self):
        self.define("one")
        before = self.module.LEASES_PATH.read_bytes()
        result = self.module.call_tool(fixtures.LEAD_ID, "lead", 1, {"name": "inspect_work_tasks", "arguments": {}})
        self.assertFalse(result["result"].get("isError"))
        self.assertEqual(before, self.module.LEASES_PATH.read_bytes())

    def test_interrupted_executor_blocks_settlement_and_owner_resolution_never_passes(self):
        self.define("one")
        self.dispatch("one")
        lease = self.read_lease()
        tasks.epoch_state(lease)["checks"]["interrupted"] = {"state": "RUNNING", "task_id": "one"}
        self.write_lease(lease)
        with self.assertRaisesRegex(workflow.WorkflowError, "interrupted"):
            self.accept("one")
        args = {"leadAgentId": fixtures.LEAD_ID, "runId": "interrupted", "evidence": "Owner inspected processes; command never started",
                "writersQuiescent": True, "expectedWorkEpoch": 1, "expectedRevision": lease["revision"]}
        before = self.module.LEASES_PATH.read_bytes()
        self.module.resolve_work_check(args)
        self.assertEqual(before, self.module.LEASES_PATH.read_bytes())
        self.module.resolve_work_check(args, apply=True)
        self.assertEqual(tasks.epoch_state(self.read_lease())["checks"]["interrupted"]["state"], "INTERRUPTED")

    def test_native_preview_then_proxy_admission_reserves_once_and_binds_live_peer(self):
        self.define("one")
        preferences = self.root / "preferences.json"
        preferences.write_text(json.dumps({"providers": {"planning": "codex-lead/gpt-6.1-sol", "impl_deep": "codex-peer/gpt-6.1-sol"}}))
        env = {**os.environ, "PASEO_AGENT_ID": fixtures.LEAD_ID, "PASEO_ROOM_ROLE": "lead",
               "ROOM_GUARD_AGENTS_DIR": str(self.module.AGENTS_ROOT), "ROOM_GUARD_LEASES_PATH": str(self.module.LEASES_PATH),
               "ROOM_GUARD_PREFERENCES": str(preferences), "ROOM_GUARD_WORKSPACES_PATH": str(self.module.WORKSPACES_PATH)}
        env["ROOM_GUARD_AUDIT_PATH"] = str(self.root / "guard-audit.jsonl")
        guard = ROOT / "hooks/room-role-guard.py"
        hook = {"hook_event_name": "PreToolUse", "tool_name": "mcp__paseo__create_agent", "tool_use_id": "native-call",
                "tool_input": {"provider": "codex-peer/gpt-6.1-sol", "initialPrompt": "Bounded work",
                               "labels": {"route": "impl_deep", "task_id": "one", "task_revision": "1"},
                               "settings": {"thinkingOptionId": "max"}}}
        preview = subprocess.run([sys.executable, str(guard), "--role", "lead"], input=json.dumps(hook), env=env, text=True, capture_output=True, check=True)
        self.assertIn("updatedInput", json.loads(preview.stdout)["hookSpecificOutput"], preview.stdout)
        normalized = json.loads(preview.stdout)["hookSpecificOutput"]["updatedInput"]
        self.assertEqual(tasks.epoch_state(self.read_lease())["tasks"]["one"]["state"], "PLANNED")
        self.assertEqual(normalized["settings"]["thinkingOptionId"], "max")
        self.module.GUARD = guard
        with patch.dict(os.environ, env):
            allowed, reason, normalized = self.module.run_guard("lead", "PreToolUse", fixtures.LEAD_ID, "create_agent", normalized, "proxy-call")
        self.assertTrue(allowed, reason)
        self.assertEqual(normalized["initialPrompt"].count("Peer report correlation (preserve exactly):"), 1)
        self.assertEqual(tasks.epoch_state(self.read_lease())["tasks"]["one"]["state"], "RESERVED")
        labels = {**normalized["labels"], "paseo.parent-agent-id": fixtures.LEAD_ID}
        self.write_agent({"id": fixtures.PEER_ID, "workspaceId": fixtures.WORKSPACE_ID, "labels": labels})
        with patch.dict(os.environ, env):
            allowed, reason, _ = self.module.run_guard("lead", "PostToolUse", fixtures.LEAD_ID, "create_agent", normalized,
                                                     "proxy-call", {"agentId": fixtures.PEER_ID})
        self.assertTrue(allowed, reason)
        self.assertEqual(tasks.epoch_state(self.read_lease())["tasks"]["one"]["state"], "RUNNING")


if __name__ == "__main__":
    unittest.main()
