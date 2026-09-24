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

zshenv_status=""
zprofile_status=""
zshrc_status=""

check_zsh_startup_fragment() {
  local target="$1"
  local destination="${target_home}/.${target}"
  local manager="${repo_root}/scripts/manage_zshrc.py"
  local status

  status="$(python3 "$manager" "$destination" --target "$target" --check)"
  case "$status" in
    unchanged|changed) ;;
    *)
      printf 'unexpected zsh PATH guard status: %s\n' "$status" >&2
      return 1
      ;;
  esac
  if [[ "$target" == "zshenv" ]]; then
    zshenv_status="$status"
  elif [[ "$target" == "zprofile" ]]; then
    zprofile_status="$status"
  else
    zshrc_status="$status"
  fi
}

check_zsh_startup_fragments() {
  # Validate all startup files before any installer mutation, so malformed markers
  # fail closed without a partial install or backup.
  check_zsh_startup_fragment zshenv
  check_zsh_startup_fragment zprofile
  check_zsh_startup_fragment zshrc
}

check_paseo_config_render() {
  local destination="${target_home}/.paseo/config.json"
  local rendered
  rendered="$(mktemp)"
  if ! python3 "${repo_root}/scripts/render_template.py" \
      "${repo_root}/config/paseo/config.json.tmpl" \
      "$rendered" --home "$target_home" \
      --preserve-json-from "$destination" \
      --preserve-existing-json-key pluginsEnabled \
      --preserve-existing-json-key plugins; then
    unlink "$rendered"
    return 1
  fi
  unlink "$rendered"
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
  if [[ "$kind" == "render" || "$kind" == "render-paseo-config" ]]; then
    local render_args=(
      "$source" "$destination" --home "$target_home"
    )
    if [[ "$kind" == "render-paseo-config" ]]; then
      render_args+=(--preserve-existing-json-key pluginsEnabled
                    --preserve-existing-json-key plugins)
    fi
    python3 "${repo_root}/scripts/render_template.py" "${render_args[@]}"
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

apply_zsh_startup_fragment() {
  local target="$1"
  local status
  local destination="${target_home}/.${target}"
  local manager="${repo_root}/scripts/manage_zshrc.py"

  if [[ "$target" == "zshenv" ]]; then
    status="$zshenv_status"
  elif [[ "$target" == "zprofile" ]]; then
    status="$zprofile_status"
  else
    status="$zshrc_status"
  fi
  if [[ "$status" == "unchanged" ]]; then
    printf 'KEEP managed zsh PATH guard %s\n' "$destination"
    return 0
  fi

  printf '%s %s\n' "$mode" "$destination"
  [[ "$mode" == "apply" ]] || return 0
  mkdir -p "$(dirname "$destination")"
  backup_existing "$destination"
  python3 "$manager" "$destination" --target "$target" --apply >/dev/null
}

apply_zsh_startup_fragments() {
  apply_zsh_startup_fragment zshenv
  apply_zsh_startup_fragment zprofile
  apply_zsh_startup_fragment zshrc
}

check_zsh_startup_fragments
check_paseo_config_render

install_file "${repo_root}/config/paseo/config.json.tmpl" \
  "${target_home}/.paseo/config.json" 600 render-paseo-config
printf 'PRESERVE host-only Paseo plugin settings when present\n'
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

for executable in claude-room codex-room codex-room-sync paseo-room-mcp paseo-room-workflow opencode-paseo-room opencode-paseo-peer; do
  install_file "${repo_root}/bin/${executable}" \
    "${target_home}/.local/bin/${executable}" 755
done
install_file "${repo_root}/bin/room_workflow.py" \
  "${target_home}/.local/bin/room_workflow.py" 644
install_file "${repo_root}/bin/room_attention.py" \
  "${target_home}/.local/bin/room_attention.py" 644
install_file "${repo_root}/bin/room_land.py" \
  "${target_home}/.local/bin/room_land.py" 644
install_file "${repo_root}/bin/paseo-room-deny" \
  "${target_home}/.local/share/paseo-room-bin/paseo" 755

apply_zsh_startup_fragments

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
