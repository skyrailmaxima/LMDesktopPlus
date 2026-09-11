#!/bin/sh
# vapor//matrix X session for the LMDesktopPlus FreeBSD spin. startx runs this;
# it paints the branded background and launches the control center, which opens
# its own GTK/WebKit window (no separate window manager required for the kiosk).
xsetroot -solid '#05060a' 2>/dev/null || true
if command -v feh >/dev/null 2>&1; then
	feh --bg-fill /usr/local/share/backgrounds/lmdesktopplus/vapor-matrix.png 2>/dev/null || true
fi
exec /usr/local/bin/lmdesktopplus
