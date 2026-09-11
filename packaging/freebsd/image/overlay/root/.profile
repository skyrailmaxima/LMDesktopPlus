# LMDesktopPlus FreeBSD spin: auto-start the vapor//matrix X session on the
# primary console after autologin. On any other tty (ssh, serial) drop to the
# shell as usual so the box stays administrable.
if [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/ttyv0" ] && command -v startx >/dev/null 2>&1; then
	exec startx
fi
