#!/usr/bin/env python3
"""Generate LightMP3 skins: images + skin.cfg, drawn procedurally.

All skins share one "readable" layout (bold font, bigger text, room for it in
every panel) and differ in palette and artwork. Usage:

    make_skins.py OUT_DIR [theme ...]

Writes OUT_DIR/<Skin Name>/skin.cfg and OUT_DIR/<Skin Name>/images/*.png.
Themes: duke, luna, clickwheel, y2k, pitlane3, pitlane2 (default: all).
"""
import math
import os
import re
import sys

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CFG = os.path.join(HERE, "..", "..", "src_v2", "skins", "default", "skin.cfg")
SS = 4  # supersampling for anti-aliased shapes
rng = np.random.default_rng(7)


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------
def rgba(c, a=None):
    if isinstance(c, str):
        c = c.lstrip("#")
        c = tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    c = tuple(c)
    if len(c) == 3:
        c = c + (255 if a is None else a,)
    elif a is not None:
        c = c[:3] + (a,)
    return c


def gradient(w, h, stops, angle=90):
    """Linear gradient. stops: [(pos 0..1, color)], angle 90 = top->bottom."""
    t = math.radians(angle)
    dx, dy = math.cos(t), math.sin(t)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    proj = (xs - w / 2) * dx + (ys - h / 2) * dy
    span = abs(w / 2 * dx) + abs(h / 2 * dy)
    p = np.clip((proj + span) / (2 * span if span else 1), 0, 1)
    return _ramp(p, stops)


def radial(w, h, cx, cy, r, stops):
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    p = np.clip(np.hypot(xs - cx, ys - cy) / r, 0, 1)
    return _ramp(p, stops)


def _ramp(p, stops):
    stops = [(pos, np.array(rgba(c), np.float32)) for pos, c in stops]
    out = np.zeros(p.shape + (4,), np.float32)
    for i in range(len(stops) - 1):
        p0, c0 = stops[i]
        p1, c1 = stops[i + 1]
        m = (p >= p0) & (p <= p1)
        f = ((p - p0) / (p1 - p0 if p1 > p0 else 1))[..., None]
        out[m] = (c0 + (c1 - c0) * f)[m]
    out[p < stops[0][0]] = stops[0][1]
    out[p > stops[-1][0]] = stops[-1][1]
    return Image.fromarray(out.clip(0, 255).astype(np.uint8), "RGBA")


def solid(w, h, c):
    return Image.new("RGBA", (w, h), rgba(c))


def mask_from(w, h, draw_fn):
    """Anti-aliased 'L' mask: draw_fn(ImageDraw, scale) draws in white."""
    m = Image.new("L", (w * SS, h * SS), 0)
    draw_fn(ImageDraw.Draw(m), SS)
    return m.resize((w, h), Image.LANCZOS)


def rrect(w, h, r, inset=0):
    return mask_from(w, h, lambda d, s: d.rounded_rectangle(
        [inset * s, inset * s, (w - inset) * s - 1, (h - inset) * s - 1], radius=max(0, r - inset) * s, fill=255))


def rrect_hanging(w, h, r, side_inset=1):
    """Rounded only at the bottom: tabs that hang from the toolbar."""
    return mask_from(w, h, lambda d, s: d.rounded_rectangle(
        [side_inset * s, -r * s, (w - side_inset) * s - 1, (h - 1) * s], radius=r * s, fill=255))


def edge_no_top(m, rows=2):
    """Outline of a shape without its top edge (text may touch the top)."""
    e = ring(m, m.filter(ImageFilter.MinFilter(3)))
    cut = Image.new("L", m.size, 255)
    ImageDraw.Draw(cut).rectangle([0, 0, m.size[0], rows - 1], fill=0)
    return ImageChops.multiply(e, cut)


def outline(w, h, r, width=1):
    """Rounded-rectangle outline drawn directly (keeps straight edges at the image border)."""
    return mask_from(w, h, lambda d, s: d.rounded_rectangle([0, 0, w * s - 1, h * s - 1], radius=r * s, outline=255, width=int(width * s)))


def poly(w, h, pts):
    return mask_from(w, h, lambda d, s: d.polygon([(x * s, y * s) for x, y in pts], fill=255))


def ellipse(w, h, box):
    return mask_from(w, h, lambda d, s: d.ellipse([v * s for v in box], fill=255))


def masked(img, mask):
    img = img.copy()
    a = ImageChops.multiply(img.getchannel("A"), mask)
    img.putalpha(a)
    return img


def ring(mask_outer, mask_inner):
    return ImageChops.subtract(mask_outer, mask_inner)


def over(*layers):
    base = layers[0].copy()
    for l in layers[1:]:
        base.alpha_composite(l)
    return base


def fill(mask, c):
    img = Image.new("RGBA", mask.size, rgba(c))
    return masked(img, mask)


def blur(img, r):
    return img.filter(ImageFilter.GaussianBlur(r))


def glow(mask, c, r):
    return blur(fill(mask, c), r)


def brushed(w, h, light, dark, streak=0.18, vertical=False):
    """Brushed metal: per-row noise smeared along the brush direction."""
    n = rng.normal(0, 1, (h, w)).astype(np.float32)
    k = max(3, w // 3 if not vertical else h // 3)
    img = Image.fromarray(((n - n.min()) / (np.ptp(n) or 1) * 255).astype(np.uint8), "L")
    img = img.filter(ImageFilter.BoxBlur(0)).resize((w, h))
    arr = np.asarray(img, np.float32) / 255.0
    # smear
    ker = np.ones(k, np.float32) / k
    if vertical:
        arr = np.apply_along_axis(lambda c: np.convolve(np.pad(c, k, mode="wrap"), ker, "same")[k:-k], 0, arr)
    else:
        arr = np.apply_along_axis(lambda r: np.convolve(np.pad(r, k, mode="wrap"), ker, "same")[k:-k], 1, arr)
    arr = (arr - arr.min()) / (np.ptp(arr) or 1)
    base = np.asarray(gradient(w, h, [(0, light), (0.5, dark), (1, light)]), np.float32)
    shade = (arr[..., None] - 0.5) * 2 * streak * 255
    out = base.copy()
    out[..., :3] = (base[..., :3] + shade).clip(0, 255)
    return Image.fromarray(out.astype(np.uint8), "RGBA")


def noise_overlay(w, h, amount, alpha=40):
    n = rng.normal(128, amount, (h, w)).clip(0, 255).astype(np.uint8)
    img = Image.merge("RGBA", [Image.fromarray(n)] * 3 + [Image.new("L", (w, h), alpha)])
    return img


def gloss(mask, top_alpha=150, bottom_alpha=10, height=0.5, color="#ffffff"):
    """White sheen over the top part of a shape."""
    w, h = mask.size
    g = gradient(w, h, [(0, rgba(color, top_alpha)), (height, rgba(color, bottom_alpha)), (height + 0.001, rgba(color, 0)), (1, rgba(color, 0))])
    return masked(g, mask)


def shift(img, dx, dy):
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (dx, dy), img)
    return out


def lighten_edge(mask, c, width=1, top=True):
    """1px highlight along the top (or shadow along the bottom) inside a shape."""
    inner = shift_mask(mask, 0, width if top else -width)
    return fill(ImageChops.subtract(mask, inner), c)


def shift_mask(m, dx, dy):
    out = Image.new("L", m.size, 0)
    out.paste(m, (dx, dy))
    return out


# ---------------------------------------------------------------------------
# Icons (drawn at SS scale via mask_from)
# ---------------------------------------------------------------------------
def icon_folder(w, h, back, front, edge, gloss_a=110):
    tab = poly(w, h, [(1, 2), (w * 0.42, 2), (w * 0.52, 4.5), (w - 2, 4.5), (w - 2, h - 2), (1, h - 2)])
    body = mask_from(w, h, lambda d, s: d.rounded_rectangle([1 * s, 5.5 * s, (w - 1) * s, (h - 1) * s], radius=2 * s, fill=255))
    img = over(fill(tab, back), fill(body, front))
    img = over(img, masked(gradient(w, h, [(0, rgba("#ffffff", gloss_a)), (0.55, rgba("#ffffff", 0))]), body))
    img = over(img, fill(ring(body, rrect_inset(body)), edge))
    return img


def rrect_inset(m):
    return m.filter(ImageFilter.MinFilter(3))


def icon_note(w, h, color, disc=None, disc_edge=None, outline=None):
    layers = [Image.new("RGBA", (w, h), (0, 0, 0, 0))]
    if disc:
        dm = ellipse(w, h, [0.5, 0.5, w - 0.5, h - 0.5])
        layers += [masked(radial(w, h, w * 0.35, h * 0.3, w * 0.8, [(0, rgba(disc[0])), (1, rgba(disc[1]))]), dm)]
        if disc_edge:
            layers += [fill(ring(dm, rrect_inset(dm)), disc_edge)]
    note = mask_from(w, h, lambda d, s: (
        d.ellipse([w * 0.16 * s, h * 0.56 * s, w * 0.54 * s, h * 0.90 * s], fill=255),
        d.rectangle([w * 0.43 * s, h * 0.12 * s, w * 0.55 * s, h * 0.74 * s], fill=255),
        d.polygon([(w * 0.43 * s, h * 0.10 * s), (w * 0.86 * s, h * 0.24 * s), (w * 0.86 * s, h * 0.44 * s), (w * 0.55 * s, h * 0.32 * s)], fill=255)))
    if outline:
        layers += [fill(note.filter(ImageFilter.MaxFilter(3)), outline)]
    layers += [fill(note, color)]
    return over(*layers)


def star_points(cx, cy, r_out, r_in, n=5):
    pts = []
    for i in range(2 * n):
        r = r_out if i % 2 == 0 else r_in
        a = -math.pi / 2 + i * math.pi / n
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def icon_star(size, fill_top, fill_bottom, edge, gloss_a=120):
    m = poly(size, size, star_points(size / 2, size / 2 + 0.8, size * 0.50, size * 0.25))
    img = masked(gradient(size, size, [(0, rgba(fill_top)), (1, rgba(fill_bottom))]), m)
    img = over(img, masked(gradient(size, size, [(0, rgba("#ffffff", gloss_a)), (0.5, rgba("#ffffff", 0))]), m))
    if edge:
        img = over(img, fill(ring(m, rrect_inset(m)), edge))
    return img


def icon_battery(w, h, shell, level, edge, frac=0.8):
    body = rrect(w - 3, h, 3)
    b = Image.new("L", (w, h), 0)
    b.paste(body, (0, 0))
    nub = mask_from(w, h, lambda d, s: d.rounded_rectangle([(w - 3.5) * s, h * 0.3 * s, w * s - 1, h * 0.7 * s], radius=1 * s, fill=255))
    shell_img = over(fill(b, shell), fill(nub, shell))
    inner = mask_from(w, h, lambda d, s: d.rounded_rectangle([2.5 * s, 2.5 * s, (2.5 + (w - 8) * frac) * s, (h - 2.5) * s], radius=1.5 * s, fill=255))
    lv = masked(gradient(w, h, [(0, rgba(level[0])), (1, rgba(level[1]))]), inner)
    hl = masked(gradient(w, h, [(0, rgba("#ffffff", 140)), (0.5, rgba("#ffffff", 0))]), b)
    return over(shell_img, fill(ring(b, rrect_inset(b)), edge), lv, hl)


def icon_cpu(s, body, pins, mark):
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    pm = mask_from(s, s, lambda d, k: [d.rectangle([(3 + i * 3) * k, 1 * k, (4.2 + i * 3) * k, (s - 1) * k], fill=255) for i in range(4)] +
                   [d.rectangle([1 * k, (3 + i * 3) * k, (s - 1) * k, (4.2 + i * 3) * k], fill=255) for i in range(4)])
    bm = rrect(s, s, 2, inset=3)
    img = over(img, fill(pm, pins), masked(gradient(s, s, [(0, rgba(body[0])), (1, rgba(body[1]))]), bm))
    cm = rrect(s, s, 1, inset=6)
    return over(img, fill(cm, mark))


def icon_speaker(s, color, wave):
    m = poly(s, s, [(2, s * 0.36), (s * 0.3, s * 0.36), (s * 0.55, s * 0.12), (s * 0.55, s * 0.88), (s * 0.3, s * 0.64), (2, s * 0.64)])
    w1 = mask_from(s, s, lambda d, k: (d.arc([s * 0.42 * k, s * 0.25 * k, s * 0.82 * k, s * 0.75 * k], -50, 50, fill=255, width=int(1.6 * k)),
                                       d.arc([s * 0.38 * k, s * 0.08 * k, s * 1.0 * k, s * 0.92 * k], -50, 50, fill=255, width=int(1.6 * k))))
    return over(fill(m, color), fill(w1, wave))


def icon_headphone(s, color):
    m = mask_from(s, s, lambda d, k: (d.arc([2 * k, 2 * k, (s - 2) * k, (s + 2) * k], 180, 360, fill=255, width=int(2 * k)),
                                      d.rounded_rectangle([1.5 * k, s * 0.5 * k, 5.5 * k, (s - 1.5) * k], radius=1.5 * k, fill=255),
                                      d.rounded_rectangle([(s - 5.5) * k, s * 0.5 * k, (s - 1.5) * k, (s - 1.5) * k], radius=1.5 * k, fill=255)))
    return fill(m, color)


# ---------------------------------------------------------------------------
# Shared readable layout
# ---------------------------------------------------------------------------
HIDE = "-1000,-1000"  # off-screen: OSLib clips it, nothing is drawn

LAYOUT = {
    "MENU_INTERLINE": "0",
    "FILE_BROWSER_SHOW_MISSINGCOVERART": "1",
    # top / bottom bars
    "POS_TOOLBAR_1": "0,0", "POS_TOOLBAR_2": "0,252",
    "POS_APP_NAME_TEXT": "6,2",
    "POS_CPU_ICON": "228,2", "POS_CPU_TEXT": "247,2",
    "POS_HEADPHONES_ICON": "322,2", "POS_REMOTE_ICON": HIDE,
    "POS_BATTERY_ICON": "342,3", "POS_BATTERY_TEXT": "376,2",
    "POS_FREE_MEMORY_LABEL": "6,254", "POS_FREE_MEMORY_TEXT": "72,254",
    "POS_VOLUME_ICON": "196,254", "POS_VOLUME_TEXT": "216,254",
    "POS_CLOCK_TEXT": "362,254",
    # tabs
    "POS_BUTTON_1": "0,23", "POS_BUTTON_2": "96,23", "POS_BUTTON_3": "192,23",
    "POS_BUTTON_4": "288,23", "POS_BUTTON_5": "384,23",
    "POS_HELP": "60,46", "POS_POPUP": "90,92",
    # player: big cover left, track info right
    "POS_COVERART": "8,26", "COVERART_WIDTH": "118", "COVERART_HEIGHT": "118",
    "POS_FILE_INFO_BKG": "132,24",
    "POS_TITLE_LABEL": "138,29", "POS_TITLE_VALUE": "192,29", "TITLE_VALUE_WIDTH": "278",
    "POS_ARTIST_LABEL": "138,47", "POS_ARTIST_VALUE": "192,47",
    "POS_ALBUM_LABEL": "138,65", "POS_ALBUM_VALUE": "192,65",
    "POS_GENRE_LABEL": "138,83", "POS_GENRE_VALUE": "192,83",
    "POS_YEAR_LABEL": "138,101", "POS_YEAR_VALUE": "192,101",
    "POS_TIME_LABEL": "138,119", "POS_TIME_VALUE": "192,119",
    "POS_RATING_LABEL": "322,83", "POS_RATING_VALUE": "382,82",
    "POS_PLAYED_LABEL": "322,101", "POS_PLAYED_VALUE": "400,101",
    "POS_TRACK_LABEL": "322,119", "POS_TRACK_VALUE": "382,119",
    # player: file specs (left) and status (right). Mode, emphasis and
    # equalizer are hidden: long values overflowed and they're rarely useful.
    "POS_FILE_SPECS_BKG": "8,154",
    "POS_MODE_LABEL": HIDE, "POS_MODE_VALUE": HIDE,
    "POS_BITRATE_LABEL": "14,160", "POS_BITRATE_VALUE": "98,160",
    "POS_SAMPLERATE_LABEL": "14,180", "POS_SAMPLERATE_VALUE": "98,180",
    "POS_FILE_FORMAT_LABEL": "14,200", "POS_FILE_FORMAT_VALUE": "98,200",
    "POS_EMPHASIS_LABEL": HIDE, "POS_EMPHASIS_VALUE": HIDE,
    "POS_PLAYER_STATUS_BKG": "244,154",
    "POS_SLEEP_MODE_LABEL": "250,158", "POS_SLEEP_MODE_VALUE": "346,158",
    "POS_PLAY_MODE_LABEL": "250,176", "POS_PLAY_MODE_VALUE": "346,176",
    "POS_STATUS_LABEL": "250,194", "POS_STATUS_VALUE": "346,194",
    "POS_VOLUME_BOOST_LABEL": "250,212", "POS_VOLUME_BOOST_VALUE": "346,212",
    "POS_EQUALIZER_LABEL": HIDE, "POS_EQUALIZER_VALUE": HIDE,
    "POS_PROGRESS": "8,236",
    # file browser: list on the left, cover art column on the right
    "POS_FILE_BROWSER": "4,42",
    "POS_FILE_BROWSER_COVERART": "376,52",
    "FILE_BROWSER_COVERART_WIDTH": "98", "FILE_BROWSER_COVERART_HEIGHT": "98",
    # playlists / editor / settings / library
    "POS_PLAYLIST_BROWSER": "4,42", "POS_PLAYLIST_BROWSER_INFO_BKG": "4,204",
    "POS_PLAYLIST_NAME_LABEL": "10,206", "POS_PLAYLIST_NAME_VALUE": "112,206",
    "POS_PLAYLIST_TOTAL_TRACKS_LABEL": "10,221", "POS_PLAYLIST_TOTAL_TRACKS_VALUE": "112,221",
    "POS_PLAYLIST_TOTAL_TIME_LABEL": "10,236", "POS_PLAYLIST_TOTAL_TIME_VALUE": "112,236",
    "POS_PLAYLIST_EDITOR": "4,42", "POS_PLAYLIST_EDITOR_TRACK_INFO_BKG": "4,204",
    "POS_PLAYLIST_TITLE_LABEL": "10,206", "POS_PLAYLIST_TITLE_VALUE": "80,206",
    "POS_PLAYLIST_ARTIST_LABEL": "10,221", "POS_PLAYLIST_ARTIST_VALUE": "80,221",
    "POS_PLAYLIST_ALBUM_LABEL": "10,236", "POS_PLAYLIST_ALBUM_VALUE": "80,236",
    "POS_SETTINGS": "4,42",
    "POS_MEDIALIBRARY": "100,52", "POS_MEDIALIBRARY_QUERY": "4,42",
    "POS_MEDIALIBRARY_INFO_BKG": "4,204",
    "POS_MEDIALIBRARY_TOTAL_TRACKS_LABEL": "10,208", "POS_MEDIALIBRARY_TOTAL_TRACKS_VALUE": "112,208",
    "POS_MEDIALIBRARY_TOTAL_TIME_LABEL": "10,226", "POS_MEDIALIBRARY_TOTAL_TIME_VALUE": "112,226",
    "POS_MEDIALIBRARY_GENRE_LABEL": "10,206", "POS_MEDIALIBRARY_GENRE_VALUE": "80,206",
    "POS_MEDIALIBRARY_YEAR_LABEL": "10,221", "POS_MEDIALIBRARY_YEAR_VALUE": "80,221",
    "POS_MEDIALIBRARY_TIME_LABEL": "200,221", "POS_MEDIALIBRARY_TIME_VALUE": "250,221",
    "POS_MEDIALIBRARY_RATING_LABEL": "10,236", "POS_MEDIALIBRARY_RATING_VALUE": "80,235",
    "POS_MEDIALIBRARY_PLAYED_LABEL": "200,236", "POS_MEDIALIBRARY_PLAYED_VALUE": "270,236",
    "POS_MEDIALIBRARY_COVERART": "426,206",
    "MEDIALIBRARY_COVERART_WIDTH": "42", "MEDIALIBRARY_COVERART_HEIGHT": "42",
}

# Image sizes for the layout above (name: (w, h)).
SIZES = {
    "bkg_default": (480, 272), "toptoolbar": (480, 21), "bottomtoolbar": (480, 20),
    "menubkg": (366, 210), "menuhighlight": (480, 15),
    "menuplaylistbkg": (472, 160), "medialibraryquerybkg": (472, 160),
    "medialibrarybkg": (280, 161),
    "playlistinfobkg": (472, 46), "trackinfobkg": (472, 46), "medialibraryinfobkg": (472, 46),
    "fileinfobkg": (342, 124), "filespecsbkg": (230, 76), "playerstatusbkg": (232, 76),
    "popupbkg": (300, 86), "helpbkg": (360, 176), "medialibraryscanbkg": (400, 100),
    "progressbkg": (464, 10), "progress": (464, 6),
    "nocoverart": (118, 118),
    "folder": (19, 16), "music": (16, 16), "star": (16, 16), "blankstar": (16, 16),
    "battery": (30, 14), "batterycharging": (30, 14), "batterylow": (30, 14),
    "cpu": (16, 16), "volume": (16, 16), "headphone": (16, 16),
}
for i in range(1, 6):
    SIZES["button%d" % i] = (96, 16)
    SIZES["buttonsel%d" % i] = (96, 16)

PANEL_NAMES = ["menubkg", "menuplaylistbkg", "medialibraryquerybkg", "medialibrarybkg", "playlistinfobkg",
               "trackinfobkg", "medialibraryinfobkg", "fileinfobkg", "filespecsbkg", "playerstatusbkg",
               "popupbkg", "helpbkg", "medialibraryscanbkg"]


def write_cfg(path, name, desc, theme_cfg):
    """Default skin.cfg with our values swapped in (comments kept)."""
    with open(DEFAULT_CFG, encoding="latin-1") as f:
        lines = f.read().replace("\r\n", "\n").split("\n")
    values = dict(LAYOUT)
    values.update(theme_cfg)
    while lines and lines[0].startswith("#") and not lines[0].startswith("####"):
        lines.pop(0)  # old header (skin name/author)
    seen = set()
    out = []
    for line in lines:
        m = re.match(r"^([A-Z0-9_]+)=", line)
        if m and m.group(1) in values:
            seen.add(m.group(1))
            line = "%s=%s" % (m.group(1), values[m.group(1)])
        out.append(line)
    extra = [k for k in values if k not in seen]
    if extra:
        out += ["", "# Added by make_skins.py"] + ["%s=%s" % (k, values[k]) for k in extra]
    header = ["#Skin Name      : %s" % name, "#     %s" % desc,
              "#     Made with tools/skins/make_skins.py (bigger bold text, high contrast)", ""]
    with open(path, "w", encoding="latin-1", newline="\r\n") as f:
        f.write("\n".join(header + out) + "\n")


# ---------------------------------------------------------------------------
# Themes
# ---------------------------------------------------------------------------
class Theme:
    name = ""
    desc = ""
    font = "flash0:/font/ltn4.pgf"  # bold sans
    size = 56  # bigger than the stock 50, and bold; 62+ overflows the 96 px tabs
    colors = {}

    def cfg(self):
        c = {"STR_FONT_NORMAL_NAME": self.font, "FONT_NORMAL_SIZE": str(self.size)}
        for k, v in self.colors.items():
            c["RGBA_" + k] = ",".join(str(x) for x in rgba(v))
        return c

    def build(self, out):
        imgs = {}
        imgs["bkg_default"] = self.background(480, 272).convert("RGB").convert("RGBA")
        imgs["toptoolbar"] = self.toolbar(480, 21, top=True)
        imgs["bottomtoolbar"] = self.toolbar(480, 20, top=False)
        for i in range(1, 6):
            imgs["button%d" % i] = self.tab(96, 16, False, i)
            imgs["buttonsel%d" % i] = self.tab(96, 16, True, i)
        for n in PANEL_NAMES:
            imgs[n] = self.panel(*SIZES[n], kind=n)
        imgs["menuhighlight"] = self.highlight(480, 15)
        imgs["progressbkg"] = self.progress_bkg(464, 10)
        imgs["progress"] = self.progress_bar(464, 6)
        imgs["nocoverart"] = self.nocover(118)
        imgs.update(self.icons())
        os.makedirs(os.path.join(out, "images"), exist_ok=True)
        for n, (w, h) in SIZES.items():
            im = imgs[n]
            assert im.size == (w, h), (self.name, n, im.size, (w, h))
            im.save(os.path.join(out, "images", n + ".png"), optimize=True)
        write_cfg(os.path.join(out, "skin.cfg"), self.name, self.desc, self.cfg())


# --- Original Xbox style ----------------------------------------------------
class Duke(Theme):
    name = "Duke"
    desc = "Original Xbox style: black and glowing green"
    G = "#7ed321"
    colors = {
        "TOOLBAR_TEXT": "#e8ffd8", "TOOLBAR_TEXT_SHADOW": (0, 0, 0, 255),
        "BUTTONBAR_TEXT": "#a8f070", "BUTTONBAR_TEXT_SHADOW": (0, 0, 0, 255),
        "BUTTONBAR_SELECTED_TEXT": "#061000", "BUTTONBAR_SELECTED_TEXT_SHADOW": (0, 0, 0, 0),
        "POPUP_TITLE_TEXT": "#9cf04a", "POPUP_TITLE_TEXT_SHADOW": (0, 0, 0, 255),
        "POPUP_MESSAGE_TEXT": "#ffffff", "POPUP_MESSAGE_TEXT_SHADOW": (0, 0, 0, 255),
        "MENU_TEXT": "#ffffff", "MENU_TEXT_SHADOW": (0, 0, 0, 255),
        "MENU_SELECTED_TEXT": "#061000", "MENU_SELECTED_TEXT_SHADOW": (0, 0, 0, 0),
        "LABEL_TEXT": "#93e550", "LABEL_TEXT_SHADOW": (0, 0, 0, 255),
        "TEXT": "#ffffff", "TEXT_SHADOW": (0, 0, 0, 255),
        "HELP_TITLE_TEXT": "#9cf04a", "HELP_TITLE_TEXT_SHADOW": (0, 0, 0, 255),
        "HELP_TEXT": "#ffffff", "HELP_TEXT_SHADOW": (0, 0, 0, 255),
    }

    def background(self, w, h):
        bg = radial(w, h, 70, 250, 420, [(0, "#2f7a12"), (0.35, "#123d08"), (0.7, "#061204"), (1, "#020402")])
        glow2 = radial(w, h, 470, 30, 260, [(0, rgba("#3b8f15", 120)), (1, rgba("#000000", 0))])
        # glowing 'tubes'
        tubes = mask_from(w, h, lambda d, s: [d.arc([(-200 + i * 60) * s, (120 - i * 25) * s, (520 + i * 40) * s, (520 + i * 10) * s], 200, 340, fill=255, width=int((2 if i % 2 else 3) * s)) for i in range(4)])
        lines = over(glow(tubes, rgba("#7ed321", 200), 3), fill(tubes, rgba("#c8ff8a", 110)))
        # faint hex grid
        hexm = mask_from(w, h, lambda d, s: [d.regular_polygon(((x + (y % 2) * 13) * s, y * 22 * s, 13 * s), 6, outline=255, width=s) for y in range(14) for x in range(0, 500, 26)])
        hexes = fill(hexm, rgba("#4caf1a", 16))
        return over(bg, glow2, hexes, lines, noise_overlay(w, h, 30, 10))

    def toolbar(self, w, h, top):
        bar = gradient(w, h, [(0, "#1d3a12"), (0.5, "#0b1a07"), (1, "#020502")] if top else [(0, "#020502"), (0.5, "#0b1a07"), (1, "#1d3a12")])
        line = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(line)
        y = h - 1 if top else 0
        d.line([(0, y), (w, y)], fill=rgba(self.G, 230))
        lg = blur(line, 1.5)
        return over(bar, gloss(Image.new("L", (w, h), 255), 40, 0, 0.5), lg, line)

    def tab(self, w, h, sel, i):
        m = rrect_hanging(w, h, 7)
        if sel:
            body = masked(gradient(w, h, [(0, "#c6ff7a"), (0.5, "#7ed321"), (1, "#3b8f10")]), m)
            return over(body, gloss(m, 150, 30, 0.45), fill(edge_no_top(m), rgba("#e6ffcc", 200)))
        body = masked(gradient(w, h, [(0, "#22421a"), (1, "#081205")]), m)
        return over(body, gloss(m, 50, 0, 0.45), fill(edge_no_top(m), rgba("#5fbf1f", 170)))

    def panel(self, w, h, kind):
        m = rrect(w, h, 7)
        body = masked(gradient(w, h, [(0, rgba("#0d2108", 215)), (1, rgba("#020502", 225))]), m)
        edge = fill(ring(m, rrect_inset(m)), rgba(self.G, 190))
        inner = glow(ring(rrect_inset(m), rrect_inset(rrect_inset(m))), rgba(self.G, 70), 2)
        return over(body, inner, edge, gloss(m, 22, 0, 0.18))

    def highlight(self, w, h):
        m = rrect(w, h, 5)
        body = masked(gradient(w, h, [(0, "#b8ff6a"), (0.5, "#7ed321"), (1, "#4aa615")]), m)
        return over(body, gloss(m, 150, 20, 0.5))

    def progress_bkg(self, w, h):
        m = rrect(w, h, 5)
        return over(fill(m, rgba("#030803", 230)), fill(ring(m, rrect_inset(m)), rgba(self.G, 200)))

    def progress_bar(self, w, h):
        m = rrect(w, h, 3, inset=0)
        m2 = Image.new("L", (w, h), 0)
        m2.paste(rrect(w - 4, h, 3), (2, 0))
        body = masked(gradient(w, h, [(0, "#d6ff9e"), (0.5, "#7ed321"), (1, "#3d9a0e")]), m2)
        return over(body, gloss(m2, 120, 0, 0.5))

    def nocover(self, s):
        m = rrect(s, s, 10)
        bg = masked(radial(s, s, s * 0.5, s * 0.45, s * 0.75, [(0, "#2e7d10"), (0.6, "#0c2406"), (1, "#020502")]), m)
        orb = ellipse(s, s, [s * 0.2, s * 0.2, s * 0.8, s * 0.8])
        orb_img = masked(radial(s, s, s * 0.42, s * 0.36, s * 0.42, [(0, "#d8ff9a"), (0.5, "#7ed321"), (1, "#245f0a")]), orb)
        note = icon_note(int(s * 0.44), int(s * 0.44), rgba("#061000", 230))
        layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        layer.paste(note, (int(s * 0.27), int(s * 0.29)), note)
        return over(bg, glow(orb, rgba(self.G, 180), 6), orb_img, gloss(orb, 160, 0, 0.45), layer, fill(ring(m, rrect_inset(m)), rgba(self.G, 200)))

    def icons(self):
        G = self.G
        return {
            "folder": icon_folder(19, 16, "#3c8f14", "#7ed321", rgba("#0f2a05", 255)),
            "music": icon_note(16, 16, "#a8f060", outline="#020502"),
            "star": icon_star(16, "#f0ffd0", "#7ed321", rgba("#0f2a05", 255)),
            "blankstar": icon_star(16, "#1a3312", "#0a1606", rgba("#5fbf1f", 220), gloss_a=30),
            "battery": icon_battery(30, 14, "#1b3112", ("#c6ff7a", "#4aa615"), rgba("#7ed321", 230)),
            "batterycharging": icon_battery(30, 14, "#1b3112", ("#fff59a", "#c9b51a"), rgba("#7ed321", 230)),
            "batterylow": icon_battery(30, 14, "#1b3112", ("#ff8a7a", "#c0261a"), rgba("#7ed321", 230), frac=0.2),
            "cpu": icon_cpu(16, ("#2d5a1a", "#0e2207"), "#9be86a", rgba(G, 255)),
            "volume": icon_speaker(16, "#e8ffd8", rgba(G, 255)),
            "headphone": icon_headphone(16, "#e8ffd8"),
        }


# --- Windows XP style -------------------------------------------------------
class Luna(Theme):
    name = "Luna"
    desc = "Windows XP style: blue bars, green start button, white text"
    colors = {
        "TOOLBAR_TEXT": "#ffffff", "TOOLBAR_TEXT_SHADOW": (10, 30, 90, 200),
        "BUTTONBAR_TEXT": "#ffffff", "BUTTONBAR_TEXT_SHADOW": (10, 30, 90, 200),
        "BUTTONBAR_SELECTED_TEXT": "#ffffff", "BUTTONBAR_SELECTED_TEXT_SHADOW": (15, 60, 15, 230),
        "POPUP_TITLE_TEXT": "#fff6b0", "POPUP_TITLE_TEXT_SHADOW": (10, 30, 90, 220),
        "POPUP_MESSAGE_TEXT": "#ffffff", "POPUP_MESSAGE_TEXT_SHADOW": (10, 30, 90, 220),
        "MENU_TEXT": "#ffffff", "MENU_TEXT_SHADOW": (10, 30, 90, 220),
        "MENU_SELECTED_TEXT": "#ffffff", "MENU_SELECTED_TEXT_SHADOW": (15, 60, 15, 230),
        "LABEL_TEXT": "#dbe9ff", "LABEL_TEXT_SHADOW": (10, 30, 90, 220),
        "TEXT": "#ffffff", "TEXT_SHADOW": (10, 30, 90, 220),
        "HELP_TITLE_TEXT": "#fff6b0", "HELP_TITLE_TEXT_SHADOW": (10, 30, 90, 220),
        "HELP_TEXT": "#ffffff", "HELP_TEXT_SHADOW": (10, 30, 90, 220),
    }

    def background(self, w, h):
        sky = gradient(w, h, [(0, "#1f63d6"), (0.45, "#5b9bf0"), (0.75, "#b9dcff"), (1, "#d8ecff")])
        clouds = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(clouds)
        for cx, cy, rw, rh in [(90, 70, 70, 16), (130, 62, 50, 14), (330, 50, 80, 18), (390, 60, 60, 14), (250, 95, 60, 10)]:
            d.ellipse([cx - rw, cy - rh, cx + rw, cy + rh], fill=(255, 255, 255, 150))
        clouds = blur(clouds, 7)
        hill = mask_from(w, h, lambda d, s: d.ellipse([-260 * s, 150 * s, 760 * s, 620 * s], fill=255))
        hill_img = masked(radial(w, h, 180, 170, 420, [(0, "#7cc544"), (0.4, "#4f9a24"), (1, "#22610f")]), hill)
        hill2 = mask_from(w, h, lambda d, s: d.ellipse([200 * s, 185 * s, 900 * s, 560 * s], fill=255))
        hill2_img = masked(radial(w, h, 380, 200, 340, [(0, rgba("#6db83a", 255)), (1, rgba("#2a6d14", 255))]), hill2)
        return over(sky, clouds, hill2_img, hill_img, noise_overlay(w, h, 20, 8))

    def toolbar(self, w, h, top):
        bar = gradient(w, h, [(0, "#3d95ff"), (0.12, "#2c7cf4"), (0.5, "#245edb"), (0.9, "#1f4fc4"), (1, "#173fa0")])
        hl = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(hl).line([(0, 0), (w, 0)], fill=rgba("#7fb8ff", 255))
        return over(bar, hl)

    def tab(self, w, h, sel, i):
        m = rrect_hanging(w, h, 6)
        if sel:  # the green Start button
            body = masked(gradient(w, h, [(0, "#7ad37a"), (0.2, "#4cb84c"), (0.6, "#2f9a2f"), (1, "#237a23")]), m)
            return over(body, gloss(m, 110, 0, 0.35), fill(edge_no_top(m), rgba("#1c5e1c", 230)))
        body = masked(gradient(w, h, [(0, "#5ea3ff"), (0.5, "#3277ea"), (1, "#2257c9")]), m)
        return over(body, gloss(m, 70, 0, 0.35), fill(edge_no_top(m), rgba("#16409c", 230)))

    def panel(self, w, h, kind):
        m = rrect(w, h, 7)
        body = masked(gradient(w, h, [(0, rgba("#6f9ff4", 238)), (0.18, rgba("#3f73df", 238)), (1, rgba("#2a59c6", 238))]), m)
        edge = fill(ring(m, rrect_inset(m)), rgba("#163f9e", 255))
        hl = fill(ring(rrect_inset(m), rrect_inset(rrect_inset(m))), rgba("#a9c8ff", 140))
        return over(body, hl, edge)

    def highlight(self, w, h):
        m = rrect(w, h, 4)
        body = masked(gradient(w, h, [(0, "#79d279"), (0.5, "#3faa3f"), (1, "#2a8a2a")]), m)
        return over(body, gloss(m, 110, 0, 0.45), fill(ring(m, rrect_inset(m)), rgba("#1c5e1c", 200)))

    def progress_bkg(self, w, h):
        m = rrect(w, h, 4)
        return over(masked(gradient(w, h, [(0, "#d9d9d9"), (1, "#ffffff")]), m), fill(ring(m, rrect_inset(m)), rgba("#6b7a99", 255)))

    def progress_bar(self, w, h):
        """XP's segmented green progress blocks."""
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        block = masked(gradient(8, h, [(0, "#bfffbf"), (0.4, "#33cc33"), (1, "#1b8f1b")]), Image.new("L", (8, h), 255))
        for x in range(3, w - 10, 10):
            img.paste(block, (x, 0))
        return img

    def nocover(self, s):
        m = rrect(s, s, 8)
        bg = masked(gradient(s, s, [(0, "#5b9bf0"), (1, "#1f4fc4")]), m)
        disc = ellipse(s, s, [s * 0.16, s * 0.16, s * 0.84, s * 0.84])
        disc_img = masked(radial(s, s, s * 0.4, s * 0.35, s * 0.5, [(0, "#ffffff"), (0.5, "#cfe3ff"), (1, "#7aa7e8")]), disc)
        hole = ellipse(s, s, [s * 0.44, s * 0.44, s * 0.56, s * 0.56])
        note = icon_note(int(s * 0.36), int(s * 0.36), "#2a8a2a")
        layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        layer.paste(note, (int(s * 0.55), int(s * 0.55)), note)
        return over(bg, gloss(m, 60, 0, 0.4), disc_img, fill(hole, "#2a59c6"), layer, fill(ring(m, rrect_inset(m)), "#163f9e"))

    def icons(self):
        return {
            "folder": icon_folder(19, 16, "#e0a830", "#f8d465", rgba("#9a6a10", 255), gloss_a=150),
            "music": icon_note(16, 16, "#ffffff", outline="#163f9e"),
            "star": icon_star(16, "#fff3a0", "#e8a317", rgba("#9a6a10", 255)),
            "blankstar": icon_star(16, "#c8d8f5", "#8aa6dc", rgba("#3a62b8", 230), gloss_a=60),
            "battery": icon_battery(30, 14, "#e8eef8", ("#9cf09c", "#2a9a2a"), rgba("#163f9e", 255)),
            "batterycharging": icon_battery(30, 14, "#e8eef8", ("#fff3a0", "#e8a317"), rgba("#163f9e", 255)),
            "batterylow": icon_battery(30, 14, "#e8eef8", ("#ff9a8a", "#d0301a"), rgba("#163f9e", 255), frac=0.2),
            "cpu": icon_cpu(16, ("#5f6b80", "#2d3546"), "#e8c060", "#cfe3ff"),
            "volume": icon_speaker(16, "#ffffff", "#cfe3ff"),
            "headphone": icon_headphone(16, "#ffffff"),
        }


# --- iPod 5th gen style -----------------------------------------------------
class ClickWheel(Theme):
    name = "ClickWheel"
    desc = "iPod video (5th gen) style: white screen, blue selection, black text"
    colors = {
        "TOOLBAR_TEXT": "#111418", "TOOLBAR_TEXT_SHADOW": (255, 255, 255, 120),
        "BUTTONBAR_TEXT": "#1d232b", "BUTTONBAR_TEXT_SHADOW": (0, 0, 0, 0),
        "BUTTONBAR_SELECTED_TEXT": "#ffffff", "BUTTONBAR_SELECTED_TEXT_SHADOW": (20, 60, 130, 200),
        "POPUP_TITLE_TEXT": "#1e5fc0", "POPUP_TITLE_TEXT_SHADOW": (0, 0, 0, 0),
        "POPUP_MESSAGE_TEXT": "#111418", "POPUP_MESSAGE_TEXT_SHADOW": (0, 0, 0, 0),
        "MENU_TEXT": "#111418", "MENU_TEXT_SHADOW": (0, 0, 0, 0),
        "MENU_SELECTED_TEXT": "#ffffff", "MENU_SELECTED_TEXT_SHADOW": (20, 60, 130, 200),
        "LABEL_TEXT": "#4b6584", "LABEL_TEXT_SHADOW": (0, 0, 0, 0),
        "TEXT": "#0b0d10", "TEXT_SHADOW": (0, 0, 0, 0),
        "HELP_TITLE_TEXT": "#1e5fc0", "HELP_TITLE_TEXT_SHADOW": (0, 0, 0, 0),
        "HELP_TEXT": "#111418", "HELP_TEXT_SHADOW": (0, 0, 0, 0),
    }

    def background(self, w, h):
        return over(gradient(w, h, [(0, "#ffffff"), (1, "#e3e8ee")]), noise_overlay(w, h, 12, 6))

    def toolbar(self, w, h, top):
        bar = gradient(w, h, [(0, "#fbfdff"), (0.5, "#dfe7f0"), (1, "#bccbdb")] if top else [(0, "#bccbdb"), (0.5, "#dfe7f0"), (1, "#fbfdff")])
        line = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        y = h - 1 if top else 0
        ImageDraw.Draw(line).line([(0, y), (w, y)], fill=rgba("#7d8ea3", 255))
        return over(bar, line)

    def tab(self, w, h, sel, i):
        m = rrect_hanging(w, h, 4)
        if sel:
            body = masked(gradient(w, h, [(0, "#8cc0f5"), (0.5, "#3d82e0"), (1, "#245fc0")]), m)
            return over(body, gloss(m, 90, 10, 0.5), fill(edge_no_top(m), rgba("#1b4f9e", 255)))
        body = masked(gradient(w, h, [(0, "#ffffff"), (1, "#d6dde6")]), m)
        return over(body, fill(edge_no_top(m), rgba("#9aa8b8", 255)))

    def panel(self, w, h, kind):
        m = rrect(w, h, 4)
        body = masked(gradient(w, h, [(0, rgba("#ffffff", 250)), (1, rgba("#f2f5f8", 250))]), m)
        return over(body, fill(ring(m, rrect_inset(m)), rgba("#a7b3c2", 255)))

    def highlight(self, w, h):
        m = Image.new("L", (w, h), 255)
        body = masked(gradient(w, h, [(0, "#78b2f2"), (0.5, "#3b7fdc"), (1, "#2a65c4")]), m)
        return over(body, gloss(m, 70, 0, 0.5))

    def progress_bkg(self, w, h):
        m = rrect(w, h, 2)
        return over(masked(gradient(w, h, [(0, "#c9d1da"), (1, "#f4f6f8")]), m), fill(ring(m, rrect_inset(m)), rgba("#8f9cab", 255)))

    def progress_bar(self, w, h):
        m2 = Image.new("L", (w, h), 0)
        m2.paste(Image.new("L", (w - 4, h), 255), (2, 0))
        body = masked(gradient(w, h, [(0, "#a8d0fb"), (0.5, "#3f86e3"), (1, "#2563c2")]), m2)
        return over(body, gloss(m2, 110, 0, 0.5))

    def nocover(self, s):
        m = rrect(s, s, 3)
        bg = masked(gradient(s, s, [(0, "#f3f5f8"), (1, "#d3dae3")]), m)
        note = icon_note(int(s * 0.6), int(s * 0.6), "#9aa8b8")
        layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        layer.paste(note, (int(s * 0.2), int(s * 0.2)), note)
        return over(bg, layer, fill(ring(m, rrect_inset(m)), "#a7b3c2"))

    def icons(self):
        return {
            "folder": icon_folder(19, 16, "#8fa3bb", "#c3d1e2", rgba("#5d6f86", 255)),
            "music": icon_note(16, 16, "#3b4a5c"),
            "star": icon_star(16, "#5b6878", "#2c3540", None, gloss_a=60),
            "blankstar": icon_star(16, "#e4e9ef", "#cdd5de", rgba("#9aa8b8", 255), gloss_a=0),
            "battery": icon_battery(30, 14, "#f4f6f8", ("#b6ef7a", "#4fae1c"), rgba("#6b7a8c", 255)),
            "batterycharging": icon_battery(30, 14, "#f4f6f8", ("#fff3a0", "#e8a317"), rgba("#6b7a8c", 255)),
            "batterylow": icon_battery(30, 14, "#f4f6f8", ("#ff9a8a", "#d0301a"), rgba("#6b7a8c", 255), frac=0.2),
            "cpu": icon_cpu(16, ("#8a97a8", "#5a6676"), "#5a6676", "#dfe7f0"),
            "volume": icon_speaker(16, "#2c3540", "#5b6878"),
            "headphone": icon_headphone(16, "#2c3540"),
        }


# --- Dark 2000s futuristic: black, dark purple, brushed steel ---------------
class Y2K(Theme):
    name = "Y2K Chrome"
    desc = "Dark 2000s future: black, deep purple and brushed steel"
    colors = {
        "TOOLBAR_TEXT": "#0e0c14", "TOOLBAR_TEXT_SHADOW": (255, 255, 255, 110),
        "BUTTONBAR_TEXT": "#13101c", "BUTTONBAR_TEXT_SHADOW": (255, 255, 255, 90),
        "BUTTONBAR_SELECTED_TEXT": "#ffffff", "BUTTONBAR_SELECTED_TEXT_SHADOW": (30, 0, 70, 255),
        "POPUP_TITLE_TEXT": "#c9a6ff", "POPUP_TITLE_TEXT_SHADOW": (0, 0, 0, 255),
        "POPUP_MESSAGE_TEXT": "#f4efff", "POPUP_MESSAGE_TEXT_SHADOW": (0, 0, 0, 255),
        "MENU_TEXT": "#efe9ff", "MENU_TEXT_SHADOW": (0, 0, 0, 255),
        "MENU_SELECTED_TEXT": "#ffffff", "MENU_SELECTED_TEXT_SHADOW": (30, 0, 70, 255),
        "LABEL_TEXT": "#b89cff", "LABEL_TEXT_SHADOW": (0, 0, 0, 255),
        "TEXT": "#f6f2ff", "TEXT_SHADOW": (0, 0, 0, 255),
        "HELP_TITLE_TEXT": "#c9a6ff", "HELP_TITLE_TEXT_SHADOW": (0, 0, 0, 255),
        "HELP_TEXT": "#f4efff", "HELP_TEXT_SHADOW": (0, 0, 0, 255),
    }
    P = "#8a4dff"

    def background(self, w, h):
        bg = gradient(w, h, [(0, "#05030a"), (0.55, "#14082a"), (1, "#2a0f52")], angle=70)
        glowc = radial(w, h, 400, 230, 300, [(0, rgba("#6a2bd9", 140)), (1, rgba("#000000", 0))])
        streaks = mask_from(w, h, lambda d, s: [d.line([((-50 + i * 70) * s, 272 * s), ((150 + i * 70) * s, 0)], fill=255, width=int(s * (1 if i % 3 else 2))) for i in range(10)])
        st = fill(streaks, rgba("#b48cff", 26))
        grid = mask_from(w, h, lambda d, s: [d.line([(0, y * s), (w * s, y * s)], fill=255, width=s) for y in range(150, 272, 12)] +
                         [d.line([((240 + (x - 240) * 0.3) * s, 150 * s), (x * s, 272 * s)], fill=255, width=s) for x in range(-480, 960, 48)])
        gr = fill(grid, rgba("#7a3dff", 30))
        scan = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(scan)
        for y in range(0, h, 3):
            d.line([(0, y), (w, y)], fill=(0, 0, 0, 40))
        return over(bg, glowc, gr, st, scan)

    def steel(self, w, h, vertical=False):
        return brushed(w, h, "#dcdfe6", "#a2a6b0", streak=0.10, vertical=vertical)

    def toolbar(self, w, h, top):
        bar = self.steel(w, h)
        hi = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(hi)
        d.line([(0, 0), (w, 0)], fill=rgba("#ffffff", 200))
        d.line([(0, h - 1), (w, h - 1)], fill=rgba("#2a2633", 255))
        purple = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(purple).line([(0, h - 2 if top else 1), (w, h - 2 if top else 1)], fill=rgba(self.P, 200))
        return over(bar, hi, purple)

    def tab(self, w, h, sel, i):
        m = poly(w, h, [(1, 0), (w - 1, 0), (w - 6, h - 1), (6, h - 1)])
        if sel:
            body = masked(gradient(w, h, [(0, "#c49bff"), (0.45, "#8a4dff"), (1, "#3d1494")]), m)
            return over(body, gloss(m, 130, 10, 0.45), fill(edge_no_top(m), rgba("#e7d8ff", 220)))
        body = masked(self.steel(w, h), m)
        return over(body, fill(edge_no_top(m), rgba("#3a3644", 255)))

    def panel(self, w, h, kind):
        m = rrect(w, h, 3)
        frame = masked(self.steel(w, h), m)
        inner_m = rrect(w, h, 2, inset=2)
        glass = masked(gradient(w, h, [(0, rgba("#1d0f38", 238)), (1, rgba("#08040f", 240))]), inner_m)
        line = fill(ring(inner_m, rrect_inset(inner_m)), rgba(self.P, 200))
        return over(frame, glass, glow(ring(inner_m, rrect_inset(inner_m)), rgba(self.P, 90), 2), line, gloss(inner_m, 26, 0, 0.2))

    def highlight(self, w, h):
        m = Image.new("L", (w, h), 255)
        body = masked(gradient(w, h, [(0, "#a874ff"), (0.5, "#6a2bd9"), (1, "#3a1191")]), m)
        return over(body, gloss(m, 100, 0, 0.5))

    def progress_bkg(self, w, h):
        m = rrect(w, h, 2)
        return over(masked(self.steel(w, h), m), fill(rrect(w, h, 2, inset=2), "#07040d"))

    def progress_bar(self, w, h):
        m2 = Image.new("L", (w, h), 0)
        m2.paste(Image.new("L", (w - 4, h - 2), 255), (2, 1))
        body = masked(gradient(w, h, [(0, "#e2ccff"), (0.5, "#9a5cff"), (1, "#5a1fc9")]), m2)
        return over(glow(m2, rgba(self.P, 160), 1.5), body)

    def nocover(self, s):
        m = rrect(s, s, 4)
        frame = masked(self.steel(s, s), m)
        inner = rrect(s, s, 3, inset=4)
        bg = masked(radial(s, s, s * 0.5, s * 0.5, s * 0.7, [(0, "#2a1452"), (1, "#05030a")]), inner)
        disc = ellipse(s, s, [s * 0.18, s * 0.18, s * 0.82, s * 0.82])
        disc_img = masked(self.steel(s, s, vertical=True), disc)
        hole = ellipse(s, s, [s * 0.42, s * 0.42, s * 0.58, s * 0.58])
        return over(frame, bg, glow(disc, rgba(self.P, 160), 4), disc_img, gloss(disc, 110, 0, 0.5), fill(hole, "#2a1452"), fill(ring(hole, rrect_inset(hole)), rgba(self.P, 255)))

    def icons(self):
        P = self.P
        chrome = lambda w, h: brushed(w, h, "#f0f2f7", "#8b8f9a", streak=0.15)
        fm = poly(19, 16, [(1, 2), (8, 2), (10, 4.5), (17, 4.5), (17, 14), (1, 14)])
        folder = over(masked(chrome(19, 16), fm), masked(gradient(19, 16, [(0, rgba(P, 0)), (1, rgba(P, 110))]), fm), fill(ring(fm, rrect_inset(fm)), "#2a2633"))
        return {
            "folder": folder,
            "music": icon_note(16, 16, "#dcc8ff", outline="#14081f"),
            "star": icon_star(16, "#e2ccff", "#6a2bd9", rgba("#1a0b33", 255)),
            "blankstar": icon_star(16, "#3a3644", "#1b1823", rgba("#9a96a6", 220), gloss_a=40),
            "battery": icon_battery(30, 14, "#c7cad3", ("#c49bff", "#5a1fc9"), rgba("#2a2633", 255)),
            "batterycharging": icon_battery(30, 14, "#c7cad3", ("#fff3a0", "#e8a317"), rgba("#2a2633", 255)),
            "batterylow": icon_battery(30, 14, "#c7cad3", ("#ff9a8a", "#d0301a"), rgba("#2a2633", 255), frac=0.2),
            "cpu": icon_cpu(16, ("#3a3644", "#14121a"), "#4a4654", P),
            "volume": icon_speaker(16, "#14121a", "#4a2a8a"),
            "headphone": icon_headphone(16, "#14121a"),
        }


# --- Gran Turismo 3 style (from title screen, GT Mode map and dealer refs) -
def road_map(w, h, color, seed=3, n=14):
    """Faint tangle of curving roads, like the GT Mode city map."""
    r = np.random.default_rng(seed)
    def draw(d, s):
        for _ in range(n):
            pts = []
            x, y = r.uniform(-40, w + 40), r.uniform(-40, h + 40)
            ang = r.uniform(0, 2 * math.pi)
            for _ in range(10):
                pts.append((x * s, y * s))
                ang += r.uniform(-0.5, 0.5)
                step = r.uniform(25, 60)
                x += math.cos(ang) * step
                y += math.sin(ang) * step
            d.line(pts, fill=255, width=int(s * r.choice([1, 1, 2])), joint="curve")
    return fill(mask_from(w, h, draw), color)


class PitLane3(Theme):
    name = "Pit Lane 3"
    desc = "Gran Turismo 3 style: red title-screen streaks, dark map strips, orange buttons"
    font = "flash0:/font/ltn6.pgf"  # bold italic
    O = "#f7941d"
    colors = {
        "TOOLBAR_TEXT": "#ffffff", "TOOLBAR_TEXT_SHADOW": (0, 0, 0, 255),
        "BUTTONBAR_TEXT": "#efe6d0", "BUTTONBAR_TEXT_SHADOW": (0, 0, 0, 255),
        "BUTTONBAR_SELECTED_TEXT": "#1b1006", "BUTTONBAR_SELECTED_TEXT_SHADOW": (0, 0, 0, 0),
        "POPUP_TITLE_TEXT": "#ffc93c", "POPUP_TITLE_TEXT_SHADOW": (0, 0, 0, 255),
        "POPUP_MESSAGE_TEXT": "#ffffff", "POPUP_MESSAGE_TEXT_SHADOW": (0, 0, 0, 255),
        "MENU_TEXT": "#ffffff", "MENU_TEXT_SHADOW": (0, 0, 0, 255),
        "MENU_SELECTED_TEXT": "#1b1000", "MENU_SELECTED_TEXT_SHADOW": (0, 0, 0, 0),
        "LABEL_TEXT": "#f9a23a", "LABEL_TEXT_SHADOW": (0, 0, 0, 255),
        "TEXT": "#ffffff", "TEXT_SHADOW": (0, 0, 0, 255),
        "HELP_TITLE_TEXT": "#ffc93c", "HELP_TITLE_TEXT_SHADOW": (0, 0, 0, 255),
        "HELP_TEXT": "#ffffff", "HELP_TEXT_SHADOW": (0, 0, 0, 255),
    }

    def background(self, w, h):
        base = gradient(w, h, [(0, "#b8161a"), (0.45, "#d9262a"), (0.75, "#e0382c"), (1, "#a81216")], angle=20)
        # horizontal motion blur streaks, hotter on the right like the title screen
        r = np.random.default_rng(11)
        streaks = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(streaks)
        for _ in range(70):
            y = r.uniform(0, h)
            x0 = r.uniform(-100, w)
            ln = r.uniform(60, 260)
            hot = min(1.0, max(0.0, (x0 + ln / 2) / w))
            c = (255, int(120 + 110 * hot * r.uniform(0.6, 1)), int(40 + 60 * r.uniform(0, 1) * hot), int(30 + 90 * hot * r.uniform(0.3, 1)))
            d.line([(x0, y), (x0 + ln, y)], fill=c, width=int(r.choice([1, 1, 2, 3])))
        for _ in range(30):
            y = r.uniform(0, h)
            x0 = r.uniform(-100, w)
            d.line([(x0, y), (x0 + r.uniform(80, 300), y)], fill=(90, 0, 4, 60), width=int(r.choice([2, 4, 6])))
        streaks = streaks.filter(ImageFilter.GaussianBlur(1.2))
        streaks = streaks.resize((w // 4, h), Image.BILINEAR).resize((w, h), Image.BILINEAR)  # smear sideways
        glow_r = radial(w, h, w * 0.9, h * 0.42, w * 0.55, [(0, rgba("#ffb347", 120)), (1, rgba("#ff6a00", 0))])
        vign = radial(w, h, w / 2, h / 2, w * 0.75, [(0, rgba("#000000", 0)), (0.7, rgba("#000000", 0)), (1, rgba("#3a0004", 140))])
        return over(base, glow_r, streaks, vign, noise_overlay(w, h, 18, 8))

    def toolbar(self, w, h, top):
        bar = gradient(w, h, [(0, rgba("#262626", 245)), (1, rgba("#050505", 245))] if top else [(0, rgba("#050505", 245)), (1, rgba("#262626", 245))])
        line = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        y = h - 2 if top else 0
        ImageDraw.Draw(line).rectangle([0, y, w, y + 1], fill=rgba(self.O, 255))
        return over(bar, line)

    def tab(self, w, h, sel, i):
        m = rrect_hanging(w, h, 7)
        if sel:  # glossy orange BUY/SPEC button
            body = masked(radial(w, h, w * 0.5, h * 0.2, w * 0.6, [(0, "#ffb15c"), (0.5, "#f47a22"), (1, "#c9440e")]), m)
            return over(body, gloss(m, 120, 10, 0.45), fill(edge_no_top(m), rgba("#2a1205", 255)))
        body = masked(gradient(w, h, [(0, rgba("#2a2a2a", 240)), (1, rgba("#0c0c0c", 240))]), m)
        return over(body, fill(edge_no_top(m), rgba("#a8936a", 220)))

    def panel(self, w, h, kind):
        m = rrect(w, h, 3)
        body = masked(gradient(w, h, [(0, rgba("#161412", 222)), (1, rgba("#050505", 230))]), m)
        roads = masked(road_map(w, h, rgba("#8a6a45", 34), seed=w * 7 + h), m)
        top = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(top).rectangle([3, 0, w - 4, 1], fill=rgba(self.O, 255))
        edge = fill(ring(m, rrect_inset(m)), rgba("#5a4a32", 200))
        return over(body, roads, edge, top)

    def highlight(self, w, h):
        """The title screen's yellow-to-orange selected item."""
        m = rrect(w, h, 3)
        body = masked(gradient(w, h, [(0, "#fff07a"), (0.45, "#ffc21a"), (1, "#ff8c00")]), m)
        return over(body, gloss(m, 90, 0, 0.4), fill(ring(m, rrect_inset(m)), rgba("#5a2a00", 230)))

    def progress_bkg(self, w, h):
        m = rrect(w, h, 3)
        return over(fill(m, rgba("#050505", 235)), fill(ring(m, rrect_inset(m)), rgba("#a8936a", 220)))

    def progress_bar(self, w, h):
        m2 = Image.new("L", (w, h), 0)
        m2.paste(rrect(w - 4, h, 2), (2, 0))
        body = masked(gradient(w, h, [(0, "#ffe27a"), (0.5, "#f7941d"), (1, "#c9440e")]), m2)
        return over(body, gloss(m2, 110, 0, 0.5))

    def nocover(self, s):
        """Dealer showroom: navy spotlight over a light reflective floor."""
        m = rrect(s, s, 4)
        sky = radial(s, s, s * 0.5, -s * 0.1, s * 0.9, [(0, "#3a5694"), (0.5, "#16244c"), (1, "#05070f")])
        floor = gradient(s, s, [(0, rgba("#ffffff", 0)), (0.55, rgba("#ffffff", 0)), (0.62, rgba("#8f98ab", 255)), (1, rgba("#eef1f6", 255))])
        btn = ellipse(s, s, [s * 0.3, s * 0.3, s * 0.7, s * 0.7])
        btn_img = masked(radial(s, s, s * 0.46, s * 0.4, s * 0.25, [(0, "#ffb15c"), (0.6, "#f47a22"), (1, "#c9440e")]), btn)
        note = icon_note(int(s * 0.24), int(s * 0.24), "#ffffff", outline="#2a1205")
        layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        layer.paste(note, (int(s * 0.37), int(s * 0.37)), note)
        return over(masked(sky, m), masked(floor, m), shift(glow(btn, rgba("#000000", 120), 3), 0, 3), btn_img,
                    gloss(btn, 120, 0, 0.45), fill(ring(btn, rrect_inset(rrect_inset(btn))), "#2a1205"), layer,
                    fill(ring(m, rrect_inset(m)), "#a8936a"))

    def icons(self):
        O = self.O
        coin = ellipse(16, 16, [0.5, 0.5, 15.5, 15.5])
        cpu = over(masked(radial(16, 16, 6, 5, 10, [(0, "#ffc27a"), (1, "#e2650f")]), coin),
                   fill(ring(coin, rrect_inset(coin)), "#2a1205"), fill(rrect(16, 16, 1, inset=5), "#2a1205"))
        return {
            "folder": icon_folder(19, 16, "#a8936a", "#e3d6b0", rgba("#3a2e1c", 255), gloss_a=110),
            "music": icon_note(16, 16, "#ffb347", outline="#140a02"),
            "star": icon_star(16, "#fff07a", "#ff8c00", rgba("#3a1a00", 255)),
            "blankstar": icon_star(16, "#3a3530", "#1a1714", rgba("#a8936a", 220), gloss_a=30),
            "battery": icon_battery(30, 14, "#e3d6b0", ("#ffe27a", "#f7941d"), rgba("#140a02", 255)),
            "batterycharging": icon_battery(30, 14, "#e3d6b0", ("#b8f07a", "#4aa615"), rgba("#140a02", 255)),
            "batterylow": icon_battery(30, 14, "#e3d6b0", ("#ff9a8a", "#d0301a"), rgba("#140a02", 255), frac=0.2),
            "cpu": cpu,
            "volume": icon_speaker(16, "#ffffff", O),
            "headphone": icon_headphone(16, "#ffffff"),
        }


# --- Gran Turismo 2 style (from city map and dealer refs) -------------------
def street_grid(w, h, color, water=None, seed=5, highway=None):
    """Amber city streets on black, with slate water, like GT2's maps."""
    r = np.random.default_rng(seed)
    layers = [Image.new("RGBA", (w, h), (0, 0, 0, 0))]
    if water:
        coast = [(w * 0.38, h + 5), (w * 0.45, h * 0.86), (w * 0.6, h * 0.8), (w * 0.72, h * 0.66), (w * 0.86, h * 0.6), (w + 5, h * 0.52), (w + 5, h + 5)]
        wm = mask_from(w, h, lambda d, s: d.polygon([(x * s, y * s) for x, y in coast], fill=255))
        river = mask_from(w, h, lambda d, s: d.line([(x * s, y * s) for x, y in
                          [(-10, h * 0.42), (w * 0.2, h * 0.46), (w * 0.4, h * 0.4), (w * 0.62, h * 0.47), (w * 0.82, h * 0.43), (w + 10, h * 0.47)]], fill=255, width=int(5 * s), joint="curve"))
        layers += [blur(fill(ImageChops.lighter(wm, river), water), 0.6)]

    def grid(d, s):
        ang = math.radians(6)
        x = -60.0
        while x < w + 60:
            d.line([(x * s, -10 * s), ((x + h * math.tan(ang)) * s, (h + 10) * s)], fill=255, width=s)
            x += r.uniform(8, 13)
        y = -30.0
        while y < h + 30:
            d.line([(-10 * s, y * s), ((w + 10) * s, (y + w * math.tan(ang * 0.5)) * s)], fill=255, width=s)
            y += r.uniform(7, 12)

    def highways(d, s):
        for _ in range(5):
            pts, x, y, a = [], r.uniform(0, w), r.uniform(0, h), r.uniform(0, 2 * math.pi)
            for _ in range(14):
                pts.append((x * s, y * s))
                a += r.uniform(-0.3, 0.3)
                x += math.cos(a) * 35
                y += math.sin(a) * 35
            d.line(pts, fill=255, width=int(2 * s), joint="curve")
    streets = fill(mask_from(w, h, grid), color)
    if water:  # streets stop at the water
        streets = masked(streets, ImageChops.invert(layers[-1].getchannel("A").point(lambda v: 255 if v > 40 else 0)))
    layers += [streets]
    if highway:
        layers += [fill(mask_from(w, h, highways), highway)]
    return over(*layers)


def road_sign(s, bg, edge, glyph):
    """Orange rounded-square map sign with a black pictogram mask."""
    m = rrect(s, s, 3, inset=0)
    img = over(masked(gradient(s, s, [(0, rgba(bg[0])), (1, rgba(bg[1]))]), m), fill(ring(m, rrect_inset(m)), edge))
    return over(img, fill(glyph, "#000000"))


class PitLane2(Theme):
    name = "Pit Lane 2"
    desc = "Gran Turismo 2 style: black, amber city map, orange signs and buttons"
    font = "flash0:/font/ltn4.pgf"  # bold upright
    O = "#f5a01a"
    colors = {
        "TOOLBAR_TEXT": "#ffffff", "TOOLBAR_TEXT_SHADOW": (0, 0, 0, 255),
        "BUTTONBAR_TEXT": "#ffffff", "BUTTONBAR_TEXT_SHADOW": (0, 0, 0, 255),
        "BUTTONBAR_SELECTED_TEXT": "#120800", "BUTTONBAR_SELECTED_TEXT_SHADOW": (0, 0, 0, 0),
        "POPUP_TITLE_TEXT": "#f5a01a", "POPUP_TITLE_TEXT_SHADOW": (0, 0, 0, 255),
        "POPUP_MESSAGE_TEXT": "#ffffff", "POPUP_MESSAGE_TEXT_SHADOW": (0, 0, 0, 255),
        "MENU_TEXT": "#ffffff", "MENU_TEXT_SHADOW": (0, 0, 0, 255),
        "MENU_SELECTED_TEXT": "#120800", "MENU_SELECTED_TEXT_SHADOW": (0, 0, 0, 0),
        "LABEL_TEXT": "#f5a01a", "LABEL_TEXT_SHADOW": (0, 0, 0, 255),
        "TEXT": "#ffffff", "TEXT_SHADOW": (0, 0, 0, 255),
        "HELP_TITLE_TEXT": "#f5a01a", "HELP_TITLE_TEXT_SHADOW": (0, 0, 0, 255),
        "HELP_TEXT": "#ffffff", "HELP_TEXT_SHADOW": (0, 0, 0, 255),
    }

    def background(self, w, h):
        base = solid(w, h, "#000000")
        streets = street_grid(w, h, rgba("#d9891a", 70), water=rgba("#3e4759", 255), highway=rgba("#f5a01a", 130))
        frame = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(frame).rectangle([3, 3, w - 4, h - 4], outline=rgba(self.O, 160), width=1)
        return over(base, streets, frame)

    def toolbar(self, w, h, top):
        bar = solid(w, h, "#000000")
        line = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        y = h - 2 if top else 0
        ImageDraw.Draw(line).rectangle([0, y, w, y + 1], fill=rgba(self.O, 255))
        return over(bar, line)

    def tab(self, w, h, sel, i):
        """Dealer tab strip: grey pills, the selected one orange."""
        m = rrect_hanging(w, h, 8, side_inset=2)
        if sel:
            body = masked(gradient(w, h, [(0, "#ffb238"), (1, "#e8800a")]), m)
            return over(body, fill(edge_no_top(m), rgba("#000000", 255)))
        body = masked(gradient(w, h, [(0, "#6a6a6a"), (1, "#3c3c3c")]), m)
        return over(body, fill(edge_no_top(m), rgba("#000000", 255)))

    def panel(self, w, h, kind):
        """Black box with an orange border, like the map frame."""
        m = rrect(w, h, 4)
        body = fill(m, rgba("#000000", 230))
        return over(body, fill(outline(w, h, 4, 2), self.O))

    def highlight(self, w, h):
        """Orange 'SOUTH CITY' box."""
        m = rrect(w, h, 3)
        return over(fill(m, self.O), fill(outline(w, h, 3, 1), "#000000"))

    def progress_bkg(self, w, h):
        m = rrect(w, h, 4)
        return over(fill(m, "#000000"), fill(outline(w, h, 4, 1), self.O))

    def progress_bar(self, w, h):
        m2 = Image.new("L", (w, h), 0)
        m2.paste(rrect(w - 4, h, 2), (2, 0))
        return fill(m2, "#ffb238")

    def nocover(self, s):
        """Black square with the orange ring 'COMPRA' button."""
        m = rrect(s, s, 4)
        bg = over(fill(m, "#000000"), masked(street_grid(s, s, rgba("#d9891a", 60), seed=9), m))
        ringm = ring(ellipse(s, s, [s * 0.2, s * 0.2, s * 0.8, s * 0.8]), ellipse(s, s, [s * 0.29, s * 0.29, s * 0.71, s * 0.71]))
        inner = ellipse(s, s, [s * 0.29, s * 0.29, s * 0.71, s * 0.71])
        note = icon_note(int(s * 0.3), int(s * 0.3), "#ffffff")
        layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        layer.paste(note, (int(s * 0.35), int(s * 0.35)), note)
        return over(bg, fill(inner, "#000000"), fill(ringm, self.O), layer, fill(outline(s, s, 4, 2), self.O))

    def icons(self):
        O = self.O
        sign = ("#ffb238", "#e8800a")
        folder_glyph = mask_from(16, 16, lambda d, k: (d.polygon([(3 * k, 5 * k), (6.5 * k, 5 * k), (7.5 * k, 6.2 * k), (13 * k, 6.2 * k), (13 * k, 12 * k), (3 * k, 12 * k)], fill=255)))
        note_glyph = mask_from(16, 16, lambda d, k: (d.ellipse([3.5 * k, 9 * k, 8.5 * k, 13 * k], fill=255), d.rectangle([7 * k, 3 * k, 8.6 * k, 11 * k], fill=255),
                                                      d.polygon([(7 * k, 3 * k), (12.5 * k, 4.8 * k), (12.5 * k, 7.2 * k), (8.6 * k, 5.6 * k)], fill=255)))
        folder = Image.new("RGBA", (19, 16), (0, 0, 0, 0))
        fs = road_sign(16, sign, "#000000", folder_glyph)
        folder.paste(fs, (1, 0), fs)
        coin = ellipse(16, 16, [0.5, 0.5, 15.5, 15.5])
        cpu = over(fill(coin, O), fill(ring(coin, rrect_inset(coin)), "#000000"), fill(rrect(16, 16, 1, inset=5), "#000000"))
        dot = lambda c: fill(poly(16, 16, star_points(8, 8.6, 8, 3.9)), c)
        return {
            "folder": folder,
            "music": road_sign(16, sign, "#000000", note_glyph),
            "star": over(dot("#000000"), fill(poly(16, 16, star_points(8, 8.6, 7, 3.3)), "#ffb238")),
            "blankstar": over(dot("#000000"), fill(poly(16, 16, star_points(8, 8.6, 7, 3.3)), "#4a4a4a")),
            "battery": icon_battery(30, 14, "#ffffff", ("#ffb238", "#e8800a"), rgba("#000000", 255)),
            "batterycharging": icon_battery(30, 14, "#ffffff", ("#b8f07a", "#4aa615"), rgba("#000000", 255)),
            "batterylow": icon_battery(30, 14, "#ffffff", ("#ff9a8a", "#d0301a"), rgba("#000000", 255), frac=0.2),
            "cpu": cpu,
            "volume": icon_speaker(16, "#ffffff", O),
            "headphone": icon_headphone(16, "#ffffff"),
        }


THEMES = {"duke": Duke, "luna": Luna, "clickwheel": ClickWheel, "y2k": Y2K, "pitlane3": PitLane3, "pitlane2": PitLane2}


def main():
    out = sys.argv[1]
    names = sys.argv[2:] or list(THEMES)
    for n in names:
        t = THEMES[n]()
        dest = os.path.join(out, t.name)
        t.build(dest)
        print("wrote", dest)


if __name__ == "__main__":
    main()
