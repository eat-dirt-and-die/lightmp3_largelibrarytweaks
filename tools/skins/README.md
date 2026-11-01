# Skin tools

- `make_skins.py OUT_DIR [theme ...]`: draws the Duke, Luna, ClickWheel, Y2K Chrome,
  Pit Lane and Crossbar skins (images + `skin.cfg`). The output in `src_v2/skins/` comes
  from `python3 tools/skins/make_skins.py src_v2/skins`; theme names are `duke`, `luna`,
  `clickwheel`, `y2k`, `pitlane3`, `pitlane2` and `crossbar`.
- `preview.py SKIN_DIR OUT_PREFIX`: renders the player, file browser and Media Library
  screens of any skin (including the stock ones) as PNGs, using the same layout rules as
  the app (including `.oft` fonts and the map menu).
- `gt_skins.py`: Pit Lane 3 (GT3 style) and Pit Lane 2 (GT2 style). Their artwork is SVG,
  rendered to PNG by headless Chromium (`svgrender.js`); the rendered SVGs are kept in
  `svg/<skin>/`. Their text uses bitmap fonts made by `oftfont.py` from the typefaces in
  `fonts/` (SIL Open Font License; the license ships with each skin as FONT-LICENSE.txt).
- `xp_skins.py`: Luna's Windows XP desktop. The Media Library home screen is a desktop of
  nine icons (map menu) with a decorative Recycle Bin, and a taskbar button that shows the
  selected entry's name; the title bar and taskbar (start button, tray) are SVG too. The
  panels, tabs and list icons still come from the Luna theme in `make_skins.py`.
- `crossbar_skins.py`: Crossbar, a PlayStation XMB style skin: wave background, a row of
  white category icons for the tabs, glass panels, and the Media Library entries as a
  column under the Media Library icon. App text uses the PSP's own sans (`ltn0.pgf`).
- Icon labels baked into the Luna and Crossbar images use DejaVu Sans Condensed (Bitstream
  Vera license, `fonts/LICENSE-DejaVu.txt`) and Inter (SIL OFL, `fonts/OFL-Inter.txt`).
  These two skins don't ship a font file. All icons are original drawings.

Needs Python 3 with Pillow and numpy; the previews use the Liberation fonts. The Pit
Lane, Luna and Crossbar skins also need Node.js with Playwright and its Chromium.

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

Tricks the stock skin format already allows (used by Luna and Crossbar):
- Tab images can be any size and overlap; Crossbar's are 96x40 icons placed 72 px apart.
- The map menu is drawn after the toolbars, so `medialibrarybkg.png` can be taller than the
  desktop area and paint over the bottom bar on that screen only (Luna's task button sits
  there, with `POS_MEDIALIBRARY_MAP_CAPTION` on it). Its transparent parts show what's under.
- Map pictures can overlap too; they are drawn in order 1 to 9.
- The Media Library home screen uses `medialibrarybkg.png`, its lists use
  `medialibraryquerybkg.png`, so the two can look completely different.

Notes on how LightMP3 lays out text (measured on a PSP-3000):
- `FONT_NORMAL_SIZE` scales the glyphs, but menu rows stay `charHeight` (about 17 px) apart.
- Text baseline is at `y + charHeight/2 + 1`, so text grows upward from its position;
  leave about 3 px above each text position.
- Menus start drawing rows at the top of their background image. Make list backgrounds a
  few pixels taller than `rows * 17` so the rows get a margin.
- Anything placed at `-1000,-1000` isn't drawn, which hides unwanted rows.
