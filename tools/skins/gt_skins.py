#!/usr/bin/env python3
"""Pit Lane 3 (Gran Turismo 3 style) and Pit Lane 2 (Gran Turismo 2 style).

Their artwork is written as SVG and rendered to PNG with headless Chromium
(svgrender.js, needs Node.js with Playwright), so shapes and lettering are
vector-accurate. Every rendered SVG is also saved under tools/skins/svg/<skin>/.
Text drawn by the app uses a bitmap font made from the same typeface
(oftfont.py): anti-aliased, with a dark outline like GT's own lettering.

Typefaces (SIL Open Font License, in tools/skins/fonts/):
  Barlow Condensed (GT3)  https://github.com/jpt/barlow
  Roboto Condensed (GT2)  https://github.com/googlefonts/roboto-classic
"""
import json
import math
import os
import shutil
import subprocess
import tempfile
from xml.sax.saxutils import escape

import numpy as np
from PIL import Image, ImageFont

from make_skins import Theme, PANEL_NAMES, rgba, icon_folder, icon_note, icon_star, icon_battery, icon_speaker, icon_headphone
from oftfont import make_oft

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "fonts")
SVG_DIR = os.path.join(HERE, "svg")

BARLOW = "Barlow Condensed"
ROBOTO = "Roboto Condensed"
FONT_FILES = [  # family, CSS weight, style, file
    (BARLOW, "600", "normal", "BarlowCondensed-SemiBold.ttf"),
    (BARLOW, "700", "normal", "BarlowCondensed-Bold.ttf"),
    (BARLOW, "700", "italic", "BarlowCondensed-BoldItalic.ttf"),
    (BARLOW, "800", "normal", "BarlowCondensed-ExtraBold.ttf"),
    (BARLOW, "800", "italic", "BarlowCondensed-ExtraBoldItalic.ttf"),
    (BARLOW, "900", "italic", "BarlowCondensed-BlackItalic.ttf"),
    (ROBOTO, "100 900", "normal", "RobotoCondensed-VF.ttf"),
]


def font_file(family, weight, style="normal"):
    for fam, w, st, f in FONT_FILES:
        if fam == family and st == style and (w == str(weight) or " " in w):
            return os.path.join(FONT_DIR, f)
    raise KeyError((family, weight, style))


def text_width(s, size, family=BARLOW, weight=800, style="normal"):
    """Advance width of s as the renderer will set it (FreeType metrics)."""
    f = ImageFont.truetype(font_file(family, weight, style), size)
    if family == ROBOTO:
        f.set_variation_by_axes([weight])
    return f.getlength(s)


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------
def doc(w, h, body, defs=""):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (w, h, w, h)
            + ("<defs>%s</defs>" % defs if defs else "") + body + "</svg>")


def f(v):
    return ("%.2f" % v).rstrip("0").rstrip(".")


def pts(points):
    return " ".join("%s,%s" % (f(x), f(y)) for x, y in points)


def text(x, y, s, size, fill, family=BARLOW, weight=800, style="normal", anchor="middle",
         stroke=None, sw=0, opacity=None, spacing=None):
    attrs = ['x="%s" y="%s"' % (f(x), f(y)), 'font-family="%s"' % family, 'font-weight="%s"' % weight,
             'font-style="%s"' % style, 'font-size="%s"' % f(size), 'text-anchor="%s"' % anchor, 'fill="%s"' % fill]
    if stroke:
        attrs.append('stroke="%s" stroke-width="%s" paint-order="stroke" stroke-linejoin="round"' % (stroke, f(sw)))
    if opacity is not None:
        attrs.append('opacity="%s"' % f(opacity))
    if spacing is not None:
        attrs.append('letter-spacing="%s"' % f(spacing))
    return "<text %s>%s</text>" % (" ".join(attrs), escape(s))


def smooth(points, closed=False):
    """Catmull-Rom spline through points, as an SVG path."""
    p = list(points)
    if len(p) < 3:
        return "M" + " L".join("%s %s" % (f(x), f(y)) for x, y in p)
    if closed:
        p = [p[-1]] + p + [p[0], p[1]]
    else:
        p = [p[0]] + p + [p[-1]]
    d = "M%s %s" % (f(p[1][0]), f(p[1][1]))
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += " C%s %s %s %s %s %s" % (f(c1[0]), f(c1[1]), f(c2[0]), f(c2[1]), f(p2[0]), f(p2[1]))
    return d + (" Z" if closed else "")


def glow_filter(fid, color, spread=1.4, blur=2.0, strength=2):
    merge = "".join('<feMergeNode in="g"/>' for _ in range(strength))
    return ('<filter id="%s" x="-40%%" y="-40%%" width="180%%" height="180%%">'
            '<feMorphology in="SourceAlpha" operator="dilate" radius="%s" result="d"/>'
            '<feGaussianBlur in="d" stdDeviation="%s" result="b"/>'
            '<feFlood flood-color="%s"/><feComposite in2="b" operator="in" result="g"/>'
            '<feMerge>%s<feMergeNode in="SourceGraphic"/></feMerge></filter>') % (fid, f(spread), f(blur), color, merge)


def pointer(x, y, fill="#ffffff", stroke="#000000", scale=1.0):
    """Mouse-style pointer arrow with its tip at (x, y)."""
    shape = [(0, 0), (0, 13), (3.4, 10), (6, 15.5), (8.4, 14.4), (5.9, 9.2), (10.4, 9.2)]
    return '<polygon points="%s" fill="%s" stroke="%s" stroke-width="1.2" stroke-linejoin="round"/>' % (
        pts([(x + px * scale, y + py * scale) for px, py in shape]), fill, stroke)


def render(skin, jobs, fonts=None):
    """jobs: {name: (svg, w, h)} -> {name: RGBA image}. The SVGs are kept in svg/<skin>/.
    fonts: (family, weight, style, file) faces the SVGs may use (default FONT_FILES)."""
    out_svg = os.path.join(SVG_DIR, skin)
    if os.path.isdir(out_svg):
        shutil.rmtree(out_svg)
    os.makedirs(out_svg)
    tmp = tempfile.mkdtemp(prefix="skinsvg")
    try:
        manifest = {"fonts": [{"family": fam, "weight": w, "style": st, "path": os.path.join(FONT_DIR, fn)}
                              for fam, w, st, fn in (fonts or FONT_FILES)], "jobs": []}
        for name, (svg, w, h) in jobs.items():
            path = os.path.join(out_svg, name + ".svg")
            with open(path, "w") as fh:
                fh.write(svg)
            manifest["jobs"].append({"svg": path, "png": os.path.join(tmp, name + ".png"), "width": w, "height": h})
        mpath = os.path.join(tmp, "manifest.json")
        with open(mpath, "w") as fh:
            json.dump(manifest, fh)
        subprocess.run(["node", os.path.join(HERE, "svgrender.js"), mpath], check=True)
        return {name: Image.open(os.path.join(tmp, name + ".png")).convert("RGBA").copy() for name in jobs}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Map generators
# ---------------------------------------------------------------------------
class Smooth2D:
    """Low-frequency displacement field (sum of sines)."""

    def __init__(self, rng, amp, waves=4, scale=0.02):
        self.terms = [(rng.uniform(-1, 1) * scale, rng.uniform(-1, 1) * scale, rng.uniform(0, 2 * math.pi),
                       amp * rng.uniform(0.4, 1.0) / waves) for _ in range(waves)]

    def __call__(self, x, y):
        return sum(a * math.sin(fx * x + fy * y + ph) for fx, fy, ph, a in self.terms)


def clip_half(poly, a, b, c):
    """Keep the part of poly with a*x + b*y <= c (Sutherland-Hodgman)."""
    out = []
    for i in range(len(poly)):
        p, q = poly[i], poly[(i + 1) % len(poly)]
        dp, dq = a * p[0] + b * p[1] - c, a * q[0] + b * q[1] - c
        if dp <= 0:
            out.append(p)
        if (dp < 0 < dq) or (dq < 0 < dp):
            t = dp / (dp - dq)
            out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return out


def voronoi(seeds, w, h, margin=40):
    rect = [(-margin, -margin), (w + margin, -margin), (w + margin, h + margin), (-margin, h + margin)]
    cells = []
    for i, (sx, sy) in enumerate(seeds):
        poly = rect
        for j, (tx, ty) in enumerate(seeds):
            if i != j:
                a, b = tx - sx, ty - sy
                c = a * (sx + tx) / 2 + b * (sy + ty) / 2
                poly = clip_half(poly, a, b, c)
        cells.append(poly)
    return cells


def water_shapes(rng, w, h, bay=True, river=True):
    """Bay in the lower right and a river winding into it (polygons / centre line)."""
    shapes = {}
    if bay:
        coast = []
        for i in range(9):
            t = i / 8
            x = w * (0.52 + 0.48 * t) + rng.uniform(-6, 6)
            y = h * (1.05 - 0.55 * t * (1.1 - 0.3 * t)) + rng.uniform(-5, 5)
            coast.append((x, y))
        shapes["bay"] = coast + [(w + 30, h * 0.3), (w + 30, h + 30), (w * 0.5, h + 30)]
    if river:
        n = 7
        line = [(-20 + (w * 0.62 + 20) * i / (n - 1), h * (0.40 + 0.08 * math.sin(i * 1.3 + rng.uniform(0, 1))) + rng.uniform(-6, 6))
                for i in range(n)]
        line[-1] = (w * 0.66, h * 0.70)
        shapes["river"] = line
    return shapes


def gt3_map(w, h, seed=7):
    """GT3 'GT Mode' city map: brown organic roads on black, muted blue water."""
    rng = np.random.default_rng(seed)
    dx, dy = Smooth2D(rng, 9), Smooth2D(rng, 9)
    body = ['<rect width="%d" height="%d" fill="#0a0908"/>' % (w, h)]
    minor = []
    for horizontal in (True, False):
        step = 12 if horizontal else 15
        lim = h if horizontal else w
        for k in range(-1, lim // step + 2):
            seg = []
            for t in range(-20, (w if horizontal else h) + 21, 9):
                x, y = (t, k * step) if horizontal else (k * step, t)
                p = (x + dx(x, y), y + dy(x, y))
                if rng.random() < 0.11 and len(seg) > 2:
                    minor.append(smooth(seg))
                    seg = []
                elif rng.random() < 0.06:
                    seg = []
                else:
                    seg.append(p)
            if len(seg) > 2:
                minor.append(smooth(seg))
    body.append('<path d="%s" fill="none" stroke="#45331f" stroke-width="0.9"/>' % " ".join(minor[::2]))
    body.append('<path d="%s" fill="none" stroke="#5a4229" stroke-width="1.1"/>' % " ".join(minor[1::2]))
    majors = []
    for _ in range(6):
        a = rng.uniform(0, 2 * math.pi)
        cx, cy = rng.uniform(w * 0.2, w * 0.8), rng.uniform(h * 0.2, h * 0.8)
        r = max(w, h) * 0.75
        line = []
        for t in np.linspace(-1, 1, 6):
            x, y = cx + math.cos(a) * r * t, cy + math.sin(a) * r * t
            line.append((x + dx(x, y) * 2.2, y + dy(x, y) * 2.2))
        majors.append(smooth(line))
    d = " ".join(majors)
    body.append('<path d="%s" fill="none" stroke="#6e5236" stroke-width="3.4" stroke-linecap="round"/>' % d)
    body.append('<path d="%s" fill="none" stroke="#17110b" stroke-width="1.1"/>' % d)
    for _ in range(3):  # district frames, as on the GT3 map
        cx, cy = rng.uniform(w * 0.25, w * 0.85), rng.uniform(h * 0.2, h * 0.7)
        bw, bh, ang = rng.uniform(70, 140), rng.uniform(40, 80), rng.uniform(-0.35, 0.35)
        corners = [(-bw / 2, -bh / 2), (bw / 2, -bh / 2), (bw / 2, bh / 2), (-bw / 2, bh / 2)]
        body.append('<polygon points="%s" fill="none" stroke="#6e5236" stroke-width="1"/>' % pts(
            [(cx + x * math.cos(ang) - y * math.sin(ang), cy + x * math.sin(ang) + y * math.cos(ang)) for x, y in corners]))
    water = water_shapes(rng, w, h)
    body.append('<path d="%s" fill="#2e4177" stroke="#495e9c" stroke-width="1"/>' % smooth(water["bay"], closed=True))
    body.append('<path d="%s" fill="none" stroke="#495e9c" stroke-width="10" stroke-linecap="round"/>' % smooth(water["river"]))
    body.append('<path d="%s" fill="none" stroke="#2e4177" stroke-width="8" stroke-linecap="round"/>' % smooth(water["river"]))
    # bridges: the first two major roads cross the water on top
    body.append('<path d="%s" fill="none" stroke="#6e5236" stroke-width="3.4"/>' % " ".join(majors[:2]))
    body.append('<path d="%s" fill="none" stroke="#17110b" stroke-width="1.1"/>' % " ".join(majors[:2]))
    return "".join(body)


def gt2_city(w, h, seed=11, strength=1.0):
    """GT2 city map: districts of amber street grids, avenues, highways, slate water, parks."""
    rng = np.random.default_rng(seed)
    cols, rows = 4, 2
    seeds = [((i + 0.5 + rng.uniform(-0.3, 0.3)) * w / cols, (j + 0.5 + rng.uniform(-0.3, 0.3)) * h / rows)
             for j in range(rows) for i in range(cols)]
    cells = voronoi(seeds, w, h)
    defs, body = [], ['<rect width="%d" height="%d" fill="#000000"/>' % (w, h)]
    street = '<g clip-path="url(#c%d)" stroke="#c97f18" stroke-width="1" opacity="%s">%s</g>'
    for k, (cell, (sx, sy)) in enumerate(zip(cells, seeds)):
        defs.append('<clipPath id="c%d"><polygon points="%s"/></clipPath>' % (k, pts(cell)))
        ang = math.radians(rng.choice([rng.uniform(-18, 18), rng.uniform(25, 40), rng.uniform(-40, -25)]))
        s1, s2 = rng.uniform(7.5, 10.5), rng.uniform(8.5, 13)
        lines = []
        R = max(w, h)
        for (ux, uy), step in (((math.cos(ang), math.sin(ang)), s1), ((-math.sin(ang), math.cos(ang)), s2)):
            nx, ny = -uy, ux
            for t in np.arange(-R, R, step):
                if rng.random() < 0.07:
                    continue
                cx, cy = sx + nx * t, sy + ny * t
                lines.append("M%s %sL%s %s" % (f(cx - ux * R), f(cy - uy * R), f(cx + ux * R), f(cy + uy * R)))
        body.append(street % (k, f(0.78 * strength), "".join('<path d="%s"/>' % d for d in lines)))
        if rng.random() < 0.5:  # a park block
            pw, ph = rng.uniform(14, 26), rng.uniform(10, 18)
            px, py = sx + rng.uniform(-20, 20), sy + rng.uniform(-14, 14)
            corners = [(-pw / 2, -ph / 2), (pw / 2, -ph / 2), (pw / 2, ph / 2), (-pw / 2, ph / 2)]
            body.append('<polygon points="%s" fill="#173a1f" opacity="%s"/>' % (pts(
                [(px + x * math.cos(ang) - y * math.sin(ang), py + x * math.sin(ang) + y * math.cos(ang)) for x, y in corners]),
                f(0.95 * strength)))
    avenues = " ".join("M" + " L".join("%s %s" % (f(x), f(y)) for x, y in cell) + " Z" for cell in cells)
    body.append('<path d="%s" fill="none" stroke="#e39628" stroke-width="1.8" opacity="%s"/>' % (avenues, f(0.9 * strength)))
    water = water_shapes(rng, w, h)
    body.append('<path d="%s" fill="#465062" stroke="#6b7690" stroke-width="1"/>' % smooth(water["bay"], closed=True))
    body.append('<path d="%s" fill="none" stroke="#465062" stroke-width="9" stroke-linecap="round"/>' % smooth(water["river"]))
    highways = []
    for (x0, y0), (x1, y1) in (((-10, h * 0.18), (w + 10, h * 0.62)), ((w * 0.22, -10), (w * 0.48, h + 10))):
        mid = [(x0 + (x1 - x0) * t + rng.uniform(-18, 18), y0 + (y1 - y0) * t + rng.uniform(-14, 14)) for t in (0.33, 0.66)]
        highways.append(smooth([(x0, y0)] + mid + [(x1, y1)]))
    d = " ".join(highways)
    body.append('<path d="%s" fill="none" stroke="#000000" stroke-width="4.6"/>' % d)
    body.append('<path d="%s" fill="none" stroke="#f5a623" stroke-width="2.2" opacity="%s"/>' % (d, f(min(1, 1.05 * strength))))
    return "".join(defs), "".join(body)


# ---------------------------------------------------------------------------
# Shared pieces
# ---------------------------------------------------------------------------
SCANLINES = '<pattern id="scan" width="4" height="2" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#000" opacity="%s"/></pattern>'


def coin(s=16):
    """Orange 'Cr.' credits coin (used for the CPU readout)."""
    defs = ('<radialGradient id="cg" cx="0.38" cy="0.32" r="0.75"><stop offset="0" stop-color="#ffd08a"/>'
            '<stop offset="1" stop-color="#e2650f"/></radialGradient>')
    body = ('<circle cx="8" cy="8" r="7.3" fill="url(#cg)" stroke="#2a1205" stroke-width="1.1"/>'
            + text(8.1, 11.2, "Cr", 8.6, "#2a1205", weight=800, style="italic"))
    return doc(s, s, body, defs)


def map_layout(items, origin):
    """Theme layout entries for the map menu: item positions in screen coordinates."""
    ox, oy = origin
    return {"POS_MEDIALIBRARY_MAP_ITEM_%d" % (i + 1): "%d,%d" % (ox + x, oy + y) for i, (x, y) in enumerate(items)}


class SvgTheme(Theme):
    """Base for themes whose artwork comes from SVG."""
    oft = None          # (file name, ttf, size, weight)
    map_items = []      # canvas positions of the 9 map entries (map coordinates)

    def svg_jobs(self, sizes):
        jobs = {"bkg_default": (self.background(480, 272), 480, 272),
                "toptoolbar": (self.bar(480, 21, True), 480, 21),
                "bottomtoolbar": (self.bar(480, 20, False), 480, 20),
                "menuhighlight": (self.highlight_svg(*sizes["menuhighlight"]),) + sizes["menuhighlight"],
                "nocoverart": (self.nocover_svg(118), 118, 118),
                "cpu": (coin(), 16, 16)}
        for i in range(1, 6):
            jobs["button%d" % i] = (self.tab(96, 16, False, i), 96, 16)
            jobs["buttonsel%d" % i] = (self.tab(96, 16, True, i), 96, 16)
        for n in PANEL_NAMES:
            if n != "medialibrarybkg":
                jobs[n] = (self.panel_svg(*sizes[n]),) + sizes[n]
        jobs["medialibrarybkg"] = (self.map_svg(*sizes["medialibrarybkg"]),) + sizes["medialibrarybkg"]
        bkg, bar = self.progress_svgs()
        jobs["progressbkg"] = (bkg, 464, 10)
        jobs["progress"] = (bar, 464, 6)
        jobs.update(self.badge_svgs())
        return jobs

    def images(self, sizes):
        imgs = render(self.name, self.svg_jobs(sizes))
        self._extras = {k: imgs.pop(k) for k in list(imgs) if k.startswith("mlitem")}
        self._svg_icons = {k[5:]: imgs.pop(k) for k in list(imgs) if k.startswith("icon_")}
        imgs.update(self.icons())
        return imgs

    def extra_images(self):
        return self._extras

    def extra_files(self, out):
        name, ttf, size, weight = self.oft
        make_oft(os.path.join(out, "images", name), os.path.join(FONT_DIR, ttf), size, 16, 12, weight=weight)
        lic = self.license
        shutil.copy(os.path.join(FONT_DIR, lic), os.path.join(out, "FONT-LICENSE.txt"))


# ---------------------------------------------------------------------------
# Pit Lane 3: Gran Turismo 3 style
# ---------------------------------------------------------------------------
GT3_ORANGE = "#f39a2b"
GT3_TAN = "#dcc493"
GT3_INK = "#170e06"


def gt3_label(x, y, s, size=13, fill=GT3_TAN, anchor="middle", weight=800, style="normal"):
    return text(x, y, s, size, fill, weight=weight, style=style, anchor=anchor, stroke=GT3_INK, sw=2.6)


def gt3_badges():
    """The nine GT Mode style map badges: (svg body, width, height, pointer tip)."""
    b = []
    # 1 Shuffle All - 'GO RACE' style slanted bars
    g = ('<linearGradient id="r1" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f07a36"/>'
         '<stop offset="1" stop-color="#b8341a"/></linearGradient>')
    bars = ''.join('<polygon points="%s" fill="url(#r1)" stroke="#1a0d07" stroke-width="1.5" stroke-linejoin="round"/>' % pts(p)
                   for p in ([(40, 6), (82, 6), (74, 21), (32, 21)], [(28, 25), (70, 25), (62, 40), (20, 40)]))
    shine = ''.join('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="#ffd2a6" stroke-width="1" opacity="0.6"/>' % (a, c, bb, c)
                    for a, bb, c in ((41.5, 80, 7.5), (29.5, 68, 26.5)))
    b.append(("<defs>%s</defs>%s%s%s" % (g, bars, shine, gt3_label(50, 56, "SHUFFLE ALL", 14)), 100, 64, (82, 40)))
    # 2 Browse all - 'MY HOME' style red house and label box
    house = ('<polygon points="%s" fill="#8e1414" stroke="#f3eee6" stroke-width="1.4" stroke-linejoin="round"/>' % pts([(64, 21), (78, 13), (78, 34), (64, 42)])
             + '<polygon points="%s" fill="#cf2020" stroke="#f3eee6" stroke-width="1.4" stroke-linejoin="round"/>' % pts([(18, 21), (41, 5), (64, 21), (64, 42), (18, 42)])
             + '<polygon points="%s" fill="#e64040" stroke="#f3eee6" stroke-width="1.4" stroke-linejoin="round"/>' % pts([(41, 5), (55, -2), (78, 13), (64, 21)])
             + '<rect x="35" y="28" width="9" height="14" fill="#5a0b0b"/>')
    box = ('<rect x="30" y="39" width="66" height="17" rx="2" fill="#f2eee6" stroke="#161616" stroke-width="1.2"/>'
           + text(63, 51.6, "BROWSE ALL", 12, "#161616", weight=800))
    b.append((house + box, 100, 62, (86, 46)))
    # 3 Artists - 'LICENSE CENTER' style emblem + panel
    emb = ('<rect x="4" y="5" width="36" height="36" rx="3" fill="#27498a" stroke="#0e0e0e" stroke-width="1.5"/>'
           '<circle cx="22" cy="23" r="12.5" fill="#ece5ca" stroke="#183466" stroke-width="1"/>'
           '<circle cx="22" cy="19.5" r="4.4" fill="#27498a"/>'
           '<path d="M13 31.5 Q13 24.8 22 24.8 Q31 24.8 31 31.5 Z" fill="#27498a"/>')
    panel = ('<rect x="40" y="9" width="86" height="29" rx="2" fill="#dccfa6" stroke="#2a2214" stroke-width="1.5"/>'
             + text(83, 20, "BROWSE", 9.5, "#2a2214", weight=800, spacing=1)
             + text(83, 35, "ARTISTS", 16, "#2a2214", weight=800))
    b.append((emb + panel, 130, 48, (114, 32)))
    # 4 Albums - 'CAR DEALER' style roundel with a record
    ring = ('<path id="arc4" d="M14 39 A25 25 0 0 1 64 39" fill="none"/>'
            '<circle cx="39" cy="39" r="31" fill="#2c6a38" stroke="#0f230f" stroke-width="1.5"/>'
            '<circle cx="39" cy="39" r="23.5" fill="#e8dfc0" stroke="#0f230f" stroke-width="1"/>'
            '<text font-family="%s" font-weight="800" font-size="7.2" fill="#e8dfc0" letter-spacing="0.6">'
            '<textPath href="#arc4" startOffset="50%%" text-anchor="middle">BROWSE BY ALBUM</textPath></text>' % BARLOW
            + '<circle cx="39" cy="39" r="19" fill="#141414"/>'
            + "".join('<circle cx="39" cy="39" r="%s" fill="none" stroke="#2c2c2c" stroke-width="0.8"/>' % r for r in (16, 13, 10))
            + '<circle cx="39" cy="39" r="5.5" fill="#c94a1d"/><circle cx="39" cy="39" r="1.4" fill="#0a0a0a"/>')
    b.append((ring + text(39, 44.5, "ALBUMS", 16, "#ece3c4", weight=800, stroke="#0f230f", sw=2.6), 80, 78, (60, 58)))
    # 5 Genres - 'GT auto' style square with a pill
    note = ('<ellipse cx="29" cy="37" rx="6.5" ry="5" fill="#d1b06e" transform="rotate(-20 29 37)"/>'
            '<rect x="33.4" y="11" width="3.6" height="27" fill="#d1b06e"/>'
            '<path d="M33.4 11 L48 16 L48 23 L37 19.5 Z" fill="#d1b06e"/>')
    sq = ('<rect x="8" y="4" width="54" height="50" rx="6" fill="#2a2016" stroke="#d1b06e" stroke-width="2.2"/>' + note
          + '<rect x="11" y="47" width="48" height="17" rx="8.5" fill="#d1b06e" stroke="#2a2016" stroke-width="1.5"/>'
          + text(35, 59.6, "GENRES", 12.5, "#2a2016", weight=800))
    b.append((sq, 72, 70, (52, 52)))
    # 6 Rating - 'MACHINE TEST' style gauge
    ticks = "".join('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="#e8dcc0" stroke-width="1.1"/>' % (
        f(30 + 18 * math.cos(a)), f(32 + 18 * math.sin(a)), f(30 + 22 * math.cos(a)), f(32 + 22 * math.sin(a)))
        for a in np.radians(np.linspace(135, 405, 10)))
    gauge = ('<circle cx="30" cy="32" r="25" fill="#130c0a" stroke="#b8291c" stroke-width="4"/>' + ticks
             + '<line x1="30" y1="32" x2="%s" y2="%s" stroke="#ff6a2a" stroke-width="2.4" stroke-linecap="round"/>' % (
                 f(30 + 19 * math.cos(math.radians(330))), f(32 + 19 * math.sin(math.radians(330))))
             + '<circle cx="30" cy="32" r="3" fill="#e8dcc0"/>')
    b.append((gauge + text(66, 46, "RATING", 18, "#e0482b", weight=800, style="italic", stroke=GT3_INK, sw=2.8), 98, 66, (84, 48)))
    # 7 Top 100 - trophy
    tg = ('<linearGradient id="r7" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffe9a0"/>'
          '<stop offset="1" stop-color="#c98d1c"/></linearGradient>')
    cup = ('<path d="M24 7 H56 V17 Q56 34 40 38 Q24 34 24 17 Z" fill="url(#r7)" stroke="#2a1c06" stroke-width="1.4"/>'
           '<path d="M24 11 H16 Q15 24 26 26" fill="none" stroke="#2a1c06" stroke-width="4.2"/>'
           '<path d="M56 11 H64 Q65 24 54 26" fill="none" stroke="#2a1c06" stroke-width="4.2"/>'
           '<path d="M24 11 H16 Q15 24 26 26" fill="none" stroke="#e7b84a" stroke-width="2"/>'
           '<path d="M56 11 H64 Q65 24 54 26" fill="none" stroke="#e7b84a" stroke-width="2"/>'
           '<rect x="36.5" y="37" width="7" height="9" fill="url(#r7)" stroke="#2a1c06" stroke-width="1.2"/>'
           '<rect x="27" y="45" width="26" height="7" rx="1.5" fill="url(#r7)" stroke="#2a1c06" stroke-width="1.3"/>'
           + text(40, 24, "100", 11, "#6b4708", weight=800))
    b.append(("<defs>%s</defs>%s%s" % (tg, cup, gt3_label(40, 66, "TOP 100", 14)), 80, 70, (60, 50)))
    # 8 Search - 'TUNE SHOP' style magnifier
    mag = ('<line x1="40" y1="33" x2="53" y2="46" stroke="#0f1118" stroke-width="8.5" stroke-linecap="round"/>'
           '<line x1="40" y1="33" x2="53" y2="46" stroke="#8fa6cf" stroke-width="5" stroke-linecap="round"/>'
           '<circle cx="29" cy="22" r="14" fill="#8fa6cf" fill-opacity="0.18" stroke="#0f1118" stroke-width="7.5"/>'
           '<circle cx="29" cy="22" r="14" fill="none" stroke="#8fa6cf" stroke-width="4.2"/>')
    b.append((mag + gt3_label(78, 41, "SEARCH", 19), 112, 58, (98, 42)))
    # 9 Scan - wrench
    wr = ('<g transform="translate(17 17) rotate(-40)">'
          '<path d="M-3 -13 A8 8 0 1 0 3 -13 L3 -7 L-3 -7 Z M-2.6 -4 H2.6 V13 Q2.6 16 0 16 Q-2.6 16 -2.6 13 Z" '
          'fill="#a9b6cb" stroke="#0f1118" stroke-width="1.5" stroke-linejoin="round"/></g>')
    b.append((wr + gt3_label(66, 26, "SCAN MS", 16), 110, 34, (96, 18)))
    return b


class PitLane3(SvgTheme):
    name = "Pit Lane 3"
    desc = "Gran Turismo 3 style: red scanline title screen, GT Mode map, condensed lettering"
    oft = ("gt3text.oft", "BarlowCondensed-Bold.ttf", 15, None)
    license = "OFL-Barlow.txt"
    colors = {
        "TOOLBAR_TEXT": "#ffffff", "TOOLBAR_TEXT_SHADOW": (0, 0, 0, 0),
        "BUTTONBAR_TEXT": (0, 0, 0, 0), "BUTTONBAR_TEXT_SHADOW": (0, 0, 0, 0),  # labels are in the tab images
        "BUTTONBAR_SELECTED_TEXT": (0, 0, 0, 0), "BUTTONBAR_SELECTED_TEXT_SHADOW": (0, 0, 0, 0),
        "POPUP_TITLE_TEXT": "#ffd23a", "POPUP_TITLE_TEXT_SHADOW": (0, 0, 0, 0),
        "POPUP_MESSAGE_TEXT": "#ffffff", "POPUP_MESSAGE_TEXT_SHADOW": (0, 0, 0, 0),
        "MENU_TEXT": "#ffffff", "MENU_TEXT_SHADOW": (0, 0, 0, 0),
        "MENU_SELECTED_TEXT": "#ffd23a", "MENU_SELECTED_TEXT_SHADOW": (0, 0, 0, 0),
        "LABEL_TEXT": "#f9a23a", "LABEL_TEXT_SHADOW": (0, 0, 0, 0),
        "TEXT": "#ffffff", "TEXT_SHADOW": (0, 0, 0, 0),
        "HELP_TITLE_TEXT": "#ffd23a", "HELP_TITLE_TEXT_SHADOW": (0, 0, 0, 0),
        "HELP_TEXT": "#ffffff", "HELP_TEXT_SHADOW": (0, 0, 0, 0),
    }
    map_origin = (4, 42)
    map_items = [(6, 30), (114, 34), (226, 40), (378, 22), (12, 102), (104, 106), (218, 104), (324, 108), (8, 174)]
    caption = (204, 186)
    sizes = {"menuhighlight": (480, 16), "medialibrarybkg": (472, 208)}

    @property
    def layout(self):
        lay = {"MENU_INTERLINE": "1", "MEDIALIBRARY_MAP": "1", "POS_MEDIALIBRARY": "%d,%d" % self.map_origin,
               "POS_MEDIALIBRARY_MAP_CAPTION": "%d,%d" % (self.map_origin[0] + self.caption[0], self.map_origin[1] + self.caption[1])}
        lay.update(map_layout(self.map_items, self.map_origin))
        return lay

    def cfg(self):
        c = super().cfg()
        c["STR_FONT_NORMAL_NAME"] = "$skinimage/" + self.oft[0]
        return c

    def background(self, w, h):
        rng = np.random.default_rng(5)
        defs = (SCANLINES % "0.2"
                + '<radialGradient id="base" cx="0.6" cy="0.46" r="0.8"><stop offset="0" stop-color="#e2432f"/>'
                '<stop offset="0.55" stop-color="#cc2a28"/><stop offset="1" stop-color="#931419"/></radialGradient>'
                '<radialGradient id="vig" cx="0.5" cy="0.5" r="0.72"><stop offset="0.65" stop-color="#2a0004" stop-opacity="0"/>'
                '<stop offset="1" stop-color="#2a0004" stop-opacity="0.55"/></radialGradient>'
                '<filter id="smear" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="34 1.6"/></filter>'
                '<filter id="glowb" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="46 7"/></filter>')
        bands = []
        for _ in range(46):  # motion-blurred photo look: soft horizontal smears
            y, hh = rng.uniform(0, h), rng.choice([1.5, 2.5, 4, 7])
            x, ww = rng.uniform(-150, w), rng.uniform(90, 320)
            col, op = (("#6a0a10", rng.uniform(0.25, 0.5)) if rng.random() < 0.55 else ("#ff7f4c", rng.uniform(0.12, 0.3)))
            bands.append('<rect x="%s" y="%s" width="%s" height="%s" fill="%s" opacity="%s"/>' % (f(x), f(y), f(ww), f(hh), col, f(op)))
        glow = ('<ellipse cx="430" cy="118" rx="150" ry="16" fill="#ffb347" opacity="0.6"/>'
                '<ellipse cx="455" cy="150" rx="120" ry="9" fill="#ffd27a" opacity="0.5"/>'
                '<ellipse cx="300" cy="140" rx="90" ry="6" fill="#ff9a4a" opacity="0.35"/>')
        body = ('<rect width="%d" height="%d" fill="url(#base)"/>' % (w, h)
                + '<g filter="url(#smear)">%s</g>' % "".join(bands)
                + '<g filter="url(#glowb)">%s</g>' % glow
                + '<rect width="%d" height="%d" fill="url(#scan)"/>' % (w, h)
                + '<rect width="%d" height="%d" fill="url(#vig)"/>' % (w, h))
        return doc(w, h, body, defs)

    def bar(self, w, h, top):
        defs = SCANLINES % "0.0" + '<pattern id="lit" width="4" height="2" patternUnits="userSpaceOnUse"><rect y="1" width="4" height="1" fill="#fff" opacity="0.04"/></pattern>'
        y = h - 1 if top else 0
        body = ('<rect width="%d" height="%d" fill="#050505" opacity="0.8"/>' % (w, h)
                + '<rect width="%d" height="%d" fill="url(#lit)"/>' % (w, h)
                + '<rect y="%d" width="%d" height="1" fill="%s" opacity="0.75"/>' % (y, w, GT3_ORANGE))
        return doc(w, h, body, defs)

    def tab(self, w, h, sel, i):
        label = ["File Browser", "Playlists", "Playlist Editor", "Media Library", "Settings"][i - 1]
        size = 15
        band = ('<linearGradient id="band" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#000" stop-opacity="0.15"/>'
                '<stop offset="0.5" stop-color="#000" stop-opacity="0.42"/><stop offset="1" stop-color="#000" stop-opacity="0.15"/></linearGradient>')
        body = '<rect width="%d" height="%d" fill="url(#band)"/>' % (w, h)
        if sel:
            grad = ('<linearGradient id="gy" x1="0" y1="0" x2="0" y2="1"><stop offset="0.1" stop-color="#fff7a8"/>'
                    '<stop offset="0.55" stop-color="#ffd21f"/><stop offset="1" stop-color="#ff9200"/></linearGradient>')
            tw = text_width(label, size, weight=800, style="italic")
            l, r = w / 2 - tw / 2 - 4, w / 2 + tw / 2 + 4
            arrows = ('<polygon points="%s" fill="#ffcc00" stroke="#3a1400" stroke-width="0.9"/>' % pts([(l, h / 2 - 3.5), (l, h / 2 + 3.5), (l - 4.5, h / 2)])
                      + '<polygon points="%s" fill="#ffcc00" stroke="#3a1400" stroke-width="0.9"/>' % pts([(r, h / 2 - 3.5), (r, h / 2 + 3.5), (r + 4.5, h / 2)]))
            body += arrows + text(w / 2, 12.6, label, size, "url(#gy)", weight=800, style="italic", stroke="#3a1400", sw=2.6)
            return doc(w, h, body, band + grad)
        body += text(w / 2, 12.6, label, size, "#f4ece6", weight=800, style="italic", stroke="#2a0606", sw=2.4, opacity=0.72)
        return doc(w, h, body, band)

    def panel_svg(self, w, h):
        defs = '<pattern id="lit" width="4" height="2" patternUnits="userSpaceOnUse"><rect y="1" width="4" height="1" fill="#fff" opacity="0.03"/></pattern>'
        body = ('<rect width="%d" height="%d" rx="2" fill="#060606" opacity="0.82"/>' % (w, h)
                + '<rect width="%d" height="%d" rx="2" fill="url(#lit)"/>' % (w, h)
                + '<rect x="2" width="%d" height="1.2" fill="%s" opacity="0.9"/>' % (w - 4, GT3_ORANGE))
        return doc(w, h, body, defs)

    def highlight_svg(self, w, h):
        defs = ('<linearGradient id="hl" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#ff9a1f" stop-opacity="0.62"/>'
                '<stop offset="0.6" stop-color="#ff7a00" stop-opacity="0.34"/><stop offset="1" stop-color="#ff7a00" stop-opacity="0.14"/></linearGradient>')
        body = ('<rect width="%d" height="%d" fill="url(#hl)"/>' % (w, h)
                + '<rect width="%d" height="1" fill="#ffd23a" opacity="0.9"/>' % w
                + '<rect y="%d" width="%d" height="1" fill="#ffd23a" opacity="0.9"/>' % (h - 1, w))
        return doc(w, h, body, defs)

    def progress_svgs(self):
        bkg = doc(464, 10, '<rect x="0.5" y="0.5" width="463" height="9" rx="3" fill="#050505" stroke="#8a6a45" stroke-width="1"/>')
        bar = doc(464, 6, '<defs><linearGradient id="p" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffe27a"/>'
                          '<stop offset="0.5" stop-color="#f7941d"/><stop offset="1" stop-color="#c9440e"/></linearGradient></defs>'
                          '<rect x="2" width="460" height="6" rx="2" fill="url(#p)"/>')
        return bkg, bar

    def nocover_svg(self, s):
        defs = ('<radialGradient id="sky" cx="0.5" cy="-0.05" r="0.95"><stop offset="0" stop-color="#4a66a8"/>'
                '<stop offset="0.5" stop-color="#16244c"/><stop offset="1" stop-color="#05070f"/></radialGradient>'
                '<linearGradient id="floor" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8f98ab"/>'
                '<stop offset="1" stop-color="#eef1f6"/></linearGradient>'
                '<radialGradient id="btn" cx="0.42" cy="0.35" r="0.7"><stop offset="0" stop-color="#ffb15c"/>'
                '<stop offset="0.6" stop-color="#f47a22"/><stop offset="1" stop-color="#c9440e"/></radialGradient>'
                '<clipPath id="cl"><rect width="%d" height="%d" rx="4"/></clipPath>' % (s, s))
        body = ('<g clip-path="url(#cl)"><rect width="%d" height="%d" fill="url(#sky)"/>' % (s, s)
                + '<rect y="%s" width="%d" height="%s" fill="url(#floor)"/>' % (f(s * 0.64), s, f(s * 0.36))
                + '<ellipse cx="%s" cy="%s" rx="%s" ry="%s" fill="#000" opacity="0.25"/>' % (f(s / 2), f(s * 0.8), f(s * 0.26), f(s * 0.05))
                + '<circle cx="%s" cy="%s" r="%s" fill="url(#btn)" stroke="#2a1205" stroke-width="2"/>' % (f(s / 2), f(s * 0.5), f(s * 0.21))
                + text(s / 2, s * 0.5 + 5.5, "PLAY", 15, "#2a1205", weight=800)
                + '</g><rect x="0.5" y="0.5" width="%d" height="%d" rx="4" fill="none" stroke="#8a6a45"/>' % (s - 1, s - 1))
        return doc(s, s, body, defs)

    def map_svg(self, w, h):
        heading = (text(8, 25, "MEDIA", 25, GT3_ORANGE, weight=900, style="italic", anchor="start", stroke="#000", sw=2.4)
                   + text(8 + text_width("MEDIA ", 25, weight=900, style="italic"), 25, "LIBRARY", 25, "#000",
                          weight=900, style="italic", anchor="start", stroke=GT3_ORANGE, sw=1.3))
        cx, cy = self.caption
        strip = ('<rect x="%d" y="%d" width="%d" height="22" fill="#2a2a2a" opacity="0.82"/>' % (cx - 8, cy - 2, w - cx + 4)
                 + '<rect x="%d" y="%d" width="3" height="22" fill="%s"/>' % (cx - 8, cy - 2, GT3_ORANGE))
        body = ('<rect width="%d" height="%d" rx="3" fill="#000"/>' % (w, h)
                + '<g clip-path="url(#mc)">%s</g>' % gt3_map(w, h)
                + heading + strip
                + '<rect x="0.5" y="0.5" width="%d" height="%d" rx="3" fill="none" stroke="#6e5236"/>' % (w - 1, h - 1))
        return doc(w, h, body, '<clipPath id="mc"><rect width="%d" height="%d" rx="3"/></clipPath>' % (w, h))

    def badge_svgs(self):
        jobs = {}
        for i, (body, w, h, tip) in enumerate(gt3_badges(), 1):
            jobs["mlitem%d" % i] = (doc(w, h, body), w, h)
            sel = ('<g filter="url(#hot)">%s</g>' % body) + pointer(*tip)
            jobs["mlitemsel%d" % i] = (doc(w, h, sel, glow_filter("hot", "#ffe27a", 1.2, 2.2, 2)), w, h)
        return jobs

    def icons(self):
        return {
            "folder": icon_folder(19, 16, "#a8936a", "#e3d6b0", rgba("#3a2e1c", 255), gloss_a=110),
            "music": icon_note(16, 16, "#ffb347", outline="#140a02"),
            "star": icon_star(16, "#fff07a", "#ff8c00", rgba("#3a1a00", 255)),
            "blankstar": icon_star(16, "#3a3530", "#1a1714", rgba("#a8936a", 220), gloss_a=30),
            "battery": icon_battery(30, 14, "#e3d6b0", ("#ffe27a", "#f7941d"), rgba("#140a02", 255)),
            "batterycharging": icon_battery(30, 14, "#e3d6b0", ("#b8f07a", "#4aa615"), rgba("#140a02", 255)),
            "batterylow": icon_battery(30, 14, "#e3d6b0", ("#ff9a8a", "#d0301a"), rgba("#140a02", 255), frac=0.2),
            "volume": icon_speaker(16, "#ffffff", GT3_ORANGE),
            "headphone": icon_headphone(16, "#ffffff"),
        }


# ---------------------------------------------------------------------------
# Pit Lane 2: Gran Turismo 2 style
# ---------------------------------------------------------------------------
GT2_ORANGE = "#f5a01a"
SIGN_GRAD = ('<linearGradient id="sg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffb43c"/>'
             '<stop offset="1" stop-color="#e8800a"/></linearGradient>')

PICTOGRAMS = {  # black pictograms in a 22x22 sign
    "person": '<circle cx="11" cy="7.6" r="3.4"/><path d="M4.6 18.4 Q4.6 11.6 11 11.6 Q17.4 11.6 17.4 18.4 Z"/>',
    "disc": '<circle cx="11" cy="11" r="7.4"/><circle cx="11" cy="11" r="2.4" fill="url(#sg)"/>'
            '<circle cx="11" cy="11" r="5" fill="none" stroke="url(#sg)" stroke-width="0.7"/>',
    "skyline": '<path d="M3.5 18.5 V10 H6.5 V7 H9 V12 H11 V4.5 H14 V9.5 H16 V6.5 H18.5 V18.5 Z"/>',
    "star": '<polygon points="11,3.6 13.2,8.6 18.6,9 14.4,12.4 15.8,17.8 11,14.8 6.2,17.8 7.6,12.4 3.4,9 8.8,8.6"/>',
    "trophy": '<path d="M6.5 4 H15.5 V8.5 Q15.5 13 11 14 Q6.5 13 6.5 8.5 Z"/><rect x="9.8" y="13.6" width="2.4" height="2.6"/>'
              '<rect x="7.4" y="16" width="7.2" height="2.6"/><path d="M6.5 5.2 H4.2 Q4 9 7 10" fill="none" stroke="#000" stroke-width="1.4"/>'
              '<path d="M15.5 5.2 H17.8 Q18 9 15 10" fill="none" stroke="#000" stroke-width="1.4"/>',
    "magnifier": '<circle cx="9.4" cy="9.4" r="5" fill="none" stroke="#000" stroke-width="2.4"/>'
                 '<line x1="13" y1="13" x2="18" y2="18" stroke="#000" stroke-width="3" stroke-linecap="round"/>',
    "wheel": '<circle cx="11" cy="11" r="7.2" fill="none" stroke="#000" stroke-width="2.2"/><circle cx="11" cy="11" r="2.2"/>'
             + "".join('<line x1="11" y1="11" x2="%s" y2="%s" stroke="#000" stroke-width="1.6"/>' % (
                 f(11 + 6.5 * math.cos(math.radians(a))), f(11 + 6.5 * math.sin(math.radians(a)))) for a in range(-90, 270, 72)),
    "house": '<path d="M3.6 11 L11 4.4 L18.4 11 H16.2 V18 H12.6 V13.6 H9.4 V18 H5.8 V11 Z"/>',
}


def gt2_sign(x, y, kind, color="orange", size=22):
    """GT2 road sign: rounded square with a black pictogram (or the checkered GO RACE flag)."""
    s = size / 22
    if kind == "checker":
        cells = "".join('<rect x="%s" y="%s" width="4.5" height="4.5" fill="#000"/>' % (f(2 + c * 4.5), f(2 + r * 4.5))
                        for r in range(4) for c in range(4) if (r + c) % 2 == 0)
        inner = '<rect x="1" y="1" width="20" height="20" rx="2.5" fill="#fff" stroke="#000" stroke-width="1.6"/>' + cells
    else:
        fill = "url(#sg)" if color == "orange" else "#d8301e"
        inner = ('<rect x="1" y="1" width="20" height="20" rx="3" fill="%s" stroke="#000" stroke-width="1.6"/>' % fill
                 + '<g fill="#000">%s</g>' % PICTOGRAMS[kind])
    return '<g transform="translate(%s %s) scale(%s)">%s</g>' % (f(x), f(y), f(s), inner)


def gt2_label(x, y, s, size=13.5, fill="#ffffff", anchor="start"):
    return text(x, y, s, size, fill, family=ROBOTO, weight=700, anchor=anchor, stroke="#000", sw=2.8)


class PitLane2(SvgTheme):
    name = "Pit Lane 2"
    desc = "Gran Turismo 2 style: black city map with amber streets, orange road signs"
    oft = ("gt2text.oft", "RobotoCondensed-VF.ttf", 14, 700)
    license = "OFL-RobotoCondensed.txt"
    colors = {
        "TOOLBAR_TEXT": "#ffffff", "TOOLBAR_TEXT_SHADOW": (0, 0, 0, 0),
        "BUTTONBAR_TEXT": (0, 0, 0, 0), "BUTTONBAR_TEXT_SHADOW": (0, 0, 0, 0),  # labels are in the tab images
        "BUTTONBAR_SELECTED_TEXT": (0, 0, 0, 0), "BUTTONBAR_SELECTED_TEXT_SHADOW": (0, 0, 0, 0),
        "POPUP_TITLE_TEXT": GT2_ORANGE, "POPUP_TITLE_TEXT_SHADOW": (0, 0, 0, 0),
        "POPUP_MESSAGE_TEXT": "#ffffff", "POPUP_MESSAGE_TEXT_SHADOW": (0, 0, 0, 0),
        "MENU_TEXT": "#ffffff", "MENU_TEXT_SHADOW": (0, 0, 0, 0),
        "MENU_SELECTED_TEXT": "#ffffff", "MENU_SELECTED_TEXT_SHADOW": (0, 0, 0, 0),
        "LABEL_TEXT": GT2_ORANGE, "LABEL_TEXT_SHADOW": (0, 0, 0, 0),
        "TEXT": "#ffffff", "TEXT_SHADOW": (0, 0, 0, 0),
        "HELP_TITLE_TEXT": GT2_ORANGE, "HELP_TITLE_TEXT_SHADOW": (0, 0, 0, 0),
        "HELP_TEXT": "#ffffff", "HELP_TEXT_SHADOW": (0, 0, 0, 0),
    }
    map_origin = (4, 42)
    # (sign kind, colour, label, label size); canvases are laid out in svg_jobs
    signs = [("checker", "orange", "SHUFFLE ALL", 13.5), ("house", "red", "BROWSE ALL", 15.5), ("person", "orange", "ARTISTS", 13.5),
             ("disc", "orange", "ALBUMS", 13.5), ("skyline", "orange", "GENRES", 13.5), ("star", "orange", "RATING", 13.5),
             ("trophy", "orange", "TOP 100", 13.5), ("magnifier", "orange", "SEARCH", 13.5), ("wheel", "orange", "SCAN MS", 13.5)]
    map_items = [(14, 44), (138, 40), (268, 44), (370, 44), (24, 100), (136, 104), (250, 100), (352, 104), (154, 150)]
    caption = (38, 13)
    sizes = {"menuhighlight": (480, 16), "medialibrarybkg": (472, 208)}

    @property
    def layout(self):
        lay = {"MENU_INTERLINE": "1", "MEDIALIBRARY_MAP": "1", "POS_MEDIALIBRARY": "%d,%d" % self.map_origin,
               "POS_MEDIALIBRARY_MAP_CAPTION": "%d,%d" % (self.map_origin[0] + self.caption[0], self.map_origin[1] + self.caption[1]),
               # GT2's exit sign sits at the left of the bottom bar
               "POS_FREE_MEMORY_LABEL": "46,254", "POS_FREE_MEMORY_TEXT": "110,254"}
        lay.update(map_layout(self.map_items, self.map_origin))
        return lay

    def cfg(self):
        c = super().cfg()
        c["STR_FONT_NORMAL_NAME"] = "$skinimage/" + self.oft[0]
        return c

    def background(self, w, h):
        defs, city = gt2_city(w, h, seed=21, strength=0.6)
        body = city + '<rect x="3" y="3" width="%d" height="%d" rx="6" fill="none" stroke="%s" stroke-width="1.5" opacity="0.75"/>' % (w - 6, h - 6, GT2_ORANGE)
        return doc(w, h, body, defs)

    def exit_sign(self, x, y):
        man = ('<g transform="translate(%s %s)" fill="#000">' % (f(x + 18), f(y + 1.5))
               + '<circle cx="5.5" cy="2" r="1.8"/><path d="M4.2 4 L7 4.4 L8.6 7.2 L10.6 7.8 L10.3 9 L7.9 8.4 L6.9 6.8 L6.3 9 L8.6 11 L8 13.4 L6.8 13.2 '
               'L7.1 11.6 L4.8 9.8 L3.6 12.6 L1.2 12.8 L1.2 11.6 L2.8 11.4 L4 8 L4.6 5.9 L3.3 6.6 L2.3 8.4 L1.2 8 L2.6 5.4 Z"/></g>')
        arrow = '<polygon points="%s" fill="#000"/>' % pts([(x + 4, y + 8), (x + 10, y + 3.5), (x + 10, y + 6.4), (x + 16, y + 6.4),
                                                           (x + 16, y + 9.6), (x + 10, y + 9.6), (x + 10, y + 12.5)])
        return ('<rect x="%s" y="%s" width="32" height="16" rx="3" fill="url(#sg)" stroke="#000" stroke-width="1.4"/>' % (f(x), f(y))
                + arrow + man)

    def bar(self, w, h, top):
        y = h - 2 if top else 0
        body = '<rect width="%d" height="%d" fill="#000"/><rect y="%d" width="%d" height="2" fill="%s"/>' % (w, h, y, w, GT2_ORANGE)
        if not top:
            body += self.exit_sign(4, 3)
        return doc(w, h, body, SIGN_GRAD)

    def tab(self, w, h, sel, i):
        label = ["File Browser", "Playlists", "Playlist Editor", "Media Library", "Settings"][i - 1]
        g = (('<linearGradient id="t" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffb43c"/>'
              '<stop offset="1" stop-color="#e8800a"/></linearGradient>') if sel else
             ('<linearGradient id="t" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#6c6c6c"/>'
              '<stop offset="1" stop-color="#383838"/></linearGradient>'))
        body = ('<rect x="2" y="0.8" width="%s" height="%s" rx="7" fill="url(#t)" stroke="#000" stroke-width="1.4"/>' % (f(w - 4), f(h - 1.6))
                + gt2_label(w / 2, 12.2, label, 13, anchor="middle"))
        return doc(w, h, body, g)

    def panel_svg(self, w, h):
        return doc(w, h, '<rect x="1" y="1" width="%d" height="%d" rx="5" fill="#000" fill-opacity="0.9" stroke="%s" stroke-width="2"/>' % (w - 2, h - 2, GT2_ORANGE))

    def highlight_svg(self, w, h):
        return doc(w, h, '<rect x="0.5" y="0.5" width="%d" height="%d" rx="3" fill="%s" stroke="#000" stroke-width="1"/>' % (w - 1, h - 1, GT2_ORANGE))

    def progress_svgs(self):
        bkg = doc(464, 10, '<rect x="0.5" y="0.5" width="463" height="9" rx="4" fill="#000" stroke="%s"/>' % GT2_ORANGE)
        bar = doc(464, 6, '<rect x="2" width="460" height="6" rx="2" fill="#ffb43c"/>')
        return bkg, bar

    def nocover_svg(self, s):
        defs, city = gt2_city(s, s, seed=4, strength=0.55)
        body = ('<g clip-path="url(#cl)">%s</g>' % city
                + '<circle cx="%s" cy="%s" r="%s" fill="#000"/>' % (f(s / 2), f(s / 2), f(s * 0.3))
                + '<circle cx="%s" cy="%s" r="%s" fill="none" stroke="%s" stroke-width="%s"/>' % (f(s / 2), f(s / 2), f(s * 0.26), GT2_ORANGE, f(s * 0.07))
                + gt2_label(s / 2, s / 2 + 5.5, "PLAY", 16, anchor="middle")
                + '<rect x="1" y="1" width="%d" height="%d" rx="4" fill="none" stroke="%s" stroke-width="2"/>' % (s - 2, s - 2, GT2_ORANGE))
        return doc(s, s, body, defs + '<clipPath id="cl"><rect width="%d" height="%d" rx="4"/></clipPath>' % (s, s))

    def map_svg(self, w, h):
        defs, city = gt2_city(w, h, seed=8, strength=1.0)
        cx, cy = self.caption
        box = ('<rect x="8" y="7" width="168" height="26" rx="4" fill="url(#sg)" stroke="#000" stroke-width="2"/>'
               + gt2_sign(12, 9.5, "checker", size=21))
        body = ('<g clip-path="url(#mc)">%s</g>' % city + box + self.exit_sign(w - 42, h - 26)
                + '<rect x="1.25" y="1.25" width="%s" height="%s" rx="6" fill="none" stroke="%s" stroke-width="2.5"/>' % (f(w - 2.5), f(h - 2.5), GT2_ORANGE))
        return doc(w, h, body, defs + SIGN_GRAD + '<clipPath id="mc"><rect width="%d" height="%d" rx="6"/></clipPath>' % (w, h))

    def badge_svgs(self):
        jobs = {}
        for i, (kind, color, label, size) in enumerate(self.signs, 1):
            tw = text_width(label, size, family=ROBOTO, weight=700)
            w, h = int(math.ceil(4 + 24 + 4 + tw + 6)), 34
            body = gt2_sign(4, 4, kind, color) + gt2_label(31, 20, label, size)
            hot = (gt2_sign(4, 4, kind, color) + gt2_label(31, 20, label, size, fill="#ffd23a")
                   + pointer(20, 18, fill="#ffd23a", stroke="#000"))
            jobs["mlitem%d" % i] = (doc(w, h, body, SIGN_GRAD), w, h)
            jobs["mlitemsel%d" % i] = (doc(w, h, '<g filter="url(#hot)">%s</g>' % hot,
                                           SIGN_GRAD + glow_filter("hot", "#ffd23a", 0.8, 1.6, 1)), w, h)
        return jobs

    def svg_jobs(self, sizes):
        jobs = super().svg_jobs(sizes)
        jobs.update(self.list_icon_svgs())
        return jobs

    def list_icon_svgs(self):
        """Folder / song list icons as small GT2 signs."""
        glyphs = {"folder": ('<path d="M3.5 6 H8.5 L10 7.8 H18.5 V17 H3.5 Z"/>', 19),
                  "music": ('<ellipse cx="8" cy="15" rx="3.4" ry="2.6" transform="rotate(-20 8 15)"/>'
                            '<rect x="10.4" y="4" width="2" height="11.2"/><path d="M10.4 4 L16.8 6.2 L16.8 9 L12.4 7.6 Z"/>', 16)}
        jobs = {}
        for name, (glyph, w) in glyphs.items():
            body = ('<g transform="translate(%s 0) scale(0.727)">' % f((w - 16) / 2)
                    + '<rect x="1" y="1" width="20" height="20" rx="3" fill="url(#sg)" stroke="#000" stroke-width="1.8"/>'
                    + '<g fill="#000">%s</g></g>' % glyph)
            jobs["icon_" + name] = (doc(w, 16, body, SIGN_GRAD), w, 16)
        return jobs

    def icons(self):
        return {
            "folder": self._svg_icons["folder"],
            "music": self._svg_icons["music"],
            "star": icon_star(16, "#ffd23a", "#f5a01a", rgba("#000000", 255)),
            "blankstar": icon_star(16, "#3a3a3a", "#1f1f1f", rgba("#000000", 255), gloss_a=20),
            "battery": icon_battery(30, 14, "#ffffff", ("#ffb238", "#e8800a"), rgba("#000000", 255)),
            "batterycharging": icon_battery(30, 14, "#ffffff", ("#b8f07a", "#4aa615"), rgba("#000000", 255)),
            "batterylow": icon_battery(30, 14, "#ffffff", ("#ff9a8a", "#d0301a"), rgba("#000000", 255), frac=0.2),
            "volume": icon_speaker(16, "#ffffff", GT2_ORANGE),
            "headphone": icon_headphone(16, "#ffffff"),
        }


THEMES = {"pitlane3": PitLane3, "pitlane2": PitLane2}
