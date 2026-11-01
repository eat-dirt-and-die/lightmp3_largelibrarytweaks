//    LightMP3
//
//    This program is free software; you can redistribute it and/or modify
//    it under the terms of the GNU General Public License as published by
//    the Free Software Foundation; either version 2 of the License, or
//    (at your option) any later version.
#ifndef __textcompat_h
#define __textcompat_h (1)

// Skins can use their own bitmap (.oft) font. Those have 256 glyphs laid out
// as Windows-1252, while the app's strings are UTF-8, so text is converted on
// the way to OSLib when such a font is active. oslib.h must be included first
// so its prototypes are declared before these macros take over the names.
#include <oslib/oslib.h>

void lmp3DrawString(int x, int y, const char *str);
void lmp3DrawStringLimited(int x, int y, int width, const char *str);
int lmp3GetStringWidth(const char *str);

#define oslDrawString(x, y, str) lmp3DrawString((x), (y), (str))
#define oslDrawStringLimited(x, y, width, str) lmp3DrawStringLimited((x), (y), (width), (str))
#define oslGetStringWidth(str) lmp3GetStringWidth(str)

#endif
