#!/usr/bin/env python3
"""Luna (Windows XP style) with a desktop for the Media Library.

The Media Library home screen becomes a desktop: nine icons on the wallpaper
(the map menu, MEDIALIBRARY_MAP=1), a decorative Recycle Bin, and a taskbar
button that shows the selected entry's name (the map caption). The wallpaper,
title bar, taskbar and icons are SVG rendered with Chromium like the Pit Lane
skins; the panels, tabs and list icons still come from Luna in make_skins.py.

The icons are original drawings in the XP style: no Microsoft artwork or logos.
Icon labels use DejaVu Sans Condensed (Bitstream Vera license, see
fonts/LICENSE-DejaVu.txt), the closest free match to XP's Tahoma.
"""
import math
import os

from PIL import ImageFont

from make_skins import Luna
from gt_skins import FONT_DIR, FONT_FILES, doc, f, pts, text, render, pointer

DEJAVU = "DejaVu Sans Condensed"
XP_FONTS = FONT_FILES + [
    (DEJAVU, "400", "normal", "DejaVuSansCondensed.ttf"),
    (DEJAVU, "700", "italic", "DejaVuSansCondensed-BoldOblique.ttf"),
]
LABEL_SIZE = 12
XP_SELECT = "#316ac5"  # XP's selection blue


def label_width(s, size=LABEL_SIZE):
    return ImageFont.truetype(os.path.join(FONT_DIR, "DejaVuSansCondensed.ttf"), size).getlength(s)


# ---------------------------------------------------------------------------
# SVG bits
# ---------------------------------------------------------------------------
def _stops(stops):
    out = []
    for st in stops:
        op = "" if len(st) < 3 else ' stop-opacity="%s"' % f(st[2])
        out.append('<stop offset="%s" stop-color="%s"%s/>' % (f(st[0]), st[1], op))
    return "".join(out)


def lin(gid, stops, x1=0, y1=0, x2=0, y2=1, user=False):
    u = ' gradientUnits="userSpaceOnUse"' if user else ""
    return '<linearGradient id="%s" x1="%s" y1="%s" x2="%s" y2="%s"%s>%s</linearGradient>' % (
        gid, f(x1), f(y1), f(x2), f(y2), u, _stops(stops))


def rad(gid, stops, cx=0.5, cy=0.5, r=0.5, fx=None, fy=None, user=False):
    u = ' gradientUnits="userSpaceOnUse"' if user else ""
    fxy = "" if fx is None else ' fx="%s" fy="%s"' % (f(fx), f(fy))
    return '<radialGradient id="%s" cx="%s" cy="%s" r="%s"%s%s>%s</radialGradient>' % (
        gid, f(cx), f(cy), f(r), fxy, u, _stops(stops))


def outlined(shapes, fill, edge, width):
    """Draw shapes with one outline around their union (no seams where they overlap)."""
    return ('<g fill="%s" stroke="%s" stroke-width="%s" stroke-linejoin="round">%s</g>' % (edge, edge, f(width), shapes)
            + '<g fill="%s">%s</g>' % (fill, shapes))


def shadow_filter(fid, dx=1.2, dy=1.6, blur=1.1, opacity=0.4, color="#000"):
    return ('<filter id="%s" x="-30%%" y="-30%%" width="160%%" height="160%%"><feDropShadow dx="%s" dy="%s" '
            'stdDeviation="%s" flood-color="%s" flood-opacity="%s"/></filter>') % (fid, f(dx), f(dy), f(blur), color, f(opacity))


# ---------------------------------------------------------------------------
# Icons: 40x40, XP style (bright gradients, dark same-hue outlines, light
# from the top left). Each returns (defs, body); p prefixes the ids.
# ---------------------------------------------------------------------------
PIPS = {1: [(.5, .5)], 2: [(.27, .27), (.73, .73)], 3: [(.24, .24), (.5, .5), (.76, .76)],
        4: [(.27, .27), (.73, .27), (.27, .73), (.73, .73)],
        5: [(.25, .25), (.75, .25), (.5, .5), (.25, .75), (.75, .75)],
        6: [(.27, .22), (.27, .5), (.27, .78), (.73, .22), (.73, .5), (.73, .78)]}


def cube(cx, cy, s, grads, pips, edge, pip, one=None):
    """Isometric die: top/left/right faces with pips mapped onto each face."""
    h = s * 0.866
    top = [(cx - h, cy - s / 2), (cx, cy - s), (cx + h, cy - s / 2), (cx, cy)]
    left = [(cx - h, cy - s / 2), (cx, cy), (cx, cy + s), (cx - h, cy + s / 2)]
    right = [(cx, cy), (cx + h, cy - s / 2), (cx + h, cy + s / 2), (cx, cy + s)]
    out = ""
    for poly, g in zip((top, left, right), grads):
        out += '<polygon points="%s" fill="url(#%s)" stroke="%s" stroke-width="0.9" stroke-linejoin="round"/>' % (
            pts(poly), g, edge)
    out += '<polyline points="%s" fill="none" stroke="#ffffff" stroke-width="0.7" opacity="0.65"/>' % pts(
        [(top[0][0] + 0.8, top[0][1] + 0.3), top[3], (top[2][0] - 0.8, top[2][1] + 0.3)])
    frames = [(top[0], top[1], top[3]), (left[0], left[1], left[3]), (right[0], right[1], right[3])]
    for (a, b, d), n in zip(frames, pips):
        r = 0.17 if n == 1 else 0.12
        col = one if (n == 1 and one) else pip
        dots = "".join('<circle cx="%s" cy="%s" r="%s"/>' % (f(u), f(v), f(r)) for u, v in PIPS[n])
        out += '<g transform="matrix(%s %s %s %s %s %s)" fill="%s">%s</g>' % (
            f(b[0] - a[0]), f(b[1] - a[1]), f(d[0] - a[0]), f(d[1] - a[1]), f(a[0]), f(a[1]), col, dots)
    return out


def icon_dice(p):
    defs = (lin(p + "wt", [(0, "#ffffff"), (1, "#eef1f6")]) + lin(p + "wl", [(0, "#e8ecf2"), (1, "#c3cad6")])
            + lin(p + "wr", [(0, "#c8cfda"), (1, "#9aa5b7")])
            + lin(p + "rt", [(0, "#ff8a76"), (1, "#ee3d27")]) + lin(p + "rl", [(0, "#e03422"), (1, "#b21b10")])
            + lin(p + "rr", [(0, "#b31e12"), (1, "#7a0e07")]))
    body = (cube(14.5, 15, 8.8, (p + "rt", p + "rl", p + "rr"), (3, 1, 2), "#4a0905", "#ffffff")
            + cube(25, 24.5, 10.2, (p + "wt", p + "wl", p + "wr"), (1, 2, 3), "#3d4452", "#1b1d22", "#d42316"))
    return defs, body


def folder(p, note=True):
    defs = (lin(p + "fb", [(0, "#f7cf63"), (1, "#d99721")]) + lin(p + "ff", [(0, "#fff3bd"), (0.3, "#ffdc6e"), (1, "#f1ad2c")])
            + lin(p + "fn", [(0, "#a6d0ff"), (0.45, "#3f84f0"), (1, "#1446b0")]))
    body = ('<path d="M3.5 9 Q3.5 6.5 6 6.5 H13.5 Q14.6 6.5 15.4 7.4 L17.2 9.5 H33 Q35.5 9.5 35.5 12 V31.5 '
            'Q35.5 34 33 34 H6 Q3.5 34 3.5 31.5 Z" fill="url(#%sfb)" stroke="#a46c10" stroke-width="1"/>' % p
            + '<rect x="7" y="11.5" width="25" height="15" fill="#ffffff" stroke="#c9ced8" stroke-width="0.6" '
              'transform="rotate(-3 19 19)"/>'
            + '<path d="M2.5 17.2 Q2.6 15.4 4.4 15.4 H35.8 Q37.6 15.4 37.4 17.2 L36 32 Q35.7 34.6 33.2 34.6 H5.6 '
              'Q3.1 34.6 2.9 32 Z" fill="url(#%sff)" stroke="#a46c10" stroke-width="1"/>' % p
            + '<path d="M4.3 16.6 H35.6" stroke="#fffbe6" stroke-width="1" opacity="0.9"/>')
    if note:
        shapes = ('<ellipse cx="22.3" cy="30.2" rx="3.3" ry="2.5" transform="rotate(-22 22.3 30.2)"/>'
                  '<ellipse cx="31.3" cy="28.2" rx="3.3" ry="2.5" transform="rotate(-22 31.3 28.2)"/>'
                  '<rect x="24.2" y="19" width="1.9" height="11"/><rect x="33.2" y="17" width="1.9" height="11"/>'
                  '<polygon points="24.2,19 35.1,16.6 35.1,20.3 24.2,22.7"/>')
        body += outlined(shapes, "url(#%sfn)" % p, "#0b358a", 1.6)
        body += ('<ellipse cx="21.4" cy="29.4" rx="1.3" ry="0.7" fill="#ffffff" opacity="0.7" transform="rotate(-22 21.4 29.4)"/>'
                 '<ellipse cx="30.4" cy="27.4" rx="1.3" ry="0.7" fill="#ffffff" opacity="0.7" transform="rotate(-22 30.4 27.4)"/>')
    return defs, body


def icon_my_music(p):
    return folder(p)


def icon_mic(p):
    defs = (rad(p + "hd", [(0, "#ffffff"), (0.3, "#dfe3ea"), (0.72, "#8c95a5"), (1, "#454c5a")], cx=0.36, cy=0.3, r=0.78)
            + lin(p + "hn", [(0, "#666b76"), (0.4, "#2c2f36"), (1, "#0d0e11")], 0, 0, 1, 0)
            + lin(p + "co", [(0, "#f4f6f9"), (0.5, "#a3abb8"), (1, "#5a6270")], 0, 0, 1, 0)
            + '<clipPath id="%sclip"><circle cx="20" cy="11" r="8.3"/></clipPath>' % p)
    mesh = "".join('<line x1="%s" y1="0" x2="%s" y2="22" />' % (f(x), f(x - 9)) for x in range(10, 40, 2)) + \
        "".join('<line x1="%s" y1="0" x2="%s" y2="22" />' % (f(x), f(x + 9)) for x in range(0, 30, 2))
    body = ('<g transform="rotate(32 20 22)">'
            '<path d="M15.6 22.3 H24.4 L22.7 36.8 Q20 38.6 17.3 36.8 Z" fill="url(#%shn)" stroke="#060708" stroke-width="0.8"/>' % p
            + '<rect x="19" y="26.5" width="2" height="4" rx="0.9" fill="#68d468" stroke="#1d5e1d" stroke-width="0.4"/>'
            + '<path d="M14.4 18.3 H25.6 L24.6 22.6 H15.4 Z" fill="url(#%sco)" stroke="#353b46" stroke-width="0.8"/>' % p
            + '<circle cx="20" cy="11" r="9" fill="url(#%shd)" stroke="#353b46" stroke-width="1"/>' % p
            + '<g clip-path="url(#%sclip)" stroke="#4b5363" stroke-width="0.45" opacity="0.5">%s</g>' % (p, mesh)
            + '<path d="M11.4 11.6 Q20 14.6 28.6 11.6" fill="none" stroke="#e9edf3" stroke-width="1.6" opacity="0.85"/>'
            + '<path d="M11.4 11.6 Q20 14.6 28.6 11.6" fill="none" stroke="#5a6272" stroke-width="0.5" transform="translate(0 1)"/>'
            + '<ellipse cx="16.6" cy="7.2" rx="3.2" ry="2" fill="#ffffff" opacity="0.75" transform="rotate(-30 16.6 7.2)"/>'
            + '</g>')
    return defs, body


def disc(p, cx, cy, r, hub=True):
    """A CD: silver with a rainbow sheen, clear hub and a hole."""
    defs = (rad(p + "sv", [(0, "#ffffff"), (0.55, "#dde2ea"), (1, "#a2abba")], cx=0.4, cy=0.35, r=0.7)
            + '<clipPath id="%sdc"><circle cx="%s" cy="%s" r="%s"/></clipPath>' % (p, f(cx), f(cy), f(r))
            + '<mask id="%shole"><rect x="0" y="0" width="40" height="40" fill="#fff"/>'
              '<circle cx="%s" cy="%s" r="%s" fill="#000"/></mask>' % (p, f(cx), f(cy), f(r * 0.18)))
    wedges = ""
    n = 36
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        hue = (i * 360 / n * 2) % 360
        op = 0.12 + 0.42 * abs(math.sin(a0 * 2 + 0.6))
        wedges += '<polygon points="%s" fill="hsl(%d,95%%,62%%)" opacity="%s"/>' % (
            pts([(cx, cy), (cx + 2 * r * math.cos(a0), cy + 2 * r * math.sin(a0)),
                 (cx + 2 * r * math.cos(a1), cy + 2 * r * math.sin(a1))]), hue, f(op))
    body = ('<g mask="url(#%shole)">' % p
            + '<circle cx="%s" cy="%s" r="%s" fill="url(#%ssv)"/>' % (f(cx), f(cy), f(r), p)
            + '<g clip-path="url(#%sdc)">%s</g>' % (p, wedges)
            + ('<circle cx="%s" cy="%s" r="%s" fill="#eef2f7" opacity="0.75" stroke="#9aa3b2" stroke-width="0.5"/>'
               % (f(cx), f(cy), f(r * 0.4)) if hub else "")
            + '<circle cx="%s" cy="%s" r="%s" fill="none" stroke="#6d7686" stroke-width="0.8"/>' % (f(cx), f(cy), f(r - 0.4))
            + '<circle cx="%s" cy="%s" r="%s" fill="none" stroke="#7d8696" stroke-width="0.6"/>' % (f(cx), f(cy), f(r * 0.18 + 0.3))
            + '</g>')
    return defs, body


def icon_album(p):
    ddefs, dbody = disc(p, 27, 19.5, 12)
    defs = ddefs + (lin(p + "cv", [(0, "#3a6be0"), (0.55, "#5a3cc8"), (1, "#8a2fb5")], 0, 0, 1, 1)
                    + lin(p + "gl", [(0, "#ffffff", 0.55), (0.5, "#ffffff", 0.08), (1, "#ffffff", 0)], 0, 0, 1, 1))
    body = (dbody
            + '<rect x="3.5" y="6.5" width="22.5" height="27.5" rx="1.4" fill="url(#%scv)" stroke="#1b2236" stroke-width="1"/>' % p
            + '<circle cx="18.5" cy="15" r="4.2" fill="#ffd54a" stroke="#c98a12" stroke-width="0.6"/>'
            + '<path d="M6 27 Q10 21.5 14 25.5 T22 24 T26 25 V33.5 H6 Z" fill="#2ad1d8" opacity="0.85"/>'
            + '<path d="M6 30 Q11 26 15 29 T26 28.5 V33.5 H6 Z" fill="#1a9fb8"/>'
            + '<rect x="3.5" y="6.5" width="3.2" height="27.5" fill="#141a2b" opacity="0.85"/>'
            + '<polygon points="7,7.5 25,7.5 25,13 7,24" fill="url(#%sgl)"/>' % p
            + '<rect x="3.5" y="6.5" width="22.5" height="27.5" rx="1.4" fill="none" stroke="#0f1424" stroke-width="1"/>')
    return defs, body


def icon_guitar(p):
    defs = (rad(p + "sb", [(0, "#ffd34a"), (0.4, "#f58c12"), (0.78, "#b0280b"), (1, "#3a0d05")], cx=0.5, cy=0.6, r=0.6)
            + lin(p + "nk", [(0, "#c08a50"), (1, "#7a4a1e")], 0, 0, 1, 0))
    bodyp = ("M20 22.5 C17.5 22.5 16.5 20.5 14.2 21.2 C11.2 22.2 11.6 25.6 12.8 27.4 C10.6 29.2 10 32.8 11.8 35.4 "
             "C13.8 38.2 18 38.4 20 37.8 C22 38.4 26.2 38.2 28.2 35.4 C30 32.8 29.4 29.2 27.2 27.4 "
             "C28.4 25.6 28.8 22.2 25.8 21.2 C23.5 20.5 22.5 22.5 20 22.5 Z")
    frets = "".join('<line x1="19" y1="%s" x2="21.2" y2="%s"/>' % (f(y), f(y)) for y in (6.5, 9.5, 12.5, 15.2, 17.8, 20.2))
    strings = "".join('<line x1="%s" y1="2" x2="%s" y2="35"/>' % (f(x), f(x)) for x in (19.55, 20.1, 20.65))
    body = ('<g transform="rotate(38 20 21)">'
            '<path d="%s" fill="url(#%ssb)" stroke="#260803" stroke-width="0.9"/>' % (bodyp, p)
            + '<path d="M21.2 25.6 C24.4 25.2 27.4 27 27.6 30.2 C27.8 33.2 25 35.6 21.6 35.1 Z" fill="#f6f2ea" stroke="#a8a090" stroke-width="0.4"/>'
            + '<rect x="18.95" y="2.5" width="2.3" height="22" fill="url(#%snk)" stroke="#3a2410" stroke-width="0.5"/>' % p
            + '<g stroke="#efe2c4" stroke-width="0.45">%s</g>' % frets
            + '<rect x="18.3" y="0.4" width="3.6" height="4.4" rx="0.9" fill="#2a1a0c" stroke="#120a04" stroke-width="0.4"/>'
            + "".join('<circle cx="%s" cy="%s" r="0.75" fill="#d9dde3"/>' % (f(x), f(y)) for x in (17.7, 22.5) for y in (1.6, 3.6))
            + '<rect x="17" y="27.4" width="6.2" height="1.9" rx="0.4" fill="#141414"/>'
            + '<rect x="17" y="30.8" width="6.2" height="1.9" rx="0.4" fill="#141414"/>'
            + '<rect x="17.4" y="34" width="5.4" height="1.5" rx="0.3" fill="#c3c8d0" stroke="#5b616b" stroke-width="0.3"/>'
            + '<g stroke="#f4f4f4" stroke-width="0.25" opacity="0.85">%s</g>' % strings
            + '<path d="M13.4 24 C12.6 25.6 13 27 13.8 27.8" fill="none" stroke="#ffe9a8" stroke-width="0.8" opacity="0.6"/>'
            + '</g>')
    return defs, body


def icon_star(p):
    cx, cy, R, r = 20, 21.5, 17.5, 7.3
    outer = [(cx + R * math.cos(math.radians(-90 + 72 * k)), cy + R * math.sin(math.radians(-90 + 72 * k))) for k in range(5)]
    inner = [(cx + r * math.cos(math.radians(-54 + 72 * k)), cy + r * math.sin(math.radians(-54 + 72 * k))) for k in range(5)]
    light = math.radians(-125)  # light from the top left
    facets = ""
    for k in range(5):
        for side, iv in ((0, inner[k - 1]), (1, inner[k])):
            mx = (outer[k][0] + iv[0] + cx) / 3 - cx
            my = (outer[k][1] + iv[1] + cy) / 3 - cy
            t = 0.5 + 0.5 * math.cos(math.atan2(my, mx) - light)
            t = t * 0.75 + (0.25 if side == 0 else 0.0)
            c = tuple(int(lo + (hi - lo) * t) for lo, hi in zip((232, 146, 0), (255, 240, 150)))
            facets += '<polygon points="%s" fill="rgb(%d,%d,%d)"/>' % (pts([(cx, cy), outer[k], iv]), c[0], c[1], c[2])
    star = [pt for k in range(5) for pt in (outer[k], inner[k])]
    body = ('<polygon points="%s" fill="#f2b51c" stroke="#9a5c06" stroke-width="2" stroke-linejoin="round"/>' % pts(star)
            + facets
            + '<polygon points="%s" fill="none" stroke="#9a5c06" stroke-width="1" stroke-linejoin="round"/>' % pts(star)
            + '<ellipse cx="15.5" cy="15.5" rx="2.6" ry="1.4" fill="#ffffff" opacity="0.7" transform="rotate(-35 15.5 15.5)"/>')
    return "", body


def bar3d(x, w, h, base, front, side, top, edge):
    d = 2.2  # depth offset
    fr = [(x, base - h), (x + w, base - h), (x + w, base), (x, base)]
    sd = [(x + w, base - h), (x + w + d, base - h - d * 0.7), (x + w + d, base - d * 0.7), (x + w, base)]
    tp = [(x, base - h), (x + d, base - h - d * 0.7), (x + w + d, base - h - d * 0.7), (x + w, base - h)]
    return "".join('<polygon points="%s" fill="%s" stroke="%s" stroke-width="0.6" stroke-linejoin="round"/>' % (pts(poly), c, edge)
                   for poly, c in ((fr, front), (sd, side), (tp, top)))


def icon_chart(p):
    defs = lin(p + "sh", [(0, "#ffffff"), (1, "#e3e9f3")]) + lin(p + "g", [(0, "#7be07b"), (1, "#2e9e2e")]) + \
        lin(p + "y", [(0, "#ffe36e"), (1, "#f0a20e")]) + lin(p + "r", [(0, "#ff8a6e"), (1, "#d92a14")])
    grid = "".join('<line x1="10" y1="%s" x2="31" y2="%s"/>' % (f(y), f(y)) for y in (14, 19.5, 25, 30.5))
    body = ('<path d="M7 3.5 H26.5 L33.5 10.5 V37 H7 Z" fill="url(#%ssh)" stroke="#6f7b8f" stroke-width="1"/>' % p
            + '<path d="M26.5 3.5 V10.5 H33.5 Z" fill="#cfd7e5" stroke="#6f7b8f" stroke-width="0.8" stroke-linejoin="round"/>'
            + '<g stroke="#c4d3ea" stroke-width="0.6">%s</g>' % grid
            + bar3d(10.2, 4.8, 8, 33.5, "url(#%sg)" % p, "#1f7a1f", "#b6f2b6", "#145214")
            + bar3d(17, 4.8, 13.5, 33.5, "url(#%sy)" % p, "#c27a06", "#fff2b0", "#7a4c02")
            + bar3d(23.8, 4.8, 20, 33.5, "url(#%sr)" % p, "#a11a0a", "#ffc2b0", "#6a0f05")
            + '<line x1="9" y1="33.6" x2="31.5" y2="33.6" stroke="#5a667a" stroke-width="0.9"/>')
    return defs, body


def icon_search(p):
    defs = (lin(p + "pg", [(0, "#ffffff"), (1, "#e6ecf5")])
            + rad(p + "gl", [(0, "#ffffff", 0.9), (0.45, "#bfe3ff", 0.75), (1, "#4f97d8", 0.85)], cx=0.38, cy=0.35, r=0.7)
            + lin(p + "rm", [(0, "#ffffff"), (0.5, "#b4bcc9"), (1, "#6a7383")], 0, 0, 1, 1)
            + lin(p + "hd", [(0, "#5b616d"), (0.5, "#1c1e23"), (1, "#060607")], 0, 0, 1, 1))
    lines = "".join('<line x1="7.5" y1="%s" x2="%s" y2="%s"/>' % (f(y), f(x2), f(y))
                    for y, x2 in ((9, 22), (12.5, 20), (16, 22), (19.5, 18), (23, 21), (26.5, 19)))
    body = ('<rect x="4.5" y="4" width="21" height="28" fill="url(#%spg)" stroke="#6f7b8f" stroke-width="1"/>' % p
            + '<g stroke="#9fb4d4" stroke-width="1.2">%s</g>' % lines
            + '<line x1="28" y1="26" x2="35" y2="33" stroke="#060607" stroke-width="6.6" stroke-linecap="round"/>'
            + '<line x1="28" y1="26" x2="35" y2="33" stroke="url(#%shd)" stroke-width="5" stroke-linecap="round"/>' % p
            + '<line x1="28.6" y1="25.6" x2="34.2" y2="31.2" stroke="#8b929e" stroke-width="1" stroke-linecap="round" opacity="0.8"/>'
            + '<line x1="26.4" y1="24.4" x2="28.6" y2="26.6" stroke="#2a2d33" stroke-width="5.4" stroke-linecap="round"/>'
            + '<line x1="26.4" y1="24.4" x2="28.6" y2="26.6" stroke="#c9ced6" stroke-width="3.6" stroke-linecap="round"/>'
            + '<circle cx="21" cy="19" r="10.1" fill="none" stroke="#2f3540" stroke-width="1"/>'
            + '<circle cx="21" cy="19" r="8.6" fill="url(#%sgl)"/>' % p
            + '<circle cx="21" cy="19" r="8.7" fill="none" stroke="url(#%srm)" stroke-width="2.6"/>' % p
            + '<circle cx="21" cy="19" r="7.3" fill="none" stroke="#3b4350" stroke-width="0.6"/>'
            + '<path d="M15.6 17.4 A5.8 5.8 0 0 1 20 13.2" fill="none" stroke="#ffffff" stroke-width="1.6" stroke-linecap="round" opacity="0.9"/>')
    return defs, body


def icon_computer(p):
    defs = (lin(p + "tf", [(0, "#f6f2e6"), (1, "#d4cbb1")]) + lin(p + "ts", [(0, "#c8bd9d"), (1, "#a2967a")])
            + lin(p + "bz", [(0, "#f8f5ec"), (1, "#d2c9ae")]) + lin(p + "sc", [(0, "#4f97ff"), (1, "#0e4cc2")])
            + lin(p + "ft", [(0, "#efe9d8"), (1, "#b9af90")]))
    edge = "#6a624b"
    body = (
        # tower, behind on the right
        '<polygon points="22.5,5.5 26.5,3 37.5,3 33.5,5.5" fill="#fbf8ef" stroke="%s" stroke-width="0.8" stroke-linejoin="round"/>' % edge
        + '<polygon points="33.5,5.5 37.5,3 37.5,30.5 33.5,33" fill="url(#%sts)" stroke="%s" stroke-width="0.8" stroke-linejoin="round"/>' % (p, edge)
        + '<rect x="22.5" y="5.5" width="11" height="27.5" fill="url(#%stf)" stroke="%s" stroke-width="0.8"/>' % (p, edge)
        + '<rect x="24.6" y="8" width="7" height="1.7" fill="#8f8772"/><rect x="24.6" y="11.3" width="7" height="1.7" fill="#8f8772"/>'
        + '<circle cx="28.1" cy="26.5" r="1.3" fill="#d6cdb3" stroke="#8f8772" stroke-width="0.4"/>'
        + '<circle cx="31.6" cy="30.6" r="0.75" fill="#3ad83a"/>'
        # monitor in front
        + '<rect x="2" y="8" width="25" height="21" rx="2" fill="url(#%sbz)" stroke="%s" stroke-width="1"/>' % (p, edge)
        + '<rect x="4.8" y="10.8" width="19.4" height="14.6" rx="1" fill="url(#%ssc)" stroke="#2a2a2a" stroke-width="0.8"/>' % p
        + '<path d="M5.2 21.4 Q11 16.8 16.5 18.6 T23.8 18.4 V25 H5.2 Z" fill="#5ab232"/>'
        + '<path d="M5.2 23 Q12 19.6 23.8 21.6 V25 H5.2 Z" fill="#3f8f22"/>'
        + '<polygon points="5.2,11.2 15,11.2 5.2,19" fill="#ffffff" opacity="0.22"/>'
        + '<circle cx="23.8" cy="27.3" r="0.65" fill="#3ad83a"/>'
        + '<rect x="12" y="29" width="5" height="2.4" fill="#cfc6ab" stroke="%s" stroke-width="0.6"/>' % edge
        + '<ellipse cx="14.5" cy="33" rx="8.2" ry="2.1" fill="url(#%sft)" stroke="%s" stroke-width="0.8"/>' % (p, edge))
    return defs, body


def icon_bin(p):
    defs = (lin(p + "bd", [(0, "#b9d0b4"), (0.3, "#eef6ec"), (0.65, "#a7c3a2"), (1, "#6f8e6a")], 0, 0, 1, 0)
            + lin(p + "rm", [(0, "#f2f8f0"), (1, "#93b28f")]))
    ribs = ""
    for i in range(1, 6):
        t = i / 6
        x0, x1 = 7.5 + 25 * t, 10.5 + 19 * t
        ribs += '<line x1="%s" y1="11" x2="%s" y2="35"/>' % (f(x0), f(x1))
    arrows = ('<g fill="none" stroke="#2f9a3a" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">'
              '<path d="M17.2 26.5 L20 21.8 L22.8 26.5 Z"/></g>'
              '<g fill="#2f9a3a"><polygon points="19,21.6 21.6,20.6 21.2,23.2"/>'
              '<polygon points="23.6,25.4 23.4,28 21.3,26.6"/><polygon points="16.4,27.2 18.2,25.4 18.9,27.8"/></g>')
    body = ('<path d="M7.5 10 L10.5 34.6 Q20 38.4 29.5 34.6 L32.5 10 Z" fill="url(#%sbd)" stroke="#45603f" stroke-width="1" stroke-linejoin="round"/>' % p
            + '<g stroke="#68875f" stroke-width="0.7" opacity="0.7">%s</g>' % ribs
            + arrows
            + '<ellipse cx="20" cy="10" rx="12.8" ry="3.7" fill="url(#%srm)" stroke="#45603f" stroke-width="1"/>' % p
            + '<ellipse cx="20" cy="10.2" rx="10.6" ry="2.5" fill="#56724f"/>'
            + '<path d="M11 12 L13 33" stroke="#ffffff" stroke-width="1.2" opacity="0.5"/>')
    return defs, body


def note_glyph(x, y, s, fill, edge=None):
    """A single eighth note (beamless) for small badges; (x, y) is the top-left of an s x s box."""
    k = s / 16.0
    shapes = ('<ellipse cx="%s" cy="%s" rx="%s" ry="%s" transform="rotate(-22 %s %s)"/>' % (
        f(x + 5.6 * k), f(y + 12.6 * k), f(3.3 * k), f(2.5 * k), f(x + 5.6 * k), f(y + 12.6 * k))
        + '<rect x="%s" y="%s" width="%s" height="%s"/>' % (f(x + 7.6 * k), f(y + 2 * k), f(1.8 * k), f(10.6 * k))
        + '<path d="M%s %s q%s %s %s %s q-%s -%s -%s -%s z"/>' % (
            f(x + 9.4 * k), f(y + 2 * k), f(4.2 * k), f(1.6 * k), f(3.6 * k), f(6.6 * k), f(0.6 * k), f(3.6 * k), f(3.6 * k), f(4.4 * k)))
    if edge:
        return outlined(shapes, fill, edge, 1.4 * k)
    return '<g fill="%s">%s</g>' % (fill, shapes)


ITEMS = [("Shuffle All", icon_dice), ("My Music", icon_my_music), ("Artists", icon_mic), ("Albums", icon_album),
         ("Genres", icon_guitar), ("Ratings", icon_star), ("Top 100", icon_chart), ("Search", icon_search),
         ("My Computer", icon_computer)]

CELL_W, CELL_H = 82, 60
ICON_X, ICON_Y = 21, 2


def desk_icon(label, icon_fn, selected=False, x=0, y=0, p="i"):
    """One desktop icon in an 82x60 cell at (x, y): picture, label, XP selection look."""
    defs, body = icon_fn(p)
    defs += shadow_filter(p + "ish", 1.2, 1.6, 1.1, 0.42)
    defs += shadow_filter(p + "lsh", 1, 1, 0.55, 0.95)
    pic = '<g filter="url(#%sish)"><g transform="translate(%s %s)">%s</g></g>' % (p, f(x + ICON_X), f(y + ICON_Y), body)
    cx, base = x + CELL_W / 2, y + 54
    tw = label_width(label)
    if not selected:
        return defs, pic + text(cx, base, label, LABEL_SIZE, "#ffffff", family=DEJAVU, weight=400).replace(
            "<text ", '<text filter="url(#%slsh)" ' % p)
    defs += ('<filter id="%ssel" x="0" y="0" width="100%%" height="100%%"><feFlood flood-color="%s" flood-opacity="0.5" result="c"/>'
             '<feComposite in="c" in2="SourceAlpha" operator="in" result="t"/>'
             '<feMerge><feMergeNode in="SourceGraphic"/><feMergeNode in="t"/></feMerge></filter>') % (p, XP_SELECT)
    defs += shadow_filter(p + "psh", 1, 1.2, 0.7, 0.5)
    pic = '<g filter="url(#%sish)"><g filter="url(#%ssel)"><g transform="translate(%s %s)">%s</g></g></g>' % (
        p, p, f(x + ICON_X), f(y + ICON_Y), body)
    bx, bw = round(cx - tw / 2 - 3), round(tw + 6)
    box = ('<rect x="%d" y="%d" width="%d" height="14" fill="%s"/>' % (bx, y + 43, bw, XP_SELECT)
           + '<rect x="%s" y="%s" width="%d" height="13" fill="none" stroke="#dfe8ff" stroke-width="1" '
             'stroke-dasharray="1 1"/>' % (f(bx + 0.5), f(y + 43.5), bw - 1))
    arrow = '<g filter="url(#%spsh)">%s</g>' % (p, pointer(x + 51, y + 26, scale=0.95))
    return defs, pic + box + text(cx, base, label, LABEL_SIZE, "#ffffff", family=DEJAVU, weight=400) + arrow


# ---------------------------------------------------------------------------
# Screens
# ---------------------------------------------------------------------------
DESK_ORIGIN = (0, 40)          # medialibrarybkg on screen: desktop, then the taskbar strip
DESK_SIZE = (480, 232)
TASKBAR_Y = 252                # bottom toolbar on screen
TASK_BUTTON = (70, 250)        # x range of the Media Library task button
TRAY_X = 290
GRID = [(4 + (i // 3) * 82, 44 + (i % 3) * 68) for i in range(9)]  # screen positions, column by column
BIN_POS = (394, 180)


def wallpaper(w=480, h=272):
    defs = (lin("sky", [(0, "#1a57c8"), (0.3, "#3a7fe4"), (0.6, "#88bdf2"), (0.8, "#c8e2fb")])
            + rad("hillA", [(0, "#b0e260"), (0.28, "#82c63c"), (0.62, "#53a126"), (1, "#2c6b13")], cx=165, cy=172, r=330, user=True)
            + rad("hillB", [(0, "#86c24c"), (0.5, "#56962e"), (1, "#30631a")], cx=390, cy=168, r=210, user=True)
            + '<filter id="cl" x="-30%" y="-80%" width="160%" height="260%"><feGaussianBlur stdDeviation="2.6"/></filter>'
            + '<filter id="cls" x="-30%" y="-80%" width="160%" height="260%"><feGaussianBlur stdDeviation="4"/></filter>'
            + '<filter id="rim" x="-10%" y="-50%" width="120%" height="200%"><feGaussianBlur stdDeviation="2.2"/></filter>'
            + '<filter id="grain" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" '
              'baseFrequency="0.85 0.32" numOctaves="2" seed="7"/>'
              '<feColorMatrix values="0 0 0 0 0.12  0 0 0 0 0.3  0 0 0 0 0.04  1.6 0 0 0 -0.75"/></filter>'
            + '<clipPath id="hills"><path d="M0 188 C70 165 170 150 260 168 C330 182 400 215 480 232 V272 H0 Z"/>'
              '<path d="M150 210 C230 172 330 150 480 158 V272 H150 Z"/></clipPath>')

    def cloud(cx, cy, s, puffs):
        out = ""
        for dx, dy, r in puffs:
            out += '<ellipse cx="%s" cy="%s" rx="%s" ry="%s"/>' % (f(cx + dx * s), f(cy + dy * s), f(r * s * 1.25), f(r * s))
        return out

    puffs_a = [(-22, 4, 9), (-10, -2, 12), (6, -5, 13), (20, 1, 10), (32, 5, 7), (-30, 7, 6), (0, 6, 11)]
    puffs_b = [(-14, 3, 8), (-2, -3, 10), (12, 0, 9), (24, 4, 6), (-24, 6, 5)]
    clouds = [(78, 64, 1.0, puffs_a), (205, 38, 0.8, puffs_b), (335, 82, 1.1, puffs_b), (430, 40, 0.9, puffs_a),
              (255, 120, 0.6, puffs_b), (40, 128, 0.55, puffs_b)]
    shade = "".join('<ellipse cx="%s" cy="%s" rx="%s" ry="%s"/>' % (f(cx + 2 * s), f(cy + 9 * s), f(30 * s), f(6 * s))
                    for cx, cy, s, _ in clouds)
    body = ('<rect width="%d" height="%d" fill="url(#sky)"/>' % (w, h)
            + '<g fill="#ffffff" opacity="0.9" filter="url(#cl)">%s</g>' % "".join(cloud(*c) for c in clouds)
            + '<g fill="#9fbfe6" opacity="0.45" filter="url(#cls)">%s</g>' % shade
            + '<path d="M150 210 C230 172 330 150 480 158 V272 H150 Z" fill="url(#hillB)"/>'
            + '<path d="M150 210 C230 172 330 150 480 158" fill="none" stroke="#d8f5a0" stroke-width="3" opacity="0.35" filter="url(#rim)"/>'
            + '<path d="M0 188 C70 165 170 150 260 168 C330 182 400 215 480 232 V272 H0 Z" fill="url(#hillA)"/>'
            + '<path d="M0 188 C70 165 170 150 260 168 C330 182 400 215 480 232" fill="none" stroke="#efffc0" '
              'stroke-width="3.5" opacity="0.4" filter="url(#rim)"/>'
            + '<g clip-path="url(#hills)"><rect width="%d" height="%d" filter="url(#grain)" opacity="0.35"/></g>' % (w, h))
    return doc(w, h, body, defs)


def mini_disc(x, y, p="m"):
    """16 px app icon: a CD with a blue note."""
    ddefs, dbody = disc(p, 20, 20, 17)
    nd = note_glyph(x + 7, y + 5, 11, "#2a6ff0", "#0b2e7a")
    return ddefs, '<g transform="translate(%s %s) scale(0.4)">%s</g>%s' % (f(x), f(y), dbody, nd)


def title_bar(w=480, h=21):
    ddefs, icon = mini_disc(5, 2.5)
    defs = (lin("tb", [(0, "#5aa8ff"), (0.08, "#3b8cfd"), (0.22, "#1d6ff0"), (0.5, "#0a5ae3"), (0.85, "#0652d6"), (1, "#0343b8")])
            + ddefs + shadow_filter("ish", 0.8, 0.8, 0.5, 0.45))
    body = ('<path d="M0 %d V6 Q0 0 6 0 H%d Q%d 0 %d 6 V%d Z" fill="url(#tb)"/>' % (h, w - 6, w, w, h)
            + '<path d="M5 0.6 H%d" stroke="#a6d4ff" stroke-width="1" opacity="0.8"/>' % (w - 5)
            + '<rect y="%d" width="%d" height="1" fill="#022c86"/>' % (h - 1, w)
            + '<g filter="url(#ish)">%s</g>' % icon)
    return doc(w, h, body, defs)


def taskbar(w=480, h=20):
    defs = (lin("tk", [(0, "#2f6fe0"), (0.06, "#5d9cfb"), (0.14, "#3a7df2"), (0.55, "#245ed8"), (0.9, "#1f52c4"), (1, "#1a46ae")])
            + lin("st", [(0, "#86d886"), (0.12, "#5fc05f"), (0.45, "#3d9d3d"), (0.85, "#318a31"), (1, "#2a782a")])
            + lin("tr", [(0, "#1a8fe8"), (0.08, "#45b8fc"), (0.18, "#1f9cf0"), (0.6, "#118ae5"), (1, "#0b72d0")])
            + shadow_filter("tsh", 1, 1, 0.45, 0.85, "#0b3a0b") + shadow_filter("nsh", 0.8, 0.8, 0.5, 0.6, "#0b3a0b"))
    start = ('<path d="M0 0 H60 Q71 0 71 10 Q71 20 60 20 H0 Z" fill="url(#st)"/>'
             '<path d="M0 0.7 H60 Q69.5 0.7 70.2 8" fill="none" stroke="#c6f5c6" stroke-width="1" opacity="0.7"/>'
             '<path d="M70.4 12 Q69.4 19.3 60 19.3 H0" fill="none" stroke="#1b5a1b" stroke-width="1" opacity="0.8"/>'
             + '<g filter="url(#nsh)">%s</g>' % note_glyph(5, 2, 16, "#ffffff")
             + text(23.5, 15, "start", 14.5, "#ffffff", family=DEJAVU, weight=700, style="italic", anchor="start").replace(
                 "<text ", '<text filter="url(#tsh)" '))
    tray = ('<rect x="%d" y="0" width="%d" height="%d" fill="url(#tr)"/>' % (TRAY_X, w - TRAY_X, h)
            + '<rect x="%d" y="0" width="1" height="%d" fill="#0c4aa6"/>' % (TRAY_X, h)
            + '<rect x="%d" y="1" width="1" height="%d" fill="#5cc4ff" opacity="0.8"/>' % (TRAY_X + 1, h - 1))
    body = '<rect width="%d" height="%d" fill="url(#tk)"/>' % (w, h) + tray + start
    return doc(w, h, body, defs)


def desktop():
    """medialibrarybkg: transparent desktop with the Recycle Bin, and the task button on the taskbar strip."""
    w, h = DESK_SIZE
    ox, oy = DESK_ORIGIN
    bdefs, bbody = desk_icon("Recycle Bin", icon_bin, False, BIN_POS[0] - ox, BIN_POS[1] - oy, p="b")
    fdefs, fbody = folder("t")
    x0, x1 = TASK_BUTTON
    ty = TASKBAR_Y - oy
    defs = (bdefs + fdefs + lin("tbn", [(0, "#1a45a8"), (0.5, "#1e50bb"), (1, "#2459c8")])
            + shadow_filter("tish", 0.6, 0.6, 0.4, 0.5))
    button = ('<rect x="%s" y="%s" width="%d" height="16" rx="2.5" fill="url(#tbn)"/>' % (f(x0 + 0.5), f(ty + 2.5), x1 - x0 - 1)
              + '<path d="M%s %s V%s Q%s %s %s %s H%s" fill="none" stroke="#0d2a70" stroke-width="1"/>' % (
                  f(x0 + 0.5), f(ty + 17.5), f(ty + 5), f(x0 + 0.5), f(ty + 2.5), f(x0 + 3), f(ty + 2.5), f(x1 - 3))
              + '<path d="M%s %s V%s Q%s %s %s %s H%s" fill="none" stroke="#5d93f0" stroke-width="1" opacity="0.8"/>' % (
                  f(x1 - 0.5), f(ty + 3), f(ty + 16), f(x1 - 0.5), f(ty + 18.5), f(x1 - 3), f(ty + 18.5), f(x0 + 3))
              + '<g filter="url(#tish)"><g transform="translate(%s %s) scale(0.4)">%s</g></g>' % (f(x0 + 6), f(ty + 2), fbody))
    return doc(w, h, bbody + button, defs)


def caption_pos():
    return (TASK_BUTTON[0] + 26, TASKBAR_Y + 2)


class LunaDesktop(Luna):
    """Luna with an XP desktop Media Library, an XP title bar and an XP taskbar."""
    desc = "Windows XP style: Media Library desktop, blue bars, green start button, white text"
    sizes = {"medialibrarybkg": DESK_SIZE}

    @property
    def layout(self):
        lay = {
            "POS_APP_NAME_TEXT": "24,2",
            # taskbar: start button | free memory (hidden behind the task button on the desktop) | tray
            "POS_FREE_MEMORY_LABEL": "78,254", "POS_FREE_MEMORY_TEXT": "144,254",
            "POS_VOLUME_ICON": "298,254", "POS_VOLUME_TEXT": "317,254",
            "POS_CLOCK_TEXT": "362,254",
            "MEDIALIBRARY_MAP": "1",
            "POS_MEDIALIBRARY": "%d,%d" % DESK_ORIGIN,
            "POS_MEDIALIBRARY_MAP_CAPTION": "%d,%d" % caption_pos(),
        }
        for i, (x, y) in enumerate(GRID):
            lay["POS_MEDIALIBRARY_MAP_ITEM_%d" % (i + 1)] = "%d,%d" % (x, y)
        return lay

    def svg_jobs(self):
        jobs = {"bkg_default": (wallpaper(), 480, 272),
                "toptoolbar": (title_bar(), 480, 21),
                "bottomtoolbar": (taskbar(), 480, 20),
                "medialibrarybkg": (desktop(),) + DESK_SIZE}
        for i, (label, fn) in enumerate(ITEMS, 1):
            for sel in (False, True):
                defs, body = desk_icon(label, fn, sel)
                jobs[("mlitemsel%d" if sel else "mlitem%d") % i] = (doc(CELL_W, CELL_H, body, defs), CELL_W, CELL_H)
        return jobs

    def images(self, sizes):
        imgs = super().images(sizes)
        svg = render(self.name, self.svg_jobs(), fonts=XP_FONTS)
        self._extras = {k: svg.pop(k) for k in list(svg) if k.startswith("mlitem")}
        imgs.update(svg)
        return imgs

    def extra_images(self):
        return self._extras


THEMES = {"luna": LunaDesktop}
