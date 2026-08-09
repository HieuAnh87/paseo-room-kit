#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target_home="${PASEO_KIT_HOME:-${HOME}}"
mode="dry-run"
force=0

usage() {
  printf 'usage: %s [--dry-run|--apply] [--force]\n' "$0"
}

while (($#)); do
  case "$1" in
    --dry-run) mode="dry-run" ;;
    --apply) mode="apply" ;;
    --force) force=1 ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
  shift
done

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_root="${target_home}/.paseo-room-kit-backups/${timestamp}"

backup_existing() {
  local destination="$1"
  [[ -e "$destination" || -L "$destination" ]] || return 0
  local relative="${destination#${target_home}/}"
  local backup="${backup_root}/${relative}"
  mkdir -p "$(dirname "$backup")"
  cp -p "$destination" "$backup"
}

install_file() {
  local source="$1"
  local destination="$2"
  local file_mode="$3"
  local kind="${4:-copy}"

  if [[ -e "$destination" || -L "$destination" ]]; then
    if ((force == 0)); then
      printf 'SKIP existing %s\n' "$destination"
      return 0
    fi
  fi

  printf '%s %s\n' "$mode" "$destination"
  [[ "$mode" == "apply" ]] || return 0
  mkdir -p "$(dirname "$destination")"
  backup_existing "$destination"
  if [[ "$kind" == "render" ]]; then
    python3 "${repo_root}/scripts/render_template.py" \
      "$source" "$destination" --home "$target_home"
  else
    cp -p "$source" "$destination"
  fi
  chmod "$file_mode" "$destination"
}

install_if_missing() {
  local source="$1"
  local destination="$2"
  local file_mode="$3"
  if [[ -e "$destination" || -L "$destination" ]]; then
    printf 'KEEP runtime state %s\n' "$destination"
    return 0
  fi
  printf '%s %s\n' "$mode" "$destination"
  [[ "$mode" == "apply" ]] || return 0
  mkdir -p "$(dirname "$destination")"
  cp -p "$source" "$destination"
  chmod "$file_mode" "$destination"
}

install_file "${repo_root}/config/paseo/config.json.tmpl" \
  "${target_home}/.paseo/config.json" 600 render
install_file "${repo_root}/config/paseo/orchestration-preferences.json" \
  "${target_home}/.paseo/orchestration-preferences.json" 644

for role in supervisor lead peer; do
  install_file "${repo_root}/config/codex/${role}.config.toml.tmpl" \
    "${target_home}/.codex/${role}.config.toml" 644 render
done
for role in supervisor lead; do
  for asset in instructions.md settings.json mcp.json; do
    install_file "${repo_root}/config/claude/${role}.${asset}.tmpl" \
      "${target_home}/.config/claude-room/${role}/${asset}" 600 render
  done
done
install_file "${repo_root}/config/codex/model-instructions.md" \
  "${target_home}/.codex/model-instructions.md" 644
install_if_missing "${repo_root}/templates/codex-config.minimal.toml" \
  "${target_home}/.codex/config.toml" 600

install_file "${repo_root}/hooks/room-role-guard.py" \
  "${target_home}/.codex/hooks/room-role-guard.py" 644
install_file "${repo_root}/hooks/test-room-role-guard.py" \
  "${target_home}/.codex/hooks/test-room-role-guard.py" 644

for executable in claude-room codex-room codex-room-sync paseo-room-mcp opencode-paseo-room opencode-paseo-peer; do
  install_file "${repo_root}/bin/${executable}" \
    "${target_home}/.local/bin/${executable}" 755
done
install_file "${repo_root}/bin/paseo-room-deny" \
  "${target_home}/.local/share/paseo-room-bin/paseo" 755

install_file "${repo_root}/config/opencode/paseo-peer.json" \
  "${target_home}/.config/opencode/paseo-peer.json" 600
for role in supervisor lead; do
  install_file "${repo_root}/config/opencode/paseo-${role}.json.tmpl" \
    "${target_home}/.config/opencode/paseo-${role}.json" 600 render
  install_file "${repo_root}/config/opencode/paseo-${role}.instructions.md.tmpl" \
    "${target_home}/.config/opencode/paseo-${role}.instructions.md" 600 render
done
install_file "${repo_root}/protocols/WORKFLOW_PROTOCOL.md" \
  "${target_home}/.config/room-workflow/WORKFLOW_PROTOCOL.md" 644
install_file "${repo_root}/protocols/DISSENT_PROTOCOL.md" \
  "${target_home}/.config/room-workflow/DISSENT_PROTOCOL.md" 644
install_if_missing "${repo_root}/templates/lead-leases.empty.json" \
  "${target_home}/.config/room-workflow/lead-leases.json" 600
install_if_missing "${repo_root}/templates/SUPERVISOR_NOTEBOOK.md" \
  "${target_home}/.config/room-workflow/SUPERVISOR_NOTEBOOK.md" 600

if [[ "$mode" == "apply" ]] && command -v codex >/dev/null 2>&1; then
  for role in supervisor lead peer; do
    HOME="$target_home" "${target_home}/.local/bin/codex-room-sync" "$role"
  done
fi

if [[ "$mode" == "apply" ]]; then
  printf 'Installed. Review %s before any deliberate Paseo restart.\n' \
    "${target_home}/.paseo/config.json"
else
  printf 'Dry run only. Re-run with --apply after review.\n'
fi
