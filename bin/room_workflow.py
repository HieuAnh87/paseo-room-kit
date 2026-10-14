"""Provider-independent workflow, authority and evidence contracts.

This module owns no runtime registry. Callers supply Paseo records and the
existing lease; provider adapters remain responsible for loading instructions.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import stat
import subprocess
from typing import Any


class WorkflowError(ValueError):
    pass


def callback_sending(lease: dict[str, Any]) -> bool:
    return any(item.get("state") == "SENDING"
               for item in lease.get("callback_deliveries", {}).values())


def require_callback_idle(lease: dict[str, Any]) -> None:
    if callback_sending(lease):
        raise WorkflowError("Callback send is in flight; reconcile its receipt before changing this lease")


def protect_callback_fences(before: dict[str, Any], after: dict[str, Any],
                            callback_write: tuple[str, str] | None = None) -> None:
    """Both registry writers enforce the same per-lease transport reservation.

    Network I/O holds no registry lock. Only the callback owner may finish its
    reserved receipt; all other changes to that lease must wait. Other leases
    remain writable. A crashed sender is reconciled under its process lock.
    """
    for workspace, old in before.items():
        new = after.get(workspace)
        if old == new:
            continue
        if callback_write is None or callback_write[0] != workspace or not isinstance(new, dict):
            raise WorkflowError("Callback send fences this lease; mutation was not committed")
        key = callback_write[1]
        old_receipts, new_receipts = old.get("callback_deliveries", {}), new.get("callback_deliveries", {})
        if (key not in old_receipts or key not in new_receipts
                or old_receipts[key].get("state") != "SENDING"
                or {k: v for k, v in old.items() if k not in {"revision", "callback_deliveries"}}
                   != {k: v for k, v in new.items() if k not in {"revision", "callback_deliveries"}}
                or {k: v for k, v in old_receipts.items() if k != key}
                   != {k: v for k, v in new_receipts.items() if k != key}
                or old_receipts[key].get("payload") != new_receipts[key].get("payload")):
            raise WorkflowError("Callback completion cannot change authority or another receipt")


def digest(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(data.encode()).hexdigest()


def default_policy() -> dict[str, Any]:
    return {
        "version": 1,
        "task_classes": {
            "read_only": {"candidate": False, "independent_review": False, "lead_self_work": True},
            "tiny": {"candidate": True, "independent_review": False, "lead_self_work": True},
            "bounded": {"candidate": True, "independent_review": False, "lead_self_work": False},
            "sensitive": {"candidate": True, "independent_review": True, "lead_self_work": False},
            "foundation": {"candidate": True, "independent_review": True, "lead_self_work": False},
        },
    }


def repository_for(record: dict[str, Any], lease: dict[str, Any] | None = None) -> pathlib.Path | None:
    raw = record.get("cwd")
    bound = lease.get("repository") if lease else None
    if bound:
        if raw and pathlib.Path(raw).resolve() != pathlib.Path(bound).resolve():
            raise WorkflowError("Lead repository placement drifted from its authority binding")
        raw = bound
    if not raw:
        return None
    if not isinstance(raw, str) or not pathlib.Path(raw).is_absolute():
        raise WorkflowError("Paseo must supply an absolute repository cwd")
    root = pathlib.Path(raw).resolve(strict=True)
    if not root.is_dir():
        raise WorkflowError("Repository placement is not a directory")
    return root


def load_policy(root: pathlib.Path | None) -> dict[str, Any] | None:
    if root is None:
        return None
    path = root / ".orchestration/workflow.json"
    if path.parent.is_symlink():
        raise WorkflowError("Orchestration directory must not be a symlink")
    if not path.exists():
        if path.is_symlink():
            raise WorkflowError("Broken workflow policy symlink")
        return None
    if path.is_symlink() or not path.is_file():
        raise WorkflowError("Workflow policy must be a regular file")
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, ValueError) as error:
        raise WorkflowError("Workflow policy is unreadable") from error
    if not isinstance(value, dict) or not {"version", "task_classes"}.issubset(value) or set(value) - {"version", "task_classes", "checks"} or type(value["version"]) is not int or value["version"] != 1:
        raise WorkflowError("Workflow policy requires version=1 and task_classes")
    classes = value["task_classes"]
    if "checks" in value:
        from room_tasks import validate_recipes
        validate_recipes(value["checks"])
    if not isinstance(classes, dict) or not classes:
        raise WorkflowError("Workflow task_classes must be a nonempty object")
    for name, gate in classes.items():
        if not isinstance(name, str) or not name or not isinstance(gate, dict):
            raise WorkflowError("Invalid workflow task class")
        if set(gate) != {"candidate", "independent_review", "lead_self_work"} or any(type(flag) is not bool for flag in gate.values()):
            raise WorkflowError("Task class requires three explicit boolean gates")
        if gate["independent_review"] and not gate["candidate"]:
            raise WorkflowError("Independent review requires a stable candidate")
    protocol = root / ".orchestration/workspace-protocol.md"
    if protocol.is_symlink() or not protocol.is_file():
        raise WorkflowError("Workflow policy requires a regular workspace-protocol.md")
    return {
        "policy": value,
        "digest": digest({"policy": hashlib.sha256(raw).hexdigest(), "protocol": hashlib.sha256(protocol.read_bytes()).hexdigest()}),
        "protocol_path": str(protocol),
    }


def task_gate(policy: dict[str, Any] | None, task_class: str) -> dict[str, bool]:
    if policy is None:
        return {"candidate": False, "independent_review": False, "lead_self_work": False}
    gate = policy["policy"]["task_classes"].get(task_class)
    if gate is None:
        raise WorkflowError(f"Task class {task_class!r} is not in this repository's protocol")
    return gate


def governance_id(lease: dict[str, Any]) -> str | None:
    # supervisor_agent_id is retained for v2 compatibility, not inferred authority.
    value = lease.get("supervisor_agent_id")
    return value if isinstance(value, str) and value else None


def governs(lease: dict[str, Any], actor: str, role: str) -> bool:
    return role == "human" or (role == "supervisor" and governance_id(lease) == actor)


def lead_matches(lease: dict[str, Any], lead: dict[str, Any]) -> bool:
    labels = lead.get("labels", {})
    if not isinstance(labels, dict):
        return False
    if lead.get("id") != lease.get("lead_agent_id") or lead.get("workspaceId") != lease.get("workspace_id"):
        return False
    if lead.get("archivedAt") or labels.get("role") != "lead":
        return False
    mode = lease.get("authority_mode", "parented")
    parent = labels.get("paseo.parent-agent-id")
    if mode == "parented":
        return parent == governance_id(lease)
    if mode in {"direct", "observed"}:
        return not parent and (mode != "direct" or governance_id(lease) is None)
    return False


RUNTIME_BINDING_VERSION = 2
RUNTIME_FIELDS = ("provider", "model", "thinkingOptionId", "modeId")


def legacy_runtime_binding(record: dict[str, Any]) -> dict[str, Any]:
    """Exact v1 extractor, retained only for the current legacy epoch."""
    return {key: record.get(key) for key in (*RUNTIME_FIELDS, "settings")}


def runtime_binding(record: dict[str, Any]) -> dict[str, Any]:
    """Normalize native persisted config and effective runtime without guessing.

    Config and runtime may be absent during startup, but conflicting nonempty
    values are never silently preferred. Opaque settings are hashed so a pin
    does not copy provider credentials into the authority registry.
    """
    containers = [record]
    for key in ("config", "settings", "runtimeInfo"):
        value = record.get(key)
        if value is not None and not isinstance(value, dict):
            raise WorkflowError(f"Lead runtime {key} must be an object")
        if isinstance(value, dict):
            containers.append(value)
    binding = {}
    for field in RUNTIME_FIELDS:
        values = [item[field] for item in containers if item.get(field) is not None]
        if not values or any(not isinstance(value, str) or not value.strip() for value in values):
            raise WorkflowError(f"Lead runtime {field} is missing or invalid; refusing an empty pin")
        if len(set(values)) != 1:
            raise WorkflowError(f"Lead configured/effective runtime {field} conflicts; checkpoint required")
        binding[field] = values[0]
    settings = {}
    for key in ("config", "settings"):
        value = record.get(key)
        if isinstance(value, dict):
            extra = {name: item for name, item in value.items() if name not in RUNTIME_FIELDS}
            if extra:
                settings[key] = extra
    # Native records expose a feature array; retain only stable feature IDs and
    # values, not labels, descriptions or other UI metadata.
    features = record.get("features")
    if isinstance(features, list):
        feature_values = {}
        for item in features:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str) or "value" not in item or item["id"] in feature_values:
                raise WorkflowError("Lead feature settings are invalid or ambiguous")
            feature_values[item["id"]] = item["value"]
        if feature_values:
            settings["features"] = feature_values
    elif features is not None:
        raise WorkflowError("Lead native features must be an array")
    binding["settings"] = {"digest": digest(settings)}
    return binding


def binding_version(lease: dict[str, Any]) -> int:
    version = lease.get("runtime_binding_version", 1)
    if type(version) is not int or version not in {1, RUNTIME_BINDING_VERSION}:
        raise WorkflowError("Unsupported runtime binding version; checkpoint required")
    return version


def require_current_binding(lease: dict[str, Any]) -> None:
    if binding_version(lease) != RUNTIME_BINDING_VERSION:
        raise WorkflowError("Legacy runtime binding is unverified; Human checkpoint rebind required before a new epoch")


def verify_context(lease: dict[str, Any], lead: dict[str, Any], *, pin: bool = False, callback_service: bool = False) -> tuple[pathlib.Path | None, dict[str, Any] | None, dict[str, bool]]:
    if not callback_service:
        require_callback_idle(lease)
    if not lead_matches(lease, lead):
        raise WorkflowError("Lead identity, placement or parentage differs from its authority binding")
    root = repository_for(lead, lease)
    policy = load_policy(root)
    current = policy["digest"] if policy else None
    if "workflow_digest" in lease and lease["workflow_digest"] != current:
        raise WorkflowError("Repository protocol changed; checkpoint and explicitly replace the binding")
    version = binding_version(lease)
    runtime = runtime_binding(lead) if version == RUNTIME_BINDING_VERSION else legacy_runtime_binding(lead)
    if "runtime_binding" in lease and lease["runtime_binding"] != runtime:
        raise WorkflowError("Lead provider/model/settings drifted; an explicit replacement is required")
    task_class = lease.get("task_class", "bounded")
    gate = task_gate(policy, task_class)
    if pin:
        lease.setdefault("workflow_digest", current)
        # Preserve the old first-pin behavior for unpinned legacy leases, but
        # never upgrade their extractor/version or replace an existing null pin.
        lease.setdefault("runtime_binding", runtime)
        if root:
            lease.setdefault("repository", str(root))
        lease.setdefault("task_class", task_class)
    return root, policy, gate


def snapshot(root: pathlib.Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    def git(*args: str) -> bytes:
        try:
            return subprocess.run(["git", "--no-optional-locks", "-C", str(root), *args], check=True, capture_output=True).stdout
        except subprocess.CalledProcessError as error:
            raise WorkflowError("Candidate requires a readable Git repository") from error
    if pathlib.Path(os.fsdecode(git("rev-parse", "--show-toplevel").rstrip(b"\n"))).resolve() != root:
        raise WorkflowError("Candidate requires the repository root")
    head_probe = subprocess.run(["git", "--no-optional-locks", "-C", str(root), "rev-parse", "--verify", "--quiet", "HEAD"], capture_output=True)
    if head_probe.returncode not in {0, 1}:
        raise WorkflowError("Candidate HEAD is unreadable")
    head = os.fsdecode(head_probe.stdout.strip()) if head_probe.returncode == 0 else None
    names = set(git("ls-files", "-z", "--cached", "--others", "--exclude-standard").split(b"\0")) - {b""}
    index = git("ls-files", "-z", "--stage")
    if any(line.startswith(b"160000 ") for line in index.split(b"\0")):
        raise WorkflowError("Submodule candidates require separate evidence; unsupported by this snapshot")
    entries = []
    for encoded in sorted(names):
        name = os.fsdecode(encoded)
        path = root / name
        try:
            info = path.lstat()
        except FileNotFoundError:
            entries.append({"path": name, "deleted": True})
            continue
        if stat.S_ISLNK(info.st_mode):
            data = os.fsencode(os.readlink(path))
            kind = "symlink"
        elif stat.S_ISREG(info.st_mode):
            data = path.read_bytes()
            kind = "file"
        else:
            raise WorkflowError(f"Unsupported candidate entry: {name}")
        entries.append({"path": name, "kind": kind, "mode": stat.S_IMODE(info.st_mode), "sha256": hashlib.sha256(data).hexdigest()})
    payload = {"version": 1, "head": head, "index_sha256": hashlib.sha256(index).hexdigest(), "files": entries}
    return {**payload, "digest": digest(payload)}


def validate_report(report: Any, peer: dict[str, Any], lead: dict[str, Any], epoch: int) -> dict[str, Any]:
    required = {"version", "reportId", "peerAgentId", "parentLeadId", "workspaceId", "workEpoch", "assignmentId", "kind", "payload"}
    if not isinstance(report, dict) or set(report) != required or type(report["version"]) is not int or report["version"] != 1:
        raise WorkflowError("Peer report requires the closed version-1 envelope")
    labels = peer.get("labels", {})
    if not isinstance(labels, dict) or peer.get("archivedAt"):
        raise WorkflowError("Peer report authority is inactive")
    expected = {
        "peerAgentId": peer.get("id"), "parentLeadId": lead.get("id"),
        "workspaceId": peer.get("workspaceId"), "workEpoch": epoch,
        "assignmentId": labels.get("assignment_id"),
    }
    if any(report[key] != value for key, value in expected.items()) or type(report["workEpoch"]) is not int:
        raise WorkflowError("Peer report correlation does not match its assignment")
    if labels.get("role") != "peer" or labels.get("paseo.parent-agent-id") != lead.get("id") or labels.get("work_epoch") != str(epoch) or labels.get("room_kind") != "managed_slp":
        raise WorkflowError("Peer report parentage or epoch authority is invalid")
    if not isinstance(report["reportId"], str) or not report["reportId"].strip() or not expected["assignmentId"]:
        raise WorkflowError("Peer report requires report and assignment identities")
    kind = report["kind"]
    if kind not in {"HANDOFF", "REVIEW", "REOPEN_REQUEST", "DEPENDENCY_REQUEST", "BLOCKED", "PROGRESS"}:
        raise WorkflowError("Unknown Peer report kind")
    payload = report["payload"]
    if not isinstance(payload, dict) or not isinstance(payload.get("evidence"), str) or not payload["evidence"].strip():
        raise WorkflowError("Peer report requires inspectable evidence")
    if kind == "REVIEW":
        if labels.get("disposition") != "reviewer" or labels.get("write_mode") != "read_only" or payload.get("verdict") not in {"APPROVE", "FINDINGS"} or not isinstance(payload.get("candidateDigest"), str):
            raise WorkflowError("Review requires an independent Reviewer assignment, candidate and verdict")
    return report
