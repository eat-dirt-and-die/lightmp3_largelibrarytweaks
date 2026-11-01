# Skin tools

- `make_skins.py OUT_DIR [theme ...]`: draws the Duke, Luna, ClickWheel, Y2K Chrome
  and Pit Lane skins (images + `skin.cfg`). The output in `src_v2/skins/` comes from
  `python3 tools/skins/make_skins.py src_v2/skins`.
- `preview.py SKIN_DIR OUT_PREFIX`: renders the player, file browser and Media Library
  screens of any skin (including the stock ones) as PNGs, using the same layout rules as
  the app (including `.oft` fonts and the map menu).
- `gt_skins.py`: Pit Lane 3 (GT3 style) and Pit Lane 2 (GT2 style). Their artwork is SVG,
  rendered to PNG by headless Chromium (`svgrender.js`); the rendered SVGs are kept in
  `svg/<skin>/`. Their text uses bitmap fonts made by `oftfont.py` from the typefaces in
  `fonts/` (SIL Open Font License; the license ships with each skin as FONT-LICENSE.txt).

Needs Python 3 with Pillow and numpy; the previews use the Liberation fonts. The two Pit
Lane skins also need Node.js with Playwright and its Chromium.

Skin features added in this fork:
- Own bitmap font: `STR_FONT_NORMAL_NAME=$skinimage/myfont.oft`. OSLib .oft fonts can be
  4 bits per pixel with a 16-colour palette that is multiplied by the text colour, so
  `oftfont.py` makes them anti-aliased with a baked dark outline. The app converts its
  UTF-8 text to the font's Windows-1252 layout. If the font won't load, the PSP's own font
  is used. Menu rows are the font's cell height (16) plus `MENU_INTERLINE`.
- Map style Media Library menu: `MEDIALIBRARY_MAP=1` draws `medialibrarybkg.png` with
  `mlitem1..9.png` (and `mlitemsel1..9.png` for the selected entry) at
  `POS_MEDIALIBRARY_MAP_ITEM_1..9`, plus the selected entry's name at
  `POS_MEDIALIBRARY_MAP_CAPTION`. Left/right also move between entries. If any picture is
  missing, the normal list is used.
- Tab labels can be part of the tab images: set `RGBA_BUTTONBAR_TEXT` and
  `RGBA_BUTTONBAR_SELECTED_TEXT` to `0,0,0,0` to hide the drawn text.

Notes on how LightMP3 lays out text (measured on a PSP-3000):
- `FONT_NORMAL_SIZE` scales the glyphs, but menu rows stay `charHeight` (about 17 px) apart.
- Text baseline is at `y + charHeight/2 + 1`, so text grows upward from its position;
  leave about 3 px above each text position.
- Menus start drawing rows at the top of their background image. Make list backgrounds a
  few pixels taller than `rows * 17` so the rows get a margin.
- Anything placed at `-1000,-1000` isn't drawn, which hides unwanted rows.
