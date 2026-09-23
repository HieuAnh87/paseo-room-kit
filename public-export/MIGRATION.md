# Fresh-history publication workflow

The exported tree is self-validating. From its root, run the focused tests,
doctor, and scanner before staging anything:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tests/test_public_export.py
./scripts/doctor.sh --repo
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_public_artifact.py .
```

Then create a separate publication repository only after reviewing the exact
file list, generated manifest, scanner output, and staged diff:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/export_public_kit.py /tmp/public-room-kit
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_public_artifact.py /tmp/public-room-kit
cd /tmp/public-room-kit
git init
git status --short
git add .
git diff --cached --check
git diff --cached
git commit -m "Publish reusable Paseo room kit"
```

Use a fresh history. Do not copy private history, configure a remote, or push
from the export workflow. Add a remote and publish only after an owner has
supplied the intended repository owner and name, confirmed whether to publish,
chosen the visibility and license, and reviewed the staged candidate. If a correction is needed, change the
allowlisted source, export to a fresh empty directory, and repeat validation.

The installer applies role-only PATH guards to `~/.zshenv`, `~/.zprofile`,
and `~/.zshrc`; it never restarts the Paseo daemon. Existing startup files are
backed up only when their managed block materially changes, and `--force` is
not required for this repair.

Before activating an existing installation, review that all custom internal
providers have `paseoTools.enabled=false` and that installed proxy, guard,
protocol, and rendered Supervisor/Lead templates match canonical sources.
Version-1 leases migrate lazily; never copy active leases, decision history,
Peer callback receipts, credentials, agent records, or host identity.

After a deliberate restart, use `inspect_slp_ownership` to identify legacy
orphan Leads by workspace + parentage + lease. Use digest-fenced
`retire_legacy_lead` only after explicit Human-authorized checkpoint or
replacement. If an expected Peer callback does not render, invoke
`recover_peer_callbacks` once; do not replace event-driven operation with
polling. No plugin migration is required, and any future plugin must remain a
thin UI over protected operations.
