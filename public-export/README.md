# Public Paseo room kit

This is the reusable, generic portion of a role-aware engineering room:

```text
Human → Lead → Peer
        ↑ optional bound Supervisor governance
```

The export contains the actual launchers, role configuration templates, hooks,
workflow protocols, empty state templates, installers, render/export/scanner
scripts, and their tests. The public overlays in this tree provide generic
README, migration, security, architecture, and workflow guidance without
carrying local project records.

The reviewable candidate is recorded in `.public-export/allowlist.json`.
`PUBLIC_EXPORT_MANIFEST.json` is generated for each export and enumerates every
payload file, mode, byte count, and digest. The compatibility lock is included
because it contains reusable tool/version pins; the source capture timestamp
and machine inventory are intentionally omitted.

Run the validation from the exported root:

```bash
./scripts/doctor.sh --repo
PYTHONDONTWRITEBYTECODE=1 python3 tests/test_public_export.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_public_artifact.py .
```

To make another reviewed candidate from this tree:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/export_public_kit.py /tmp/public-room-kit
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_public_artifact.py /tmp/public-room-kit
```

The exporter requires a caller-selected new or empty directory, preserves
executable modes, and performs no Git initialization, remote changes, or push.
The installer manages role-only PATH guards in `~/.zshenv`, `~/.zprofile`, and `~/.zshrc`
without restarting the Paseo daemon; ordinary human shells retain the real
Paseo CLI.
Managed lifecycle uses a version-2 lease registry with room kind, work epoch,
revision, and evidence digest. Native Peer callbacks remain primary;
`recover_peer_callbacks` is the one-shot digest-deduplicated recovery path.
Every internal custom provider sets Paseo 0.11.2 `paseoTools.enabled=false`, so
the role-aware proxy remains its only control surface if global injection is
enabled later. Legacy Lead cleanup is workspace/parentage/lease fenced and does
not trust native idle status. A future plugin may only be a thin UI over these
protected operations.
Public upstream references are limited to ordinary documentation links such
as the [Paseo documentation](https://paseo.sh/docs) and an
[upstream repository](https://github.com/example/upstream).

## Repository workflow and direct authority

From an ordinary owner shell, preview then create missing project tactics:

```bash
paseo-room-workflow init /path/to/project
paseo-room-workflow init /path/to/project --apply
```

Review `.orchestration/workspace-protocol.md` and `workflow.json` before binding an existing root Lead. Preview with `paseo-room-workflow bind --lead-id LEAD_ID --task-class bounded`, then add `--apply`. Add `--supervisor-id SUPERVISOR_ID` for an independent observer; neither form reparents agents. The compatible Supervisor-created Lead path remains available.

`bindings` shows authority versions; `decisions` shows Human choices. `decide`, `reopen`, `resolve`, `archive` and `withdraw` take a JSON request and preview unless `--apply` is supplied. Common gates bind protocol, runtime metadata, report correlation and review candidate across providers. No repository policy preserves legacy behavior; initialize it before binding to enable candidate gates. See [workflow protocol](protocols/WORKFLOW_PROTOCOL.md) for schemas and limits.

## UI specialists

UI defaults to `antigravity-cli/gemini-3.8-flash` High. Install the Antigravity CLI provider plugin separately and verify its live catalog before dispatch; this kit only configures it. `ui_opus` selects `claude-ui/claude-opus-5-5` High with a non-empty `ui_choice_reason`. Both are engineering Peers; the independent Claude Reviewer remains read-only. No automatic provider fallback. Antigravity tool/subagent boundaries are cooperative assignment rules, not the deterministic Claude hooks or OS isolation.
