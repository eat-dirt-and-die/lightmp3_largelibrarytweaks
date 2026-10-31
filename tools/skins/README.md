# Skin tools

- `make_skins.py OUT_DIR [theme ...]`: draws the Duke, Luna, ClickWheel, Y2K Chrome
  and Pit Lane skins (images + `skin.cfg`). The output in `src_v2/skins/` comes from
  `python3 tools/skins/make_skins.py src_v2/skins`.
- `preview.py SKIN_DIR OUT_PREFIX`: renders the player, file browser and Media Library
  screens of any skin (including the stock ones) as PNGs, using the same layout rules as
  the app.

Both need Python 3 with Pillow and numpy; the previews use the Liberation fonts.

Notes on how LightMP3 lays out text (measured on a PSP-3000):
- `FONT_NORMAL_SIZE` scales the glyphs, but menu rows stay `charHeight` (about 17 px) apart.
- Text baseline is at `y + charHeight/2 + 1`, so text grows upward from its position;
  leave about 3 px above each text position.
- Menus start drawing rows at the top of their background image. Make list backgrounds a
  few pixels taller than `rows * 17` so the rows get a margin.
- Anything placed at `-1000,-1000` isn't drawn, which hides unwanted rows.
