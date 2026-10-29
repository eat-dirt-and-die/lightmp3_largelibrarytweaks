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
#include <oslib/oslib.h>
#include "../main.h"
#include "shuffleAll.h"
#include "common.h"
#include "languages.h"
#include "settings.h"
#include "gui_player.h"
#include "../system/opendir.h"
#include "../system/clock.h"
#include "../players/m3u.h"

#define PROGRESS_INTERVAL 250000 //Redraw the progress popup at most every 250ms

struct shuffleDir{
    char name[264];
    char shortName[264];
};

static void drawProgress(int songs){
    char message[64];
    snprintf(message, sizeof(message), "%i", songs);
    oslStartDrawing();
    drawCommonGraphics();
    drawWait(langGetString("ADDING_PLAYLIST"), message);
    oslEndDrawing();
    oslEndFrame();
    oslSyncFrame();
}

static void showNoSongs(){
    while (!osl_quit){
        oslStartDrawing();
        drawCommonGraphics();
        drawMessageBox(langGetString("SHUFFLE_ALL"), langGetString("SHUFFLE_ALL_NONE"));
        oslEndDrawing();
        oslEndFrame();
        oslSyncFrame();
        oslReadKeys();
        if (getConfirmButton() || getCancelButton())
            break;
    }
}

///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Shuffle All: put every song in dirName and its subfolders (except the ones
// in ML_EXCLUDE) in a playlist and get it ready to play in shuffle mode.
// No library scan or tag reading is needed, so this is quick even for big
// libraries. The cancel button stops it.
// Returns the number of songs found; when > 0 the caller should switch to
// MODE_PLAYER.
///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
int shuffleAll(char *dirName, char *dirNameShort, int fromMode){
    struct shuffleDir current;
    struct shuffleDir *dirStack = NULL;
    int dirStackCount = 0;
    int dirStackSize = 64;
    struct opendir_struct directory;
    char fileName[264] = "";
    unsigned int lastDraw = sceKernelGetSystemTimeLow();
    int cancelled = 0;
    int full = 0;
    int i;

    cpuBoost();
    M3U_clear();
    drawProgress(0);

    dirStack = malloc(sizeof(struct shuffleDir) * dirStackSize);
    if (dirStack){
        snprintf(dirStack[0].name, sizeof(dirStack[0].name), "%s", dirName);
        snprintf(dirStack[0].shortName, sizeof(dirStack[0].shortName), "%s", dirNameShort);
        dirStackCount = 1;
    }

    opendir_beginBatch();
    while (dirStackCount > 0 && !osl_quit && !cancelled && !full){
        current = dirStack[--dirStackCount];
        if (opendir_open(&directory, current.name, current.shortName, fileExt, fileExtCount - 1, 1) == 0){
            int needSlash = current.name[strlen(current.name) - 1] != '/';
            for (i = 0; i < directory.number_of_directory_entries; i++){
                struct dirElement *entry = &directory.directory_entry[i];
                if (FIO_S_ISREG(entry->d_stat.st_mode)){
                    snprintf(fileName, sizeof(fileName), needSlash ? "%s/%s" : "%s%s", current.shortName, entry->d_name);
                    if (M3U_addSong(fileName, 0, entry->longname) < 0){
                        full = 1; //Out of memory: play what we have
                        break;
                    }
                }else if (FIO_S_ISDIR(entry->d_stat.st_mode)){
                    if (dirStackCount == dirStackSize){
                        struct shuffleDir *bigger = realloc(dirStack, sizeof(struct shuffleDir) * dirStackSize * 2);
                        if (!bigger)
                            continue;
                        dirStack = bigger;
                        dirStackSize *= 2;
                    }
                    snprintf(dirStack[dirStackCount].name, sizeof(dirStack[dirStackCount].name), needSlash ? "%s/%s" : "%s%s", current.name, entry->longname);
                    if (opendir_isExcluded(dirStack[dirStackCount].name, userSettings->mediaLibraryExclude))
                        continue;
                    snprintf(dirStack[dirStackCount].shortName, sizeof(dirStack[dirStackCount].shortName), needSlash ? "%s/%s" : "%s%s", current.shortName, entry->d_name);
                    dirStackCount++;
                }
            }
        }
        opendir_close(&directory);

        if (sceKernelGetSystemTimeLow() - lastDraw > PROGRESS_INTERVAL){
            drawProgress(M3U_getSongCount());
            oslReadKeys();
            if (getCancelButton())
                cancelled = 1;
            lastDraw = sceKernelGetSystemTimeLow();
        }
    }
    opendir_endBatch();
    free(dirStack);

    int count = cancelled ? 0 : M3U_getSongCount();
    if (count > 0){
        drawProgress(count);
        M3U_save(MLtempM3Ufile);
        snprintf(userSettings->selectedBrowserItem, sizeof(userSettings->selectedBrowserItem), "%s", MLtempM3Ufile);
        snprintf(userSettings->selectedBrowserItemShort, sizeof(userSettings->selectedBrowserItemShort), "%s", MLtempM3Ufile);
        userSettings->playlistStartIndex = -1;
        userSettings->previousMode = fromMode;
        if (userSettings->playMode != MODE_SHUFFLE && userSettings->playMode != MODE_SHUFFLE_REPEAT){
            userSettings->restorePlayMode = userSettings->playMode;
            userSettings->playMode = MODE_SHUFFLE_REPEAT;
        }
    }
    M3U_clear();
    if (!count && !cancelled && !osl_quit)
        showNoSongs();
    oslReadKeys();
    cpuRestore();
    return count;
}
