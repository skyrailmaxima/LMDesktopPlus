from __future__ import annotations

import argparse
import signal
import sys
import time
import webbrowser
from importlib.resources import as_file, files

from . import __version__
from .agents import AgentRegistry
from .server import start_server
from .single_instance import SingleInstance, focus_existing_window
from .util import APP_ID


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lmdesktopplus", description="LMDesktopPlus vapor//matrix machine UI")
    parser.add_argument("--browser", action="store_true", help="open in the default browser instead of an embedded GTK window")
    parser.add_argument("--kiosk", action="store_true", help="open the embedded window fullscreen")
    parser.add_argument("--print-url", action="store_true", help="print the local UI URL")
    parser.add_argument("--agent-run", metavar="NAME", help=argparse.SUPPRESS)
    parser.add_argument(
        "--live-wallpaper",
        action="store_true",
        help="open the feature-flagged live matrix wallpaper window (no control-center server)",
    )
    parser.add_argument(
        "--rain-intensity",
        type=int,
        default=55,
        help="matrix rain intensity 0–100 for --live-wallpaper",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def run_browser(url: str) -> int:
    webbrowser.open(url, new=1)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        return 0


def run_live_wallpaper(intensity: int) -> int:
    """Fullscreen WebKit window running packaged live-wallpaper.html (DV.rain)."""
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        try:
            gi.require_version("WebKit2", "4.1")
        except ValueError:
            gi.require_version("WebKit2", "4.0")
        from gi.repository import Gtk, WebKit2
    except (ImportError, ValueError) as exc:
        print(f"Live wallpaper WebKit unavailable ({exc}).", file=sys.stderr)
        return 1

    clamped = max(0, min(100, int(intensity)))
    static_root = files("lmdesktopplus").joinpath("static")
    with as_file(static_root) as static_dir:
        html_path = static_dir / "live-wallpaper.html"
        if not html_path.is_file():
            print("Packaged live-wallpaper.html is missing.", file=sys.stderr)
            return 1
        uri = html_path.resolve().as_uri() + f"?i={clamped}"

        window = Gtk.Window(title="LMDesktopPlus Live Wallpaper")
        window.set_default_size(1280, 720)
        window.set_icon_name("lmdesktopplus")
        try:
            # X11 / XWayland class matched by owned hypr-live-wallpaper.conf rules.
            window.set_wmclass("lmdesktopplus-livewall", "lmdesktopplus-livewall")
        except Exception:  # noqa: BLE001 — optional on pure Wayland
            pass
        view = WebKit2.WebView()
        settings = view.get_settings()
        settings.set_property("enable-developer-extras", False)
        view.load_uri(uri)
        window.add(view)
        window.connect("destroy", Gtk.main_quit)
        window.fullscreen()
        window.show_all()
        Gtk.main()
    return 0


def run_gtk(url: str, kiosk: bool, start_fullscreen: bool, ui_state=None) -> int:
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        try:
            gi.require_version("WebKit2", "4.1")
        except ValueError:
            gi.require_version("WebKit2", "4.0")
        from gi.repository import Gdk, GLib, Gtk, WebKit2
    except (ImportError, ValueError) as exc:
        print(f"Embedded WebKit UI unavailable ({exc}); opening the browser fallback.", file=sys.stderr)
        return run_browser(url)

    saved = ui_state.get() if ui_state is not None else None
    geom = saved["window"] if saved else {"width": 1320, "height": 840, "maximized": False}

    window = Gtk.Window(title="LMDesktopPlus Machine UI")
    window.set_default_size(int(geom["width"]), int(geom["height"]))
    window.set_icon_name("lmdesktopplus")
    try:
        # X11 / XWayland WM_CLASS so the window matches the .desktop
        # StartupWMClass and window-manager rules can target it.
        window.set_wmclass(APP_ID, APP_ID)
    except Exception:  # noqa: BLE001 — optional on pure Wayland
        pass
    view = WebKit2.WebView()
    settings = view.get_settings()
    settings.set_property("enable-developer-extras", True)
    settings.set_property("enable-smooth-scrolling", True)
    view.load_uri(url)
    window.add(view)

    # Track live geometry so the last non-maximized size is what we restore.
    live = {"width": int(geom["width"]), "height": int(geom["height"]), "maximized": bool(geom["maximized"])}

    def on_configure(_widget, event):
        if not live["maximized"]:
            live["width"], live["height"] = int(event.width), int(event.height)
        return False

    def on_window_state(_widget, event):
        live["maximized"] = bool(event.new_window_state & Gdk.WindowState.MAXIMIZED)
        return False

    def save_geometry():
        if ui_state is not None:
            ui_state.set_window(live["width"], live["height"], live["maximized"])

    def on_destroy(_widget):
        save_geometry()
        Gtk.main_quit()

    window.connect("configure-event", on_configure)
    window.connect("window-state-event", on_window_state)
    window.connect("destroy", on_destroy)
    window.show_all()
    if geom["maximized"] and not (kiosk or start_fullscreen):
        window.maximize()
    if kiosk or start_fullscreen:
        window.fullscreen()

    fullscreen_state = {"active": bool(kiosk or start_fullscreen)}

    def on_key(_widget, event):
        key = getattr(event, "keyval", None)
        if key == 65480:  # F11
            if fullscreen_state["active"]:
                window.unfullscreen()
            else:
                window.fullscreen()
            fullscreen_state["active"] = not fullscreen_state["active"]
        return False

    window.connect("key-press-event", on_key)

    # Clean shutdown on SIGINT/SIGTERM: persist geometry, then quit the loop so
    # main()'s finally block tears down the server and releases the lock.
    def on_signal():
        save_geometry()
        Gtk.main_quit()
        return GLib.SOURCE_REMOVE

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, on_signal)
        except (AttributeError, ValueError, OSError):
            pass

    Gtk.main()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.agent_run:
        return AgentRegistry().exec_agent(args.agent_run)
    if args.live_wallpaper:
        return run_live_wallpaper(args.rain_intensity)

    # A single control-center instance owns the loopback server. A second
    # launch focuses the running window (best effort) instead of starting a
    # rival server.
    guard = SingleInstance()
    if not guard.acquire():
        focus_existing_window(APP_ID)
        print("LMDesktopPlus is already running; focusing the existing window.", file=sys.stderr)
        return 0

    server, thread, url = start_server()
    if args.print_url:
        print(url)
    try:
        fullscreen = server.state.settings.get().get("behavior", {}).get("start_fullscreen", False)
        if args.browser:
            return run_browser(url)
        return run_gtk(url, args.kiosk, bool(fullscreen), ui_state=server.state.ui_state)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        guard.release()


if __name__ == "__main__":
    raise SystemExit(main())
