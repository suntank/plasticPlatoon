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
 * Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
 * 02111-1307, USA.
 *
 * =======================================================================
 *
 * This file implements the 2D stuff. For example the HUD and the
 * networkgraph.
 *
 * =======================================================================
 */

#include "header/client.h"
#include "header/performance.h"
#include "cl_splitscreen.h"
#include "input/header/aim_assist.h"

static float scr_con_current; /* aproaches scr_conlines at scr_conspeed */
static float scr_conlines; /* 0.0 to 1.0 lines of console to display */

static qboolean scr_initialized; /* ready to draw */

static int scr_draw_loading;

vrect_t scr_vrect; /* position of render window on screen */

cvar_t *scr_viewsize;
cvar_t *scr_conspeed;
cvar_t *scr_centertime;
cvar_t *scr_showturtle;
cvar_t *scr_showpause;

cvar_t *scr_netgraph;
cvar_t *scr_timegraph;
cvar_t *scr_debuggraph;
cvar_t *scr_graphheight;
cvar_t *scr_graphscale;
cvar_t *scr_graphshift;
cvar_t *scr_drawall;

cvar_t *r_hudscale; /* named for consistency with R1Q2 */
cvar_t *r_consolescale;
cvar_t *r_menuscale;
static cvar_t *scr_gamebird_hud;

typedef struct
{
	int x1, y1, x2, y2;
} dirty_t;

static dirty_t scr_dirty, scr_old_dirty[2];

static char crosshair_pic[MAX_QPATH];
static int crosshair_width, crosshair_height;

extern cvar_t *cl_showfps;
extern cvar_t *crosshair_scale;
extern cvar_t *cl_showspeed;
extern float GetPlayerSpeed(float *, float *);

static void SCR_TimeRefresh_f(void);
static void SCR_Loading_f(void);

#define CHAR_SIZE 8

/*
 * A new packet was just parsed
 */
void
CL_AddNetgraph(void)
{
	int i;
	int in;
	int ping;

	/* if using the debuggraph for something
	   else, don't add the net lines */
	if (scr_debuggraph->value || scr_timegraph->value)
	{
		return;
	}

	for (i = 0; i < cls.netchan.dropped; i++)
	{
		SCR_DebugGraph(30, 0x40);
	}

	for (i = 0; i < cl.surpressCount; i++)
	{
		SCR_DebugGraph(30, 0xdf);
	}

	/* see what the latency was on this packet */
	in = cls.netchan.incoming_acknowledged & (CMD_BACKUP - 1);
	ping = cls.realtime - cl.cmd_time[in];
	ping /= 30;

	if (ping > 30)
	{
		ping = 30;
	}

	SCR_DebugGraph((float)ping, 0xd0);
}

typedef struct
{
	float value;
	int color;
} graphsamp_t;

static int current;
static graphsamp_t values[2024];

void
SCR_DebugGraph(float value, int color)
{
	values[current & 2023].value = value;
	values[current & 2023].color = color;
	current++;
}

static void
SCR_DrawDebugGraph(void)
{
	int a, x, y, w, i, h;
	float v;
	int color;

	/* draw the graph */
	w = scr_vrect.width;

	x = scr_vrect.x;
	y = scr_vrect.y + scr_vrect.height;
	Draw_Fill(x, y - scr_graphheight->value,
			w, scr_graphheight->value, 8);

	for (a = 0; a < w; a++)
	{
		i = (current - 1 - a + 1024) & 1023;
		v = values[i].value;
		color = values[i].color;
		v = v * scr_graphscale->value + scr_graphshift->value;

		if (v < 0)
		{
			v += scr_graphheight->value *
				 (1 + (int)(-v / scr_graphheight->value));
		}

		h = (int)v % (int)scr_graphheight->value;
		Draw_Fill(x + w - 1 - a, y - h, 1, h, color);
	}
}

static char scr_centerstring[1024];
static float scr_centertime_start; /* for slow victory printing */
static float scr_centertime_off;
static int scr_center_lines;
static int scr_erase_center;

/*
 * Called for important messages that should stay
 * in the center of the screen for a few moments
 */
void
SCR_CenterPrint(char *str)
{
	char *s;

	Q_strlcpy(scr_centerstring, str, sizeof(scr_centerstring));
	scr_centertime_off = scr_centertime->value;
	scr_centertime_start = cl.time;

	/* count the number of lines for centering */
	scr_center_lines = 1;
	s = str;

	while (*s)
	{
		if (*s == '\n')
		{
			scr_center_lines++;
		}

		s++;
	}

	/* echo it to the console */
	Com_Printf("\n\n\35\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\37\n\n");

	s = str;

	do
	{
		char line[64];
		int i, j, l;

		/* scan the width of the line */
		for (l = 0; l < 40; l++)
		{
			if ((s[l] == '\n') || !s[l])
			{
				break;
			}
		}

		for (i = 0; i < (40 - l) / 2; i++)
		{
			line[i] = ' ';
		}

		for (j = 0; j < l; j++)
		{
			line[i++] = s[j];
		}

		line[i] = '\n';
		line[i + 1] = 0;

		Com_Printf("%s", line);

		while (*s && *s != '\n')
		{
			s++;
		}

		if (!*s)
		{
			break;
		}

		s++; /* skip the \n */
	}
	while (1);

	Com_Printf("\n\n\35\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\36\37\n\n");
	Con_ClearNotify();
}

static void
SCR_DrawCenterString(void)
{
	char *start;
	int l;
	int j;
	int x, y;
	int remaining;
	float scale;
    const int char_unscaled_width  = 8;
    const int char_unscaled_height = 8;

	/* the finale prints the characters one at a time */
	remaining = 9999;

	scr_erase_center = 0;
	start = scr_centerstring;
	scale = SCR_GetConsoleScale();

	if (scr_center_lines <= 4)
	{
		y = (viddef.height * 0.35) / scale;
	}

	else
	{
		y = 48 / scale;
	}

	do
	{
		/* scan the width of the line */
		for (l = 0; l < 40; l++)
		{
			if ((start[l] == '\n') || !start[l])
			{
				break;
			}
		}

		x = ((viddef.width / scale) - (l * char_unscaled_width)) / 2;
		SCR_AddDirtyPoint(x, y);

		for (j = 0; j < l; j++, x += char_unscaled_width)
		{
			Draw_CharScaled(x * scale, y * scale, start[j], scale);

			if (!remaining--)
			{
				return;
			}
		}

		SCR_AddDirtyPoint(x, y + char_unscaled_height);

		y += char_unscaled_height;

		while (*start && *start != '\n')
		{
			start++;
		}

		if (!*start)
		{
			break;
		}

		start++; /* skip the \n */
	}
	while (1);
}

static void
SCR_CheckDrawCenterString(void)
{
	scr_centertime_off -= cls.rframetime;

	if (scr_centertime_off <= 0)
	{
		return;
	}

	SCR_DrawCenterString();
}

/*
 * Sets scr_vrect, the coordinates of the rendered window
 */
static void
SCR_CalcVrect(void)
{
	int size;

	/* bound viewsize */
	if (scr_viewsize->value < 40)
	{
		Cvar_Set("viewsize", "40");
	}

	if (scr_viewsize->value > 100)
	{
		Cvar_Set("viewsize", "100");
	}

	size = scr_viewsize->value;

	scr_vrect.width = viddef.width * size / 100;
	scr_vrect.height = viddef.height * size / 100;

	scr_vrect.x = (viddef.width - scr_vrect.width) / 2;
	scr_vrect.y = (viddef.height - scr_vrect.height) / 2;
}

/*
 * Keybinding command
 */
static void
SCR_SizeUp_f(void)
{
	Cvar_SetValue("viewsize", (float)scr_viewsize->value + 10);
}

/*
 * Keybinding command
 */
static void
SCR_SizeDown_f(void)
{
	Cvar_SetValue("viewsize", (float)scr_viewsize->value - 10);
}

/*
 * Set a specific sky and rotation speed
 */
static void
SCR_Sky_f(void)
{
	float rotate = 0;
	vec3_t axis;

	if (Cmd_Argc() < 2)
	{
		Com_Printf("Usage: sky <basename> <rotate> <axis x y z>\n");
		return;
	}

	if (Cmd_Argc() > 2)
	{
		rotate = (float)strtod(Cmd_Argv(2), (char **)NULL);
	}

	else
	{
		rotate = 0;
	}

	if (Cmd_Argc() == 6)
	{
		axis[0] = (float)strtod(Cmd_Argv(3), (char **)NULL);
		axis[1] = (float)strtod(Cmd_Argv(4), (char **)NULL);
		axis[2] = (float)strtod(Cmd_Argv(5), (char **)NULL);
	}
	else
	{
		axis[0] = 0;
		axis[1] = 0;
		axis[2] = 1;
	}

	R_SetSky(Cmd_Argv(1), rotate, axis);
}

void
SCR_Init(void)
{
	scr_viewsize = Cvar_Get("viewsize", "100", CVAR_ARCHIVE);
	scr_conspeed = Cvar_Get("scr_conspeed", "3", 0);
	scr_centertime = Cvar_Get("scr_centertime", "2.5", 0);
	scr_showturtle = Cvar_Get("scr_showturtle", "0", 0);
	scr_showpause = Cvar_Get("scr_showpause", "1", 0);
	scr_netgraph = Cvar_Get("netgraph", "0", 0);
	scr_timegraph = Cvar_Get("timegraph", "0", 0);
	scr_debuggraph = Cvar_Get("debuggraph", "0", 0);
	scr_graphheight = Cvar_Get("graphheight", "32", 0);
	scr_graphscale = Cvar_Get("graphscale", "1", 0);
	scr_graphshift = Cvar_Get("graphshift", "0", 0);
	scr_drawall = Cvar_Get("scr_drawall", "0", 0);
	r_hudscale = Cvar_Get("r_hudscale", "-1", CVAR_ARCHIVE);
	r_consolescale = Cvar_Get("r_consolescale", "-1", CVAR_ARCHIVE);
	r_menuscale = Cvar_Get("r_menuscale", "-1", CVAR_ARCHIVE);
	scr_gamebird_hud = Cvar_Get("scr_gamebird_hud", "0", CVAR_ARCHIVE);

	/* register our commands */
	Cmd_AddCommand("timerefresh", SCR_TimeRefresh_f);
	Cmd_AddCommand("loading", SCR_Loading_f);
	Cmd_AddCommand("sizeup", SCR_SizeUp_f);
	Cmd_AddCommand("sizedown", SCR_SizeDown_f);
	Cmd_AddCommand("sky", SCR_Sky_f);

	scr_initialized = true;
}

static void
SCR_DrawNet(void)
{
	float scale = SCR_GetMenuScale();

	if (cls.netchan.outgoing_sequence - cls.netchan.incoming_acknowledged < CMD_BACKUP - 1)
	{
		return;
	}

	Draw_PicScaled(scr_vrect.x + 64 * scale, scr_vrect.y, "net", scale);
}

static void
SCR_DrawPause(void)
{
	int w, h;
	float scale = SCR_GetMenuScale();

	if (!scr_showpause->value) /* turn off for screenshots */
	{
		return;
	}

	if (!cl_paused->value)
	{
		return;
	}

	Draw_GetPicSize(&w, &h, "pause");
	Draw_PicScaled((viddef.width - w * scale) / 2, viddef.height / 2 + 8 * scale, "pause", scale);
}

static void
SCR_DrawLoading(void)
{
	int w, h;
	float scale = SCR_GetMenuScale();

	if (!scr_draw_loading)
	{
		return;
	}

	Draw_GetPicSize(&w, &h, "loading");
	Draw_PicScaled((viddef.width - w * scale) / 2, (viddef.height - h * scale) / 2, "loading", scale);
}

/*
 * Scroll it up or down
 */
void
SCR_RunConsole(void)
{
	/* src_conspeed must be a positiv integer,
	   otherwise things go wrong. Clamp it. */
	if (scr_conspeed->value < 0.1f)
	{
		Cvar_Set("scr_conspeed", "0.1");
	}

	/* decide on the height of the console */
	if (cls.key_dest == key_console)
	{
		scr_conlines = 0.5; /* half screen */
	}
	else
	{
		scr_conlines = 0; /* none visible */
	}

	if (scr_conlines < scr_con_current)
	{
		scr_con_current -= scr_conspeed->value * cls.rframetime;

		if (scr_conlines > scr_con_current)
		{
			scr_con_current = scr_conlines;
		}
	}
	else if (scr_conlines > scr_con_current)
	{
		scr_con_current += scr_conspeed->value * cls.rframetime;

		if (scr_conlines < scr_con_current)
		{
			scr_con_current = scr_conlines;
		}
	}
}

static void
SCR_DrawConsole(void)
{
	Con_CheckResize();

	if ((cls.state == ca_disconnected) || (cls.state == ca_connecting))
	{
		/* forced full screen console */
		Con_DrawConsole(1.0);
		return;
	}

	if ((cls.state != ca_active) || !cl.refresh_prepped)
	{
		/* connected, but can't render */
		Con_DrawConsole(0.5);
		Draw_Fill(0, viddef.height / 2, viddef.width, viddef.height / 2, 0);
		return;
	}

	if (scr_con_current)
	{
		Con_DrawConsole(scr_con_current);
	}
	else
	{
		if ((cls.key_dest == key_game) || (cls.key_dest == key_message))
		{
			Con_DrawNotify(); /* only draw notify in game */
		}
	}
}

void
SCR_BeginLoadingPlaque(void)
{
	S_StopAllSounds();
	cl.sound_prepped = false; /* don't play ambients */

	OGG_Stop();

	if (cls.disable_screen)
	{
		return;
	}

	if (developer->value)
	{
		/* Hack: When we are returning here (not drawing
		   the loading plaque) we don't reset the palette
		   later on. We might end up with the cinematic
		   palette applied to the world. Enforce the world
		   palette. */
		if (cl.cinematictime > 0)
		{
			R_SetPalette(NULL);
		}

		return;
	}

	if (cls.state == ca_disconnected)
	{
		/* if at console, don't bring up the plaque */
		return;
	}

	if (cls.key_dest == key_console)
	{
		return;
	}

	if (cl.cinematictime > 0)
	{
		scr_draw_loading = 2; /* clear to balack first */
	}
	else
	{
		scr_draw_loading = 1;
	}

	SCR_UpdateScreen();

	scr_draw_loading = false;

	SCR_StopCinematic();
	cls.disable_screen = Sys_Milliseconds();
	cls.disable_servercount = cl.servercount;
}

void
SCR_EndLoadingPlaque(void)
{
	cls.disable_screen = 0;
	Con_ClearNotify();
}

static void
SCR_Loading_f(void)
{
	SCR_BeginLoadingPlaque();
}

static void
SCR_TimeRefresh_f(void)
{
	int i;
	int start, stop;
	float time;

	if (cls.state != ca_active)
	{
		return;
	}

	start = Sys_Milliseconds();

	if (Cmd_Argc() == 2)
	{
		/* run without page flipping */
		int j;

		for (j = 0; j < 1000; j++)
		{
			R_BeginFrame(0);

			for (i = 0; i < 128; i++)
			{
				cl.refdef.viewangles[1] = i / 128.0f * 360.0f;
				R_RenderFrame(&cl.refdef);
			}

			R_EndFrame();
		}
	}
	else
	{
		for (i = 0; i < 128; i++)
		{
			cl.refdef.viewangles[1] = i / 128.0f * 360.0f;

			R_BeginFrame(0);
			R_RenderFrame(&cl.refdef);
			R_EndFrame();
		}
	}

	stop = Sys_Milliseconds();
	time = (stop - start) / 1000.0f;
	Com_Printf("%f seconds (%f fps)\n", time, 128 / time);
}

void
SCR_AddDirtyPoint(int x, int y)
{
	if (x < scr_dirty.x1)
	{
		scr_dirty.x1 = x;
	}

	if (x > scr_dirty.x2)
	{
		scr_dirty.x2 = x;
	}

	if (y < scr_dirty.y1)
	{
		scr_dirty.y1 = y;
	}

	if (y > scr_dirty.y2)
	{
		scr_dirty.y2 = y;
	}
}

void
SCR_DirtyScreen(void)
{
	SCR_AddDirtyPoint(0, 0);
	SCR_AddDirtyPoint(viddef.width - 1, viddef.height - 1);
}

/*
 * Clear any parts of the tiled background that were drawn on last frame
 */
static void
SCR_TileClear(void)
{
	int i;
	int top, bottom, left, right;
	dirty_t clear;

	if (scr_con_current == 1.0)
	{
		return; /* full screen console */
	}

	if (scr_viewsize->value == 100)
	{
		return; /* full screen rendering */
	}

	if (cl.cinematictime > 0)
	{
		return; /* full screen cinematic */
	}


	/* This highly complicated pseudo damage tracking is very effective
	   with the soft render, it gives about 10% speedup. On the GL
	   renderers the speedup is negligible, but in introduce a bug:
	   OpenGL requires to redraw the borders after every glClear(),
	   which the damage tracking doesn't take into account. Fix this
	   by not using the damage tracking when running somethinge else
	   than the soft renderer. Just redraw the borders every frame. */
	if (strcmp(vid_renderer->string, "soft") != 0) {
		// Top
		Draw_TileClear(scr_vrect.x, 0, scr_vrect.width, scr_vrect.y, "backtile");

		// Bottom
		Draw_TileClear(scr_vrect.x, scr_vrect.y + scr_vrect.height, scr_vrect.width, viddef.height, "backtile");

		// Left
		Draw_TileClear(0, 0, scr_vrect.x, viddef.height, "backtile");

		// Right
		Draw_TileClear(scr_vrect.x + scr_vrect.width, 0, viddef.width, viddef.height, "backtile");
	} else {
		/* erase rect will be the union of the past three
		   frames so tripple buffering works properly */
		clear = scr_dirty;

		for (i = 0; i < 2; i++)
		{
			if (scr_old_dirty[i].x1 < clear.x1)
			{
				clear.x1 = scr_old_dirty[i].x1;
			}

			if (scr_old_dirty[i].x2 > clear.x2)
			{
				clear.x2 = scr_old_dirty[i].x2;
			}

			if (scr_old_dirty[i].y1 < clear.y1)
			{
				clear.y1 = scr_old_dirty[i].y1;
			}

			if (scr_old_dirty[i].y2 > clear.y2)
			{
				clear.y2 = scr_old_dirty[i].y2;
			}
		}

		scr_old_dirty[1] = scr_old_dirty[0];
		scr_old_dirty[0] = scr_dirty;

		scr_dirty.x1 = 9999;
		scr_dirty.x2 = -9999;
		scr_dirty.y1 = 9999;
		scr_dirty.y2 = -9999;

		/* don't bother with anything convered by the console */
		top = (int)(scr_con_current * viddef.height);

		if (top >= clear.y1)
		{
			clear.y1 = top;
		}

		if (clear.y2 <= clear.y1)
		{
			return; /* nothing disturbed */
		}

		top = scr_vrect.y;
		bottom = top + scr_vrect.height - 1;
		left = scr_vrect.x;
		right = left + scr_vrect.width - 1;

		if (clear.y1 < top)
		{
			/* clear above view screen */
			i = clear.y2 < top - 1 ? clear.y2 : top - 1;
			Draw_TileClear(clear.x1, clear.y1,
					clear.x2 - clear.x1 + 1, i - clear.y1 + 1, "backtile");
			clear.y1 = top;
		}

		if (clear.y2 > bottom)
		{
			/* clear below view screen */
			i = clear.y1 > bottom + 1 ? clear.y1 : bottom + 1;
			Draw_TileClear(clear.x1, i,
					clear.x2 - clear.x1 + 1, clear.y2 - i + 1, "backtile");
			clear.y2 = bottom;
		}

		if (clear.x1 < left)
		{
			/* clear left of view screen */
			i = clear.x2 < left - 1 ? clear.x2 : left - 1;
			Draw_TileClear(clear.x1, clear.y1,
					i - clear.x1 + 1, clear.y2 - clear.y1 + 1, "backtile");
			clear.x1 = left;
		}

		if (clear.x2 > right)
		{
			/* clear left of view screen */
			i = clear.x1 > right + 1 ? clear.x1 : right + 1;
			Draw_TileClear(i, clear.y1,
					clear.x2 - i + 1, clear.y2 - clear.y1 + 1, "backtile");
			clear.x2 = right;
		}
	}
}

#define STAT_MINUS 10
static char *sb_nums[2][11] = {
	{
		"num_0", "num_1", "num_2", "num_3", "num_4", "num_5",
		"num_6", "num_7", "num_8", "num_9", "num_minus"
	},
	{
		"anum_0", "anum_1", "anum_2", "anum_3", "anum_4", "anum_5",
		"anum_6", "anum_7", "anum_8", "anum_9", "anum_minus"
	}
};

#define ICON_WIDTH 24
#define ICON_HEIGHT 24
#define CHARACTER_WIDTH 16
#define ICON_SPACE 8

/*
 * Allow embedded \n in the string
 */
void
SizeHUDString(char *string, int *w, int *h)
{
	int lines, width, current;

	lines = 1;
	width = 0;

	current = 0;

	while (*string)
	{
		if (*string == '\n')
		{
			lines++;
			current = 0;
		}
		else
		{
			current++;

			if (current > width)
			{
				width = current;
			}
		}

		string++;
	}

	*w = width * 8;
	*h = lines * 8;
}

static void
DrawHUDStringScaled(const char *string, int x, int y, int centerwidth, int xor, float factor)
{
	int margin;
	int i;
	qboolean wrap = scr_gamebird_hud && scr_gamebird_hud->value && centerwidth;
	/* The help panel is 256 virtual pixels wide; leave eight-pixel insets. */
	int maxwidth = wrap ? Q_max(1, Q_min(1023, (centerwidth - 80) / CHAR_SIZE)) : 1023;

	margin = x;

	while (*string)
	{
		/* scan out one line of text from the string */
		int width;
		char line[1024];

		width = 0;

		while (*string && *string != '\n' && width < maxwidth)
		{
			line[width++] = *string++;
		}
		if (wrap && width == maxwidth && *string && *string != '\n' && *string != ' ')
		{
			int split = width;
			while (split > 0 && line[split - 1] != ' ')
			{
				split--;
			}
			if (split > 0)
			{
				string -= width - split;
				width = split - 1;
			}
		}

		line[width] = 0;

		if (centerwidth)
		{
			x = margin + (centerwidth - width * 8)*factor / 2;
		}

		else
		{
			x = margin;
		}

		for (i = 0; i < width; i++)
		{
			Draw_CharScaled(x, y, line[i] ^ xor, factor);
			x += 8*factor;
		}

		if (*string)
		{
			if (wrap)
			{
				while (*string == ' ') string++;
			}
			if (*string == '\n') string++;
			y += CHAR_SIZE * factor;
		}
	}
}

void
DrawHUDString(char *string, int x, int y, int centerwidth, int xor)
{
	DrawHUDStringScaled(string, x, y, centerwidth, xor, 1.0f);
}

void
SCR_DrawFieldScaled(int x, int y, int color, int width, int value, float factor)
{
	char num[16], *ptr;
	int l;
	int frame;

	if (width < 1)
	{
		return;
	}

	/* draw number string */
	if (width > 5)
	{
		width = 5;
	}

	SCR_AddDirtyPoint(x, y);
	SCR_AddDirtyPoint(x + (width * CHARACTER_WIDTH + 2) * factor, y + factor * 24);

	Com_sprintf(num, sizeof(num), "%i", value);
	l = (int)strlen(num);

	if (l > width)
	{
		l = width;
	}

	x += (2 + CHARACTER_WIDTH * (width - l)) * factor;

	ptr = num;

	while (*ptr && l)
	{
		if (*ptr == '-')
		{
			frame = STAT_MINUS;
		}

		else
		{
			frame = *ptr - '0';
		}

		Draw_PicScaled(x, y, sb_nums[color][frame], factor);
		x += CHARACTER_WIDTH * factor;
		ptr++;
		l--;
	}
}

void
SCR_DrawField(int x, int y, int color, int width, int value)
{
	SCR_DrawFieldScaled(x, y, color, width, value, 1.0f);
}

/*
 * Allows rendering code to cache all needed sbar graphics
 */
void
SCR_TouchPics(void)
{
	int i, j;

	for (i = 0; i < 2; i++)
	{
		for (j = 0; j < 11; j++)
		{
			Draw_FindPic(sb_nums[i][j]);
		}
	}

	CL_TouchADSOverlayPics();

	if (crosshair->value)
	{
		if ((crosshair->value > 3) || (crosshair->value < 0))
		{
			crosshair->value = 3;
		}

		Com_sprintf(crosshair_pic, sizeof(crosshair_pic), "ch%i",
				(int)(crosshair->value));
		Draw_GetPicSize(&crosshair_width, &crosshair_height, crosshair_pic);

		if (!crosshair_width)
		{
			crosshair_pic[0] = 0;
		}
	}
}

static void
SCR_ExecuteLayoutString(char *s)
{
	int x, y;
	float scale;

	scale = SCR_GetHUDScale();
	if (scr_gamebird_hud && scr_gamebird_hud->value)
	{
		/* Help/objective layouts use a 320x240 canvas, too. */
		scale = fminf(scale, fminf(viddef.width / 320.0f, viddef.height / 240.0f));
	}

	if ((cls.state != ca_active) || !cl.refresh_prepped)
	{
		return;
	}

	if (!s[0])
	{
		return;
	}

	x = 0;
	y = 0;

	while (s)
	{
		const char *token;

		token = COM_Parse(&s);

		if (!strcmp(token, "xl"))
		{
			token = COM_Parse(&s);
			x = scale * (int)strtol(token, (char **)NULL, 10);
			continue;
		}

		if (!strcmp(token, "xr"))
		{
			token = COM_Parse(&s);
			x = viddef.width + scale * (int)strtol(token, (char **)NULL, 10);
			continue;
		}

		if (!strcmp(token, "xv"))
		{
			token = COM_Parse(&s);
			x = viddef.width / 2 - scale * 160 + scale * (int)strtol(token, (char **)NULL, 10);
			continue;
		}

		if (!strcmp(token, "yt"))
		{
			token = COM_Parse(&s);
			y = scale * (int)strtol(token, (char **)NULL, 10);
			continue;
		}

		if (!strcmp(token, "yb"))
		{
			token = COM_Parse(&s);
			y = viddef.height + scale * (int)strtol(token, (char **)NULL, 10);
			continue;
		}

		if (!strcmp(token, "yv"))
		{
			token = COM_Parse(&s);
			y = viddef.height / 2 - scale * 120 + scale * (int)strtol(token, (char **)NULL, 10);
			continue;
		}

		if (!strcmp(token, "pic"))
		{
			int index, value;

			/* draw a pic from a stat number */
			token = COM_Parse(&s);
			index = (int)strtol(token, (char **)NULL, 10);

			if ((index < 0) || (index >= MAX_STATS))
			{
				Com_DPrintf("%s: bad stats index %d (0x%x) in pic\n",
					__func__, index, index);
				continue;
			}

			value = cl.frame.playerstate.stats[index];

			if (value >= MAX_IMAGES)
			{
				Com_DPrintf("%s: Pic %d >= MAX_IMAGES in pic\n",
					__func__, value);
				continue;
			}

			if (cl.configstrings[CS_IMAGES + value][0] != '\0')
			{
				const char *text;
				int w, h;

				text = cl.configstrings[CS_IMAGES + value];
				Draw_GetPicSize(&w, &h, text);
				SCR_AddDirtyPoint(x, y);
				SCR_AddDirtyPoint(x + (w - 1) * scale, y + (h - 1) * scale);
				Draw_PicScaled(x, y, text, scale);
			}

			continue;
		}

		if (!strcmp(token, "client"))
		{
			/* draw a deathmatch client block */
			int score, ping, time, value;
			clientinfo_t *ci;

			token = COM_Parse(&s);
			x = viddef.width / 2 - scale * 160 + scale * (int)strtol(token, (char **)NULL, 10);
			token = COM_Parse(&s);
			y = viddef.height / 2 - scale * 120 + scale * (int)strtol(token, (char **)NULL, 10);
			SCR_AddDirtyPoint(x, y);
			SCR_AddDirtyPoint(x + scale * 159, y + scale * 31);

			token = COM_Parse(&s);
			value = (int)strtol(token, (char **)NULL, 10);

			if ((value >= MAX_CLIENTS) || (value < 0))
			{
				Com_DPrintf("%s: client >= MAX_CLIENTS in client\n", __func__);
				continue;
			}

			ci = &cl.clientinfo[value];

			token = COM_Parse(&s);
			score = (int)strtol(token, (char **)NULL, 10);

			token = COM_Parse(&s);
			ping = (int)strtol(token, (char **)NULL, 10);

			token = COM_Parse(&s);
			time = (int)strtol(token, (char **)NULL, 10);

			DrawAltStringScaled(x + scale * 32, y, ci->name, scale);
			DrawAltStringScaled(x + scale * 32, y + scale * CHAR_SIZE, "Score: ", scale);
			DrawAltStringScaled(x + scale * (32 + 7 * CHAR_SIZE), y + scale * CHAR_SIZE, va("%i", score), scale);
			DrawStringScaled(x + scale * 32, y + scale * 16, va("Ping:  %i", ping), scale);
			DrawStringScaled(x + scale * 32, y + scale * 24, va("Time:  %i", time), scale);

			if (!ci->icon)
			{
				ci = &cl.baseclientinfo;
			}

			Draw_PicScaled(x, y, ci->iconname, scale);
			continue;
		}

		if (!strcmp(token, "ctf"))
		{
			/* draw a ctf client block */
			int score, ping, value;
			clientinfo_t *ci;
			char block[80];

			token = COM_Parse(&s);
			x = viddef.width / 2 - scale * 160 + scale*(int)strtol(token, (char **)NULL, 10);
			token = COM_Parse(&s);
			y = viddef.height / 2 - scale * 120 + scale*(int)strtol(token, (char **)NULL, 10);
			SCR_AddDirtyPoint(x, y);
			SCR_AddDirtyPoint(x + scale * 159, y + scale * 31);

			token = COM_Parse(&s);
			value = (int)strtol(token, (char **)NULL, 10);

			if ((value >= MAX_CLIENTS) || (value < 0))
			{
				Com_DPrintf("%s: client >= MAX_CLIENTS in client\n", __func__);
				continue;
			}

			ci = &cl.clientinfo[value];

			token = COM_Parse(&s);
			score = (int)strtol(token, (char **)NULL, 10);

			token = COM_Parse(&s);
			ping = (int)strtol(token, (char **)NULL, 10);

			if (ping > 999)
			{
				ping = 999;
			}

			sprintf(block, "%3d %3d %-12.12s", score, ping, ci->name);

			if (value == cl.playernum)
			{
				DrawAltStringScaled(x, y, block, scale);
			}

			else
			{
				DrawStringScaled(x, y, block, scale);
			}

			continue;
		}

		if (!strcmp(token, "picn"))
		{
			int w, h;

			/* draw a pic from a name */
			token = COM_Parse(&s);
			Draw_GetPicSize(&w, &h, token);
			SCR_AddDirtyPoint(x, y);
			SCR_AddDirtyPoint(x + scale * (w - 1), y + scale * (h - 1));
			Draw_PicScaled(x, y, token, scale);
			continue;
		}

		if (!strcmp(token, "num"))
		{
			int value, width;

			/* draw a number */
			token = COM_Parse(&s);
			width = (int)strtol(token, (char **)NULL, 10);
			token = COM_Parse(&s);
			value = cl.frame.playerstate.stats[(int)strtol(token, (char **)NULL, 10)];
			SCR_DrawFieldScaled(x, y, 0, width, value, scale);
			continue;
		}

		if (!strcmp(token, "hnum"))
		{
			/* health number */
			int color, value, width;

			width = 3;
			value = cl.frame.playerstate.stats[STAT_HEALTH];

			if (value > 25)
			{
				color = 0;  /* green */
			}
			else if (value > 0)
			{
				color = (cl.frame.serverframe >> 2) & 1; /* flash */
			}
			else
			{
				color = 1;
			}

			if (cl.frame.playerstate.stats[STAT_FLASHES] & 1)
			{
				Draw_PicScaled(x, y, "field_3", scale);
			}

			SCR_DrawFieldScaled(x, y, color, width, value, scale);
			continue;
		}

		if (!strcmp(token, "anum"))
		{
			/* ammo number */
			int color, value, width;

			width = 3;
			value = cl.frame.playerstate.stats[STAT_AMMO];

			if (value > 5)
			{
				color = 0; /* green */
			}
			else if (value >= 0)
			{
				color = (cl.frame.serverframe >> 2) & 1; /* flash */
			}
			else
			{
				continue; /* negative number = don't show */
			}

			if (cl.frame.playerstate.stats[STAT_FLASHES] & 4)
			{
				Draw_PicScaled(x, y, "field_3", scale);
			}

			SCR_DrawFieldScaled(x, y, color, width, value, scale);
			continue;
		}

		if (!strcmp(token, "rnum"))
		{
			/* armor number */
			int color, value, width;

			width = 3;
			value = cl.frame.playerstate.stats[STAT_ARMOR];

			if (value < 1)
			{
				continue;
			}

			color = 0; /* green */

			if (cl.frame.playerstate.stats[STAT_FLASHES] & 2)
			{
				Draw_PicScaled(x, y, "field_3", scale);
			}

			SCR_DrawFieldScaled(x, y, color, width, value, scale);
			continue;
		}

		if (!strcmp(token, "stat_string"))
		{
			int index;

			token = COM_Parse(&s);
			index = (int)strtol(token, (char **)NULL, 10);

			if ((index < 0) || (index >= MAX_STATS))
			{
				Com_DPrintf("%s: bad stats index %d (0x%x) in stat_string\n",
					__func__, index, index);
				continue;
			}

			index = cl.frame.playerstate.stats[index];

			if ((index < 0) || (index >= MAX_CONFIGSTRINGS))
			{
				Com_DPrintf("%s: bad stats index %d (0x%x) in stat_string\n",
					__func__, index, index);
				continue;
			}

			DrawStringScaled(x, y, cl.configstrings[index], scale);
			continue;
		}

		if (!strcmp(token, "cstring"))
		{
			token = COM_Parse(&s);
			DrawHUDStringScaled(token, x, y, 320, 0, scale); // FIXME: or scale 320 here?
			continue;
		}

		if (!strcmp(token, "string"))
		{
			token = COM_Parse(&s);
			DrawStringScaled(x, y, token, scale);
			continue;
		}

		if (!strcmp(token, "cstring2"))
		{
			token = COM_Parse(&s);
			DrawHUDStringScaled(token, x, y, 320, 0x80, scale); // FIXME: or scale 320 here?
			continue;
		}

		if (!strcmp(token, "string2"))
		{
			token = COM_Parse(&s);
			DrawAltStringScaled(x, y, token, scale);
			continue;
		}

		if (!strcmp(token, "if"))
		{
			int index, value;

			/* draw a number */
			token = COM_Parse(&s);
			index = (int)strtol(token, (char **)NULL, 10);

			if ((index < 0) || (index >= MAX_STATS))
			{
				Com_DPrintf("%s: bad stats index %d (0x%x) in if\n",
					__func__, index, index);
				value = 0;
			}
			else
			{
				value = cl.frame.playerstate.stats[index];
			}

			if (!value)
			{
				/* skip to endif */
				while (s && strcmp(token, "endif"))
				{
					token = COM_Parse(&s);
				}
			}

			continue;
		}

		if (!strcmp(token, "endif") || !token[0])
		{
			/* just skip endif and empty line */
			continue;
		}

		Com_DPrintf("%s: Unknown token: %s\n", __func__, token);
	}
}

void
SCR_DrawGrenadeHUD(const player_state_t *ps, int right, int y, float scale)
{
	int index = ps->stats[STAT_GRENADE_ICON];
	const char *icon;
	int icon_w, icon_h;
	int icon_x, count_x, count_y;
	const int digits = 3;

	if (scale <= 0 || index <= 0 || index >= MAX_IMAGES)
	{
		return;
	}

	/* Other game modules may use this stat slot for a different purpose. */
	icon = cl.configstrings[CS_IMAGES + index];
	if (strcmp(icon, "a_grenades"))
	{
		return;
	}

	Draw_GetPicSize(&icon_w, &icon_h, icon);
	if (icon_w <= 0 || icon_h <= 0)
	{
		return;
	}

	icon_x = right - (int)(icon_w * scale);
	count_x = icon_x - (int)((digits * CHARACTER_WIDTH + 2) * scale);
	count_y = y + (int)((icon_h - 24) * scale / 2);
	Draw_PicScaled(count_x, count_y, "field_3", scale);
	SCR_DrawFieldScaled(count_x, count_y, 0, digits, ps->stats[STAT_GRENADES], scale);

	SCR_AddDirtyPoint(icon_x, y);
	SCR_AddDirtyPoint(right - 1, y + (int)(icon_h * scale) - 1);
	Draw_PicScaled(icon_x, y, icon, scale);
}

static const char *
SCR_GameBirdStatIcon(const player_state_t *ps, int stat, const char *fallback)
{
	int index = ps->stats[stat];
	if (index > 0 && index < MAX_IMAGES && cl.configstrings[CS_IMAGES + index][0])
	{
		return cl.configstrings[CS_IMAGES + index];
	}
	return fallback;
}

static void
SCR_DrawGameBirdStat(const player_state_t *ps, int column, int stat, int icon_stat,
	const char *fallback, int color, int flash, float scale, int margin)
{
	const char *icon = SCR_GameBirdStatIcon(ps, icon_stat, fallback);
	int icon_w, icon_h, field_w, group_w, group_h, x, y;

	Draw_GetPicSize(&icon_w, &icon_h, icon);
	if (icon_w < 0 || icon_h < 0)
	{
		icon_w = icon_h = 0;
	}
	field_w = (int)((3 * CHARACTER_WIDTH + 2) * scale);
	group_w = field_w + (int)((icon_w + 2) * scale);
	group_h = (int)((icon_h > 24 ? icon_h : 24) * scale);
	x = (2 * column + 1) * viddef.width / 6 - group_w / 2;
	y = viddef.height - margin - group_h;
	SCR_AddDirtyPoint(x, y);
	SCR_AddDirtyPoint(x + group_w - 1, y + group_h - 1);

	if (ps->stats[STAT_FLASHES] & flash)
	{
		Draw_PicScaled(x, y + (group_h - (int)(24 * scale)) / 2, "field_3", scale);
	}
	SCR_DrawFieldScaled(x, y + (group_h - (int)(24 * scale)) / 2,
		color, 3, ps->stats[stat], scale);
	if (icon_w > 0 && icon_h > 0)
	{
		Draw_PicScaled(x + field_w + (int)(2 * scale), y, icon, scale);
	}
}

static void
SCR_DrawGameBirdStats(void)
{
	const player_state_t *ps = &cl.frame.playerstate;
	float scale = fminf(SCR_GetHUDScale(),
		fminf(viddef.width / 320.0f, viddef.height / 240.0f));
	int margin = 4;
	int health_color, ammo_color;
	const char *icon;
	int icon_w, icon_h;

	if (cls.state != ca_active || !cl.refresh_prepped || scale <= 0)
	{
		return;
	}
	/* Keep the three columns stable when armor/ammo are empty. */
	health_color = ps->stats[STAT_HEALTH] > 25 ? 0 :
		(ps->stats[STAT_HEALTH] > 0 ? (cl.frame.serverframe >> 2) & 1 : 1);
	ammo_color = ps->stats[STAT_AMMO] > 5 ? 0 : (cl.frame.serverframe >> 2) & 1;
	SCR_DrawGameBirdStat(ps, 0, STAT_HEALTH, STAT_HEALTH_ICON, "i_health",
		health_color, 1, scale, margin);
	SCR_DrawGameBirdStat(ps, 1, STAT_ARMOR, STAT_ARMOR_ICON, "i_jacketarmor",
		0, 2, scale, margin);
	if (ps->stats[STAT_AMMO] >= 0)
	{
		SCR_DrawGameBirdStat(ps, 2, STAT_AMMO, STAT_AMMO_ICON, "a_bullets",
			ammo_color, 4, scale, margin);
	}
	SCR_DrawGrenadeHUD(ps, viddef.width - margin, margin, scale);

	/* Keep transient status information above the bottom row. */
	if (ps->stats[STAT_TIMER] > 0)
	{
		icon = SCR_GameBirdStatIcon(ps, STAT_TIMER_ICON, "");
		SCR_DrawFieldScaled(margin, margin, 0, 2, ps->stats[STAT_TIMER], scale);
		if (icon[0])
		{
			Draw_PicScaled(margin + (int)(36 * scale), margin, icon, scale);
		}
	}
	if (ps->stats[STAT_PICKUP_STRING] > 0 && ps->stats[STAT_PICKUP_STRING] < MAX_CONFIGSTRINGS)
	{
		char text[64];
		int columns = (viddef.width - 2 * margin) / (8 * scale);
		Q_strlcpy(text, cl.configstrings[ps->stats[STAT_PICKUP_STRING]],
			(size_t)Q_min(columns + 1, (int)sizeof(text)));
		DrawStringScaled((viddef.width - (int)(strlen(text) * 8 * scale)) / 2,
			viddef.height - margin - (int)(52 * scale), text, scale);
	}
	icon = SCR_GameBirdStatIcon(ps, STAT_HELPICON, "");
	if (icon[0])
	{
		Draw_GetPicSize(&icon_w, &icon_h, icon);
		if (icon_w > 0 && icon_h > 0)
		{
			Draw_PicScaled((viddef.width - (int)(icon_w * scale)) / 2,
				viddef.height - margin - (int)((icon_h + 38) * scale), icon, scale);
		}
	}
	icon = SCR_GameBirdStatIcon(ps, STAT_SELECTED_ICON, "");
	if (icon[0])
	{
		Draw_PicScaled(margin, margin + (int)(36 * scale), icon, scale);
	}
	if (ps->stats[STAT_FRAGS] || ps->stats[STAT_SPECTATOR])
	{
		DrawStringScaled(margin, viddef.height - margin - (int)(68 * scale),
			ps->stats[STAT_SPECTATOR] ? "SPECTATOR" : va("FRAGS %d", ps->stats[STAT_FRAGS]), scale);
	}
}

/*
 * The status bar is a small layout program that
 * is based on the stats array
 */
static void
SCR_DrawStats(void)
{
	if (scr_gamebird_hud && scr_gamebird_hud->value)
	{
		SCR_DrawGameBirdStats();
		return;
	}
	SCR_ExecuteLayoutString(cl.configstrings[CS_STATUSBAR]);

	/* Saved levels can restore a status bar from before the grenade HUD. */
	if (cls.state == ca_active && cl.refresh_prepped)
	{
		float scale = SCR_GetHUDScale();

		SCR_DrawGrenadeHUD(&cl.frame.playerstate, viddef.width / 2 + (int)(122 * scale),
			viddef.height - (int)(84 * scale), scale);
	}
}

#define STAT_LAYOUTS 13

static void
SCR_DrawLayout(void)
{
	if (!cl.frame.playerstate.stats[STAT_LAYOUTS])
	{
		return;
	}

	SCR_ExecuteLayoutString(cl.layout);
}

static void
SCR_DrawADSOverlay(void)
{
	const char *overlay_pic;
	static int ads_last_muzzle_seq = 0;
	static float ads_kick_offset = 0.0f;
	const float ads_kick_impulse = 20.0f;
	const float ads_kick_return_speed = 68.0f;
	const float ads_kick_max = 40.0f;
	qboolean kick_enabled;
	int kick_y = 0;

	if (!CL_IsADSActive())
	{
		ads_kick_offset = 0.0f;
		ads_last_muzzle_seq = pp_viewmodel_muzzle_seq;
		return;
	}

	overlay_pic = CL_PlayerADSPic(CL_ColorClientinfo(cl.playernum), CL_GetADSOverlayPicName());
	if (!overlay_pic)
	{
		ads_kick_offset = 0.0f;
		ads_last_muzzle_seq = pp_viewmodel_muzzle_seq;
		return;
	}

	if (!Draw_FindPic(overlay_pic))
	{
		ads_kick_offset = 0.0f;
		ads_last_muzzle_seq = pp_viewmodel_muzzle_seq;
		return;
	}

	kick_enabled = Q_stricmp(CL_GetADSOverlayPicName(), "ads_railgun.png") != 0;

	if (kick_enabled)
	{
		if (pp_viewmodel_muzzle_seq != ads_last_muzzle_seq)
		{
			ads_kick_offset += ads_kick_impulse;
			if (ads_kick_offset > ads_kick_max)
			{
				ads_kick_offset = ads_kick_max;
			}
		}

		ads_kick_offset -= ads_kick_return_speed * cls.rframetime;
		if (ads_kick_offset < 0.0f)
		{
			ads_kick_offset = 0.0f;
		}

		kick_y = (int)(ads_kick_offset + 0.5f);
	}
	else
	{
		ads_kick_offset = 0.0f;
	}

	ads_last_muzzle_seq = pp_viewmodel_muzzle_seq;

	Draw_StretchPic(0, kick_y, viddef.width, viddef.height, overlay_pic);
	SCR_AddDirtyPoint(0, 0);
	SCR_AddDirtyPoint(viddef.width - 1, viddef.height - 1);
}

void
SCR_DrawScreenImageOverlay(const cl_screen_image_t *image,
	int x, int y, int width, int height)
{
	int pic_w = 0, pic_h = 0;
	int draw_w, draw_h, draw_x, draw_y;
	double w, h, scale;

	if (!image || !image->pic[0] || width <= 0 || height <= 0 ||
		(int)(image->endtime - (unsigned int)cls.realtime) <= 0)
	{
		return;
	}

	if (!Draw_FindPic(image->pic))
	{
		return;
	}

	Draw_GetPicSize(&pic_w, &pic_h, image->pic);
	if (pic_w <= 0 || pic_h <= 0)
	{
		return;
	}

	w = image->width > 0 ? image->width : pic_w;
	h = image->height > 0 ? image->height : pic_h;
	if (image->width <= 0 && image->height > 0)
	{
		w = (double)pic_w * h / pic_h;
	}
	else if (image->height <= 0 && image->width > 0)
	{
		h = (double)pic_h * w / pic_w;
	}

	/* Fit the complete image inside this player's viewport, preserving aspect. */
	scale = fmin(1.0, fmin(width / w, height / h));
	draw_w = (int)(w * scale);
	draw_h = (int)(h * scale);
	if (draw_w <= 0 || draw_h <= 0)
	{
		return;
	}

	draw_x = x + (width - draw_w) / 2;
	draw_y = y + (height - draw_h) / 2;
	Draw_StretchPic(draw_x, draw_y, draw_w, draw_h, image->pic);
	SCR_AddDirtyPoint(draw_x, draw_y);
	SCR_AddDirtyPoint(draw_x + draw_w - 1, draw_y + draw_h - 1);
}

// ----

static void
SCR_DrawSpeed(void)
{
	if (cl_showspeed->value < 1)  //Disabled, do nothing
		return;

	char spd_str[32];
	float speed, speedxy;
	float scale = SCR_GetConsoleScale();
	int str_len, xPos, yPos = 0;

	GetPlayerSpeed(&speed, &speedxy);
	snprintf(spd_str, sizeof(spd_str), "%6.2f (%6.2f) QU/s", speed, speedxy);
	str_len = scale * (strlen(spd_str) * CHAR_SIZE + 2);

	if (cl_showspeed->value == 1) //Draw speed and xy speed at top right
	{
		xPos = viddef.width - str_len;

		if (cl_showfps->value == 1 || cl_showfps->value == 2)  // If showfps is enabled, draw it underneath
		{
			yPos = scale * 10;
		}
		else if (cl_showfps->value > 2)
		{
			yPos = scale * 20;
		}

		DrawStringScaled(xPos, yPos, spd_str, scale);
		SCR_AddDirtyPoint(xPos, yPos);
		SCR_AddDirtyPoint(viddef.width, yPos);
	}

	else if (cl_showspeed->value > 1) //Draw only xy speed under the crosshair
	{
		if (scale != 1)  // Check if low resolution
		{
			scale -= 1;
		}

		snprintf(spd_str, sizeof(spd_str), "%6.2f", speedxy);
		str_len = scale * (strlen(spd_str) * CHAR_SIZE + 2);
		yPos = scr_vrect.y + (scr_vrect.height / 2) + (scale * 10);
		xPos = scr_vrect.x + (scr_vrect.width / 2) - (str_len / 2);
		
		DrawStringScaled(xPos, yPos, spd_str, scale);
		SCR_AddDirtyPoint(xPos, yPos);
		SCR_AddDirtyPoint(xPos + str_len, yPos);
	}
}

static void
SCR_Framecounter(void)
{
	long long newtime;
	static int frame;
	static int frametimes[60] = {0};
	static long long oldtime;

	/* skip statistics without show fps */
	if (cl_showfps->value < 1)
	{
		return;
	}

	newtime = Sys_Microseconds();
	frametimes[frame] = (int)(newtime - oldtime);

	oldtime = newtime;
	frame++;
	if (frame > 59)
	{
		frame = 0;
	}

	float scale = SCR_GetConsoleScale();

	if (cl_showfps->value == 1)
	{
		// Calculate average of frames.
		char str[10];
		int avg = 0;
		int num = 0;

		for (int i = 0; i < 60; i++) {
			if (frametimes[i] != 0) {
				avg += frametimes[i];
				num++;
			}
		}

		snprintf(str, sizeof(str), "%3.2ffps", (1000.0 * 1000.0) / (avg / num));
		DrawStringScaled(viddef.width - scale * (strlen(str) * CHAR_SIZE + 2), 0, str, scale);
		SCR_AddDirtyPoint(viddef.width - scale * (strlen(str) * CHAR_SIZE + 2), 0);
		SCR_AddDirtyPoint(viddef.width, 0);
	}
	else if (cl_showfps->value >= 2)
	{
		// Calculate average of frames.
		int avg = 0;
		int num = 0;
		char str[64];

		for (int i = 0; i < 60; i++) {
			if (frametimes[i] != 0) {
				avg += frametimes[i];
				num++;
			}
		}

		// Find lowest and highest
		int min = frametimes[0];
		int max = frametimes[1];

		for (int i = 1; i < 60; i++)
		{
			if ((frametimes[i] > 0) &&  (min < frametimes[i]))
			{
				min = frametimes[i];
			}

			if ((frametimes[i] > 0) && (max > frametimes[i]))
			{
				max = frametimes[i];
			}
		}

		snprintf(str, sizeof(str), "Min: %7.2ffps, Max: %7.2ffps, Avg: %7.2ffps",
		         (1000.0 * 1000.0) / min, (1000.0 * 1000.0) / max, (1000.0 * 1000.0) / (avg / num));
		DrawStringScaled(viddef.width - scale * (strlen(str) * CHAR_SIZE + 2), 0, str, scale);
		SCR_AddDirtyPoint(viddef.width - scale * (strlen(str) * CHAR_SIZE + 2), 0);
		SCR_AddDirtyPoint(viddef.width, 0);

		if (cl_showfps->value > 2)
		{
			snprintf(str, sizeof(str), "Max: %5.2fms, Min: %5.2fms, Avg: %5.2fms",
			         0.001f * min, 0.001f * max, 0.001f * ((float)avg / num));
			DrawStringScaled(viddef.width - scale * (strlen(str) * CHAR_SIZE + 2), scale * 10, str, scale);
			SCR_AddDirtyPoint(viddef.width - scale * (strlen(str) * CHAR_SIZE + 2), scale * 10);
			SCR_AddDirtyPoint(viddef.width, scale + 10);
		}
	}
}

// ----
/*
 * This is called every frame, and can also be called
 * explicitly to flush text to the screen.
 */
void
SCR_UpdateScreen(void)
{
	int numframes;
	int i;
	float separation[2] = {0, 0};
	float scale = SCR_GetMenuScale();

	/* if the screen is disabled (loading plaque is
	   up, or vid mode changing) do nothing at all */
	if (cls.disable_screen)
	{
		if (Sys_Milliseconds() - cls.disable_screen > 120000)
		{
			cls.disable_screen = 0;
			Com_Printf("Loading plaque timed out.\n");
		}

		return;
	}

	if (!scr_initialized || !con.initialized)
	{
		return; /* not initialized yet */
	}

	CL_PerfBeginDisplay();
	if (gl1_stereo->value && !SS_IsSessionActive())
	{
		numframes = 2;
		separation[0] = -gl1_stereo_separation->value / 2;
		separation[1] = +gl1_stereo_separation->value / 2;
	}
	else
	{
		separation[0] = 0;
		separation[1] = 0;
		numframes = 1;
	}

	for (i = 0; i < numframes; i++)
	{
		R_BeginFrame(separation[i]);

		if (scr_draw_loading == 2)
		{
			/* loading plaque over black screen */
			int w, h;

			R_EndWorldRenderpass();
			if(i == 0){
				R_SetPalette(NULL);
			}

			if(i == numframes - 1){
				scr_draw_loading = false;
			}

			Draw_GetPicSize(&w, &h, "loading");
			Draw_PicScaled((viddef.width - w * scale) / 2, (viddef.height - h * scale) / 2, "loading", scale);
		}

		/* if a cinematic is supposed to be running,
		   handle menus and console specially */
		else if (cl.cinematictime > 0)
		{
			if (cls.key_dest == key_menu)
			{
				if (cl.cinematicpalette_active)
				{
					R_SetPalette(NULL);
					cl.cinematicpalette_active = false;
				}

				R_EndWorldRenderpass();
				M_Draw();
			}
			else if (cls.key_dest == key_console)
			{
				if (cl.cinematicpalette_active)
				{
					R_SetPalette(NULL);
					cl.cinematicpalette_active = false;
				}

				R_EndWorldRenderpass();
				SCR_DrawConsole();
			}
			else
			{
				R_EndWorldRenderpass();
				SCR_DrawCinematic();
			}
		}
		else
		{
			/* make sure the game palette is active */
			if (cl.cinematicpalette_active)
			{
				R_SetPalette(NULL);
				cl.cinematicpalette_active = false;
			}

			/* do 3D refresh drawing, and then update the screen */
			SCR_CalcVrect();

			/* clear any dirty part of the background */
			SCR_TileClear();

			if (SS_RenderViews(separation[i]))
			{
				SS_DrawGameplayHUD();

				if (cl.frame.playerstate.stats[STAT_LAYOUTS] & 1)
				{
					SCR_DrawLayout();
				}

				if (cl.frame.playerstate.stats[STAT_LAYOUTS] & 2)
				{
					CL_DrawInventory();
				}

				SCR_DrawNet();
				SCR_CheckDrawCenterString();
			}
			else
			{
				V_RenderView(separation[i]);
				SCR_DrawADSOverlay();

				SCR_DrawStats();
				SCR_DrawSpeed();

				if (cl.frame.playerstate.stats[STAT_LAYOUTS] & 1)
				{
					SCR_DrawLayout();
				}

				if (cl.frame.playerstate.stats[STAT_LAYOUTS] & 2)
				{
					CL_DrawInventory();
				}

				SCR_DrawScreenImageOverlay(&cl.screen_image, 0, 0, viddef.width, viddef.height);
				SCR_DrawNet();
				SCR_CheckDrawCenterString();
			}

			if (scr_timegraph->value)
			{
				SCR_DebugGraph(cls.rframetime * 300, 0);
			}

			if (scr_debuggraph->value || scr_timegraph->value ||
				scr_netgraph->value)
			{
				SCR_DrawDebugGraph();
			}

			SCR_DrawPause();

			SCR_DrawConsole();

			M_Draw();
			SS_DrawSessionOverlay();

			SCR_DrawLoading();
		}
	}

	SCR_Framecounter();
	CL_PerfBeginPresent();
	R_EndFrame();
	CL_PerfEndPresent();
	CL_PerfEndDisplay();
}

static float
SCR_ClampScale(float scale)
{
	float f;

	f = viddef.width / 320.0f;
	if (scale > f)
	{
		scale = f;
	}

	f = viddef.height / 240.0f;
	if (scale > f)
	{
		scale = f;
	}

	if (scale < 1)
	{
		scale = 1;
	}

	return scale;
}

static float
SCR_GetDefaultScale(void)
{
	int i = viddef.width / 640;
	int j = viddef.height / 240;

	if (i > j)
	{
		i = j;
	}
	if (i < 1)
	{
		i = 1;
	}

	return i;
}

void
SCR_DrawCrosshair(void)
{
	float scale;
	float assist_x, assist_y;

	if (!crosshair->value || (CL_UsesModelADS(&cl.frame.playerstate) && CL_IsADSActive()))
	{
		return;
	}

	if (crosshair->modified)
	{
		crosshair->modified = false;
		SCR_TouchPics();
	}

	if (!crosshair_pic[0])
	{
		return;
	}

	if (crosshair_scale->value < 0)
	{
		scale = SCR_GetDefaultScale();
	}
	else
	{
		scale = SCR_ClampScale(crosshair_scale->value);
	}

	PP_AimAssistReticle(&cl.frame.playerstate, scr_vrect.width, scr_vrect.height,
		cl.refdef.fov_x, cl.refdef.fov_y, Key_UsingGamepad() &&
		!CL_IsADSActive() && Cvar_VariableValue("cl_aimassist") > 0, &assist_x, &assist_y);
	Draw_PicScaled(scr_vrect.x + (scr_vrect.width - crosshair_width * scale) / 2 + (int)assist_x,
			scr_vrect.y + (scr_vrect.height - crosshair_height * scale) / 2 + (int)assist_y,
			crosshair_pic, scale);
}

float
SCR_GetHUDScale(void)
{
	float scale;

	if (!scr_initialized)
	{
		scale = 1;
	}
	else if (r_hudscale->value < 0)
	{
		scale = SCR_GetDefaultScale();
	}
	else if (r_hudscale->value == 0) /* HACK: allow scale 0 to hide the HUD */
	{
		scale = 0;
	}
	else
	{
		scale = SCR_ClampScale(r_hudscale->value);
	}

	return scale;
}

float
SCR_GetConsoleScale(void)
{
	float scale;

	if (!scr_initialized)
	{
		scale = 1;
	}
	else if (r_consolescale->value < 0)
	{
		scale = SCR_GetDefaultScale();
	}
	else
	{
		scale = SCR_ClampScale(r_consolescale->value);
	}

	return scale;
}

float
SCR_GetMenuScale(void)
{
	float scale;

	if (!scr_initialized)
	{
		scale = 1;
	}
	else if (r_menuscale->value < 0)
	{
		scale = SCR_GetDefaultScale();
	}
	else
	{
		scale = SCR_ClampScale(r_menuscale->value);
	}

	return scale;
}
