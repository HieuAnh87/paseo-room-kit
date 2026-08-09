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
