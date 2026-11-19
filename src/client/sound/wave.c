/*
 * Copyright (C) 1997-2001 Id Software, Inc.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or (at
 * your option) any later version.
 *
 * This program is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
 *
 * See the GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307,
 * USA.
 *
 * =======================================================================
 *
 * This file implements a subset of the WAVE audio file format.
 *
 * =======================================================================
 */

#include "../header/client.h"
#include "header/local.h"

static byte *data_p;
static byte *iff_end;
static byte *last_chunk;
static byte *iff_data;
static int iff_chunk_len;

static short
GetLittleShort(void)
{
	short val = 0;

	val = *data_p;
	val = val + (*(data_p + 1) << 8);
	data_p += 2;
	return val;
}

static int
GetLittleLong(void)
{
	int val = 0;

	val = *data_p;
	val = val + (*(data_p + 1) << 8);
	val = val + (*(data_p + 2) << 16);
	val = val + (*(data_p + 3) << 24);
	data_p += 4;
	return val;
}

static void
FindNextChunk(char *name)
{
	while (1)
	{
		data_p = last_chunk;
		data_p += 4;

		if (data_p >= iff_end)
		{
			data_p = NULL;
			return;
		}

		iff_chunk_len = GetLittleLong();

		if (iff_chunk_len < 0)
		{
			data_p = NULL;
			return;
		}

		data_p -= 8;
		last_chunk = data_p + 8 + ((iff_chunk_len + 1) & ~1);

		if (!strncmp((const char *)data_p, name, 4))
		{
			return;
		}
	}
}

static void
FindChunk(char *name)
{
	last_chunk = iff_data;
	FindNextChunk(name);
}

wavinfo_t
GetWavinfo(char *name, byte *wav, int wavlength)
{
	wavinfo_t info;
	int format;
	int frames;
	int loop_frames = 0;

	memset(&info, 0, sizeof(info));

	if (!wav)
	{
		return info;
	}

	iff_data = wav;
	iff_end = wav + wavlength;

	/* find "RIFF" chunk */
	FindChunk("RIFF");

	if (!(data_p && !strncmp((const char *)data_p + 8, "WAVE", 4)))
	{
		Com_Printf("Missing RIFF/WAVE chunks\n");
		return info;
	}

	/* get "fmt " chunk */
	iff_data = data_p + 12;

	FindChunk("fmt ");

	if (!data_p)
	{
		Com_Printf("Missing fmt chunk\n");
		return info;
	}

	data_p += 8;
	format = GetLittleShort();

	if (format != 1)
	{
		Com_Printf("Microsoft PCM format only\n");
		return info;
	}

	info.channels = GetLittleShort();
	info.rate = GetLittleLong();
	data_p += 4 + 2;
	info.width = GetLittleShort() / 8;

	if (info.channels < 1 || (info.width != 1 && info.width != 2))
	{
		memset(&info, 0, sizeof(info));
		return info;
	}

	/* get cue chunk */
	FindChunk("cue ");

	if (data_p)
	{
		data_p += 32;
		info.loopstart = GetLittleLong();

		/* if the next chunk is a LIST chunk,
		   look for a cue length marker */
		FindNextChunk("LIST");

		if (data_p)
		{
			if (((data_p - wav) + 32 <= wavlength) &&
				!strncmp((const char *)data_p + 28, "mark", 4))
			{
				int i;

				/* this is not a proper parse,
				   but it works with cooledit... */
				data_p += 24;
				i = GetLittleLong(); /* samples in loop */
				loop_frames = info.loopstart + i;
			}
		}
	}
	else
	{
		info.loopstart = -1;
	}

	/* find data chunk */
	FindChunk("data");

	if (!data_p)
	{
		Com_Printf("Missing data chunk\n");
		return info;
	}

	data_p += 4;
	frames = GetLittleLong() / (info.width * info.channels);

	if (loop_frames)
	{
		if (frames < loop_frames)
		{
			Com_Error(ERR_DROP, "%s: Sound %s has a bad loop length",
				__func__, name);
		}
		frames = loop_frames;
	}
	info.samples = frames * info.channels;
	info.dataofs = (int)(data_p - wav);

	return info;
}

