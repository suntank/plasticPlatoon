#include "cl_splitscreen.h"
#define client_state_t server_client_state_t
#include "../server/header/server.h"
#undef client_state_t

extern cvar_t *crosshair_scale;

typedef enum
{
	SS_SESSION_ACTION_RESUME = 0,
	SS_SESSION_ACTION_DROPOUT,
	SS_SESSION_ACTION_EXIT,
	SS_SESSION_ACTION_COUNT
} ss_session_action_t;

typedef struct
{
	float recoil_strength;
	float recoil_recovery;
	float recoil_push_back;
	float recoil_pitch_kick;
} ss_viewmodel_recoil_t;

static ss_state_t ss_state =
{
	.transport = SS_TRANSPORT_INTERNET,
	.requested_players = 2
};

static qboolean SS_FindServerClientForSlot(const ss_local_player_t *slot,
	client_t **client_out, int *client_num_out);
static void SS_SendSlotStringCmdNow(ss_local_player_t *slot, const char *cmd);
static void SS_ParseSharedMuzzleFlash(sizebuf_t *msg, qboolean monster_flash);
static void SS_ParseSharedTempEntity(ss_local_player_t *slot, sizebuf_t *msg);
static void SS_ParseLocalSlotMuzzleFlash(ss_local_player_t *slot, int entnum, int weapon);
static float SS_GetSlotViewLerp(const ss_local_player_t *slot);
static const player_state_t *SS_GetPreviousPlayerState(const ss_local_player_t *slot,
	const player_state_t *ps);
static centity_t *SS_AllocSlotEntity(ss_local_player_t *slot, int entnum);
static void SS_FreeSlotEntities(ss_local_player_t *slot);
static void SS_TriggerSlotViewmodelKick(ss_local_player_t *slot,
	const ss_viewmodel_recoil_t *recoil_cfg, qboolean ads_active, float current_time);

static float
SS_GetDeltaAngle(const player_state_t *ps, int axis)
{
	float angle;

	if (!ps || axis < 0 || axis >= 3)
	{
		return 0.0f;
	}

	angle = SHORT2ANGLE(ps->pmove.delta_angles[axis]);

	if (angle > 180.0f)
	{
		angle -= 360.0f;
	}

	return angle;
}

static void
SS_ClampSlotPitch(ss_local_player_t *slot, const player_state_t *ps)
{
	float pitch_delta;

	if (!slot || !ps)
	{
		return;
	}

	pitch_delta = SS_GetDeltaAngle(ps, PITCH);

	if (slot->viewangles[PITCH] + pitch_delta < -360.0f)
	{
		slot->viewangles[PITCH] += 360.0f;
	}

	if (slot->viewangles[PITCH] + pitch_delta > 360.0f)
	{
		slot->viewangles[PITCH] -= 360.0f;
	}

	if (slot->viewangles[PITCH] + pitch_delta > 89.0f)
	{
		slot->viewangles[PITCH] = 89.0f - pitch_delta;
	}

	if (slot->viewangles[PITCH] + pitch_delta < -89.0f)
	{
		slot->viewangles[PITCH] = -89.0f - pitch_delta;
	}
}

static const ss_viewmodel_recoil_t ss_default_recoil =
{
	0.35f, 8.0f, 4.0f, 2.5f
};

static float
SS_ViewmodelAngleOffset(float angle, float base)
{
	float delta = angle - base;

	while (delta > 180.0f)
	{
		delta -= 360.0f;
	}

	while (delta < -180.0f)
	{
		delta += 360.0f;
	}

	return delta;
}

static int
SS_ClampPlayerCount(int player_count)
{
	if (player_count < 2)
	{
		return 2;
	}

	if (player_count > SS_MAX_LOCAL_PLAYERS)
	{
		return SS_MAX_LOCAL_PLAYERS;
	}

	return player_count;
}

static void
SS_SetSessionCvar(const char *name, int value)
{
	Cvar_Get(name, "0", 0);
	Cvar_SetValue(name, (float)value);
}

static qboolean
SS_IsConfirmKey(int key)
{
	return key == K_ENTER || key == K_KP_ENTER || key == K_BTN_SOUTH;
}

static qboolean
SS_IsCloseKey(int key)
{
	return key == K_ESCAPE || key == K_BTN_START || key == K_BTN_EAST ||
		key == K_BTN_BACK;
}

static qboolean
SS_IsUpKey(int key)
{
	return key == K_UPARROW || key == K_DPAD_UP;
}

static qboolean
SS_IsDownKey(int key)
{
	return key == K_DOWNARROW || key == K_DPAD_DOWN;
}

static qboolean
SS_IsScoreboardKey(int key)
{
	return key == K_TAB || key == K_BTN_NORTH;
}

static void
SS_DrawString(int x, int y, const char *text, qboolean highlighted, float scale)
{
	size_t i;

	if (!text)
	{
		return;
	}

	for (i = 0; text[i]; ++i)
	{
		Draw_CharScaled(x + (int)(i * 8 * scale), y,
			text[i] + (highlighted ? 128 : 0), scale);
	}
}

static void
SS_DrawCenteredStringInRect(const ss_viewport_t *viewport, int y, const char *text,
	qboolean highlighted, float scale)
{
	int width;
	int x;

	if (!viewport || !text)
	{
		return;
	}

	width = (int)(strlen(text) * 8 * scale);
	x = viewport->x + (viewport->w - width) / 2;
	SS_DrawString(x, y, text, highlighted, scale);
}

static int
SS_GetSlotCount(void)
{
	return SS_GetPlayerCount();
}

static ss_local_player_t *
SS_FindSlotByDeviceIndex(int device_index, qboolean allow_keyboard_fallback)
{
	int i;
	ss_local_player_t *fallback = NULL;

	for (i = 0; i < SS_GetSlotCount(); ++i)
	{
		ss_local_player_t *slot = &ss_state.slots[i];

		if (!slot->active)
		{
			continue;
		}

		if (slot->device_index == device_index)
		{
			return slot;
		}

		if (allow_keyboard_fallback && device_index == 1 && i == 0)
		{
			fallback = slot;
		}
	}

	return fallback;
}

static qboolean
SS_HasOpenSessionMenu(void)
{
	int i;

	for (i = 0; i < SS_GetSlotCount(); ++i)
	{
		if (ss_state.slots[i].menu_open)
		{
			return true;
		}
	}

	return false;
}

static void
SS_UpdatePauseState(void)
{
	if (!ss_state.session_active)
	{
		Cvar_Set("paused", "0");
		return;
	}

	Cvar_Set("paused", SS_HasOpenSessionMenu() ? "1" : "0");
}

static void
SS_CloseSlotMenu(ss_local_player_t *slot)
{
	if (!slot)
	{
		return;
	}

	slot->menu_open = false;
	slot->exit_hold_active = false;
	slot->exit_hold_start = 0;
	SS_UpdatePauseState();
}

static void
SS_OpenSlotMenu(ss_local_player_t *slot)
{
	if (!slot || slot->state == SS_SLOT_DROPPED)
	{
		return;
	}

	slot->menu_open = true;
	slot->menu_cursor = SS_SESSION_ACTION_RESUME;
	slot->exit_hold_active = false;
	slot->exit_hold_start = 0;
	SS_UpdatePauseState();
}

static qboolean
SS_AreAllSlotsDropped(void)
{
	int i;

	for (i = 0; i < SS_GetSlotCount(); ++i)
	{
		ss_local_player_t *slot = &ss_state.slots[i];

		if (slot->active && slot->state != SS_SLOT_DROPPED)
		{
			return false;
		}
	}

	return true;
}

static void
SS_ExitToMultiplayerMenu(void)
{
	if (!ss_state.session_active)
	{
		return;
	}

	SS_EndSession();
	Cbuf_AddText("disconnect\nmenu_multiplayer\n");
}

static void
SS_DropSlot(ss_local_player_t *slot)
{
	if (!slot || slot->state == SS_SLOT_DROPPED)
	{
		return;
	}

	slot->state = SS_SLOT_DROPPED;
	slot->ready = false;
	slot->menu_open = false;
	slot->exit_hold_active = false;
	slot->exit_hold_start = 0;
	slot->scoreboard_down = false;

	if (slot->loopback_slot > 0 && slot->connection_state >= ca_connected)
	{
		int previous_slot = NET_GetLoopbackSlot(NS_CLIENT);

		NET_SetLoopbackSlot(NS_CLIENT, slot->loopback_slot);
		MSG_WriteByte(&slot->netchan.message, clc_stringcmd);
		MSG_WriteString(&slot->netchan.message, "disconnect");
		Netchan_Transmit(&slot->netchan, 0, NULL);
		NET_SetLoopbackSlot(NS_CLIENT, previous_slot);
		slot->connection_state = ca_disconnected;
	}

	if (SS_AreAllSlotsDropped())
	{
		SS_ExitToMultiplayerMenu();
		return;
	}

	SS_UpdatePauseState();
}

static void
SS_AdvanceMenuCursor(ss_local_player_t *slot, int step)
{
	int cursor;

	if (!slot)
	{
		return;
	}

	cursor = slot->menu_cursor + step;

	if (cursor < 0)
	{
		cursor = SS_SESSION_ACTION_COUNT - 1;
	}
	else if (cursor >= SS_SESSION_ACTION_COUNT)
	{
		cursor = 0;
	}

	slot->menu_cursor = cursor;
	slot->exit_hold_active = false;
	slot->exit_hold_start = 0;
}

static void
SS_ActivateMenuSelection(ss_local_player_t *slot)
{
	if (!slot)
	{
		return;
	}

	switch (slot->menu_cursor)
	{
		case SS_SESSION_ACTION_RESUME:
			SS_CloseSlotMenu(slot);
			break;

		case SS_SESSION_ACTION_DROPOUT:
			SS_DropSlot(slot);
			break;

		case SS_SESSION_ACTION_EXIT:
			if (!slot->exit_hold_active)
			{
				slot->exit_hold_active = true;
				slot->exit_hold_start = Sys_Milliseconds();
			}
			break;
	}
}

static int
SS_GetEventDeviceIndex(void)
{
	int gamepad_index = Key_GetEventGamepadIndex();

	return (gamepad_index >= 0) ? (gamepad_index + 2) : 1;
}

static const char *
SS_GetExitPrompt(const ss_local_player_t *slot)
{
	if (slot && slot->device_index == 1)
	{
		return "Hold Enter for 3 seconds";
	}

	return "Hold A for 3 seconds";
}

static void
SS_DrawSessionDividerLines(void)
{
	const int line_color = 8;
	int half_w = viddef.width / 2;
	int half_h = viddef.height / 2;

	if (SS_GetSlotCount() == 2)
	{
		Draw_Fill(0, half_h - 1, viddef.width, 2, line_color);
		return;
	}

	Draw_Fill(half_w - 1, 0, 2, viddef.height, line_color);
	Draw_Fill(0, half_h - 1, viddef.width, 2, line_color);
}

static int
SS_ParseEntityBits(sizebuf_t *msg, unsigned *bits)
{
	unsigned b;
	unsigned total;
	int number;

	total = MSG_ReadByte(msg);

	if (total & U_MOREBITS1)
	{
		b = MSG_ReadByte(msg);
		total |= b << 8;
	}

	if (total & U_MOREBITS2)
	{
		b = MSG_ReadByte(msg);
		total |= b << 16;
	}

	if (total & U_MOREBITS3)
	{
		b = MSG_ReadByte(msg);
		total |= b << 24;
	}

	number = (total & U_NUMBER16) ? MSG_ReadShort(msg) : MSG_ReadByte(msg);
	*bits = total;
	return number;
}

static void
SS_ParseDelta(sizebuf_t *msg, const entity_state_t *from, entity_state_t *to,
	int number, int bits)
{
	static const entity_state_t nullstate = {0};

	if (!from)
	{
		from = &nullstate;
	}

	*to = *from;
	VectorCopy(from->origin, to->old_origin);
	to->number = number;

	if (bits & U_MODEL) to->modelindex = MSG_ReadByte(msg);
	if (bits & U_MODEL2) to->modelindex2 = MSG_ReadByte(msg);
	if (bits & U_MODEL3) to->modelindex3 = MSG_ReadByte(msg);
	if (bits & U_MODEL4) to->modelindex4 = MSG_ReadByte(msg);
	if (bits & U_FRAME8) to->frame = MSG_ReadByte(msg);
	if (bits & U_FRAME16) to->frame = MSG_ReadShort(msg);

	if ((bits & (U_SKIN8 | U_SKIN16)) == (U_SKIN8 | U_SKIN16))
	{
		to->skinnum = MSG_ReadLong(msg);
	}
	else if (bits & U_SKIN8)
	{
		to->skinnum = MSG_ReadByte(msg);
	}
	else if (bits & U_SKIN16)
	{
		to->skinnum = MSG_ReadShort(msg);
	}

	if ((bits & (U_EFFECTS8 | U_EFFECTS16)) == (U_EFFECTS8 | U_EFFECTS16))
	{
		to->effects = MSG_ReadLong(msg);
	}
	else if (bits & U_EFFECTS8)
	{
		to->effects = MSG_ReadByte(msg);
	}
	else if (bits & U_EFFECTS16)
	{
		to->effects = MSG_ReadShort(msg);
	}

	if ((bits & (U_RENDERFX8 | U_RENDERFX16)) == (U_RENDERFX8 | U_RENDERFX16))
	{
		to->renderfx = MSG_ReadLong(msg);
	}
	else if (bits & U_RENDERFX8)
	{
		to->renderfx = MSG_ReadByte(msg);
	}
	else if (bits & U_RENDERFX16)
	{
		to->renderfx = MSG_ReadShort(msg);
	}

	if (bits & U_ORIGIN1) to->origin[0] = MSG_ReadCoord(msg);
	if (bits & U_ORIGIN2) to->origin[1] = MSG_ReadCoord(msg);
	if (bits & U_ORIGIN3) to->origin[2] = MSG_ReadCoord(msg);
	if (bits & U_ANGLE1) to->angles[0] = MSG_ReadAngle(msg);
	if (bits & U_ANGLE2) to->angles[1] = MSG_ReadAngle(msg);
	if (bits & U_ANGLE3) to->angles[2] = MSG_ReadAngle(msg);
	if (bits & U_OLDORIGIN) MSG_ReadPos(msg, to->old_origin);
	if (bits & U_SOUND) to->sound = MSG_ReadByte(msg);
	if (bits & U_EVENT) to->event = MSG_ReadByte(msg);
	else to->event = 0;
	if (bits & U_SOLID) to->solid = MSG_ReadShort(msg);
}

static void
SS_DeltaEntity(ss_local_player_t *slot, frame_t *frame, int newnum,
	const entity_state_t *old, int bits, sizebuf_t *msg)
{
	centity_t dummy;
	centity_t *ent;
	entity_state_t *state;

	state = &slot->parse_entities[slot->parse_entities_num &
		(MAX_PARSE_ENTITIES - 1)];
	slot->parse_entities_num++;
	frame->num_entities++;

	ent = SS_AllocSlotEntity(slot, newnum);

	if (!ent)
	{
		memset(&dummy, 0, sizeof(dummy));
		ent = &dummy;
	}

	SS_ParseDelta(msg, old, state, newnum, bits);

	if ((state->modelindex != ent->current.modelindex) ||
		(state->modelindex2 != ent->current.modelindex2) ||
		(state->modelindex3 != ent->current.modelindex3) ||
		(state->modelindex4 != ent->current.modelindex4) ||
		(state->event == EV_PLAYER_TELEPORT) ||
		(state->event == EV_OTHER_TELEPORT) ||
		(abs((int)(state->origin[0] - ent->current.origin[0])) > 512) ||
		(abs((int)(state->origin[1] - ent->current.origin[1])) > 512) ||
		(abs((int)(state->origin[2] - ent->current.origin[2])) > 512))
	{
		ent->serverframe = -99;
	}

	if (ent->serverframe != frame->serverframe - 1)
	{
		ent->trailcount = 1024;
		ent->prev = *state;

		if (state->event == EV_OTHER_TELEPORT)
		{
			VectorCopy(state->origin, ent->prev.origin);
			VectorCopy(state->origin, ent->lerp_origin);
		}
		else
		{
			VectorCopy(state->old_origin, ent->prev.origin);
			VectorCopy(state->old_origin, ent->lerp_origin);
		}
	}
	else
	{
		ent->prev = ent->current;
	}

	ent->serverframe = frame->serverframe;
	ent->current = *state;
}

static void
SS_ParsePacketEntities(ss_local_player_t *slot, frame_t *oldframe,
	frame_t *newframe, sizebuf_t *msg)
{
	entity_state_t *oldstate = NULL;
	unsigned bits;
	unsigned newnum;
	int oldindex = 0;
	int oldnum;

	newframe->parse_entities = slot->parse_entities_num;
	newframe->num_entities = 0;

	if (!oldframe)
	{
		oldnum = 99999;
	}
	else if (oldframe->num_entities <= 0)
	{
		oldnum = 99999;
	}
	else
	{
		oldstate = &slot->parse_entities[oldframe->parse_entities &
			(MAX_PARSE_ENTITIES - 1)];
		oldnum = oldstate->number;
	}

	while (1)
	{
		newnum = SS_ParseEntityBits(msg, &bits);

		if (newnum > MAX_CL_ENTNUM)
		{
			Com_Printf("%s: bad entity %u > %d\n", __func__, newnum, MAX_CL_ENTNUM);
			return;
		}

		if (!newnum)
		{
			break;
		}

		while (oldnum < (int)newnum)
		{
			SS_DeltaEntity(slot, newframe, oldnum, oldstate, 0, msg);
			oldindex++;

			if (!oldframe || oldindex >= oldframe->num_entities)
			{
				oldnum = 99999;
			}
			else
			{
				oldstate = &slot->parse_entities[(oldframe->parse_entities + oldindex) &
					(MAX_PARSE_ENTITIES - 1)];
				oldnum = oldstate->number;
			}
		}

		if (bits & U_REMOVE)
		{
			oldindex++;

			if (!oldframe || oldindex >= oldframe->num_entities)
			{
				oldnum = 99999;
			}
			else
			{
				oldstate = &slot->parse_entities[(oldframe->parse_entities + oldindex) &
					(MAX_PARSE_ENTITIES - 1)];
				oldnum = oldstate->number;
			}

			continue;
		}

		if (oldnum == (int)newnum)
		{
			SS_DeltaEntity(slot, newframe, (int)newnum, oldstate, bits, msg);
			oldindex++;

			if (!oldframe || oldindex >= oldframe->num_entities)
			{
				oldnum = 99999;
			}
			else
			{
				oldstate = &slot->parse_entities[(oldframe->parse_entities + oldindex) &
					(MAX_PARSE_ENTITIES - 1)];
				oldnum = oldstate->number;
			}

			continue;
		}

		if (oldnum > (int)newnum)
		{
			centity_t *ent = SS_AllocSlotEntity(slot, (int)newnum);
			SS_DeltaEntity(slot, newframe, (int)newnum,
				ent ? &ent->baseline : NULL, bits, msg);
		}
	}

	while (oldnum != 99999)
	{
		SS_DeltaEntity(slot, newframe, oldnum, oldstate, 0, msg);
		oldindex++;

		if (!oldframe || oldindex >= oldframe->num_entities)
		{
			oldnum = 99999;
		}
		else
		{
			oldstate = &slot->parse_entities[(oldframe->parse_entities + oldindex) &
				(MAX_PARSE_ENTITIES - 1)];
			oldnum = oldstate->number;
		}
	}
}

static void
SS_ParsePlayerstate(ss_local_player_t *slot, frame_t *oldframe,
	frame_t *newframe, sizebuf_t *msg)
{
	player_state_t *state = &newframe->playerstate;
	int flags;
	int statbits;
	int i;

	(void)slot;

	if (oldframe)
	{
		*state = oldframe->playerstate;
	}
	else
	{
		memset(state, 0, sizeof(*state));
		state->fov = 90.0f;
	}

	flags = MSG_ReadShort(msg);

	if (flags & PS_M_TYPE) state->pmove.pm_type = MSG_ReadByte(msg);
	if (flags & PS_M_ORIGIN)
	{
		state->pmove.origin[0] = MSG_ReadShort(msg);
		state->pmove.origin[1] = MSG_ReadShort(msg);
		state->pmove.origin[2] = MSG_ReadShort(msg);
	}
	if (flags & PS_M_VELOCITY)
	{
		state->pmove.velocity[0] = MSG_ReadShort(msg);
		state->pmove.velocity[1] = MSG_ReadShort(msg);
		state->pmove.velocity[2] = MSG_ReadShort(msg);
	}
	if (flags & PS_M_TIME) state->pmove.pm_time = MSG_ReadByte(msg);
	if (flags & PS_M_FLAGS) state->pmove.pm_flags = MSG_ReadByte(msg);
	if (flags & PS_M_GRAVITY) state->pmove.gravity = MSG_ReadShort(msg);
	if (flags & PS_M_DELTA_ANGLES)
	{
		state->pmove.delta_angles[0] = MSG_ReadShort(msg);
		state->pmove.delta_angles[1] = MSG_ReadShort(msg);
		state->pmove.delta_angles[2] = MSG_ReadShort(msg);
	}

	if (cl.attractloop)
	{
		state->pmove.pm_type = PM_FREEZE;
	}

	if (flags & PS_VIEWOFFSET)
	{
		state->viewoffset[0] = MSG_ReadChar(msg) * 0.25f;
		state->viewoffset[1] = MSG_ReadChar(msg) * 0.25f;
		state->viewoffset[2] = MSG_ReadChar(msg) * 0.25f;
	}
	if (flags & PS_VIEWANGLES)
	{
		state->viewangles[0] = MSG_ReadAngle16(msg);
		state->viewangles[1] = MSG_ReadAngle16(msg);
		state->viewangles[2] = MSG_ReadAngle16(msg);
	}
	if (flags & PS_KICKANGLES)
	{
		state->kick_angles[0] = MSG_ReadChar(msg) * 0.25f;
		state->kick_angles[1] = MSG_ReadChar(msg) * 0.25f;
		state->kick_angles[2] = MSG_ReadChar(msg) * 0.25f;
	}
	if (flags & PS_WEAPONINDEX) state->gunindex = MSG_ReadByte(msg);
	if (flags & PS_WEAPONFRAME)
	{
		state->gunframe = MSG_ReadByte(msg);
		state->gunoffset[0] = MSG_ReadChar(msg) * 0.25f;
		state->gunoffset[1] = MSG_ReadChar(msg) * 0.25f;
		state->gunoffset[2] = MSG_ReadChar(msg) * 0.25f;
		state->gunangles[0] = MSG_ReadChar(msg) * 0.25f;
		state->gunangles[1] = MSG_ReadChar(msg) * 0.25f;
		state->gunangles[2] = MSG_ReadChar(msg) * 0.25f;
	}
	if (flags & PS_BLEND)
	{
		state->blend[0] = MSG_ReadByte(msg) / 255.0f;
		state->blend[1] = MSG_ReadByte(msg) / 255.0f;
		state->blend[2] = MSG_ReadByte(msg) / 255.0f;
		state->blend[3] = MSG_ReadByte(msg) / 255.0f;
	}
	if (flags & PS_FOV) state->fov = (float)MSG_ReadByte(msg);
	if (flags & PS_RDFLAGS) state->rdflags = MSG_ReadByte(msg);

	statbits = MSG_ReadLong(msg);

	for (i = 0; i < MAX_STATS; ++i)
	{
		if (statbits & (1u << i))
		{
			state->stats[i] = MSG_ReadShort(msg);
		}
	}
}

static void
SS_ParseInventory(ss_local_player_t *slot, sizebuf_t *msg)
{
	int i;

	for (i = 0; i < MAX_ITEMS; ++i)
	{
		slot->inventory[i] = MSG_ReadShort(msg);
	}
}

static void
SS_ParseConfigString(sizebuf_t *msg)
{
	int index;
	char *value;

	index = MSG_ReadShort(msg);

	if (index < 0 || index >= MAX_CONFIGSTRINGS)
	{
		return;
	}

	value = MSG_ReadString(msg);
	Q_strlcpy(cl.configstrings[index], value, sizeof(cl.configstrings[index]));
}

static void
SS_ParseBaseline(ss_local_player_t *slot, sizebuf_t *msg)
{
	centity_t *ent;
	entity_state_t baseline;
	unsigned bits;
	int newnum;

	newnum = SS_ParseEntityBits(msg, &bits);
	memset(&baseline, 0, sizeof(baseline));
	SS_ParseDelta(msg, NULL, &baseline, newnum, bits);

	ent = SS_AllocSlotEntity(slot, newnum);

	if (ent)
	{
		ent->baseline = baseline;
	}
}

static void
SS_SkipSoundPacket(sizebuf_t *msg)
{
	int flags;

	flags = MSG_ReadByte(msg);
	(void)MSG_ReadByte(msg);

	if (flags & SND_VOLUME) (void)MSG_ReadByte(msg);
	if (flags & SND_ATTENUATION) (void)MSG_ReadByte(msg);
	if (flags & SND_OFFSET) (void)MSG_ReadByte(msg);
	if (flags & SND_ENT) (void)MSG_ReadShort(msg);
	if (flags & SND_POS)
	{
		vec3_t pos;
		MSG_ReadPos(msg, pos);
	}
}

static void
SS_FreeSlotEntities(ss_local_player_t *slot)
{
	if (!slot || !slot->entities)
	{
		return;
	}

	Z_Free(slot->entities);
	slot->entities = NULL;
	slot->entity_count = 0;
}

static centity_t *
SS_AllocSlotEntity(ss_local_player_t *slot, int entnum)
{
	int nextpow2;

	if (!slot || entnum < 0 || entnum > MAX_CL_ENTNUM)
	{
		return NULL;
	}

	if (entnum >= slot->entity_count)
	{
		nextpow2 = (slot->entity_count || (entnum >= 32)) ?
			(int)NextPow2gt(entnum) : 32;
		slot->entities = Z_Realloc(slot->entities, nextpow2 * sizeof(*slot->entities));
		slot->entity_count = nextpow2;
	}

	return &slot->entities[entnum];
}

static void
SS_ParseSharedMuzzleFlash(sizebuf_t *msg, qboolean monster_flash)
{
	sizebuf_t saved_message;
	int previous_playernum;

	if (!msg)
	{
		return;
	}

	saved_message = net_message;
	net_message = *msg;
	previous_playernum = cl.playernum;

	/* Split-screen slots use their own local viewmodel path, so treat these
	 * parsed flashes as third-person effects to avoid disturbing player-one
	 * recoil and ADS feedback state. */
	cl.playernum = -1;

	if (monster_flash)
	{
		CL_AddMuzzleFlash2();
	}
	else
	{
		CL_AddMuzzleFlash();
	}

	cl.playernum = previous_playernum;
	*msg = net_message;
	net_message = saved_message;
}

static void
SS_ParseLocalSlotMuzzleFlash(ss_local_player_t *slot, int entnum, int weapon)
{
	sizebuf_t saved_message;
	sizebuf_t local_message;
	byte local_data[8];
	refdef_t saved_refdef;
	frame_t saved_frame;
	usercmd_t saved_cmd;
	centity_t saved_entity;
	vec3_t saved_viewangles;
	vec3_t entity_origin;
	vec3_t entity_angles;
	const player_state_t *ps;
	float yaw_delta;
	int saved_playernum;
	int saved_muzzle_seq;
	int i;

	if (!slot || !slot->snapshot_valid)
	{
		return;
	}

	ps = &slot->frame.playerstate;

	for (i = 0; i < 3; ++i)
	{
		entity_origin[i] = ps->pmove.origin[i] * 0.125f;
		entity_angles[i] = slot->viewangles[i] + SS_GetDeltaAngle(ps, i);
	}

	yaw_delta = SHORT2ANGLE(ps->pmove.delta_angles[YAW]);

	if (yaw_delta > 180.0f)
	{
		yaw_delta -= 360.0f;
	}

	SZ_Init(&local_message, local_data, sizeof(local_data));
	MSG_WriteShort(&local_message, entnum);
	MSG_WriteByte(&local_message, weapon);
	MSG_BeginReading(&local_message);

	saved_message = net_message;
	saved_playernum = cl.playernum;
	saved_refdef = cl.refdef;
	saved_frame = cl.frame;
	saved_cmd = cl.cmd;
	saved_entity = cl_entities[entnum];
	saved_muzzle_seq = pp_viewmodel_muzzle_seq;
	VectorCopy(cl.viewangles, saved_viewangles);

	net_message = local_message;
	cl.playernum = entnum - 1;
	cl.frame = slot->frame;
	slot->muzzle_flash_seq++;
	cl.cmd.buttons &= ~BUTTON_ADS;

	if (slot->ads_down)
	{
		cl.cmd.buttons |= BUTTON_ADS;
	}

	for (i = 0; i < 3; ++i)
	{
		cl.refdef.vieworg[i] = ps->pmove.origin[i] * 0.125f + ps->viewoffset[i];
		cl.refdef.viewangles[i] = entity_angles[i] + ps->kick_angles[i];
	}

	VectorCopy(entity_origin, cl_entities[entnum].current.origin);
	VectorCopy(entity_origin, cl_entities[entnum].prev.origin);
	VectorCopy(entity_origin, cl_entities[entnum].lerp_origin);
	VectorCopy(entity_angles, cl_entities[entnum].current.angles);
	VectorCopy(entity_angles, cl_entities[entnum].prev.angles);
	cl_entities[entnum].current.number = entnum;
	cl_entities[entnum].prev.number = entnum;
	cl_entities[entnum].serverframe = slot->frame.serverframe;

	/* Match the normal client's delta-adjusted yaw basis before invoking the
	 * stock muzzle-flash parser for this split-screen slot. */
	cl.viewangles[YAW] = entity_angles[YAW] - yaw_delta;

	CL_AddMuzzleFlash();

	pp_viewmodel_muzzle_seq = saved_muzzle_seq;
	cl_entities[entnum] = saved_entity;
	cl.cmd = saved_cmd;
	cl.frame = saved_frame;
	cl.refdef = saved_refdef;
	VectorCopy(saved_viewangles, cl.viewangles);
	cl.playernum = saved_playernum;
	net_message = saved_message;
}

static float
SS_GetSlotViewLerp(const ss_local_player_t *slot)
{
	float lerp;

	if (!slot)
	{
		return 1.0f;
	}

	if (cl_paused->value)
	{
		return 1.0f;
	}

	if (!slot->snapshot_valid)
	{
		return Q_clamp(cl.lerpfrac, 0.0f, 1.0f);
	}

	if (cl.time >= slot->frame.servertime)
	{
		return 1.0f;
	}

	if (cl.time <= slot->frame.servertime - 100)
	{
		return 0.0f;
	}

	lerp = 1.0f - (slot->frame.servertime - cl.time) * 0.01f;

	if (cl_timedemo->value)
	{
		return 1.0f;
	}

	return Q_clamp(lerp, 0.0f, 1.0f);
}

static const player_state_t *
SS_GetPreviousPlayerState(const ss_local_player_t *slot, const player_state_t *ps)
{
	const frame_t *oldframe;
	const player_state_t *ops;
	int i;

	if (!slot || !slot->snapshot_valid || !ps)
	{
		return ps;
	}

	oldframe = &slot->frames[(slot->frame.serverframe - 1) & UPDATE_MASK];

	if ((oldframe->serverframe != slot->frame.serverframe - 1) || !oldframe->valid)
	{
		return ps;
	}

	ops = &oldframe->playerstate;

	for (i = 0; i < 3; ++i)
	{
		if (abs(ops->pmove.origin[i] - ps->pmove.origin[i]) > 256 * 8)
		{
			return ps;
		}
	}

	return ops;
}

static void
SS_SkipBeamPacket(sizebuf_t *msg, qboolean with_offset)
{
	vec3_t tmp;

	(void)MSG_ReadShort(msg);
	MSG_ReadPos(msg, tmp);
	MSG_ReadPos(msg, tmp);

	if (with_offset)
	{
		MSG_ReadPos(msg, tmp);
	}
}

static void
SS_SkipLightningPacket(sizebuf_t *msg)
{
	vec3_t tmp;

	(void)MSG_ReadShort(msg);
	(void)MSG_ReadShort(msg);
	MSG_ReadPos(msg, tmp);
	MSG_ReadPos(msg, tmp);
}

static void
SS_SkipSteamPacket(sizebuf_t *msg)
{
	vec3_t tmp;
	int id;

	id = MSG_ReadShort(msg);

	if (id == -1)
	{
		(void)MSG_ReadByte(msg);
		MSG_ReadPos(msg, tmp);
		MSG_ReadDir(msg, tmp);
		(void)MSG_ReadByte(msg);
		(void)MSG_ReadShort(msg);
		return;
	}

	(void)MSG_ReadByte(msg);
	MSG_ReadPos(msg, tmp);
	MSG_ReadDir(msg, tmp);
	(void)MSG_ReadByte(msg);
	(void)MSG_ReadShort(msg);
	(void)MSG_ReadLong(msg);
}

static void
SS_SkipTempEntity(sizebuf_t *msg)
{
	vec3_t tmp;
	int type;

	type = MSG_ReadByte(msg);

	switch (type)
	{
		case TE_BLOOD:
		case TE_GUNSHOT:
		case TE_SPARKS:
		case TE_BULLET_SPARKS:
		case TE_SCREEN_SPARKS:
		case TE_SHIELD_SPARKS:
		case TE_SHOTGUN:
		case TE_BLASTER:
		case TE_GREENBLOOD:
		case TE_BLASTER2:
		case TE_FLECHETTE:
		case TE_MOREBLOOD:
		case TE_ELECTRIC_SPARKS:
			MSG_ReadPos(msg, tmp);
			MSG_ReadDir(msg, tmp);
			break;

		case TE_MORTAR_EXPLOSION:
		case TE_EXPLOSION2:
		case TE_GRENADE_EXPLOSION:
		case TE_GRENADE_EXPLOSION_WATER:
		case TE_PLASMA_EXPLOSION:
		case TE_EXPLOSION1_BIG:
		case TE_EXPLOSION1_NP:
		case TE_EXPLOSION1:
		case TE_ROCKET_EXPLOSION:
		case TE_ROCKET_EXPLOSION_WATER:
		case TE_BFG_EXPLOSION:
		case TE_BFG_BIGEXPLOSION:
		case TE_BOSSTPORT:
		case TE_PLAIN_EXPLOSION:
		case TE_TELEPORT_EFFECT:
		case TE_DBALL_GOAL:
		case TE_WIDOWSPLASH:
		case TE_FLAME:
			MSG_ReadPos(msg, tmp);
			break;

		case TE_SPLASH:
		case TE_LASER_SPARKS:
		case TE_WELDING_SPARKS:
		case TE_TUNNEL_SPARKS:
			(void)MSG_ReadByte(msg);
			MSG_ReadPos(msg, tmp);
			MSG_ReadDir(msg, tmp);
			(void)MSG_ReadByte(msg);
			break;

		case TE_BLUEHYPERBLASTER:
		case TE_RAILTRAIL:
		case TE_RAILTRAIL2:
		case TE_BUBBLETRAIL:
		case TE_DEBUGTRAIL:
		case TE_FORCEWALL:
		case TE_BUBBLETRAIL2:
			MSG_ReadPos(msg, tmp);
			MSG_ReadPos(msg, tmp);
			break;

		case TE_BFG_LASER:
			MSG_ReadPos(msg, tmp);
			MSG_ReadPos(msg, tmp);
			break;

		case TE_PARASITE_ATTACK:
		case TE_MEDIC_CABLE_ATTACK:
			SS_SkipBeamPacket(msg, false);
			break;

		case TE_GRAPPLE_CABLE:
			SS_SkipBeamPacket(msg, true);
			break;

		case TE_LIGHTNING:
			SS_SkipLightningPacket(msg);
			break;

		case TE_FLASHLIGHT:
			MSG_ReadPos(msg, tmp);
			(void)MSG_ReadShort(msg);
			break;

		case TE_HEATBEAM:
		case TE_MONSTER_HEATBEAM:
			(void)MSG_ReadShort(msg);
			MSG_ReadPos(msg, tmp);
			MSG_ReadPos(msg, tmp);
			break;

		case TE_HEATBEAM_SPARKS:
		case TE_HEATBEAM_STEAM:
			MSG_ReadPos(msg, tmp);
			MSG_ReadDir(msg, tmp);
			break;

		case TE_STEAM:
			SS_SkipSteamPacket(msg);
			break;

		case TE_CHAINFIST_SMOKE:
			MSG_ReadPos(msg, tmp);
			break;

		case TE_TRACKER_EXPLOSION:
			MSG_ReadPos(msg, tmp);
			break;

		case TE_WIDOWBEAMOUT:
			(void)MSG_ReadShort(msg);
			MSG_ReadPos(msg, tmp);
			break;

		case TE_NUKEBLAST:
			MSG_ReadPos(msg, tmp);
			break;

		default:
			Com_DPrintf("Split-screen got unknown temp entity type %d\n", type);
			break;
	}
}

static unsigned int
SS_HashTempEntityPayload(const byte *data, int len)
{
	unsigned int hash = 2166136261u;
	int i;

	for (i = 0; i < len; ++i)
	{
		hash ^= data[i];
		hash *= 16777619u;
	}

	return hash;
}

static void
SS_ParseSharedTempEntity(ss_local_player_t *slot, sizebuf_t *msg)
{
	typedef struct
	{
		int framecount;
		int count;
		unsigned int hashes[128];
		int lengths[128];
	} ss_temp_entity_cache_t;

	static ss_temp_entity_cache_t cache;
	sizebuf_t saved_message;
	sizebuf_t probe;
	frame_t saved_frame;
	int payload_start;
	int payload_len;
	int i;

	if (!slot || !msg)
	{
		return;
	}

	payload_start = msg->readcount;
	probe = *msg;
	SS_SkipTempEntity(&probe);
	payload_len = probe.readcount - payload_start;

	if (payload_len <= 0)
	{
		*msg = probe;
		return;
	}

	if (cache.framecount != cls.framecount)
	{
		cache.framecount = cls.framecount;
		cache.count = 0;
	}

	{
		unsigned int hash = SS_HashTempEntityPayload(&msg->data[payload_start],
			payload_len);

		for (i = 0; i < cache.count; ++i)
		{
			if (cache.hashes[i] == hash && cache.lengths[i] == payload_len)
			{
				*msg = probe;
				return;
			}
		}

		if (cache.count < (int)ARRLEN(cache.hashes))
		{
			cache.hashes[cache.count] = hash;
			cache.lengths[cache.count] = payload_len;
			++cache.count;
		}
	}

	saved_message = net_message;
	saved_frame = cl.frame;
	net_message = *msg;
	cl.frame = slot->frame;
	CL_ParseTEnt();
	*msg = net_message;
	net_message = saved_message;
	cl.frame = saved_frame;
}

static void
SS_TrimStuffText(char *text)
{
	size_t len;

	if (!text)
	{
		return;
	}

	len = strlen(text);

	while (len > 0 && (text[len - 1] == '\n' || text[len - 1] == '\r' ||
		text[len - 1] == ' ' || text[len - 1] == '\t'))
	{
		text[--len] = '\0';
	}
}

static void
SS_HandleStuffText(ss_local_player_t *slot, const char *text)
{
	char command[1024];

	if (!slot || !text)
	{
		return;
	}

	Q_strlcpy(command, text, sizeof(command));
	SS_TrimStuffText(command);

	if (!strncmp(command, "cmd ", 4))
	{
		SS_SendSlotStringCmdNow(slot, command + 4);
		return;
	}

	if (!strncmp(command, "precache ", 9))
	{
		slot->servercount = (int)strtol(command + 9, NULL, 10);
		slot->connection_state = ca_active;
		SS_SendSlotStringCmdNow(slot, va("begin %i", slot->servercount));
	}
}

static void
SS_ParseServerData(ss_local_player_t *slot, sizebuf_t *msg)
{
	int protocol;

	if (!slot)
	{
		return;
	}

	protocol = MSG_ReadLong(msg);

	if (protocol != PROTOCOL_VERSION)
	{
		Com_Printf("Split-screen slot %d got protocol %d, expected %d\n",
			slot->local_index + 1, protocol, PROTOCOL_VERSION);
		return;
	}

	slot->servercount = MSG_ReadLong(msg);
	(void)MSG_ReadByte(msg);
	(void)MSG_ReadString(msg);
	slot->playernum = MSG_ReadShort(msg);
	(void)MSG_ReadString(msg);
	slot->snapshot_valid = false;
	slot->parse_entities_num = 0;
	slot->muzzle_flash_seq = 0;
	slot->last_muzzle_flash_seq = 0;
	memset(&slot->frame, 0, sizeof(slot->frame));

	if (slot->entities && slot->entity_count > 0)
	{
		memset(slot->entities, 0, slot->entity_count * sizeof(*slot->entities));
	}
}

static void
SS_ParseFrame(ss_local_player_t *slot, sizebuf_t *msg)
{
	frame_t newframe;
	frame_t *old = NULL;
	int cmd;
	int len;
	int area_len;
	int suppress_count;
	int i;

	if (!slot)
	{
		return;
	}

	memset(&newframe, 0, sizeof(newframe));
	newframe.serverframe = MSG_ReadLong(msg);
	newframe.deltaframe = MSG_ReadLong(msg);
	newframe.servertime = newframe.serverframe * 100;

	if (cls.serverProtocol != 26)
	{
		suppress_count = MSG_ReadByte(msg);
		(void)suppress_count;
	}

	if (newframe.deltaframe <= 0)
	{
		newframe.valid = true;
		old = NULL;
	}
	else
	{
		old = &slot->frames[newframe.deltaframe & UPDATE_MASK];

		if (old->valid && old->serverframe == newframe.deltaframe &&
			slot->parse_entities_num - old->parse_entities <= MAX_PARSE_ENTITIES - 128)
		{
			newframe.valid = true;
		}
	}

	area_len = MSG_ReadByte(msg);
	len = area_len;

	if (len < 0)
	{
		len = 0;
	}
	else if (len > (int)sizeof(newframe.areabits))
	{
		len = (int)sizeof(newframe.areabits);
	}

	MSG_ReadData(msg, &newframe.areabits, len);

	while (area_len-- > len)
	{
		(void)MSG_ReadByte(msg);
	}

	cmd = MSG_ReadByte(msg);

	if (cmd != svc_playerinfo)
	{
		Com_Printf("Split-screen slot %d got 0x%X instead of playerinfo\n",
			slot->local_index + 1, cmd);
		return;
	}

	SS_ParsePlayerstate(slot, old, &newframe, msg);

	cmd = MSG_ReadByte(msg);

	if (cmd != svc_packetentities)
	{
		Com_Printf("Split-screen slot %d got 0x%X instead of packetentities\n",
			slot->local_index + 1, cmd);
		return;
	}

	SS_ParsePacketEntities(slot, old, &newframe, msg);
	slot->frame = newframe;
	slot->frames[newframe.serverframe & UPDATE_MASK] = newframe;

	if (newframe.valid && !slot->snapshot_valid)
	{
		for (i = 0; i < 3; ++i)
		{
			slot->viewangles[i] = newframe.playerstate.viewangles[i] -
				SS_GetDeltaAngle(&newframe.playerstate, i);
		}

		SS_ClampSlotPitch(slot, &newframe.playerstate);
	}

	slot->snapshot_valid = newframe.valid;
}

static void
SS_ParseServerMessage(ss_local_player_t *slot, sizebuf_t *msg)
{
	int cmd;

	if (!slot || !msg)
	{
		return;
	}

	while (1)
	{
		if (msg->readcount > msg->cursize)
		{
			Com_Printf("Split-screen slot %d received malformed server message\n",
				slot->local_index + 1);
			return;
		}

		cmd = MSG_ReadByte(msg);

		if (cmd == -1)
		{
			break;
		}

		switch (cmd)
		{
			case svc_nop:
				break;

			case svc_disconnect:
				slot->connection_state = ca_disconnected;
				return;

			case svc_reconnect:
				slot->connection_state = ca_connecting;
				slot->connect_time = cls.realtime - 1500;
				return;

			case svc_print:
				(void)MSG_ReadByte(msg);
				(void)MSG_ReadString(msg);
				break;

			case svc_centerprint:
				(void)MSG_ReadString(msg);
				break;

			case svc_stufftext:
				SS_HandleStuffText(slot, MSG_ReadString(msg));
				break;

			case svc_serverdata:
				SS_ParseServerData(slot, msg);
				break;

			case svc_configstring:
				SS_ParseConfigString(msg);
				break;

			case svc_sound:
				SS_SkipSoundPacket(msg);
				break;

			case svc_spawnbaseline:
				SS_ParseBaseline(slot, msg);
				break;

			case svc_temp_entity:
				SS_ParseSharedTempEntity(slot, msg);
				break;

			case svc_muzzleflash:
			{
				sizebuf_t saved_message;
				sizebuf_t local_message;
				byte local_data[8];
				int entnum;
				int weapon;

				saved_message = net_message;
				net_message = *msg;
				entnum = MSG_ReadShort(&net_message);
				weapon = MSG_ReadByte(&net_message);
				*msg = net_message;
				net_message = saved_message;

				if (slot->snapshot_valid && entnum == slot->playernum + 1)
				{
					SS_ParseLocalSlotMuzzleFlash(slot, entnum, weapon);
				}
				else
				{
					SZ_Init(&local_message, local_data, sizeof(local_data));
					MSG_WriteShort(&local_message, entnum);
					MSG_WriteByte(&local_message, weapon);
					MSG_BeginReading(&local_message);
					SS_ParseSharedMuzzleFlash(&local_message, false);
				}
				break;
			}

			case svc_muzzleflash2:
				SS_ParseSharedMuzzleFlash(msg, true);
				break;

			case svc_download:
				(void)MSG_ReadShort(msg);
				(void)MSG_ReadByte(msg);
				return;

			case svc_frame:
				SS_ParseFrame(slot, msg);
				break;

			case svc_inventory:
				SS_ParseInventory(slot, msg);
				break;

			case svc_layout:
				Q_strlcpy(slot->layout, MSG_ReadString(msg), sizeof(slot->layout));
				break;

			case svc_playerinfo:
			case svc_packetentities:
			case svc_deltapacketentities:
			default:
				Com_DPrintf("Split-screen slot %d got unsupported server cmd %d\n",
					slot->local_index + 1, cmd);
				return;
		}
	}
}

static qboolean
SS_ShouldShowSharedScoreboard(void)
{
	int i;

	for (i = 0; i < SS_GetSlotCount(); ++i)
	{
		const ss_local_player_t *slot = &ss_state.slots[i];

		if (slot->active && slot->state != SS_SLOT_DROPPED &&
			slot->scoreboard_down)
		{
			return true;
		}
	}

	return false;
}

static int
SS_GetSlotIndexForServerClient(const client_t *server_client)
{
	int i;

	if (!server_client)
	{
		return -1;
	}

	for (i = 0; i < SS_GetSlotCount(); ++i)
	{
		client_t *slot_client;

		if (!SS_FindServerClientForSlot(&ss_state.slots[i], &slot_client, NULL))
		{
			continue;
		}

		if (slot_client == server_client)
		{
			return i;
		}
	}

	return -1;
}

static void
SS_DrawSharedScoreboard(void)
{
	typedef struct
	{
		client_t *server_client;
		int score;
		int local_slot;
	} ss_score_entry_t;

	ss_score_entry_t entries[MAX_CLIENTS];
	float scale;
	int count = 0;
	int i;
	int j;
	int x;
	int y;

	if (!SS_ShouldShowSharedScoreboard())
	{
		return;
	}

	for (i = 0; i < (int)maxclients->value && count < MAX_CLIENTS; ++i)
	{
		client_t *server_client = &svs.clients[i];
		const player_state_t *ps;

		if (server_client->state != cs_spawned)
		{
			continue;
		}

		ps = &server_client->frames[sv.framenum & UPDATE_MASK].ps;
		entries[count].server_client = server_client;
		entries[count].score = ps->stats[STAT_FRAGS];
		entries[count].local_slot = SS_GetSlotIndexForServerClient(server_client);
		++count;
	}

	for (i = 0; i < count; ++i)
	{
		for (j = i + 1; j < count; ++j)
		{
			if (entries[j].score > entries[i].score)
			{
				ss_score_entry_t temp = entries[i];
				entries[i] = entries[j];
				entries[j] = temp;
			}
		}
	}

	scale = SCR_GetMenuScale();
	Draw_Fill(0, 0, viddef.width, viddef.height, 0);
	Draw_Fill((int)(24 * scale), (int)(18 * scale),
		viddef.width - (int)(48 * scale), viddef.height - (int)(36 * scale), 8);
	Draw_Fill((int)(28 * scale), (int)(22 * scale),
		viddef.width - (int)(56 * scale), viddef.height - (int)(44 * scale), 0);

	SS_DrawString((int)(36 * scale), (int)(32 * scale), "SCOREBOARD", true, scale);
	SS_DrawString((int)(36 * scale), (int)(48 * scale), "NAME", false, scale);
	SS_DrawString((int)(220 * scale), (int)(48 * scale), "SCORE", false, scale);
	SS_DrawString((int)(276 * scale), (int)(48 * scale), "PING", false, scale);

	x = (int)(36 * scale);
	y = (int)(64 * scale);

	for (i = 0; i < count && i < 12; ++i)
	{
		char name[48];
		qboolean highlighted = entries[i].local_slot >= 0;

		if (entries[i].local_slot >= 0)
		{
			Com_sprintf(name, sizeof(name), "P%d %s",
				entries[i].local_slot + 1, entries[i].server_client->name);
		}
		else
		{
			Q_strlcpy(name, entries[i].server_client->name, sizeof(name));
		}

		SS_DrawString(x, y + (int)(i * 12 * scale), name, highlighted, scale);
		SS_DrawString((int)(220 * scale), y + (int)(i * 12 * scale),
			va("%d", entries[i].score), highlighted, scale);
		SS_DrawString((int)(276 * scale), y + (int)(i * 12 * scale),
			va("%d", entries[i].server_client->ping), highlighted, scale);
	}
}

static qboolean
SS_GetSlotPlayerState(int slot_index, client_t **client_out,
	const player_state_t **ps_out)
{
	ss_local_player_t *slot = SS_GetSlot(slot_index);
	client_t *server_client;

	if (!slot || !slot->active || slot->state == SS_SLOT_DROPPED)
	{
		return false;
	}

	if (slot->snapshot_valid)
	{
		if (client_out)
		{
			if (SS_FindServerClientForSlot(slot, &server_client, NULL))
			{
				*client_out = server_client;
			}
			else
			{
				*client_out = NULL;
			}
		}

		if (ps_out)
		{
			*ps_out = &slot->frame.playerstate;
		}

		return true;
	}

	if (!SS_FindServerClientForSlot(slot, &server_client, NULL))
	{
		return false;
	}

	if (client_out)
	{
		*client_out = server_client;
	}

	if (ps_out)
	{
		*ps_out = &server_client->frames[sv.framenum & UPDATE_MASK].ps;
	}

	return true;
}

static const byte *
SS_GetSlotAreaBits(const ss_local_player_t *slot, const client_t *server_client)
{
	if (slot && slot->snapshot_valid)
	{
		return slot->frame.areabits;
	}

	if (server_client)
	{
		return server_client->frames[sv.framenum & UPDATE_MASK].areabits;
	}

	return NULL;
}

static int
SS_GetSlotRenderPlayernum(const ss_local_player_t *slot, const client_t *server_client)
{
	if (slot && slot->snapshot_valid && slot->playernum >= 0)
	{
		return slot->playernum;
	}

	if (server_client)
	{
		return (int)(server_client - svs.clients);
	}

	return cl.playernum;
}

static qboolean
SS_IsSlotInventoryOpen(int slot_index)
{
	const ss_local_player_t *slot = SS_GetSlot(slot_index);

	return slot && slot->snapshot_valid &&
		(slot->frame.playerstate.stats[STAT_LAYOUTS] & 2) != 0;
}

static float
SS_GetViewportScale(const ss_viewport_t *viewport, float base_scale)
{
	float width_scale;
	float height_scale;
	float limit;

	if (!viewport || base_scale <= 0.0f)
	{
		return 0.0f;
	}

	width_scale = viewport->w / 320.0f;
	height_scale = viewport->h / 240.0f;
	limit = width_scale;

	if (height_scale < limit)
	{
		limit = height_scale;
	}

	if (limit < 0.5f)
	{
		limit = 0.5f;
	}

	if (base_scale > limit)
	{
		base_scale = limit;
	}

	return base_scale;
}

static void
SS_DrawViewportCrosshair(const ss_viewport_t *viewport, float scale)
{
	char crosshair_pic[MAX_QPATH];
	int crosshair_width;
	int crosshair_height;

	if (!viewport || scale <= 0.0f || !crosshair->value)
	{
		return;
	}

	if (crosshair->value < 0)
	{
		Com_sprintf(crosshair_pic, sizeof(crosshair_pic), "ch0");
	}
	else if (crosshair->value > 3)
	{
		Com_sprintf(crosshair_pic, sizeof(crosshair_pic), "ch3");
	}
	else
	{
	Com_sprintf(crosshair_pic, sizeof(crosshair_pic), "ch%i",
		(int)crosshair->value);
	}
	Draw_GetPicSize(&crosshair_width, &crosshair_height, crosshair_pic);

	if (crosshair_width <= 0 || crosshair_height <= 0)
	{
		return;
	}

	if (crosshair_scale->value > 0)
	{
		scale = crosshair_scale->value;
		scale = SS_GetViewportScale(viewport, scale);
	}

	Draw_PicScaled(viewport->x + (viewport->w - crosshair_width * scale) / 2,
		viewport->y + (viewport->h - crosshair_height * scale) / 2,
		crosshair_pic, scale);
}

static void
SS_DrawViewportIcon(int x, int y, int image_index, float scale)
{
	if (image_index <= 0 || image_index >= MAX_IMAGES)
	{
		return;
	}

	if (cl.configstrings[CS_IMAGES + image_index][0] == '\0')
	{
		return;
	}

	Draw_PicScaled(x, y, cl.configstrings[CS_IMAGES + image_index], scale);
}

static void
SS_DrawViewportStatLine(const ss_viewport_t *viewport, int x, int y,
	int image_index, const char *label, int value, float scale)
{
	int icon_w = 0;
	int icon_h = 0;

	if (!viewport || scale <= 0.0f)
	{
		return;
	}

	if (image_index > 0 && image_index < MAX_IMAGES &&
		cl.configstrings[CS_IMAGES + image_index][0] != '\0')
	{
		Draw_GetPicSize(&icon_w, &icon_h, cl.configstrings[CS_IMAGES + image_index]);
		SS_DrawViewportIcon(x, y, image_index, scale);
	}

	if (label && label[0])
	{
		SS_DrawString(x + (int)((icon_w + 6) * scale), y,
			va("%s %d", label, value), false, scale);
	}
	else
	{
		SS_DrawString(x + (int)((icon_w + 6) * scale), y,
			va("%d", value), false, scale);
	}

	(void)icon_h;
}

static void
SS_DrawViewportStringAtBottom(const ss_viewport_t *viewport, const char *text,
	int line_index, qboolean highlighted, float scale)
{
	int y;

	if (!viewport || !text || !text[0] || scale <= 0.0f)
	{
		return;
	}

	y = viewport->y + viewport->h - (int)((12 + line_index * 10) * scale);
	SS_DrawString(viewport->x + (int)(8 * scale), y, text, highlighted, scale);
}

static void
SS_DrawViewportInventory(int slot_index, const ss_viewport_t *viewport, float scale)
{
	const ss_local_player_t *slot = SS_GetSlot(slot_index);
	int index[MAX_ITEMS];
	int count = 0;
	int selected_num = 0;
	int selected_item;
	int top;
	int i;
	int x;
	int y;
	int display_items = 7;

	if (!viewport || scale <= 0.0f)
	{
		return;
	}

	if (!slot || !slot->snapshot_valid || !SS_IsSlotInventoryOpen(slot_index))
	{
		return;
	}

	selected_item = slot->frame.playerstate.stats[STAT_SELECTED_ITEM];

	for (i = 0; i < MAX_ITEMS; ++i)
	{
		if (i == selected_item)
		{
			selected_num = count;
		}

		if (slot->inventory[i] > 0)
		{
			index[count++] = i;
		}
	}

	if (count <= 0)
	{
		return;
	}

	if (viewport->h < (int)(200 * scale))
	{
		display_items = 5;
	}

	top = selected_num - display_items / 2;

	if (count - top < display_items)
	{
		top = count - display_items;
	}

	if (top < 0)
	{
		top = 0;
	}

	x = viewport->x + (int)(16 * scale);
	y = viewport->y + (int)(36 * scale);

	Draw_Fill(viewport->x + (int)(12 * scale), viewport->y + (int)(20 * scale),
		viewport->w - (int)(24 * scale), viewport->h - (int)(40 * scale), 8);
	Draw_Fill(viewport->x + (int)(16 * scale), viewport->y + (int)(24 * scale),
		viewport->w - (int)(32 * scale), viewport->h - (int)(48 * scale), 0);

	SS_DrawString(x, viewport->y + (int)(28 * scale), "INVENTORY", true, scale);
	SS_DrawString(x, viewport->y + (int)(40 * scale), "USE  COUNT  ITEM", false, scale);

	for (i = top; i < count && i < top + display_items; ++i)
	{
		int item = index[i];
		char line[128];
		qboolean selected = (item == selected_item);
		const char *item_name = cl.configstrings[CS_ITEMS + item];

		Com_sprintf(line, sizeof(line), "%3d  %5d  %s",
			i + 1, slot->inventory[item],
			item_name[0] ? item_name : "unknown");
		SS_DrawString(x, y + (int)((i - top) * 10 * scale), line, selected, scale);
	}

	SS_DrawViewportStringAtBottom(viewport, "DPAD L/R SELECT  DPAD UP USE", 0,
		false, scale);
	SS_DrawViewportStringAtBottom(viewport, "DPAD DOWN CLOSE", 1, false, scale);
}

static const char *
SS_GetADSOverlayPicName(const player_state_t *ps)
{
	const char *gun_model;

	if (!ps || ps->gunindex <= 0 || ps->gunindex >= MAX_MODELS)
	{
		return NULL;
	}

	gun_model = cl.configstrings[CS_MODELS + ps->gunindex];

	if (!gun_model || !gun_model[0])
	{
		return NULL;
	}

	if (strstr(gun_model, "v_blast")) return "ads_blaster.png";
	if (strstr(gun_model, "v_shotg2")) return "ads_supershotgun.png";
	if (strstr(gun_model, "v_shotg")) return "ads_shotgun.png";
	if (strstr(gun_model, "v_machn")) return "ads_machinegun.png";
	if (strstr(gun_model, "v_chain")) return "ads_chaingun.png";
	if (strstr(gun_model, "v_handgr")) return "ads_handgrenade.png";
	if (strstr(gun_model, "v_launch")) return "ads_grenadelauncher.png";
	if (strstr(gun_model, "v_rocket")) return "ads_rocketlauncher.png";
	if (strstr(gun_model, "v_hyperb")) return "ads_hyperblaster.png";
	if (strstr(gun_model, "v_rail")) return "ads_railgun.png";
	if (strstr(gun_model, "v_bfg")) return "ads_mortar.png";

	return NULL;
}

static qboolean
SS_IsSlotADSActive(int slot_index, const player_state_t *ps)
{
	const ss_local_player_t *slot = SS_GetSlot(slot_index);
	const char *overlay_pic;

	if (!slot || cls.key_dest != key_game)
	{
		return false;
	}

	if (slot_index == 0)
	{
		if (!(cl.cmd.buttons & BUTTON_ADS))
		{
			return false;
		}
	}
	else if (!slot->ads_down || slot->menu_open || slot->state == SS_SLOT_DROPPED)
	{
		return false;
	}

	overlay_pic = SS_GetADSOverlayPicName(ps);
	return overlay_pic && Draw_FindPic(overlay_pic) != NULL;
}

static qboolean
SS_IsSlotAttackActive(int slot_index)
{
	const ss_local_player_t *slot = SS_GetSlot(slot_index);

	if (!slot || cls.key_dest != key_game)
	{
		return false;
	}

	if (slot_index == 0)
	{
		return (cl.cmd.buttons & BUTTON_ATTACK) != 0;
	}

	return slot->attack_down && !slot->menu_open && slot->state != SS_SLOT_DROPPED;
}

static const ss_viewmodel_recoil_t *
SS_GetViewmodelRecoil(const player_state_t *ps)
{
	const char *gun_model;

	if (!ps || ps->gunindex <= 0 || ps->gunindex >= MAX_MODELS)
	{
		return &ss_default_recoil;
	}

	gun_model = cl.configstrings[CS_MODELS + ps->gunindex];

	if (!gun_model || !gun_model[0])
	{
		return &ss_default_recoil;
	}

	if (strstr(gun_model, "v_blast"))
	{
		static const ss_viewmodel_recoil_t recoil = { 0.55f, 10.0f, 5.0f, 4.0f };
		return &recoil;
	}

	if (strstr(gun_model, "v_shotg2"))
	{
		static const ss_viewmodel_recoil_t recoil = { 1.0f, 5.0f, 9.0f, 8.0f };
		return &recoil;
	}

	if (strstr(gun_model, "v_shotg"))
	{
		static const ss_viewmodel_recoil_t recoil = { 0.95f, 6.0f, 7.0f, 6.0f };
		return &recoil;
	}

	if (strstr(gun_model, "v_machn"))
	{
		static const ss_viewmodel_recoil_t recoil = { 0.55f, 24.0f, 3.0f, 2.0f };
		return &recoil;
	}

	if (strstr(gun_model, "v_chain"))
	{
		static const ss_viewmodel_recoil_t recoil = { 0.5f, 22.0f, 3.0f, 2.0f };
		return &recoil;
	}

	if (strstr(gun_model, "v_rocket") || strstr(gun_model, "v_launch"))
	{
		static const ss_viewmodel_recoil_t recoil = { 0.95f, 5.0f, 8.0f, 6.0f };
		return &recoil;
	}

	if (strstr(gun_model, "v_rail"))
	{
		static const ss_viewmodel_recoil_t recoil = { 1.0f, 4.0f, 7.0f, 9.0f };
		return &recoil;
	}

	if (strstr(gun_model, "v_hyperb"))
	{
		static const ss_viewmodel_recoil_t recoil = { 0.2f, 30.0f, 1.5f, 1.0f };
		return &recoil;
	}

	return &ss_default_recoil;
}

static void
SS_TriggerSlotViewmodelKick(ss_local_player_t *slot,
	const ss_viewmodel_recoil_t *recoil_cfg, qboolean ads_active, float current_time)
{
	if (!slot || !recoil_cfg)
	{
		return;
	}

	slot->viewmodel_recoil = recoil_cfg->recoil_strength;
	slot->last_attack_time = current_time;

	if (ads_active)
	{
		slot->ads_kick_offset += 20.0f;

		if (slot->ads_kick_offset > 40.0f)
		{
			slot->ads_kick_offset = 40.0f;
		}
	}
}

static void
SS_UpdateSlotCombatVisualState(int slot_index, const player_state_t *ps,
	qboolean ads_active)
{
	ss_local_player_t *slot = SS_GetSlot(slot_index);
	const ss_viewmodel_recoil_t *recoil_cfg;
	float dt;
	float current_time;
	qboolean attack_active;
	int muzzle_seq;

	if (!slot || !ps)
	{
		return;
	}

	dt = cls.rframetime;

	if (dt < 0.0f)
	{
		dt = 0.0f;
	}
	else if (dt > 0.1f)
	{
		dt = 0.1f;
	}

	current_time = cls.realtime * 0.001f;
	recoil_cfg = SS_GetViewmodelRecoil(ps);
	attack_active = SS_IsSlotAttackActive(slot_index);
	muzzle_seq = (slot_index == 0) ? pp_viewmodel_muzzle_seq : slot->muzzle_flash_seq;

	if (slot->last_gunindex != ps->gunindex)
	{
		slot->viewmodel_raise = 0.0f;
		slot->viewmodel_recoil = 0.0f;
		slot->ads_kick_offset = 0.0f;
		slot->viewmodel_valid = false;
		slot->last_gunindex = ps->gunindex;
	}

	if (muzzle_seq != slot->last_muzzle_flash_seq)
	{
		SS_TriggerSlotViewmodelKick(slot, recoil_cfg, ads_active, current_time);
	}
	else if (attack_active && !slot->previous_attack_down)
	{
		SS_TriggerSlotViewmodelKick(slot, recoil_cfg, ads_active, current_time);
	}

	slot->previous_attack_down = attack_active;
	slot->last_muzzle_flash_seq = muzzle_seq;
	slot->ads_active = ads_active;
	slot->viewmodel_recoil -= dt * recoil_cfg->recoil_recovery;

	if (slot->viewmodel_recoil < 0.0f)
	{
		slot->viewmodel_recoil = 0.0f;
	}

	slot->viewmodel_raise += dt * 4.0f;

	if (slot->viewmodel_raise > 1.0f)
	{
		slot->viewmodel_raise = 1.0f;
	}

	slot->ads_kick_offset -= dt * 68.0f;

	if (slot->ads_kick_offset < 0.0f || !ads_active)
	{
		slot->ads_kick_offset = 0.0f;
	}
}

static qboolean
SS_DrawViewportADSOverlay(int slot_index, const ss_viewport_t *viewport,
	const player_state_t *ps)
{
	const char *overlay_pic;
	ss_local_player_t *slot = SS_GetSlot(slot_index);
	float scale;
	int pic_w = 0;
	int pic_h = 0;
	int draw_w;
	int draw_h;
	int draw_x;
	int draw_y;
	int max_kick_y;
	int kick_y = 0;

	if (!viewport || !SS_IsSlotADSActive(slot_index, ps))
	{
		return false;
	}

	overlay_pic = SS_GetADSOverlayPicName(ps);

	if (!overlay_pic)
	{
		return false;
	}

	Draw_GetPicSize(&pic_w, &pic_h, overlay_pic);

	if (pic_w <= 0 || pic_h <= 0)
	{
		return false;
	}

	if (slot)
	{
		kick_y = (int)(slot->ads_kick_offset + 0.5f);
	}

	scale = Q_min(viewport->w / (float)pic_w, viewport->h / (float)pic_h);
	scale *= 0.92f;

	if (scale <= 0.0f)
	{
		return false;
	}

	draw_w = (int)(pic_w * scale + 0.5f);
	draw_h = (int)(pic_h * scale + 0.5f);
	draw_x = viewport->x + (viewport->w - draw_w) / 2;
	draw_y = viewport->y + (viewport->h - draw_h) / 2;
	max_kick_y = Q_max((viewport->h - draw_h) / 2, 0);

	if (kick_y > max_kick_y)
	{
		kick_y = max_kick_y;
	}

	draw_y += kick_y;

	Draw_StretchPic(draw_x, draw_y, draw_w, draw_h, overlay_pic);
	return true;
}

static void
SS_AddSlotViewWeapon(int slot_index, const refdef_t *refdef,
	const player_state_t *ps)
{
	entity_t gun = {0};
	ss_local_player_t *slot = SS_GetSlot(slot_index);
	const player_state_t *ops;
	const ss_viewmodel_recoil_t *recoil_cfg;
	vec3_t base_origin;
	vec3_t base_angles;
	vec3_t forward;
	vec3_t right;
	vec3_t up;
	float current_time;
	float time_since_fire;
	float bob_scale;
	float bob_up;
	float bob_right;
	float hide;
	float lerp;
	int i;

	if (!refdef || !ps || !cl_gun->value || SS_IsSlotADSActive(slot_index, ps))
	{
		return;
	}

	if (ps->gunindex <= 0 || ps->gunindex >= MAX_MODELS)
	{
		return;
	}

	if (ps->fov > 90.0f && cl_gun->value < 2.0f)
	{
		return;
	}

	if (gun_model)
	{
		gun.model = gun_model;
	}
	else
	{
		gun.model = cl.model_draw[ps->gunindex];
	}

	if (!gun.model)
	{
		return;
	}

	ops = SS_GetPreviousPlayerState(slot, ps);
	lerp = SS_GetSlotViewLerp(slot);

	for (i = 0; i < 3; ++i)
	{
		gun.origin[i] = refdef->vieworg[i] + ops->gunoffset[i] +
			lerp * (ps->gunoffset[i] - ops->gunoffset[i]);
		gun.oldorigin[i] = gun.origin[i];
		gun.angles[i] = refdef->viewangles[i] +
			LerpAngle(ops->gunangles[i], ps->gunangles[i], lerp);
	}

	VectorCopy(gun.origin, base_origin);
	VectorCopy(gun.angles, base_angles);

	AngleVectors(refdef->viewangles, forward, right, up);
	recoil_cfg = SS_GetViewmodelRecoil(ps);
	current_time = cls.realtime * 0.001f;
	time_since_fire = current_time - (slot ? slot->last_attack_time : 0.0f);
	bob_scale = (time_since_fire < 0.25f) ? 0.25f : 1.0f;
	bob_up = sinf(current_time * 2.0f) * 0.45f * bob_scale;
	bob_right = sinf(current_time * 1.5f) * 0.35f * bob_scale;
	hide = 1.0f - (slot ? slot->viewmodel_raise : 1.0f);

	VectorMA(gun.origin, bob_up, up, gun.origin);
	VectorMA(gun.origin, bob_right, right, gun.origin);
	VectorMA(gun.origin, -hide * 18.0f, up, gun.origin);
	VectorMA(gun.origin, -hide * 10.0f, forward, gun.origin);
	gun.angles[PITCH] += hide * 22.0f;
	gun.angles[ROLL] += hide * 8.0f;

	if (slot)
	{
		VectorMA(gun.origin, -slot->viewmodel_recoil * recoil_cfg->recoil_push_back,
			forward, gun.origin);
		VectorMA(gun.origin, slot->viewmodel_recoil, up, gun.origin);
		gun.angles[PITCH] -= slot->viewmodel_recoil * recoil_cfg->recoil_pitch_kick;
		gun.angles[ROLL] += sinf(current_time * 1.5f) * 0.75f * bob_scale;
		gun.angles[YAW] += sinf(current_time) * 0.5f * bob_scale;
	}

	if (slot)
	{
		vec3_t proc_origin;
		vec3_t proc_angles;
		float smooth = Q_clamp(cls.rframetime * 24.0f, 0.0f, 1.0f);

		if (!slot->viewmodel_valid)
		{
			for (i = 0; i < 3; ++i)
			{
				slot->viewmodel_origin[i] = gun.origin[i] - base_origin[i];
				slot->viewmodel_angles[i] =
					SS_ViewmodelAngleOffset(gun.angles[i], base_angles[i]);
			}
			slot->viewmodel_valid = true;
		}
		else
		{
			float max_origin_error = 0.0f;

			for (i = 0; i < 3; ++i)
			{
				proc_origin[i] = gun.origin[i] - base_origin[i];
				proc_angles[i] = SS_ViewmodelAngleOffset(gun.angles[i], base_angles[i]);
			}

			for (i = 0; i < 3; ++i)
			{
				float origin_error = fabsf(proc_origin[i] - slot->viewmodel_origin[i]);

				if (origin_error > max_origin_error)
				{
					max_origin_error = origin_error;
				}
			}

			if (max_origin_error > 4.0f)
			{
				smooth = 1.0f;
			}
			else if (max_origin_error > 1.5f)
			{
				smooth = Q_max(smooth, 0.6f);
			}

			for (i = 0; i < 3; ++i)
			{
				slot->viewmodel_origin[i] +=
					(proc_origin[i] - slot->viewmodel_origin[i]) * smooth;
				slot->viewmodel_angles[i] =
					LerpAngle(slot->viewmodel_angles[i], proc_angles[i], smooth);
			}
		}

		for (i = 0; i < 3; ++i)
		{
			gun.origin[i] = base_origin[i] + slot->viewmodel_origin[i];
			gun.angles[i] = base_angles[i] + slot->viewmodel_angles[i];
		}
	}

	gun.frame = ps->gunframe;
	gun.oldframe = ps->gunframe;
	gun.backlerp = 0.0f;
	gun.flags = RF_MINLIGHT | RF_DEPTHHACK | RF_WEAPONMODEL;
	V_AddEntity(&gun);
}

static void
SS_BuildSlotUserinfo(ss_local_player_t *slot)
{
	char name[64];
	char skin[MAX_QPATH];
	const char *base_name;

	if (!slot)
	{
		return;
	}

	Q_strlcpy(slot->userinfo, Cvar_Userinfo(), sizeof(slot->userinfo));

	base_name = Info_ValueForKey(slot->userinfo, "name");

	if (!base_name[0])
	{
		base_name = "Player";
	}

	Com_sprintf(name, sizeof(name), "%s P%d", base_name, slot->local_index + 1);
	Info_SetValueForKey(slot->userinfo, "name", name);

	if (slot->model[0] && slot->skin[0])
	{
		Com_sprintf(skin, sizeof(skin), "%s/%s", slot->model, slot->skin);
		Info_SetValueForKey(slot->userinfo, "skin", skin);
	}
}

static void
SS_SendSlotConnect(ss_local_player_t *slot)
{
	netadr_t adr;
	int previous_slot;

	if (!slot)
	{
		return;
	}

	memset(&adr, 0, sizeof(adr));
	NET_StringToAdr("localhost", &adr);
	adr.port = BigShort(PORT_SERVER);

	SS_BuildSlotUserinfo(slot);
	slot->connect_time = cls.realtime;
	slot->connection_state = ca_connecting;

	previous_slot = NET_GetLoopbackSlot(NS_CLIENT);
	NET_SetLoopbackSlot(NS_CLIENT, slot->loopback_slot);
	Netchan_OutOfBandPrint(NS_CLIENT, adr, "connect %i %i %i \"%s\"\n",
		PROTOCOL_VERSION, (int)Cvar_VariableValue("qport"), 0, slot->userinfo);
	NET_SetLoopbackSlot(NS_CLIENT, previous_slot);
}

static void
SS_TransmitSlot(ss_local_player_t *slot, int length, byte *data)
{
	int previous_slot;

	if (!slot || slot->connection_state < ca_connected)
	{
		return;
	}

	previous_slot = NET_GetLoopbackSlot(NS_CLIENT);
	NET_SetLoopbackSlot(NS_CLIENT, slot->loopback_slot);
	Netchan_Transmit(&slot->netchan, length, data);
	NET_SetLoopbackSlot(NS_CLIENT, previous_slot);
}

static void
SS_QueueSlotStringCmd(ss_local_player_t *slot, const char *cmd)
{
	if (!slot || !cmd)
	{
		return;
	}

	MSG_WriteByte(&slot->netchan.message, clc_stringcmd);
	MSG_WriteString(&slot->netchan.message, cmd);
}

static void
SS_SendSlotStringCmdNow(ss_local_player_t *slot, const char *cmd)
{
	if (!slot || !cmd || slot->connection_state < ca_active)
	{
		return;
	}

	SS_QueueSlotStringCmd(slot, cmd);
	SS_TransmitSlot(slot, 0, NULL);
}

static void
SS_HandleSlotConnectionlessPacket(ss_local_player_t *slot, sizebuf_t *message,
	netadr_t from)
{
	char *command;
	char *line;

	if (!slot || !message)
	{
		return;
	}

	MSG_BeginReading(message);
	MSG_ReadLong(message);
	line = MSG_ReadStringLine(message);

	Cmd_TokenizeString(line, false);
	command = Cmd_Argv(0);

	if (!strcmp(command, "client_connect"))
	{
		Netchan_Setup(NS_CLIENT, &slot->netchan, from,
			(int)Cvar_VariableValue("qport"));
		slot->connection_state = ca_connected;
		SS_QueueSlotStringCmd(slot, "new");

		if (cl.servercount > 0)
		{
			SS_QueueSlotStringCmd(slot, va("begin %i", cl.servercount));
			slot->connection_state = ca_active;
		}

		SS_TransmitSlot(slot, 0, NULL);
	}
}

static void
SS_PollSlotPackets(ss_local_player_t *slot)
{
	byte message_buffer[MAX_MSGLEN];
	sizebuf_t message;
	netadr_t from;
	int previous_slot;

	if (!slot || slot->connection_state == ca_disconnected)
	{
		return;
	}

	SZ_Init(&message, message_buffer, sizeof(message_buffer));
	previous_slot = NET_GetLoopbackSlot(NS_CLIENT);
	NET_SetLoopbackSlot(NS_CLIENT, slot->loopback_slot);

	while (NET_GetPacket(NS_CLIENT, &from, &message))
	{
		if (*(int *)message.data == -1)
		{
			SS_HandleSlotConnectionlessPacket(slot, &message, from);
			SZ_Clear(&message);
			continue;
		}

		if (slot->connection_state < ca_connected)
		{
			SZ_Clear(&message);
			continue;
		}

		if (!NET_CompareAdr(from, slot->netchan.remote_address))
		{
			SZ_Clear(&message);
			continue;
		}

		if (!Netchan_Process(&slot->netchan, &message))
		{
			SZ_Clear(&message);
			continue;
		}

		SS_ParseServerMessage(slot, &message);
		SZ_Clear(&message);
	}

	NET_SetLoopbackSlot(NS_CLIENT, previous_slot);
}

static float
SS_NormalizeAxis(int value)
{
	const int deadzone = 8192;

	if (value > -deadzone && value < deadzone)
	{
		return 0.0f;
	}

	if (value < 0)
	{
		return (float)(value + deadzone) / (32768.0f - deadzone);
	}

	return (float)(value - deadzone) / (32767.0f - deadzone);
}

static void
SS_BuildSlotCmd(ss_local_player_t *slot)
{
	float move_x;
	float move_y;
	float look_x;
	float look_y;
	usercmd_t *cmd;
	int ms;
	int cmd_index;

	if (!slot)
	{
		return;
	}

	if (slot->snapshot_valid)
	{
		SS_ClampSlotPitch(slot, &slot->frame.playerstate);
	}
	else
	{
		if (slot->viewangles[PITCH] > 89.0f)
		{
			slot->viewangles[PITCH] = 89.0f;
		}
		else if (slot->viewangles[PITCH] < -89.0f)
		{
			slot->viewangles[PITCH] = -89.0f;
		}
	}

	cmd_index = slot->netchan.outgoing_sequence & (CMD_BACKUP - 1);
	cmd = &slot->cmds[cmd_index];
	memset(cmd, 0, sizeof(*cmd));

	move_x = SS_NormalizeAxis(slot->axis_left_x);
	move_y = SS_NormalizeAxis(slot->axis_left_y);
	look_x = SS_NormalizeAxis(slot->axis_right_x);
	look_y = SS_NormalizeAxis(slot->axis_right_y);

	slot->viewangles[YAW] -= look_x * cl_yawspeed->value * cls.nframetime * 2.0f;
	slot->viewangles[PITCH] -= look_y * cl_pitchspeed->value * cls.nframetime * 2.0f;

	cmd->angles[PITCH] = ANGLE2SHORT(slot->viewangles[PITCH]);
	cmd->angles[YAW] = ANGLE2SHORT(slot->viewangles[YAW]);
	cmd->angles[ROLL] = ANGLE2SHORT(slot->viewangles[ROLL]);

	cmd->forwardmove = (short)(-move_y * cl_forwardspeed->value);
	cmd->sidemove = (short)(move_x * cl_sidespeed->value);

	if (slot->jump_down)
	{
		cmd->upmove += cl_upspeed->value;
	}

	if (slot->crouch_down)
	{
		cmd->upmove -= cl_upspeed->value;
	}

	if (slot->attack_down)
	{
		cmd->buttons |= BUTTON_ATTACK;
	}

	if (slot->use_down)
	{
		cmd->buttons |= BUTTON_USE;
	}

	if (slot->ads_down)
	{
		cmd->buttons |= BUTTON_ADS;
	}

	ms = (int)(cls.nframetime * 1000.0f);

	if (ms < 1)
	{
		ms = 16;
	}
	else if (ms > 250)
	{
		ms = 100;
	}

	cmd->msec = ms;
	cmd->lightlevel = (byte)cl_lightlevel->value;
	slot->cmd = *cmd;
}

static void
SS_SendSlotMove(ss_local_player_t *slot)
{
	sizebuf_t buf;
	byte data[128];
	usercmd_t nullcmd;
	usercmd_t *cmd;
	usercmd_t *oldcmd;
	int i;
	int checksum_index;

	if (!slot || slot->connection_state < ca_active)
	{
		return;
	}

	SS_BuildSlotCmd(slot);
	SZ_Init(&buf, data, sizeof(data));

	MSG_WriteByte(&buf, clc_move);
	checksum_index = buf.cursize;
	MSG_WriteByte(&buf, 0);
	MSG_WriteLong(&buf, -1);

	i = (slot->netchan.outgoing_sequence - 2) & (CMD_BACKUP - 1);
	cmd = &slot->cmds[i];
	memset(&nullcmd, 0, sizeof(nullcmd));
	MSG_WriteDeltaUsercmd(&buf, &nullcmd, cmd);
	oldcmd = cmd;

	i = (slot->netchan.outgoing_sequence - 1) & (CMD_BACKUP - 1);
	cmd = &slot->cmds[i];
	MSG_WriteDeltaUsercmd(&buf, oldcmd, cmd);
	oldcmd = cmd;

	i = slot->netchan.outgoing_sequence & (CMD_BACKUP - 1);
	cmd = &slot->cmds[i];
	MSG_WriteDeltaUsercmd(&buf, oldcmd, cmd);

	buf.data[checksum_index] = COM_BlockSequenceCRCByte(
		buf.data + checksum_index + 1, buf.cursize - checksum_index - 1,
		slot->netchan.outgoing_sequence);

	SS_TransmitSlot(slot, buf.cursize, buf.data);

	cmd = &slot->cmds[slot->netchan.outgoing_sequence & (CMD_BACKUP - 1)];
	memset(cmd, 0, sizeof(*cmd));
}

static qboolean
SS_FindServerClientForSlot(const ss_local_player_t *slot, client_t **client_out,
	int *client_num_out)
{
	netadr_t adr;
	int i;

	if (!slot || slot->loopback_slot < 0)
	{
		return false;
	}

	memset(&adr, 0, sizeof(adr));
	adr.type = NA_LOOPBACK;
	adr.port = BigShort(slot->loopback_slot + 1);

	for (i = 0; i < maxclients->value; ++i)
	{
		client_t *server_client = &svs.clients[i];

		if (server_client->state != cs_spawned)
		{
			continue;
		}

		if (!NET_CompareAdr(server_client->netchan.remote_address, adr))
		{
			continue;
		}

		if (client_out)
		{
			*client_out = server_client;
		}

		if (client_num_out)
		{
			*client_num_out = i;
		}

		return true;
	}

	return false;
}

static void
SS_ApplyPlayerView(refdef_t *refdef, const ss_local_player_t *slot,
	const player_state_t *ps,
	const byte *areabits, const ss_viewport_t *viewport)
{
	const player_state_t *ops;
	float lerp;
	int i;

	if (!refdef || !ps || !viewport)
	{
		return;
	}

	if (slot && slot->local_index == 0)
	{
		refdef->x = viewport->x;
		refdef->y = viewport->y;
		refdef->width = viewport->w;
		refdef->height = viewport->h;

		if (refdef->fov_x < 1.0f || refdef->fov_x > 179.0f)
		{
			refdef->fov_x = 90.0f;
		}

		refdef->fov_y = CalcFov(refdef->fov_x, (float)refdef->width,
			(float)refdef->height);
		return;
	}

	ops = SS_GetPreviousPlayerState(slot, ps);
	lerp = SS_GetSlotViewLerp(slot);

	for (i = 0; i < 3; ++i)
	{
		refdef->vieworg[i] = ops->pmove.origin[i] * 0.125f + ops->viewoffset[i] +
			lerp * (ps->pmove.origin[i] * 0.125f + ps->viewoffset[i] -
				(ops->pmove.origin[i] * 0.125f + ops->viewoffset[i]));

		if (slot && ps->pmove.pm_type < PM_DEAD)
		{
			refdef->viewangles[i] = slot->viewangles[i] +
				SS_GetDeltaAngle(ps, i) +
				LerpAngle(ops->kick_angles[i], ps->kick_angles[i], lerp);
		}
		else
		{
			refdef->viewangles[i] = LerpAngle(ops->viewangles[i],
				ps->viewangles[i], lerp) +
				LerpAngle(ops->kick_angles[i], ps->kick_angles[i], lerp);
		}
	}

	for (i = 0; i < 4; ++i)
	{
		refdef->blend[i] = ps->blend[i];
	}

	refdef->x = viewport->x;
	refdef->y = viewport->y;
	refdef->width = viewport->w;
	refdef->height = viewport->h;
	refdef->fov_x = ps->fov;
	if (refdef->fov_x < 1.0f || refdef->fov_x > 179.0f)
	{
		refdef->fov_x = 90.0f;
	}
	refdef->fov_y = CalcFov(refdef->fov_x, (float)refdef->width,
		(float)refdef->height);
	refdef->rdflags = ps->rdflags;
	refdef->areabits = (byte *)areabits;
}

static void
SS_RenderSlotView(int slot_index, float stereo_separation)
{
	refdef_t refdef;
	client_t *server_client;
	ss_local_player_t *slot;
	const ss_viewport_t *viewport;
	int previous_playernum;
	int slot_playernum;
	qboolean previous_skip_view_weapon;
	centity_t *previous_entities;
	entity_state_t *previous_parse_entities;
	int previous_entity_count;
	float previous_lerpfrac;
	const player_state_t *ps;
	const byte *areabits;

	slot = SS_GetSlot(slot_index);

	if (!slot || !slot->active || slot->state == SS_SLOT_DROPPED)
	{
		return;
	}

	viewport = &ss_state.viewports[slot_index];

	if (!viewport->active)
	{
		return;
	}

	if (!SS_GetSlotPlayerState(slot_index, &server_client, &ps))
	{
		return;
	}

	areabits = SS_GetSlotAreaBits(slot, server_client);
	slot_playernum = SS_GetSlotRenderPlayernum(slot, server_client);
	previous_playernum = cl.playernum;
	cl.playernum = slot_playernum;
	previous_skip_view_weapon = cl_skip_view_weapon;
	cl_skip_view_weapon = true;

	if (slot->local_index == 0)
	{
		VectorCopy(cl.viewangles, slot->viewangles);
	}

	SS_UpdateSlotCombatVisualState(slot_index, ps,
		SS_IsSlotADSActive(slot_index, ps));

	previous_entities = cl_entities;
	previous_entity_count = cl_numentities;
	previous_parse_entities = cl_entity_parse_stream;
	previous_lerpfrac = cl.lerpfrac;

	if (slot->local_index > 0)
	{
		cl_entities = slot->entities;
		cl_numentities = slot->entity_count;
		cl_entity_parse_stream = slot->parse_entities;
	}

	V_ClearScene();

	if (slot->local_index == 0)
	{
		CL_AddEntities();
	}
	else
	{
		cl.lerpfrac = SS_GetSlotViewLerp(slot);
		CL_AddPacketEntities(&slot->frame);
		CL_AddTEnts();
		CL_AddParticles();
		CL_AddDLights();
		CL_AddLightStyles();
	}

	refdef = cl.refdef;

	cl_entities = previous_entities;
	cl_numentities = previous_entity_count;
	cl_entity_parse_stream = previous_parse_entities;
	cl.lerpfrac = previous_lerpfrac;

	SS_ApplyPlayerView(&refdef, slot, ps, areabits, viewport);
	SS_AddSlotViewWeapon(slot_index, &refdef, ps);

	if (stereo_separation != 0)
	{
		vec3_t forward, right, up, tmp;

		AngleVectors(refdef.viewangles, forward, right, up);
		VectorScale(right, stereo_separation, tmp);
		VectorAdd(refdef.vieworg, tmp, refdef.vieworg);
	}

	refdef.vieworg[0] += 1.0f / 16.0f;
	refdef.vieworg[1] += 1.0f / 16.0f;
	refdef.vieworg[2] += 1.0f / 16.0f;
	refdef.time = cl.time * 0.001f;
	V_PopulateRefdef(&refdef);

	R_RenderFrame(&refdef);

	cl_skip_view_weapon = previous_skip_view_weapon;
	cl.playernum = previous_playernum;
}

static void
SS_DrawViewportHUD(int slot_index)
{
	const ss_viewport_t *viewport = &ss_state.viewports[slot_index];
	const player_state_t *ps;
	qboolean ads_active;
	qboolean inventory_open;
	float scale;
	int margin;
	int line_height;
	int left_x;
	int right_x;
	int icon_w = 0;
	int unused_h = 0;
	int value_x;
	int value_width;

	if (!viewport->active)
	{
		return;
	}

	if (ss_state.slots[slot_index].state == SS_SLOT_DROPPED)
	{
		Draw_Fill(viewport->x, viewport->y, viewport->w, viewport->h, 0);
		return;
	}

	if (!SS_GetSlotPlayerState(slot_index, NULL, &ps))
	{
		return;
	}

	ads_active = SS_DrawViewportADSOverlay(slot_index, viewport, ps);
	inventory_open = SS_IsSlotInventoryOpen(slot_index);
	scale = SS_GetViewportScale(viewport, SCR_GetHUDScale());

	if (scale <= 0.0f)
	{
		return;
	}

	margin = (int)(8 * scale);
	line_height = (int)(12 * scale);
	left_x = viewport->x + margin;
	right_x = viewport->x + viewport->w - margin;

	if (ps->stats[STAT_HEALTH_ICON] > 0 &&
		ps->stats[STAT_HEALTH_ICON] < MAX_IMAGES &&
		cl.configstrings[CS_IMAGES + ps->stats[STAT_HEALTH_ICON]][0] != '\0')
	{
		Draw_GetPicSize(&icon_w, &unused_h,
			cl.configstrings[CS_IMAGES + ps->stats[STAT_HEALTH_ICON]]);
	}
	else
	{
		icon_w = 0;
	}

	value_x = left_x + (int)((icon_w + 6) * scale);
	value_width = (int)(strlen(va("%d", ps->stats[STAT_HEALTH])) * 8 * scale);

	SS_DrawString(left_x, viewport->y + margin, va("P%d", slot_index + 1), true, scale);
	SS_DrawViewportStatLine(viewport, left_x, viewport->y + margin + line_height,
		ps->stats[STAT_HEALTH_ICON], "HP", ps->stats[STAT_HEALTH], scale);

	if (ps->stats[STAT_ARMOR] > 0)
	{
		SS_DrawViewportStatLine(viewport, left_x,
			viewport->y + margin + line_height * 2,
			ps->stats[STAT_ARMOR_ICON], "AR", ps->stats[STAT_ARMOR], scale);
	}

	if (ps->stats[STAT_AMMO] >= 0)
	{
		int ammo_width = (int)(strlen(va("AM %d", ps->stats[STAT_AMMO])) * 8 * scale);
		int ammo_x = right_x - ammo_width;

		if (ps->stats[STAT_AMMO_ICON] > 0 &&
			ps->stats[STAT_AMMO_ICON] < MAX_IMAGES &&
			cl.configstrings[CS_IMAGES + ps->stats[STAT_AMMO_ICON]][0] != '\0')
		{
			int ammo_icon_w = 0;
			int ammo_icon_h = 0;

			Draw_GetPicSize(&ammo_icon_w, &ammo_icon_h,
				cl.configstrings[CS_IMAGES + ps->stats[STAT_AMMO_ICON]]);
			ammo_x -= (int)((ammo_icon_w + 6) * scale);
		}

		SS_DrawViewportStatLine(viewport, ammo_x, viewport->y + margin + line_height,
			ps->stats[STAT_AMMO_ICON], "AM", ps->stats[STAT_AMMO], scale);
	}

	if (ps->stats[STAT_TIMER] > 0)
	{
		int timer_width = (int)(strlen(va("TM %d", ps->stats[STAT_TIMER])) * 8 * scale);
		int timer_x = right_x - timer_width;

		if (ps->stats[STAT_TIMER_ICON] > 0 &&
			ps->stats[STAT_TIMER_ICON] < MAX_IMAGES &&
			cl.configstrings[CS_IMAGES + ps->stats[STAT_TIMER_ICON]][0] != '\0')
		{
			int timer_icon_w = 0;
			int timer_icon_h = 0;

			Draw_GetPicSize(&timer_icon_w, &timer_icon_h,
				cl.configstrings[CS_IMAGES + ps->stats[STAT_TIMER_ICON]]);
			timer_x -= (int)((timer_icon_w + 6) * scale);
		}

		SS_DrawViewportStatLine(viewport, timer_x,
			viewport->y + margin + line_height * 2,
			ps->stats[STAT_TIMER_ICON], "TM", ps->stats[STAT_TIMER], scale);
	}

	if (ps->stats[STAT_SELECTED_ICON] > 0)
	{
		int selected_icon_w = 0;
		int selected_icon_h = 0;

		if (ps->stats[STAT_SELECTED_ICON] < MAX_IMAGES &&
			cl.configstrings[CS_IMAGES + ps->stats[STAT_SELECTED_ICON]][0] != '\0')
		{
			Draw_GetPicSize(&selected_icon_w, &selected_icon_h,
				cl.configstrings[CS_IMAGES + ps->stats[STAT_SELECTED_ICON]]);
			Draw_PicScaled(viewport->x + viewport->w - margin -
				(int)(selected_icon_w * scale),
				viewport->y + viewport->h - margin -
				(int)(selected_icon_h * scale),
				cl.configstrings[CS_IMAGES + ps->stats[STAT_SELECTED_ICON]], scale);
		}
	}

	if (ps->stats[STAT_PICKUP_STRING] > 0 &&
		ps->stats[STAT_PICKUP_STRING] < MAX_CONFIGSTRINGS &&
		cl.configstrings[ps->stats[STAT_PICKUP_STRING]][0] != '\0')
	{
		SS_DrawViewportStringAtBottom(viewport,
			cl.configstrings[ps->stats[STAT_PICKUP_STRING]], 0, false, scale);
	}

	if (ps->stats[STAT_FRAGS] || Cvar_VariableValue("deathmatch"))
	{
		SS_DrawViewportStringAtBottom(viewport,
			va("FRAGS %d", ps->stats[STAT_FRAGS]), 1, false, scale);
	}

	if (ps->stats[STAT_HEALTH] <= 25)
	{
		SS_DrawString(value_x + value_width + (int)(6 * scale),
			viewport->y + margin + line_height, "LOW", true, scale);
	}

	if (!ads_active && !inventory_open)
	{
		SS_DrawViewportCrosshair(viewport, scale);
	}

	if (inventory_open)
	{
		SS_DrawViewportInventory(slot_index, viewport, scale);
	}
}

void
SS_DrawGameplayHUD(void)
{
	int i;

	if (!ss_state.session_active || cls.state != ca_active || !cl.refresh_prepped)
	{
		return;
	}

	SS_UpdateViewports(viddef.width, viddef.height);
	SS_DrawSessionDividerLines();

	for (i = 0; i < SS_GetSlotCount(); ++i)
	{
		if (!ss_state.viewports[i].active)
		{
			if (ss_state.viewports[i].black_fill)
			{
				Draw_Fill(ss_state.viewports[i].x, ss_state.viewports[i].y,
					ss_state.viewports[i].w, ss_state.viewports[i].h, 0);
			}

			continue;
		}

		SS_DrawViewportHUD(i);
	}
}

void
SS_ResetState(void)
{
	int i;

	for (i = 0; i < SS_MAX_LOCAL_PLAYERS; ++i)
	{
		SS_FreeSlotEntities(&ss_state.slots[i]);
	}

	memset(&ss_state, 0, sizeof(ss_state));
	ss_state.transport = SS_TRANSPORT_INTERNET;
	ss_state.requested_players = 2;
	ss_state.last_local_client_frame = -1;
	SS_SetSessionCvar("ss_active", 0);
	SS_SetSessionCvar("ss_players", 0);
}

void
SS_SetTransport(ss_transport_t transport)
{
	ss_state.transport = transport;
	ss_state.enabled = (transport == SS_TRANSPORT_SPLITSCREEN);
}

ss_transport_t
SS_GetTransport(void)
{
	return ss_state.transport;
}

void
SS_SetPlayerCount(int player_count)
{
	ss_state.requested_players = SS_ClampPlayerCount(player_count);
}

int
SS_GetPlayerCount(void)
{
	return SS_ClampPlayerCount(ss_state.requested_players);
}

qboolean
SS_IsSplitScreenSelected(void)
{
	return ss_state.transport == SS_TRANSPORT_SPLITSCREEN;
}

qboolean
SS_IsLobbyActive(void)
{
	return ss_state.lobby_active;
}

void
SS_SetDetectedGamepadCount(int gamepad_count)
{
	int i;
	int max_gamepads = SS_MAX_INPUT_DEVICES - 2;

	if (gamepad_count < 0)
	{
		gamepad_count = 0;
	}
	else if (gamepad_count > max_gamepads)
	{
		gamepad_count = max_gamepads;
	}

	memset(ss_state.device_labels, 0, sizeof(ss_state.device_labels));

	Q_strlcpy(ss_state.device_labels[0], "Unassigned",
		sizeof(ss_state.device_labels[0]));
	Q_strlcpy(ss_state.device_labels[1], "Keyboard+Mouse",
		sizeof(ss_state.device_labels[1]));

	ss_state.device_count = gamepad_count + 2;

	for (i = 0; i < gamepad_count; ++i)
	{
		Com_sprintf(ss_state.device_labels[i + 2],
			sizeof(ss_state.device_labels[i + 2]), "Gamepad%d", i + 1);
	}
}

int
SS_GetDeviceCount(void)
{
	return ss_state.device_count;
}

const char *
SS_GetDeviceLabel(int device_index)
{
	if (device_index < 0 || device_index >= ss_state.device_count)
	{
		return "Unavailable";
	}

	return ss_state.device_labels[device_index];
}

void
SS_SetDeviceLabel(int device_index, const char *label)
{
	if (device_index < 0 || device_index >= SS_MAX_INPUT_DEVICES)
	{
		return;
	}

	Q_strlcpy(ss_state.device_labels[device_index], label ? label : "Unavailable",
		sizeof(ss_state.device_labels[device_index]));
}

void
SS_BeginLobby(void)
{
	int i;
	int player_count = SS_GetPlayerCount();

	ss_state.enabled = true;
	ss_state.lobby_active = true;

	for (i = 0; i < SS_MAX_LOCAL_PLAYERS; ++i)
	{
		ss_local_player_t *slot = &ss_state.slots[i];

		memset(slot, 0, sizeof(*slot));
		slot->local_index = i;

		if (i < player_count)
		{
			slot->active = true;
			slot->state = SS_SLOT_SETUP;
			slot->loopback_slot = i;
			slot->connection_state = ca_disconnected;
			slot->device_index = (i + 1 < ss_state.device_count) ? (i + 1) : 0;
		}
	}
}

void
SS_EndLobby(void)
{
	ss_state.lobby_active = false;
}

qboolean
SS_AreAllSlotsReady(void)
{
	int i;
	int player_count = SS_GetPlayerCount();

	if (player_count <= 0)
	{
		return false;
	}

	for (i = 0; i < player_count; ++i)
	{
		if (!ss_state.slots[i].active || !ss_state.slots[i].ready)
		{
			return false;
		}
	}

	return true;
}

void
SS_SetPendingMatch(const ss_match_config_t *config)
{
	if (!config)
	{
		memset(&ss_state.match, 0, sizeof(ss_state.match));
		return;
	}

	ss_state.match = *config;
	ss_state.match.pending = true;
}

const ss_match_config_t *
SS_GetPendingMatch(void)
{
	return &ss_state.match;
}

qboolean
SS_HasPendingMatch(void)
{
	return ss_state.match.pending;
}

void
SS_ClearPendingMatch(void)
{
	memset(&ss_state.match, 0, sizeof(ss_state.match));
}

qboolean
SS_IsDeviceSelectable(int slot_index, int device_index)
{
	int i;

	if (device_index < 0 || device_index >= ss_state.device_count)
	{
		return false;
	}

	if (device_index == 0)
	{
		return true;
	}

	for (i = 0; i < SS_GetPlayerCount(); ++i)
	{
		if (i == slot_index)
		{
			continue;
		}

		if (ss_state.slots[i].active && ss_state.slots[i].device_index == device_index)
		{
			return false;
		}
	}

	return true;
}

void
SS_CalcViewports(int player_count, int screen_w, int screen_h,
	ss_viewport_t out_rects[SS_MAX_LOCAL_PLAYERS])
{
	int half_w = screen_w / 2;
	int half_h = screen_h / 2;
	int i;

	for (i = 0; i < SS_MAX_LOCAL_PLAYERS; ++i)
	{
		memset(&out_rects[i], 0, sizeof(out_rects[i]));
	}

	player_count = SS_ClampPlayerCount(player_count);

	if (player_count == 2)
	{
		out_rects[0].x = 0;
		out_rects[0].y = 0;
		out_rects[0].w = screen_w;
		out_rects[0].h = half_h;
		out_rects[0].active = true;

		out_rects[1].x = 0;
		out_rects[1].y = half_h;
		out_rects[1].w = screen_w;
		out_rects[1].h = screen_h - half_h;
		out_rects[1].active = true;
		return;
	}

	out_rects[0].x = 0;
	out_rects[0].y = 0;
	out_rects[0].w = half_w;
	out_rects[0].h = half_h;
	out_rects[0].active = true;

	out_rects[1].x = half_w;
	out_rects[1].y = 0;
	out_rects[1].w = screen_w - half_w;
	out_rects[1].h = half_h;
	out_rects[1].active = true;

	out_rects[2].x = 0;
	out_rects[2].y = half_h;
	out_rects[2].w = half_w;
	out_rects[2].h = screen_h - half_h;
	out_rects[2].active = true;

	out_rects[3].x = half_w;
	out_rects[3].y = half_h;
	out_rects[3].w = screen_w - half_w;
	out_rects[3].h = screen_h - half_h;
	out_rects[3].active = (player_count == 4);
	out_rects[3].black_fill = (player_count == 3);
}

void
SS_UpdateViewports(int screen_w, int screen_h)
{
	SS_CalcViewports(SS_GetPlayerCount(), screen_w, screen_h, ss_state.viewports);
}

ss_state_t *
SS_GetState(void)
{
	return &ss_state;
}

ss_local_player_t *
SS_GetSlot(int slot_index)
{
	if (slot_index < 0 || slot_index >= SS_MAX_LOCAL_PLAYERS)
	{
		return NULL;
	}

	return &ss_state.slots[slot_index];
}

void
SS_AssignSlotModelSkin(int slot_index, int model_index, int skin_index,
	const char *model_name, const char *skin_name)
{
	ss_local_player_t *slot = SS_GetSlot(slot_index);

	if (!slot)
	{
		return;
	}

	slot->model_index = model_index;
	slot->skin_index = skin_index;
	slot->ready = false;
	slot->state = SS_SLOT_SETUP;
	Q_strlcpy(slot->model, model_name ? model_name : "", sizeof(slot->model));
	Q_strlcpy(slot->skin, skin_name ? skin_name : "", sizeof(slot->skin));
}

qboolean
SS_AssignSlotDevice(int slot_index, int device_index)
{
	ss_local_player_t *slot = SS_GetSlot(slot_index);

	if (!slot || !SS_IsDeviceSelectable(slot_index, device_index))
	{
		return false;
	}

	slot->device_index = device_index;
	slot->ready = false;
	slot->state = SS_SLOT_SETUP;
	return true;
}

void
SS_ApplyPrimaryProfile(void)
{
	ss_local_player_t *slot = SS_GetSlot(0);
	char skin[MAX_QPATH];

	if (!slot || !slot->model[0] || !slot->skin[0])
	{
		return;
	}

	Com_sprintf(skin, sizeof(skin), "%s/%s", slot->model, slot->skin);
	Cvar_Set("skin", skin);
}

void
SS_BeginSession(void)
{
	int i;

	ss_state.session_active = true;
	NET_SetLoopbackClientCount(SS_GetSlotCount());
	NET_SetLoopbackSlot(NS_CLIENT, 0);

	for (i = 0; i < SS_GetSlotCount(); ++i)
	{
		ss_local_player_t *slot = &ss_state.slots[i];

		slot->menu_open = false;
		slot->menu_cursor = SS_SESSION_ACTION_RESUME;
		slot->exit_hold_active = false;
		slot->exit_hold_start = 0;
		slot->connect_time = 0;
		slot->parse_entities_num = 0;
		memset(&slot->frame, 0, sizeof(slot->frame));
		memset(slot->frames, 0, sizeof(slot->frames));
		memset(slot->parse_entities, 0, sizeof(slot->parse_entities));
		VectorCopy(cl.viewangles, slot->viewangles);
		slot->axis_left_x = 0;
		slot->axis_left_y = 0;
		slot->axis_right_x = 0;
		slot->axis_right_y = 0;
		slot->attack_down = false;
		slot->previous_attack_down = false;
		slot->scoreboard_down = false;
		slot->use_down = false;
		slot->ads_down = false;
		slot->jump_down = false;
		slot->crouch_down = false;
		slot->ads_active = false;
		slot->last_gunindex = 0;
		slot->muzzle_flash_seq = 0;
		slot->last_muzzle_flash_seq = 0;
		slot->viewmodel_recoil = 0.0f;
		slot->viewmodel_raise = 0.0f;
		slot->last_attack_time = 0.0f;
		slot->ads_kick_offset = 0.0f;
		VectorClear(slot->viewmodel_origin);
		VectorClear(slot->viewmodel_angles);
		slot->viewmodel_valid = false;
		slot->connection_state = (i == 0) ? cls.state : ca_disconnected;
		slot->state = SS_SLOT_ACTIVE;

		if (slot->entities && slot->entity_count > 0)
		{
			memset(slot->entities, 0, slot->entity_count * sizeof(*slot->entities));
		}
	}

	SS_SetSessionCvar("ss_active", 1);
	SS_SetSessionCvar("ss_players", SS_GetPlayerCount());
	SS_UpdatePauseState();
}

void
SS_EndSession(void)
{
	int i;

	ss_state.session_active = false;
	ss_state.lobby_active = false;
	NET_SetLoopbackClientCount(1);
	NET_SetLoopbackSlot(NS_CLIENT, 0);

	for (i = 0; i < SS_MAX_LOCAL_PLAYERS; ++i)
	{
		ss_state.slots[i].menu_open = false;
		ss_state.slots[i].exit_hold_active = false;
		ss_state.slots[i].exit_hold_start = 0;
		ss_state.slots[i].connect_time = 0;
		ss_state.slots[i].parse_entities_num = 0;
		ss_state.slots[i].snapshot_valid = false;
		memset(&ss_state.slots[i].frame, 0, sizeof(ss_state.slots[i].frame));
		memset(ss_state.slots[i].frames, 0, sizeof(ss_state.slots[i].frames));
		memset(ss_state.slots[i].parse_entities, 0, sizeof(ss_state.slots[i].parse_entities));
		memset(ss_state.slots[i].cmds, 0, sizeof(ss_state.slots[i].cmds));
		memset(&ss_state.slots[i].cmd, 0, sizeof(ss_state.slots[i].cmd));
		VectorClear(ss_state.slots[i].viewangles);
		ss_state.slots[i].axis_left_x = 0;
		ss_state.slots[i].axis_left_y = 0;
		ss_state.slots[i].axis_right_x = 0;
		ss_state.slots[i].axis_right_y = 0;
		ss_state.slots[i].attack_down = false;
		ss_state.slots[i].previous_attack_down = false;
		ss_state.slots[i].scoreboard_down = false;
		ss_state.slots[i].use_down = false;
		ss_state.slots[i].ads_down = false;
		ss_state.slots[i].jump_down = false;
		ss_state.slots[i].crouch_down = false;
		ss_state.slots[i].ads_active = false;
		ss_state.slots[i].last_gunindex = 0;
		ss_state.slots[i].muzzle_flash_seq = 0;
		ss_state.slots[i].last_muzzle_flash_seq = 0;
		ss_state.slots[i].viewmodel_recoil = 0.0f;
		ss_state.slots[i].viewmodel_raise = 0.0f;
		ss_state.slots[i].last_attack_time = 0.0f;
		ss_state.slots[i].ads_kick_offset = 0.0f;
		VectorClear(ss_state.slots[i].viewmodel_origin);
		VectorClear(ss_state.slots[i].viewmodel_angles);
		ss_state.slots[i].viewmodel_valid = false;
		ss_state.slots[i].connection_state = ca_disconnected;

		if (ss_state.slots[i].entities && ss_state.slots[i].entity_count > 0)
		{
			memset(ss_state.slots[i].entities, 0,
				ss_state.slots[i].entity_count * sizeof(*ss_state.slots[i].entities));
		}
	}

	ss_state.last_local_client_frame = -1;
	SS_ClearPendingMatch();
	SS_SetSessionCvar("ss_active", 0);
	SS_SetSessionCvar("ss_players", 0);
	SS_UpdatePauseState();
}

qboolean
SS_IsSessionActive(void)
{
	return ss_state.session_active;
}

qboolean
SS_IsMenuInputActiveForDevice(int device_index)
{
	ss_local_player_t *slot;

	if (!ss_state.session_active)
	{
		return false;
	}

	slot = SS_FindSlotByDeviceIndex(device_index, false);
	return slot && slot->menu_open;
}

qboolean
SS_ShouldAcceptSessionKey(int device_index, int key)
{
	ss_local_player_t *slot;

	if (!ss_state.session_active)
	{
		return false;
	}

	slot = SS_FindSlotByDeviceIndex(device_index, true);

	if (!slot || slot->state == SS_SLOT_DROPPED)
	{
		return false;
	}

	if (key == K_BTN_START || key == K_ESCAPE)
	{
		return true;
	}

	if (!slot->menu_open)
	{
		return false;
	}

	return SS_IsConfirmKey(key) || SS_IsCloseKey(key) ||
		SS_IsUpKey(key) || SS_IsDownKey(key);
}

qboolean
SS_HandleSessionKey(int key, qboolean down)
{
	ss_local_player_t *slot;
	int device_index;

	if (!ss_state.session_active || cls.key_dest != key_game)
	{
		return false;
	}

	device_index = SS_GetEventDeviceIndex();
	slot = SS_FindSlotByDeviceIndex(device_index, true);

	if (!slot || slot->state == SS_SLOT_DROPPED)
	{
		return false;
	}

	if (!down)
	{
		if (slot->menu_open && SS_IsConfirmKey(key))
		{
			slot->exit_hold_active = false;
			slot->exit_hold_start = 0;
			return true;
		}

		return false;
	}

	if (key == K_BTN_START || key == K_ESCAPE)
	{
		if (slot->menu_open)
		{
			SS_CloseSlotMenu(slot);
		}
		else
		{
			SS_OpenSlotMenu(slot);
		}

		return true;
	}

	if (!slot->menu_open)
	{
		return false;
	}

	if (key == K_BTN_EAST || key == K_BTN_BACK)
	{
		SS_CloseSlotMenu(slot);
		return true;
	}

	if (SS_IsUpKey(key))
	{
		SS_AdvanceMenuCursor(slot, -1);
		return true;
	}

	if (SS_IsDownKey(key))
	{
		SS_AdvanceMenuCursor(slot, 1);
		return true;
	}

	if (SS_IsConfirmKey(key))
	{
		SS_ActivateMenuSelection(slot);
		return true;
	}

	return false;
}

qboolean
SS_ShouldCaptureGameplayDevice(int device_index)
{
	ss_local_player_t *slot;

	if (!ss_state.session_active)
	{
		return false;
	}

	slot = SS_FindSlotByDeviceIndex(device_index, false);

	if (!slot || slot->loopback_slot <= 0 || slot->state == SS_SLOT_DROPPED)
	{
		return false;
	}

	return !slot->menu_open;
}

qboolean
SS_HandleGameplayKey(int key, qboolean down)
{
	ss_local_player_t *slot;
	int device_index;

	if (!ss_state.session_active || cls.key_dest != key_game)
	{
		return false;
	}

	device_index = SS_GetEventDeviceIndex();
	slot = SS_FindSlotByDeviceIndex(device_index, false);

	if (!slot || slot->state == SS_SLOT_DROPPED)
	{
		return false;
	}

	if (SS_IsScoreboardKey(key))
	{
		slot->scoreboard_down = down;
		return true;
	}

	if (slot->loopback_slot <= 0 || slot->menu_open)
	{
		return false;
	}

	switch (key)
	{
		case K_SHOULDER_LEFT:
			if (!down)
			{
				return true;
			}
			SS_SendSlotStringCmdNow(slot, "weapprev");
			return true;

		case K_SHOULDER_RIGHT:
			if (!down)
			{
				return true;
			}
			SS_SendSlotStringCmdNow(slot, "weapnext");
			return true;

		case K_DPAD_LEFT:
			if (!down)
			{
				return true;
			}
			SS_SendSlotStringCmdNow(slot,
				SS_IsSlotInventoryOpen(slot->local_index) ? "invprev" : "weapprev");
			return true;

		case K_DPAD_RIGHT:
			if (!down)
			{
				return true;
			}
			SS_SendSlotStringCmdNow(slot,
				SS_IsSlotInventoryOpen(slot->local_index) ? "invnext" : "weapnext");
			return true;

		case K_DPAD_UP:
			if (!down)
			{
				return true;
			}
			SS_SendSlotStringCmdNow(slot, "invuse");
			return true;

		case K_DPAD_DOWN:
			if (!down)
			{
				return true;
			}
			SS_SendSlotStringCmdNow(slot, "inven");
			return true;

		case K_TRIG_RIGHT:
			slot->attack_down = down;
			return true;

		case K_TRIG_LEFT:
			slot->ads_down = down;
			return true;

		case K_BTN_WEST:
			slot->use_down = down;
			return true;

		case K_BTN_SOUTH:
			slot->jump_down = down;
			return true;

		case K_BTN_EAST:
			slot->crouch_down = down;
			return true;
	}

	return false;
}

void
SS_SetDeviceAxis(int device_index, ss_axis_t axis, int value)
{
	ss_local_player_t *slot = SS_FindSlotByDeviceIndex(device_index, false);

	if (!slot || slot->loopback_slot <= 0 || slot->menu_open ||
		slot->state == SS_SLOT_DROPPED)
	{
		return;
	}

	switch (axis)
	{
		case SS_AXIS_LEFT_X:
			slot->axis_left_x = value;
			break;

		case SS_AXIS_LEFT_Y:
			slot->axis_left_y = value;
			break;

		case SS_AXIS_RIGHT_X:
			slot->axis_right_x = value;
			break;

		case SS_AXIS_RIGHT_Y:
			slot->axis_right_y = value;
			break;
	}
}

qboolean
SS_RenderViews(float stereo_separation)
{
	int i;

	if (!ss_state.session_active || cls.state != ca_active || !cl.refresh_prepped)
	{
		return false;
	}

	SS_UpdateViewports(viddef.width, viddef.height);

	for (i = 0; i < SS_GetSlotCount(); ++i)
	{
		if (!ss_state.viewports[i].active)
		{
			if (ss_state.viewports[i].black_fill)
			{
				Draw_Fill(ss_state.viewports[i].x, ss_state.viewports[i].y,
					ss_state.viewports[i].w, ss_state.viewports[i].h, 0);
			}

			continue;
		}

		SS_RenderSlotView(i, stereo_separation);
	}

	return true;
}

void
SS_DrawSessionOverlay(void)
{
	static const char *menu_items[SS_SESSION_ACTION_COUNT] =
	{
		"Resume",
		"Drop Out",
		"Exit Match"
	};
	float scale;
	int i;
	int item;
	int y;

	if (!ss_state.session_active || cls.key_dest != key_game)
	{
		return;
	}

	scale = SCR_GetMenuScale();
	SS_UpdateViewports(viddef.width, viddef.height);
	SS_DrawSessionDividerLines();

	for (i = 0; i < SS_GetSlotCount(); ++i)
	{
		const ss_viewport_t *viewport = &ss_state.viewports[i];
		ss_local_player_t *slot = &ss_state.slots[i];

		if (!viewport->active)
		{
			continue;
		}

		if (slot->state == SS_SLOT_DROPPED)
		{
			Draw_Fill(viewport->x, viewport->y, viewport->w, viewport->h, 0);
			SS_DrawCenteredStringInRect(viewport,
				viewport->y + viewport->h / 2 - (int)(12 * scale),
				va("P%d DROPPED", i + 1), true, scale);
			continue;
		}

		if (!slot->menu_open)
		{
			continue;
		}

		Draw_Fill(viewport->x, viewport->y, viewport->w, viewport->h, 0);
		Draw_Fill(viewport->x + 12, viewport->y + 12,
			viewport->w - 24, viewport->h - 24, 8);
		Draw_Fill(viewport->x + 16, viewport->y + 16,
			viewport->w - 32, viewport->h - 32, 0);

		SS_DrawCenteredStringInRect(viewport, viewport->y + (int)(28 * scale),
			va("PLAYER %d", i + 1), true, scale);

		for (item = 0; item < SS_SESSION_ACTION_COUNT; ++item)
		{
			y = viewport->y + (int)((58 + item * 18) * scale);

			SS_DrawCenteredStringInRect(viewport, y, menu_items[item],
				slot->menu_cursor == item, scale);
		}

		SS_DrawCenteredStringInRect(viewport,
			viewport->y + viewport->h - (int)(42 * scale),
			SS_GetDeviceLabel(slot->device_index), false, scale);

		if (slot->menu_cursor == SS_SESSION_ACTION_EXIT)
		{
			unsigned int hold_elapsed = 0;

			if (slot->exit_hold_active)
			{
				hold_elapsed = Sys_Milliseconds() - slot->exit_hold_start;

				if (hold_elapsed >= 3000)
				{
					SS_ExitToMultiplayerMenu();
					return;
				}
			}

			SS_DrawCenteredStringInRect(viewport,
				viewport->y + viewport->h - (int)(26 * scale),
				SS_GetExitPrompt(slot), false, scale);

			Draw_Fill(viewport->x + 28,
				viewport->y + viewport->h - (int)(14 * scale),
				viewport->w - 56, (int)(6 * scale), 8);

			if (slot->exit_hold_active)
			{
				int fill_w = (int)(((viewport->w - 56) * hold_elapsed) / 3000.0f);
				Draw_Fill(viewport->x + 28,
					viewport->y + viewport->h - (int)(14 * scale),
					fill_w, (int)(6 * scale), 4);
			}
		}
	}

	if (SS_GetSlotCount() == 3 && ss_state.viewports[3].black_fill)
	{
		const ss_viewport_t *viewport = &ss_state.viewports[3];
		Draw_Fill(viewport->x, viewport->y, viewport->w, viewport->h, 0);
	}

	if (!SS_HasOpenSessionMenu())
	{
		SS_DrawSharedScoreboard();
	}
}

void
SS_RunLocalClients(void)
{
	int i;
	qboolean allow_send;

	if (!ss_state.session_active || !Com_ServerState() ||
		cls.state < ca_connected || cl.servercount <= 0)
	{
		return;
	}

	allow_send = (ss_state.last_local_client_frame != cls.framecount);
	ss_state.slots[0].connection_state = cls.state;

	for (i = 1; i < SS_GetSlotCount(); ++i)
	{
		ss_local_player_t *slot = &ss_state.slots[i];

		if (!slot->active || slot->state == SS_SLOT_DROPPED)
		{
			continue;
		}

		SS_PollSlotPackets(slot);

		if (slot->connection_state == ca_disconnected)
		{
			if (allow_send)
			{
				SS_SendSlotConnect(slot);
			}
			continue;
		}

		if (slot->connection_state == ca_connecting)
		{
			if (allow_send && cls.realtime - slot->connect_time >= 3000)
			{
				SS_SendSlotConnect(slot);
			}

			continue;
		}

		if (allow_send && slot->connection_state >= ca_active)
		{
			SS_SendSlotMove(slot);
		}
		else if (allow_send && slot->connection_state >= ca_connected)
		{
			if (slot->netchan.message.cursize ||
				(cls.realtime - slot->netchan.last_sent > 1000))
			{
				SS_TransmitSlot(slot, 0, NULL);
			}
		}
	}

	if (allow_send)
	{
		ss_state.last_local_client_frame = cls.framecount;
	}
}
