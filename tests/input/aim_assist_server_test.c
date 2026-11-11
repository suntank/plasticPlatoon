/* Authoritative target filtering and real weapon-angle correction. */
#include "../../src/game/player/aim_assist.c"
#include <assert.h>

game_import_t gi;
game_export_t globals;
level_locals_t level;
edict_t *g_edicts;
cvar_t *deathmatch;

static edict_t entities[12];
static gclient_t clients[2];
static cvar_t dm, vars[8];
static int var_count, blocked, trace_calls;
static edict_t *trace_target;

static cvar_t *cvar(const char *name, const char *value, int flags)
{
	cvar_t *var = &vars[var_count++];
	assert(var_count < 8);
	var->value = strtof(value, NULL);
	return var;
}

static trace_t trace_world(vec3_t start, vec3_t mins, vec3_t maxs,
	vec3_t end, edict_t *pass, int mask)
{
	trace_t result = {0};
	assert(pass == &entities[1] && mask == MASK_SHOT);
	++trace_calls;
	result.fraction = blocked == 1 || (blocked == 2 && end[2] < 15) ? 0.25f : 1;
	result.ent = result.fraction < 1 ? &entities[0] : trace_target;
	return result;
}

static void enemy(int index, float x, float y)
{
	edict_t *ent = &entities[index];
	memset(ent, 0, sizeof(*ent));
	ent->inuse = true;
	ent->svflags = SVF_MONSTER;
	ent->health = 100;
	ent->takedamage = DAMAGE_AIM;
	VectorSet(ent->mins, -16, -16, -24);
	VectorSet(ent->maxs, 16, 16, 32);
	VectorSet(ent->s.origin, x, y, 0);
}

static void reset(void)
{
	memset(entities, 0, sizeof(entities));
	memset(clients, 0, sizeof(clients));
	memset(&level, 0, sizeof(level));
	memset(&dm, 0, sizeof(dm));
	g_edicts = entities;
	globals.num_edicts = 6;
	deathmatch = &dm;
	gi.cvar = cvar;
	gi.trace = trace_world;
	entities[1].client = &clients[0];
	entities[1].inuse = true;
	entities[1].health = 100;
	entities[1].viewheight = 22;
	clients[0].ps.pmove.pm_type = PM_NORMAL;
	blocked = trace_calls = 0;
	trace_target = NULL;
	PP_AimAssist_ResetClient(&entities[1]);
	if (assist_enabled) assist_enabled->value = 1;
}

static void update(int buttons, int msec)
{
	usercmd_t cmd = {0};
	cmd.buttons = buttons;
	cmd.msec = msec;
	PP_AimAssist_Update(&entities[1], &cmd);
}

static qboolean targeted(void)
{
	return (clients[0].ps.stats[STAT_AIMASSIST_FLAGS] & AIMASSIST_TARGET) != 0;
}

static void test_controller_and_real_shot(void)
{
	vec3_t saved, before;
	reset();
	enemy(2, 512, 32);
	update(0, 16);
	assert(!clients[0].ps.stats[STAT_AIMASSIST_FLAGS] && trace_calls == 0);
	VectorCopy(clients[0].v_angle, before);
	update(BUTTON_GAMEPAD, 16);
	assert(targeted() && clients[0].ps.stats[STAT_AIMASSIST_YAW] > 300);
	assert(clients[0].ps.stats[STAT_AIMASSIST_HIP_YAW] > 0);
	assert(clients[0].ps.stats[STAT_AIMASSIST_HIP_YAW] < clients[0].ps.stats[STAT_AIMASSIST_YAW]);
	assert(VectorCompare(before, clients[0].v_angle));
	assert(PP_AimAssist_BeginShot(&entities[1], saved));
	assert(clients[0].v_angle[YAW] > 0 && clients[0].v_angle[YAW] < 1);
	assert(clients[0].ps.viewangles[YAW] == 0); /* The hip camera stays still. */
	PP_AimAssist_EndShot(&entities[1], saved);
	assert(VectorCompare(before, clients[0].v_angle));
	update(BUTTON_GAMEPAD | BUTTON_ADS, 16);
	assert(targeted() && clients[0].ps.stats[STAT_AIMASSIST_YAW] > 0);
	assert(clients[0].ps.stats[STAT_AIMASSIST_HIP_YAW] == 0);
	assert(!PP_AimAssist_BeginShot(&entities[1], saved)); /* No doubled ADS aim. */
	update(0, 16);
	assert(!clients[0].ps.stats[STAT_AIMASSIST_FLAGS]);
	assert(!PP_AimAssist_BeginShot(&entities[1], saved));
}

static void test_filtering(void)
{
	reset(); enemy(2, 512, 20);
	entities[2].health = 0; update(BUTTON_GAMEPAD, 100); assert(!targeted());
	enemy(2, 512, 20); entities[2].deadflag = DEAD_DEAD; update(BUTTON_GAMEPAD, 100); assert(!targeted());
	enemy(2, 512, 20); entities[2].monsterinfo.aiflags |= AI_GOOD_GUY; update(BUTTON_GAMEPAD, 100); assert(!targeted());
	enemy(2, 512, 20); entities[2].svflags |= SVF_NOCLIENT; update(BUTTON_GAMEPAD, 100); assert(!targeted());
	enemy(2, 512, 20); entities[2].svflags |= SVF_DEADMONSTER; update(BUTTON_GAMEPAD, 100); assert(!targeted());
	enemy(2, 512, 20); entities[2].takedamage = DAMAGE_NO; update(BUTTON_GAMEPAD, 100); assert(!targeted());
	enemy(2, 512, 20); entities[2].client = &clients[1]; update(BUTTON_GAMEPAD, 100); assert(!targeted());
	enemy(2, 2048, 0); update(BUTTON_GAMEPAD, 100); assert(!targeted());
	enemy(2, 512, 100); update(BUTTON_GAMEPAD, 100); assert(!targeted());
	enemy(2, 512, 20); blocked = 1; update(BUTTON_GAMEPAD, 100); assert(!targeted());
	blocked = 2; update(BUTTON_GAMEPAD, 100); assert(!targeted()); /* Head visible, chest behind cover. */
	dm.value = 1; update(BUTTON_GAMEPAD, 100); assert(!targeted());
	dm.value = 0; clients[0].showhelp = true; update(BUTTON_GAMEPAD, 100); assert(!targeted());
	clients[0].showhelp = false; entities[1].health = 0; update(BUTTON_GAMEPAD, 100); assert(!targeted());
	entities[1].health = 100; assist_enabled->value = 0; update(BUTTON_GAMEPAD, 100); assert(!targeted());
}

static void test_chest_target_for_both_modes(void)
{
	/* This fixture's chest is z=9.6; its higher/head sample was z=20.8.
	 * Starting directly on that higher point must still settle on the chest. */
	const float chest_pitch = atan2f(22.0f - 9.6f, 512.0f) * (180.0f / M_PI);
	const float head_pitch = atan2f(22.0f - 20.8f, 512.0f) * (180.0f / M_PI);
	int hip_pitch = 0, mode;
	for (mode = 0; mode < 2; ++mode)
	{
		vec3_t saved;
		int buttons = BUTTON_GAMEPAD | (mode ? BUTTON_ADS : 0);
		reset();
		enemy(2, 512, 0);
		clients[0].v_angle[PITCH] = head_pitch;
		update(buttons, 100);
		assert(targeted());
		assert(fabsf(head_pitch + clients[0].ps.stats[STAT_AIMASSIST_PITCH] * 0.01f - chest_pitch) < 0.01f);
		assert(clients[0].ps.stats[STAT_AIMASSIST_PITCH] > 100);
		if (!mode)
		{
			hip_pitch = clients[0].ps.stats[STAT_AIMASSIST_PITCH];
			assert(PP_AimAssist_BeginShot(&entities[1], saved));
			assert(fabsf(clients[0].v_angle[PITCH] - chest_pitch) < 0.01f);
			PP_AimAssist_EndShot(&entities[1], saved);
		}
		else
		{
			assert(clients[0].ps.stats[STAT_AIMASSIST_PITCH] == hip_pitch);
		}

		/* A visible head above cover is insufficient for either mode. */
		blocked = 2;
		update(buttons, 100);
		assert(!targeted());
		blocked = 0;
		update(buttons, 100);
		assert(targeted());
	}
}

static void test_stability_and_time(void)
{
	float one_step;
	reset(); enemy(2, 512, 32);
	update(BUTTON_GAMEPAD, 100);
	one_step = aim_states[0].hip_yaw;
	reset(); enemy(2, 512, 32);
	update(BUTTON_GAMEPAD, 50); update(BUTTON_GAMEPAD, 50);
	assert(fabsf(aim_states[0].hip_yaw - one_step) < 0.0001f);
	enemy(3, 512, 8);
	update(BUTTON_GAMEPAD, 16);
	assert(aim_states[0].target == 2); /* New closer-to-center enemy cannot steal a lock. */
	entities[2].health = 0;
	update(BUTTON_GAMEPAD, 16);
	assert(aim_states[0].target == 3);
	clients[0].v_angle[YAW] = 90;
	update(BUTTON_GAMEPAD, 100);
	assert(!targeted() && aim_states[0].hip_yaw == 0);
	PP_AimAssist_ResetClient(&entities[1]);
	assert(aim_states[0].target == 0 && !aim_states[0].active);
}

int main(void)
{
	test_controller_and_real_shot();
	test_chest_target_for_both_modes();
	test_filtering();
	test_stability_and_time();
	puts("Server aim assist: chest preference in both modes, controller gating, hostility/LOS, shot alignment, hysteresis and timing passed");
	return 0;
}
