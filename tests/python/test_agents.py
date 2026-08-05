from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lmdesktopplus.agents import (
    AgentRegistry,
    dispatch_peer_op,
    tune_peer_argv,
    weave_peer_roster,
)


class PeerArgvTests(unittest.TestCase):
    def test_tune_peer_argv_allows_bare_binary_and_flags(self):
        self.assertEqual(tune_peer_argv("claude"), ["claude"])
        self.assertEqual(tune_peer_argv(["aider", "--model", "gpt"]), ["aider", "--model", "gpt"])
        self.assertEqual(tune_peer_argv("cursor --reuse-window"), ["cursor", "--reuse-window"])

    def test_tune_peer_argv_rejects_shell_and_paths(self):
        self.assertIsNone(tune_peer_argv("bash -c 'id'"))
        self.assertIsNone(tune_peer_argv(["/usr/bin/claude"]))
        self.assertIsNone(tune_peer_argv(["claude", ";rm"]))
        self.assertIsNone(tune_peer_argv(""))
        self.assertIsNone(tune_peer_argv(["claude", "`id`"]))


class PeerRosterTests(unittest.TestCase):
    def test_weave_peer_roster_dedupes_and_safe_names(self):
        rows = weave_peer_roster(
            [
                {"name": "Claude", "command": ["claude"]},
                {"name": "claude", "command": ["claude", "--x"]},
                {"name": "../evil", "command": ["x"]},
                {"name": "ok", "command": "aider --yes"},
            ]
        )
        names = [row["name"] for row in rows]
        self.assertEqual(names, ["claude", "ok"])
        self.assertEqual(rows[1]["command"], ["aider", "--yes"])


class AgentCrudTests(unittest.TestCase):
    def test_forge_retune_melt_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "agents.json"
            with patch("lmdesktopplus.agents.app_data_dir", return_value=Path(tmp) / "data"):
                registry = AgentRegistry(path=path)
                forged = registry.forge_peer(
                    {
                        "name": "nova",
                        "label": "Nova",
                        "command": "aider",
                        "workspace": "~/work",
                        "sandbox": True,
                        "network": False,
                        "description": "test peer",
                    }
                )
                self.assertTrue(forged.get("ok"))
                self.assertEqual(forged["peer"]["name"], "nova")
                self.assertFalse(forged["peer"]["network"])

                retuned = registry.retune_peer(
                    {"name": "nova", "label": "Nova X", "command": ["aider", "--yes"]}
                )
                self.assertTrue(retuned.get("ok"))
                self.assertEqual(retuned["peer"]["label"], "Nova X")
                self.assertEqual(retuned["peer"]["command"], ["aider", "--yes"])

                melted = registry.melt_peer({"name": "nova"})
                self.assertTrue(melted.get("ok"))
                self.assertIsNone(registry.fetch_peer("nova"))

    def test_forge_rejects_duplicate_and_bad_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "agents.json"
            with patch("lmdesktopplus.agents.app_data_dir", return_value=Path(tmp) / "data"):
                registry = AgentRegistry(path=path)
                dup = registry.forge_peer({"name": "claude", "command": ["claude"]})
                self.assertFalse(dup.get("ok"))
                bad = registry.forge_peer({"name": "x", "command": ["/bin/sh", "-c", "id"]})
                self.assertFalse(bad.get("ok"))

    def test_dispatch_peer_op_maps_crud_aliases(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "agents.json"
            with patch("lmdesktopplus.agents.app_data_dir", return_value=Path(tmp) / "data"):
                registry = AgentRegistry(path=path)
                created = dispatch_peer_op(
                    registry, "create", {"name": "zeta", "command": ["claude"]}
                )
                self.assertTrue(created.get("ok"))
                deleted = dispatch_peer_op(registry, "melt", {"name": "zeta"})
                self.assertTrue(deleted.get("ok"))
                unknown = dispatch_peer_op(registry, "explode", {})
                self.assertFalse(unknown.get("ok"))


if __name__ == "__main__":
    unittest.main()
