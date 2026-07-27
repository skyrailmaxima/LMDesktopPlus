PORTNAME=		lmdesktopplus
DISTVERSION=		0.6.8
CATEGORIES=		x11-wm

MAINTAINER=		lmdesktopplus@localhost
COMMENT=		Digitalvapor vapor//matrix machine UI for FreeBSD
WWW=			https://github.com/skyrailmaxima/LMDesktopPlus

LICENSE=		MIT
LICENSE_FILE=		${WRKSRC}/LICENSE

# UI package only — Mint rice (install.sh / Hyprland) stays Linux.
USES=			python:3.10+
USE_PYTHON=		flavors
SUB_FILES=		lmdesktopplus
SUB_LIST=		PYTHON_CMD=${PYTHON_CMD}

RUN_DEPENDS=	${PYTHON_PKGNAMEPREFIX}gobject3>=3.42:devel/py-gobject3@${PY_FLAVOR}

OPTIONS_DEFINE=		WEBKIT
OPTIONS_DEFAULT=	WEBKIT
WEBKIT_DESC=		Embedded GTK/WebKit window (else use --browser)
WEBKIT_RUN_DEPENDS=	webkit2-gtk@40>=2.40:www/webkit2-gtk@40

# Soft runtime peers (fail-soft when missing): kitty, alacritty, xterm, tmux,
# btop, firefox. NetworkManager, bubblewrap, apt, and Hyprland are Linux-only.

NO_ARCH=		yes
NO_BUILD=		yes

# Local tree: make WRKSRC=/path/to/repo stage
WRKSRC?=		${.CURDIR}/../..

do-install:
	${MKDIR} ${STAGEDIR}${PREFIX}/lib/lmdesktopplus \
		${STAGEDIR}${PREFIX}/bin \
		${STAGEDIR}${PREFIX}/share/applications \
		${STAGEDIR}${PREFIX}/share/icons/hicolor/scalable/apps \
		${STAGEDIR}${PREFIX}/share/doc/lmdesktopplus
	${CP} -R ${WRKSRC}/src/lmdesktopplus \
		${STAGEDIR}${PREFIX}/lib/lmdesktopplus/lmdesktopplus
	${MKDIR} ${STAGEDIR}${PREFIX}/lib/lmdesktopplus/assets
	${CP} -R ${WRKSRC}/assets/wallpapers \
		${STAGEDIR}${PREFIX}/lib/lmdesktopplus/assets/wallpapers
	${INSTALL_SCRIPT} ${WRKDIR}/lmdesktopplus \
		${STAGEDIR}${PREFIX}/bin/lmdesktopplus
	${INSTALL_DATA} ${WRKSRC}/share/applications/lmdesktopplus.desktop \
		${STAGEDIR}${PREFIX}/share/applications/lmdesktopplus.desktop
	${REINPLACE_CMD} \
		-e 's|^Exec=.*|Exec=${PREFIX}/bin/lmdesktopplus|' \
		-e 's|^TryExec=.*|TryExec=${PREFIX}/bin/lmdesktopplus|' \
		${STAGEDIR}${PREFIX}/share/applications/lmdesktopplus.desktop
	${INSTALL_DATA} ${WRKSRC}/share/icons/hicolor/scalable/apps/lmdesktopplus.svg \
		${STAGEDIR}${PREFIX}/share/icons/hicolor/scalable/apps/lmdesktopplus.svg
	${INSTALL_DATA} ${WRKSRC}/README.md \
		${STAGEDIR}${PREFIX}/share/doc/lmdesktopplus/
	${INSTALL_DATA} ${WRKSRC}/docs/machine-ui.md \
		${STAGEDIR}${PREFIX}/share/doc/lmdesktopplus/
	${INSTALL_DATA} ${WRKSRC}/docs/freebsd-ui.md \
		${STAGEDIR}${PREFIX}/share/doc/lmdesktopplus/
	${INSTALL_DATA} ${WRKSRC}/CHANGELOG.md \
		${STAGEDIR}${PREFIX}/share/doc/lmdesktopplus/

.include <bsd.port.mk>
