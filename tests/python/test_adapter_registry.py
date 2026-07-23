from __future__ import annotations

import unittest

from lmdesktopplus.adapters import AdapterRegistry
from lmdesktopplus.adapters.base import NullAdapter


class AdapterRegistryTests(unittest.TestCase):
    def test_registry_get_and_snapshot(self):
        registry = AdapterRegistry()
        registry.register(NullAdapter("probe"))

        self.assertIn("probe", registry.as_dict())
        self.assertTrue(registry.get("probe").snapshot()["available"])


if __name__ == "__main__":
    unittest.main()
