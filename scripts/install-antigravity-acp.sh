#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target_home="${PASEO_KIT_HOME:-${HOME}}"
target="${target_home}/.local/share/antigravity-acp"
mode="dry-run"

while (($#)); do
  case "$1" in
    --dry-run) mode="dry-run" ;;
    --apply) mode="apply" ;;
    -h|--help)
      printf 'usage: %s [--dry-run|--apply]\n' "$0"
      exit 0
      ;;
    *) exit 2 ;;
  esac
  shift
done

repository="$(jq -r '.antigravity_acp.repository' "${repo_root}/versions.lock.json")"
commit="$(jq -r '.antigravity_acp.commit' "${repo_root}/versions.lock.json")"

case "$(uname -s)/$(uname -m)" in
  Darwin/arm64) build="build:mac-arm64" ;;
  Darwin/x86_64) build="build:mac-x64" ;;
  Linux/aarch64|Linux/arm64) build="build:linux-arm64" ;;
  Linux/x86_64) build="build:linux-x64" ;;
  *)
    printf 'Unsupported platform: %s/%s\n' "$(uname -s)" "$(uname -m)" >&2
    exit 1
    ;;
esac

printf '%s clone %s at %s into %s\n' "$mode" "$repository" "$commit" "$target"
printf '%s bun install --frozen-lockfile; bun run %s\n' "$mode" "$build"
[[ "$mode" == "apply" ]] || exit 0

command -v git >/dev/null
command -v bun >/dev/null
command -v jq >/dev/null
if [[ -e "$target" ]]; then
  printf 'Target already exists; refusing to overwrite: %s\n' "$target" >&2
  exit 1
fi

mkdir -p "$(dirname "$target")"
git clone "$repository" "$target"
git -C "$target" checkout --detach "$commit"
(cd "$target" && bun install --frozen-lockfile && bun run "$build")
