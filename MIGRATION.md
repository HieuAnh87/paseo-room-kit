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

Compare installed versions with `versions.lock.json`. The Paseo pin is now
`0.9.1`; the root lock's `captured_at` remains the last full tool-inventory
snapshot, because this bump intentionally refreshes Paseo only. Do not treat
the other pins as freshly captured. A newer version is not automatically
wrong, but provider/model schemas and MCP behavior must be revalidated.

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

The canonical provider template sets `paseoTools.enabled=false` on every
internal custom Supervisor, Lead, Peer, and UI provider. This is the Paseo 0.9.1
per-provider defense: even if global native tool injection is enabled later,
room roles receive only the role-aware proxy control surface.

The apply step also manages one marked PATH guard in each `~/.zshenv`,
`~/.zprofile`, and `~/.zshrc`. The guard prepends `~/.local/share/paseo-room-bin` only when
`PASEO_ROOM_ROLE` is non-empty, covering non-interactive zsh shells as well as
cooperative interactive PATH reordering. Dry-run does not create or change
any startup file. Apply removes stale or duplicate managed blocks, preserves
unrelated content, and backs up each existing file that materially changes
under the same `~/.paseo-room-kit-backups/<timestamp>/` root; missing files are
created without a backup. This repair does not require `--force`, and the
installer performs no daemon restart.

If `~/.codex/config.toml` already exists, it is preserved unless `--force` is explicitly supplied. Add machine-local MCP servers and credentials there after installation; never commit that file.

## 6. Validate before restart

```bash
./scripts/doctor.sh --live
```

Run preflight/live version checks from an ordinary, unwrapped owner shell.
Managed role shells fail closed because their deny wrapper intentionally blocks
direct CLI and daemon probes; they do not report an unverified version as a
successful check.

Review:

- Paseo provider catalog;
- `injectIntoAgents=false`;
- every internal custom provider has `paseoTools.enabled=false`;
- installed proxy, guard, guard tests, protocol, and rendered Supervisor/Lead
  templates match canonical repository sources;
- Supervisor/Lead role runtimes contain `mcp_servers.paseo`;
- Peer runtime does not;
- route guard tests pass;
- no active/pending Lead lease exists unexpectedly.

For an existing SLP installation, review `inspect_slp_ownership` before
replacement. A custom Lead is healthy only when workspace, Paseo-owned
parentage, managed lease, `room_kind`, and epoch agree. After an explicit
Human-authorized checkpoint/replacement, use the returned authority digest with
`retire_legacy_lead` to soft-archive an orphan that is not the managed lease
holder. Do not use native `idle` as ownership evidence.

Peer callbacks remain event-driven. If one expected callback does not render,
the Lead may call `recover_peer_callbacks` once. The protected recovery reads
durable activity once and persists a digest-deduplicated receipt; it is not a
polling loop.

## 7. Restart deliberately

Paseo must reload provider config before new sessions use it. Restart only when no active agent needs preservation. After restart, rerun `./scripts/doctor.sh --live` and perform the read-only Supervisor → Lead → Peer smoke test documented in `docs/09-operations-runbook.md`.

The optional Room Flow plugin is installed separately on a matching 0.9.1
daemon and app. It displays the existing lease and Paseo state without owning
or mirroring lifecycle authority.

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
