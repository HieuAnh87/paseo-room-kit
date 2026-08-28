# Security and privacy

This repository is intended to remain private unless all provider names, internal service names, historical notes, and organization-specific documentation are separately reviewed for publication.

## Never commit

- `~/.codex/config.toml` from a real machine;
- auth files or provider credential directories;
- `.env` files;
- database URLs, API keys, bearer tokens, cookies, or auth headers;
- `~/.paseo/agents`, `projects`, `workspaces`, `daemon.log`, or PID files;
- active `lead-leases.json`;
- `SUPERVISOR_NOTEBOOK.md` containing real work history;
- uploads, transcripts, `models_cache.json`, compiled binaries, or `node_modules`.

## Before every push

```bash
./scripts/doctor.sh --repo
git diff --cached
git grep -nE 'gh[pousr]_[A-Za-z0-9_]+|sk-[A-Za-z0-9_-]+|AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY'
```

Use GitHub secret scanning where available. If a secret is ever committed, revoke/rotate it first; deleting it from the latest commit is not sufficient.

## Public artifact review

The generic candidate is exported through an explicit allowlist and checked
with:

```bash
python3 scripts/export_public_kit.py /tmp/public-room-kit
python3 scripts/check_public_artifact.py /tmp/public-room-kit
```

The scanner rejects accepted private names, personal Unix/Windows home paths,
UUIDs and runtime identity shapes, non-synthetic corporate email, credential,
auth, token, private-key, and database-URI shapes, plus source-only audit or
inventory metadata, internal/private endpoints, and VCS metadata. It also
requires the generated manifest to match the reviewed allowlist. Clearly
synthetic placeholders such as `<TOKEN>`,
`test@example.com`, `$HOME`, and the all-zero UUID are allowed so generic
tests remain readable. Ordinary public HTTP(S) links—including localhost,
Paseo, and upstream links—are allowed only as links; URL user-info and
sensitive query values still fail the scan.

The export manifest enumerates every file, records its mode, and records a
digest for each payload. The publication workflow uses `git init` in the
fresh output directory only after review; the exporter never creates a
repository, changes remotes, or pushes.
