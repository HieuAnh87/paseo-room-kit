# Paseo Room Kit

Portable, private-by-default setup kit for the following orchestration topology:

```text
Human → Supervisor → Lead → Peer
```

The repository contains role profiles, provider routing, the role-aware Paseo MCP proxy, deterministic authority/lease guard, workflow protocols, launchers, validation tests, and migration instructions. It does not contain agent history, credentials, active leases, daemon logs, workspaces, compiled provider binaries, or a machine-local Codex MCP configuration.

## Safety model

- Human talks to the Supervisor front door.
- Supervisor owns governance, topology, lifecycle, and Human handback.
- Lead is the sole engineering owner inside one project workspace.
- Peer performs one bounded assignment and returns evidence to Lead.
- Supervisor and Lead receive the role-aware Paseo MCP proxy.
- The Human can choose either the Codex Supervisor or the isolated Claude Opus Supervisor front door.
- Peer receives no Paseo control MCP.
- Final Lead result uses `handback_to_parent`; Lead never supplies a Supervisor ID.
- Native runtime state such as `idle` or `DONE` is not engineering acceptance.
- Successful final handback marks Lead `HANDBACK_READY`; workspace archive releases the Lead lease.
- Repository-mutating rooms default to managed worktrees so logical rooms do not share one dirty checkout.

This is deterministic workflow isolation for cooperative agents, not an OS security sandbox against a hostile process.

## Fresh-machine setup

Read [MIGRATION.md](MIGRATION.md), then:

```bash
./scripts/doctor.sh --preflight
./scripts/install.sh --dry-run
./scripts/install-antigravity-acp.sh --dry-run
./scripts/install.sh --apply
./scripts/doctor.sh --live
```

The installer never restarts Paseo. Restart the daemon only after reviewing the rendered config, confirming there is no active agent work, and explicitly choosing to do so.

After the restart, `claude-supervisor/claude-opus-4-8` is available as a
parallel Human-facing front door. Stable Lead routing remains
`codex-lead/gpt-5.6-sol`. An owner-explicit pilot can instead use
`claude-lead/claude-sonnet-5[1m]` at High with a 300K auto-compact window;
selecting Claude for the Supervisor still does not transfer engineering
ownership into the Supervisor.

## Existing-machine update

The installer skips existing files by default. Use `--force` only after reviewing the dry-run; replaced files are copied to `~/.paseo-room-kit-backups/<timestamp>/`.

```bash
./scripts/install.sh --dry-run --force
./scripts/install.sh --apply --force
```

Runtime state files such as `lead-leases.json` and `SUPERVISOR_NOTEBOOK.md` are never overwritten.

## Repository validation

```bash
./scripts/doctor.sh --repo
```

Detailed architecture and operations notes are under [docs/](docs/README.md). Version pins are recorded in [versions.lock.json](versions.lock.json).
