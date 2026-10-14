"""Optional task DAG, logical write reservations and local check receipts.

State lives inside the canonical Lead lease. Call mutations under its lock.
Reservations govern dispatch, not OS filesystem permissions or Human acceptance.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import os
import pathlib
import re
import selectors
import signal
import subprocess
import time
from typing import Any

from room_workflow import WorkflowError, digest

HELD = {"RESERVED", "RUNNING", "HELD"}
STATES = HELD | {"PLANNED", "ACCEPTED", "CANCELLED"}
IDENTITY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")


def identity(value: Any) -> str:
    if not isinstance(value, str) or not IDENTITY.fullmatch(value):
        raise WorkflowError("Task/check identity must be 1-80 simple characters")
    return value


def text(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 8000:
        raise WorkflowError("Task objective/evidence must be nonempty and bounded")
    return value.strip()


def epoch_state(lease: dict, *, create: bool = False) -> dict:
    state = lease.get("work_tasks")
    if state is None:
        if not create:
            return {"tasks": {}, "checks": {}}
        state = lease["work_tasks"] = {"version": 1, "epochs": {}}
    if not isinstance(state, dict) or set(state) != {"version", "epochs"} or state["version"] != 1 or not isinstance(state["epochs"], dict):
        raise WorkflowError("Invalid task ledger; failing closed")
    for key, value in state["epochs"].items():
        if not isinstance(key, str) or not key.isdigit() or not isinstance(value, dict) or set(value) != {"tasks", "checks"} or not all(isinstance(value[k], dict) for k in value):
            raise WorkflowError("Invalid task epoch; failing closed")
        for task_id, task in value["tasks"].items():
            identity(task_id)
            if (not isinstance(task, dict) or task.get("state") not in STATES
                or type(task.get("revision")) is not int or task["revision"] < 1
                or not isinstance(task.get("dependencies"), list)
                or not isinstance(task.get("consumed_revisions"), dict)
                or not isinstance(task.get("scope"), list)
                or type(task.get("write")) is not bool
                or not isinstance(task.get("scope_root"), str)):
                raise WorkflowError("Invalid task record; failing closed")
    key = str(lease["work_epoch"])
    if create:
        return state["epochs"].setdefault(key, {"tasks": {}, "checks": {}})
    return state["epochs"].get(key, {"tasks": {}, "checks": {}})


def scope_root(root: pathlib.Path) -> str:
    result = subprocess.run(["git", "--no-optional-locks", "-C", str(root), "rev-parse", "--git-common-dir"], check=True, capture_output=True, text=True)
    return str((root / result.stdout.strip()).resolve())


def normalize_scope(root: pathlib.Path, paths: Any, write: bool) -> list[str]:
    if not isinstance(paths, list) or len(paths) > 32 or (write and not paths):
        raise WorkflowError("Writer requires 1-32 explicit relative scope paths")
    result = []
    for raw in paths:
        if (not isinstance(raw, str) or not raw or len(raw) > 1000
            or raw.startswith("/") or any(c in raw for c in "\\\x00\n*?[]")
            or raw != "." and any(part in {"", ".", "..", ".git"} for part in raw.split("/"))):
            raise WorkflowError("Scope paths must be normalized literals; directories cover their subtree")
        cursor = root
        for part in raw.split("/"):
            cursor = cursor / part
            if cursor.is_symlink():
                raise WorkflowError("Scope paths cannot traverse symlinks")
        if not cursor.resolve().is_relative_to(root.resolve()):
            raise WorkflowError("Scope escapes repository")
        result.append(raw)
    return sorted(set(result))


def overlaps(left: str, right: str) -> bool:
    return left == "." or right == "." or left == right or left.startswith(right + "/") or right.startswith(left + "/")


def dependencies_ready(tasks: dict, task: dict) -> bool:
    return all(dep in tasks and tasks[dep]["state"] == "ACCEPTED" for dep in task["dependencies"])


def provenance_current(tasks: dict, task: dict) -> bool:
    return dependencies_ready(tasks, task) and task["consumed_revisions"] == {dep: tasks[dep]["revision"] for dep in task["dependencies"]}


def define(lease: dict, root: pathlib.Path, arguments: dict, recipes: dict) -> dict:
    task_id = identity(arguments["taskId"])
    shelf = epoch_state(lease, create=True)
    tasks = shelf["tasks"]
    if task_id in tasks or len(tasks) >= 64:
        raise WorkflowError("Task already exists or epoch task limit (64) reached")
    deps = arguments["dependsOn"]
    if not isinstance(deps, list) or len(deps) > 32 or len(set(map(identity, deps))) != len(deps) or any(dep not in tasks for dep in deps):
        raise WorkflowError("Dependencies must be unique existing tasks in this epoch")
    checks = arguments["requiredChecks"]
    if not isinstance(checks, list) or len(checks) > 32 or len(set(map(identity, checks))) != len(checks) or any(check not in recipes for check in checks):
        raise WorkflowError("Required checks must name unique repository check recipes")
    if type(arguments["write"]) is not bool:
        raise WorkflowError("Task write must be an explicit boolean")
    task = {"task_id": task_id, "objective": text(arguments["objective"]), "revision": 1,
            "state": "PLANNED", "write": arguments["write"],
            "scope": normalize_scope(root, arguments["scope"], arguments["write"]),
            "scope_root": scope_root(root), "dependencies": list(deps),
            "consumed_revisions": {}, "required_checks": list(checks), "attempts": []}
    tasks[task_id] = task
    return task


def reserve(registry: dict, lease: dict, task_id: str, task_revision: str, assignment: str, reservation_id: str, write: bool, root: pathlib.Path) -> dict:
    tasks = epoch_state(lease)["tasks"]
    task = tasks.get(task_id)
    if not task or str(task["revision"]) != task_revision or task["write"] != write:
        raise WorkflowError("Dispatch task/revision/write disposition does not match its definition")
    if task["state"] == "RESERVED" and task.get("reservation_id") == reservation_id:
        if task.get("assignment_id") != assignment:
            raise WorkflowError("Reservation retry changed assignment identity")
        return task
    if task["state"] != "PLANNED" or not dependencies_ready(tasks, task):
        raise WorkflowError("Task is already assigned or its prerequisites are not accepted")
    if normalize_scope(root, task["scope"], task["write"]) != task["scope"] or scope_root(root) != task["scope_root"]:
        raise WorkflowError("Task repository/scope drifted")
    if write:
        for other in registry["leases"].values():
            if other.get("state") != "active":
                continue
            epoch_state(other)  # Validate before traversing historical reservations.
            for shelf in other.get("work_tasks", {}).get("epochs", {}).values():
                for held in shelf["tasks"].values():
                    if (held["write"] and held["state"] in HELD and held["scope_root"] == task["scope_root"]
                        and any(overlaps(a, b) for a in task["scope"] for b in held["scope"])):
                        raise WorkflowError("Write scope overlaps an unsettled task reservation")
    task.update(state="RESERVED", assignment_id=assignment, reservation_id=reservation_id,
                consumed_revisions={dep: tasks[dep]["revision"] for dep in task["dependencies"]})
    return task


def bind_peer(lease: dict, task_id: str, labels: dict, peer_id: str) -> None:
    task = epoch_state(lease)["tasks"].get(task_id)
    if (task and task["state"] == "RUNNING" and task.get("peer_agent_id") == peer_id
        and task.get("assignment_id") == labels.get("assignment_id") and str(task["revision"]) == labels.get("task_revision")):
        return
    if (not task or task["state"] != "RESERVED" or task.get("assignment_id") != labels.get("assignment_id")
        or str(task["revision"]) != labels.get("task_revision")):
        raise WorkflowError("Created Peer does not match its durable task reservation")
    task.update(state="RUNNING", peer_agent_id=peer_id)


def require_peer_current(lease: dict, labels: dict) -> None:
    tasks = epoch_state(lease)["tasks"]
    if not tasks:
        return
    task = tasks.get(labels.get("task_id"))
    if (not task or task["state"] != "RUNNING" or str(task["revision"]) != labels.get("task_revision")
        or task.get("assignment_id") != labels.get("assignment_id") or not provenance_current(tasks, task)):
        raise WorkflowError("Peer task is held, stale or not bound to current prerequisites")


def settle(lease: dict, task_id: str, decision: str, evidence: str, candidate: str | None) -> dict:
    shelf = epoch_state(lease)
    tasks = shelf["tasks"]
    task = tasks.get(identity(task_id))
    if not task or task["state"] not in HELD | {"PLANNED"} or decision not in {"ACCEPTED", "CANCELLED"}:
        raise WorkflowError("Only an unsettled task can be accepted or explicitly cancelled")
    if any(check.get("state") == "RUNNING" for check in shelf["checks"].values()):
        raise WorkflowError("Resolve the running or interrupted executor before settling tasks")
    if decision == "ACCEPTED":
        if task["state"] != "RUNNING" or not candidate or not provenance_current(tasks, task):
            raise WorkflowError("Acceptance requires current assignment, candidate and prerequisite revisions")
        for recipe in task["required_checks"]:
            if not any(check.get("task_id") == task_id and check.get("task_revision") == task["revision"]
                       and check.get("recipe_id") == recipe and check.get("state") == "PASSED"
                       and check.get("candidate_before") == candidate == check.get("candidate_after")
                       for check in shelf["checks"].values()):
                raise WorkflowError("Task requires a passing executor receipt for this exact candidate: " + recipe)
    task.update(state=decision, settlement_evidence=text(evidence), candidate_digest=candidate)
    return task


def reopen(lease: dict, task_id: str, evidence: str) -> dict:
    tasks = epoch_state(lease)["tasks"]
    task = tasks.get(identity(task_id))
    if not task or task["state"] not in {"ACCEPTED", "CANCELLED"}:
        raise WorkflowError("Settle and quiesce the existing attempt before reopening")
    task["attempts"].append({k: task[k] for k in ("revision", "state", "assignment_id", "peer_agent_id", "candidate_digest") if k in task})
    task.update(revision=task["revision"] + 1, state="PLANNED", consumed_revisions={}, reopen_evidence=text(evidence))
    for key in ("assignment_id", "peer_agent_id", "reservation_id", "candidate_digest", "settlement_evidence"):
        task.pop(key, None)
    changed = {task_id}
    while True:
        descendants = {key for key, value in tasks.items() if key not in changed and any(dep in changed for dep in value["dependencies"])}
        if not descendants:
            break
        for key in descendants:
            value = tasks[key]
            if value["state"] in {"RUNNING", "RESERVED", "ACCEPTED"}:
                value.update(state="HELD", hold_reason="Prerequisite reopened: " + task_id)
            # A held reservation remains held until explicit, quiescent cancellation.
        changed.update(descendants)
    return {"task": task, "affected_tasks": sorted(changed - {task_id})}


def verify_complete(lease: dict) -> None:
    shelf = epoch_state(lease)
    tasks = shelf["tasks"]
    if any(check.get("state") == "RUNNING" for check in shelf["checks"].values()):
        raise WorkflowError("Resolve interrupted checks before final handback")
    if any(task["state"] not in {"ACCEPTED", "CANCELLED"} for task in tasks.values()):
        raise WorkflowError("Settle all current-epoch tasks before final handback")


def check_recipes(policy: dict | None) -> dict:
    return policy["policy"].get("checks", {}) if policy else {}


def validate_recipes(recipes: Any) -> None:
    if not isinstance(recipes, dict) or len(recipes) > 32:
        raise WorkflowError("Checks must be a bounded object of repository recipes")
    for name, recipe in recipes.items():
        identity(name)
        if not isinstance(recipe, dict) or set(recipe) != {"argv", "timeoutSeconds", "maxOutputBytes"}:
            raise WorkflowError("Check recipe requires argv, timeoutSeconds and maxOutputBytes")
        argv = recipe["argv"]
        if not isinstance(argv, list) or not 1 <= len(argv) <= 64 or any(not isinstance(arg, str) or not arg or "\x00" in arg or len(arg) > 8000 for arg in argv):
            raise WorkflowError("Check argv must be a bounded nonempty string list")
        if type(recipe["timeoutSeconds"]) is not int or not 1 <= recipe["timeoutSeconds"] <= 300:
            raise WorkflowError("Check timeoutSeconds must be 1-300")
        if type(recipe["maxOutputBytes"]) is not int or not 1024 <= recipe["maxOutputBytes"] <= 1048576:
            raise WorkflowError("Check maxOutputBytes must be 1024-1048576")


def execute_check(root: pathlib.Path, recipe: dict, on_start=None) -> dict:
    """Fixed repository argv, no caller-supplied command or shell interpolation."""
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    start = time.monotonic()
    output = bytearray()
    hashed = hashlib.sha256()
    timed_out = exceeded = False
    process = subprocess.Popen(recipe["argv"], cwd=root, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
    assert process.stdout is not None
    os.set_blocking(process.stdout.fileno(), False)
    total = 0
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        try:
            if on_start is not None:
                on_start(process.pid)
            while selector.get_map():
                if time.monotonic() - start >= recipe["timeoutSeconds"]:
                    timed_out = True
                    break
                for key, _ in selector.select(timeout=min(0.1, recipe["timeoutSeconds"])):
                    data = os.read(key.fileobj.fileno(), 65536)
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    total += len(data)
                    hashed.update(data)
                    output.extend(data[:max(0, recipe["maxOutputBytes"] - len(output))])
                    if total > recipe["maxOutputBytes"]:
                        exceeded = True
                        break
                if exceeded:
                    break
            # A process may close output then continue running.
            if not timed_out and not exceeded:
                try:
                    process.wait(timeout=max(0.001, recipe["timeoutSeconds"] - (time.monotonic() - start)))
                except subprocess.TimeoutExpired:
                    timed_out = True
        finally:
            # Kill the whole check process group, including background descendants.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            process.stdout.close()
    return {"argv": list(recipe["argv"]), "started_at": started,
            "process_group_id": process.pid,
            "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "elapsed_seconds": round(time.monotonic() - start, 3), "exit_code": process.returncode,
            "timed_out": timed_out, "output_limit_exceeded": exceeded,
            "output_bytes_read": total, "output_sha256": hashed.hexdigest(),
            "output_hash_complete": not timed_out and not exceeded,
            "output": output.decode("utf-8", errors="replace"), "limits": dict(recipe)}
