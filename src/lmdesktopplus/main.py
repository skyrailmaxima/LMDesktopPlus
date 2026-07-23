from __future__ import annotations

import argparse
import signal
import sys
import time
import webbrowser

from . import __version__
from .agents import AgentRegistry
from .server import start_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lmdesktopplus", description="LMDesktopPlus vapor//matrix machine UI")
    parser.add_argument("--browser", action="store_true", help="open in the default browser instead of an embedded GTK window")
    parser.add_argument("--kiosk", action="store_true", help="open the embedded window fullscreen")
    parser.add_argument("--print-url", action="store_true", help="print the local UI URL")
    parser.add_argument("--agent-run", metavar="NAME", help=argparse.SUPPRESS)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def run_browser(url: str) -> int:
    webbrowser.open(url, new=1)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        return 0


def run_gtk(url: str, kiosk: bool, start_fullscreen: bool) -> int:
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        try:
            gi.require_version("WebKit2", "4.1")
        except ValueError:
            gi.require_version("WebKit2", "4.0")
        from gi.repository import Gtk, WebKit2
    except (ImportError, ValueError) as exc:
        print(f"Embedded WebKit UI unavailable ({exc}); opening the browser fallback.", file=sys.stderr)
        return run_browser(url)

    window = Gtk.Window(title="LMDesktopPlus Machine UI")
    window.set_default_size(1320, 840)
    window.set_icon_name("lmdesktopplus")
    view = WebKit2.WebView()
    settings = view.get_settings()
    settings.set_property("enable-developer-extras", True)
    settings.set_property("enable-smooth-scrolling", True)
    view.load_uri(url)
    window.add(view)
    window.connect("destroy", Gtk.main_quit)
    window.show_all()
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
    Gtk.main()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.agent_run:
        return AgentRegistry().exec_agent(args.agent_run)

    server, thread, url = start_server()
    if args.print_url:
        print(url)
    try:
        fullscreen = server.state.settings.get().get("behavior", {}).get("start_fullscreen", False)
        if args.browser:
            return run_browser(url)
        return run_gtk(url, args.kiosk, bool(fullscreen))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


if __name__ == "__main__":
    raise SystemExit(main())
