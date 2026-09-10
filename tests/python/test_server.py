from __future__ import annotations

import json
import urllib.error
import urllib.request
import unittest

from lmdesktopplus.server import start_server


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.server, self.thread, self.url = start_server()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, path, token=None, body=None, headers=None):
        req_headers = {}
        if token is not None:
            req_headers["X-LMDP-Token"] = token
        if headers:
            req_headers.update(headers)
        data = None
        method = "GET"
        if body is not None:
            data = json.dumps(body).encode()
            req_headers["Content-Type"] = "application/json"
            method = "POST"
        req = urllib.request.Request(
            self.url.rstrip("/") + path, data=data, headers=req_headers, method=method
        )
        return urllib.request.urlopen(req, timeout=10)

    def test_index_injects_token(self):
        with self.request("/") as response:
            text = response.read().decode()
        self.assertIn(self.server.token, text)
        self.assertNotIn("__LMDP_TOKEN__", text)


    def test_digitalvapor_assets_are_served(self):
        for path, marker in (
            ("/digitalvapor.css", "--dv-accent"),
            ("/digitalvapor.js", "Digitalvapor"),
            ("/bindings.js", "LMDPBindings"),
        ):
            with self.request(path) as response:
                text = response.read().decode()
            self.assertIn(marker, text)

    def test_index_uses_csp_compatible_token_metadata(self):
        with self.request("/") as response:
            text = response.read().decode()
        self.assertIn('name="lmdp-token"', text)
        self.assertNotIn("window.LMDP_TOKEN", text)
        self.assertIn("digitalvapor.css", text)
        self.assertIn("digitalvapor.js", text)
        self.assertIn("bindings.js", text)

    def test_api_rejects_missing_token(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.request("/api/v1/state")
        self.assertEqual(ctx.exception.code, 401)

    def test_state_and_allowlisted_action(self):
        with self.request("/api/v1/state", self.server.token) as response:
            payload = json.load(response)
        self.assertIn("metrics", payload)
        self.assertIn("assets", payload)
        self.assertIn("audio", payload["adapters"])
        self.assertIn("display", payload["adapters"])
        self.assertIn("session", payload["adapters"])
        self.assertIn("wallpaper", payload["adapters"])
        self.assertIn("hyprland_active", payload["adapters"]["session"])
        self.assertIn("capabilities", payload["adapters"]["session"])
        self.assertIn("audio.volume", payload["assets"]["icons"])
        self.assertIn("display.brightness", payload["assets"]["icons"])
        self.assertIn("package.vapor-matrix-svg", payload["assets"]["wallpapers"])
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.request("/api/v1/action", self.server.token, {"action": "launch", "target": "not-real"})
        self.assertEqual(ctx.exception.code, 400)

    def test_domain_state_endpoints(self):
        with self.request("/api/v1/state/core", self.server.token) as response:
            core = json.load(response)
        self.assertIn("version", core)
        self.assertIn("settings", core)
        self.assertNotIn("metrics", core)
        self.assertNotIn("adapters", core)

        with self.request("/api/v1/state/metrics", self.server.token) as response:
            metrics = json.load(response)
        self.assertIn("metrics", metrics)

        with self.request("/api/v1/state/adapters", self.server.token) as response:
            adapters = json.load(response)
        self.assertIn("session", adapters["adapters"])

        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.request("/api/v1/state/not-a-domain", self.server.token)
        self.assertEqual(ctx.exception.code, 404)

    def test_api_rejects_cross_site_fetch(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.request(
                "/api/v1/state",
                self.server.token,
                headers={"Sec-Fetch-Site": "cross-site"},
            )
        self.assertEqual(ctx.exception.code, 403)

    def test_api_rejects_foreign_origin(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.request(
                "/api/v1/state",
                self.server.token,
                headers={"Origin": "https://evil.example"},
            )
        self.assertEqual(ctx.exception.code, 403)

    def test_api_rejects_other_loopback_origin_port(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.request(
                "/api/v1/state",
                self.server.token,
                headers={"Origin": "http://127.0.0.1:9"},
            )
        self.assertEqual(ctx.exception.code, 403)

    def test_api_rejects_null_origin(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.request(
                "/api/v1/state",
                self.server.token,
                headers={"Origin": "null"},
            )
        self.assertEqual(ctx.exception.code, 403)

    def test_api_rejects_spoofed_host(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.request(
                "/api/v1/state",
                self.server.token,
                headers={"Host": f"evil.example:{self.server.server_address[1]}"},
            )
        self.assertEqual(ctx.exception.code, 403)

    def test_api_accepts_exact_server_origin(self):
        with self.request(
            "/api/v1/state/core",
            self.server.token,
            headers={"Origin": self.server.origin},
        ) as response:
            payload = json.load(response)
        self.assertIn("version", payload)

    def test_adapter_command_maps_uncaught_exceptions(self):
        class BoomAdapter:
            id = "boom"

            def available(self):
                return True

            def snapshot(self):
                return {"available": True}

            def command(self, name, payload):
                raise TimeoutError("host hung")

        self.server.state.adapters.register(BoomAdapter())
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.request(
                "/api/v1/adapter/boom",
                self.server.token,
                {"name": "ping", "payload": {}},
            )
        self.assertEqual(ctx.exception.code, 400)
        body = json.loads(ctx.exception.read().decode())
        self.assertEqual(body["error_code"], "timeout")
        self.assertEqual(body["error"], "Adapter command failed")

    def test_adapter_command_route_dispatches_allowlisted_command(self):
        class StubAdapter:
            id = "stub"

            def available(self):
                return True

            def snapshot(self):
                return {"available": True}

            def command(self, name, payload):
                if name != "ping":
                    return {"ok": False, "error": "unknown stub command"}
                return {"ok": True, "value": payload.get("value")}

        self.server.state.adapters.register(StubAdapter())
        with self.request(
            "/api/v1/adapter/stub",
            self.server.token,
            {"name": "ping", "payload": {"value": 7}},
        ) as response:
            self.assertEqual(json.load(response), {"ok": True, "value": 7})

        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.request(
                "/api/v1/adapter/stub",
                self.server.token,
                {"name": "unknown", "payload": {}},
            )
        self.assertEqual(ctx.exception.code, 400)

    def test_adapter_command_route_rejects_unknown_adapter(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.request(
                "/api/v1/adapter/not-real",
                self.server.token,
                {"name": "anything", "payload": {}},
            )
        self.assertEqual(ctx.exception.code, 404)

    def test_icon_assets_are_served(self):
        with self.request("/icons/volume.svg") as response:
            text = response.read().decode()
        self.assertIn("<svg", text)
        self.assertIn("currentColor", text)

    def test_icon_path_traversal_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.request("/icons/../app.js")
        self.assertEqual(ctx.exception.code, 404)

    def test_ui_state_scene_persists_and_injects(self):
        import tempfile
        from pathlib import Path

        from lmdesktopplus.ui_state import UiStateStore

        with tempfile.TemporaryDirectory() as tmp:
            self.server.state.ui_state = UiStateStore(Path(tmp) / "ui-state.json")
            with self.request("/api/v1/ui-state", self.server.token, {"scene": "monitor"}) as response:
                payload = json.load(response)
            self.assertEqual(payload["scene"], "monitor")
            with self.request("/") as response:
                text = response.read().decode()
            self.assertIn('content="monitor"', text)
            self.assertNotIn("__LMDP_SCENE__", text)
            # An invalid scene id is rejected and the previous value is kept.
            with self.request("/api/v1/ui-state", self.server.token, {"scene": "../etc"}) as response:
                payload = json.load(response)
            self.assertEqual(payload["scene"], "monitor")

    def test_wallpaper_thumbnail_is_served_from_catalog(self):
        with self.request(
            "/wallpaper-thumbs/package.vapor-matrix-svg.png"
        ) as response:
            self.assertEqual(response.headers.get_content_type(), "image/png")
            self.assertTrue(response.read().startswith(b"\x89PNG"))


if __name__ == "__main__":
    unittest.main()
