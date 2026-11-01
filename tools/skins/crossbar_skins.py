#!/usr/bin/env python3
"""Crossbar: a PlayStation XMB style skin (wave background, category icons).

The five tabs are a row of white category icons; the selected one is bigger,
glows and has its name underneath. Lists float on the wave in light glass
panels with a soft glow highlight. The Media Library home screen is the
"cross": its nine entries (the map menu, MEDIALIBRARY_MAP=1) form a column
under the Media Library category icon, like the XMB's item list.

Everything is SVG rendered with Chromium (gt_skins.render). The app's own
text uses the PSP's built-in sans (flash0:/font/ltn0.pgf), which is the
typeface family the XMB itself uses; the labels baked into images use Inter
(SIL Open Font License, fonts/OFL-Inter.txt). The icons are original
drawings; no Sony artwork or logos.
"""
import math

import numpy as np

from make_skins import Theme, SIZES, PANEL_NAMES, HIDE
from gt_skins import FONT_FILES, doc, f, pts, text, render, smooth
from xp_skins import lin, rad, outlined

INTER = "Inter"
CROSS_FONTS = FONT_FILES + [
    (INTER, "400", "normal", "Inter-Regular.otf"),
    (INTER, "500", "normal", "Inter-Medium.otf"),
    (INTER, "600", "normal", "Inter-SemiBold.otf"),
]

# ---------------------------------------------------------------------------
# White glyphs on a 32x32 grid. The group around them sets fill and stroke to
# the white gradient; shapes switch one of them off as needed.
# ---------------------------------------------------------------------------
DARK = 'fill="#1c3f86" stroke="none" opacity="0.45"'
NOTE2 = ('<g stroke="none"><ellipse cx="9.5" cy="24.5" rx="4.4" ry="3.3" transform="rotate(-20 9.5 24.5)"/>'
         '<ellipse cx="22.5" cy="21.5" rx="4.4" ry="3.3" transform="rotate(-20 22.5 21.5)"/>'
         '<rect x="12.3" y="8" width="2.6" height="16.5"/><rect x="25.3" y="5" width="2.6" height="16.5"/>'
         '<polygon points="12.3,8 27.9,4.4 27.9,9.4 12.3,13"/></g>')
LINES3 = ('<g stroke="none"><rect x="3" y="6" width="17" height="3" rx="1.5"/><rect x="3" y="12" width="17" height="3" rx="1.5"/>'
          '<rect x="3" y="18" width="11" height="3" rx="1.5"/></g>')
GUITAR_BODY = ("M16 17.5 C14.2 17.5 13.4 16 11.8 16.5 C9.6 17.2 9.9 19.7 10.8 21 C9.2 22.3 8.8 24.9 10.1 26.8 "
               "C11.6 28.8 14.6 29 16 28.5 C17.4 29 20.4 28.8 21.9 26.8 C23.2 24.9 22.8 22.3 21.2 21 "
               "C22.1 19.7 22.4 17.2 20.2 16.5 C18.6 16 17.8 17.5 16 17.5 Z")
GLYPHS = {
    "folder": ('<path stroke="none" opacity="0.72" d="M3 9 Q3 6.5 5.5 6.5 H12.5 L15.5 9.5 H26.5 Q29 9.5 29 12 V24.5 '
               'Q29 27 26.5 27 H5.5 Q3 27 3 24.5 Z"/>'
               '<path stroke="none" d="M2.6 14.4 Q2.8 12.6 4.6 12.6 H27.6 Q29.6 12.6 29.4 14.6 L28.6 25 Q28.4 27.2 26.2 '
               '27.2 H5.8 Q3.6 27.2 3.4 25 Z"/>'),
    "playlist": (LINES3 + '<g stroke="none"><ellipse cx="22.5" cy="25" rx="4" ry="3" transform="rotate(-20 22.5 25)"/>'
                 '<rect x="25" y="9" width="2.4" height="16"/><path d="M27.4 9 q5 2 4 8.5 q-1.5 -3.8 -4 -4.4 z"/></g>'),
    "editor": (LINES3 + '<g stroke="none" transform="rotate(40 22 17)"><rect x="19.5" y="5" width="5" height="16.5" rx="0.8"/>'
               '<polygon points="19.5,21.5 24.5,21.5 22,27"/><rect x="19.5" y="2" width="5" height="2.2" rx="0.8" opacity="0.7"/></g>'),
    "music": NOTE2,
    "toolbox": ('<path fill="none" stroke-width="2.6" d="M11 12.5 V8.5 Q11 6.5 13 6.5 H19 Q21 6.5 21 8.5 V12.5"/>'
                '<rect stroke="none" x="3" y="12" width="26" height="15" rx="2.5"/>'
                '<rect x="3" y="16.6" width="26" height="1.4" %s/>' % DARK
                + '<rect x="13.8" y="14.6" width="4.4" height="5" rx="1" %s/>' % DARK),
    "shuffle": ('<g fill="none" stroke-width="3" stroke-linecap="round">'
                '<path d="M3.5 23 H8.5 C14.5 23 16.5 9 22.5 9 H25"/><path d="M3.5 9 H8.5 C14.5 9 16.5 23 22.5 23 H25"/></g>'
                '<g stroke="none"><polygon points="23.5,3.8 30.5,9 23.5,14.2"/><polygon points="23.5,17.8 30.5,23 23.5,28.2"/></g>'),
    "mic": ('<rect stroke="none" x="11" y="2.5" width="10" height="16" rx="5"/>'
            '<g %s><rect x="11" y="7" width="10" height="1.2"/><rect x="11" y="10.4" width="10" height="1.2"/>'
            '<rect x="11" y="13.8" width="10" height="1.2"/></g>' % DARK
            + '<path fill="none" stroke-width="2.2" d="M7.5 13.5 V15 Q7.5 22.5 16 22.5 Q24.5 22.5 24.5 15 V13.5"/>'
            '<rect stroke="none" x="14.8" y="22" width="2.4" height="5"/><rect stroke="none" x="10" y="27" width="12" height="2.6" rx="1.3"/>'),
    "disc": ('<path stroke="none" fill-rule="evenodd" d="M3 16 A13 13 0 1 1 29 16 A13 13 0 1 1 3 16 Z '
             'M12.6 16 A3.4 3.4 0 1 0 19.4 16 A3.4 3.4 0 1 0 12.6 16 Z"/>'
             '<circle cx="16" cy="16" r="7" fill="none" stroke="#1c3f86" stroke-width="0.8" opacity="0.35"/>'
             '<path d="M7.5 11 A10 10 0 0 1 13 6.4" fill="none" stroke="#1c3f86" stroke-width="1.2" opacity="0.3" stroke-linecap="round"/>'),
    "guitar": ('<g transform="rotate(40 16 16) translate(16 16.5) scale(1.32) translate(-16 -14.6)" stroke="none"><path d="%s"/>' % GUITAR_BODY
               + '<rect x="15" y="1.8" width="2" height="17"/><rect x="14.2" y="0.2" width="3.6" height="3.6" rx="0.8"/>'
               '<rect x="13.6" y="21.3" width="4.8" height="1.5" rx="0.5" %s/>' % DARK
               + '<rect x="13.6" y="24" width="4.8" height="1.5" rx="0.5" %s/></g>' % DARK),
    "star": '<polygon stroke="none" points="%s"/>' % pts(
        [(16 + (14 if k % 2 == 0 else 5.8) * math.cos(math.radians(-90 + 36 * k)),
          17 + (14 if k % 2 == 0 else 5.8) * math.sin(math.radians(-90 + 36 * k))) for k in range(10)]),
    "trophy": ('<path stroke="none" d="M9 3.5 H23 V10 Q23 18 16 19.5 Q9 18 9 10 Z"/>'
               '<g fill="none" stroke-width="2.2"><path d="M9 6.5 H5.4 Q4.8 12.8 10 13.8"/><path d="M23 6.5 H26.6 Q27.2 12.8 22 13.8"/></g>'
               '<rect stroke="none" x="14.5" y="19" width="3" height="4.5"/><rect stroke="none" x="9.5" y="23.5" width="13" height="4.5" rx="1"/>'
               '<rect x="12" y="25" width="8" height="1.5" rx="0.5" %s/>' % DARK),
    "search": ('<circle cx="13" cy="13" r="8.4" stroke="none" opacity="0.28"/>'
               '<circle cx="13" cy="13" r="8.4" fill="none" stroke-width="3.2"/>'
               '<line x1="19.4" y1="19.4" x2="27.6" y2="27.6" stroke-width="4.6" stroke-linecap="round"/>'),
    "scan": ('<path stroke="none" opacity="0.8" d="M6.5 4 H19 L24 9 V27.5 Q24 28.5 23 28.5 H7.5 Q6.5 28.5 6.5 27.5 Z"/>'
             '<g %s><rect x="9" y="6" width="1.6" height="4"/><rect x="12" y="6" width="1.6" height="4"/><rect x="15" y="6" width="1.6" height="4"/></g>' % DARK
             + '<path d="M29 21.5 A6.6 6.6 0 1 1 25.4 15.6" fill="none" stroke="#163a80" stroke-width="5" stroke-linecap="round" opacity="0.8"/>'
             '<path d="M29 21.5 A6.6 6.6 0 1 1 25.4 15.6" fill="none" stroke-width="2.6" stroke-linecap="round"/>'
             '<polygon stroke="#163a80" stroke-width="0.8" points="23.6,12.2 29.2,15.2 23.8,19"/>'),
}

TABS = [("File Browser", "folder"), ("Playlists", "playlist"), ("Playlist Editor", "editor"),
        ("Media Library", "music"), ("Settings", "toolbox")]
ML_ITEMS = [("Shuffle All", "shuffle"), ("Browse All", "music"), ("Artists", "mic"), ("Albums", "disc"),
            ("Genres", "guitar"), ("Ratings", "star"), ("Top 100", "trophy"), ("Search", "search"),
            ("Scan for Media", "scan")]

WHITE = lin("gw", [(0, "#ffffff"), (0.55, "#f2f6fc"), (1, "#c9d6ea")], 0, 0, 0, 32, user=True)
SHADOW = ('<filter id="sh" x="-40%" y="-40%" width="180%" height="180%"><feDropShadow dx="0" dy="1" stdDeviation="1" '
          'flood-color="#00103a" flood-opacity="0.7"/></filter>')
GLOW = ('<filter id="glow" x="-60%" y="-60%" width="220%" height="220%">'
        '<feGaussianBlur in="SourceAlpha" stdDeviation="2.4" result="b"/>'
        '<feFlood flood-color="#cfe6ff" flood-opacity="0.9"/><feComposite in2="b" operator="in" result="g"/>'
        '<feDropShadow dx="0" dy="1" stdDeviation="0.8" flood-color="#00103a" flood-opacity="0.6" in="SourceGraphic" result="s"/>'
        '<feMerge><feMergeNode in="g"/><feMergeNode in="s"/></feMerge></filter>')
TEXT_SH = ('<filter id="tsh" x="-20%" y="-50%" width="140%" height="200%"><feDropShadow dx="0" dy="1" stdDeviation="0.9" '
           'flood-color="#00103a" flood-opacity="0.85"/></filter>')
TEXT_GLOW = ('<filter id="tgl" x="-20%" y="-80%" width="140%" height="260%">'
             '<feGaussianBlur in="SourceAlpha" stdDeviation="2" result="b"/>'
             '<feFlood flood-color="#bcdcff" flood-opacity="0.75"/><feComposite in2="b" operator="in" result="g"/>'
             '<feDropShadow dx="0" dy="1" stdDeviation="0.8" flood-color="#00103a" flood-opacity="0.7" in="SourceGraphic" result="s"/>'
             '<feMerge><feMergeNode in="g"/><feMergeNode in="s"/></feMerge></filter>')
DEFS = WHITE + SHADOW + GLOW + TEXT_SH + TEXT_GLOW


def glyph(name, cx, cy, size, selected=False, opacity=1.0):
    s = size / 32.0
    op = "" if opacity >= 1 else ' opacity="%s"' % f(opacity)
    return ('<g filter="url(#%s)"%s><g transform="translate(%s %s) scale(%s)" fill="url(#gw)" stroke="url(#gw)">%s</g></g>'
            % ("glow" if selected else "sh", op, f(cx - size / 2), f(cy - size / 2), f(s), GLYPHS[name]))


def label(x, y, s, size, weight, anchor, selected=False, opacity=1.0):
    t = text(x, y, s, size, "#ffffff", family=INTER, weight=weight, anchor=anchor, opacity=None if opacity >= 1 else opacity)
    return t.replace("<text ", '<text filter="url(#%s)" ' % ("tgl" if selected else "tsh"))


# ---------------------------------------------------------------------------
# Screens
# ---------------------------------------------------------------------------
TAB_X0, TAB_STEP, TAB_Y = 12, 72, 21   # tab images are 96 wide; icons sit 72 px apart
TAB_W, TAB_H = 96, 40
CONTENT_Y = 62
ML_TAB = 3
ML_X = TAB_X0 + ML_TAB * TAB_STEP + TAB_W // 2 - 16   # item column under the Media Library icon
ML_Y0, ML_STEP = 61, 20       # images are 28 tall and overlap; each entry's own space is the middle 20 px
ITEM_W, ITEM_H = 196, 28


def wave_background(w=480, h=272, seed=3):
    rng = np.random.default_rng(seed)
    defs = (lin("bg", [(0, "#03133f"), (0.42, "#0d3c98"), (0.6, "#1652b8"), (0.8, "#0b2f7c"), (1, "#020e33")])
            + rad("hl", [(0, "#5a9cf0", 0.5), (0.6, "#3b7fe0", 0.12), (1, "#3b7fe0", 0)], cx=0.42, cy=0.62, r=0.62)
            + '<filter id="soft" x="-10%" y="-50%" width="120%" height="200%"><feGaussianBlur stdDeviation="5"/></filter>'
            + '<filter id="glowl" x="-10%" y="-50%" width="120%" height="200%"><feGaussianBlur stdDeviation="1.6"/></filter>')

    def curve(t, extra=0.0):
        amp = 24 + 16 * math.sin(t * 2.6 + 0.4)
        ph = 0.5 + t * 1.4 + extra
        y0 = 176 + (t - 0.5) * 26
        return [(x, y0 + amp * math.sin(2 * math.pi * x / 600 + ph) + 8 * math.sin(2 * math.pi * x / 250 + ph * 1.8 + 1))
                for x in range(-30, w + 31, 8)]

    def band(t0, t1, extra=0.0):
        a, b = curve(t0, extra), curve(t1, extra)
        return smooth(a) + " L" + " L".join("%s %s" % (f(x), f(y)) for x, y in reversed(b)) + " Z"

    lines = ""
    n = 30
    for k in range(n):
        t = k / (n - 1)
        op = 0.04 + 0.2 * (1 - abs(t - 0.5) * 2) ** 1.6
        lines += '<path d="%s" fill="none" stroke="#ffffff" stroke-width="%s" opacity="%s"/>' % (
            smooth(curve(t)), f(0.6 + 0.7 * rng.random()), f(op))
    body = ('<rect width="%d" height="%d" fill="url(#bg)"/>' % (w, h)
            + '<rect width="%d" height="%d" fill="url(#hl)"/>' % (w, h)
            + '<path d="%s" fill="#bfe0ff" opacity="0.1" filter="url(#soft)"/>' % band(0.25, 0.75)
            + '<path d="%s" fill="#ffffff" opacity="0.07"/>' % band(0.4, 0.6, 0.15)
            + '<g filter="url(#glowl)" opacity="0.8">%s</g>' % lines
            + lines)
    return doc(w, h, body, defs)


def status_bar(w, h, top):
    g = lin("sb", [(0, "#000814", 0.55), (1, "#000814", 0)] if top else [(0, "#000814", 0), (1, "#000814", 0.55)])
    line = ('<rect x="214" y="%d" width="%d" height="1" fill="url(#ln)"/>' % (h - 1, w - 214)) if top else ""
    defs = g + lin("ln", [(0, "#ffffff", 0), (0.25, "#ffffff", 0.55), (1, "#ffffff", 0.55)], 0, 0, 1, 0)
    return doc(w, h, '<rect width="%d" height="%d" fill="url(#sb)"/>' % (w, h) + line, defs)


def tab_svg(i, selected):
    name, g = TABS[i]
    cx = TAB_W / 2
    if selected:
        body = glyph(g, cx, 15, 30, True) + label(cx, 37, name, 11, 500, "middle", True)
    else:
        body = glyph(g, cx, 15, 22, False, 0.62)
    return doc(TAB_W, TAB_H, body, DEFS)


def glass(w, h, alpha=0.3, radius=6, edge=True):
    """Dark glass panel: (defs, body)."""
    defs = lin("gp", [(0, "#000a24", alpha + 0.08), (1, "#000a24", alpha)])
    body = '<rect width="%d" height="%d" rx="%d" fill="url(#gp)"/>' % (w, h, radius)
    if edge:
        defs += lin("ge", [(0, "#ffffff", 0), (0.15, "#ffffff", 0.28), (0.85, "#ffffff", 0.28), (1, "#ffffff", 0)], 0, 0, 1, 0)
        body += '<rect x="%d" y="0" width="%d" height="1" fill="url(#ge)"/>' % (radius, w - 2 * radius)
    return defs, body


def glass_panel(w, h, alpha=0.3, radius=6, edge=True):
    defs, body = glass(w, h, alpha, radius, edge)
    return doc(w, h, body, defs)


def dialog_panel(w, h):
    """PS3 style dialog: dark glass with thin light rules top and bottom."""
    defs = (lin("dp", [(0, "#030b22", 0.88), (1, "#071a44", 0.88)])
            + lin("dl", [(0, "#ffffff", 0), (0.1, "#ffffff", 0.8), (0.9, "#ffffff", 0.8), (1, "#ffffff", 0)], 0, 0, 1, 0))
    body = ('<rect width="%d" height="%d" fill="url(#dp)"/>' % (w, h)
            + '<rect y="1" width="%d" height="1" fill="url(#dl)"/>' % w
            + '<rect y="%d" width="%d" height="1" fill="url(#dl)"/>' % (h - 2, w))
    return doc(w, h, body, defs)


def highlight(w, h):
    """Glowing glass band (stretched to the list width by the app)."""
    defs = (lin("hb", [(0, "#cfe8ff", 0.62), (0.45, "#8cc0ff", 0.42), (1, "#8cc0ff", 0.14)], 0, 0, 1, 0)
            + lin("hv", [(0, "#ffffff", 0.28), (0.5, "#ffffff", 0), (1, "#000a24", 0.12)])
            + lin("hl", [(0, "#ffffff", 1), (0.6, "#ffffff", 0.7), (1, "#ffffff", 0.25)], 0, 0, 1, 0))
    body = ('<rect width="%d" height="%d" fill="url(#hb)"/>' % (w, h)
            + '<rect width="%d" height="%d" fill="url(#hv)"/>' % (w, h)
            + '<rect width="%d" height="1" fill="url(#hl)"/>' % w
            + '<rect y="%d" width="%d" height="1" fill="url(#hl)" opacity="0.55"/>' % (h - 1, w))
    return doc(w, h, body, defs)


def progress_svgs():
    bkg = doc(464, 10, '<rect x="1" y="3" width="462" height="4" rx="2" fill="#ffffff" opacity="0.22"/>'
                       '<rect x="1" y="3" width="462" height="1" fill="#ffffff" opacity="0.25"/>')
    bar = doc(464, 6, '<defs><linearGradient id="p" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#7fb8ff"/>'
                      '<stop offset="1" stop-color="#ffffff"/></linearGradient>'
                      '<filter id="g" x="-5%" y="-100%" width="110%" height="300%"><feGaussianBlur stdDeviation="1"/></filter></defs>'
                      '<rect x="1" y="1" width="462" height="4" rx="2" fill="#bfe0ff" opacity="0.8" filter="url(#g)"/>'
                      '<rect x="1" y="1" width="462" height="4" rx="2" fill="url(#p)"/>')
    return bkg, bar


def nocover(s=118):
    gdefs, gbody = glass(s, s, 0.38, 6)
    body = (gbody + glyph("music", s / 2, s / 2, 56, True)
            + '<rect x="0.5" y="0.5" width="%d" height="%d" rx="6" fill="none" stroke="#ffffff" stroke-opacity="0.35"/>' % (s - 1, s - 1))
    return doc(s, s, body, DEFS + gdefs)


def small_icons():
    """List and status icons: white glyphs sized for the 18 px rows and the bars."""
    jobs = {}

    def icon(name, w, h, body, defs=""):
        jobs["icon_" + name] = (doc(w, h, body, DEFS + defs), w, h)

    icon("folder", 19, 16, glyph("folder", 9.5, 8, 17.5))
    icon("music", 16, 16, glyph("music", 8, 8, 15))
    icon("star", 16, 16, glyph("star", 8, 8, 15))
    icon("blankstar", 16, 16, '<g opacity="0.45">%s</g>' % glyph("star", 8, 8, 15))
    icon("volume", 16, 16, '<g filter="url(#sh)" fill="#ffffff"><polygon points="2,6 5,6 9,2.5 9,13.5 5,10 2,10"/></g>'
         '<g filter="url(#sh)" fill="none" stroke="#ffffff" stroke-width="1.4" stroke-linecap="round">'
         '<path d="M11 5.5 Q12.8 8 11 10.5"/><path d="M12.8 3.5 Q15.6 8 12.8 12.5"/></g>')
    icon("headphone", 16, 16, '<g filter="url(#sh)" fill="none" stroke="#ffffff" stroke-width="1.7">'
         '<path d="M2.6 10 V8 Q2.6 2.4 8 2.4 Q13.4 2.4 13.4 8 V10"/></g>'
         '<g filter="url(#sh)" fill="#ffffff"><rect x="1.6" y="8.6" width="3.6" height="5.6" rx="1.2"/>'
         '<rect x="10.8" y="8.6" width="3.6" height="5.6" rx="1.2"/></g>')
    icon("cpu", 16, 16, '<g filter="url(#sh)"><rect x="3.5" y="3.5" width="9" height="9" rx="1.2" fill="#ffffff"/>'
         '<g stroke="#ffffff" stroke-width="1.1">%s</g><rect x="6" y="6" width="4" height="4" fill="#1c3f86" opacity="0.5"/></g>'
         % "".join('<line x1="%s" y1="1" x2="%s" y2="15"/><line x1="1" y1="%s" x2="15" y2="%s"/>' % (v, v, v, v) for v in (5.5, 8, 10.5)))
    for name, frac, fill in (("battery", 0.8, "#ffffff"), ("batterycharging", 0.8, "#9fe6a8"), ("batterylow", 0.2, "#ff8f80")):
        icon(name, 30, 14, '<g filter="url(#sh)"><rect x="1.5" y="2" width="24" height="10" rx="2" fill="none" stroke="#ffffff" stroke-width="1.4"/>'
             '<rect x="26" y="5" width="2.4" height="4" rx="0.8" fill="#ffffff"/>'
             '<rect x="3.6" y="4.1" width="%s" height="5.8" rx="1" fill="%s"/></g>' % (f(19.8 * frac), fill))
    return jobs


def ml_item(i, selected):
    name, g = ML_ITEMS[i]
    if selected:
        body = (glyph(g, 16, ITEM_H / 2, 26, True)
                + label(35, ITEM_H / 2 + 5, name, 14, 600, "start", True))
    else:
        body = (glyph(g, 16, ITEM_H / 2, 16, False, 0.7)
                + label(35, ITEM_H / 2 + 4.2, name, 12, 400, "start", False, 0.72))
    return doc(ITEM_W, ITEM_H, body, DEFS)


class Crossbar(Theme):
    name = "Crossbar"
    desc = "PlayStation XMB style: wave background, category icons, Media Library cross"
    font = "flash0:/font/ltn0.pgf"  # the PSP's own sans
    size = 58
    colors = {
        "TOOLBAR_TEXT": "#ffffff", "TOOLBAR_TEXT_SHADOW": (0, 8, 30, 170),
        "BUTTONBAR_TEXT": (0, 0, 0, 0), "BUTTONBAR_TEXT_SHADOW": (0, 0, 0, 0),  # names are in the icons
        "BUTTONBAR_SELECTED_TEXT": (0, 0, 0, 0), "BUTTONBAR_SELECTED_TEXT_SHADOW": (0, 0, 0, 0),
        "POPUP_TITLE_TEXT": "#ffffff", "POPUP_TITLE_TEXT_SHADOW": (0, 8, 30, 200),
        "POPUP_MESSAGE_TEXT": "#e4ecf8", "POPUP_MESSAGE_TEXT_SHADOW": (0, 8, 30, 200),
        "MENU_TEXT": "#e2eaf7", "MENU_TEXT_SHADOW": (0, 8, 30, 190),
        "MENU_SELECTED_TEXT": "#ffffff", "MENU_SELECTED_TEXT_SHADOW": (10, 40, 110, 230),
        "LABEL_TEXT": "#a6c6f2", "LABEL_TEXT_SHADOW": (0, 8, 30, 190),
        "TEXT": "#ffffff", "TEXT_SHADOW": (0, 8, 30, 190),
        "HELP_TITLE_TEXT": "#ffffff", "HELP_TITLE_TEXT_SHADOW": (0, 8, 30, 200),
        "HELP_TEXT": "#e4ecf8", "HELP_TEXT_SHADOW": (0, 8, 30, 200),
    }
    sizes = {"menubkg": (366, 188), "menuplaylistbkg": (472, 138), "medialibraryquerybkg": (472, 138),
             "medialibrarybkg": (472, 188), "menuhighlight": (480, 18)}
    for _i in range(1, 6):
        sizes["button%d" % _i] = (TAB_W, TAB_H)
        sizes["buttonsel%d" % _i] = (TAB_W, TAB_H)

    @property
    def layout(self):
        lay = {"MENU_INTERLINE": "1", "MEDIALIBRARY_MAP": "1",
               "POS_FILE_BROWSER": "4,%d" % CONTENT_Y, "POS_SETTINGS": "4,%d" % CONTENT_Y,
               "POS_FILE_BROWSER_COVERART": "380,72", "FILE_BROWSER_COVERART_WIDTH": "92", "FILE_BROWSER_COVERART_HEIGHT": "92",
               "POS_PLAYLIST_BROWSER": "4,%d" % CONTENT_Y, "POS_PLAYLIST_EDITOR": "4,%d" % CONTENT_Y,
               "POS_MEDIALIBRARY_QUERY": "4,%d" % CONTENT_Y, "POS_MEDIALIBRARY": "4,%d" % CONTENT_Y}
        for i in range(5):
            lay["POS_BUTTON_%d" % (i + 1)] = "%d,%d" % (TAB_X0 + i * TAB_STEP, TAB_Y)
        for i in range(9):
            lay["POS_MEDIALIBRARY_MAP_ITEM_%d" % (i + 1)] = "%d,%d" % (ML_X, ML_Y0 + i * ML_STEP)
        return lay

    def svg_jobs(self, sizes):
        jobs = {"bkg_default": (wave_background(), 480, 272),
                "toptoolbar": (status_bar(480, 21, True), 480, 21),
                "bottomtoolbar": (status_bar(480, 20, False), 480, 20),
                "menuhighlight": (highlight(*sizes["menuhighlight"]),) + sizes["menuhighlight"],
                "nocoverart": (nocover(), 118, 118)}
        for i in range(5):
            jobs["button%d" % (i + 1)] = (tab_svg(i, False), TAB_W, TAB_H)
            jobs["buttonsel%d" % (i + 1)] = (tab_svg(i, True), TAB_W, TAB_H)
        for n in PANEL_NAMES:
            w, h = sizes[n]
            if n == "medialibrarybkg":
                jobs[n] = (doc(w, h, ""), w, h)  # the cross floats on the wave
            elif n in ("popupbkg", "helpbkg", "medialibraryscanbkg"):
                jobs[n] = (dialog_panel(w, h), w, h)
            else:
                jobs[n] = (glass_panel(w, h, 0.36), w, h)
        bkg, bar = progress_svgs()
        jobs["progressbkg"] = (bkg, 464, 10)
        jobs["progress"] = (bar, 464, 6)
        for i in range(9):
            jobs["mlitem%d" % (i + 1)] = (ml_item(i, False), ITEM_W, ITEM_H)
            jobs["mlitemsel%d" % (i + 1)] = (ml_item(i, True), ITEM_W, ITEM_H)
        jobs.update(small_icons())
        return jobs

    def images(self, sizes):
        imgs = render(self.name, self.svg_jobs(sizes), fonts=CROSS_FONTS)
        self._extras = {k: imgs.pop(k) for k in list(imgs) if k.startswith("mlitem")}
        for k in [k for k in imgs if k.startswith("icon_")]:
            imgs[k[5:]] = imgs.pop(k)
        return imgs

    def extra_images(self):
        return self._extras


THEMES = {"crossbar": Crossbar}
