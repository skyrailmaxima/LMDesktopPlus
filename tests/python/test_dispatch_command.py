from __future__ import annotations

import unittest

from lmdesktopplus.adapters.base import dispatch_command


class DispatchCommandTests(unittest.TestCase):
    def test_dispatches_known_command(self):
        calls: list[dict] = []

        def ping(payload):
            calls.append(payload)
            return {"ok": True, "echo": payload.get("msg")}

        result = dispatch_command({"ping": ping}, "ping", {"msg": "hi"})
        self.assertEqual(result, {"ok": True, "echo": "hi"})
        self.assertEqual(calls, [{"msg": "hi"}])

    def test_unknown_command_uses_adapter_id(self):
        result = dispatch_command({}, "explode", {}, adapter_id="vpn")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "unavailable")
        self.assertEqual(result["error"], "unknown vpn command: explode")

    def test_unknown_command_without_adapter_id(self):
        result = dispatch_command({}, "explode", {})
        self.assertEqual(result["error"], "unknown command: explode")


if __name__ == "__main__":
    unittest.main()
