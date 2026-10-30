//    LightMP3
//
//    This program is free software; you can redistribute it and/or modify
//    it under the terms of the GNU General Public License as published by
//    the Free Software Foundation; either version 2 of the License, or
//    (at your option) any later version.
#ifndef __coverart_h
#define __coverart_h (1)

#include <oslib/oslib.h>

OSL_IMAGE *coverArtLoadMemory(unsigned char *data, int size, int location, int pixelFormat);
OSL_IMAGE *coverArtLoadFile(char *fileName, int location, int pixelFormat);

#endif
