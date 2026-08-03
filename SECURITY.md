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
