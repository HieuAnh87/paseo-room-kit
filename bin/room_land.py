"""Optional owner-shell fast-forward of an already accepted room candidate.

The lease remains the sole lifecycle authority. A land plan is a disposable,
read-only preview, not another registry or an implicit consequence of ACCEPTED.
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import pathlib
import re
import subprocess
from typing import Any

import room_workflow as workflow


def git(root: pathlib.Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    # Owner shells sometimes inherit Git worktree/index overrides from tooling.
    # Those must not redirect a land check or mutation to another repository.
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment["LC_ALL"] = "C"
    result = subprocess.run(["git", "--no-optional-locks", "-C", str(root), *args],
                            capture_output=True, env=environment)
    if check and result.returncode:
        raise workflow.WorkflowError(f"Land Git check failed: {' '.join(args)}: {result.stderr.decode(errors='replace').strip()}")
    return result


def git_text(root: pathlib.Path, *args: str) -> str:
    return git(root, *args).stdout.decode().strip()


def repository(root: pathlib.Path) -> pathlib.Path:
    root = root.resolve(strict=True)
    if not root.is_dir() or pathlib.Path(git_text(root, "rev-parse", "--show-toplevel")).resolve() != root:
        raise workflow.WorkflowError("Land requires an exact Git worktree root")
    return root


def common_dir(root: pathlib.Path) -> pathlib.Path:
    value = pathlib.Path(git_text(root, "rev-parse", "--git-common-dir"))
    return (root / value).resolve() if not value.is_absolute() else value.resolve()


def branch_ref(root: pathlib.Path) -> str:
    ref = git_text(root, "symbolic-ref", "--quiet", "HEAD")
    if not ref.startswith("refs/heads/"):
        raise workflow.WorkflowError("Land source and checked-out target require local branches")
    return ref


def clean(root: pathlib.Path) -> None:
    if git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout:
        raise workflow.WorkflowError(f"Land requires a clean worktree and index: {root}")


def worktrees(root: pathlib.Path) -> dict[str, pathlib.Path]:
    result: dict[str, pathlib.Path] = {}
    path: pathlib.Path | None = None
    for line in git(root, "worktree", "list", "--porcelain").stdout.decode().splitlines():
        if line.startswith("worktree "):
            path = pathlib.Path(line[9:]).resolve()
        elif line.startswith("branch ") and path is not None:
            ref = line[7:]
            if ref in result:
                raise workflow.WorkflowError("A local branch is checked out in multiple worktrees")
            result[ref] = path
    return result


@contextlib.contextmanager
def lease_registry(proxy: Any, *, exclusive: bool):
    # Use the proxy's existing lock, but do not invoke locked_leases: it writes
    # the registry on exit, including for a read-only prepare.
    path = proxy.LEASES_PATH
    lock_path = path.with_suffix(path.suffix + ".lock")
    try:
        with lock_path.open("r") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
            try:
                value = json.loads(path.read_text())
                if not isinstance(value, dict) or value.get("version") != 2 or not isinstance(value.get("leases"), dict):
                    raise workflow.WorkflowError("Managed lease registry is invalid")
                for workspace_id, lease in value["leases"].items():
                    proxy.validate_lease_entry(workspace_id, lease)
                yield value
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    except (FileNotFoundError, OSError, json.JSONDecodeError) as error:
        raise workflow.WorkflowError("Managed lease registry or its lock is unreadable") from error


def active_lease(registry: dict[str, Any], lead_id: str) -> dict[str, Any]:
    matches = [lease for lease in registry["leases"].values()
               if lease.get("state") == "active" and lease.get("lead_agent_id") == lead_id
               and lease.get("room_kind") == "managed_slp"]
    if len(matches) != 1:
        raise workflow.WorkflowError("Land requires one active managed Lead lease")
    return matches[0]


def accepted_context(proxy: Any, registry: dict[str, Any], lead_id: str) -> tuple[dict[str, Any], pathlib.Path, dict[str, bool], str]:
    lease = active_lease(registry, lead_id)
    state, lead = proxy.agent_record_status(lead_id)
    if state != "active" or not isinstance(lead, dict) or not workflow.lead_matches(lease, lead):
        raise workflow.WorkflowError("Lead authority record is missing or drifted")
    if proxy.workspace_lifecycle(lease.get("workspace_id")) != "active":
        raise workflow.WorkflowError("Workspace authority is inactive or unreadable")
    epoch, revision = lease.get("work_epoch"), lease.get("revision")
    evidence = lease.get("evidence_digest")
    if (type(epoch) is not int or epoch < 1 or type(revision) is not int or revision < 1
            or not isinstance(evidence, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", evidence)
            or lease.get("decision_state") != "HANDBACK_READY" or lease.get("handback_epoch") != epoch
            or lease.get("human_decision") != "ACCEPTED" or lease.get("human_decision_epoch") != epoch
            or lease.get("human_decision_evidence_digest") != evidence):
        raise workflow.WorkflowError("Land requires a current digest-bound Human ACCEPTED decision")
    root, _policy, gate = workflow.verify_context(lease, lead)
    if root is None or not gate["candidate"]:
        raise workflow.WorkflowError("Land requires a repository policy with candidate proof")
    root = repository(root)
    snapshot = workflow.snapshot(root)
    candidate = snapshot["digest"]
    if lease.get("candidate_digest") != candidate or not isinstance(snapshot["head"], str):
        raise workflow.WorkflowError("Accepted candidate changed")
    reviews = lease.get("candidate_reviews", {})
    if gate["independent_review"]:
        if not isinstance(reviews, dict):
            raise workflow.WorkflowError("Candidate review evidence is invalid")
        relevant = [item for item in reviews.values() if isinstance(item, dict)
                    and item.get("candidate_digest") == candidate and item.get("work_epoch") == epoch]
        if not any(item.get("verdict") == "APPROVE" for item in relevant) or any(
                item.get("verdict") == "FINDINGS" for item in relevant):
            raise workflow.WorkflowError("Accepted candidate lacks a clean independent review")
    return lease, root, gate, snapshot["head"]


def idle_room_agents(proxy: Any, workspace_id: str) -> list[str]:
    identities = []
    for path in sorted(proxy.AGENTS_ROOT.glob("*/*.json")):
        if path.is_symlink():
            raise workflow.WorkflowError("Agent inventory contains a symlink; writer status is uncertain")
        try:
            record = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as error:
            raise workflow.WorkflowError("Agent inventory is unreadable; writer status is uncertain") from error
        if (not isinstance(record, dict) or not isinstance(record.get("id"), str)
                or not proxy.AGENT_ID_PATTERN.fullmatch(record["id"])):
            raise workflow.WorkflowError("Agent inventory is invalid; writer status is uncertain")
        labels = record.get("labels")
        if (record.get("workspaceId") != workspace_id or record.get("archivedAt")
                or not isinstance(labels, dict) or labels.get("role") not in {"lead", "peer"}):
            continue
        identity = record["id"]
        response = proxy.upstream_tool_call("human", "room-land-status", "get_agent_status", {"agentId": identity})
        status = proxy.structured_content(response)
        snapshot = status.get("snapshot") if isinstance(status, dict) else None
        pending = snapshot.get("pendingPermissions") if isinstance(snapshot, dict) else None
        if not isinstance(status, dict) or status.get("status") not in {"idle", "closed"} or pending != []:
            raise workflow.WorkflowError(f"Agent {identity} is active, blocked, or unreadable; pause writers before land")
        identities.append(identity)
    if not identities:
        raise workflow.WorkflowError("No readable room agents for accepted Lead")
    return sorted(identities)


def other_room_writers(proxy: Any, registry: dict[str, Any], current: dict[str, Any], git_dir: pathlib.Path) -> None:
    for lease in registry["leases"].values():
        if lease is current or lease.get("state") not in {"active", "pending"}:
            continue
        raw = lease.get("repository")
        if not isinstance(raw, str):
            other_id = lease.get("lead_agent_id")
            other = proxy.load_agent_record(other_id) if isinstance(other_id, str) else None
            raw = other.get("cwd") if isinstance(other, dict) else None
        if not isinstance(raw, str) or not pathlib.Path(raw).is_dir():
            raise workflow.WorkflowError("Another managed room has unreadable repository placement")
        if common_dir(repository(pathlib.Path(raw))) == git_dir:
            raise workflow.WorkflowError("Another managed room holds a worktree in this Git repository")


def prepare_unlocked(proxy: Any, registry: dict[str, Any], lead_id: str, target_branch: str,
                     target_worktree: pathlib.Path | None) -> dict[str, Any]:
    lease, source, gate, candidate_head = accepted_context(proxy, registry, lead_id)
    clean(source)
    source_ref = branch_ref(source)
    source_sha = git_text(source, "rev-parse", "--verify", "HEAD^{commit}")
    if source_sha != candidate_head or git_text(source, "rev-parse", source_ref) != source_sha:
        raise workflow.WorkflowError("Source branch moved after accepted candidate inspection")
    if not target_branch or git(source, "check-ref-format", "--branch", target_branch, check=False).returncode:
        raise workflow.WorkflowError("Target must be a valid local branch name")
    target_ref = "refs/heads/" + target_branch
    if source_ref == target_ref:
        raise workflow.WorkflowError("Source and target branches must differ")
    target_sha = git_text(source, "rev-parse", "--verify", target_ref + "^{commit}")
    if source_sha == target_sha or git(source, "merge-base", "--is-ancestor", target_sha, source_sha, check=False).returncode:
        raise workflow.WorkflowError("Target is already current or source is not a fast-forward descendant")
    checked_out = worktrees(source).get(target_ref)
    target_path = repository(target_worktree) if target_worktree is not None else None
    if checked_out is None and target_path is not None:
        raise workflow.WorkflowError("Target branch is not checked out at the supplied worktree")
    if checked_out is not None and target_path != checked_out:
        raise workflow.WorkflowError("Target branch is checked out; pass its exact clean --target-worktree")
    if target_path is not None:
        if common_dir(target_path) != common_dir(source) or branch_ref(target_path) != target_ref:
            raise workflow.WorkflowError("Target worktree or branch differs from the source Git repository")
        clean(target_path)
        if git_text(target_path, "rev-parse", "HEAD") != target_sha:
            raise workflow.WorkflowError("Target worktree HEAD differs from branch ref")
    git_dir = common_dir(source)
    other_room_writers(proxy, registry, lease, git_dir)
    idle_agents = idle_room_agents(proxy, lease["workspace_id"])
    plan = {
        "version": 1,
        "leadId": lead_id,
        "workspaceId": lease["workspace_id"],
        "sourceWorktree": str(source),
        "sourceBranch": source_ref,
        "sourceSha": source_sha,
        "targetBranch": target_ref,
        "targetSha": target_sha,
        "targetWorktree": str(target_path) if target_path is not None else None,
        "workEpoch": lease["work_epoch"],
        "revision": lease["revision"],
        "evidenceDigest": lease["evidence_digest"],
        "candidateDigest": lease["candidate_digest"],
        "workflowDigest": lease.get("workflow_digest"),
        "taskClass": lease.get("task_class"),
        "independentReviewRequired": gate["independent_review"],
        "reviewProofDigest": workflow.digest(lease.get("candidate_reviews", {})),
        "idleAgents": idle_agents,
        "commitsAhead": int(git_text(source, "rev-list", "--count", target_sha + ".." + source_sha)),
        "diffStat": git_text(source, "diff", "--stat", target_sha, source_sha),
        "machineGateProof": "not-recorded-by-room-workflow",
    }
    return {**plan, "planDigest": workflow.digest(plan)}


def prepare(proxy: Any, lead_id: str, target_branch: str,
            target_worktree: pathlib.Path | None = None) -> dict[str, Any]:
    with lease_registry(proxy, exclusive=False) as registry:
        return prepare_unlocked(proxy, registry, lead_id, target_branch, target_worktree)


def apply(proxy: Any, proposed: dict[str, Any], approval_digest: str) -> dict[str, Any]:
    if not isinstance(proposed, dict) or not isinstance(approval_digest, str):
        raise workflow.WorkflowError("Land requires a JSON plan and exact Human-approved plan digest")
    expected = proposed.get("planDigest")
    if not isinstance(expected, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", expected) or expected != approval_digest:
        raise workflow.WorkflowError("Human approval does not match the land plan digest")
    lead_id, target_ref = proposed.get("leadId"), proposed.get("targetBranch")
    if not isinstance(lead_id, str) or not isinstance(target_ref, str) or not target_ref.startswith("refs/heads/"):
        raise workflow.WorkflowError("Land plan identity is invalid")
    raw_target = proposed.get("targetWorktree")
    if raw_target is not None and not isinstance(raw_target, str):
        raise workflow.WorkflowError("Land target worktree is invalid")
    with lease_registry(proxy, exclusive=True) as registry:
        current = prepare_unlocked(proxy, registry, lead_id, target_ref[len("refs/heads/"):],
                                   pathlib.Path(raw_target) if raw_target is not None else None)
        if proposed != current or current["planDigest"] != approval_digest:
            raise workflow.WorkflowError("Land plan drifted; prepare and approve a new exact plan")
        source = pathlib.Path(current["sourceWorktree"])
        target = pathlib.Path(raw_target) if raw_target is not None else None
        if target is not None:
            git(target, "merge", "--ff-only", "--no-edit", current["sourceSha"])
            if git_text(target, "rev-parse", "HEAD") != current["sourceSha"]:
                raise workflow.WorkflowError("Target branch did not reach the approved source commit")
        else:
            git(source, "update-ref", current["targetBranch"], current["sourceSha"], current["targetSha"])
        return {"applied": True, "planDigest": approval_digest, "targetBranch": current["targetBranch"],
                "oldSha": current["targetSha"], "newSha": current["sourceSha"]}
