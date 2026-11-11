#include "../../src/client/cl_splitscreen.c"
#include <assert.h>

static int pad_ids[SS_MAX_LOCAL_PLAYERS] = {-1, -1, -1, -1};
static int freed_entities;
static int event_gamepad, loopback_slot, sent_slot, transmitted;
static char sent_command[128];
client_static_t cls;
char *keybindings[K_LAST];
static cvar_t move_speed = {.value = 200}, turn_speed = {.value = 140};
static cvar_t pitch_speed = {.value = 150}, run = {.value = 1}, light = {.value = 128};
static float pad_pitch_speed = 120, pad_yaw_speed = 160, pad_deadzone = 0.16f;
static float ads_sensitivity = 0.5f, auto_level, auto_level_time = 0.25f;
cvar_t *cl_forwardspeed = &move_speed, *cl_sidespeed = &move_speed;
cvar_t *cl_upspeed = &move_speed, *cl_yawspeed = &turn_speed;
cvar_t *cl_pitchspeed = &pitch_speed, *cl_run = &run, *cl_lightlevel = &light;

qboolean IN_IsGamepadConnected(int index) { return pad_ids[index] >= 0; }
int IN_GetDetectedGamepadId(int index) { return pad_ids[index]; }
const char *IN_GetDetectedGamepadName(int index) { return "Same controller model"; }
cvar_t *Cvar_Get(const char *name, const char *value, int flags) { return NULL; }
void Cvar_SetValue(const char *name, float value) {}
cvar_t *Cvar_Set(const char *name, const char *value) { return NULL; }
float Cvar_VariableValue(const char *name)
{
	if (!strcmp(name, "joy_pitchspeed")) return pad_pitch_speed;
	if (!strcmp(name, "joy_yawspeed")) return pad_yaw_speed;
	if (!strcmp(name, "cl_ads_sensitivity")) return ads_sensitivity;
	if (!strcmp(name, "cl_gamebird_autolevel")) return auto_level;
	if (!strcmp(name, "cl_gamebird_autolevel_time")) return auto_level_time;
	if (!strcmp(name, "joy_left_deadzone") || !strcmp(name, "joy_right_deadzone"))
		return pad_deadzone;
	return 1.0f;
}
void Com_Printf(const char *fmt, ...) {}
void Com_Error(int code, const char *fmt, ...) { abort(); }
void Z_Free(void *ptr) { ++freed_entities; free(ptr); }
int Key_GetEventGamepadIndex(void) { return event_gamepad; }
int NET_GetLoopbackSlot(netsrc_t sock) { return loopback_slot; }
void NET_SetLoopbackSlot(netsrc_t sock, int slot) { loopback_slot = slot; }
void MSG_WriteByte(sizebuf_t *buf, int value) {}
void MSG_WriteString(sizebuf_t *buf, const char *value)
{
	Q_strlcpy(sent_command, value, sizeof(sent_command));
}
void Netchan_Transmit(netchan_t *channel, int length, byte *data)
{
	sent_slot = loopback_slot;
	++transmitted;
}

static void begin(int players, int pad0, int pad1, int pad2, int pad3)
{
	SS_ResetState();
	pad_ids[0] = pad0; pad_ids[1] = pad1;
	pad_ids[2] = pad2; pad_ids[3] = pad3;
	SS_SetPlayerCount(players);
	SS_BeginLobby();
}

static void test_two_gamepads(void)
{
	begin(2, 100, 200, -1, -1);
	assert(SS_GetSlot(0)->device_index == 2);
	assert(SS_GetSlot(1)->device_index == 3);
	assert(SS_FindLobbySlotForDevice(2) == 0);
	assert(SS_FindLobbySlotForDevice(3) == 1);
	assert(strcmp(SS_GetDeviceLabel(2), SS_GetDeviceLabel(3)) != 0);
	assert(!SS_AreAllSlotsReady());
	assert(SS_SetSlotReady(0, true));
	assert(!SS_AreAllSlotsReady());
	assert(SS_SetSlotReady(1, true));
	assert(SS_AreAllSlotsReady());
	SS_EndLobby();
	assert(!SS_AreAllSlotsReady());
}

static void test_assignment_and_join(void)
{
	begin(2, 100, 200, -1, -1);
	assert(SS_AssignSlotDevice(0, 3));
	assert(SS_GetSlot(0)->device_index == 3);
	assert(SS_GetSlot(1)->device_index == 2);
	assert(SS_SetSlotReady(1, true));
	assert(!SS_IsDeviceSelectable(0, 2));
	assert(!SS_AssignSlotDevice(0, 2));
	assert(SS_SetSlotReady(1, false));
	assert(SS_AssignSlotDevice(0, 0));
	assert(!SS_SetSlotReady(0, true));
	assert(SS_JoinLobbyDevice(3) == 0);
	assert(SS_JoinLobbyDevice(3) == 0);
	assert(!SS_IsDeviceSelectable(-1, 1));
	assert(!SS_AssignSlotDevice(3, 1));
	assert(!SS_AssignSlotDevice(0, 4));
	assert(SS_JoinLobbyDevice(4) == -1);
	assert(SS_JoinLobbyDevice(0) == -1);
	assert(SS_AssignSlotDevice(0, 1));
	assert(SS_JoinLobbyDevice(3) == 0);
	assert(SS_GetSlot(0)->device_index == 3);
}

static void test_hotplug_and_sparse_registry(void)
{
	ss_local_player_t *p2;
	begin(2, 100, 200, -1, -1);
	p2 = SS_GetSlot(1);
	SS_SetSlotReady(0, true);
	SS_SetSlotReady(1, true);
	p2->attack_down = true;
	p2->jump_down = true;
	p2->axis_left_x = 12000;
	pad_ids[1] = -1;
	SS_RefreshDevices();
	assert(p2->device_index == 3);
	assert(!p2->ready && p2->state == SS_SLOT_SETUP);
	assert(!p2->attack_down && !p2->jump_down && !p2->axis_left_x);
	assert(SS_GetSlot(0)->ready);
	assert(!SS_AreAllSlotsReady());
	assert(!SS_SetSlotReady(1, true));
	pad_ids[1] = 201;
	SS_RefreshDevices();
	assert(!p2->ready);
	assert(SS_SetSlotReady(1, true));
	assert(SS_AreAllSlotsReady());
	/* Replacing a connected device without an observed empty frame must
	 * still require the replacement controller to confirm readiness. */
	pad_ids[1] = 202;
	SS_RefreshDevices();
	assert(!p2->ready && !SS_AreAllSlotsReady());
	begin(2, -1, 200, -1, 400);
	assert(SS_GetSlot(0)->device_index == 3);
	assert(SS_GetSlot(1)->device_index == 5);
	assert(!SS_IsDeviceSelectable(0, 2));
	assert(SS_IsDeviceSelectable(0, 5));
}

static void test_insufficient_controllers(void)
{
	begin(4, -1, 200, -1, -1);
	assert(SS_GetSlot(0)->device_index == 1);
	assert(SS_GetSlot(1)->device_index == 3);
	assert(SS_GetSlot(2)->device_index == 0);
	assert(SS_GetSlot(3)->device_index == 0);
	assert(!SS_SetSlotReady(2, true));
	pad_ids[3] = 400;
	SS_RefreshDevices();
	assert(SS_JoinLobbyDevice(5) == 2);
	pad_ids[1] = -1;
	SS_RefreshDevices();
	pad_ids[2] = 300;
	SS_RefreshDevices();
	assert(SS_JoinLobbyDevice(4) == 1);
	assert(SS_FindLobbySlotForDevice(4) == 1);
	assert(SS_FindLobbySlotForDevice(3) == -1);
}

static void test_state_validation_and_reentry(void)
{
	int before;
	begin(2, 100, 200, -1, -1);
	SS_SetSlotReady(0, true);
	SS_SetSlotReady(1, true);
	SS_GetSlot(1)->device_index = SS_GetSlot(0)->device_index;
	assert(!SS_AreAllSlotsReady());
	SS_GetSlot(1)->entities = malloc(sizeof(centity_t));
	before = freed_entities;
	SS_BeginLobby();
	assert(freed_entities == before + 1);
	assert(!SS_GetSlot(1)->entities);
	assert(!SS_GetSlot(0)->ready && !SS_GetSlot(1)->ready);
}

static void test_secondary_gameplay_bindings(void)
{
	ss_local_player_t *p1, *p2;
	int before;
	begin(2, 100, 200, -1, -1);
	p1 = SS_GetSlot(0);
	p2 = SS_GetSlot(1);
	SS_GetState()->session_active = true;
	SS_EndLobby();
	cls.key_dest = key_game;
	event_gamepad = 1;
	keybindings[K_TRIG_RIGHT] = "+attack";
	keybindings[K_TRIG_LEFT] = "+ads";
	keybindings[K_BTN_SOUTH] = "+moveup";
	keybindings[K_BTN_EAST] = "+movedown";
	keybindings[K_BTN_WEST] = "+use";
	assert(SS_HandleGameplayKey(K_TRIG_RIGHT, true));
	assert(SS_HandleGameplayKey(K_TRIG_LEFT, true));
	assert(SS_HandleGameplayKey(K_BTN_SOUTH, true));
	assert(SS_HandleGameplayKey(K_BTN_EAST, true));
	assert(SS_HandleGameplayKey(K_BTN_WEST, true));
	assert(p2->attack_down && p2->ads_down && p2->jump_down &&
		p2->crouch_down && p2->use_down);
	assert(!p1->attack_down && !p1->ads_down && !p1->jump_down &&
		!p1->crouch_down && !p1->use_down);
	assert(SS_HandleGameplayKey(K_TRIG_RIGHT, false));
	assert(SS_HandleGameplayKey(K_TRIG_LEFT, false));
	assert(SS_HandleGameplayKey(K_BTN_SOUTH, false));
	assert(SS_HandleGameplayKey(K_BTN_EAST, false));
	assert(SS_HandleGameplayKey(K_BTN_WEST, false));
	assert(!p2->attack_down && !p2->ads_down && !p2->jump_down &&
		!p2->crouch_down && !p2->use_down);
	/* Remaps and intentional unbinds affect the second pad too. */
	keybindings[K_BTN_SOUTH] = "+attack";
	assert(SS_HandleGameplayKey(K_BTN_SOUTH, true));
	assert(p2->attack_down && !p2->jump_down);
	assert(SS_HandleGameplayKey(K_BTN_SOUTH, false));
	keybindings[K_TRIG_RIGHT] = "";
	assert(SS_HandleGameplayKey(K_TRIG_RIGHT, true));
	assert(!p2->attack_down);
	/* Primary buttons remain on the existing primary command path. */
	event_gamepad = 0;
	assert(!SS_HandleGameplayKey(K_BTN_SOUTH, true));
	assert(!p1->attack_down);
	event_gamepad = 1;
	p2->connection_state = ca_connected;
	keybindings[K_SHOULDER_RIGHT] = "quickgrenade";
	before = transmitted;
	assert(SS_HandleGameplayKey(K_SHOULDER_RIGHT, true));
	assert(transmitted == before + 1 && sent_slot == 1 && loopback_slot == 0);
	assert(!strcmp(sent_command, "quickgrenade"));
	assert(SS_HandleGameplayKey(K_SHOULDER_RIGHT, false));
	assert(transmitted == before + 1);
	keybindings[K_SHOULDER_RIGHT] = "weapnext";
	assert(SS_HandleGameplayKey(K_SHOULDER_RIGHT, true));
	assert(!strcmp(sent_command, "weapnext"));
	keybindings[K_BTN_BACK] = "score";
	assert(SS_HandleGameplayKey(K_BTN_BACK, true));
	assert(p2->scoreboard_down && !p1->scoreboard_down);
	assert(SS_HandleGameplayKey(K_BTN_BACK, false));
	keybindings[K_BTN_BACK] = "inven";
	assert(SS_HandleGameplayKey(K_BTN_BACK, true));
	assert(!strcmp(sent_command, "inven") && !p2->scoreboard_down);
	/* A keyboard assigned to player 2 uses its movement and inventory binds. */
	assert(SS_AssignSlotDevice(1, 1));
	event_gamepad = -1;
	keybindings['w'] = "+forward";
	keybindings['a'] = "+moveleft";
	keybindings[K_TAB] = "inven";
	assert(SS_HandleGameplayKey('w', true));
	assert(SS_HandleGameplayKey('a', true));
	assert(p2->forward_down && p2->moveleft_down && !p1->forward_down);
	assert(SS_HandleGameplayKey('w', false));
	assert(SS_HandleGameplayKey('a', false));
	assert(!p2->forward_down && !p2->moveleft_down);
	assert(SS_HandleGameplayKey(K_TAB, true));
	assert(!strcmp(sent_command, "inven") && !p2->scoreboard_down);
	keybindings['x'] = "custom_alias";
	before = transmitted;
	assert(SS_HandleGameplayKey('x', true));
	assert(transmitted == before);
}

static void test_secondary_motion_and_menu(void)
{
	ss_local_player_t *p1, *p2;
	begin(2, 100, 200, -1, -1);
	p1 = SS_GetSlot(0);
	p2 = SS_GetSlot(1);
	SS_GetState()->session_active = true;
	cls.key_dest = key_game;
	cls.nframetime = 0.1f;
	SS_SetDeviceAxis(3, SS_AXIS_RIGHT_X, 32767);
	SS_SetDeviceAxis(3, SS_AXIS_RIGHT_Y, 32767);
	SS_SetDeviceAxis(3, SS_AXIS_LEFT_Y, -32768);
	p2->attack_down = p2->ads_down = p2->jump_down = p2->use_down = true;
	SS_BuildSlotCmd(p2);
	assert(fabsf(p2->viewangles[YAW] + 8) < 0.001f);
	assert(fabsf(p2->viewangles[PITCH] - 6) < 0.001f);
	assert(p2->cmd.forwardmove == 400 && p2->cmd.upmove == 200);
	assert((p2->cmd.buttons & (BUTTON_ATTACK | BUTTON_ADS | BUTTON_USE)) ==
		(BUTTON_ATTACK | BUTTON_ADS | BUTTON_USE));
	assert(!p1->viewangles[YAW] && !p1->viewangles[PITCH]);
	pad_pitch_speed = -60;
	pad_yaw_speed = 80;
	SS_BuildSlotCmd(p2);
	assert(fabsf(p2->viewangles[YAW] + 12) < 0.001f);
	assert(fabsf(p2->viewangles[PITCH] - 3) < 0.001f);
	SS_SetDeviceAxis(3, SS_AXIS_LEFT_Y, 2000);
	SS_SetDeviceAxis(3, SS_AXIS_RIGHT_X, 2000);
	SS_SetDeviceAxis(3, SS_AXIS_RIGHT_Y, 2000);
	SS_BuildSlotCmd(p2);
	assert(p2->cmd.forwardmove == 0);
	assert(fabsf(p2->viewangles[YAW] + 12) < 0.001f);
	SS_OpenSlotMenu(p2);
	assert(!p2->attack_down && !p2->ads_down && !p2->jump_down && !p2->use_down);
	assert(!p2->axis_right_x && !p2->axis_right_y);
	SS_CloseSlotMenu(p2);
	assert(SS_AssignSlotDevice(1, 1));
	assert(SS_AddDeviceMouseMotion(1, 4, -3));
	assert(fabsf(p2->viewangles[YAW] + 8) < 0.001f);
	assert(fabsf(p2->viewangles[PITCH]) < 0.001f);
	assert(!p1->viewangles[YAW] && !p1->viewangles[PITCH]);
	assert(SS_AddDeviceMouseMotion(1, 0, 1000));
	assert(p2->viewangles[PITCH] == 89);
	SS_OpenSlotMenu(p2);
	assert(SS_AddDeviceMouseMotion(1, 10, -10));
	assert(p2->viewangles[PITCH] == 89 && fabsf(p2->viewangles[YAW] + 8) < 0.001f);
}

static void test_secondary_gamebird_controls(void)
{
	ss_local_player_t *p1, *p2;
	float yaw, pitch;
	int before;
	begin(2, 100, 200, -1, -1);
	p1 = SS_GetSlot(0);
	p2 = SS_GetSlot(1);
	SS_GetState()->session_active = true;
	SS_EndLobby();
	cls.key_dest = key_game;
	cls.nframetime = 0.1f;
	event_gamepad = 1;
	p2->connection_state = ca_connected;
	pad_pitch_speed = 120;
	keybindings[K_DPAD_UP] = "+gb_up";
	keybindings[K_DPAD_DOWN] = "+gb_down";
	keybindings[K_DPAD_LEFT] = "+gb_left";
	keybindings[K_DPAD_RIGHT] = "+gb_right";
	keybindings[K_BTN_WEST] = "+gb_modifier";
	keybindings[K_BTN_NORTH] = "+ads";
	keybindings[K_BTN_EAST] = "+moveup";
	assert(SS_HandleGameplayKey(K_DPAD_UP, true));
	assert(SS_HandleGameplayKey(K_DPAD_LEFT, true));
	SS_BuildSlotCmd(p2);
	assert(p2->cmd.forwardmove > 0 && p2->viewangles[YAW] > 0);
	assert(!p2->viewangles[PITCH] && !p1->gb_up_down && !p1->gb_left_down);
	assert(SS_HandleGameplayKey(K_BTN_NORTH, true));
	SS_BuildSlotCmd(p2);
	assert(!p2->cmd.forwardmove && p2->viewangles[PITCH] < 0);
	pitch = p2->viewangles[PITCH];
	pad_pitch_speed = -120;
	SS_BuildSlotCmd(p2);
	assert(!p2->cmd.forwardmove && p2->viewangles[PITCH] > pitch);
	assert(SS_HandleGameplayKey(K_BTN_NORTH, false));
	SS_BuildSlotCmd(p2);
	assert(p2->cmd.forwardmove > 0);
	assert(SS_HandleGameplayKey(K_DPAD_UP, false));
	assert(SS_HandleGameplayKey(K_DPAD_LEFT, false));
	assert(SS_HandleGameplayKey(K_DPAD_DOWN, true));
	SS_BuildSlotCmd(p2);
	assert(p2->cmd.forwardmove < 0);
	/* Holding a direction before the modifier does not trigger a toggle. */
	assert(SS_HandleGameplayKey(K_BTN_WEST, true));
	SS_BuildSlotCmd(p2);
	assert(!p2->gb_crouched && !p2->cmd.forwardmove);
	assert(SS_HandleGameplayKey(K_DPAD_DOWN, false));
	before = transmitted;
	assert(SS_HandleGameplayKey(K_DPAD_UP, true));
	assert(transmitted == before + 1 && !strcmp(sent_command, "help"));
	assert(sent_slot == 1 && loopback_slot == 0);
	assert(SS_HandleGameplayKey(K_DPAD_UP, true));
	assert(transmitted == before + 1);
	assert(SS_HandleGameplayKey(K_DPAD_UP, false));
	assert(SS_HandleGameplayKey(K_DPAD_UP, true));
	assert(transmitted == before + 2 && !strcmp(sent_command, "help"));
	assert(SS_HandleGameplayKey(K_DPAD_UP, false));
	before = transmitted;
	assert(SS_HandleGameplayKey(K_DPAD_LEFT, true));
	assert(transmitted == before + 1 && !strcmp(sent_command, "weapprev"));
	assert(sent_slot == 1 && loopback_slot == 0);
	assert(SS_HandleGameplayKey(K_DPAD_LEFT, true));
	assert(transmitted == before + 1);
	assert(SS_HandleGameplayKey(K_DPAD_LEFT, false));
	assert(SS_HandleGameplayKey(K_DPAD_RIGHT, true));
	assert(transmitted == before + 2 && !strcmp(sent_command, "weapnext"));
	assert(SS_HandleGameplayKey(K_DPAD_DOWN, true));
	assert(p2->gb_crouched && !p1->gb_crouched);
	assert(SS_HandleGameplayKey(K_DPAD_DOWN, true));
	assert(p2->gb_crouched);
	assert(SS_HandleGameplayKey(K_BTN_NORTH, true));
	yaw = p2->viewangles[YAW];
	pitch = p2->viewangles[PITCH];
	SS_BuildSlotCmd(p2);
	assert(!p2->cmd.forwardmove && p2->cmd.upmove < 0);
	assert(p2->viewangles[YAW] == yaw && p2->viewangles[PITCH] == pitch);
	/* Releasing the modifier restores the held directions in ADS mode. */
	assert(SS_HandleGameplayKey(K_BTN_WEST, false));
	pad_pitch_speed = 120;
	SS_BuildSlotCmd(p2);
	assert(!p2->cmd.forwardmove && p2->viewangles[YAW] < yaw);
	assert(p2->viewangles[PITCH] > pitch);
	pitch = p2->viewangles[PITCH];
	pad_pitch_speed = -120;
	SS_BuildSlotCmd(p2);
	assert(p2->viewangles[PITCH] < pitch);
	SS_OpenSlotMenu(p2);
	assert(!p2->gb_down_down && !p2->gb_right_down && !p2->gb_modifier_down);
	assert(p2->gb_crouched);
	SS_CloseSlotMenu(p2);
	assert(SS_HandleGameplayKey(K_DPAD_DOWN, false));
	assert(SS_HandleGameplayKey(K_DPAD_RIGHT, false));
	SS_BuildSlotCmd(p2);
	assert(p2->gb_crouched && p2->cmd.upmove < 0 && !p2->cmd.forwardmove);
	assert(SS_HandleGameplayKey(K_BTN_EAST, true));
	SS_BuildSlotCmd(p2);
	assert(!p2->gb_crouched && p2->cmd.upmove > 0);
	assert(SS_HandleGameplayKey(K_BTN_EAST, false));
	assert(SS_HandleGameplayKey(K_BTN_WEST, true));
	assert(SS_HandleGameplayKey(K_DPAD_DOWN, true));
	assert(p2->gb_crouched);
	assert(SS_HandleGameplayKey(K_DPAD_DOWN, false));
	assert(SS_HandleGameplayKey(K_DPAD_DOWN, true));
	assert(!p2->gb_crouched);
	assert(SS_HandleGameplayKey(K_DPAD_DOWN, false));
	assert(SS_HandleGameplayKey(K_DPAD_DOWN, true));
	p2->snapshot_valid = true;
	p2->frame.playerstate.pmove.pm_type = PM_DEAD;
	SS_BuildSlotCmd(p2);
	assert(!p2->gb_crouched && !p2->cmd.upmove);
	p2->gb_crouched = true;
	SS_ClearSlotSnapshot(p2);
	assert(!p2->gb_crouched);
	/* Primary input is still handled by the ordinary client command path. */
	event_gamepad = 0;
	assert(!SS_HandleGameplayKey(K_DPAD_UP, true));
	assert(!p1->gb_up_down && !p1->viewangles[YAW] && !p1->viewangles[PITCH]);
}

static void test_secondary_ads_level_and_mouse(void)
{
	ss_local_player_t *p2;
	float pitch;
	begin(2, 100, 200, -1, -1);
	p2 = SS_GetSlot(1);
	SS_GetState()->session_active = true;
	SS_EndLobby();
	cls.key_dest = key_game;
	cls.nframetime = 0.1f;
	auto_level = 1;
	p2->viewangles[PITCH] = 30;
	p2->ads_down = true;
	SS_BuildSlotCmd(p2);
	p2->ads_down = false;
	SS_BuildSlotCmd(p2);
	assert(fabsf(p2->viewangles[PITCH] - 18) < 0.001f);
	SS_BuildSlotCmd(p2);
	assert(fabsf(p2->viewangles[PITCH] - 6) < 0.001f);
	SS_BuildSlotCmd(p2);
	assert(fabsf(p2->viewangles[PITCH]) < 0.001f);
	assert(SS_AssignSlotDevice(1, 1));
	p2->ads_down = true;
	assert(SS_AddDeviceMouseMotion(1, 20, 10));
	assert(fabsf(p2->viewangles[YAW] - 10) < 0.001f);
	assert(fabsf(p2->viewangles[PITCH] - 5) < 0.001f);
	SS_BuildSlotCmd(p2);
	/* Mouse pitch on the release frame cancels the spring before it starts. */
	p2->ads_down = false;
	assert(SS_AddDeviceMouseMotion(1, 0, 3));
	pitch = p2->viewangles[PITCH];
	SS_BuildSlotCmd(p2);
	assert(!p2->gb_autolevel.active && p2->viewangles[PITCH] == pitch);
	p2->ads_down = true; SS_BuildSlotCmd(p2);
	p2->ads_down = false; SS_BuildSlotCmd(p2);
	SS_OpenSlotMenu(p2);
	assert(!p2->gb_autolevel.active);
	auto_level = 0;
}

int main(void)
{
	test_two_gamepads();
	test_assignment_and_join();
	test_hotplug_and_sparse_registry();
	test_insufficient_controllers();
	test_state_validation_and_reentry();
	test_secondary_gameplay_bindings();
	test_secondary_motion_and_menu();
	test_secondary_gamebird_controls();
	test_secondary_ads_level_and_mouse();
	puts("split-screen state: assignment, readiness, hotplug, bindings, motion and player isolation passed");
	return 0;
}
