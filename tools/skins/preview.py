#!/usr/bin/env python3
"""Render approximate previews of LightMP3 screens from a skin folder.

Mirrors the drawing code in src_v2/gui (drawToolbars, drawButtonBar, drawMenu,
drawFileInfo/drawPlayer, drawMLinfo) closely enough to judge a skin's layout
and colours without a PSP. Text is drawn with Liberation Sans in place of the
PSP's ltn*.pgf fonts, so expect small differences in glyph shapes and widths.

Usage: preview.py SKIN_DIR OUT_PREFIX [--scale 2]
Writes OUT_PREFIX-player.png, -browser.png, -library.png, -artists.png and
OUT_PREFIX-sheet.png (all four on one image).
"""
import argparse
import os
import re

from PIL import Image, ImageDraw, ImageFont

from oftfont import OftFont

W, H = 480, 272
# OSLib's charHeight for intraFont is the font's texYSize, which doesn't change
# with FONT_NORMAL_SIZE. Measured from photos of a PSP-3000: about 17 px.
CHAR_HEIGHT = 17
# Liberation Sans at this many px per 1.0 of intraFont size matches the PSP
# font's widths (measured from the same photos).
PX_PER_SIZE = 22.0

FONT_DIR = "/usr/share/fonts/truetype/liberation"
PGF_TO_TTF = {  # flash0:/font/ltnN.pgf -> closest Liberation face
    0: "LiberationSans-Regular.ttf", 1: "LiberationSerif-Regular.ttf",
    2: "LiberationSans-Italic.ttf", 3: "LiberationSerif-Italic.ttf",
    4: "LiberationSans-Bold.ttf", 5: "LiberationSerif-Bold.ttf",
    6: "LiberationSans-BoldItalic.ttf", 7: "LiberationSerif-BoldItalic.ttf",
}

HERE = os.path.dirname(os.path.abspath(__file__))
LANG_FILE = os.path.join(HERE, "..", "..", "src_v2", "languages", "English", "lang.txt")


def load_lang():
    strings = {}
    with open(LANG_FILE, encoding="latin-1") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                strings[k] = v
    return strings


class Skin:
    def __init__(self, path):
        self.path = path
        self.cfg = {}
        with open(os.path.join(path, "skin.cfg"), encoding="latin-1") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                self.cfg[k.strip()] = v.split("#")[0].strip()  # allow trailing comments
        img_dir = os.path.join(path, "images")
        if "STR_IMAGE_PATH" in self.cfg:
            img_dir = os.path.join(path, "..", self.cfg["STR_IMAGE_PATH"], "images")
        self.images = {}
        for name in os.listdir(img_dir):
            if name.endswith(".png"):
                self.images[name[:-4]] = Image.open(os.path.join(img_dir, name)).convert("RGBA")
        # Like common.c: folder/music icons fall back to the default skin's.
        for name in ("folder", "music"):
            if name not in self.images:
                self.images[name] = Image.open(os.path.join(path, "..", "default", "images", name + ".png")).convert("RGBA")
        # A skin's own bitmap font (.oft) is drawn exactly like OSLib does it.
        self.oft = None
        self.char_height = CHAR_HEIGHT
        font_name = self.cfg.get("STR_FONT_NORMAL_NAME", "")
        if font_name.lower().endswith(".oft"):
            self.oft = OftFont(font_name.replace("$skinimage", img_dir))
            self.char_height = self.oft.charHeight
        size = int(self.cfg.get("FONT_NORMAL_SIZE", "50")) / 100.0
        m = re.search(r"ltn(\d+)\.pgf", font_name)
        face = PGF_TO_TTF.get(int(m.group(1)) % 8 if m else 0)
        self.font = ImageFont.truetype(os.path.join(FONT_DIR, face), max(6.0, size * PX_PER_SIZE))

    def pos(self, key):
        x, y = self.cfg[key].split(",")[:2]
        return int(x), int(y)

    def param(self, key, default=0):
        try:
            return int(self.cfg.get(key, default))
        except ValueError:
            return default

    def color(self, key):
        default = "0,0,0,0" if key.endswith("_SHADOW") else "255,255,255,255"
        parts = [int(p) for p in self.cfg.get(key, default).split(",")]
        return tuple(parts[:4])


class Screen:
    def __init__(self, skin):
        self.skin = skin
        self.img = Image.new("RGBA", (W, H), (0, 0, 0, 255))

    def image(self, name, x, y, width=None, height=None, crop_width=None):
        im = self.skin.images[name]
        if crop_width is not None:
            im = im.crop((0, 0, max(0, min(crop_width, im.width)), im.height))
        if width and height and (width, height) != im.size:
            im = im.resize((width, height), Image.LANCZOS)
        if im.width and im.height:
            self.img.alpha_composite(im, (x, y)) if 0 <= x and 0 <= y and x + im.width <= W and y + im.height <= H \
                else self._paste_clipped(im, x, y)

    def _paste_clipped(self, im, x, y):
        # copy (no mask) so semi-transparent pixels keep their alpha, then blend once like the GU does
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        layer.paste(im, (x, y))
        self.img.alpha_composite(layer)

    def width(self, s):
        if self.skin.oft:
            return self.skin.oft.width(s)
        return self.skin.font.getlength(s)

    def text(self, x, y, s, color_key, max_width=None):
        """oslDrawString: intraFont baseline at y + charHeight/2 + 1; .oft cell top at y."""
        if x < -100 or y < -100:
            return
        color = self.skin.color(color_key)
        if self.skin.oft:
            self.skin.oft.draw(self.img, x, y, s, color, max_width)
            return
        shadow = self.skin.color(color_key + "_SHADOW")
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        base = y + CHAR_HEIGHT // 2 + 1
        if max_width is not None:
            while s and self.width(s) > max_width:
                s = s[:-1]
        if shadow[3]:
            d.text((x + 1, base + 1), s, font=self.skin.font, fill=shadow, anchor="ls")
        d.text((x, base), s, font=self.skin.font, fill=color, anchor="ls")
        self.img.alpha_composite(layer)

    # -- common parts -------------------------------------------------------
    def common(self):
        sk = self.skin
        self.image("bkg_default", 0, 0)
        self.image("toptoolbar", *sk.pos("POS_TOOLBAR_1"))
        self.image("bottomtoolbar", *sk.pos("POS_TOOLBAR_2"))
        self.text(*sk.pos("POS_APP_NAME_TEXT"), "LightMP3 v. 2.0.0RC5 by Sakya", "RGBA_TOOLBAR_TEXT")
        self.image("battery", *sk.pos("POS_BATTERY_ICON"))
        self.text(*sk.pos("POS_BATTERY_TEXT"), "93% - 06:16", "RGBA_TOOLBAR_TEXT")
        self.image("volume", *sk.pos("POS_VOLUME_ICON"))
        self.text(*sk.pos("POS_VOLUME_TEXT"), "63%", "RGBA_TOOLBAR_TEXT")
        self.image("headphone", *sk.pos("POS_HEADPHONES_ICON"))
        self.image("cpu", *sk.pos("POS_CPU_ICON"))
        self.text(*sk.pos("POS_CPU_TEXT"), "333 / 166", "RGBA_TOOLBAR_TEXT")
        self.text(*sk.pos("POS_FREE_MEMORY_LABEL"), LANG["FREE_MEMORY"], "RGBA_TOOLBAR_TEXT")
        self.text(*sk.pos("POS_FREE_MEMORY_TEXT"), "541 kb", "RGBA_TOOLBAR_TEXT")
        self.text(*sk.pos("POS_CLOCK_TEXT"), "31/10/2026 05:02", "RGBA_TOOLBAR_TEXT")

    def button_bar(self, selected):
        sk = self.skin
        for i in range(5):
            x, y = sk.pos("POS_BUTTON_%d" % (i + 1))
            label = LANG["BUTTON_%d" % (i + 1)]
            sx = int(x + (sk.images["button%d" % (i + 1)].width - self.width(label)) / 2.0)
            if i == selected:
                self.image("buttonsel%d" % (i + 1), x, y)
                self.text(sx, y, label, "RGBA_BUTTONBAR_SELECTED_TEXT")
            else:
                self.image("button%d" % (i + 1), x, y)
                self.text(sx, y, label, "RGBA_BUTTONBAR_TEXT")

    def menu(self, bkg, x, y, items, selected, align="left", icons=None):
        """drawMenu. items: list of text; icons: list of image names or None."""
        sk = self.skin
        interline = sk.param("MENU_INTERLINE")
        bg = sk.images[bkg]
        width, height = bg.size
        row = sk.char_height + interline
        visible = height // row
        start_y = int(y + (height - visible * row) / 2.0)
        self.image(bkg, x, y)
        for n, label in enumerate(items[:visible]):
            ry = start_y + row * n
            key = "RGBA_MENU_TEXT"
            if n == selected:
                hl = sk.images["menuhighlight"].resize((width, sk.images["menuhighlight"].height))
                self._paste_clipped(hl, x, ry)
                key = "RGBA_MENU_SELECTED_TEXT"
            icon = icons[n] if icons else None
            icon_w = sk.images[icon].width if icon else 0
            if align == "left":
                tx, ix = x + icon_w + 4, x + 4
            else:
                tx = int(x + (width - (self.width(label) + icon_w)) / 2)
                ix = tx - icon_w
            if icon:
                self.image(icon, ix, ry)
            self.text(tx, ry, label, key, max_width=width - (tx - x) - 4)

    def rating(self, x, y, value):
        star = self.skin.images["star"]
        for i in range(5):
            self.image("star" if i < value else "blankstar", x + star.width * i, y)


def cover_placeholder(size):
    """A neutral, made-up 'album cover' so cover placement shows in previews."""
    im = Image.new("RGBA", (size, size))
    d = ImageDraw.Draw(im)
    for yy in range(size):
        t = yy / max(1, size - 1)
        d.line([(0, yy), (size, yy)], fill=(int(230 - 120 * t), int(90 + 60 * t), int(60 + 150 * t), 255))
    d.ellipse([size * 0.18, size * 0.18, size * 0.82, size * 0.82], outline=(255, 255, 255, 200), width=max(2, size // 30))
    d.ellipse([size * 0.42, size * 0.42, size * 0.58, size * 0.58], fill=(255, 255, 255, 220))
    return im


def render_player(skin):
    s = Screen(skin)
    sk = skin
    s.common()
    s.image("fileinfobkg", *sk.pos("POS_FILE_INFO_BKG"))
    for key, label in [("TITLE", "TITLE"), ("ARTIST", "ARTIST"), ("ALBUM", "ALBUM"), ("GENRE", "GENRE"),
                       ("RATING", "RATING"), ("YEAR", "YEAR"), ("PLAYED", "PLAYED"), ("TIME", "TIME"),
                       ("TRACK", "TRACK")]:
        s.text(*sk.pos("POS_%s_LABEL" % key), LANG[label], "RGBA_LABEL_TEXT")
    tx, ty = sk.pos("POS_TITLE_VALUE")
    s.text(tx, ty, "Antibiotics (Extended Club Mix)", "RGBA_TEXT", max_width=sk.param("TITLE_VALUE_WIDTH") or None)
    s.text(*sk.pos("POS_ARTIST_VALUE"), "Digitalism", "RGBA_TEXT")
    s.text(*sk.pos("POS_ALBUM_VALUE"), "I Love You, Dude", "RGBA_TEXT")
    s.text(*sk.pos("POS_GENRE_VALUE"), "Electro", "RGBA_TEXT")
    s.text(*sk.pos("POS_YEAR_VALUE"), "2011", "RGBA_TEXT")
    s.text(*sk.pos("POS_PLAYED_VALUE"), "3", "RGBA_TEXT")
    s.rating(*sk.pos("POS_RATING_VALUE"), 4)
    s.text(*sk.pos("POS_TIME_VALUE"), "00:01:24 / 00:03:58", "RGBA_TEXT")
    s.text(*sk.pos("POS_TRACK_VALUE"), "3567 / 4912", "RGBA_TEXT")
    cx, cy = sk.pos("POS_COVERART")
    cw, ch = sk.param("COVERART_WIDTH"), sk.param("COVERART_HEIGHT")
    s._paste_clipped(cover_placeholder(cw).resize((cw, ch)), cx, cy)
    s.image("filespecsbkg", *sk.pos("POS_FILE_SPECS_BKG"))
    for key, label, value in [("MODE", "MODE", "joint (MS/intensity) stereo"), ("BITRATE", "BITRATE", "320 [320] kbit"),
                              ("SAMPLERATE", "SAMPLERATE", "44100 Hz"), ("FILE_FORMAT", "FILE_FORMAT", "MP3 Layer III"),
                              ("EMPHASIS", "EMPHASIS", "no")]:
        s.text(*sk.pos("POS_%s_LABEL" % key), LANG[label], "RGBA_LABEL_TEXT")
        s.text(*sk.pos("POS_%s_VALUE" % key), value, "RGBA_TEXT")
    s.image("playerstatusbkg", *sk.pos("POS_PLAYER_STATUS_BKG"))
    for key, label, value in [("SLEEP_MODE", "SLEEP_MODE", "Off"), ("PLAY_MODE", "PLAY_MODE", "Shuffle/repeat"),
                              ("STATUS", "STATUS", "Playing"), ("VOLUME_BOOST", "VOLUME_BOOST", "0"),
                              ("EQUALIZER", "EQUALIZER", "Not supported")]:
        s.text(*sk.pos("POS_%s_LABEL" % key), LANG[label], "RGBA_LABEL_TEXT")
        s.text(*sk.pos("POS_%s_VALUE" % key), value, "RGBA_TEXT")
    px, py = sk.pos("POS_PROGRESS")
    s.image("progressbkg", px, py)
    s.image("progress", px, py + 2, crop_width=int(sk.images["progress"].width * 0.35))
    return s.img


FILES = [("PSP", "folder"), ("Daft Punk - Discovery", "folder"), ("Digitalism - I Love You, Dude", "folder"),
         ("Justice - Cross", "folder"), ("long mixes", "folder"), ("Portishead - Dummy", "folder"),
         ("01 - Antibiotics.mp3", "music"), ("02 - Circles.mp3", "music"), ("03 - Forrest Gump.mp3", "music"),
         ("04 - Blitz.mp3", "music"), ("05 - Reeperbahn.mp3", "music"), ("06 - 2 Hearts.mp3", "music"),
         ("07 - Just Another Day.mp3", "music"), ("08 - Miami Showdown.mp3", "music")]


def render_browser(skin):
    s = Screen(skin)
    sk = skin
    s.common()
    s.button_bar(0)
    x, y = sk.pos("POS_FILE_BROWSER")
    s.menu("menubkg", x, y, [f for f, _ in FILES], 7, icons=[i for _, i in FILES])
    cx, cy = sk.pos("POS_FILE_BROWSER_COVERART")
    cw, ch = sk.param("FILE_BROWSER_COVERART_WIDTH"), sk.param("FILE_BROWSER_COVERART_HEIGHT")
    s._paste_clipped(cover_placeholder(cw).resize((cw, ch)), cx, cy)
    return s.img


def render_library(skin):
    s = Screen(skin)
    sk = skin
    s.common()
    s.button_bar(3)
    items = [LANG[k] for k in ["SHUFFLE_ALL", "BROWSE_ALL", "BROWSE_ARTIST", "BROWSE_ALBUM", "BROWSE_GENRE",
                               "BROWSE_RATING", "BROWSE_TOP100", "SEARCH", "SCAN_MS"]]
    x, y = sk.pos("POS_MEDIALIBRARY")
    if sk.param("MEDIALIBRARY_MAP", -1) == 1 and all("mlitem%d" % i in sk.images for i in range(1, 10)):
        # gui_mediaLibrary.c drawMapMenu()
        selected = 2
        s.image("medialibrarybkg", x, y)
        for i in range(1, 10):
            s.image(("mlitemsel%d" if i - 1 == selected else "mlitem%d") % i, *sk.pos("POS_MEDIALIBRARY_MAP_ITEM_%d" % i))
        if "POS_MEDIALIBRARY_MAP_CAPTION" in sk.cfg:
            s.text(*sk.pos("POS_MEDIALIBRARY_MAP_CAPTION"), items[selected], "RGBA_TEXT")
    else:
        s.menu("medialibrarybkg", x, y, items, 0, align="center")
    return s.img


ARTISTS = ["Aphex Twin (41)", "Boards of Canada (63)", "Chemical Brothers (88)", "Daft Punk (52)",
           "Deadmau5 (37)", "Digitalism (29)", "Gorillaz (74)", "Justice (31)", "Kraftwerk (45)",
           "LCD Soundsystem (40)", "Massive Attack (58)", "Moby (33)"]


def render_artists(skin):
    s = Screen(skin)
    sk = skin
    s.common()
    s.button_bar(3)
    x, y = sk.pos("POS_MEDIALIBRARY_QUERY")
    s.menu("medialibraryquerybkg", x, y, ARTISTS, 5, icons=["folder"] * len(ARTISTS))
    s.image("medialibraryinfobkg", *sk.pos("POS_MEDIALIBRARY_INFO_BKG"))
    s.text(*sk.pos("POS_MEDIALIBRARY_TOTAL_TRACKS_LABEL"), LANG["TOTAL_TRACKS"], "RGBA_LABEL_TEXT")
    s.text(*sk.pos("POS_MEDIALIBRARY_TOTAL_TIME_LABEL"), LANG["TOTAL_TIME"], "RGBA_LABEL_TEXT")
    s.text(*sk.pos("POS_MEDIALIBRARY_TOTAL_TRACKS_VALUE"), "29", "RGBA_TEXT")
    s.text(*sk.pos("POS_MEDIALIBRARY_TOTAL_TIME_VALUE"), "01:58:12", "RGBA_TEXT")
    return s.img


def sheet(images, scale, title, captions):
    pad, cap = 16 * scale // 2, 22 * scale // 2
    tw, th = W * scale, H * scale
    title_h = 34 * scale // 2
    out = Image.new("RGB", (pad + 2 * (tw + pad), title_h + pad + 2 * (th + cap + pad)), (24, 24, 28))
    d = ImageDraw.Draw(out)
    tfont = ImageFont.truetype(os.path.join(FONT_DIR, "LiberationSans-Bold.ttf"), 20 * scale // 2)
    cfont = ImageFont.truetype(os.path.join(FONT_DIR, "LiberationSans-Regular.ttf"), 14 * scale // 2)
    d.text((pad, pad // 2), title, font=tfont, fill=(240, 240, 240))
    for n, (im, c) in enumerate(zip(images, captions)):
        col, rowi = n % 2, n // 2
        x = pad + col * (tw + pad)
        y = title_h + pad + rowi * (th + cap + pad)
        d.text((x, y), c, font=cfont, fill=(180, 180, 190))
        out.paste(im.convert("RGB").resize((tw, th), Image.NEAREST), (x, y + cap))
    return out


LANG = load_lang()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("skin")
    ap.add_argument("out")
    ap.add_argument("--scale", type=int, default=2)
    ap.add_argument("--title", default=None)
    a = ap.parse_args()
    skin = Skin(a.skin)
    shots = [("player", render_player(skin)), ("browser", render_browser(skin)),
             ("library", render_library(skin)), ("artists", render_artists(skin))]
    for name, im in shots:
        im.convert("RGB").resize((W * a.scale, H * a.scale), Image.NEAREST).save("%s-%s.png" % (a.out, name))
    title = a.title or os.path.basename(os.path.normpath(a.skin))
    sheet([im for _, im in shots], a.scale, title,
          ["Now playing", "File browser", "Media Library", "Browse by artist"]).save("%s-sheet.png" % a.out)


if __name__ == "__main__":
    main()
