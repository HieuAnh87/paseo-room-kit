# Fresh-machine migration

## 1. Install prerequisites

Install and authenticate these tools independently:

- Paseo Desktop/CLI;
- Codex CLI;
- Claude Code, authenticated with `claude auth status`;
- Python 3.11+;
- Git and `jq`;
- OpenCode and Bun when using the AI Box/OpenCode routes;
- Antigravity/`agy` when using the Gemini UI route.

Credentials remain machine-local. Do not copy auth directories from another machine.

## 2. Clone privately

```bash
git clone <private-repository-url> paseo-room-kit
cd paseo-room-kit
```

## 3. Check compatibility

```bash
./scripts/doctor.sh --preflight
```

Compare installed versions with `versions.lock.json`. A newer version is not automatically wrong, but provider/model schemas and MCP behavior must be revalidated.

## 4. Install Antigravity ACP when needed

```bash
./scripts/install-antigravity-acp.sh --dry-run
./scripts/install-antigravity-acp.sh --apply
```

The script checks out the pinned source commit and builds the binary for the current macOS/Linux architecture. Authentication remains owned by `agy`.

## 5. Install room files

```bash
./scripts/install.sh --dry-run
./scripts/install.sh --apply
```

The installer renders `{{HOME}}` and the platform-specific Antigravity ACP binary path. It does not install credentials, project MCP secrets, agent history, or active lease state.

If `~/.codex/config.toml` already exists, it is preserved unless `--force` is explicitly supplied. Add machine-local MCP servers and credentials there after installation; never commit that file.

## 6. Validate before restart

```bash
./scripts/doctor.sh --live
```

Review:

- Paseo provider catalog;
- `injectIntoAgents=false`;
- Supervisor/Lead role runtimes contain `mcp_servers.paseo`;
- Peer runtime does not;
- route guard tests pass;
- no active/pending Lead lease exists unexpectedly.

## 7. Restart deliberately

Paseo must reload provider config before new sessions use it. Restart only when no active agent needs preservation. After restart, rerun `./scripts/doctor.sh --live` and perform the read-only Supervisor → Lead → Peer smoke test documented in `docs/09-operations-runbook.md`.

## 8. Supply private machine-local configuration

Keep these outside Git:

- Codex/Claude/OpenCode/Antigravity authentication;
- database and observability MCP credentials;
- API keys and auth headers;
- Paseo agent/workspace records and daemon logs;
- Supervisor notebook and active lease state.

## Publish the generic public candidate

The public exporter has its own explicit allowlist and writes only to a
caller-selected new or empty directory. Review and scan that directory before
starting a fresh publication repository:

```bash
python3 scripts/export_public_kit.py /tmp/public-room-kit
python3 scripts/check_public_artifact.py /tmp/public-room-kit
cd /tmp/public-room-kit
git init
git status --short
git add .
git diff --cached --check
git diff --cached
git commit -m "Publish generic room-kit examples"
```

Do not copy the private repository's history, configure a remote, or push from
the export workflow. Add a remote and publish only after an owner reviews the
candidate, manifest, scanner result, and staged diff; supplies the future
repository owner and name; confirms whether to publish; and chooses visibility
and licensing. If a correction is
needed, export to a fresh empty directory and repeat the review.
