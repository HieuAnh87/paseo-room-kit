"""Native record pins, checkpoint migration and unavailable Peer identity."""
from __future__ import annotations

import copy
import json
import os
import pathlib
import subprocess
import sys
import unittest
import uuid
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))
import room_workflow as workflow
import test_proxy_handback as fixtures
import test_workflow as authority


def native_record():
    config = {"model": "gpt-6.1-sol", "thinkingOptionId": "xhigh", "modeId": "full-access"}
    return {"provider": "codex-lead", "config": config,
            "runtimeInfo": {"provider": "codex-lead", **config},
            "features": [{"id": "fast_mode", "value": False, "label": "Fast"}]}


class NativeBindingTest(unittest.TestCase):
    def test_native_fields_are_non_null_and_ui_metadata_is_not_configuration(self):
        record = native_record()
        binding = workflow.runtime_binding(record)
        self.assertEqual(binding["model"], "gpt-6.1-sol")
        self.assertEqual(binding["thinkingOptionId"], "xhigh")
        self.assertEqual(binding["modeId"], "full-access")
        record["features"][0]["label"] = "Translated label"
        self.assertEqual(binding, workflow.runtime_binding(record))

    def test_flat_and_nested_identity_fields_normalize_equally(self):
        config = native_record()["config"]
        expected = workflow.runtime_binding({"provider": "codex-lead", "config": config})
        self.assertEqual(expected, workflow.runtime_binding({"provider": "codex-lead", **config}))
        self.assertEqual(expected, workflow.runtime_binding({"provider": "codex-lead", "settings": config}))

    def test_each_missing_runtime_field_refuses_a_pin(self):
        for field in workflow.RUNTIME_FIELDS:
            with self.subTest(field=field):
                record = native_record()
                record.pop(field, None)
                record["config"].pop(field, None)
                record["runtimeInfo"].pop(field, None)
                with self.assertRaisesRegex(workflow.WorkflowError, "missing"):
                    workflow.runtime_binding(record)

    def test_configured_effective_conflicts_fail_closed(self):
        for field in workflow.RUNTIME_FIELDS:
            with self.subTest(field=field):
                record = native_record()
                record["runtimeInfo"][field] = "changed"
                with self.assertRaisesRegex(workflow.WorkflowError, "conflicts"):
                    workflow.runtime_binding(record)

    def test_settings_and_features_are_pinned_without_copying_secrets(self):
        record = native_record()
        record["config"]["opaque_setting"] = "synthetic-private-value"
        before = workflow.runtime_binding(record)
        self.assertNotIn("synthetic-private-value", json.dumps(before))
        record["config"]["opaque_setting"] = "changed"
        self.assertNotEqual(before, workflow.runtime_binding(record))
        after = workflow.runtime_binding(record)
        record["features"][0]["value"] = True
        self.assertNotEqual(after, workflow.runtime_binding(record))

    def test_invalid_containers_duplicate_features_and_versions_are_rejected(self):
        for update in ({"settings": "invalid"}, {"features": {}},
                       {"features": [{"id": "fast_mode", "value": False}] * 2}):
            with self.subTest(update=update), self.assertRaises(workflow.WorkflowError):
                workflow.runtime_binding(dict(native_record(), **update))
        for version in (0, 3, True, "2", None):
            with self.subTest(version=version), self.assertRaises(workflow.WorkflowError):
                workflow.binding_version({"runtime_binding_version": version})


class CheckpointTest(unittest.TestCase):
    setUp = fixtures.ManagedLifecycleTest.setUp
    tearDown = fixtures.ManagedLifecycleTest.tearDown
    write_agent = fixtures.ManagedLifecycleTest.write_agent
    write_workspace = fixtures.ManagedLifecycleTest.write_workspace
    base_lease = fixtures.ManagedLifecycleTest.base_lease
    write_lease = fixtures.ManagedLifecycleTest.write_lease
    read_lease = fixtures.ManagedLifecycleTest.read_lease
    upstream_call = fixtures.ManagedLifecycleTest.upstream_call
    text = staticmethod(fixtures.ManagedLifecycleTest.text)
    root_binding = authority.WorkflowAuthorityTest.root_binding

    def ready(self, legacy=True):
        self.root_binding()
        self.module.handback_to_parent(fixtures.LEAD_ID, "lead", 1, {"message": "Bounded evidence"})
        lease = self.read_lease()
        if legacy:
            lease.pop("runtime_binding_version")
            lease["runtime_binding"] = workflow.legacy_runtime_binding(self.lead)
            self.write_lease(lease)
        return {"agentId": fixtures.LEAD_ID, "expectedWorkEpoch": 1,
                "expectedRevision": lease["revision"],
                "runtimeBindingDigest": workflow.digest(workflow.runtime_binding(self.lead)),
                "evidence": "Owner independently verified synthetic launch tuple"}

    def test_new_binding_rejects_missing_configuration_without_granting_authority(self):
        self.module.LEASES_PATH.unlink()
        self.lead["labels"].pop("paseo.parent-agent-id")
        self.lead.pop("config")
        self.write_agent(self.lead)
        with self.assertRaisesRegex(workflow.WorkflowError, "missing"):
            self.module.bind_root_lead(fixtures.LEAD_ID, None, "tiny", apply=True)
        self.assertFalse(self.module.LEASES_PATH.exists())
        self.assertEqual(self.calls, [])

    def test_each_nested_drift_refuses_context(self):
        self.root_binding()
        lease = self.read_lease()
        for field in ("model", "thinkingOptionId", "modeId", "settings"):
            lead = copy.deepcopy(self.lead)
            if field == "settings":
                lead["config"]["additional_setting"] = True
            else:
                lead["config"][field] = "changed"
            with self.subTest(field=field), self.assertRaisesRegex(workflow.WorkflowError, "drifted"):
                workflow.verify_context(lease, lead)

    def test_legacy_handback_survives_but_never_silently_upgrades(self):
        self.root_binding()
        lease = self.read_lease()
        lease.pop("runtime_binding_version")
        lease["runtime_binding"] = workflow.legacy_runtime_binding(self.lead)
        self.write_lease(lease)
        result = self.module.handback_to_parent(fixtures.LEAD_ID, "lead", 1, {"message": "Legacy closure"})
        self.assertFalse(result["result"]["isError"], self.text(result))
        ready = self.read_lease()
        self.assertNotIn("runtime_binding_version", ready)
        self.assertEqual(ready["runtime_binding"], lease["runtime_binding"])
        self.assertNotIn("human_decision", ready)
        view = self.module.list_room_attention("human", "human", 2, {"leadAgentId": fixtures.LEAD_ID})
        self.assertEqual(json.loads(self.text(view))["runtime_binding_status"], "LEGACY_UNVERIFIED")

    def test_legacy_unpinned_lease_preserves_v1_first_pin_without_upgrade(self):
        lease = self.base_lease()
        lease.pop("runtime_binding_version")
        workflow.verify_context(lease, self.lead, pin=True)
        self.assertEqual(lease["runtime_binding"], workflow.legacy_runtime_binding(self.lead))
        self.assertNotIn("runtime_binding_version", lease)

    def test_legacy_epoch_cannot_reopen_before_rebind(self):
        request = self.ready()
        before = self.module.LEASES_PATH.read_bytes()
        with self.assertRaisesRegex(workflow.WorkflowError, "Legacy"):
            self.module.reopen_work_epoch("human", "human", 2, {
                "agentId": fixtures.LEAD_ID, "prompt": "Next bounded epoch",
                "expectedWorkEpoch": 1, "expectedRevision": request["expectedRevision"]})
        self.assertEqual(before, self.module.LEASES_PATH.read_bytes())

    def test_checkpoint_rebind_preserves_proof_and_human_decision_boundary(self):
        request = self.ready()
        before = self.module.LEASES_PATH.read_bytes()
        self.assertFalse(self.module.rebind_runtime(request)["applied"])
        self.assertEqual(before, self.module.LEASES_PATH.read_bytes())
        old = self.read_lease()
        result = self.module.rebind_runtime(request, apply=True)
        self.assertTrue(result["applied"])
        changed = self.read_lease()
        self.assertEqual(changed["runtime_binding_version"], 2)
        self.assertEqual(changed["runtime_binding"], workflow.runtime_binding(self.lead))
        self.assertEqual(changed["revision"], old["revision"] + 1)
        for key in ("work_epoch", "evidence_digest", "handback_message", "decision_state"):
            self.assertEqual(changed[key], old[key])
        self.assertNotIn("human_decision", changed)
        result = self.module.reopen_work_epoch("human", "human", 3, {
            "agentId": fixtures.LEAD_ID, "prompt": "Next bounded epoch",
            "expectedWorkEpoch": 1, "expectedRevision": changed["revision"]})
        self.assertFalse(result["result"]["isError"], self.text(result))

    def test_rebind_rejects_actor_stale_digest_and_active_work(self):
        request = self.ready()
        before = self.module.LEASES_PATH.read_bytes()
        for update, role in (({}, "lead"), ({"expectedRevision": 999}, "human"),
                             ({"runtimeBindingDigest": "sha256:wrong"}, "human")):
            with self.subTest(update=update, role=role), self.assertRaises(workflow.WorkflowError):
                self.module.rebind_runtime(dict(request, **update), apply=True, role=role)
            self.assertEqual(before, self.module.LEASES_PATH.read_bytes())
        lease = self.read_lease()
        lease["decision_state"] = "WORKING"
        self.write_lease(lease)
        with self.assertRaisesRegex(workflow.WorkflowError, "checkpoint"):
            self.module.rebind_runtime(request, apply=True)

    def test_rebind_rejects_unarchived_descendant(self):
        request = self.ready()
        self.write_agent({"id": fixtures.PEER_ID, "labels": {"paseo.parent-agent-id": fixtures.LEAD_ID}})
        with self.assertRaisesRegex(workflow.WorkflowError, "descendants"):
            self.module.rebind_runtime(request, apply=True)

    def test_rebind_rejects_busy_lead_running_check_or_unsettled_task(self):
        request = self.ready()
        self.lead["lastStatus"] = "running"
        self.write_agent(self.lead)
        with self.assertRaisesRegex(workflow.WorkflowError, "idle"):
            self.module.rebind_runtime(request, apply=True)
        self.lead["lastStatus"] = "idle"
        self.write_agent(self.lead)
        lease = self.read_lease()
        shelf = {"tasks": {}, "checks": {"run-one": {"state": "RUNNING"}}}
        lease["work_tasks"] = {"version": 1, "epochs": {"1": shelf}}
        self.write_lease(lease)
        with self.assertRaisesRegex(workflow.WorkflowError, "quiescent"):
            self.module.rebind_runtime(request, apply=True)


class ProcessIdentityTest(unittest.TestCase):
    def setUp(self):
        self.proxy = fixtures.load_proxy()
        self.identity = str(uuid.uuid4())

    def test_explicit_identity_validates_without_inspecting_processes(self):
        with patch.dict(os.environ, {"PASEO_AGENT_ID": self.identity}), patch.object(self.proxy.subprocess, "run") as run:
            self.assertEqual(self.proxy.resolve_agent_id(), self.identity)
            run.assert_not_called()
        with patch.dict(os.environ, {"PASEO_AGENT_ID": "not-an-id"}), patch.object(self.proxy.subprocess, "run") as run:
            self.assertEqual(self.proxy.resolve_agent_id(), "")
            run.assert_not_called()

    def test_no_env_or_process_identity_denies_mcp_tools(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(self.proxy.subprocess, "run", side_effect=OSError("unavailable")):
            self.assertEqual(self.proxy.resolve_agent_id(), "")
        catalog = self.proxy.handle("", "lead", {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertEqual(catalog["result"]["tools"], [])
        result = self.proxy.handle("", "lead", {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "inspect_work_context", "arguments": {}}})
        self.assertTrue(result["result"]["isError"])
        self.assertIn("PASEO_AGENT_ID", fixtures.ManagedLifecycleTest.text(result))

    def test_filtered_environment_recovers_same_user_launcher_identity(self):
        # Model the stdio child losing its launcher environment. This tests
        # process recovery, not the causal effect of daemon MCP injection.
        def process(argv, **kwargs):
            value = str(os.getuid()) if argv[-1] == "uid=" else "launcher PASEO_AGENT_ID=" + self.identity
            return subprocess.CompletedProcess(argv, 0, value, "")
        with patch.dict(os.environ, {}, clear=True), patch.object(self.proxy.subprocess, "run", side_effect=process):
            self.assertEqual(self.proxy.resolve_agent_id(), self.identity)

    def test_foreign_user_parent_is_not_inspected_for_identity(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(self.proxy.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, str(os.getuid() + 1), "")) as run:
            self.assertEqual(self.proxy.resolve_agent_id(), "")
            self.assertEqual(run.call_count, 1)


class CallbackIdentityTest(unittest.TestCase):
    setUp = fixtures.ManagedLifecycleTest.setUp
    tearDown = fixtures.ManagedLifecycleTest.tearDown
    write_agent = fixtures.ManagedLifecycleTest.write_agent
    write_workspace = fixtures.ManagedLifecycleTest.write_workspace
    base_lease = fixtures.ManagedLifecycleTest.base_lease
    write_lease = fixtures.ManagedLifecycleTest.write_lease
    read_lease = fixtures.ManagedLifecycleTest.read_lease
    upstream_call = fixtures.ManagedLifecycleTest.upstream_call
    text = staticmethod(fixtures.ManagedLifecycleTest.text)

    def report(self):
        peer = {"id": fixtures.PEER_ID, "workspaceId": fixtures.WORKSPACE_ID,
                "labels": {"role": "peer", "room_kind": "managed_slp", "work_epoch": "1",
                           "assignment_id": "assignment-one", "paseo.parent-agent-id": fixtures.LEAD_ID}}
        self.write_agent(peer)
        lease = self.read_lease()
        lease["peer_briefs"] = {fixtures.PEER_ID: {"assignment_id": "assignment-one", "work_epoch": 1}}
        self.write_lease(lease)
        return {"version": 1, "reportId": "report-one", "peerAgentId": None,
                "parentLeadId": fixtures.LEAD_ID, "workspaceId": fixtures.WORKSPACE_ID,
                "workEpoch": 1, "assignmentId": "assignment-one", "kind": "HANDOFF",
                "payload": {"evidence": "Exact synthetic callback evidence"}}

    def test_null_identity_correlates_only_canonical_assignment_and_deduplicates(self):
        report = self.report()
        first = self.module.record_peer_report(fixtures.LEAD_ID, "lead", 1, {"report": report})
        self.assertFalse(first["result"]["isError"], self.text(first))
        receipt = json.loads(self.text(first))
        self.assertEqual(receipt["report"]["peerAgentId"], fixtures.PEER_ID)
        self.assertEqual(receipt["report"]["assignmentId"], report["assignmentId"])
        self.assertEqual(receipt["identity_correlation"]["method"], "canonical_creation_assignment")
        revision = self.read_lease()["revision"]
        second = self.module.record_peer_report(fixtures.LEAD_ID, "lead", 2, {"report": report})
        self.assertEqual(self.text(first), self.text(second))
        self.assertEqual(self.read_lease()["revision"], revision)
        self.assertIsNone(report["peerAgentId"])

    def test_cross_epoch_assignment_unknown_or_wrong_identity_is_not_repaired(self):
        report = self.report()
        for update in ({"workEpoch": 2}, {"assignmentId": "unknown"}, {"peerAgentId": "unknown-peer"}, {"parentLeadId": "foreign"}):
            before = self.read_lease()
            with self.subTest(update=update):
                result = self.module.record_peer_report(fixtures.LEAD_ID, "lead", 1, {"report": dict(report, **update)})
                self.assertTrue(result["result"]["isError"])
                self.assertEqual(before, self.read_lease())

    def test_ambiguous_or_missing_creation_receipt_needs_lead_decision(self):
        report = self.report()
        second = self.module.load_agent_record(fixtures.PEER_ID)
        second["id"] = "other-peer"
        self.write_agent(second)
        lease = self.read_lease()
        lease["peer_briefs"]["other-peer"] = dict(lease["peer_briefs"][fixtures.PEER_ID])
        self.write_lease(lease)
        result = self.module.record_peer_report(fixtures.LEAD_ID, "lead", 1, {"report": report})
        self.assertTrue(result["result"]["isError"])
        self.assertIn("NEEDS_LEAD_DECISION", self.text(result))
        lease["peer_briefs"] = {}
        self.write_lease(lease)
        result = self.module.record_peer_report(fixtures.LEAD_ID, "lead", 2, {"report": report})
        self.assertTrue(result["result"]["isError"])

    def test_done_text_while_running_is_not_terminal_and_idle_without_outcome_is_unknown(self):
        self.assertIsNone(self.module.peer_terminal_handback({"status": "running"}, {"content": "Task outcome: DONE"}))
        self.assertIsNone(self.module.peer_terminal_handback({"status": "idle"}, {"content": "No outcome"}))
        self.assertEqual(self.module.peer_terminal_handback({"status": "idle"}, {"content": "Task outcome: DONE\nEvidence"})[0], "DONE")


if __name__ == "__main__":
    unittest.main()
