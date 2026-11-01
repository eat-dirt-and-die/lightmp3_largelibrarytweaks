//    LightMP3
//
//    This program is free software; you can redistribute it and/or modify
//    it under the terms of the GNU General Public License as published by
//    the Free Software Foundation; either version 2 of the License, or
//    (at your option) any later version.
#include <string.h>
#include <oslib/oslib.h>

// Unicode code points of Windows-1252 bytes 0x80-0x9F (0 = unused byte).
static const unsigned short cp1252High[32] = {
    0x20AC, 0, 0x201A, 0x0192, 0x201E, 0x2026, 0x2020, 0x2021, 0x02C6, 0x2030, 0x0160, 0x2039, 0x0152, 0, 0x017D, 0,
    0, 0x2018, 0x2019, 0x201C, 0x201D, 0x2022, 0x2013, 0x2014, 0x02DC, 0x2122, 0x0161, 0x203A, 0x0153, 0, 0x017E, 0x0178
};

static unsigned char toCp1252(unsigned int cp){
    int i;
    if (cp < 0x80 || (cp >= 0xA0 && cp <= 0xFF))
        return (unsigned char)cp;
    for (i = 0; i < 32; i++)
        if (cp1252High[i] == cp)
            return (unsigned char)(0x80 + i);
    return '?';
}

// Converts UTF-8 to the glyph indexes of a bitmap font. Bytes that aren't
// valid UTF-8 are kept as they are (Latin-1, e.g. ID3v1 tags), which is also
// what the font expects for them. intraFont reads UTF-8 itself.
static const char *forCurrentFont(const char *str){
    static char converted[1024];
    const unsigned char *s = (const unsigned char *)str;
    int out = 0;

    if (!str || !osl_curFont || osl_curFont->fontType != OSL_FONT_OFT)
        return str;
    while (*s && out < (int)sizeof(converted) - 1){
        unsigned int cp = *s;
        int extra = 0;
        if (cp >= 0xC2 && cp <= 0xDF)
            extra = 1;
        else if (cp >= 0xE0 && cp <= 0xEF)
            extra = 2;
        else if (cp >= 0xF0 && cp <= 0xF4)
            extra = 3;
        if (extra){
            int i;
            unsigned int value = cp & (0x3F >> extra);
            for (i = 1; i <= extra; i++){
                if ((s[i] & 0xC0) != 0x80)
                    break;
                value = (value << 6) | (s[i] & 0x3F);
            }
            if (i > extra){
                converted[out++] = (char)toCp1252(value);
                s += extra + 1;
                continue;
            }
        }
        converted[out++] = (char)*s++;
    }
    converted[out] = '\0';
    return converted;
}

void lmp3DrawString(int x, int y, const char *str){
    oslDrawString(x, y, forCurrentFont(str));
}

void lmp3DrawStringLimited(int x, int y, int width, const char *str){
    oslDrawStringLimited(x, y, width, forCurrentFont(str));
}

int lmp3GetStringWidth(const char *str){
    return oslGetStringWidth(forCurrentFont(str));
}
