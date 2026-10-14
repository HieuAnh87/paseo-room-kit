# Paseo Room Kit

Portable, private-by-default setup kit for the following orchestration topology:

```text
Human → Lead → Peer
        ↑ optional bound Supervisor governance
```

The repository contains role profiles, provider routing, the role-aware Paseo MCP proxy, deterministic authority/lease guard, workflow protocols, launchers, validation tests, and migration instructions. It does not contain agent history, credentials, active leases, daemon logs, workspaces, compiled provider binaries, or a machine-local Codex MCP configuration.

## Safety model

- Human can assign a root Lead directly or use an optional Supervisor front door.
- Supervisor owns governance, topology, lifecycle, and Human handback.
- Lead is the sole engineering owner inside one project workspace.
- Peer performs one bounded assignment and returns evidence to Lead.
- Supervisor and Lead receive the role-aware Paseo MCP proxy.
- The Human can choose Codex or isolated Claude Opus Supervisor front doors.
- Peer receives no Paseo control MCP.
- Final Lead result uses `submit_work_result` (`handback_to_parent` remains an alias); the active binding selects governance delivery or the direct Human queue.
- Managed lifecycle truth is fenced by `room_kind`, work epoch, revision, and
  evidence digest in the version-2 lease registry.
- Native runtime state such as `idle` or `DONE` is not engineering acceptance.
- Choose L, LP (default for new root bindings), or SLP at a Human checkpoint;
  L blocks Peer dispatch and cannot weaken repository review gates. See
  [modes and callbacks](docs/22-modes-and-callback.md).
- Native scoped Peer callbacks are primary; the trusted `room-callback` plugin
  supplies assignment-fenced lifecycle notifications when scoped tools are absent.
  Dispatch fails closed if neither transport is ready. `recover_peer_callbacks` is a bounded,
  digest-deduplicated recovery path when an expected callback does not render.
- Human accept/abandon, bounded reopen, uncertain delivery resolution, and
  archive use protected epoch-aware operations; generic prompt/archive bypasses
  are denied.
- Custom internal SLP providers set Paseo 0.11.2 `paseoTools.enabled=false`;
  the role-aware proxy remains their only Paseo control surface even if global
  tool injection is enabled later.
- Legacy Lead visibility and cleanup use workspace + parentage + lease authority
  and a digest-fenced soft archive, never native `idle`.
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

Run preflight/live version checks from an ordinary, unwrapped owner shell.
Managed role shells fail closed instead of bypassing the deny wrapper or
reporting an unverified CLI/daemon version as healthy.

The installer never restarts Paseo. It manages marked, idempotent PATH guards
in `~/.zshenv`, `~/.zprofile`, and `~/.zshrc`; they prepend the room deny-wrapper directory
only when `PASEO_ROOM_ROLE` is non-empty, so ordinary human shells keep the
real Paseo CLI. Existing startup files are backed up under the normal
`~/.paseo-room-kit-backups/<timestamp>/` root before their first material
change, and this security repair does not require `--force`. Restart the
daemon only after reviewing the rendered config, confirming there is no active
agent work, and explicitly choosing to do so.

After reload, `claude-supervisor/claude-opus-5-5` is available at High or XHigh
as a parallel Human-facing front door. Codex Supervisor also offers High or
XHigh on `gpt-6.1-sol`; both Supervisors default to High. The stable Lead uses
`gpt-6.1-sol` with High, XHigh (default) or Max (`codex-lead`). A Supervisor may
autonomously select `claude-lead/claude-opus-5-5` with High, XHigh (default) or Max for a new bounded
objective, with a 300K auto-compact window; an explicit owner preference wins.
Each Lead owns one objective/workstream in one workspace, including its bounded
Peer tasks and same-objective follow-ups. Selecting Claude for the Supervisor
still does not transfer engineering ownership into the Supervisor.

In the standard stack, bounded implementation/search Peers use GPT-6 Luna
High (default), XHigh or Max, candidate review uses a fresh read-only Claude Opus 5.5 High Reviewer,
and an independent GPT-6 Luna Medium Watcher scans managed rooms daily at 01:00 Asia/Ho_Chi_Minh.


## Existing-machine update

The installer skips existing files by default. Use `--force` only after reviewing the dry-run; replaced files are copied to `~/.paseo-room-kit-backups/<timestamp>/`.

The managed zsh startup-file PATH repair is an exception: `--apply` installs
or updates it without `--force`, removes stale duplicate managed blocks, and
does not create a backup when the exact managed block is already present.

```bash
./scripts/install.sh --dry-run --force
./scripts/install.sh --apply --force
```

Runtime state files such as `lead-leases.json` and `SUPERVISOR_NOTEBOOK.md` are never overwritten.
Existing version-1 leases are upgraded lazily and fail closed if malformed;
decision history, callback receipts, active epochs, and machine identity are
never copied from the repository or public export.

## Repository validation

```bash
./scripts/doctor.sh --repo
```

## Public export

The repository contains a separately reviewed candidate under `public-export/`.
It exports the reusable launchers, role configuration, hooks, protocols,
templates, installers, validation scripts, and tests, with public overlays for
the top-level docs. Export it to a new or empty directory, then scan the
result:

```bash
python3 scripts/export_public_kit.py /tmp/public-room-kit
python3 scripts/check_public_artifact.py /tmp/public-room-kit
```

The exporter uses an explicit file allowlist, preserves executable modes, and
does not copy runtime, session, audit, history, inventory, or notebook
material. It refuses traversal, symlinks, binaries, duplicate destinations,
missing/non-regular sources, and unsafe or non-empty destinations. The output
manifest enumerates every exported file. See the candidate's
[`MIGRATION.md`](public-export/MIGRATION.md) for a fresh-history workflow; the
exporter does not initialize a repository, change remotes, or push.

Detailed architecture and operations notes are under [docs/](docs/README.md). Version pins are recorded in [versions.lock.json](versions.lock.json).

## Repository workflow and direct authority

From an ordinary owner shell, preview then create missing project tactics:

```bash
paseo-room-workflow init /path/to/project
paseo-room-workflow init /path/to/project --apply
```

Review `.orchestration/workspace-protocol.md` and `workflow.json` before binding an existing root Lead. Preview with `paseo-room-workflow bind --lead-id LEAD_ID --task-class bounded`, then add `--apply`. Add `--supervisor-id SUPERVISOR_ID` for an independent observer; neither form reparents agents. The compatible Supervisor-created Lead path remains available.

`bindings` shows authority versions; `decisions` shows Human choices. `decide`, `reopen`, `resolve`, `archive` and `withdraw` take a JSON request and preview unless `--apply` is supplied. Common gates bind protocol, runtime metadata, report correlation and review candidate across providers. No repository policy preserves legacy behavior; initialize it before binding to enable candidate gates. See [workflow protocol](protocols/WORKFLOW_PROTOCOL.md) for schemas and limits.

Managed asks and Peer attention signals are available through the proxy; the owner shell can use `paseo-room-workflow asks --lead-id LEAD_ID` and `answer-ask REQUEST.json [--apply]`. A separate `land-prepare`/`land-apply` path can fast-forward an already accepted, committed candidate after exact Human plan approval. The optional Paseo 0.9.x Flow/Health plugin under [`plugin/`](plugin/) reads canonical state without taking authority. See [attention and land operations](docs/18-attention-and-land.md).

Human owner-shell grants allow exact Peer steering with Lead notice first and completion routed to Lead. Lead-only `resolve_peer_report` keeps material reopen requests pending until evidence-backed disposition; changed work must match the final candidate. Read-only `list_room_observations` joins brief/report/disposition and steering receipts without inferring correctness or acceptance. See [the article comparison and validation limits](docs/19-slp-article-review.md).
