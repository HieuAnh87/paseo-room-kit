from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import pathlib
import tempfile
import types
import unittest
from unittest.mock import patch


ROOT = pathlib.Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader("codex_room_sync", str(ROOT / "bin/codex-room-sync"))
spec = importlib.util.spec_from_loader(loader.name, loader)
assert spec is not None
sync = importlib.util.module_from_spec(spec)
loader.exec_module(sync)


def response(*models: dict) -> types.SimpleNamespace:
    return types.SimpleNamespace(stdout=json.dumps({"models": list(models)}))


class CodexModelCatalogTest(unittest.TestCase):
    def test_peer_catalog_refreshes_for_the_deep_model_even_when_luna_is_bundled(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            sync.os.environ, {"CODEX_BIN": "/fake/codex"}
        ), patch.object(sync.subprocess, "run") as run:
            run.side_effect = [response({"slug": "gpt-6-luna"}),
                               response({"slug": "gpt-6-luna"}, {"slug": "gpt-6.1-sol"})]
            target = sync.write_no_native_agents_model_catalog(pathlib.Path(directory), "gpt-6-luna", ("gpt-6.1-sol",))
            self.assertEqual({m["slug"] for m in json.loads(target.read_text())["models"]}, {"gpt-6-luna", "gpt-6.1-sol"})
            self.assertEqual(run.call_count, 2)

    def test_new_account_model_refreshes_catalog_and_disables_native_agents(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            sync.os.environ, {"CODEX_BIN": "/fake/codex"}
        ), patch.object(sync.subprocess, "run") as run:
            run.side_effect = [
                response({"slug": "gpt-6-sol", "multi_agent_version": "v2"}),
                response(
                    {"slug": "gpt-6.1-sol", "multi_agent_version": "v2", "context_window": 272000},
                    {"slug": "gpt-6-luna", "multi_agent_version": "v2"},
                ),
            ]
            target = sync.write_no_native_agents_model_catalog(pathlib.Path(directory), "gpt-6.1-sol")
            models = json.loads(target.read_text())["models"]
            self.assertEqual(models[0]["slug"], "gpt-6.1-sol")
            self.assertEqual(models[0]["context_window"], 272000)
            self.assertTrue(all(model["multi_agent_version"] is None for model in models))
            self.assertEqual(run.call_args_list[1].args[0], ["/fake/codex", "debug", "models"])

    def test_bundled_peer_model_does_not_require_network_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            sync.os.environ, {"CODEX_BIN": "/fake/codex"}
        ), patch.object(sync.subprocess, "run", return_value=response(
            {"slug": "gpt-6-luna", "multi_agent_version": "v2"}
        )) as run:
            target = sync.write_no_native_agents_model_catalog(pathlib.Path(directory), "gpt-6-luna")
            self.assertIsNone(json.loads(target.read_text())["models"][0]["multi_agent_version"])
            run.assert_called_once()

    def test_missing_requested_model_preserves_previous_runtime_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            sync.os.environ, {"CODEX_BIN": "/fake/codex"}
        ), patch.object(sync.subprocess, "run", return_value=response({"slug": "gpt-6-sol"})):
            root = pathlib.Path(directory)
            target = root / "model-catalog.no-native-agents.json"
            target.write_text("previous catalog\n")
            with self.assertRaisesRegex(SystemExit, "gpt-6.1-sol"):
                sync.write_no_native_agents_model_catalog(root, "gpt-6.1-sol")
            self.assertEqual(target.read_text(), "previous catalog\n")


if __name__ == "__main__":
    unittest.main()
