/* Complete-display-frame diagnostics for single player and local split screen.
 * GPL-2.0-or-later. Durations other than optional gpu_ms are CPU wall times.
 * Disabled by default; no renderer synchronization is introduced. */
#include "header/client.h"
#include "header/performance.h"
#include "cl_splitscreen.h"
#define client_state_t server_client_state_t
#include "../server/header/server.h"
#undef client_state_t
#include <ctype.h>
#include <inttypes.h>
#ifdef __linux__
#include <unistd.h>
#endif

#define PERF_VIEWS 8 /* four split views, or two stereo eyes */
static const char *perf_metrics[] = {
	"cpu_ms", "visibility_ms", "model_ms", "draws", "world_triangles",
	"model_triangles", "static_vertex_bytes", "static_index_bytes",
	"dynamic_vertex_bytes", "dynamic_index_bytes", "client_vertex_bytes",
	"client_index_bytes", "pose_vertices", "topology_builds", "pvs_builds",
	"pvs_hits", "lightmap_bytes", "pose_cache_hits"
};
#define PERF_METRICS (sizeof(perf_metrics) / sizeof(perf_metrics[0]))

typedef struct {
	int slot, width, height, entities, particles, lights, supported;
	float origin[3], angles[3];
	long long begin, usec;
	uint64_t serial, completed_serial, gpu_serial;
	double values[PERF_METRICS], gpu_ms;
	int gpu_supported;
} perf_view_t;

static cvar_t *perf_frames, *perf_quit, *perf_screenshot;
static FILE *perf_csv, *perf_views, *perf_meta;
static perf_view_t perf_view[PERF_VIEWS];
static int perf_count, perf_view_count, perf_depth, perf_display_active;
static int perf_initialized;
static long long perf_begin, perf_last_end, perf_prepare_begin, perf_prepare;
static long long perf_present_begin, perf_present, perf_server, perf_simulation;
static long long perf_snapshot, perf_client;
static long perf_rss = -1;
typedef struct { int pending, servercount; float origin[3], angles[3]; } bench_pose_t;
static bench_pose_t bench_pose[4];
static char bench_map[MAX_QPATH];
#ifndef PP_PERF_BASELINE
static cl_effect_stats_t perf_effect_previous;
#endif

static const char *perf_effect_names = ",particles_created,particle_updates,particles_expired,shared_preparations,entity_effect_evaluations,entity_effect_reuses,temp_events_parsed,sprite_updates,active_particles,prepared_particles";

/* These opt-in console commands exercise the real local-client architecture.
 * They do not replace simulation, networking or interpolation with test paths. */
static void
CL_BenchLocal_f(void)
{
	int players, i;
	char *end;
	long requested_players = strtol(Cmd_Argv(1), &end, 10);
	const char *map = Cmd_Argv(2);
	if (Cmd_Argc() != 3 || !Cmd_Argv(1)[0] || *end || requested_players < 1 || requested_players > 4) {
		Com_Printf("Usage: cl_bench_local <1..4> <map> (from a disconnected client)\n");
		return;
	}
	players = (int)requested_players;
	if (Com_ServerState() || cls.state > ca_disconnected) {
		Com_Printf("Disconnect before starting an isolated benchmark session.\n");
		return;
	}
	if (!map[0] || strlen(map) >= MAX_QPATH) return;
	for (i = 0; map[i]; ++i) {
		if (!isalnum((unsigned char)map[i]) && map[i] != '_' && map[i] != '-' && map[i] != '/') return;
	}
	memset(bench_pose, 0, sizeof(bench_pose));
	Q_strlcpy(bench_map, map, sizeof(bench_map));
	Cvar_SetValue("maxclients", players > 1 ? players : 1);
	Cvar_SetValue("coop", players > 1);
	Cvar_SetValue("deathmatch", 0);
	Cvar_SetValue("singleplayer", players == 1);
	if (players > 1) {
		SS_SetTransport(SS_TRANSPORT_SPLITSCREEN);
		SS_SetPlayerCount(players);
		SS_BeginLobby();
		for (i = 0; i < players; ++i) {
			SS_AssignSlotModelSkin(i, 0, 0, "male", "grunt");
			SS_GetSlot(i)->ready = true;
		}
		SS_EndLobby();
		SS_ApplyPrimaryProfile();
		SS_BeginSession();
	}
	M_ForceMenuOff();
	Cbuf_AddText(va("map %s\n", map));
}

static void
CL_BenchPose_f(void)
{
	int slot, i;
	char *end;
	long parsed_slot = strtol(Cmd_Argv(1), &end, 10);
	float values[5];
	if (Cmd_Argc() != 7 || !Cmd_Argv(1)[0] || *end || parsed_slot < 0 || parsed_slot >= 4) {
		Com_Printf("Usage: cl_bench_pose <slot 0..3> <x> <y> <z> <pitch> <yaw>; requires cheats 1\n");
		return;
	}
	slot = (int)parsed_slot;
	for (i = 0; i < 5; ++i) {
		double value = strtod(Cmd_Argv(i + 2), &end);
		if (!Cmd_Argv(i + 2)[0] || *end || !isfinite(value) || fabs(value) > 32767) {
			Com_Printf("Invalid benchmark coordinate or angle.\n");
			return;
		}
		values[i] = (float)value;
	}
	if (!Cvar_VariableValue("cheats")) {
		Com_Printf("cl_bench_pose requires cheats 1 on the local server.\n");
		return;
	}
	for (i = 0; i < 3; ++i) bench_pose[slot].origin[i] = values[i];
	bench_pose[slot].angles[0] = values[3];
	bench_pose[slot].angles[1] = values[4];
	bench_pose[slot].angles[2] = 0;
	bench_pose[slot].pending = 1;
	bench_pose[slot].servercount = cls.state == ca_active ? cl.servercount : 0;
}

static void
CL_BenchApplyPoses(void)
{
	int slot, n, axis;
	if (!svs.initialized || !ge || !ge->ClientCommand || !cl.frame.valid) return;
	for (slot = 0; slot < 4; ++slot) {
		if (!bench_pose[slot].pending) continue;
		if ((bench_pose[slot].servercount && bench_pose[slot].servercount != cl.servercount) ||
			(!bench_pose[slot].servercount && bench_map[0] &&
			strcmp(cl.configstrings[CS_MODELS + 1], va("maps/%s.bsp", bench_map)))) {
			bench_pose[slot].pending = 0;
			continue;
		}
		if (slot && (!SS_IsSessionActive() || !SS_GetSlot(slot) || !SS_GetSlot(slot)->snapshot_valid)) continue;
		for (n = 0; n < (int)maxclients->value; ++n) {
			client_t *client = &svs.clients[n];
			if (client->state != cs_spawned || client->netchan.remote_address.type != NA_LOOPBACK ||
				client->netchan.remote_address.port != (unsigned short)BigShort(slot + 1)) continue;
			Cmd_TokenizeString(va("teleport %.6f %.6f %.6f", bench_pose[slot].origin[0],
				bench_pose[slot].origin[1], bench_pose[slot].origin[2]), false);
			ge->ClientCommand(EDICT_NUM(n + 1));
			for (axis = 0; axis < 3; ++axis) {
				float angle = bench_pose[slot].angles[axis] - SHORT2ANGLE(EDICT_NUM(n + 1)->client->ps.pmove.delta_angles[axis]);
				if (!slot) cl.viewangles[axis] = angle;
				if (SS_IsSessionActive()) SS_GetSlot(slot)->viewangles[axis] = angle;
			}
			bench_pose[slot].pending = 0;
			break;
		}
	}
}

int CL_PerfEnabled(void) { return perf_csv != NULL; }
void CL_PerfAddServer(long long usec) { if (perf_csv) perf_server += usec; }
void CL_PerfAddSimulation(long long usec) { if (perf_csv) perf_simulation += usec; }
void CL_PerfAddSnapshot(long long usec) { if (perf_csv) perf_snapshot += usec; }
void CL_PerfAddClient(long long usec) { if (perf_csv) perf_client += usec; }

static void
CL_PerfStop_f(void)
{
	if (perf_csv) fclose(perf_csv);
	if (perf_views) fclose(perf_views);
	if (perf_meta) fclose(perf_meta);
	if (perf_csv) Com_Printf("Performance capture stopped: %d complete frames.\n", perf_count);
	perf_csv = perf_views = perf_meta = NULL;
	perf_display_active = 0;
}

static void
CL_PerfStart_f(void)
{
	char paths[3][MAX_OSPATH], label[64];
	const char *suffixes[] = {"frames.csv", "views.csv", "settings.txt"};
	FILE *files[3] = {NULL, NULL, NULL};
	const char *name = Cmd_Argc() > 1 ? Cmd_Argv(1) : "capture";
	size_t i;
	if (!name[0] || strlen(name) >= sizeof(label)) {
		Com_Printf("Usage: cl_perf_start <short-name> (letters, digits, _ and -)\n");
		return;
	}
	for (i = 0; name[i]; ++i) {
		if (!isalnum((unsigned char)name[i]) && name[i] != '_' && name[i] != '-') {
			Com_Printf("Invalid performance capture name.\n");
			return;
		}
	}
	Q_strlcpy(label, name, sizeof(label));
	for (i = 0; i < 3; ++i) {
		Com_sprintf(paths[i], sizeof(paths[i]), "%s/perf/%s-%s", FS_Gamedir(), label, suffixes[i]);
		FS_CreatePath(paths[i]);
		/* Exclusive creation preserves previous captures, including when a
		 * second process races the same label. Keep an active capture intact
		 * until all three new files have been reserved successfully. */
		files[i] = fopen(paths[i], "wx");
		if (!files[i]) {
			while (i > 0) { --i; fclose(files[i]); remove(paths[i]); }
			Com_Printf("Could not create capture files; use a new label and a writable game directory.\n");
			return;
		}
	}
	CL_PerfStop_f();
	perf_csv = files[0]; perf_views = files[1]; perf_meta = files[2];
	Cvar_Set("r_perf", "1");
	perf_count = 0;
	perf_last_end = perf_server = perf_simulation = perf_snapshot = perf_client = 0;
	perf_rss = -1;
#ifndef PP_PERF_BASELINE
	perf_effect_previous = *CL_GetEffectStats();
#endif
	fprintf(perf_csv, "frame,frame_ms,screen_ms,server_ms,simulation_ms,snapshot_send_ms,client_update_ms,prepare_ms,submit_ms,present_ms,views,width,height,server_edicts,monsters,dead_monsters,projectiles_by_effect,rss_kib");
	for (i = 0; i < PERF_METRICS; ++i) fprintf(perf_csv, ",%s", perf_metrics[i]);
	fprintf(perf_csv, "%s\n", perf_effect_names);
	fprintf(perf_views, "frame,slot,submit_ms,width,height,x,y,z,pitch,yaw,roll,entities,particles,lights,renderer_counters,renderer_serial,gpu_supported,gpu_origin_serial,gpu_ms");
	for (i = 0; i < PERF_METRICS; ++i) fprintf(perf_views, ",%s", perf_metrics[i]);
	fprintf(perf_views, "\n");
	fprintf(perf_meta, "All *_ms except gpu_ms are CPU-side wall times.\n"
		"gpu_ms is optional asynchronous GPU work for gpu_origin_serial, which can be a preceding view; -1 means unavailable.\n"
		"Deduplicate GPU origin serials and associate them with renderer_serial; do not add a delayed result to the current frame.\n"
		"frame_ms is completion-to-completion for the entire display, including frame limiting. First row has no interval.\n"
		"server_ms includes simulation + snapshot/send; submit_ms includes visibility and model work. Do not add nested columns.\n"
		"rss_kib is process resident memory sampled every 60 frames on Linux; -1 means unavailable.\n"
		"monsters/dead_monsters use server flags; projectiles_by_effect is an estimate, not a gameplay entity census.\n"
		"r_perf counters exclude 2D/HUD. Unsupported renderer counters are -1 in per-view CSV.\n");
	Com_Printf("Performance capture: %s/perf/%s-{frames,views}.csv\n", FS_Gamedir(), label);
}

void
CL_PerfInit(void)
{
	perf_initialized = 1;
	perf_frames = Cvar_Get("cl_perf_frames", "0", 0);
	perf_quit = Cvar_Get("cl_perf_quit", "0", 0);
	perf_screenshot = Cvar_Get("cl_perf_screenshot", "0", 0);
	Cmd_AddCommand("cl_perf_start", CL_PerfStart_f);
	Cmd_AddCommand("cl_perf_stop", CL_PerfStop_f);
	Cmd_AddCommand("cl_bench_local", CL_BenchLocal_f);
	Cmd_AddCommand("cl_bench_pose", CL_BenchPose_f);
}
void
CL_PerfShutdown(void)
{
	if (!perf_initialized) return;
	perf_initialized = 0;
	CL_PerfStop_f();
	Cmd_RemoveCommand("cl_perf_start");
	Cmd_RemoveCommand("cl_perf_stop");
	Cmd_RemoveCommand("cl_bench_local");
	Cmd_RemoveCommand("cl_bench_pose");
}

void
CL_PerfBeginDisplay(void)
{
	CL_BenchApplyPoses();
	perf_display_active = perf_csv && cls.state == ca_active && cl.refresh_prepped;
	if (!perf_display_active) return;
	perf_begin = Sys_Microseconds();
	perf_view_count = perf_depth = 0;
	perf_prepare = perf_present = 0;
	memset(perf_view, 0, sizeof(perf_view));
}

void CL_PerfBeginPrepare(void)
{
	if (perf_display_active && perf_depth++ == 0) perf_prepare_begin = Sys_Microseconds();
}
void CL_PerfEndPrepare(void)
{
	if (perf_display_active && perf_depth > 0 && --perf_depth == 0)
		perf_prepare += Sys_Microseconds() - perf_prepare_begin;
}
void CL_PerfBeginView(int slot)
{
	if (!perf_display_active || slot < 0 || slot >= 4 || perf_view_count >= PERF_VIEWS) return;
	perf_view[perf_view_count].serial = strtoull(Cvar_VariableString("r_perf_serial"), NULL, 10);
	perf_view[perf_view_count].begin = Sys_Microseconds();
}

void
CL_PerfEndView(int slot, const void *refdef)
{
	const refdef_t *rd = refdef;
	perf_view_t *v;
	size_t i;
	char name[64];
	if (!perf_display_active || !rd || slot < 0 || slot >= 4 || perf_view_count >= PERF_VIEWS) return;
	v = &perf_view[perf_view_count];
	v->usec = Sys_Microseconds() - v->begin;
	v->slot = slot;
	v->width = rd->width; v->height = rd->height;
	VectorCopy(rd->vieworg, v->origin);
	VectorCopy(rd->viewangles, v->angles);
	v->entities = rd->num_entities; v->particles = rd->num_particles; v->lights = rd->num_dlights;
	v->completed_serial = strtoull(Cvar_VariableString("r_perf_serial"), NULL, 10);
	v->supported = v->completed_serial != v->serial;
	v->gpu_supported = v->supported && Cvar_VariableValue("r_perf_gpu_supported");
	v->gpu_serial = v->gpu_supported ? strtoull(Cvar_VariableString("r_perf_gpu_serial"), NULL, 10) : 0;
	v->gpu_ms = v->gpu_supported ? Cvar_VariableValue("r_perf_gpu_ms") : -1;
	for (i = 0; i < PERF_METRICS; ++i) {
		Com_sprintf(name, sizeof(name), "r_perf_%s", perf_metrics[i]);
		v->values[i] = v->supported ? Cvar_VariableValue(name) : -1;
	}
	++perf_view_count;
}

void CL_PerfBeginPresent(void)
{
	if (perf_display_active) perf_present_begin = Sys_Microseconds();
}
void CL_PerfEndPresent(void)
{
	if (perf_display_active) perf_present += Sys_Microseconds() - perf_present_begin;
}

static void
CL_PerfSettings(void)
{
	static const char *settings[] = {
		"vid_renderer", "vid_fullscreen", "r_mode", "r_customwidth", "r_customheight",
		"r_vsync", "cl_async", "cl_maxfps", "vid_maxfps", "gl_finish",
		"gl1_picmip", "gl_texturemode", "gl1_dynamic", "r_shadows", "r_anisotropic", "r_msaa_samples",
		"r_novis", "r_cull", "r_fullbright", "r_drawentities", "r_drawworld", "r_retexturing", "r_lerpmodels",
		"gl1_static_world", "gl3_static_world", "r_viscache", "r_modulate", "r_clear", "vid_gamma",
		"gl1_overbrightbits", "gl3_overbrightbits", "gl3_intensity", "gl1_multitexture", "gl1_lightmapcopies",
		"r_perf_static_vertex_total", "r_perf_static_index_total", "r_perf_gpu_supported",
		"cl_entities", "cl_particles", "cl_lights", "cl_blend", "paused", "timescale",
		"skill", "coop", "deathmatch", "maxclients", "ss_active", "ss_players"
	};
	size_t i;
	fprintf(perf_meta, "map=%s\nframebuffer=%dx%d\n", cl.configstrings[CS_MODELS + 1], viddef.width, viddef.height);
	for (i = 0; i < sizeof(settings) / sizeof(settings[0]); ++i)
		fprintf(perf_meta, "%s=%s\n", settings[i], Cvar_VariableString(settings[i]));
	fprintf(perf_meta, "Record GL_VENDOR/GL_RENDERER/GL_VERSION from the startup log, OS, CPU, driver, display transport and commit separately.\n");
	fflush(perf_meta);
}

void
CL_PerfEndDisplay(void)
{
	long long end, submit = 0;
	int slot, entities = -1, monsters = 0, dead = 0, projectiles = 0, all_supported = 1;
	double sum[PERF_METRICS] = {0};
	size_t i;
	if (!perf_display_active || !perf_view_count) return;
	end = Sys_Microseconds();
	if (!perf_count) CL_PerfSettings();
#ifdef __linux__
	if (perf_count % 60 == 0) {
		FILE *f = fopen("/proc/self/statm", "r");
		unsigned long pages, total_pages;
		if (f) {
			if (fscanf(f, "%lu %lu", &total_pages, &pages) == 2) perf_rss = (long)(pages * (unsigned long)sysconf(_SC_PAGESIZE) / 1024);
			fclose(f);
		}
	}
#endif
	if (svs.initialized && ge && ge->edicts) {
		int n;
		entities = 0;
		for (n = 0; n < ge->num_edicts; ++n) {
			edict_t *e = EDICT_NUM(n);
			if (!e->inuse) continue;
			++entities;
			if (e->svflags & SVF_DEADMONSTER) ++dead;
			else if (e->svflags & SVF_MONSTER) ++monsters;
			if (e->s.effects & (EF_ROCKET | EF_GRENADE | EF_BLASTER | EF_HYPERBLASTER)) ++projectiles;
		}
	}
	for (slot = 0; slot < PERF_VIEWS; ++slot) {
		perf_view_t *v = &perf_view[slot];
		if (!v->begin) continue;
		submit += v->usec;
		fprintf(perf_views, "%d,%d,%.3f,%d,%d,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%d,%d,%d,%d,%" PRIu64 ",%d,%" PRIu64 ",%.3f",
			perf_count, v->slot, v->usec / 1000.0, v->width, v->height,
			v->origin[0], v->origin[1], v->origin[2], v->angles[0], v->angles[1], v->angles[2],
			v->entities, v->particles, v->lights, v->supported, v->completed_serial,
			v->gpu_supported, v->gpu_serial, v->gpu_ms);
		for (i = 0; i < PERF_METRICS; ++i) {
			fprintf(perf_views, ",%.3f", v->values[i]);
			if (v->supported) sum[i] += v->values[i];
			else all_supported = 0;
		}
		fputc('\n', perf_views);
	}
	fprintf(perf_csv, "%d,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%d,%d,%d,%d,%d,%d,%d,%ld",
		perf_count, perf_last_end ? (end - perf_last_end) / 1000.0 : 0.0,
		(end - perf_begin) / 1000.0, perf_server / 1000.0, perf_simulation / 1000.0,
		perf_snapshot / 1000.0, perf_client / 1000.0, perf_prepare / 1000.0,
		submit / 1000.0, perf_present / 1000.0, perf_view_count, viddef.width, viddef.height,
		entities, monsters, dead, projectiles, perf_rss);
	for (i = 0; i < PERF_METRICS; ++i) fprintf(perf_csv, ",%.3f", all_supported ? sum[i] : -1.0);
#ifndef PP_PERF_BASELINE
	{
		const cl_effect_stats_t *s = CL_GetEffectStats();
#define PERF_EFFECT_DELTA(field) fprintf(perf_csv, ",%" PRIu64, s->field >= perf_effect_previous.field ? s->field - perf_effect_previous.field : s->field)
		PERF_EFFECT_DELTA(particles_created);
		PERF_EFFECT_DELTA(particle_updates);
		PERF_EFFECT_DELTA(particles_expired);
		PERF_EFFECT_DELTA(shared_preparations);
		PERF_EFFECT_DELTA(entity_effect_evaluations);
		PERF_EFFECT_DELTA(entity_effect_reuses);
		PERF_EFFECT_DELTA(temp_events_parsed);
		PERF_EFFECT_DELTA(sprite_updates);
#undef PERF_EFFECT_DELTA
		fprintf(perf_csv, ",%u,%u", s->active_particles, s->prepared_particles);
		perf_effect_previous = *s;
	}
#else
	fprintf(perf_csv, ",-1,-1,-1,-1,-1,-1,-1,-1,-1,-1");
#endif
	fputc('\n', perf_csv);
	perf_last_end = end;
	perf_server = perf_simulation = perf_snapshot = perf_client = 0;
	perf_display_active = 0;
	++perf_count;
	if (perf_count % 120 == 0) { fflush(perf_csv); fflush(perf_views); }
	if (perf_frames && perf_frames->value > 0 && perf_count >= perf_frames->value) {
		CL_PerfStop_f();
		if (perf_screenshot && perf_screenshot->value) Cbuf_AddText("screenshot\n");
		if (perf_quit && perf_quit->value) Cbuf_AddText("quit\n");
	}
}
