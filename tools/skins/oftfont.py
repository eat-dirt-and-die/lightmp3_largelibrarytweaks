#!/usr/bin/env python3
"""Make and read OSLib bitmap fonts (.oft) for LightMP3 skins.

OSLib .oft layout (checked against libosl's oslLoadFontFile/oslLoadFont):
  64-byte header  "OSLFont v01\\0", pixelFormat (bits per pixel: 1/2/4),
                  variableWidth, charWidth, charHeight, lineWidth (bytes per
                  glyph row), addedSpace (extra texture pixels after each
                  glyph's advance), paletteCount
  256 bytes       advance width of each character (if variableWidth)
  glyphs          256 * charHeight * lineWidth bytes; pixels LSB first
  palette         paletteCount * u32 (0xAABBGGRR)

Each glyph pixel indexes the palette, and OSLib multiplies the result by the
current text colour. So white entries at various alphas give anti-aliased
text in any colour, and black entries give an outline that stays black.
Characters are Windows-1252; the app converts its UTF-8 strings to match.
"""
import struct

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HEADER = struct.Struct("<12sBBxxiiiBxH29s3x")
assert HEADER.size == 64


def _char(code):
    if code < 32:
        return None
    try:
        return bytes([code]).decode("cp1252")
    except UnicodeDecodeError:
        return None


def make_oft(path, ttf, size, cell_height, baseline, weight=None, tracking=0,
             outline=0.9, shadow=0.55):
    """Render ttf at size px into an .oft font at path.

    baseline: pixel row of the baseline inside the cell (text is drawn with its
    cell top at the y the app asks for). outline/shadow: strength (0..1) of the
    baked dark outline and the down-right shadow.
    """
    font = ImageFont.truetype(ttf, size)
    if weight is not None:
        font.set_variation_by_axes([weight])
    pad = 1  # room for the outline left of the glyph
    cells, widths = [], []
    for code in range(256):
        ch = _char(code)
        if ch is None:
            cells.append(np.zeros((cell_height, 1), np.float32))
            widths.append(0)
            continue
        adv = max(1, int(round(font.getlength(ch))) + tracking)
        w = adv + pad + 4
        im = Image.new("L", (w, cell_height), 0)
        ImageDraw.Draw(im).text((pad, baseline), ch, font=font, fill=255, anchor="ls")
        cells.append(np.asarray(im, np.float32) / 255.0)
        widths.append(adv)

    # coverage -> (gray, alpha) with a soft outline and shadow
    comp = []
    for ct in cells:
        h, w = ct.shape
        p = np.pad(ct, 2)
        ring = np.zeros_like(ct)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx or dy:
                    k = 1.0 if dx == 0 or dy == 0 else 0.7
                    ring = np.maximum(ring, p[2 + dy:2 + dy + h, 2 + dx:2 + dx + w] * k)
        sh = p[1:1 + h, 1:1 + w] * shadow  # pixel up-left of us is ink: shadow falls here
        co = np.clip(np.maximum(ring * outline, sh), 0, 1)
        a = ct + (1 - ct) * co
        g = np.where(a > 0, ct / np.maximum(a, 1e-6), 0)
        comp.append((g, a))

    # palette: transparent, solid text, solid outline + 13 learned entries
    samples = np.concatenate([np.stack([g[a > 0.04], a[a > 0.04]], 1) for g, a in comp])
    fixed = np.array([[1.0, 1.0], [0.0, 1.0]])
    rng = np.random.default_rng(1)
    centers = np.concatenate([fixed, samples[rng.choice(len(samples), 13, replace=False)]])
    for _ in range(25):
        d = ((samples[:, None, :] - centers[None]) ** 2).sum(-1)
        lab = d.argmin(1)
        for k in range(2, len(centers)):
            m = lab == k
            if m.any():
                centers[k] = samples[m].mean(0)
    palette = [(0.0, 0.0)] + [tuple(c) for c in centers]  # index 0 = transparent

    added = max(c.shape[1] - wd for c, wd in zip(cells, widths) if wd) if any(widths) else 0
    added = max(0, min(added, 255))
    max_cell = max(wd for wd in widths) + added
    line_width = (max_cell + 1) // 2  # 4 bits per pixel
    data = bytearray()
    pal = np.array(palette[1:])
    for (g, a), wd in zip(comp, widths):
        h = cell_height
        idx = np.zeros((h, line_width * 2), np.uint8)
        if wd:
            cw = min(g.shape[1], wd + added)
            gg, aa = g[:, :cw], a[:, :cw]
            d = ((np.stack([gg, aa], -1)[:, :, None, :] - pal[None, None]) ** 2).sum(-1)
            sel = d.argmin(-1) + 1
            sel[aa <= 0.04] = 0
            idx[:, :cw] = sel
        for row in idx:
            data += bytes((row[0::2] | (row[1::2] << 4)).astype(np.uint8))
    pal_bytes = b"".join(struct.pack("<I", (int(round(gv * 255)) * 0x010101) | (int(round(av * 255)) << 24))
                         for gv, av in palette)
    avg = int(round(np.mean([w for w in widths[32:127] if w])))
    header = HEADER.pack(b"OSLFont v01\0", 4, 1, avg, cell_height, line_width, added, len(palette), b"\0" * 29)
    with open(path, "wb") as f:
        f.write(header + bytes(widths) + bytes(data) + pal_bytes)
    return {"cell_height": cell_height, "added_space": added, "line_width": line_width}


class OftFont:
    """Reads an .oft font and draws text the way OSLib does (for previews)."""

    def __init__(self, path):
        raw = open(path, "rb").read()
        tag, bpp, variable, cw, ch, lw, added, npal, _ = HEADER.unpack_from(raw, 0)
        assert tag.startswith(b"OSLFont v01"), path
        off = 64
        if variable:
            self.widths = list(raw[off:off + 256])
            off += 256
        else:
            self.widths = [cw] * 256
        self.charHeight, self.added = ch, added
        size = 256 * ch * lw
        data = np.frombuffer(raw[off:off + size], np.uint8).reshape(256, ch, lw)
        off += size
        if npal:
            pal = np.frombuffer(raw[off:off + 4 * npal], "<u4")
        else:
            pal = np.array([0x00FFFFFF, 0xFFFFFFFF], "<u4")
        self.palette = np.zeros((16, 4), np.float32)
        for i, v in enumerate(pal[:16]):
            self.palette[i] = [(v & 255), (v >> 8) & 255, (v >> 16) & 255, (v >> 24) & 255]
        per = 8 // bpp
        mask = (1 << bpp) - 1
        self.glyphs = []
        for c in range(256):
            rows = data[c]
            idx = np.zeros((ch, lw * per), np.uint8)
            for k in range(per):
                idx[:, k::per] = (rows >> (k * bpp)) & mask
            self.glyphs.append(idx[:, :self.widths[c] + added])

    def to_bytes(self, text):
        out = bytearray()
        for ch in text:
            try:
                out += ch.encode("cp1252")
            except UnicodeEncodeError:
                out += b"?"
        return bytes(out)

    def width(self, text):
        return sum(self.widths[b] for b in self.to_bytes(text))

    def draw(self, canvas, x, y, text, color, max_width=None):
        """Composite text onto an RGBA PIL image with its cell top at y."""
        if color[3] == 0:
            return
        base = np.asarray(canvas, np.float32).copy()
        H, W = base.shape[:2]
        tint = np.array(color, np.float32) / 255.0
        start = x
        for b in self.to_bytes(text):
            if max_width is not None and x + self.widths[b] - start > max_width:
                break
            g = self.palette[self.glyphs[b]] / 255.0 * tint  # modulate like the PSP's GU
            gh, gw = g.shape[:2]
            x0, y0 = max(0, x), max(0, y)
            x1, y1 = min(W, x + gw), min(H, y + gh)
            if x1 > x0 and y1 > y0:
                src = g[y0 - y:y1 - y, x0 - x:x1 - x]
                dst = base[y0:y1, x0:x1] / 255.0
                a = src[..., 3:4]
                out_a = a + dst[..., 3:4] * (1 - a)
                out_rgb = (src[..., :3] * a + dst[..., :3] * dst[..., 3:4] * (1 - a)) / np.maximum(out_a, 1e-6)
                base[y0:y1, x0:x1] = np.concatenate([out_rgb, out_a], -1) * 255
            x += self.widths[b]
        canvas.paste(Image.fromarray(base.clip(0, 255).astype(np.uint8), "RGBA"))


if __name__ == "__main__":
    import sys
    make_oft(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]))
