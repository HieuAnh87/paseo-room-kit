#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mode="${1:---repo}"
target_home="${PASEO_KIT_HOME:-${HOME}}"
failures=0
export PYTHONDONTWRITEBYTECODE=1
paseo_pin=""
room_role_active=0

pass() { printf 'PASS %s\n' "$*"; }
warn() { printf 'WARN %s\n' "$*"; }
fail() { printf 'FAIL %s\n' "$*" >&2; failures=$((failures + 1)); }

check_command() {
  if command -v "$1" >/dev/null 2>&1; then
    pass "command $1"
  else
    fail "missing command $1"
  fi
}

load_paseo_pin() {
  local lock_file="${repo_root}/versions.lock.json"
  if ! paseo_pin="$(python3 - "$lock_file" <<'PY'
import json
import re
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    value = json.load(handle)

pin = value.get("paseo") if isinstance(value, dict) else None
if not isinstance(pin, str) or not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", pin):
    raise ValueError("missing stable Paseo semver pin")
print(pin)
PY
)"; then
    paseo_pin=""
    fail "invalid Paseo version pin in ${lock_file}"
    return 1
  fi
}

check_cli_version() {
  [[ -n "$paseo_pin" ]] || return 0

  if ((room_role_active)); then
    fail "Paseo CLI version cannot be verified safely from managed role ${PASEO_ROOM_ROLE}; run this check from an unwrapped owner shell"
    return 0
  fi

  if ! command -v paseo >/dev/null 2>&1; then
    fail "Paseo CLI version unavailable: command not found (expected ${paseo_pin})"
    return 0
  fi

  local raw_version displayed_version
  if ! raw_version="$(paseo --version 2>/dev/null)"; then
    fail "Paseo CLI version probe failed (expected ${paseo_pin})"
    return 0
  fi
  printf -v displayed_version '%q' "$raw_version"
  if [[ ! "$raw_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    fail "Paseo CLI version output is not a stable semver: ${displayed_version}"
  elif [[ "$raw_version" != "$paseo_pin" ]]; then
    fail "Paseo CLI version mismatch: expected ${paseo_pin}, got ${displayed_version}"
  else
    pass "Paseo CLI version matches pin ${paseo_pin}"
  fi
}

check_room_wrapper() {
  [[ -n "${PASEO_ROOM_ROLE:-}" ]] || return 0
  room_role_active=1

  local expected_wrapper actual_paseo role_display actual_display expected_display
  expected_wrapper="${target_home}/.local/share/paseo-room-bin/paseo"
  actual_paseo="$(command -v paseo 2>/dev/null || true)"
  if [[ "$actual_paseo" == "$expected_wrapper" ]] && \
    [[ -f "$expected_wrapper" && -x "$expected_wrapper" && ! -L "$expected_wrapper" ]] && \
    cmp -s "${repo_root}/bin/paseo-room-deny" "$expected_wrapper"; then
    pass "room deny wrapper active for role ${PASEO_ROOM_ROLE}"
    return 0
  fi

  printf -v role_display '%q' "${PASEO_ROOM_ROLE}"
  printf -v actual_display '%q' "${actual_paseo:-<missing>}"
  printf -v expected_display '%q' "$expected_wrapper"
  fail "PASEO_ROOM_ROLE=${role_display} but the effective Paseo command is not the exact executable room deny wrapper: command -v paseo is ${actual_display}; expected ${expected_display}; doctor will not modify shell config"
}

check_daemon_version() {
  [[ -n "$paseo_pin" ]] || return 0

  if ((room_role_active)); then
    fail "Paseo daemon version cannot be verified safely from managed role ${PASEO_ROOM_ROLE}; run this check from an unwrapped owner shell"
    return 0
  fi

  local status_json daemon_version
  if ! status_json="$(paseo daemon status --json 2>/dev/null)"; then
    fail "Paseo daemon status probe failed (expected Paseo 0.8 JSON)"
    return 0
  fi

  if ! daemon_version="$(printf '%s' "$status_json" | jq -er -s '
    if length != 1 then
      error("expected exactly one JSON value")
    elif (.[0] | type) != "object" then
      error("expected a status object")
    elif (.[0] | has("daemonVersion")) | not then
      error("daemonVersion is missing")
    elif (.[0].daemonVersion | type) != "string" then
      error("daemonVersion must be a string")
    elif (.[0].daemonVersion | length) == 0 then
      error("daemonVersion must not be empty")
    else
      .[0].daemonVersion
    end
  ')"; then
    fail "Paseo daemon status JSON is invalid or missing string daemonVersion (Paseo 0.8 schema)"
  else
    pass "Paseo daemon reachable"
    if [[ "$daemon_version" != "$paseo_pin" ]]; then
      fail "Paseo daemon version mismatch: expected ${paseo_pin}, got ${daemon_version}"
    else
      pass "Paseo daemon version matches pin ${paseo_pin}"
    fi
  fi
}

check_provider_tool_policy() {
  local config_path="$1"
  local label="$2"
  if python3 - "$config_path" <<'PY'
import json
import sys

required = {
    "claude-supervisor",
    "codex-supervisor",
    "codex-lead",
    "claude-lead",
    "codex-peer",
    "opencode-peer",
    "opencode-supervisor",
    "opencode-lead",
    "gemini-ui",
}
with open(sys.argv[1], encoding="utf-8") as handle:
    value = json.load(handle)
providers = value.get("agents", {}).get("providers", {})
if not isinstance(providers, dict):
    raise ValueError("missing provider registry")
for provider_id in required:
    provider = providers.get(provider_id)
    if not isinstance(provider, dict) or provider.get("paseoTools") != {"enabled": False}:
        raise ValueError(f"{provider_id} does not disable native Paseo tools")
PY
  then
    pass "${label} disables native Paseo tools for every internal SLP provider"
  else
    fail "${label} does not defensively disable native Paseo tools for every internal SLP provider"
  fi
}

check_installed_copy() {
  local source="$1"
  local destination="$2"
  local label="$3"
  if [[ -f "$destination" ]] && cmp -s "$source" "$destination"; then
    pass "${label} matches canonical source"
  else
    fail "${label} differs from canonical source"
  fi
}

check_installed_render() {
  local source="$1"
  local destination="$2"
  local label="$3"
  local rendered
  rendered="$(mktemp)"
  if python3 "${repo_root}/scripts/render_template.py" \
      "$source" "$rendered" --home "$target_home" >/dev/null &&
    [[ -f "$destination" ]] &&
    cmp -s "$rendered" "$destination"; then
    pass "${label} matches canonical rendered source"
  else
    fail "${label} differs from canonical rendered source"
  fi
  rm -f "$rendered"
}

case "$mode" in
  --repo|--preflight|--live) ;;
  *) printf 'usage: %s [--repo|--preflight|--live]\n' "$0" >&2; exit 2 ;;
esac

python3 "${repo_root}/tests/test_portability.py" || failures=$((failures + 1))
python3 "${repo_root}/tests/test_proxy_handback.py" || failures=$((failures + 1))
python3 "${repo_root}/tests/test_workflow.py" || failures=$((failures + 1))
python3 "${repo_root}/tests/test_public_export.py" || failures=$((failures + 1))
python3 -c 'import pathlib, sys; [compile(path.read_text(), str(path), "exec") for path in map(pathlib.Path, sys.argv[1:])]' \
  "${repo_root}/hooks/room-role-guard.py" \
  "${repo_root}/hooks/test-room-role-guard.py" \
  "${repo_root}/bin/codex-room-sync" \
  "${repo_root}/bin/paseo-room-mcp" \
  "${repo_root}/bin/paseo-room-workflow" \
  "${repo_root}/bin/room_workflow.py" \
  "${repo_root}/scripts/render_template.py" \
  "${repo_root}/scripts/manage_zshrc.py" \
  "${repo_root}/scripts/export_public_kit.py" \
  "${repo_root}/scripts/check_public_artifact.py" || failures=$((failures + 1))
bash -n \
  "${repo_root}/bin/claude-room" \
  "${repo_root}/bin/codex-room" \
  "${repo_root}/bin/opencode-paseo-room" \
  "${repo_root}/bin/opencode-paseo-peer" \
  "${repo_root}/bin/paseo-room-deny" \
  "${repo_root}/scripts/install.sh" \
  "${repo_root}/scripts/install-antigravity-acp.sh" || failures=$((failures + 1))
python3 "${repo_root}/hooks/test-room-role-guard.py" || failures=$((failures + 1))
check_provider_tool_policy \
  "${repo_root}/config/paseo/config.json.tmpl" \
  "canonical provider policy"

if [[ "$mode" == "--preflight" || "$mode" == "--live" ]]; then
  load_paseo_pin || true
  for command in git jq python3 rg paseo claude codex; do
    check_command "$command"
  done
  for optional in bun opencode; do
    if command -v "$optional" >/dev/null 2>&1; then
      pass "optional command $optional"
    else
      warn "optional command missing: $optional"
    fi
  done
  check_room_wrapper
  check_cli_version
fi

if [[ "$mode" == "--live" ]]; then
  check_daemon_version
  if jq -e '.daemon.mcp.enabled == true and .daemon.mcp.injectIntoAgents == false' \
    "${target_home}/.paseo/config.json" >/dev/null; then
    pass "global Paseo MCP injection disabled"
  else
    fail "unexpected Paseo MCP injection config"
  fi
  check_provider_tool_policy \
    "${target_home}/.paseo/config.json" \
    "installed provider policy"
  check_installed_copy \
    "${repo_root}/bin/paseo-room-mcp" \
    "${target_home}/.local/bin/paseo-room-mcp" \
    "installed role proxy"
  for asset in paseo-room-workflow room_workflow.py; do
    check_installed_copy \
      "${repo_root}/bin/${asset}" \
      "${target_home}/.local/bin/${asset}" \
      "installed shared workflow ${asset}"
  done
  check_installed_copy \
    "${repo_root}/hooks/room-role-guard.py" \
    "${target_home}/.codex/hooks/room-role-guard.py" \
    "installed role guard"
  check_installed_copy \
    "${repo_root}/hooks/test-room-role-guard.py" \
    "${target_home}/.codex/hooks/test-room-role-guard.py" \
    "installed role guard tests"
  check_installed_copy \
    "${repo_root}/protocols/WORKFLOW_PROTOCOL.md" \
    "${target_home}/.config/room-workflow/WORKFLOW_PROTOCOL.md" \
    "installed workflow protocol"
  for role in supervisor lead; do
    check_installed_render \
      "${repo_root}/config/codex/${role}.config.toml.tmpl" \
      "${target_home}/.codex/${role}.config.toml" \
      "installed Codex ${role} template"
    for asset in instructions.md settings.json mcp.json; do
      check_installed_render \
        "${repo_root}/config/claude/${role}.${asset}.tmpl" \
        "${target_home}/.config/claude-room/${role}/${asset}" \
        "installed Claude ${role} ${asset}"
    done
    for asset in json instructions.md; do
      check_installed_render \
        "${repo_root}/config/opencode/paseo-${role}.${asset}.tmpl" \
        "${target_home}/.config/opencode/paseo-${role}.${asset}" \
        "installed OpenCode ${role} ${asset}"
    done
  done
  for role in supervisor lead; do
    if rg -q '^\[mcp_servers\.paseo\]$' \
      "${target_home}/.codex-runtime/${role}/config.toml"; then
      pass "${role} role MCP present"
    else
      fail "${role} role MCP missing"
    fi
  done
  if rg -q '^\[mcp_servers\.paseo\]$' \
    "${target_home}/.codex-runtime/peer/config.toml"; then
    fail "peer unexpectedly has Paseo MCP"
  else
    pass "peer has no Paseo MCP"
  fi
fi

if ((failures)); then
  printf '%d check group(s) failed\n' "$failures" >&2
  exit 1
fi
pass "doctor complete"
