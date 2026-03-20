#ifndef CL_SPLITSCREEN_H
#define CL_SPLITSCREEN_H

#include "header/client.h"

#define SS_MAX_LOCAL_PLAYERS 4
#define SS_MAX_INPUT_DEVICES (SS_MAX_LOCAL_PLAYERS + 2)

typedef enum
{
	SS_TRANSPORT_INTERNET = 0,
	SS_TRANSPORT_LOCAL,
	SS_TRANSPORT_SPLITSCREEN
} ss_transport_t;

typedef enum
{
	SS_AXIS_LEFT_X = 0,
	SS_AXIS_LEFT_Y,
	SS_AXIS_RIGHT_X,
	SS_AXIS_RIGHT_Y
} ss_axis_t;

typedef enum
{
	SS_SLOT_EMPTY = 0,
	SS_SLOT_SETUP,
	SS_SLOT_READY,
	SS_SLOT_CONNECTING,
	SS_SLOT_ACTIVE,
	SS_SLOT_DROPPED
} ss_slot_state_t;

typedef struct
{
	int x;
	int y;
	int w;
	int h;
	qboolean active;
	qboolean black_fill;
} ss_viewport_t;

typedef struct
{
	int local_index;
	ss_slot_state_t state;
	qboolean active;
	qboolean ready;
	qboolean menu_open;
	qboolean exit_hold_active;
	int loopback_slot;
	connstate_t connection_state;
	int model_index;
	int skin_index;
	int device_index;
	int menu_cursor;
	int connect_time;
	unsigned int exit_hold_start;
	netchan_t netchan;
	usercmd_t cmd;
	usercmd_t cmds[CMD_BACKUP];
	frame_t frame;
	frame_t frames[UPDATE_BACKUP];
	entity_state_t parse_entities[MAX_PARSE_ENTITIES];
	int parse_entities_num;
	centity_t *entities;
	int entity_count;
	int servercount;
	int playernum;
	int inventory[MAX_ITEMS];
	char layout[1024];
	qboolean snapshot_valid;
	vec3_t viewangles;
	int axis_left_x;
	int axis_left_y;
	int axis_right_x;
	int axis_right_y;
	qboolean attack_down;
	qboolean previous_attack_down;
	qboolean scoreboard_down;
	qboolean use_down;
	qboolean ads_down;
	qboolean jump_down;
	qboolean crouch_down;
	qboolean ads_active;
	int last_gunindex;
	int muzzle_flash_seq;
	int last_muzzle_flash_seq;
	float viewmodel_recoil;
	float viewmodel_raise;
	float last_attack_time;
	float ads_kick_offset;
	vec3_t viewmodel_origin;
	vec3_t viewmodel_angles;
	qboolean viewmodel_valid;
	char userinfo[MAX_INFO_STRING];
	char model[MAX_QPATH];
	char skin[MAX_QPATH];
} ss_local_player_t;

typedef struct
{
	char startmap[MAX_QPATH];
	char spot[MAX_QPATH];
	char hostname[80];
	float maxclients;
	float timelimit;
	float fraglimit;
	float capturelimit;
	int deathmatch;
	int coop;
	qboolean use_spot;
	qboolean has_capturelimit;
	qboolean pending;
} ss_match_config_t;

typedef struct
{
	qboolean enabled;
	qboolean lobby_active;
	qboolean session_active;
	ss_transport_t transport;
	int requested_players;
	int device_count;
	char device_labels[SS_MAX_INPUT_DEVICES][32];
	ss_viewport_t viewports[SS_MAX_LOCAL_PLAYERS];
	ss_local_player_t slots[SS_MAX_LOCAL_PLAYERS];
	ss_match_config_t match;
	int last_local_client_frame;
} ss_state_t;

void SS_ResetState(void);
void SS_SetTransport(ss_transport_t transport);
ss_transport_t SS_GetTransport(void);
void SS_SetPlayerCount(int player_count);
int SS_GetPlayerCount(void);
qboolean SS_IsSplitScreenSelected(void);
qboolean SS_IsLobbyActive(void);

void SS_SetDetectedGamepadCount(int gamepad_count);
int SS_GetDeviceCount(void);
const char *SS_GetDeviceLabel(int device_index);
void SS_SetDeviceLabel(int device_index, const char *label);

void SS_BeginLobby(void);
void SS_EndLobby(void);
qboolean SS_AreAllSlotsReady(void);
qboolean SS_IsDeviceSelectable(int slot_index, int device_index);
void SS_CalcViewports(int player_count, int screen_w, int screen_h,
	ss_viewport_t out_rects[SS_MAX_LOCAL_PLAYERS]);
void SS_UpdateViewports(int screen_w, int screen_h);

ss_state_t *SS_GetState(void);
ss_local_player_t *SS_GetSlot(int slot_index);
void SS_AssignSlotModelSkin(int slot_index, int model_index, int skin_index,
	const char *model_name, const char *skin_name);
qboolean SS_AssignSlotDevice(int slot_index, int device_index);
void SS_SetPendingMatch(const ss_match_config_t *config);
const ss_match_config_t *SS_GetPendingMatch(void);
qboolean SS_HasPendingMatch(void);
void SS_ClearPendingMatch(void);
void SS_ApplyPrimaryProfile(void);
void SS_BeginSession(void);
void SS_EndSession(void);
qboolean SS_IsSessionActive(void);
qboolean SS_IsMenuInputActiveForDevice(int device_index);
qboolean SS_ShouldAcceptSessionKey(int device_index, int key);
qboolean SS_HandleSessionKey(int key, qboolean down);
qboolean SS_ShouldCaptureGameplayDevice(int device_index);
qboolean SS_HandleGameplayKey(int key, qboolean down);
void SS_SetDeviceAxis(int device_index, ss_axis_t axis, int value);
qboolean SS_RenderViews(float stereo_separation);
void SS_DrawGameplayHUD(void);
void SS_DrawSessionOverlay(void);
void SS_RunLocalClients(void);

#endif
