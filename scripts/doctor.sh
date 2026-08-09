#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mode="${1:---repo}"
target_home="${PASEO_KIT_HOME:-${HOME}}"
failures=0

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

case "$mode" in
  --repo|--preflight|--live) ;;
  *) printf 'usage: %s [--repo|--preflight|--live]\n' "$0" >&2; exit 2 ;;
esac

python3 "${repo_root}/tests/test_portability.py" || failures=$((failures + 1))
python3 "${repo_root}/tests/test_proxy_handback.py" || failures=$((failures + 1))
python3 -m py_compile \
  "${repo_root}/hooks/room-role-guard.py" \
  "${repo_root}/hooks/test-room-role-guard.py" \
  "${repo_root}/bin/codex-room-sync" \
  "${repo_root}/bin/paseo-room-mcp" \
  "${repo_root}/scripts/render_template.py" || failures=$((failures + 1))
bash -n \
  "${repo_root}/bin/claude-room" \
  "${repo_root}/bin/codex-room" \
  "${repo_root}/bin/opencode-paseo-room" \
  "${repo_root}/bin/opencode-paseo-peer" \
  "${repo_root}/bin/paseo-room-deny" \
  "${repo_root}/scripts/install.sh" \
  "${repo_root}/scripts/install-antigravity-acp.sh" || failures=$((failures + 1))
python3 "${repo_root}/hooks/test-room-role-guard.py" || failures=$((failures + 1))

if [[ "$mode" == "--preflight" || "$mode" == "--live" ]]; then
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
fi

if [[ "$mode" == "--live" ]]; then
  if paseo status --json >/dev/null; then
    pass "Paseo daemon reachable"
  else
    fail "Paseo daemon unavailable"
  fi
  if jq -e '.daemon.mcp.enabled == true and .daemon.mcp.injectIntoAgents == false' \
    "${target_home}/.paseo/config.json" >/dev/null; then
    pass "global Paseo MCP injection disabled"
  else
    fail "unexpected Paseo MCP injection config"
  fi
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
