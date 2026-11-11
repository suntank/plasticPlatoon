/*
 * Local multiplayer setup. Kept separate from the single-cursor menus, while
 * reusing their model catalogue and match launcher. All drawing uses physical
 * pixels and one fitted scale; gameplay viewport geometry is independent.
 */

enum
{
	SS_LOBBY_DEVICE,
	SS_LOBBY_MODEL,
	SS_LOBBY_SKIN,
	SS_LOBBY_READY,
	SS_LOBBY_ROWS
};

static menuframework_s s_splitscreen_lobby_menu;
static int s_splitscreen_lobby_cursor[SS_MAX_LOCAL_PLAYERS];
static int s_splitscreen_keyboard_slot;
static char s_splitscreen_notice[96];
static int s_splitscreen_notice_until;

static void
SplitScreenLobby_Notice(const char *message)
{
	Q_strlcpy(s_splitscreen_notice, message, sizeof(s_splitscreen_notice));
	s_splitscreen_notice_until = cls.realtime + 3500;
}

static void
SplitScreenLobby_Close(void)
{
	PlayerModelFree();
	SS_EndLobby();
	SS_ClearPendingMatch();
}

static void
SplitScreenLobby_SyncSlotModelSkin(int slot_index)
{
	ss_local_player_t *slot = SS_GetSlot(slot_index);

	if (!slot || slot->model_index < 0 || slot->model_index >= s_modelname.num)
	{
		return;
	}

	if (slot->skin_index < 0 || slot->skin_index >= s_skinnames[slot->model_index].num)
	{
		slot->skin_index = 0;
	}

	SS_AssignSlotModelSkin(slot_index, slot->model_index, slot->skin_index,
		s_modelname.data[slot->model_index],
		s_skinnames[slot->model_index].data[slot->skin_index]);
}

static void
SplitScreenLobby_CycleChoice(int slot_index, int direction)
{
	ss_local_player_t *slot = SS_GetSlot(slot_index);
	int row = s_splitscreen_lobby_cursor[slot_index];
	int count, device, attempt;

	if (slot->ready)
	{
		SplitScreenLobby_Notice("Cancel ready before changing your setup.");
		return;
	}

	switch (row)
	{
		case SS_LOBBY_DEVICE:
			count = SS_GetDeviceCount();
			device = slot->device_index;
			for (attempt = 0; attempt < count; ++attempt)
			{
				device = (device + direction + count) % count;
				/* Never cycle onto an unreachable or empty device. */
				if (SS_IsDeviceConnected(device) &&
					SS_IsDeviceSelectable(slot_index, device) &&
					SS_AssignSlotDevice(slot_index, device))
				{
					SplitScreenLobby_Notice("Input selected. Confirm each player with their assigned input.");
					return;
				}
			}
			SplitScreenLobby_Notice("Connect another controller, or cancel its ready state.");
			break;
		case SS_LOBBY_MODEL:
			if (s_modelname.num > 0)
			{
				slot->model_index = (slot->model_index + direction + s_modelname.num) % s_modelname.num;
				slot->skin_index = 0;
				SplitScreenLobby_SyncSlotModelSkin(slot_index);
			}
			break;
		case SS_LOBBY_SKIN:
			count = s_skinnames[slot->model_index].num;
			if (count > 0)
			{
				slot->skin_index = (slot->skin_index + direction + count) % count;
				SplitScreenLobby_SyncSlotModelSkin(slot_index);
			}
			break;
	}
}

static qboolean
SplitScreenLobby_MenuInit(void)
{
	int model = 0, skin_index = 0, i;

	PlayerModelFree();
	if (!PlayerConfig_ScanDirectories())
	{
		PlayerModelFree();
		return false;
	}

	PlayerConfig_GetDefaultSelection(&model, &skin_index);
	SS_RefreshDevices();
	SS_BeginLobby();
	s_splitscreen_keyboard_slot = 0;
	s_splitscreen_notice_until = 0;

	for (i = 0; i < SS_GetPlayerCount(); ++i)
	{
		ss_local_player_t *slot = SS_GetSlot(i);
		s_splitscreen_lobby_cursor[i] = SS_LOBBY_READY;
		slot->model_index = model;
		slot->skin_index = skin_index;
		SplitScreenLobby_SyncSlotModelSkin(i);
		if (slot->device_index == 1)
		{
			s_splitscreen_keyboard_slot = i;
		}
	}
	return true;
}

/* Bounded strings prevent long device/model/map names from crossing cards. */
static void
SplitScreenLobby_DrawText(int x, int y, int width, const char *text,
	float scale, qboolean highlight)
{
	int i, columns = (int)(width / (8 * scale));
	int length = strlen(text);

	for (i = 0; i < columns && i < length; ++i)
	{
		int character = (unsigned char)text[i];
		if (length > columns && i >= columns - 3)
		{
			character = '.';
		}
		Draw_CharScaled(x + (int)(i * 8 * scale), y,
			character + (highlight ? 128 : 0), scale);
	}
}

static void
SplitScreenLobby_DrawPanel(int slot_index, int x, int y, int w, int h, float scale)
{
	ss_local_player_t *slot = SS_GetSlot(slot_index);
	qboolean connected = SS_IsDeviceConnected(slot->device_index);
	int inset = (int)(10 * scale);
	int row, row_height = (int)((SS_GetPlayerCount() > 2 ? 17 : 26) * scale);
	int row_y = y + (int)(30 * scale);
	int border = (int)scale;
	char text[128];
	const char *status;

	if (border < 1)
	{
		border = 1;
	}
	Draw_Fill(x, y, w, h, slot->ready ? 112 : 24);
	Draw_Fill(x + border, y + border, w - border * 2, h - border * 2, 0);
	Com_sprintf(text, sizeof(text), "PLAYER %d%s", slot_index + 1,
		slot->ready ? "   READY" : "   SETUP");
	SplitScreenLobby_DrawText(x + inset, y + (int)(10 * scale), w - 2 * inset,
		text, scale, true);

	for (row = 0; row < SS_LOBBY_ROWS; ++row)
	{
		qboolean selected = s_splitscreen_lobby_cursor[slot_index] == row;
		switch (row)
		{
			case SS_LOBBY_DEVICE:
				Com_sprintf(text, sizeof(text), "Input: %s", SS_GetDeviceLabel(slot->device_index));
				break;
			case SS_LOBBY_MODEL:
				Com_sprintf(text, sizeof(text), "Model: %s", slot->model);
				break;
			case SS_LOBBY_SKIN:
				Com_sprintf(text, sizeof(text), "Skin:  %s", slot->skin);
				break;
			default:
				Q_strlcpy(text, slot->ready ? "Cancel ready" : "Ready", sizeof(text));
				break;
		}
		if (selected)
		{
			Draw_Fill(x + inset / 2, row_y - (int)(3 * scale), w - inset,
				(int)(14 * scale), 16);
		}
		SplitScreenLobby_DrawText(x + inset, row_y, (int)(8 * scale),
			selected ? ">" : " ", scale, true);
		SplitScreenLobby_DrawText(x + inset + (int)(12 * scale), row_y,
			w - 2 * inset - (int)(12 * scale), text, scale, false);
		row_y += row_height;
	}

	if (!connected)
	{
		status = slot->device_index ? "Disconnected - reconnect controller" : "Press confirm on a controller to join";
	}
	else if (slot->ready)
	{
		status = "Input confirmed - ready to play";
	}
	else
	{
		status = slot->device_index == 1 ? "Press Enter on Ready to confirm" :
			(japanese_confirm ? "Press B on Ready to confirm input" : "Press A on Ready to confirm input");
	}
	SplitScreenLobby_DrawText(x + inset, y + h - (int)(17 * scale), w - 2 * inset,
		status, scale, !connected);
}

static void
SplitScreenLobby_MenuDraw(void)
{
	float scale = SCR_GetMenuScale();
	int x, y, w, i, rows = SS_GetPlayerCount() > 2 ? 2 : 1;
	const ss_match_config_t *match = SS_GetPendingMatch();
	char text[160];
	const char *status;

	SS_RefreshDevices();
	/* A fitted canvas also works when the user selects an oversized menu scale. */
	if (scale > viddef.width / 640.0f)
	{
		scale = viddef.width / 640.0f;
	}
	if (scale > viddef.height / 420.0f)
	{
		scale = viddef.height / 420.0f;
	}
	x = (viddef.width - (int)(640 * scale)) / 2;
	y = (viddef.height - (int)(420 * scale)) / 2;
	w = (int)(624 * scale);
	Draw_Fill(0, 0, viddef.width, viddef.height, 0);
	Com_sprintf(text, sizeof(text), "SPLIT-SCREEN / %d PLAYERS", SS_GetPlayerCount());
	SplitScreenLobby_DrawText(x + (int)(8 * scale), y + (int)(10 * scale), w, text, scale, true);
	Com_sprintf(text, sizeof(text), "2. Controllers  |  %s  |  %s",
		match->coop ? "Cooperative" : "Deathmatch", match->startmap);
	SplitScreenLobby_DrawText(x + (int)(8 * scale), y + (int)(29 * scale), w, text, scale, false);
	SplitScreenLobby_DrawText(x + (int)(8 * scale), y + (int)(48 * scale), w,
		"Each player: confirm Ready with your own controller.", scale, false);

	for (i = 0; i < SS_GetPlayerCount(); ++i)
	{
		int panel_y = rows == 2 ? 70 + (i / 2) * 136 : 84;
		int panel_h = rows == 2 ? 128 : 224;
		SplitScreenLobby_DrawPanel(i, x + (int)((8 + (i % 2) * 318) * scale),
			y + (int)(panel_y * scale), (int)(306 * scale), (int)(panel_h * scale), scale);
	}

	status = SS_AreAllSlotsReady() ? "ALL READY - Player 1: press Start  /  Keyboard: F10" :
		"Waiting for every player to confirm Ready.";
	SplitScreenLobby_DrawText(x + (int)(8 * scale), y + (int)(349 * scale), w, status, scale, true);
	if (cls.realtime < s_splitscreen_notice_until)
	{
		status = s_splitscreen_notice;
	}
	else
	{
		Com_sprintf(text, sizeof(text), "Keyboard editing Player %d  |  Tab: next player  |  Esc: back",
			s_splitscreen_keyboard_slot + 1);
		status = text;
	}
	SplitScreenLobby_DrawText(x + (int)(8 * scale), y + (int)(370 * scale), w, status, scale, false);
	SplitScreenLobby_DrawText(x + (int)(8 * scale), y + (int)(389 * scale), w,
		japanese_confirm ? "D-pad/arrows: select & change  |  B: confirm  |  A: cancel ready/back" :
		"D-pad/arrows: select & change  |  A: confirm  |  B: cancel ready/back", scale, false);
	SplitScreenLobby_DrawText(x + (int)(8 * scale), y + (int)(405 * scale), w,
		japanese_confirm ? "Unassigned pad: B to join  |  Any pad: A/Select again when unready goes back" :
		"Unassigned pad: A to join  |  Any pad: B/Select again when unready goes back", scale, false);
}

static const char *
SplitScreenLobby_Start(int source_device)
{
	ss_match_config_t config;
	ss_local_player_t *host = SS_GetSlot(0);

	if (source_device != 1 && source_device != host->device_index)
	{
		SplitScreenLobby_Notice("Player 1 starts the match once everyone is ready.");
		return menu_move_sound;
	}
	if (!SS_AreAllSlotsReady())
	{
		SplitScreenLobby_Notice("Each player must confirm Ready with their own input first.");
		return menu_move_sound;
	}
	if (!SS_HasPendingMatch())
	{
		SplitScreenLobby_Notice("Go back and choose match settings first.");
		return menu_move_sound;
	}
	/* Close frees the pending config, so launch from our own copy. */
	config = *SS_GetPendingMatch();
	SplitScreenLobby_Close();
	StartServer_ExecuteConfig(&config, true);
	M_ForceMenuOff();
	return menu_in_sound;
}

static const char *
SplitScreenLobby_MenuKey(int key)
{
	int gamepad = Key_GetEventGamepadIndex();
	int device = gamepad >= 0 ? gamepad + 2 : 1;
	int menu_key = Key_GetMenuKey(key);
	int slot_index;
	ss_local_player_t *slot;

	SS_RefreshDevices();
	if (gamepad < 0 && menu_key == K_ESCAPE)
	{
		M_PopMenu();
		return NULL;
	}
	if ((gamepad >= 0 && key == K_BTN_START) || (gamepad < 0 && key == K_F10))
	{
		return SplitScreenLobby_Start(device);
	}
	/* Keyboard remains a setup fallback even when every player uses a pad. */
	if (gamepad < 0 && key == K_TAB)
	{
		s_splitscreen_keyboard_slot = (s_splitscreen_keyboard_slot + 1) % SS_GetPlayerCount();
		return menu_move_sound;
	}
	slot_index = gamepad >= 0 ? SS_FindLobbySlotForDevice(device) : s_splitscreen_keyboard_slot;
	if (slot_index < 0)
	{
		if (menu_key == K_ESCAPE || menu_key == K_BACKSPACE || key == K_BTN_BACK)
		{
			M_PopMenu();
			return NULL;
		}
		if (menu_key == K_ENTER)
		{
			slot_index = SS_JoinLobbyDevice(device);
			if (slot_index >= 0)
			{
				s_splitscreen_lobby_cursor[slot_index] = SS_LOBBY_READY;
				SplitScreenLobby_Notice("Controller joined. Confirm Ready when you are set.");
				return menu_in_sound;
			}
			SplitScreenLobby_Notice("All players have inputs. Use Keyboard Tab to edit assignments.");
		}
		return NULL;
	}
	slot = SS_GetSlot(slot_index);
	if (!slot || !slot->active)
	{
		return NULL;
	}
	if (menu_key == K_ESCAPE || menu_key == K_BACKSPACE || key == K_BTN_BACK)
	{
		/* A lone controller may be assigned to P2 while P1 uses the keyboard.
		 * Every local input needs a way out even when other players are absent. */
		if (gamepad >= 0 && !slot->ready)
		{
			M_PopMenu();
			return NULL;
		}
		SS_SetSlotReady(slot_index, false);
		s_splitscreen_lobby_cursor[slot_index] = SS_LOBBY_READY;
		return menu_out_sound;
	}

	switch (menu_key)
	{
		case K_UPARROW:
		case 'w':
		case 'W':
			s_splitscreen_lobby_cursor[slot_index] =
				(s_splitscreen_lobby_cursor[slot_index] + SS_LOBBY_ROWS - 1) % SS_LOBBY_ROWS;
			return menu_move_sound;
		case K_DOWNARROW:
		case 's':
		case 'S':
			s_splitscreen_lobby_cursor[slot_index] =
				(s_splitscreen_lobby_cursor[slot_index] + 1) % SS_LOBBY_ROWS;
			return menu_move_sound;
		case K_LEFTARROW:
		case 'a':
		case 'A':
			SplitScreenLobby_CycleChoice(slot_index, -1);
			return menu_move_sound;
		case K_RIGHTARROW:
		case 'd':
		case 'D':
			SplitScreenLobby_CycleChoice(slot_index, 1);
			return menu_move_sound;
		case K_ENTER:
		case K_SPACE:
			if (s_splitscreen_lobby_cursor[slot_index] != SS_LOBBY_READY)
			{
				SplitScreenLobby_CycleChoice(slot_index, 1);
				return menu_move_sound;
			}
			if (!slot->ready && slot->device_index != device)
			{
				SplitScreenLobby_Notice("Use this player's assigned controller to confirm Ready.");
				return menu_move_sound;
			}
			if (!SS_SetSlotReady(slot_index, !slot->ready))
			{
				SplitScreenLobby_Notice("Connect and select an input before confirming Ready.");
				return menu_move_sound;
			}
			return slot->ready ? menu_in_sound : menu_out_sound;
	}
	return NULL;
}

static void
M_Menu_SplitScreenLobby_f(void)
{
	if (!SplitScreenLobby_MenuInit())
	{
		Menu_SetStatusBar(&s_startserver_menu, "no valid player models found");
		return;
	}
	s_splitscreen_lobby_menu.draw = SplitScreenLobby_MenuDraw;
	s_splitscreen_lobby_menu.key = SplitScreenLobby_MenuKey;
	M_PushMenu(&s_splitscreen_lobby_menu);
}
