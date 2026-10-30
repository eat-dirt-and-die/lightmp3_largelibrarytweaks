//    LightMP3
//
//    This program is free software; you can redistribute it and/or modify
//    it under the terms of the GNU General Public License as published by
//    the Free Software Foundation; either version 2 of the License, or
//    (at your option) any later version.
//
//    This program is distributed in the hope that it will be useful,
//    but WITHOUT ANY WARRANTY; without even the implied warranty of
//    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
//    GNU General Public License for more details.
//
//    You should have received a copy of the GNU General Public License
//    along with this program; if not, write to the Free Software
//    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#include <pspkernel.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <setjmp.h>
#include <jpeglib.h>
#include <oslib/oslib.h>
#include "coverart.h"

///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Cover art loading.
// OSLib's oslLoadImageFileJPG uses libjpeg's default error handler, which
// calls exit() on any fatal error (PNG data in an MP3 tag, CMYK JPEGs, broken
// headers...), dropping straight back to the XMB. Decode JPEGs here with an
// error handler that just gives up on the image, and hand PNGs to the PNG
// loader instead.
///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
#define MAX_COVER_SIDE 512              //OSLib images can't be bigger than 512x512
#define MAX_COVER_FILE_SIZE (1024*1024)

struct safeJpegError{
    struct jpeg_error_mgr pub;
    jmp_buf jump;
};

static void safeErrorExit(j_common_ptr cinfo){
    longjmp(((struct safeJpegError *)cinfo->err)->jump, 1);
}

static void quietMessage(j_common_ptr cinfo){
}

static OSL_IMAGE *loadJPEG(unsigned char *data, int size, int location, int pixelFormat){
    struct jpeg_decompress_struct cinfo;
    struct safeJpegError err;
    OSL_IMAGE * volatile img = NULL;
    JSAMPLE * volatile row = NULL;
    volatile int locked = 0;

    cinfo.err = jpeg_std_error(&err.pub);
    err.pub.error_exit = safeErrorExit;
    err.pub.output_message = quietMessage;
    if (setjmp(err.jump)){
        if (locked)
            oslUnlockImage(img);
        jpeg_destroy_decompress(&cinfo);
        free(row);
        if (img)
            oslDeleteImage(img);
        return NULL;
    }

    jpeg_create_decompress(&cinfo);
    jpeg_mem_src(&cinfo, data, size);
    jpeg_read_header(&cinfo, TRUE);
    if (cinfo.jpeg_color_space == JCS_CMYK || cinfo.jpeg_color_space == JCS_YCCK)
        cinfo.out_color_space = JCS_CMYK;
    else
        cinfo.out_color_space = JCS_RGB;
    //Let the decoder shrink big covers (it's also much faster):
    cinfo.scale_num = 1;
    cinfo.scale_denom = 1;
    while ((cinfo.image_width / cinfo.scale_denom > MAX_COVER_SIDE || cinfo.image_height / cinfo.scale_denom > MAX_COVER_SIDE) && cinfo.scale_denom < 8)
        cinfo.scale_denom *= 2;
    jpeg_start_decompress(&cinfo);
    if (cinfo.output_width > MAX_COVER_SIDE || cinfo.output_height > MAX_COVER_SIDE)
        longjmp(err.jump, 1);

    img = oslCreateImage(cinfo.output_width, cinfo.output_height, location & OSL_LOCATION_MASK, pixelFormat);
    row = malloc(cinfo.output_width * cinfo.output_components);
    if (!img || !row)
        longjmp(err.jump, 1);

    oslLockImage(img);
    locked = 1;
    while (cinfo.output_scanline < cinfo.output_height){
        int y = cinfo.output_scanline;
        JSAMPROW rowPtr = row;
        unsigned int x;
        jpeg_read_scanlines(&cinfo, &rowPtr, 1);
        for (x = 0; x < cinfo.output_width; x++){
            int r, g, b;
            if (cinfo.out_color_space == JCS_CMYK){
                //Photoshop-style (inverted) CMYK, the usual kind in the wild:
                JSAMPLE *p = &row[x * 4];
                r = p[0] * p[3] / 255;
                g = p[1] * p[3] / 255;
                b = p[2] * p[3] / 255;
            }else{
                JSAMPLE *p = &row[x * 3];
                r = p[0];
                g = p[1];
                b = p[2];
            }
            u32 color = RGBA(r, g, b, 255);
            if (pixelFormat != OSL_PF_8888)
                color = oslConvertColor(pixelFormat, OSL_PF_8888, color);
            oslSetImagePixel(img, x, y, color);
        }
    }
    oslUnlockImage(img);
    locked = 0;
    jpeg_finish_decompress(&cinfo);
    jpeg_destroy_decompress(&cinfo);
    free(row);

    if (location & OSL_SWIZZLED)
        oslSwizzleImage(img);
    return img;
}

static OSL_IMAGE *loadPNG(unsigned char *data, int size, int location, int pixelFormat){
    //Width/height from the IHDR chunk (OSLib can't handle more than 512x512):
    if (size < 24 || memcmp(data + 12, "IHDR", 4))
        return NULL;
    unsigned int width = (data[16] << 24) | (data[17] << 16) | (data[18] << 8) | data[19];
    unsigned int height = (data[20] << 24) | (data[21] << 16) | (data[22] << 8) | data[23];
    if (!width || !height || width > MAX_COVER_SIDE || height > MAX_COVER_SIDE)
        return NULL;
    oslSetTempFileData(data, size, &VF_MEMORY);
    return oslLoadImageFilePNG(oslGetTempFileName(), location, pixelFormat);
}

OSL_IMAGE *coverArtLoadMemory(unsigned char *data, int size, int location, int pixelFormat){
    if (!data || size < 8)
        return NULL;
    if (data[0] == 0xFF && data[1] == 0xD8 && data[2] == 0xFF)
        return loadJPEG(data, size, location, pixelFormat);
    if (!memcmp(data, "\x89PNG\r\n\x1a\n", 8))
        return loadPNG(data, size, location, pixelFormat);
    return NULL;
}

OSL_IMAGE *coverArtLoadFile(char *fileName, int location, int pixelFormat){
    OSL_IMAGE *img = NULL;
    SceUID fd = sceIoOpen(fileName, PSP_O_RDONLY, 0777);
    if (fd < 0)
        return NULL;
    int size = sceIoLseek32(fd, 0, PSP_SEEK_END);
    sceIoLseek32(fd, 0, PSP_SEEK_SET);
    if (size > 0 && size <= MAX_COVER_FILE_SIZE){
        unsigned char *data = malloc(size);
        if (data){
            if (sceIoRead(fd, data, size) == size)
                img = coverArtLoadMemory(data, size, location, pixelFormat);
            free(data);
        }
    }
    sceIoClose(fd);
    return img;
}
