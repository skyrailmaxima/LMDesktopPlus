from __future__ import annotations

import unittest

from lmdesktopplus import fncache
from lmdesktopplus.adapters.base import dispatch_command
from lmdesktopplus.fncache import UseLevel, cache_snapshot, register_fn, resolve_fn, warm_high_use


class FnCacheTests(unittest.TestCase):
    def test_register_resolve_and_hits(self):
        name = "test.audit_probe"

        @register_fn(name, UseLevel.HIGH, "unit-test probe callable")
        def probe(value):
            return value * 2

        self.assertEqual(resolve_fn(name)(3), 6)
        meta = fncache.fn_meta(name)
        self.assertEqual(meta["level"], "high use")
        self.assertGreaterEqual(meta["hits"], 1)
        self.assertIn(name, warm_high_use())
        snap = cache_snapshot()
        self.assertEqual(snap[name]["purpose"], "unit-test probe callable")

    def test_dispatch_command_is_indexed_as_high_use(self):
        meta = fncache.fn_meta("adapters.dispatch_command")
        self.assertIsNotNone(meta)
        self.assertEqual(meta["level"], "high use")
        # Touch the registered wrapper through normal import path.
        result = dispatch_command({"ping": lambda _p: {"ok": True}}, "ping", {})
        self.assertTrue(result.get("ok"))


if __name__ == "__main__":
    unittest.main()
