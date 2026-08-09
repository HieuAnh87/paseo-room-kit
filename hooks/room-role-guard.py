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
from collections.abc import Iterator
from typing import Any


PARENT_LABEL = "paseo.parent-agent-id"
ROLE_LABEL = "role"
ROUTE_LABEL = "route"
TASK_STATE_LABEL = "task_state"
PENDING_LEASE_SECONDS = 300

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
    override = os.environ.get("ROOM_GUARD_LEASES_PATH")
    return (
        pathlib.Path(override)
        if override
        else pathlib.Path.home() / ".config/room-workflow/lead-leases.json"
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
        os.replace(temporary, path)
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
        value = load_json(path, {"version": 1, "leases": {}})
        if not isinstance(value, dict):
            value = {"version": 1, "leases": {}}
        value["version"] = 1
        if not isinstance(value.get("leases"), dict):
            value["leases"] = {}
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


def active_leads(workspace_id: str) -> list[dict[str, Any]]:
    results = []
    for record in iter_agent_records():
        if record.get("archivedAt"):
            continue
        if record.get("workspaceId") != workspace_id:
            continue
        labels = record.get("labels")
        if isinstance(labels, dict) and labels.get(ROLE_LABEL) == "lead":
            results.append(record)
    return results


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


def reserve_lead_lease(
    workspace_id: str,
    supervisor_id: str,
    provider: str,
    tool_use_id: str,
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
                record = find_agent(lead_id if isinstance(lead_id, str) else None)
                if record and not record.get("archivedAt"):
                    deny(f"Workspace {workspace_id} already has active Lead {lead_id}.")

        live = active_leads(workspace_id)
        if live:
            lead_id = live[0]["id"]
            leases[workspace_id] = {
                "state": "active",
                "workspace_id": workspace_id,
                "lead_agent_id": lead_id,
                "supervisor_agent_id": supervisor_id,
                "provider": live[0].get("provider"),
                "reconciled_at": isoformat(now),
            }
            deny(f"Workspace {workspace_id} already has active Lead {lead_id}.")

        leases[workspace_id] = {
            "state": "pending",
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
        expected = providers["planning"]
        if provider != expected:
            deny(f"Supervisor may create only the planning Lead route ({expected}), not {provider}.")
        workspace_id = current_workspace_id(tool_input)
        tool_use_id = hook_input.get("tool_use_id")
        if not isinstance(tool_use_id, str) or not tool_use_id:
            deny("Room guard requires a tool_use_id to reserve the Lead lease.")
        reserve_lead_lease(workspace_id, current_agent_id(), provider, tool_use_id)
        labels[ROLE_LABEL] = "lead"
        labels[ROUTE_LABEL] = "planning"
        labels[TASK_STATE_LABEL] = "LEASED"
        settings["modeId"] = "full-access"
    else:
        route = labels.get(ROUTE_LABEL)
        if not route:
            deny("Lead must label every Peer creation with an explicit route.")
        allowed_routes = {"impl", "impl_deep", "search", "ui", "research", "audit"}
        if route not in allowed_routes:
            deny(f"Lead cannot create route {route!r}.")
        expected = providers.get(route)
        if not expected:
            deny(f"No provider preference is configured for Peer route {route}.")
        if provider != expected:
            deny(f"Route {route} requires {expected}, not {provider}.")
        labels[ROLE_LABEL] = "peer"
        labels[TASK_STATE_LABEL] = "ASSIGNED"
        required_thinking = ROUTE_THINKING.get(route)
        if required_thinking:
            settings["thinkingOptionId"] = required_thinking
        if provider.startswith("codex-peer/"):
            settings["modeId"] = "full-access"

    updated["labels"] = labels
    updated["settings"] = settings
    updated["notifyOnFinish"] = True
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
    if tool_input.get("notifyOnFinish") is not True:
        deny("Nested create_agent requires notifyOnFinish: true.")

    if role == "supervisor":
        expected = providers["planning"]
        if provider != expected:
            deny(f"Supervisor may create only the planning Lead route ({expected}), not {provider}.")
        required_labels = {
            ROLE_LABEL: "lead",
            ROUTE_LABEL: "planning",
            TASK_STATE_LABEL: "LEASED",
        }
        for key, expected_value in required_labels.items():
            if labels.get(key) != expected_value:
                deny(f"Supervisor create_agent requires {key}: {expected_value}.")
        if settings.get("modeId") != "full-access":
            deny("Supervisor create_agent requires settings.modeId: full-access.")
        workspace_id = current_workspace_id(tool_input)
        tool_use_id = hook_input.get("tool_use_id")
        if not isinstance(tool_use_id, str) or not tool_use_id:
            deny("Room guard requires a tool_use_id to reserve the Lead lease.")
        reserve_lead_lease(workspace_id, current_agent_id(), provider, tool_use_id)
        return

    route = labels.get(ROUTE_LABEL)
    allowed_routes = {"impl", "impl_deep", "search", "ui", "research", "audit"}
    if route not in allowed_routes:
        deny(f"Lead must use an allowed static Peer route, not {route!r}.")
    expected = providers.get(route)
    if not expected:
        deny(f"No provider preference is configured for Peer route {route}.")
    if provider != expected:
        deny(f"Route {route} requires {expected}, not {provider}.")
    required_labels = {ROLE_LABEL: "peer", TASK_STATE_LABEL: "ASSIGNED"}
    for key, expected_value in required_labels.items():
        if labels.get(key) != expected_value:
            deny(f"Lead create_agent requires {key}: {expected_value}.")
    required_thinking = ROUTE_THINKING.get(route)
    if required_thinking and settings.get("thinkingOptionId") != required_thinking:
        deny(f"Peer route {route} requires thinkingOptionId: {required_thinking}.")
    if provider.startswith("codex-peer/") and settings.get("modeId") != "full-access":
        deny("Codex Peer creation requires settings.modeId: full-access.")


def guard_target_mutation(role: str, tool_name: str, tool_input: dict[str, Any]) -> None:
    if role == "peer":
        deny(f"Peer cannot call Paseo mutation {tool_name}.")
    target = tool_input.get("agentId")
    if not isinstance(target, str) or not target:
        deny(f"{tool_name} requires an explicit agentId.")
    caller = current_agent_id()
    if target == caller and tool_name in {"update_agent", "set_agent_mode"}:
        return
    record = find_agent(target)
    if not record:
        deny(f"Room guard could not resolve target agent {target}.")
    labels = record.get("labels")
    labels = labels if isinstance(labels, dict) else {}
    expected_role = "lead" if role == "supervisor" else "peer"
    if labels.get(ROLE_LABEL) != expected_role:
        deny(f"{role.title()} may mutate only a {expected_role} seat.")
    if labels.get(PARENT_LABEL) != caller:
        deny(f"Target {target} is not owned by the current {role} seat.")


def guard_workspace_mutation(role: str, tool_name: str, tool_input: dict[str, Any]) -> None:
    if role != "supervisor":
        deny(f"Only Supervisor can call Paseo workspace mutation {tool_name}.")
    workspace_id = tool_input.get("workspaceId")
    if not isinstance(workspace_id, str) or not workspace_id:
        deny(f"{tool_name} requires an explicit workspaceId.")
    caller = find_agent(current_agent_id())
    if caller and caller.get("workspaceId") == workspace_id:
        deny("Supervisor cannot archive its own active workspace.")


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
        record = find_agent(lead_id if isinstance(lead_id, str) else None)
        if not record or not record.get("archivedAt"):
            continue
        lease["state"] = "released"
        lease["released_at"] = released_at
        lease["release_reason"] = "archived_agent_reconciled"


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
