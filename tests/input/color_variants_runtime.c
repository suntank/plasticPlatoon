/* Opt-in LD_PRELOAD visual QA controller. It drives the real local server and
 * normal userinfo broadcasts; no test commands are added to the shipped game.
 * Bind executable symbols using PP_COLOR_<symbol>=<hex PIE-relative address>.
 * One complete PP_COLOR_CONTROLS line is consumed per SDL_PollEvent call.
 */
#define _GNU_SOURCE
#include <SDL.h>
#include <arpa/inet.h>
#include <dlfcn.h>
#include <link.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#undef EV_NONE
#include "../../src/client/header/client.h"
#include "../../src/client/cl_splitscreen.h"
#define client_state_t server_client_state_t
#include "../../src/server/header/server.h"
#undef client_state_t

static client_state_t *color_cl;
static client_static_t *color_cls;
static server_static_t *color_svs;
static game_export_t **color_ge;
static cvar_t **color_maxclients;
static void (*tokenize)(char *, qboolean);
static void (*set_info)(char *, const char *, const char *);
static ss_local_player_t *(*get_slot)(int);
static cvar_t *(*set_cvar)(const char *, const char *);
static void (*add_text)(const char *);
static int initialized;
static long control_offset;
extern int PP_ColorGameEquip(void *, uintptr_t, const char *);
extern int PP_ColorGameGib(void *, int, int, void *, const char *);

static int find_game(struct dl_phdr_info *info, size_t size, void *data)
{
	const char *name = strrchr(info->dlpi_name, '/');
	(void)size;
	if (!strcmp(name ? name + 1 : info->dlpi_name, "game.so")) {
		*(uintptr_t *)data = info->dlpi_addr;
		return 1;
	}
	return 0;
}

static void *symbol(uintptr_t base, const char *name)
{
	char environment[128], *end;
	const char *value;
	unsigned long long offset;
	snprintf(environment, sizeof(environment), "PP_COLOR_%s", name);
	value = getenv(environment);
	if (!value || !*value) {
		fprintf(stderr, "PP_COLOR_ERROR missing %s\n", environment);
		exit(91);
	}
	offset = strtoull(value, &end, 16);
	if (*end || !offset) {
		fprintf(stderr, "PP_COLOR_ERROR invalid %s\n", environment);
		exit(91);
	}
	return (void *)(base + offset);
}

static int find_main(struct dl_phdr_info *info, size_t size, void *data)
{
	(void)size; (void)data;
	if (info->dlpi_name[0]) return 0;
	color_cl = symbol(info->dlpi_addr, "cl");
	color_cls = symbol(info->dlpi_addr, "cls");
	color_svs = symbol(info->dlpi_addr, "svs");
	color_ge = symbol(info->dlpi_addr, "ge");
	color_maxclients = symbol(info->dlpi_addr, "maxclients");
	tokenize = symbol(info->dlpi_addr, "Cmd_TokenizeString");
	set_info = symbol(info->dlpi_addr, "Info_SetValueForKey");
	get_slot = symbol(info->dlpi_addr, "SS_GetSlot");
	set_cvar = symbol(info->dlpi_addr, "Cvar_Set");
	if (getenv("PP_COLOR_Cbuf_AddText")) add_text = symbol(info->dlpi_addr, "Cbuf_AddText");
	return 1;
}

static void json_string(const char *value)
{
	const unsigned char *p = (const unsigned char *)(value ? value : "");
	fputc('"', stderr);
	for (; *p; ++p) {
		if (*p == '"' || *p == '\\') fputc('\\', stderr);
		if (*p >= 32) fputc(*p, stderr);
		else fprintf(stderr, "\\u%04x", *p);
	}
	fputc('"', stderr);
}

static edict_t *edict(int n)
{
	game_export_t *game = *color_ge;
	return (edict_t *)((byte *)game->edicts + game->edict_size * n);
}

static client_t *local_client(int slot, int *number)
{
	int n;
	if (slot < 0 || slot >= SS_MAX_LOCAL_PLAYERS || !color_svs->initialized ||
		!*color_ge || !*color_maxclients || !color_svs->clients) return NULL;
	for (n = 0; n < (int)(*color_maxclients)->value; ++n) {
		client_t *client = &color_svs->clients[n];
		if (client->state != cs_spawned || client->netchan.remote_address.type != NA_LOOPBACK ||
			client->netchan.remote_address.port != htons(slot + 1)) continue;
		if (number) *number = n;
		return client;
	}
	return NULL;
}

static const char *model_name(int index)
{
	return index > 0 && index < MAX_MODELS ? color_cl->configstrings[CS_MODELS + index] : "";
}

static void state(const char *label)
{
	int i;
	fprintf(stderr, "PP_COLOR_STATE {\"label\":"); json_string(label);
	fprintf(stderr, ",\"connection\":%d,\"clients\":[", color_cls->state);
	for (i = 0; i < SS_MAX_LOCAL_PLAYERS; ++i) {
		int server_number = -1, playernum;
		client_t *server_client = local_client(i, &server_number);
		ss_local_player_t *slot = get_slot(i);
		const frame_t *frame = i && slot ? &slot->frame : &color_cl->frame;
		const clientinfo_t *ci;
		const char *body;
		playernum = i && slot ? slot->playernum : color_cl->playernum;
		ci = playernum >= 0 && playernum < MAX_CLIENTS ? &color_cl->clientinfo[playernum] : &color_cl->baseclientinfo;
		if (i) fputc(',', stderr);
		fprintf(stderr, "{\"slot\":%d,\"spawned\":%s,\"server_client\":%d,\"playernum\":%d,\"weaponcolor\":",
			i, server_client ? "true" : "false", server_number, playernum);
		json_string(ci->weaponcolor);
		fputs(",\"clientinfo\":", stderr); json_string(ci->cinfo);
		body = strchr(ci->cinfo, '\\');
		fputs(",\"body_skin\":", stderr); json_string(body ? body + 1 : "");
		fputs(",\"body_image\":", stderr);
		json_string(ci->skin && color_cl->refresh_prepped ? (const char *)ci->skin : "");
		fputs(",\"slot_skin\":", stderr); json_string(slot ? slot->skin : "");
		fprintf(stderr, ",\"gunindex\":%d,\"gunmodel\":", frame->playerstate.gunindex);
		json_string(model_name(frame->playerstate.gunindex));
		fprintf(stderr, ",\"server_gunindex\":%d,\"linked_modelindex\":%d,\"weapon_slot\":%d,\"server_flags\":%d,\"ads_held\":%s,\"cmd_ads\":%s}",
			server_client && edict(server_number + 1)->client ? edict(server_number + 1)->client->ps.gunindex : -1,
			server_client ? edict(server_number + 1)->s.modelindex2 : -1,
			server_client ? edict(server_number + 1)->s.skinnum >> 8 : -1,
			server_client ? edict(server_number + 1)->s.renderfx : 0,
			slot && slot->ads_down ? "true" : "false",
			i ? slot && (slot->cmd.buttons & BUTTON_ADS) ? "true" : "false" :
			(color_cl->cmd.buttons & BUTTON_ADS) ? "true" : "false");
	}
	fputs("]}\n", stderr); fflush(stderr);
}

static void enemy_state(const char *label)
{
	game_export_t *game = *color_ge;
	int i, first = 1;
	fputs("PP_COLOR_ENEMIES {\"label\":", stderr); json_string(label);
	fputs(",\"entities\":[", stderr);
	if (game && color_svs->initialized) for (i = 1; i < game->num_edicts; ++i) {
		edict_t *ent = edict(i);
		entity_state_t *s = &ent->s;
		if (!ent->inuse || !s->modelindex || s->modelindex == 255) continue;
		if (!first) fputc(',', stderr);
		first = 0;
		fprintf(stderr, "{\"number\":%d,\"flags\":%d,\"skinnum\":%d,\"model\":", i, s->renderfx, s->skinnum);
		json_string(model_name(s->modelindex));
		fputs(",\"attached\":[", stderr); json_string(model_name(s->modelindex2));
		fputc(',', stderr); json_string(model_name(s->modelindex3));
		fputc(',', stderr); json_string(model_name(s->modelindex4));
		fprintf(stderr, "],\"origin\":[%.4f,%.4f,%.4f]}", s->origin[0], s->origin[1], s->origin[2]);
	}
	fputs("]}\n", stderr); fflush(stderr);
}

static void skin(int slot_index, const char *color)
{
	char body[MAX_QPATH];
	int n;
	client_t *client = local_client(slot_index, &n);
	ss_local_player_t *slot = get_slot(slot_index);
	if (!client || !(*color_ge)->ClientUserinfoChanged || !color[0] || strlen(color) > 40 ||
		strspn(color, "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-") != strlen(color)) return;
	snprintf(body, sizeof(body), "soldier/%s", color);
	set_info(client->userinfo, "skin", body);
	(*color_ge)->ClientUserinfoChanged(edict(n + 1), client->userinfo);
	if (slot) {
		snprintf(slot->model, sizeof(slot->model), "soldier");
		snprintf(slot->skin, sizeof(slot->skin), "%s", color);
		set_info(slot->userinfo, "skin", body);
	}
	if (!slot_index) set_cvar("skin", body);
	fprintf(stderr, "PP_COLOR_APPLIED skin %d %s\n", slot_index, color);
	fflush(stderr);
}

static void controls(void)
{
	const char *path = getenv("PP_COLOR_CONTROLS");
	FILE *file;
	char line[MAX_STRING_CHARS], op[32] = {0}, arg[128] = {0};
	int slot, value, consumed = 0, offset = 0;
	if (!path || !(file = fopen(path, "r"))) return;
	fseek(file, control_offset, SEEK_SET);
	if (!fgets(line, sizeof(line), file)) { fclose(file); return; }
	/* An append may race this read; wait for the newline before consuming. */
	if (!strchr(line, '\n')) { fclose(file); return; }
	control_offset = ftell(file);
	fclose(file);
	if (sscanf(line, "%31s %127s", op, arg) < 1) return;
	if (!strcmp(op, "state")) state(arg);
	else if (!strcmp(op, "enemy_state")) enemy_state(arg);
	else if (!strcmp(op, "skin") && sscanf(line, "%*s %d %127s", &slot, arg) == 2) skin(slot, arg);
	else if (!strcmp(op, "ads") && sscanf(line, "%*s %d %d", &slot, &value) == 2 &&
		slot >= 0 && slot < SS_MAX_LOCAL_PLAYERS && (value == 0 || value == 1)) {
		ss_local_player_t *player = get_slot(slot);
		if (player) player->ads_down = value != 0;
		if (!slot) {
			if (add_text) add_text(value ? "+ads\n" : "-ads\n");
			else fputs("PP_COLOR_ERROR primary ads needs PP_COLOR_Cbuf_AddText\n", stderr);
		}
		fprintf(stderr, "PP_COLOR_APPLIED ads %d %d\n", slot, value);
		fflush(stderr);
	}
	else if (!strcmp(op, "equip") && sscanf(line, "%*s %d %n", &slot, &offset) == 1) {
		int n, result = 0;
		uintptr_t game_base = 0;
		client_t *client = local_client(slot, &n);
		line[strcspn(line, "\r\n")] = 0;
		dl_iterate_phdr(find_game, &game_base);
		if (client && offset > 0 && game_base)
			result = PP_ColorGameEquip(edict(n + 1), game_base, line + offset);
		fprintf(stderr, "PP_COLOR_APPLIED equip %d %d %s\n", slot, result, line + offset);
		fflush(stderr);
	}
	else if (!strcmp(op, "gib") && arg[0]) {
		int n, result = -1;
		game_export_t *game = *color_ge;
		client_t *client = local_client(0, &n);
		if (client && game)
			result = PP_ColorGameGib(game->edicts, game->edict_size, game->num_edicts, edict(n + 1), arg);
		fprintf(stderr, "PP_COLOR_APPLIED gib %d %s\n", result, arg);
		fflush(stderr);
	}
	else if (!strcmp(op, "clientcmd") && sscanf(line, "%*s %d %n", &slot, &offset) == 1) {
		int n;
		client_t *client = local_client(slot, &n);
		if (client && offset > 0 && (*color_ge)->ClientCommand) {
			line[strcspn(line, "\r\n")] = 0;
			tokenize(line + offset, false);
			(*color_ge)->ClientCommand(edict(n + 1));
			consumed = 1;
		}
		fprintf(stderr, "PP_COLOR_APPLIED clientcmd %d %d %s\n", slot, consumed, line + offset);
		fflush(stderr);
	}
}

int SDL_PollEvent(SDL_Event *event)
{
	static int (*real_poll)(SDL_Event *);
	if (!real_poll) real_poll = dlsym(RTLD_NEXT, "SDL_PollEvent");
	if (!initialized) {
		dl_iterate_phdr(find_main, NULL);
		if (!color_cl || !color_cls || !color_svs || !color_ge) exit(91);
		initialized = 1;
	}
	controls();
	return real_poll(event);
}
