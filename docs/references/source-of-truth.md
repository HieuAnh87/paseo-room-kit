# Source-of-truth map

## Paseo

| Path | Vai trò |
|---|---|
| `~/.paseo/config.json` | daemon, provider registry, MCP injection, browser/relay settings |
| `~/.paseo/orchestration-preferences.json` | semantic routing categories và freeform preferences |
| `~/.paseo/projects/workspaces.json` | workspace registry |
| `~/.paseo/projects/projects.json` | project registry |
| `~/.paseo/agents/` | agent state files |
| `~/.paseo/daemon.log` | daemon log; có thể chứa metadata/prompt |

## Codex

| Path | Vai trò |
|---|---|
| `~/.codex/config.toml` | baseline, MCP, trusted projects, plugins/features |
| `~/.codex/supervisor.config.toml` | Supervisor role overlay |
| `~/.codex/lead.config.toml` | Lead role overlay |
| `~/.codex/peer.config.toml` | Peer role overlay |
| `~/.codex/model-instructions.md` | shared agent behavior/instructions |
| `~/.codex/AGENTS.md` | shared Codex context |
| `~/.codex/hooks/room-role-guard.py` | deterministic role, route, ownership and lease guard |
| `~/.codex-runtime/` | generated role runtime, not canonical source |

## Launchers/protocol

| Path | Vai trò |
|---|---|
| `~/.local/bin/codex-room` | role launcher |
| `~/.local/bin/codex-room-sync` | runtime config materializer |
| `~/.local/bin/paseo-room-mcp` | role-aware Paseo MCP proxy; primary enforcement boundary |
| `~/.local/share/paseo-room-bin/paseo` | room-runtime CLI deny wrapper; allows only Paseo Codex lifecycle bridge |
| `~/.local/bin/opencode-paseo-peer` | OpenCode pure ACP wrapper |
| `~/.config/room-workflow/WORKFLOW_PROTOCOL.md` | authority, labels, lease and terminal-state contract |
| `~/.config/room-workflow/lead-leases.json` | active/pending Lead lease registry |
| `~/.config/room-workflow/DISSENT_PROTOCOL.md` | Lead–Peer dissent law |
| `~/.config/room-workflow/SUPERVISOR_NOTEBOOK.md` | durable governance learning |
| `~/.config/room-workflow/workspaces/` | workspace authority/purpose records |

## External ACP

| Path | Vai trò |
|---|---|
| `~/.local/share/antigravity-acp/` | cloned ACP source, dependencies, compiled binary and sibling `agy` |
| `~/.config/opencode/paseo-peer.json` | OpenCode Peer config; currently intentionally minimal |
