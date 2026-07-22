from __future__ import annotations

import unittest

from lmdesktopplus.adapters import AdapterRegistry
from lmdesktopplus.adapters.base import NullAdapter


class AdapterRegistryTests(unittest.TestCase):
    def test_registry_get_and_snapshot(self):
        registry = AdapterRegistry()
        registry.register(NullAdapter("probe"))

        snap = registry.as_dict()["probe"]
        self.assertEqual(snap["id"], "probe")
        self.assertTrue(snap["available"])
        self.assertIn("status", snap)
        self.assertIn("capabilities", snap)
        self.assertTrue(registry.get("probe").snapshot()["available"])

    def test_registry_wraps_raw_snapshots_and_isolates_failures(self):
        class RawAdapter:
            id = "raw"

            def available(self):
                return True

            def snapshot(self):
                return {"available": True, "value": 3}

            def command(self, name, payload):
                return {"ok": False, "error": "unused"}

        class BoomAdapter:
            id = "boom"

            def available(self):
                return True

            def snapshot(self):
                raise PermissionError("denied")

            def command(self, name, payload):
                return {"ok": False, "error": "unused"}

        registry = AdapterRegistry()
        registry.register(RawAdapter())
        registry.register(BoomAdapter())
        snaps = registry.as_dict()
        self.assertEqual(snaps["raw"]["state"]["value"], 3)
        self.assertEqual(snaps["boom"]["status"], "error")
        self.assertEqual(snaps["boom"]["error_code"], "permission_denied")


if __name__ == "__main__":
    unittest.main()

