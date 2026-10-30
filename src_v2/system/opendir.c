/*
This source was taken (and modified) from:
PMP Mod
Copyright (C) 2006 jonny

Homepage: http://jonny.leffe.dnsalias.com
E-mail:   jonny@leffe.dnsalias.com

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
*/

/*
"opendir" c code (~3 lines of perl -> ~100 lines of c :s)
*/

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <strings.h>
#include "opendir.h"
#include "fat.h"
#include "libminiconv.h"
#include <pspsysmem.h>

static int FATinit = 0;
static int batchHeld = 0;

static void initFAT(){
	if (!FATinit){
		fat_init(sceKernelDevkitVersion());
		FATinit = 1;
	}
}

// Call around a run of many opendir_open() calls (library scan, Shuffle All)
// so the FAT table is read once instead of once per folder.
void opendir_beginBatch(){
	initFAT();
	if (!batchHeld)
		batchHeld = fat_hold();
}

void opendir_endBatch(){
	if (batchHeld){
		fat_release();
		batchHeld = 0;
	}
}

// Check a folder (long name path) against a ';' separated exclude list.
// Entries with a ':' are full paths ("ms0:/MUSIC/Podcasts") and also exclude
// everything below them; entries without one match a folder name anywhere
// ("Podcasts"). Matching ignores case and trailing slashes.
int opendir_isExcluded(const char *dirName, const char *excludeList){
	char entry[264];
	const char *p = excludeList;
	const char *baseName = strrchr(dirName, '/');
	int dirLen = strlen(dirName);

	baseName = baseName ? baseName + 1 : dirName;
	while (dirLen > 0 && dirName[dirLen - 1] == '/')
		dirLen--;

	while (p && *p){
		const char *end = strchr(p, ';');
		int len = end ? end - p : strlen(p);
		while (len > 0 && (*p == ' ' || *p == '\t')){
			p++;
			len--;
		}
		while (len > 0 && (p[len - 1] == ' ' || p[len - 1] == '/' || p[len - 1] == '\r' || p[len - 1] == '\n'))
			len--;
		if (len > 0 && len < sizeof(entry)){
			memcpy(entry, p, len);
			entry[len] = '\0';
			if (strchr(entry, ':')){
				if (dirLen >= len && !strncasecmp(dirName, entry, len) && (dirLen == len || dirName[len] == '/'))
					return 1;
			}else if (!strcasecmp(baseName, entry))
				return 1;
		}
		p = end ? end + 1 : NULL;
	}
	return 0;
}

// Fallback listing through the firmware when the raw FAT read fails
// (not enough memory for the FAT table, or a device other than ms0:).
// The firmware fills the 8.3 short name in when d_private points at a
// SceIoFatDirentPrivate. Depending on firmware/SDK version it may instead
// write the short name at the start of the buffer (over "size"), so handle
// both and only keep a short name that really opens.
static void firmwareShortName(const char *directoryShort, SceIoFatDirentPrivate *priv, char *shortName){
	char path[264];
	SceIoStat st;

	if (priv->size == sizeof(*priv))
		memcpy(shortName, priv->s_name, 13);
	else
		memcpy(shortName, priv, 13);
	shortName[13] = '\0';
	if (!shortName[0])
		return;
	if (directoryShort[strlen(directoryShort)-1] != '/')
		snprintf(path, sizeof(path), "%s/%s", directoryShort, shortName);
	else
		snprintf(path, sizeof(path), "%s%s", directoryShort, shortName);
	if (sceIoGetstat(path, &st) < 0)
		shortName[0] = '\0';
}

static char *opendir_open_firmware(struct opendir_struct *p, const char *directoryShort, char extFilter[][5], int extNumber, int includeDirs){
	SceIoDirent entry;
	SceIoFatDirentPrivate priv;
	unsigned int allocated = 64;
	SceUID dir = sceIoDopen(directoryShort);
	if (dir < 0)
		return("opendir_open: sceIoDopen failed");

	p->directory_entry = malloc_64(sizeof(struct dirElement) * allocated);
	if (p->directory_entry == 0){
		sceIoDclose(dir);
		return("opendir_open: malloc_64 failed on directory_entry");
	}

	memset(&entry, 0, sizeof(entry));
	memset(&priv, 0, sizeof(priv));
	priv.size = sizeof(priv);
	entry.d_private = &priv;
	while (sceIoDread(dir, &entry) > 0){
		struct dirElement *el;
		if (entry.d_name[0] == '.')
			goto next;
		if (FIO_S_ISREG(entry.d_stat.st_mode)){
			char ext[5] = "";
			int j;
			getExtension(entry.d_name, ext, 4);
			for (j = 0; j < extNumber; j++)
				if (!strcmp(ext, extFilter[j]))
					break;
			if (j == extNumber)
				goto next;
		}else if (!FIO_S_ISDIR(entry.d_stat.st_mode) || !includeDirs)
			goto next;

		if (p->number_of_directory_entries == allocated){
			struct dirElement *bigger = malloc_64(sizeof(struct dirElement) * allocated * 2);
			if (!bigger)
				break;
			memcpy(bigger, p->directory_entry, sizeof(struct dirElement) * allocated);
			free_64(p->directory_entry);
			p->directory_entry = bigger;
			allocated *= 2;
		}
		el = &p->directory_entry[p->number_of_directory_entries++];
		strncpy(el->longname, entry.d_name, sizeof(el->longname) - 1);
		el->longname[sizeof(el->longname) - 1] = '\0';
		char shortName[14];
		firmwareShortName(directoryShort, &priv, shortName);
		if (shortName[0])
			strcpy(el->d_name, shortName);
		else
			strcpy(el->d_name, el->longname);
		el->d_stat = entry.d_stat;
next:
		memset(&entry, 0, sizeof(entry));
		memset(&priv, 0, sizeof(priv));
		priv.size = sizeof(priv);
		entry.d_private = &priv;
	}
	sceIoDclose(dir);
	sortDirectory(p);
	return(0);
}

void opendir_safe_constructor(struct opendir_struct *p){
	p->directory_entry = 0;
	p->number_of_directory_entries = 0;
}


void opendir_close(struct opendir_struct *p){
	if (p->directory_entry) free_64(p->directory_entry);
	opendir_safe_constructor(p);
}


char *opendir_open(struct opendir_struct *p, const char *directory, const char *directoryShort, char extFilter[][5], int extNumber, int includeDirs){
	initFAT();

	char sdir[264] = "";
	strcpy(sdir, directoryShort);
	opendir_safe_constructor(p);

	p_fat_info finfo;
    u32 number_of_directory_entries = fat_readdir(directory, sdir, &finfo);
	if(number_of_directory_entries == INVALID)
		return opendir_open_firmware(p, directoryShort, extFilter, extNumber, includeDirs);

    //FILE *log = fopen("open_dir.txt", "w");
	p->directory_entry = malloc_64(sizeof(struct dirElement) * number_of_directory_entries);
	if (p->directory_entry == 0){
		opendir_close(p);
		//fwrite("1\n", sizeof(char), strlen("1\n"), log);
		free((void *)finfo);
		return("opendir_open: malloc_64 failed on directory_entry");
	}

	int i = 0;
	for (i = 0; i < number_of_directory_entries; i++){
		//Filtro le dir "." e "..":
		if (finfo[i].filename[0] == '.'){
			//fwrite("2\n", sizeof(char), strlen("1\n"), log);
			continue;
		}

		//File or folder comes straight from the FAT entry. This used to call
		//sceIoGetstat() per entry, and the firmware looks each name up by
		//scanning the folder, so big folders took a minute or more to list.
		memset(&p->directory_entry[p->number_of_directory_entries].d_stat, 0, sizeof(SceIoStat));
		p->directory_entry[p->number_of_directory_entries].d_stat.st_mode = (finfo[i].attr & FAT_FILEATTR_DIRECTORY) ? (FIO_S_IFDIR | 0777) : (FIO_S_IFREG | 0777);
		p->directory_entry[p->number_of_directory_entries].d_stat.st_size = finfo[i].filesize;

		//Controllo il filtro sulle estensioni (solo per i files):
		if (FIO_S_ISREG(p->directory_entry[p->number_of_directory_entries].d_stat.st_mode)){
			//fwrite(" FILE ", sizeof(char), strlen(" FILE "), log);
			int extOK = 0;
			char ext[5] = "";

			getExtension(finfo[i].longname, ext, 4);
			extOK = 0;
			int j = 0;
			for (j = 0; j < extNumber; j++){
				if (strcmp(ext, extFilter[j]) == 0){
					extOK = 1;
					break;
				}
			}
			if (extOK == 0){
				//fwrite("4\n", sizeof(char), strlen("1\n"), log);
				continue;
			}
		}else if (FIO_S_ISDIR(p->directory_entry[p->number_of_directory_entries].d_stat.st_mode)){
			//fwrite(" DIR ", sizeof(char), strlen(" DIR "), log);

			//Salto le directory se devo:
			if (includeDirs == 0){
				//fwrite("5\n", sizeof(char), strlen("1\n"), log);
				continue;
			}
		}
		//Elemento ok:
		strcpy(p->directory_entry[p->number_of_directory_entries].d_name, finfo[i].filename);
        strcpy(p->directory_entry[p->number_of_directory_entries].longname, finfo[i].longname);
		//fwrite(" OK\n", sizeof(char), strlen(" OK\n"), log);
		p->number_of_directory_entries++;
	}
	//fclose(log);
	free((void *)finfo);

	sortDirectory(p);
	return(0);
}


//Ordinamento dei file di una directory (directories first, then by name):
static int compareDirElements(const void *a, const void *b){
	const struct dirElement *e1 = a;
	const struct dirElement *e2 = b;
	int dir1 = FIO_S_ISDIR(e1->d_stat.st_mode) ? 1 : 0;
	int dir2 = FIO_S_ISDIR(e2->d_stat.st_mode) ? 1 : 0;
	if (dir1 != dir2)
		return dir2 - dir1;
	return stricmp(e1->longname, e2->longname);
}

void sortDirectory(struct opendir_struct *directory){
	if (directory->number_of_directory_entries > 1)
		qsort(directory->directory_entry, directory->number_of_directory_entries, sizeof(struct dirElement), compareDirElements);
}

//Extract extension from a filename:
void getExtension(char *fileName, char *extension, int extMaxLength){
    int i = 0;
    int j = 0;
    int count = 0;
    for (i = strlen(fileName) - 1; i >= 0; i--){
        if (fileName[i] == '.'){
            if (i == strlen(fileName) - 1)
                return;
            for (j = i+1; j < strlen(fileName); j++){
                extension[count++] = toupper(fileName[j]);
                if (count > extMaxLength)
                    return;
            }
            extension[count] = '\0';
            return;
        }
    }
}

//Get directory up one level:
int directoryUp(char *dirName)
{
	if (strcmp(dirName, "ms0:/")){
		//Cerco l'ultimo slash:
		int i = 0;
		for (i = strlen(dirName) - 1; i >= 0; i--){
			if (dirName[i] == '/' && i != strlen(dirName)){
				if (i > 4){
					dirName[i] = '\0';
				}else{
					dirName[i+1] = '\0';
				}
				break;
			}
		}
		return(0);
	}else{
		return(-1);
	}
}

//Prendo solo il nome del file/directory:
void getFileName(char *fileName, char *onlyName){
	int slash = 0;

	//Cerco l'ultimo slash:
	int i = 0;
	int len = strlen(fileName);
	for (i = len - 2; i >= 0; i--){
		if (fileName[i] == '/'){
			slash = i;
			break;
		}
	}
	if (slash)
		strcpy(onlyName, fileName + slash + 1);
	else
		strcpy(onlyName, fileName);
}

//Check if a file esists (return fileSize if exists, -1 if doesen't exists):
int fileExists(char *fileName){
    SceIoStat stbuf;
    if(sceIoGetstat(fileName, &stbuf) < 0)
        return -1;
    return stbuf.st_size;
}
