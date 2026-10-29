//    LightMP3 - compatibility shims for the current pspdev toolchain
//
//    This program is free software; you can redistribute it and/or modify
//    it under the terms of the GNU General Public License as published by
//    the Free Software Foundation; either version 2 of the License, or
//    (at your option) any later version.
#include <errno.h>
#include <sys/stat.h>

// libFLAC references utimensat() from its metadata-writing code, which
// LightMP3 never calls. Newlib on PSP doesn't provide it, so stub it out.
int utimensat(int dirfd, const char *pathname, const struct timespec times[2], int flags){
    errno = ENOSYS;
    return -1;
}
