#!/usr/bin/env python3
"""Deterministic role and routing guard for Paseo room agents."""

from __future__ import annotations

import argparse
import ast
import contextlib
import datetime as dt
import fcntl
import json
import os
import pathlib
import re
import sys
import tempfile
import uuid
from collections.abc import Iterator
from typing import Any

module_root = pathlib.Path(__file__).resolve().parents[1] / "bin"
if not (module_root / "room_workflow.py").is_file():
    module_root = pathlib.Path.home() / ".local/bin"
sys.path.insert(0, str(module_root))
import room_workflow as workflow

PARENT_LABEL = "paseo.parent-agent-id"
ROLE_LABEL = "role"
ROUTE_LABEL = "route"
TASK_STATE_LABEL = "task_state"
LEAD_PROFILE_LABEL = "lead_profile"
STACK_PROFILE_LABEL = "stack_profile"
ROOM_KIND_LABEL = "room_kind"
WORK_EPOCH_LABEL = "work_epoch"
MANAGED_ROOM_KIND = "managed_slp"
PENDING_LEASE_SECONDS = 300
CUSTOM_LEAD_PROVIDERS = {"codex-lead", "claude-lead", "opencode-lead"}

PEER_OUTCOMES = {
    "DONE",
    "BLOCKED_PERMISSION",
    "NEEDS_LEAD_DECISION",
    "FAILED",
}

ROUTE_THINKING = {
    "impl": "max",
    "impl_deep": "max",
    "search": "low",
    "research": "max",
    "audit": "max",
}

TARGET_MUTATIONS = {
    "archive_agent",
    "cancel_agent",
    "kill_agent",
    "respond_to_permission",
    "send_agent_prompt",
    "set_agent_mode",
    "update_agent",
}
WORKSPACE_MUTATIONS = {"archive_workspace"}

DIRECT_PASEO_MUTATION_RE = re.compile(
    r"""(?ix)
    (?:^|[;&|(\n]\s*|(?:command|env|exec|sudo)\s+)
    (?:[^\s;&|()]*/)?paseo
    \s+
    (?:
        run
        |send
        |stop
        |archive
        |agent\s+(?:run|send|stop|delete|archive|reload|detach|update|mode)
        |workspace\s+(?:create|archive)
        |schedule\b
        |heartbeat\b
    )
    """
)

ANY_PASEO_COMMAND_RE = re.compile(
    r"""(?ix)
    (?:^|[;&|(\n]\s*|(?:command|env|exec|sudo)\s+)
    (?:[^\s;&|()]*/)?paseo(?:\s|$)
    """
)

EXEC_PASEO_CALL_RE = re.compile(r"\btools\s*\.\s*mcp__paseo__([A-Za-z0-9_]+)\s*\(")
EXEC_SENSITIVE_NAMES = {"create_agent", *TARGET_MUTATIONS, *WORKSPACE_MUTATIONS}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=("supervisor", "lead", "peer"), required=True)
    return parser.parse_args()


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def isoformat(value: dt.datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def preferences_path() -> pathlib.Path:
    override = os.environ.get("ROOM_GUARD_PREFERENCES")
    return pathlib.Path(override) if override else pathlib.Path.home() / ".paseo/orchestration-preferences.json"


def agents_dir() -> pathlib.Path:
    override = os.environ.get("ROOM_GUARD_AGENTS_DIR")
    return pathlib.Path(override) if override else pathlib.Path.home() / ".paseo/agents"


def leases_path() -> pathlib.Path:
    override = os.environ.get("ROOM_GUARD_LEASES_PATH") or os.environ.get(
        "PASEO_ROOM_LEASES_PATH"
    )
    return (
        pathlib.Path(override)
        if override
        else pathlib.Path.home() / ".config/room-workflow/lead-leases.json"
    )


def workspaces_path() -> pathlib.Path:
    override = os.environ.get("ROOM_GUARD_WORKSPACES_PATH")
    return (
        pathlib.Path(override)
        if override
        else pathlib.Path.home() / ".paseo/projects/workspaces.json"
    )


def audit_path() -> pathlib.Path:
    override = os.environ.get("ROOM_GUARD_AUDIT_PATH")
    return (
        pathlib.Path(override)
        if override
        else pathlib.Path.home() / ".config/room-workflow/guard-audit.jsonl"
    )


def read_input() -> dict[str, Any]:
    try:
        value = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError) as error:
        deny(f"Room guard could not read hook input: {error}")
    if not isinstance(value, dict):
        deny("Room guard received a non-object hook input.")
    return value


def emit(payload: dict[str, Any]) -> None:
    json.dump(payload, sys.stdout, separators=(",", ":"))
    sys.stdout.write("\n")


def deny(reason: str) -> None:
    emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }
    )
    raise SystemExit(0)


def allow_with_input(tool_input: dict[str, Any]) -> None:
    emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "updatedInput": tool_input,
            }
        }
    )
    raise SystemExit(0)


def load_json(path: pathlib.Path, default: Any = None) -> Any:
    try:
        with path.open() as stream:
            return json.load(stream)
    except FileNotFoundError:
        return default
    except (json.JSONDecodeError, OSError):
        return default


def write_json_atomic(path: pathlib.Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)


def exec_source(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("input", "code", "source"):
            candidate = value.get(key)
            if isinstance(candidate, str):
                return candidate
    return ""


def scan_balanced(text: str, start: int, opener: str, closer: str) -> int | None:
    if start >= len(text) or text[start] != opener:
        return None
    depth = 0
    quote = ""
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char in ("'", '"', "`"):
            quote = char
        elif char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return index
    return None


def iter_exec_paseo_calls(source: str) -> Iterator[tuple[str, str]]:
    for match in EXEC_PASEO_CALL_RE.finditer(source):
        open_paren = match.end() - 1
        close_paren = scan_balanced(source, open_paren, "(", ")")
        if close_paren is None:
            deny(f"Cannot parse nested Paseo {match.group(1)} call safely.")
        yield match.group(1), source[open_paren + 1 : close_paren].strip()


def top_level_object_properties(source: str) -> dict[str, str]:
    source = source.strip()
    if not source.startswith("{"):
        deny("Nested Paseo mutations must use a static object literal.")
    end = scan_balanced(source, 0, "{", "}")
    if end is None or source[end + 1 :].strip():
        deny("Cannot parse nested Paseo mutation arguments safely.")

    properties: dict[str, str] = {}
    index = 1
    while index < end:
        while index < end and (source[index].isspace() or source[index] == ","):
            index += 1
        if index >= end:
            break

        key_match = re.match(r"[A-Za-z_$][A-Za-z0-9_$]*", source[index:])
        if not key_match:
            deny("Nested Paseo mutation keys must be static identifiers.")
        key = key_match.group(0)
        index += len(key)
        while index < end and source[index].isspace():
            index += 1
        if index >= end or source[index] != ":":
            deny(f"Nested Paseo mutation property {key} must have an explicit value.")
        index += 1
        value_start = index
        brace = bracket = paren = 0
        quote = ""
        escaped = False
        while index < end:
            char = source[index]
            if quote:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = ""
                index += 1
                continue
            if char in ("'", '"', "`"):
                quote = char
            elif char == "{":
                brace += 1
            elif char == "}":
                if brace == 0 and bracket == 0 and paren == 0:
                    break
                brace -= 1
            elif char == "[":
                bracket += 1
            elif char == "]":
                bracket -= 1
            elif char == "(":
                paren += 1
            elif char == ")":
                paren -= 1
            elif char == "," and brace == 0 and bracket == 0 and paren == 0:
                break
            index += 1
        properties[key] = source[value_start:index].strip()
        if index < end and source[index] == ",":
            index += 1
    return properties


def static_string(properties: dict[str, str], key: str, required: bool = True) -> str | None:
    raw = properties.get(key)
    if raw is None:
        if required:
            deny(f"Nested Paseo mutation requires static {key}.")
        return None
    try:
        value = ast.literal_eval(raw)
    except (SyntaxError, ValueError):
        deny(f"Nested Paseo mutation {key} must be a static string.")
    if not isinstance(value, str):
        deny(f"Nested Paseo mutation {key} must be a string.")
    return value


def static_bool(properties: dict[str, str], key: str) -> bool:
    raw = properties.get(key)
    if raw == "true":
        return True
    if raw == "false":
        return False
    deny(f"Nested Paseo mutation {key} must be an explicit boolean.")


def nested_mutation_input(arguments: str, tool_name: str) -> dict[str, Any]:
    properties = top_level_object_properties(arguments)
    value: dict[str, Any] = {}
    for key in ("agentId", "provider", "workspaceId"):
        if key in properties:
            value[key] = static_string(properties, key)
    if tool_name == "create_agent":
        value["notifyOnFinish"] = static_bool(properties, "notifyOnFinish")
        for key in ("labels", "settings"):
            raw = properties.get(key)
            if raw is None:
                deny(f"Nested create_agent requires static {key}.")
            nested = top_level_object_properties(raw)
            value[key] = {
                nested_key: static_string(nested, nested_key)
                for nested_key in nested
            }
    elif tool_name == "update_agent" and "labels" in properties:
        nested = top_level_object_properties(properties["labels"])
        value["labels"] = {
            nested_key: static_string(nested, nested_key)
            for nested_key in nested
        }
    return value


def audit_event(role: str, hook_input: dict[str, Any]) -> None:
    tool_name = hook_input.get("tool_name")
    raw_input = hook_input.get("tool_input")
    source = exec_source(raw_input)
    relevant = (
        tool_name in {"Bash", "exec"}
        and ("paseo" in source.lower())
        or isinstance(tool_name, str)
        and paseo_tool_name(tool_name) is not None
    )
    if not relevant:
        return
    nested = [match.group(1) for match in EXEC_PASEO_CALL_RE.finditer(source)]
    event = {
        "at": isoformat(utc_now()),
        "event": hook_input.get("hook_event_name"),
        "role": role,
        "tool": tool_name,
        "agent_id": os.environ.get("PASEO_AGENT_ID"),
        "nested_paseo_tools": nested,
    }
    path = audit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("a") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            stream.write(json.dumps(event, separators=(",", ":")) + "\n")
            stream.flush()
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass


@contextlib.contextmanager
def locked_leases() -> Iterator[dict[str, Any]]:
    path = leases_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with lock_path.open("a+") as lock_stream:
        fcntl.flock(lock_stream.fileno(), fcntl.LOCK_EX)
        try:
            with path.open() as stream:
                value = json.load(stream)
        except FileNotFoundError:
            value = {"version": 2, "leases": {}}
        except (json.JSONDecodeError, OSError) as error:
            raise RuntimeError("Lead lease registry is unreadable; failing closed") from error
        if not isinstance(value, dict):
            raise RuntimeError("Lead lease registry is not an object; failing closed")
        old_version = value.get("version", 1)
        value["version"] = 2
        if not isinstance(value.get("leases"), dict):
            raise RuntimeError("Lead lease registry has invalid leases; failing closed")
        for workspace_id, lease in value["leases"].items():
            if not isinstance(workspace_id, str) or not workspace_id:
                raise RuntimeError("Lead lease registry has an invalid workspace key; failing closed")
            if not isinstance(lease, dict):
                raise RuntimeError(f"Lead lease {workspace_id} is not an object; failing closed")
            stored_workspace = lease.get("workspace_id")
            if stored_workspace is not None and stored_workspace != workspace_id:
                raise RuntimeError(f"Lead lease {workspace_id} has mismatched workspace authority")
            revision = lease.get("revision", 1)
            if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
                raise RuntimeError(f"Lead lease {workspace_id} has invalid revision; failing closed")
            lease["revision"] = revision
        if isinstance(old_version, int) and old_version < 2:
            for lease in value["leases"].values():
                lease.setdefault("room_kind", MANAGED_ROOM_KIND)
                lease.setdefault("work_epoch", 1)
                lease.setdefault("handback_epoch", 0)
                lease.setdefault("decision_state", "WORKING")
                lease.setdefault("legacy_epoch_unknown", True)
        try:
            yield value
        finally:
            write_json_atomic(path, value)
            fcntl.flock(lock_stream.fileno(), fcntl.LOCK_UN)


def iter_agent_records() -> Iterator[dict[str, Any]]:
    root = agents_dir()
    if not root.exists():
        return
    for path in root.rglob("*.json"):
        value = load_json(path)
        if isinstance(value, dict) and isinstance(value.get("id"), str):
            yield value


def find_agent(agent_id: str | None) -> dict[str, Any] | None:
    if not agent_id:
        return None
    for record in iter_agent_records():
        if record.get("id") == agent_id:
            return record
    return None


def agent_record_status(agent_id: str | None) -> tuple[str, dict[str, Any] | None]:
    """Distinguish missing records from transiently unreadable records."""
    if not agent_id:
        return "missing", None
    root = agents_dir()
    matches = list(root.rglob(f"{agent_id}.json")) if root.exists() else []
    if not matches:
        return "missing", None
    for path in matches:
        value = load_json(path)
        if isinstance(value, dict) and value.get("id") == agent_id:
            return ("archived" if value.get("archivedAt") else "active"), value
    return "unreadable", None


def active_leads(workspace_id: str) -> list[dict[str, Any]]:
    results = []
    for record in iter_agent_records():
        if record.get("archivedAt"):
            continue
        if record.get("workspaceId") != workspace_id:
            continue
        labels = record.get("labels")
        labeled_lead = isinstance(labels, dict) and labels.get(ROLE_LABEL) == "lead"
        custom_lead = record.get("provider") in CUSTOM_LEAD_PROVIDERS
        if labeled_lead or custom_lead:
            results.append(record)
    return results


def workspace_lifecycle(workspace_id: str) -> str | None:
    """Return active/archived/missing only when the workspace registry is readable."""
    records = load_json(workspaces_path())
    if not isinstance(records, list):
        return None
    for record in records:
        if not isinstance(record, dict) or record.get("workspaceId") != workspace_id:
            continue
        return "archived" if record.get("archivedAt") else "active"
    return "missing"


def paseo_tool_name(tool_name: str) -> str | None:
    marker = "mcp__paseo__"
    if tool_name.startswith(marker):
        return tool_name[len(marker) :]
    if tool_name.startswith("paseo_"):
        return tool_name[len("paseo_") :]
    return None


def current_agent_id() -> str:
    value = os.environ.get("PASEO_AGENT_ID", "").strip()
    if not value:
        deny("Room guard requires PASEO_AGENT_ID for Paseo mutations.")
    return value


def current_workspace_id(tool_input: dict[str, Any]) -> str:
    explicit = tool_input.get("workspaceId")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    record = find_agent(current_agent_id())
    workspace_id = record.get("workspaceId") if record else None
    if not isinstance(workspace_id, str) or not workspace_id:
        deny("Room guard could not resolve the target workspace.")
    return workspace_id


def load_providers() -> dict[str, str]:
    value = load_json(preferences_path())
    providers = value.get("providers") if isinstance(value, dict) else None
    if not isinstance(providers, dict):
        deny("Room guard could not load orchestration provider preferences.")
    result = {key: item for key, item in providers.items() if isinstance(item, str) and item}
    if "planning" not in result:
        deny("Room guard requires a planning provider preference.")
    return result


def normalize_labels(tool_input: dict[str, Any]) -> dict[str, str]:
    labels = tool_input.get("labels")
    if labels is None:
        return {}
    if not isinstance(labels, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in labels.items()
    ):
        deny("Agent labels must be a string-to-string object.")
    return dict(labels)


def resolve_lead_route(
    providers: dict[str, str],
    labels: dict[str, str],
) -> tuple[str, str, str]:
    profile = labels.get(LEAD_PROFILE_LABEL, "stable")
    provider_key = {
        "stable": "planning",
        "pilot": "planning_pilot",
        "budget": "planning_budget",
    }.get(profile)
    if provider_key is None:
        deny(f"Unsupported Lead profile {profile!r}.")
    expected = providers.get(provider_key)
    if not expected:
        deny(f"Room guard requires a {provider_key} provider preference.")
    stack_profile = "budget" if profile == "budget" else "standard"
    requested_stack = labels.get(STACK_PROFILE_LABEL, stack_profile)
    if requested_stack != stack_profile:
        deny(
            f"Lead profile {profile} requires {STACK_PROFILE_LABEL}: {stack_profile}."
        )
    caller = find_agent(current_agent_id())
    caller_provider = caller.get("provider") if isinstance(caller, dict) else None
    if profile == "budget" and caller_provider != "opencode-supervisor":
        deny("Only the OpenCode budget Supervisor may create the budget Lead.")
    if caller_provider == "opencode-supervisor" and profile != "budget":
        deny("The OpenCode budget Supervisor may create only the budget Lead.")
    return profile, stack_profile, expected


def normalize_lead_settings(provider: str, settings: dict[str, Any]) -> None:
    if provider.startswith("codex-lead/"):
        settings["modeId"] = "full-access"
        return
    if provider.startswith("claude-lead/"):
        settings["modeId"] = "bypassPermissions"
        settings["thinkingOptionId"] = "high"
        return
    if provider.startswith("opencode-lead/"):
        settings["modeId"] = "build"
        settings["thinkingOptionId"] = "max"
        return
    deny(f"Lead route must use an approved custom Lead provider, not {provider}.")


def validate_lead_settings(provider: str, settings: dict[str, Any]) -> None:
    if provider.startswith("codex-lead/"):
        if settings.get("modeId") != "full-access":
            deny("Codex Lead creation requires settings.modeId: full-access.")
        return
    if provider.startswith("claude-lead/"):
        if settings.get("modeId") != "bypassPermissions":
            deny("Claude Lead creation requires settings.modeId: bypassPermissions.")
        if settings.get("thinkingOptionId") != "high":
            deny("Claude Lead creation requires thinkingOptionId: high.")
        return
    if provider.startswith("opencode-lead/"):
        if settings.get("modeId") != "build":
            deny("OpenCode Lead creation requires settings.modeId: build.")
        if settings.get("thinkingOptionId") != "max":
            deny("OpenCode Lead creation requires thinkingOptionId: max.")
        return
    deny(f"Lead route must use an approved custom Lead provider, not {provider}.")


def current_lead_stack_profile() -> str:
    record = find_agent(current_agent_id())
    labels = record.get("labels") if isinstance(record, dict) else None
    if not isinstance(labels, dict):
        return "standard"
    stack_profile = labels.get(STACK_PROFILE_LABEL, "standard")
    if stack_profile not in {"standard", "budget"}:
        deny(f"Unsupported Lead stack profile {stack_profile!r}.")
    return stack_profile


def current_lead_work_epoch() -> int:
    lead_id = current_agent_id()
    record = find_agent(lead_id)
    labels = record.get("labels") if isinstance(record, dict) else None
    lease = managed_lease_for_target(lead_id=lead_id)
    if (
        not isinstance(record, dict)
        or not isinstance(labels, dict)
        or record.get("archivedAt")
        or not isinstance(lease, dict)
        or lease.get("workspace_id") != record.get("workspaceId")
        or lease.get("room_kind") != MANAGED_ROOM_KIND
        or lease.get("decision_state") != "WORKING"
    ):
        deny("Lead cannot create a Peer without active managed workspace and lease authority.")
    epoch = lease.get("work_epoch")
    if not isinstance(epoch, int) or isinstance(epoch, bool) or epoch < 1:
        deny("Managed Lead work epoch is invalid.")
    if labels.get(ROOM_KIND_LABEL) != MANAGED_ROOM_KIND:
        deny("Managed Lead room_kind label does not match lease authority.")
    if labels.get(WORK_EPOCH_LABEL) != str(epoch):
        deny("Managed Lead work_epoch label does not match lease authority.")
    try:
        workflow.verify_context(lease, record)
    except (workflow.WorkflowError, OSError) as error:
        deny(str(error))
    return epoch


def peer_route_provider_key(route: str, stack_profile: str) -> str:
    return f"{route}_budget" if stack_profile == "budget" else route


def peer_route_thinking(route: str, stack_profile: str) -> str | None:
    if stack_profile == "budget" and route != "ui":
        return "max"
    return ROUTE_THINKING.get(route)


def reserve_lead_lease(
    workspace_id: str,
    supervisor_id: str,
    provider: str,
    tool_use_id: str,
    task_class: str = "bounded",
) -> None:
    now = utc_now()
    with locked_leases() as registry:
        reconcile_archived_leases(registry, now)
        leases = registry["leases"]
        existing = leases.get(workspace_id)
        if isinstance(existing, dict):
            state = existing.get("state")
            expires_at = existing.get("expires_at")
            if state == "pending" and isinstance(expires_at, str):
                with contextlib.suppress(ValueError):
                    expires = dt.datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                    if expires > now:
                        deny(f"Workspace {workspace_id} already has a pending Lead reservation.")
            if state == "active":
                lead_id = existing.get("lead_agent_id")
                deny(f"Workspace {workspace_id} already has active Lead lease {lead_id}.")

        live = active_leads(workspace_id)
        if live:
            lead_id = live[0]["id"]
            live_labels = live[0].get("labels")
            legacy_orphan = (
                not isinstance(live_labels, dict)
                or live_labels.get(ROLE_LABEL) != "lead"
                or live_labels.get(ROOM_KIND_LABEL) != MANAGED_ROOM_KIND
            )
            leases[workspace_id] = {
                "state": "active",
                "room_kind": MANAGED_ROOM_KIND,
                "work_epoch": 1,
                "handback_epoch": 0,
                "decision_state": "LEGACY_BLOCKED" if legacy_orphan else "WORKING",
                "workspace_id": workspace_id,
                "lead_agent_id": lead_id,
                "supervisor_agent_id": supervisor_id,
                "provider": live[0].get("provider"),
                "reconciled_at": isoformat(now),
            }
            if legacy_orphan:
                leases[workspace_id]["legacy_orphan"] = True
            deny(f"Workspace {workspace_id} already has active Lead {lead_id}.")

        leases[workspace_id] = {
            "state": "pending",
            "authority_mode": "parented",
            "task_class": task_class,
            "room_kind": MANAGED_ROOM_KIND,
            "work_epoch": 1,
            "handback_epoch": 0,
            "decision_state": "WORKING",
            "workspace_id": workspace_id,
            "supervisor_agent_id": supervisor_id,
            "provider": provider,
            "reservation_id": tool_use_id,
            "reserved_at": isoformat(now),
            "expires_at": isoformat(now + dt.timedelta(seconds=PENDING_LEASE_SECONDS)),
        }


def guard_create_agent(
    role: str,
    hook_input: dict[str, Any],
    tool_input: dict[str, Any],
) -> None:
    if role == "peer":
        deny("Peer cannot create or dispatch agents.")

    providers = load_providers()
    provider = tool_input.get("provider")
    if not isinstance(provider, str):
        deny("create_agent requires an explicit provider/model route.")
    labels = normalize_labels(tool_input)
    updated = dict(tool_input)
    settings = updated.get("settings")
    if settings is None:
        settings = {}
    if not isinstance(settings, dict):
        deny("create_agent settings must be an object.")
    settings = dict(settings)

    if role == "supervisor":
        profile, stack_profile, expected = resolve_lead_route(providers, labels)
        if provider != expected:
            deny(
                f"Supervisor Lead profile {profile} requires {expected}, not {provider}."
            )
        workspace_id = current_workspace_id(tool_input)
        tool_use_id = hook_input.get("tool_use_id")
        if not isinstance(tool_use_id, str) or not tool_use_id:
            deny("Room guard requires a tool_use_id to reserve the Lead lease.")
        reserve_lead_lease(workspace_id, current_agent_id(), provider, tool_use_id,
                           labels.get("task_class", "bounded"))
        labels[ROLE_LABEL] = "lead"
        labels[ROUTE_LABEL] = "planning"
        labels[TASK_STATE_LABEL] = "LEASED"
        labels[LEAD_PROFILE_LABEL] = profile
        labels[STACK_PROFILE_LABEL] = stack_profile
        labels[ROOM_KIND_LABEL] = MANAGED_ROOM_KIND
        labels[WORK_EPOCH_LABEL] = "1"
        normalize_lead_settings(provider, settings)
    else:
        epoch = current_lead_work_epoch()
        route = labels.get(ROUTE_LABEL)
        if not route:
            deny("Lead must label every Peer creation with an explicit route.")
        allowed_routes = {"impl", "impl_deep", "search", "ui", "research", "audit"}
        if route not in allowed_routes:
            deny(f"Lead cannot create route {route!r}.")
        stack_profile = current_lead_stack_profile()
        provider_key = peer_route_provider_key(route, stack_profile)
        expected = providers.get(provider_key)
        if not expected:
            deny(f"No provider preference is configured for Peer route {provider_key}.")
        if provider != expected:
            deny(f"Route {provider_key} requires {expected}, not {provider}.")
        labels[ROLE_LABEL] = "peer"
        labels[TASK_STATE_LABEL] = "ASSIGNED"
        labels[STACK_PROFILE_LABEL] = stack_profile
        labels[ROOM_KIND_LABEL] = MANAGED_ROOM_KIND
        labels[WORK_EPOCH_LABEL] = str(epoch)
        labels["assignment_id"] = uuid.uuid4().hex
        disposition = labels.get("disposition", "reviewer" if route == "audit" else "engineer").lower()
        if disposition not in {"engineer", "architect", "reviewer", "scout"}:
            deny("Peer disposition must be engineer, architect, reviewer or scout.")
        labels["disposition"] = disposition
        labels["write_mode"] = "write" if disposition == "engineer" else "read_only"
        prompt = updated.get("initialPrompt", "")
        if not isinstance(prompt, str):
            deny("Peer initialPrompt must be a string.")
        correlation = {"version": 1, "parentLeadId": current_agent_id(),
                       "workspaceId": current_workspace_id(tool_input),
                       "workEpoch": epoch, "assignmentId": labels["assignment_id"]}
        updated["initialPrompt"] = prompt + "\n\nPeer report correlation (preserve exactly):\n" + json.dumps(correlation, sort_keys=True) + (
            "\nReturn a version-1 JSON report with these fields plus reportId (unique per report), "
            "peerAgentId (your own Paseo identity), kind and payload. "
            "payload.evidence must name actual artifacts/checks and their limits. "
            "For REVIEW add payload.candidateDigest and payload.verdict=APPROVE|FINDINGS. "
            "Otherwise kind=HANDOFF|REOPEN_REQUEST|DEPENDENCY_REQUEST|BLOCKED|PROGRESS. "
            "Keep the Task outcome line for native callback compatibility. "
            + ("This is an inspection-only assignment: do not write files or change code." if disposition != "engineer" else "Own proof of writes within the assigned scope.")
        )
        required_thinking = peer_route_thinking(route, stack_profile)
        if required_thinking:
            settings["thinkingOptionId"] = required_thinking
        if provider.startswith("codex-peer/"):
            settings["modeId"] = "full-access"
        if provider.startswith("opencode-peer/"):
            settings["modeId"] = "build"

    updated["labels"] = labels
    updated["settings"] = settings
    # Lead completion is reported only through epoch-aware handback_to_parent.
    # Peer completion still uses Paseo's native parent callback.
    updated["notifyOnFinish"] = role != "supervisor"
    allow_with_input(updated)


def guard_nested_create_agent(
    role: str,
    hook_input: dict[str, Any],
    tool_input: dict[str, Any],
) -> None:
    if role == "peer":
        deny("Peer cannot create or dispatch agents.")

    providers = load_providers()
    provider = tool_input.get("provider")
    labels = tool_input.get("labels")
    settings = tool_input.get("settings")
    if not isinstance(provider, str) or not isinstance(labels, dict) or not isinstance(settings, dict):
        deny("Nested create_agent requires static provider, labels, and settings.")
    if role == "supervisor":
        profile, stack_profile, expected = resolve_lead_route(providers, labels)
        if provider != expected:
            deny(
                f"Supervisor Lead profile {profile} requires {expected}, not {provider}."
            )
        required_labels = {
            ROLE_LABEL: "lead",
            ROUTE_LABEL: "planning",
            TASK_STATE_LABEL: "LEASED",
            ROOM_KIND_LABEL: MANAGED_ROOM_KIND,
            WORK_EPOCH_LABEL: "1",
        }
        for key, expected_value in required_labels.items():
            if labels.get(key) != expected_value:
                deny(f"Supervisor create_agent requires {key}: {expected_value}.")
        if LEAD_PROFILE_LABEL in labels and labels[LEAD_PROFILE_LABEL] != profile:
            deny(f"Supervisor create_agent requires {LEAD_PROFILE_LABEL}: {profile}.")
        if STACK_PROFILE_LABEL in labels and labels[STACK_PROFILE_LABEL] != stack_profile:
            deny(f"Supervisor create_agent requires {STACK_PROFILE_LABEL}: {stack_profile}.")
        validate_lead_settings(provider, settings)
        if tool_input.get("notifyOnFinish") is not False:
            deny("Managed Lead creation requires notifyOnFinish: false.")
        workspace_id = current_workspace_id(tool_input)
        tool_use_id = hook_input.get("tool_use_id")
        if not isinstance(tool_use_id, str) or not tool_use_id:
            deny("Room guard requires a tool_use_id to reserve the Lead lease.")
        reserve_lead_lease(workspace_id, current_agent_id(), provider, tool_use_id)
        return

    epoch = current_lead_work_epoch()
    if tool_input.get("notifyOnFinish") is not True:
        deny("Nested Peer create_agent requires notifyOnFinish: true.")
    route = labels.get(ROUTE_LABEL)
    allowed_routes = {"impl", "impl_deep", "search", "ui", "research", "audit"}
    if route not in allowed_routes:
        deny(f"Lead must use an allowed static Peer route, not {route!r}.")
    stack_profile = current_lead_stack_profile()
    provider_key = peer_route_provider_key(route, stack_profile)
    expected = providers.get(provider_key)
    if not expected:
        deny(f"No provider preference is configured for Peer route {provider_key}.")
    if provider != expected:
        deny(f"Route {provider_key} requires {expected}, not {provider}.")
    required_labels = {
        ROLE_LABEL: "peer",
        TASK_STATE_LABEL: "ASSIGNED",
        ROOM_KIND_LABEL: MANAGED_ROOM_KIND,
        WORK_EPOCH_LABEL: str(epoch),
    }
    for key, expected_value in required_labels.items():
        if labels.get(key) != expected_value:
            deny(f"Lead create_agent requires {key}: {expected_value}.")
    if stack_profile == "budget" and labels.get(STACK_PROFILE_LABEL) != "budget":
        deny("Budget Lead create_agent requires stack_profile: budget.")
    required_thinking = peer_route_thinking(route, stack_profile)
    if required_thinking and settings.get("thinkingOptionId") != required_thinking:
        deny(f"Peer route {route} requires thinkingOptionId: {required_thinking}.")
    if provider.startswith("codex-peer/") and settings.get("modeId") != "full-access":
        deny("Codex Peer creation requires settings.modeId: full-access.")
    if provider.startswith("opencode-peer/") and settings.get("modeId") != "build":
        deny("OpenCode Peer creation requires settings.modeId: build.")


def guard_lifecycle_label_update(
    requested: Any,
    current: dict[str, Any],
) -> None:
    if not isinstance(requested, dict):
        return
    for key in (TASK_STATE_LABEL, ROOM_KIND_LABEL, WORK_EPOCH_LABEL):
        if requested.get(key) != current.get(key):
            deny(f"Managed Lead lifecycle label {key} is proxy-owned.")


def managed_lease_decision_state(lead_id: str) -> str | None:
    with locked_leases() as registry:
        for lease in registry["leases"].values():
            if (
                isinstance(lease, dict)
                and lease.get("state") == "active"
                and lease.get("room_kind") == MANAGED_ROOM_KIND
                and lease.get("lead_agent_id") == lead_id
            ):
                state = lease.get("decision_state")
                return state if isinstance(state, str) else None
    return None


def managed_lease_for_target(
    *, lead_id: str | None = None, workspace_id: str | None = None
) -> dict[str, Any] | None:
    with locked_leases() as registry:
        for key, lease in registry["leases"].items():
            if not isinstance(lease, dict) or lease.get("state") != "active":
                continue
            if lease.get("room_kind") != MANAGED_ROOM_KIND:
                continue
            if lead_id is not None and lease.get("lead_agent_id") == lead_id:
                return dict(lease)
            if workspace_id is not None and key == workspace_id:
                return dict(lease)
    return None


def guard_target_mutation(role: str, tool_name: str, tool_input: dict[str, Any]) -> None:
    if role == "peer":
        deny(f"Peer cannot call Paseo mutation {tool_name}.")
    target = tool_input.get("agentId")
    if not isinstance(target, str) or not target:
        deny(f"{tool_name} requires an explicit agentId.")
    caller = current_agent_id()
    if target == caller and tool_name in {"update_agent", "set_agent_mode"}:
        if role == "lead" and tool_name == "update_agent":
            own_record = find_agent(caller)
            own_labels = own_record.get("labels") if isinstance(own_record, dict) else None
            guard_lifecycle_label_update(
                tool_input.get("labels"),
                own_labels if isinstance(own_labels, dict) else {},
            )
        return
    record = find_agent(target)
    if not record:
        deny(f"Room guard could not resolve target agent {target}.")
    if role == "supervisor" and tool_name == "archive_agent" and record.get("archivedAt"):
        return
    labels = record.get("labels")
    labels = labels if isinstance(labels, dict) else {}
    expected_role = "lead" if role == "supervisor" else "peer"
    if labels.get(ROLE_LABEL) != expected_role:
        deny(f"{role.title()} may mutate only a {expected_role} seat.")
    if role == "supervisor" and tool_name == "send_agent_prompt":
        decision_state = managed_lease_decision_state(target)
        if decision_state is not None or labels.get(ROOM_KIND_LABEL) == MANAGED_ROOM_KIND:
            deny(
                "Generic prompts to a managed Lead are blocked by lifecycle state "
                f"{decision_state or labels.get(TASK_STATE_LABEL)}; use a protected SLP operation."
            )
    if role == "supervisor":
        lease = managed_lease_for_target(lead_id=target)
        owned = (workflow.governs(lease, caller, role) and workflow.lead_matches(lease, record)) if lease else labels.get(PARENT_LABEL) == caller
    else:
        owned = labels.get(PARENT_LABEL) == caller
        lease = managed_lease_for_target(lead_id=caller)
        if lease and labels.get(ROOM_KIND_LABEL) == MANAGED_ROOM_KIND and labels.get(WORK_EPOCH_LABEL) != str(lease.get("work_epoch")):
            deny("Peer mutation is fenced to the current Lead work epoch.")
        if tool_name == "update_agent" and isinstance(tool_input.get("labels"), dict):
            for key in (ROLE_LABEL, PARENT_LABEL, ROOM_KIND_LABEL, WORK_EPOCH_LABEL, "assignment_id", "disposition", "write_mode"):
                if key in tool_input["labels"] and tool_input["labels"][key] != labels.get(key):
                    deny(f"Peer authority label {key} is proxy-owned.")
    if not owned:
        deny(f"Target {target} is not bound to the current {role} authority.")
    if role == "supervisor" and tool_name == "update_agent":
        guard_lifecycle_label_update(tool_input.get("labels"), labels)


def guard_workspace_mutation(role: str, tool_name: str, tool_input: dict[str, Any]) -> None:
    if role != "supervisor":
        deny(f"Only Supervisor can call Paseo workspace mutation {tool_name}.")
    workspace_id = tool_input.get("workspaceId")
    if not isinstance(workspace_id, str) or not workspace_id:
        deny(f"{tool_name} requires an explicit workspaceId.")
    caller = find_agent(current_agent_id())
    if caller and caller.get("workspaceId") == workspace_id:
        deny("Supervisor cannot archive its own active workspace.")
    lease = managed_lease_for_target(workspace_id=workspace_id)
    if lease is not None:
        deny("Managed workspace archive must use the protected archive_slp_workspace operation.")


def guard_bash(role: str, tool_input: dict[str, Any]) -> None:
    command = tool_input.get("command")
    if not isinstance(command, str):
        return
    if role == "peer" and ANY_PASEO_COMMAND_RE.search(command):
        deny("Peer cannot invoke the Paseo CLI.")
    if DIRECT_PASEO_MUTATION_RE.search(command):
        deny("Direct Paseo mutations are blocked; use the guarded Paseo MCP tools.")


def guard_exec(role: str, hook_input: dict[str, Any], raw_tool_input: Any) -> None:
    source = exec_source(raw_tool_input)
    if not source:
        return
    if role == "peer" and "mcp__paseo__" in source:
        deny("Peer cannot use Paseo orchestration tools through exec.")

    calls = list(iter_exec_paseo_calls(source))
    direct_sensitive = [item for item in calls if item[0] in EXEC_SENSITIVE_NAMES]
    for name in EXEC_SENSITIVE_NAMES:
        occurrences = source.count(f"mcp__paseo__{name}")
        parsed = sum(1 for parsed_name, _ in calls if parsed_name == name)
        if occurrences > parsed:
            deny(f"Dynamic or indirect nested Paseo mutation {name} is blocked.")
    if len(direct_sensitive) > 1:
        deny("Use exactly one nested Paseo mutation per exec call.")

    for tool_name, arguments in direct_sensitive:
        tool_input = nested_mutation_input(arguments, tool_name)
        if tool_name == "create_agent":
            guard_nested_create_agent(role, hook_input, tool_input)
        elif tool_name in TARGET_MUTATIONS:
            guard_target_mutation(role, tool_name, tool_input)
        elif tool_name in WORKSPACE_MUTATIONS:
            guard_workspace_mutation(role, tool_name, tool_input)


def recursive_find(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        if key in value:
            return value[key]
        for child in value.values():
            found = recursive_find(child, key)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = recursive_find(child, key)
            if found is not None:
                return found
    elif isinstance(value, str):
        with contextlib.suppress(json.JSONDecodeError):
            decoded = json.loads(value)
            found = recursive_find(decoded, key)
            if found is not None:
                return found
        if key == "agentId":
            match = re.search(r'"agentId"\s*:\s*"([^"]+)"', value)
            if match:
                return match.group(1)
    return None


def response_failed(value: Any) -> bool:
    if isinstance(value, dict):
        if value.get("isError") is True or "error" in value:
            return True
        return any(response_failed(child) for child in value.values())
    if isinstance(value, list):
        return any(response_failed(child) for child in value)
    return False


def finalize_lead_lease(hook_input: dict[str, Any]) -> None:
    tool_input = hook_input.get("tool_input")
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    workspace_id = current_workspace_id(tool_input)
    reservation_id = hook_input.get("tool_use_id")
    response = hook_input.get("tool_response")
    agent_id = None if response_failed(response) else recursive_find(response, "agentId")
    with locked_leases() as registry:
        lease = registry["leases"].get(workspace_id)
        if not isinstance(lease, dict) or lease.get("reservation_id") != reservation_id:
            return
        if not isinstance(agent_id, str) or not agent_id:
            lease["state"] = "failed"
            lease["failed_at"] = isoformat(utc_now())
            return
        lease.pop("expires_at", None)
        lease["state"] = "active"
        lease["lead_agent_id"] = agent_id
        lease["acquired_at"] = isoformat(utc_now())
        lease.setdefault("room_kind", MANAGED_ROOM_KIND)
        lease.setdefault("work_epoch", 1)
        lease.setdefault("handback_epoch", 0)
        lease.setdefault("decision_state", "WORKING")


def release_lead_lease(hook_input: dict[str, Any]) -> None:
    response = hook_input.get("tool_response")
    if response_failed(response):
        return
    tool_input = hook_input.get("tool_input")
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    target = tool_input.get("agentId")
    if not isinstance(target, str):
        return
    with locked_leases() as registry:
        for lease in registry["leases"].values():
            if not isinstance(lease, dict) or lease.get("lead_agent_id") != target:
                continue
            lease["state"] = "released"
            lease["released_at"] = isoformat(utc_now())


def reconcile_archived_leases(
    registry: dict[str, Any],
    now: dt.datetime | None = None,
) -> None:
    released_at = isoformat(now or utc_now())
    for lease in registry["leases"].values():
        if not isinstance(lease, dict) or lease.get("state") != "active":
            continue
        lead_id = lease.get("lead_agent_id")
        record_state, record = agent_record_status(
            lead_id if isinstance(lead_id, str) else None
        )
        workspace_id = lease.get("workspace_id")
        workspace_state = (
            workspace_lifecycle(workspace_id)
            if isinstance(workspace_id, str)
            else None
        )
        if record_state in {"active", "unreadable"} and workspace_state not in {
            "archived",
            "missing",
        }:
            continue
        lease["state"] = "released"
        lease["released_at"] = released_at
        if record_state == "missing":
            lease["release_reason"] = "missing_agent_reconciled"
        elif record_state == "archived":
            lease["release_reason"] = "archived_agent_reconciled"
        else:
            lease["release_reason"] = f"{workspace_state}_workspace_reconciled"


def release_workspace_leases(hook_input: dict[str, Any]) -> None:
    response = hook_input.get("tool_response")
    if response_failed(response):
        return
    tool_input = hook_input.get("tool_input")
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    workspace_id = tool_input.get("workspaceId")
    if not isinstance(workspace_id, str):
        return
    now = utc_now()
    with locked_leases() as registry:
        reconcile_archived_leases(registry, now)
        lease = registry["leases"].get(workspace_id)
        if not isinstance(lease, dict) or lease.get("state") not in {"pending", "active"}:
            return
        lease["state"] = "released"
        lease["released_at"] = isoformat(now)
        lease["release_reason"] = "workspace_archived"


def handle_pre(role: str, hook_input: dict[str, Any]) -> None:
    raw_tool_name = hook_input.get("tool_name")
    tool_name = raw_tool_name if isinstance(raw_tool_name, str) else ""
    raw_tool_input = hook_input.get("tool_input")
    tool_input = raw_tool_input if isinstance(raw_tool_input, dict) else {}

    if tool_name == "Bash":
        guard_bash(role, tool_input)
        return
    if tool_name == "exec":
        guard_exec(role, hook_input, raw_tool_input)
        return

    paseo_name = paseo_tool_name(tool_name)
    if not paseo_name:
        return
    if role == "peer":
        deny("Peer cannot use Paseo orchestration tools.")
    if paseo_name == "create_agent":
        guard_create_agent(role, hook_input, tool_input)
    if paseo_name in TARGET_MUTATIONS:
        guard_target_mutation(role, paseo_name, tool_input)
    if paseo_name in WORKSPACE_MUTATIONS:
        guard_workspace_mutation(role, paseo_name, tool_input)


def handle_post(role: str, hook_input: dict[str, Any]) -> None:
    if role != "supervisor":
        return
    raw_tool_name = hook_input.get("tool_name")
    raw_tool_name = raw_tool_name if isinstance(raw_tool_name, str) else ""
    if raw_tool_name == "exec":
        calls = list(iter_exec_paseo_calls(exec_source(hook_input.get("tool_input"))))
        sensitive = [item for item in calls if item[0] in EXEC_SENSITIVE_NAMES]
        if len(sensitive) != 1:
            return
        nested_name, arguments = sensitive[0]
        nested_input = nested_mutation_input(arguments, nested_name)
        nested_hook_input = dict(hook_input)
        nested_hook_input["tool_input"] = nested_input
        if nested_name == "create_agent":
            finalize_lead_lease(nested_hook_input)
        elif nested_name in {"archive_agent", "kill_agent"}:
            release_lead_lease(nested_hook_input)
        elif nested_name == "archive_workspace":
            release_workspace_leases(nested_hook_input)
        return
    tool_name = paseo_tool_name(raw_tool_name)
    if tool_name == "create_agent":
        finalize_lead_lease(hook_input)
    elif tool_name in {"archive_agent", "kill_agent"}:
        release_lead_lease(hook_input)
    elif tool_name == "archive_workspace":
        release_workspace_leases(hook_input)


def main() -> None:
    args = parse_args()
    hook_input = read_input()
    audit_event(args.role, hook_input)
    event = hook_input.get("hook_event_name")
    if event == "PreToolUse":
        handle_pre(args.role, hook_input)
    elif event == "PostToolUse":
        handle_post(args.role, hook_input)


if __name__ == "__main__":
    main()
