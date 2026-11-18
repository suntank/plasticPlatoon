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
static float (*model_ads_blend)(int);
static float *primary_recoil;
#ifdef PP_ADS_RECOIL_QA
static refexport_t *ads_ref;
static ss_state_t *ads_split;
static int *ads_muzzle_seq;
static void (*ads_render_frame)(refdef_t *);
static char ads_watch_label[128];
static const char *model_name(int);
static void json_string(const char *);
static void ads_observe_frame(refdef_t *fd)
{
    int slot_index=0;
    if(ads_split&&ads_split->session_active)for(int i=0;i<4;i++)
        if(fd->x==ads_split->viewports[i].x&&fd->y==ads_split->viewports[i].y){slot_index=i;break;}
    ss_local_player_t *slot=get_slot(slot_index);
    if(ads_watch_label[0])for(int i=0;i<fd->num_entities;i++) {
        entity_t *e=&fd->entities[i];const char *name="";
        if(!(e->flags&RF_WEAPONMODEL))continue;
        for(int j=1;j<MAX_MODELS;j++)if(e->model==color_cl->model_draw[j]){name=model_name(j);break;}
        fputs("PP_ADS_RECOIL {\"label\":",stderr);json_string(ads_watch_label);
        fprintf(stderr,",\"slot\":%d,\"time\":%d,\"muzzle_seq\":%d,\"blend\":%.6f,\"recoil\":%.6f,\"model\":",slot_index,color_cls->realtime,
            slot_index?(slot?slot->muzzle_flash_seq:0):(ads_muzzle_seq?*ads_muzzle_seq:0),
            model_ads_blend?model_ads_blend(slot_index):-1,
            ads_split&&ads_split->session_active?(slot?slot->viewmodel_recoil:0):(primary_recoil?*primary_recoil:0));
        json_string(name);
        fprintf(stderr,",\"frame\":%d,\"oldframe\":%d,\"backlerp\":%.6f,\"fov\":[%.5f,%.5f],\"camera\":[%.6f,%.6f,%.6f],\"viewangles\":[%.6f,%.6f,%.6f],\"origin\":[%.6f,%.6f,%.6f],\"angles\":[%.6f,%.6f,%.6f]}\n",
            e->frame,e->oldframe,e->backlerp,fd->fov_x,fd->fov_y,fd->vieworg[0],fd->vieworg[1],fd->vieworg[2],
            fd->viewangles[0],fd->viewangles[1],fd->viewangles[2],e->origin[0],e->origin[1],e->origin[2],
            e->angles[0],e->angles[1],e->angles[2]);
    }
    if(ads_watch_label[0])fflush(stderr);
    ads_render_frame(fd);
}
#endif
#ifdef PP_SOLDIER_QA
static struct model_s *(*body_register_model)(const char *);
static refexport_t *body_ref;
static void (*body_render_frame)(refdef_t *);
static void body_diagnostic_frame(refdef_t *fd)
{
	/* Private A/B lighting: expose anatomy and skin detail consistently.
	 * The shipped renderer and ordinary gameplay lighting are untouched. */
	for (int i=0;i<fd->num_entities;i++) fd->entities[i].flags |= RF_FULLBRIGHT;
	body_render_frame(fd);
}
extern int PP_SoldierBodyPose(void *, int, int, uintptr_t, const char *, int);
extern int PP_SoldierLegacyCook(void *, uintptr_t);
#endif
static int initialized;
static long control_offset;
/* Test-only screenshot trigger at an observed network weapon frame. */
static int capture_slot = -1, capture_frame;
static char capture_label[128], capture_model[MAX_QPATH];
static int recoil_capture_slot = -1;
static float recoil_capture_threshold;
static char recoil_capture_label[128];
extern int PP_ColorGameEquip(void *, uintptr_t, const char *);
extern int PP_ColorGameAmmoState(void *, uintptr_t, int[7]);
extern int PP_ColorGameHealthState(void *, int[2]);
extern int PP_ColorGameArmorState(void *, uintptr_t, int[3]);
extern int PP_ColorGameGib(void *, int, int, void *, const char *);
#ifdef PP_PROJECTILE_QA
extern int PP_ColorGameProjectileState(void *, int, int, const char *);
extern int PP_ColorGameObserver(void *);
static edict_t *edict(int);
static client_t *local_client(int, int *);
static const char *model_name(int);
static void json_string(const char *);
static char flight_model[128], flight_label[128];
static float flight_x;
static int flight_pause, flight_armed;
static char impact_model[128], impact_label[128];
static int impact_armed, impact_seen;
static vec3_t impact_last;

static void projectile_probe(const char *label)
{
	game_export_t *game = *color_ge;
	if (game) PP_ColorGameProjectileState(game->edicts, game->edict_size, game->num_edicts, label);
}

static void projectile_camera(const float *point, const float *angles)
{
	int n, axis;
	if (!local_client(0, &n)) return;
	edict_t *player = edict(n + 1);
	if (!player->client) return;
	for (axis = 0; axis < 3; ++axis) {
		player->s.origin[axis] = point[axis];
		player->client->ps.pmove.origin[axis] = (short)(point[axis] * 8);
		player->client->ps.viewoffset[axis] = 0;
		player->client->ps.viewangles[axis] = angles[axis];
		color_cl->viewangles[axis] = angles[axis] - SHORT2ANGLE(player->client->ps.pmove.delta_angles[axis]);
		color_cl->predicted_origin[axis] = point[axis];
		color_cl->predicted_angles[axis] = angles[axis];
	}
	player->client->ps.pmove.pm_flags &= ~PMF_TIME_TELEPORT;
	player->client->ps.pmove.pm_time = 0;
	color_cl->frame.playerstate = player->client->ps;
	/* A frozen frame still interpolates viewoffset from oldframe. Keep both
	 * QA camera endpoints equal so a paused observer has its exact eye. */
	color_cl->frames[(color_cl->frame.serverframe - 1) & UPDATE_MASK].playerstate = player->client->ps;
	color_cl->force_refdef = true;
}

static void watch_projectile(void)
{
	game_export_t *game = *color_ge;
	if (!game) return;
	for (int n = 1; flight_armed && n < game->num_edicts; ++n) {
		edict_t *entity = edict(n);
		if (!entity->inuse || !entity->s.modelindex ||
			!strstr(model_name(entity->s.modelindex), flight_model) || entity->s.origin[0] < flight_x) continue;
		if (flight_pause) set_cvar("paused", "1");
		fprintf(stderr, "PP_PROJECTILE_GATE {\"label\":"); json_string(flight_label);
		fprintf(stderr, ",\"number\":%d,\"origin\":[%.5f,%.5f,%.5f],\"paused\":%s}\n",
			n, entity->s.origin[0], entity->s.origin[1], entity->s.origin[2], flight_pause ? "true" : "false");
		projectile_probe(flight_label);
		if (!flight_pause && add_text) add_text("screenshot png\n");
		fflush(stderr);
		flight_armed = 0;
		break;
	}
	if (impact_armed) {
		int present = 0;
		for (int n = 1; n < game->num_edicts; ++n) {
			edict_t *entity = edict(n);
			if (!entity->inuse || !entity->s.modelindex || !strstr(model_name(entity->s.modelindex), impact_model)) continue;
			VectorCopy(entity->s.origin, impact_last);
			present = impact_seen = 1;
		}
		if (impact_seen && !present) {
			fprintf(stderr, "PP_PROJECTILE_IMPACT {\"label\":"); json_string(impact_label);
			fprintf(stderr, ",\"last_origin\":[%.5f,%.5f,%.5f]}\n", impact_last[0],impact_last[1],impact_last[2]);
			projectile_probe(impact_label);
			if (add_text) add_text("wait\nwait\nscreenshot png\n");
			fflush(stderr);
			impact_armed = 0;
		}
	}
}
#endif

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
	if (getenv("PP_COLOR_CL_GetModelADSBlend")) model_ads_blend = symbol(info->dlpi_addr, "CL_GetModelADSBlend");
	if (getenv("PP_COLOR_pp_viewmodel_recoil")) primary_recoil = symbol(info->dlpi_addr, "pp_viewmodel_recoil");
#ifdef PP_ADS_RECOIL_QA
    ads_ref=symbol(info->dlpi_addr,"re");
    ads_split=symbol(info->dlpi_addr,"ss_state");
    ads_muzzle_seq=symbol(info->dlpi_addr,"pp_viewmodel_muzzle_seq");
#endif
#ifdef PP_SOLDIER_QA
	body_register_model = symbol(info->dlpi_addr, "R_RegisterModel");
	body_ref = symbol(info->dlpi_addr, "re");
#endif
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
		fprintf(stderr, ",\"gunframe\":%d,\"server_gunframe\":%d,\"server_gunindex\":%d,\"linked_modelindex\":%d,\"weapon_slot\":%d,\"server_flags\":%d,\"bodyframe\":%d,\"pm_flags\":%d,\"pm_type\":%d,\"ads_held\":%s,\"cmd_ads\":%s,\"model_ads_blend\":%.6f,\"viewmodel_recoil\":%.6f}",
			frame->playerstate.gunframe,
			server_client && edict(server_number + 1)->client ? edict(server_number + 1)->client->ps.gunframe : -1,
			server_client && edict(server_number + 1)->client ? edict(server_number + 1)->client->ps.gunindex : -1,
			server_client ? edict(server_number + 1)->s.modelindex2 : -1,
			server_client ? edict(server_number + 1)->s.skinnum >> 8 : -1,
			server_client ? edict(server_number + 1)->s.renderfx : 0,
			server_client ? edict(server_number + 1)->s.frame : -1,
			server_client && edict(server_number + 1)->client ? edict(server_number + 1)->client->ps.pmove.pm_flags : -1,
			server_client && edict(server_number + 1)->client ? edict(server_number + 1)->client->ps.pmove.pm_type : -1,
			slot && slot->ads_down ? "true" : "false",
			i ? slot && (slot->cmd.buttons & BUTTON_ADS) ? "true" : "false" :
			(color_cl->cmd.buttons & BUTTON_ADS) ? "true" : "false",
			model_ads_blend ? model_ads_blend(i) : -1.0f,
			i ? (slot ? slot->viewmodel_recoil : -1.0f) : (primary_recoil ? *primary_recoil : -1.0f));
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
		fprintf(stderr, "{\"number\":%d,\"flags\":%d,\"effects\":%u,\"svflags\":%d,\"solid\":%d,\"skinnum\":%d,\"model\":",
			i, s->renderfx, s->effects, ent->svflags, ent->solid, s->skinnum);
		json_string(model_name(s->modelindex));
		fputs(",\"attached\":[", stderr); json_string(model_name(s->modelindex2));
		fputc(',', stderr); json_string(model_name(s->modelindex3));
		fputc(',', stderr); json_string(model_name(s->modelindex4));
		fprintf(stderr, "],\"origin\":[%.4f,%.4f,%.4f]}", s->origin[0], s->origin[1], s->origin[2]);
	}
	fputs("]}\n", stderr); fflush(stderr);
}

#ifdef PP_DROPSHIP_QA
extern int PP_ColorGameDropshipState(void *, int, int, const char *);
extern int PP_ColorGameDropshipUse(void *, int, int, void *, const char *);

static void dropship_render(const char *label)
{
    int first = 1;
    fputs("PP_DROPSHIP_RENDER {\"label\":", stderr); json_string(label);
    fprintf(stderr, ",\"client_time_ms\":%d,\"entities\":[", color_cl->time);
    for (int i = 0; i < color_cl->refdef.num_entities; ++i) {
        entity_t *e = &color_cl->refdef.entities[i];
        const char *name = "";
        for (int j = 1; j < MAX_MODELS; ++j) {
            if (e->model == color_cl->model_draw[j]) { name = model_name(j); break; }
        }
        if (!strstr(name, "models/vehicles/platoon_dropship/")) continue;
        if (!first) fputc(',', stderr);
        first = 0;
        fputs("{\"model\":", stderr); json_string(name);
        fprintf(stderr, ",\"origin\":[%.5f,%.5f,%.5f],\"angles\":[%.5f,%.5f,%.5f],\"frame\":%d,\"oldframe\":%d,\"backlerp\":%.5f,\"flags\":%d}",
            e->origin[0], e->origin[1], e->origin[2], e->angles[0], e->angles[1], e->angles[2],
            e->frame, e->oldframe, e->backlerp, e->flags);
    }
    fputs("]}\n", stderr); fflush(stderr);
}
#endif

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

#ifdef PP_BOSS_QA
extern int PP_BossQA(void *,int,int,void *,uintptr_t,const char *,const char *);
static void boss_render(const char *label)
{
    int first=1;
    fprintf(stderr,"PP_BOSS_RENDER {\"label\":\"%s\",\"entities\":[",label);
    for(int i=0;i<color_cl->refdef.num_entities;i++) {
        entity_t *e=&color_cl->refdef.entities[i];const char *name="";
        for(int j=1;j<MAX_MODELS;j++)if(e->model==color_cl->model_draw[j]){name=model_name(j);break;}
        if(!strstr(name,"models/monsters/plastic_boss/"))continue;
        if(!first)fputc(',',stderr);first=0;
        fputs("{\"model\":",stderr);json_string(name);fputs(",\"skin\":",stderr);json_string(e->skin?(const char *)e->skin:"");
        fprintf(stderr,",\"frame\":%d,\"origin\":[%.4f,%.4f,%.4f],\"angles\":[%.4f,%.4f,%.4f]}",
            e->frame,e->origin[0],e->origin[1],e->origin[2],e->angles[0],e->angles[1],e->angles[2]);
    }
    fputs("]}\n",stderr);fflush(stderr);
}
#endif

static void controls(void)
{
	const char *path = getenv("PP_COLOR_CONTROLS");
	FILE *file;
	char line[MAX_STRING_CHARS], op[32] = {0}, arg[128] = {0};
	int slot, value, consumed = 0, offset = 0;
	float threshold;
	if (!path || !(file = fopen(path, "r"))) return;
	fseek(file, control_offset, SEEK_SET);
	if (!fgets(line, sizeof(line), file)) { fclose(file); return; }
	/* An append may race this read; wait for the newline before consuming. */
	if (!strchr(line, '\n')) { fclose(file); return; }
	control_offset = ftell(file);
	fclose(file);
	if (sscanf(line, "%31s %127s", op, arg) < 1) return;
	if (!strcmp(op, "state")) state(arg);
#ifdef PP_ADS_RECOIL_QA
    else if(!strcmp(op,"ads_watch")) {
        snprintf(ads_watch_label,sizeof(ads_watch_label),"%s",!strcmp(arg,"off")?"":arg);
    }
#endif
#ifdef PP_BOSS_QA
    else if(!strcmp(op,"boss")||!strcmp(op,"boss_state")) {
        game_export_t *game=*color_ge;int n;uintptr_t game_base=0;dl_iterate_phdr(find_game,&game_base);
        if(game&&local_client(0,&n)&&game_base)
            PP_BossQA(game->edicts,game->edict_size,game->num_edicts,edict(n+1),game_base,
                      !strcmp(op,"boss_state")?"state":arg,arg);
    }
    else if(!strcmp(op,"boss_render"))boss_render(arg);
#endif
#ifdef PP_SOLDIER_QA
	else if (!strcmp(op, "body_pose") && sscanf(line, "%*s %127s %d", arg, &value)==2) {
		uintptr_t game_base=0; dl_iterate_phdr(find_game,&game_base);
		game_export_t *game=*color_ge;
		if (game && game_base) PP_SoldierBodyPose(game->edicts,game->edict_size,game->num_edicts,game_base,arg,value);
	}
	else if (!strcmp(op, "legacy_cook")) {
		uintptr_t game_base=0;int n;dl_iterate_phdr(find_game,&game_base);
		if (local_client(0,&n) && game_base) PP_SoldierLegacyCook(edict(n+1),game_base);
	}
	else if (!strcmp(op, "body_render")) {
		const char *paths[]={"models/monsters/soldier/tris.md2","models/monsters/soldier/tall/tris.md2",
			"players/soldier/tris.md2","players/soldier/tris_pistol.md2",
			"models/experimental/soldier/enemy.md2","models/experimental/soldier/enemy_tall.md2",
			"models/experimental/soldier/player.md2","models/experimental/soldier/player_pistol.md2"};
		struct model_s *models[8];for(int k=0;k<8;k++) models[k]=body_register_model(paths[k]);
		fputs("PP_BODY_RENDER {\"label\":",stderr);json_string(arg);fputs(",\"bodies\":[",stderr);
		int first=1;
		for(int i=0;i<color_cl->refdef.num_entities;i++) for(int k=0;k<8;k++) {
			entity_t *e=&color_cl->refdef.entities[i];if(e->model!=models[k]) continue;
			if(!first)fputc(',',stderr);first=0;
			fputs("{\"model\":",stderr);json_string(paths[k]);
			fprintf(stderr,",\"frame\":%d,\"origin\":[%.3f,%.3f,%.3f]}",e->frame,e->origin[0],e->origin[1],e->origin[2]);
		}
		fputs("]}\n",stderr);fflush(stderr);
	}
#endif
#ifdef PP_DROPSHIP_QA
    else if (!strcmp(op, "dropship_state")) {
        game_export_t *game = *color_ge;
        if (game) PP_ColorGameDropshipState(game->edicts, game->edict_size, game->num_edicts, arg);
    }
    else if (!strcmp(op, "dropship_use")) {
        game_export_t *game = *color_ge;
        int n, invoked = -1;
        if (game && local_client(0, &n))
            invoked = PP_ColorGameDropshipUse(game->edicts, game->edict_size, game->num_edicts, edict(n + 1), arg);
        fprintf(stderr, "PP_DROPSHIP_USE %s %d\n", arg, invoked); fflush(stderr);
    }
    else if (!strcmp(op, "dropship_render")) dropship_render(arg);
    else if (!strcmp(op, "dropship_pause")) {
        cvar_t *paused = set_cvar("paused", atoi(arg) ? "1" : "0");
        fprintf(stderr, "PP_DROPSHIP_PAUSE %s maxclients=%.0f paused=%.0f\n", arg,
            (*color_maxclients)->value, paused ? paused->value : -1.f); fflush(stderr);
    }
#endif
#ifdef PP_PROJECTILE_QA
	else if (!strcmp(op, "projectiles")) projectile_probe(arg);
	else if (!strcmp(op, "observer") && sscanf(line, "%*s %d", &slot) == 1) {
		int n;
		if (local_client(slot, &n)) PP_ColorGameObserver(edict(n + 1));
	}
	else if (!strcmp(op, "captureflight") &&
		sscanf(line, "%*s %127s %f %d %127s", flight_model, &flight_x, &flight_pause, flight_label) == 4) {
		flight_armed = 1;
	}
	else if (!strcmp(op, "captureimpact") && sscanf(line, "%*s %127s %127s", impact_model, impact_label) == 2) {
		impact_armed = 1;
		impact_seen = 0;
	}
	else if (!strcmp(op, "camera_pose")) {
		float point[3], angles[3] = {0};
		if (sscanf(line, "%*s %f %f %f %f %f", &point[0], &point[1], &point[2], &angles[0], &angles[1]) == 5)
			projectile_camera(point, angles);
	}
#endif
	else if (!strcmp(op, "camera_state")) {
		fprintf(stderr, "PP_QA_CAMERA {\"label\":"); json_string(arg);
		fprintf(stderr, ",\"client_time_ms\":%d,\"input\":[%.4f,%.4f,%.4f],\"view\":[%.4f,%.4f,%.4f],\"origin\":[%.4f,%.4f,%.4f],\"snapshot\":[%.4f,%.4f,%.4f]}\n",
			color_cl->time,
			color_cl->viewangles[0],color_cl->viewangles[1],color_cl->viewangles[2],
			color_cl->refdef.viewangles[0],color_cl->refdef.viewangles[1],color_cl->refdef.viewangles[2],
			color_cl->refdef.vieworg[0],color_cl->refdef.vieworg[1],color_cl->refdef.vieworg[2],
			color_cl->frame.playerstate.viewangles[0],color_cl->frame.playerstate.viewangles[1],color_cl->frame.playerstate.viewangles[2]);
		fflush(stderr);
	}
	else if (!strcmp(op, "clear_teleport") && sscanf(line, "%*s %d", &slot) == 1) {
		/* The normal benchmark teleport sets a short freeze. Noclip returns
		 * before Pmove expires that timer, permanently flattening camera
		 * pitch. Only the isolated QA camera uses this opt-in repair. */
		int n;
		if (local_client(slot, &n) && edict(n + 1)->client) {
			edict(n + 1)->client->ps.pmove.pm_time = 0;
			edict(n + 1)->client->ps.pmove.pm_flags &= ~PMF_TIME_TELEPORT;
		}
	}
	else if (!strcmp(op, "console") && add_text) {
		/* File-driven commands let screenshot runners share the same native
		 * command path without depending on another process's UDP namespace. */
		const char *text = strchr(line, ' ');
		if (text) add_text(text + 1);
	}
	else if (!strcmp(op, "captureframe") && add_text &&
		sscanf(line, "%*s %d %d %63s %127s", &slot, &value, capture_model, arg) == 4 &&
		slot >= 0 && slot < SS_MAX_LOCAL_PLAYERS && value >= 0 && value < 40) {
		capture_slot = slot;
		capture_frame = value;
		snprintf(capture_label, sizeof(capture_label), "%s", arg);
	}
	else if (!strcmp(op, "capturerecoil") && add_text &&
		sscanf(line, "%*s %d %f %127s", &slot, &threshold, arg) == 3 &&
		slot >= 0 && slot < SS_MAX_LOCAL_PLAYERS && threshold > 0 && threshold <= 1) {
		recoil_capture_slot = slot;
		recoil_capture_threshold = threshold;
		snprintf(recoil_capture_label, sizeof(recoil_capture_label), "%s", arg);
	}
	else if (!strcmp(op, "enemy_state")) enemy_state(arg);
	else if (!strcmp(op, "ammo_state") && arg[0]) {
		static const char *const names[]={"Shells", "Bullets", "Grenades", "GL Ammo",
			"Rockets", "Napalm", "Sniper Rounds"};
		int n, counts[7];
		uintptr_t game_base=0;
		client_t *client=local_client(0,&n);
		dl_iterate_phdr(find_game,&game_base);
		if (client && game_base && PP_ColorGameAmmoState(edict(n+1),game_base,counts)) {
			fputs("PP_AMMO_INVENTORY {\"label\":",stderr); json_string(arg);
			fputs(",\"slot\":0,\"counts\":{",stderr);
			for (int i=0; i<7; ++i) {
				if (i) fputc(',',stderr);
				json_string(names[i]); fprintf(stderr,":%d",counts[i]);
			}
			fputs("}}\n",stderr);
		} else fprintf(stderr,"PP_COLOR_ERROR ammo_state unavailable %s\n",arg);
		fflush(stderr);
	}
	else if (!strcmp(op, "health_state") && arg[0]) {
		int n, values[2];
		if (local_client(0, &n) && PP_ColorGameHealthState(edict(n + 1), values)) {
			fputs("PP_HEALTH_STATE {\"label\":", stderr); json_string(arg);
			fprintf(stderr, ",\"health\":%d,\"max_health\":%d}\n", values[0], values[1]);
		} else fprintf(stderr, "PP_COLOR_ERROR health_state unavailable %s\n", arg);
		fflush(stderr);
	}
	else if (!strcmp(op, "armor_state") && arg[0]) {
		int n, values[3];
		uintptr_t game_base = 0;
		dl_iterate_phdr(find_game, &game_base);
		if (local_client(0, &n) && game_base && PP_ColorGameArmorState(edict(n + 1), game_base, values)) {
			fputs("PP_ARMOR_STATE {\"label\":", stderr); json_string(arg);
			fprintf(stderr, ",\"counts\":{\"jacket\":%d,\"combat\":%d,\"body\":%d}}\n", values[0], values[1], values[2]);
		} else fprintf(stderr, "PP_COLOR_ERROR armor_state unavailable %s\n", arg);
		fflush(stderr);
	}
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
	else if (!strcmp(op, "attack") && sscanf(line, "%*s %d %d", &slot, &value) == 2 &&
		slot >= 0 && slot < SS_MAX_LOCAL_PLAYERS && (value == 0 || value == 1)) {
		ss_local_player_t *player = get_slot(slot);
		if (player) player->attack_down = value != 0;
		if (!slot && add_text) add_text(value ? "+attack\n" : "-attack\n");
		fprintf(stderr, "PP_COLOR_APPLIED attack %d %d\n", slot, value);
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

static void capture_weapon_frame(void)
{
	ss_local_player_t *slot;
	const frame_t *frame;
	if (capture_slot < 0 || color_cls->state != ca_active || !add_text) return;
	slot = get_slot(capture_slot);
	frame = capture_slot && slot ? &slot->frame : &color_cl->frame;
	if (!strstr(model_name(frame->playerstate.gunindex), capture_model) ||
		frame->playerstate.gunframe != capture_frame) return;
	fprintf(stderr, "PP_COLOR_FRAME_CAPTURE %s %d %d\n",
		capture_label, capture_slot, frame->playerstate.gunframe);
	fflush(stderr);
	state(capture_label);
	add_text("screenshot png\n");
	capture_slot = -1;
}

static void capture_weapon_recoil(void)
{
	ss_local_player_t *slot;
	float amount;
	if (recoil_capture_slot < 0 || color_cls->state != ca_active || !add_text) return;
	slot = get_slot(recoil_capture_slot);
	amount = recoil_capture_slot ? (slot ? slot->viewmodel_recoil : -1.0f) :
		(primary_recoil ? *primary_recoil : -1.0f);
	if (amount < recoil_capture_threshold) return;
	fprintf(stderr, "PP_COLOR_RECOIL_CAPTURE %s %d %.6f\n",
		recoil_capture_label, recoil_capture_slot, amount);
	fflush(stderr);
	state(recoil_capture_label);
	add_text("screenshot png\n");
	recoil_capture_slot = -1;
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
#ifdef PP_SOLDIER_QA
	if (body_ref && body_ref->RenderFrame && body_ref->RenderFrame != body_diagnostic_frame) {
		body_render_frame = body_ref->RenderFrame;
		body_ref->RenderFrame = body_diagnostic_frame;
	}
#endif
#ifdef PP_ADS_RECOIL_QA
    if(ads_ref&&ads_ref->RenderFrame&&ads_ref->RenderFrame!=ads_observe_frame) {
        ads_render_frame=ads_ref->RenderFrame;ads_ref->RenderFrame=ads_observe_frame;
    }
#endif
	controls();
#ifdef PP_PROJECTILE_QA
	watch_projectile();
#endif
	capture_weapon_frame();
	capture_weapon_recoil();
	return real_poll(event);
}
