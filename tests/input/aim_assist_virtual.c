/* Isolated real-SDL integration fixture. Never writes engine state. */
#define _GNU_SOURCE
#include <SDL.h>
#include <dlfcn.h>
#include <link.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#undef EV_NONE
#include "../../src/client/header/client.h"

static SDL_Joystick *pad;
static int attached, initialized;
static long control_offset;
static client_state_t *client;
static client_static_t *client_static;

static int find_main(struct dl_phdr_info *info, size_t size, void *data)
{
	if (!info->dlpi_name[0])
	{
		client = (client_state_t *)(info->dlpi_addr + strtoull(getenv("PP_AIM_CLIENT_OFFSET"), NULL, 16));
		client_static = (client_static_t *)(info->dlpi_addr + strtoull(getenv("PP_AIM_STATIC_OFFSET"), NULL, 16));
		return 1;
	}
	return 0;
}

int SDL_Init(Uint32 flags)
{
	static int (*real_init)(Uint32);
	if (!real_init) real_init = dlsym(RTLD_NEXT, "SDL_Init");
	int result = real_init(flags);
	if (!result && (flags & SDL_INIT_GAMECONTROLLER) && !attached)
	{
		SDL_VirtualJoystickDesc desc;
		memset(&desc, 0, sizeof(desc));
		desc.version = SDL_VIRTUAL_JOYSTICK_DESC_VERSION;
		desc.type = SDL_JOYSTICK_TYPE_GAMECONTROLLER;
		desc.naxes = SDL_CONTROLLER_AXIS_MAX;
		desc.nbuttons = SDL_CONTROLLER_BUTTON_MAX;
		desc.button_mask = (1U << SDL_CONTROLLER_BUTTON_MAX) - 1;
		desc.axis_mask = (1U << SDL_CONTROLLER_AXIS_MAX) - 1;
		desc.name = "Aim Assist Test Pad";
		int device = SDL_JoystickAttachVirtualEx(&desc);
		if (device < 0 || !(pad = SDL_JoystickOpen(device))) exit(90);
		SDL_JoystickSetVirtualAxis(pad, SDL_CONTROLLER_AXIS_TRIGGERLEFT, -32768);
		SDL_JoystickSetVirtualAxis(pad, SDL_CONTROLLER_AXIS_TRIGGERRIGHT, -32768);
		attached = 1;
	}
	return result;
}

static void snapshot(const char *label)
{
	const player_state_t *ps = &client->frame.playerstate;
	fprintf(stderr, "PP_AIM_STATE {\"label\":\"%s\",\"connection\":%d,\"buttons\":%u,\"angles\":[%.6f,%.6f],\"server_angles\":[%.6f,%.6f],\"origin\":[%d,%d,%d],\"stats\":[%d,%d,%d,%d,%d]}\n",
		label, client_static->state, client->cmd.buttons,
		client->viewangles[PITCH], client->viewangles[YAW], ps->viewangles[PITCH], ps->viewangles[YAW],
		ps->pmove.origin[0], ps->pmove.origin[1], ps->pmove.origin[2],
		ps->stats[STAT_AIMASSIST_FLAGS], ps->stats[STAT_AIMASSIST_PITCH], ps->stats[STAT_AIMASSIST_YAW],
		ps->stats[STAT_AIMASSIST_HIP_PITCH], ps->stats[STAT_AIMASSIST_HIP_YAW]);
	fflush(stderr);
}

static void controls(void)
{
	FILE *file = fopen(getenv("PP_AIM_CONTROLS"), "r");
	char line[256], op[32], arg[96];
	int index, value;
	if (!file) return;
	fseek(file, control_offset, SEEK_SET);
	/* Process one request per poll so every event reaches the real input path. */
	if (fgets(line, sizeof(line), file))
	{
		control_offset = ftell(file);
		if (sscanf(line, "%31s %95s", op, arg) >= 1)
		{
			if (!strcmp(op, "state")) snapshot(arg);
			else if (!strcmp(op, "button") && sscanf(line, "%*s %d %d", &index, &value) == 2)
			{
				SDL_JoystickSetVirtualButton(pad, index, value);
				SDL_JoystickUpdate();
			}
			else if (!strcmp(op, "axis") && sscanf(line, "%*s %d %d", &index, &value) == 2)
			{
				SDL_JoystickSetVirtualAxis(pad, index, value);
				SDL_JoystickUpdate();
			}
			else if (!strcmp(op, "key"))
			{
				SDL_Event event = {0};
				event.type = SDL_KEYDOWN;
				event.key.state = SDL_PRESSED;
				event.key.keysym.sym = SDL_GetKeyFromName(arg);
				event.key.keysym.scancode = SDL_GetScancodeFromKey(event.key.keysym.sym);
				SDL_PushEvent(&event);
				event.type = SDL_KEYUP;
				event.key.state = SDL_RELEASED;
				SDL_PushEvent(&event);
			}
		}
	}
	fclose(file);
}

int SDL_PollEvent(SDL_Event *event)
{
	static int (*real_poll)(SDL_Event *);
	if (!real_poll) real_poll = dlsym(RTLD_NEXT, "SDL_PollEvent");
	if (!initialized)
	{
		dl_iterate_phdr(find_main, NULL);
		if (!client || !client_static) exit(91);
		initialized = 1;
	}
	if (real_poll(event)) return 1;
	controls();
	return real_poll(event);
}
