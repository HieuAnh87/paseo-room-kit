# Public Paseo room kit

This is the reusable, generic portion of a role-aware engineering room:

```text
Human → Supervisor → Lead → Peer
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
Public upstream references are limited to ordinary documentation links such
as the [Paseo documentation](https://paseo.sh/docs) and an
[upstream repository](https://github.com/example/upstream).
