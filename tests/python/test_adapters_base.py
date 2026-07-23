from __future__ import annotations

import subprocess
import unittest

from lmdesktopplus.adapters.base import classify_exception, command_error, envelope


class AdapterBaseTests(unittest.TestCase):
    def test_envelope_marks_unavailable_and_nests_state(self):
        payload = envelope("probe", {"available": False, "backend": None, "detail": 1})
        self.assertEqual(payload["id"], "probe")
        self.assertFalse(payload["available"])
        self.assertEqual(payload["status"], "unavailable")
        self.assertEqual(payload["state"]["detail"], 1)
        self.assertIn("updated_at", payload)
        self.assertFalse(payload["stale"])

    def test_envelope_preserves_explicit_status(self):
        payload = envelope("session", {"available": True, "status": "armed", "armed": True})
        self.assertEqual(payload["status"], "armed")
        self.assertTrue(payload["state"]["armed"])

    def test_command_error_shape(self):
        self.assertEqual(
            command_error("timeout", "took too long", retryable=True),
            {"ok": False, "error_code": "timeout", "error": "took too long", "retryable": True},
        )

    def test_classify_exception(self):
        code, message = classify_exception(subprocess.TimeoutExpired(cmd=["x"], timeout=1))
        self.assertEqual(code, "timeout")
        self.assertIn("timed out", message)
        self.assertEqual(classify_exception(FileNotFoundError("missing"))[0], "unavailable")
        self.assertEqual(classify_exception(PermissionError("no"))[0], "permission_denied")
        self.assertEqual(classify_exception(RuntimeError("boom"))[0], "internal_error")


if __name__ == "__main__":
    unittest.main()
