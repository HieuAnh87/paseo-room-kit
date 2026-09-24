#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
INSTALL = ROOT / "scripts/install.sh"
MANAGER = ROOT / "scripts/manage_zshrc.py"
BEGIN_MARKER = "# >>> paseo-room-kit managed PATH guard >>>"
END_MARKER = "# <<< paseo-room-kit managed PATH guard <<<"
ZSHENV_BEGIN_MARKER = "# >>> paseo-room-kit managed zshenv PATH guard >>>"
ZSHENV_END_MARKER = "# <<< paseo-room-kit managed zshenv PATH guard <<<"
ZPROFILE_BEGIN_MARKER = "# >>> paseo-room-kit managed zprofile PATH guard >>>"
ZPROFILE_END_MARKER = "# <<< paseo-room-kit managed zprofile PATH guard <<<"
ZSHRC_BEGIN_MARKER = "# >>> paseo-room-kit managed zshrc PATH guard >>>"
ZSHRC_END_MARKER = "# <<< paseo-room-kit managed zshrc PATH guard <<<"


class InstallTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tempdir.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.fake_bin = self.root / "fake-bin"
        self.fake_bin.mkdir()
        self.python_bin = pathlib.Path(os.sys.executable).parent

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def run_install(
        self, mode: str, *, force: bool = False
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment.update(
            {
                "HOME": str(self.home),
                "PASEO_KIT_HOME": str(self.home),
                # Keep the installer dependencies available without allowing
                # an installed host codex to trigger runtime synchronization.
                "PATH": os.pathsep.join(
                    [
                        str(self.fake_bin),
                        str(self.python_bin),
                        "/usr/bin",
                        "/bin",
                        "/usr/sbin",
                        "/sbin",
                    ]
                ),
            }
        )
        command = ["bash", str(INSTALL), mode]
        if force:
            command.append("--force")
        return subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
        )

    def zsh_environment(self, real_bin: pathlib.Path, *, role: str | None) -> dict[str, str]:
        environment = os.environ.copy()
        environment.update(
            {
                "HOME": str(self.home),
                "ZDOTDIR": str(self.home),
                "PATH": os.pathsep.join([str(real_bin), "/usr/bin", "/bin"]),
                "TEST_REAL_BIN": str(real_bin),
            }
        )
        if role is None:
            environment.pop("PASEO_ROOM_ROLE", None)
        else:
            environment["PASEO_ROOM_ROLE"] = role
        return environment

    def test_dry_run_does_not_mutate(self) -> None:
        originals = {
            ".zshenv": "# human zshenv configuration\n",
            ".zprofile": "# human zprofile configuration\n",
            ".zshrc": "# human zshrc configuration\n",
        }
        for name, contents in originals.items():
            (self.home / name).write_text(contents, encoding="utf-8")
        before = self.snapshot_home()

        result = self.run_install("--dry-run")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.snapshot_home(), before)
        self.assertFalse((self.home / ".paseo-room-kit-backups").exists())

    def snapshot_home(self) -> dict[str, bytes]:
        return {
            path.relative_to(self.home).as_posix(): path.read_bytes()
            for path in self.home.rglob("*")
            if path.is_file()
        }

    def test_apply_inserts_once_and_backs_up_existing_files(self) -> None:
        originals = {
            ".zshenv": "# human zshenv configuration\n",
            ".zprofile": "# human zprofile configuration\n",
            ".zshrc": "# human zshrc configuration\n",
        }
        for name, contents in originals.items():
            (self.home / name).write_text(contents, encoding="utf-8")

        result = self.run_install("--apply")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for name, original in originals.items():
            contents = (self.home / name).read_text(encoding="utf-8")
            begin, end = {
                ".zshenv": (ZSHENV_BEGIN_MARKER, ZSHENV_END_MARKER),
                ".zprofile": (ZPROFILE_BEGIN_MARKER, ZPROFILE_END_MARKER),
                ".zshrc": (ZSHRC_BEGIN_MARKER, ZSHRC_END_MARKER),
            }[name]
            self.assertEqual(contents.count(begin), 1)
            self.assertEqual(contents.count(end), 1)
            self.assertIn(original.rstrip("\n"), contents)

        backup_files = {
            path.name: path
            for path in (self.home / ".paseo-room-kit-backups").glob("*/.*")
            if path.is_file()
        }
        self.assertEqual(set(backup_files), set(originals))
        self.assertEqual(
            {path.parent for path in backup_files.values()},
            {next(iter(backup_files.values())).parent},
        )
        for name, original in originals.items():
            self.assertEqual(backup_files[name].read_text(encoding="utf-8"), original)

    def test_force_apply_preserves_host_only_paseo_plugin_settings(self) -> None:
        paseo = self.home / ".paseo"
        paseo.mkdir()
        installed = paseo / "config.json"
        original = b'{"pluginsEnabled":true,"plugins":{"room-flow":{"source":"/tmp/room-flow"}}}\n'
        installed.write_bytes(original)

        result = self.run_install("--apply", force=True)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        rendered = json.loads(installed.read_text(encoding="utf-8"))
        self.assertIs(rendered["pluginsEnabled"], True)
        self.assertEqual(rendered["plugins"], {"room-flow": {"source": "/tmp/room-flow"}})
        providers = rendered["agents"]["providers"]
        for provider_id in (
            "claude-supervisor",
            "codex-supervisor",
            "codex-lead",
            "claude-lead",
            "codex-peer",
            "opencode-peer",
            "opencode-supervisor",
            "opencode-lead",
            "gemini-ui",
        ):
            self.assertIs(providers[provider_id]["paseoTools"]["enabled"], False)
        backups = list(
            (self.home / ".paseo-room-kit-backups").glob("*/.paseo/config.json")
        )
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original)

    def test_second_apply_is_idempotent_without_another_backup(self) -> None:
        for name in (".zshenv", ".zprofile", ".zshrc"):
            (self.home / name).write_text(
                f"# human {name} configuration\n", encoding="utf-8"
            )
        first = self.run_install("--apply")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        contents = self.snapshot_home()

        second = self.run_install("--apply")

        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(self.snapshot_home(), contents)
        for name, begin in (
            (".zshenv", ZSHENV_BEGIN_MARKER),
            (".zprofile", ZPROFILE_BEGIN_MARKER),
            (".zshrc", ZSHRC_BEGIN_MARKER),
        ):
            self.assertEqual(
                (self.home / name).read_bytes().count(begin.encode()), 1
            )

    def test_apply_replaces_stale_duplicate_blocks(self) -> None:
        zshrc = self.home / ".zshrc"
        zshenv = self.home / ".zshenv"
        stale = (
            f"# before\n{BEGIN_MARKER}\nold block\n{END_MARKER}\n"
            f"# between\n{BEGIN_MARKER}\nold duplicate\n{END_MARKER}\n# after\n"
        )
        zshrc.write_text(stale, encoding="utf-8")
        zshenv.write_text(
            f"# env before\n{ZSHENV_BEGIN_MARKER}\nstale env\n"
            f"{ZSHENV_END_MARKER}\n# env after\n",
            encoding="utf-8",
        )

        result = self.run_install("--apply")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        contents = zshrc.read_text(encoding="utf-8")
        self.assertEqual(contents.count(ZSHRC_BEGIN_MARKER), 1)
        self.assertEqual(contents.count(ZSHRC_END_MARKER), 1)
        self.assertNotIn(BEGIN_MARKER, contents)
        self.assertNotIn(END_MARKER, contents)
        self.assertIn("# before\n# between\n# after\n", contents)
        self.assertNotIn("old block", contents)
        self.assertNotIn("old duplicate", contents)
        env_contents = zshenv.read_text(encoding="utf-8")
        self.assertEqual(env_contents.count(ZSHENV_BEGIN_MARKER), 1)
        self.assertEqual(env_contents.count(ZSHENV_END_MARKER), 1)
        self.assertIn("# env before\n# env after\n", env_contents)
        self.assertNotIn("stale env", env_contents)

    def test_apply_creates_missing_zsh_startup_files_without_backup(self) -> None:
        result = self.run_install("--apply")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for name, begin, end in (
            (".zshenv", ZSHENV_BEGIN_MARKER, ZSHENV_END_MARKER),
            (".zprofile", ZPROFILE_BEGIN_MARKER, ZPROFILE_END_MARKER),
            (".zshrc", ZSHRC_BEGIN_MARKER, ZSHRC_END_MARKER),
        ):
            startup_file = self.home / name
            self.assertTrue(startup_file.is_file())
            contents = startup_file.read_text(encoding="utf-8")
            self.assertEqual(contents.count(begin), 1)
            self.assertEqual(contents.count(end), 1)
        self.assertFalse((self.home / ".paseo-room-kit-backups").exists())

    def test_unbalanced_managed_markers_fail_closed_without_writing(self) -> None:
        malformed = {
            "unmatched begin": f"# before\n{ZSHRC_BEGIN_MARKER}\n# after\n",
            "orphan end": f"# before\n{ZSHRC_END_MARKER}\n# after\n",
            "nested begin": (
                f"{ZSHRC_BEGIN_MARKER}\n"
                f"{ZSHENV_BEGIN_MARKER}\n"
                f"{ZSHENV_END_MARKER}\n"
                f"{ZSHRC_END_MARKER}\n"
            ),
        }
        for label, contents in malformed.items():
            with self.subTest(label=label):
                path = self.root / f"{label.replace(' ', '-')}.zshrc"
                path.write_text(contents, encoding="utf-8")
                before = path.read_bytes()
                result = subprocess.run(
                    [
                        sys.executable,
                        str(MANAGER),
                        str(path),
                        "--target",
                        "zshrc",
                        "--apply",
                    ],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(path.read_bytes(), before)

        zshrc = self.home / ".zshrc"
        zshrc.write_text(malformed["unmatched begin"], encoding="utf-8")
        before_home = self.snapshot_home()
        result = self.run_install("--apply")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.snapshot_home(), before_home)
        self.assertFalse((self.home / ".paseo-room-kit-backups").exists())

    def test_apply_preserves_symlink_and_atomically_replaces_its_target(self) -> None:
        target = self.root / "shared-zprofile"
        original = "# shared human zprofile configuration\n"
        target.write_text(original, encoding="utf-8")
        zprofile = self.home / ".zprofile"
        zprofile.symlink_to(target)
        before_inode = target.stat().st_ino

        result = self.run_install("--apply")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(zprofile.is_symlink())
        self.assertNotEqual(target.stat().st_ino, before_inode)
        self.assertIn(ZPROFILE_BEGIN_MARKER, target.read_text(encoding="utf-8"))
        backups = list(
            (self.home / ".paseo-room-kit-backups").glob("*/.zprofile")
        )
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), original)

    def test_deny_wrapper_uses_a_real_newline_escape(self) -> None:
        contents = (ROOT / "bin/paseo-room-deny").read_text(encoding="utf-8")
        self.assertIn(r"disabled.\n' >&2", contents)
        self.assertNotIn(r"disabled.\\n' >&2", contents)

    @unittest.skipUnless(shutil.which("zsh"), "zsh is unavailable")
    def test_login_noninteractive_guard_survives_zprofile_path_mutation(self) -> None:
        real_bin = self.root / "real-bin"
        real_bin.mkdir()
        real_paseo = real_bin / "paseo"
        real_paseo.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        real_paseo.chmod(0o755)
        (self.home / ".zprofile").write_text(
            'PATH="$TEST_REAL_BIN:$PATH"\nexport PATH\n',
            encoding="utf-8",
        )

        result = self.run_install("--apply")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        room = subprocess.run(
            ["zsh", "-lc", "command -v paseo"],
            cwd=ROOT,
            env=self.zsh_environment(real_bin, role="peer"),
            capture_output=True,
            text=True,
        )
        self.assertEqual(room.returncode, 0, room.stdout + room.stderr)
        self.assertEqual(
            room.stdout.strip(),
            str(self.home / ".local/share/paseo-room-bin/paseo"),
        )

    @unittest.skipUnless(shutil.which("zsh"), "zsh is unavailable")
    def test_zsh_path_guard_survives_later_path_mutation(self) -> None:
        result = self.run_install("--apply")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        real_bin = self.root / "real-bin"
        real_bin.mkdir()
        real_paseo = real_bin / "paseo"
        real_paseo.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        real_paseo.chmod(0o755)

        zshrc = self.home / ".zshrc"
        zshrc.unlink()
        zshrc.write_text(
            "autoload -Uz add-zsh-hook\n"
            "_simulate_late_path_mutation() {\n"
            '  PATH="$TEST_REAL_BIN:$PATH"\n'
            "  export PATH\n"
            "}\n"
            "add-zsh-hook chpwd _simulate_late_path_mutation\n",
            encoding="utf-8",
        )
        # Re-applying moves the managed block to canonical EOF after the
        # simulated NVM hook, so our chpwd hook is registered after it.
        result = self.run_install("--apply")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        contents = zshrc.read_text(encoding="utf-8")
        self.assertTrue(contents.rstrip().endswith(ZSHRC_END_MARKER))

        with zshrc.open("a", encoding="utf-8") as stream:
            stream.write(
                "\n# A direct assignment after the managed block is outside the guard.\n"
            )

        noninteractive_command = ["zsh", "-lc", "command -v paseo"]
        command = ["zsh", "-lic", "cd .; command -v paseo"]
        room = subprocess.run(
            noninteractive_command,
            cwd=ROOT,
            env=self.zsh_environment(real_bin, role="peer"),
            capture_output=True,
            text=True,
        )
        self.assertEqual(room.returncode, 0, room.stdout + room.stderr)
        self.assertEqual(
            room.stdout.strip(),
            str(self.home / ".local/share/paseo-room-bin/paseo"),
        )

        ordinary = subprocess.run(
            noninteractive_command,
            cwd=ROOT,
            env=self.zsh_environment(real_bin, role=None),
            capture_output=True,
            text=True,
        )
        self.assertEqual(ordinary.returncode, 0, ordinary.stdout + ordinary.stderr)
        self.assertEqual(ordinary.stdout.strip(), str(real_paseo))

        room = subprocess.run(
            command,
            cwd=ROOT,
            env=self.zsh_environment(real_bin, role="peer"),
            capture_output=True,
            text=True,
        )
        self.assertEqual(room.returncode, 0, room.stdout + room.stderr)
        self.assertEqual(
            room.stdout.strip(),
            str(self.home / ".local/share/paseo-room-bin/paseo"),
        )

        ordinary = subprocess.run(
            command,
            cwd=ROOT,
            env=self.zsh_environment(real_bin, role=None),
            capture_output=True,
            text=True,
        )
        self.assertEqual(ordinary.returncode, 0, ordinary.stdout + ordinary.stderr)
        self.assertEqual(ordinary.stdout.strip(), str(real_paseo))


if __name__ == "__main__":
    unittest.main()
