/* Controller aiming assistance. Selection is authoritative, so clients never
 * attract their aim toward a corpse, a squad mate, or a target behind a wall. */
#include "../header/local.h"

typedef struct
{
	int target;
	qboolean active, ads;
	float hip_pitch, hip_yaw;
} pp_aimassist_state_t;

/* Deliberately transient: changing gclient_t would invalidate existing saves. */
static pp_aimassist_state_t aim_states[MAX_CLIENTS];
static cvar_t *assist_enabled, *assist_range, *assist_ads_cone;
static cvar_t *assist_hip_cone, *assist_hip_speed;

static pp_aimassist_state_t *
PP_AimAssist_State(edict_t *ent)
{
	int index;
	if (!ent || !ent->client || !g_edicts)
	{
		return NULL;
	}
	index = (int)(ent - g_edicts) - 1;
	return index >= 0 && index < MAX_CLIENTS ? &aim_states[index] : NULL;
}

static float
PP_AimAssist_AngleDelta(float angle)
{
	angle = fmodf(angle, 360.0f);
	if (angle > 180.0f) angle -= 360.0f;
	if (angle < -180.0f) angle += 360.0f;
	return angle;
}

static float
PP_AimAssist_Approach(float current, float target, float step)
{
	float delta = target - current;
	if (delta > step) delta = step;
	if (delta < -step) delta = -step;
	return current + delta;
}

static float
PP_AimAssist_Value(cvar_t *var, float fallback, float low, float high)
{
	float value = var->value;
	if (!isfinite(value)) value = fallback;
	return Q_clamp(value, low, high);
}

static void
PP_AimAssist_Init(void)
{
	if (assist_enabled) return;
	assist_enabled = gi.cvar("sv_aimassist", "1", 0);
	assist_range = gi.cvar("sv_aimassist_range", "1024", 0);
	assist_ads_cone = gi.cvar("sv_aimassist_ads_cone", "8", 0);
	assist_hip_cone = gi.cvar("sv_aimassist_hip_cone", "6", 0);
	assist_hip_speed = gi.cvar("sv_aimassist_hip_speed", "40", 0);
}

void
PP_AimAssist_ResetClient(edict_t *ent)
{
	pp_aimassist_state_t *state = PP_AimAssist_State(ent);
	int i;
	if (!state) return;
	memset(state, 0, sizeof(*state));
	for (i = STAT_AIMASSIST_FLAGS; i <= STAT_AIMASSIST_HIP_YAW; ++i)
	{
		ent->client->ps.stats[i] = 0;
	}
}

/* Use one consistent chest/body point in both modes. Choosing whichever body
 * sample is nearest the reticle biases assistance toward heads at eye level. */
static qboolean
PP_AimAssist_Target(edict_t *player, edict_t *target, float cone, float range,
	float *pitch, float *yaw, float *score)
{
	vec3_t eye, point, direction, angles;
	float distance, candidate_score;
	if (!target->inuse || target == player || target->client ||
		!(target->svflags & SVF_MONSTER) || (target->svflags & (SVF_DEADMONSTER | SVF_NOCLIENT)) ||
		target->health <= 0 || target->deadflag || target->takedamage == DAMAGE_NO ||
		(target->monsterinfo.aiflags & AI_GOOD_GUY))
	{
		return false;
	}
	VectorCopy(player->s.origin, eye);
	eye[2] += player->viewheight;
	{
		trace_t trace;
		float p, y;
		point[0] = target->s.origin[0] + (target->mins[0] + target->maxs[0]) * 0.5f;
		point[1] = target->s.origin[1] + (target->mins[1] + target->maxs[1]) * 0.5f;
		point[2] = target->s.origin[2] + target->mins[2] +
			(target->maxs[2] - target->mins[2]) * 0.6f;
		VectorSubtract(point, eye, direction);
		distance = VectorLength(direction);
		if (distance < 1.0f || distance > range) return false;
		/* vectoangles() rounds to whole degrees; assistance must not inherit
 * that visible one-degree stepping while settling onto a target. */
		angles[YAW] = atan2f(direction[1], direction[0]) * (180.0f / M_PI);
		angles[PITCH] = -atan2f(direction[2], hypotf(direction[0], direction[1])) * (180.0f / M_PI);
		p = PP_AimAssist_AngleDelta(angles[PITCH] - player->client->v_angle[PITCH]);
		y = PP_AimAssist_AngleDelta(angles[YAW] - player->client->v_angle[YAW]);
		candidate_score = p * p + y * y;
		if (candidate_score > cone * cone) return false;
		trace = gi.trace(eye, NULL, NULL, point, player, MASK_SHOT);
		if (trace.startsolid || trace.allsolid || (trace.fraction < 1.0f && trace.ent != target)) return false;
		*pitch = p;
		*yaw = y;
		*score = candidate_score;
	}
	return true;
}

void
PP_AimAssist_Update(edict_t *ent, const usercmd_t *cmd)
{
	pp_aimassist_state_t *state = PP_AimAssist_State(ent);
	gclient_t *client;
	float range, cone, pitch = 0, yaw = 0, score = 0, dt, step;
	int target = 0, i;
	if (!state || !cmd) return;
	PP_AimAssist_Init();
	client = ent->client;
	if (!assist_enabled->value || deathmatch->value || !(cmd->buttons & BUTTON_GAMEPAD) ||
		ent->health <= 0 || ent->deadflag || client->resp.spectator || client->chase_target ||
		client->ps.pmove.pm_type != PM_NORMAL || level.intermissiontime ||
		client->showhelp || client->showinventory || client->showscores)
	{
		PP_AimAssist_ResetClient(ent);
		return;
	}
	state->active = true;
	state->ads = (cmd->buttons & BUTTON_ADS) != 0;
	range = PP_AimAssist_Value(assist_range, 1024, 64, 4096);
	cone = PP_AimAssist_Value(state->ads ? assist_ads_cone : assist_hip_cone,
		state->ads ? 8 : 6, 0, 20);
	/* A retained target gets a small release margin. This avoids jumping
 * between adjacent enemies while still allowing the player to look away. */
	if (state->target > 0 && state->target < globals.num_edicts &&
		PP_AimAssist_Target(ent, &g_edicts[state->target], cone + 2, range,
			&pitch, &yaw, &score))
	{
		target = state->target;
	}
	else
	{
		for (i = 1; i < globals.num_edicts; ++i)
		{
			float p, y, candidate_score = 0;
			if (PP_AimAssist_Target(ent, &g_edicts[i], cone, range, &p, &y, &candidate_score) &&
				(!target || candidate_score < score))
			{
				target = i;
				pitch = p;
				yaw = y;
				score = candidate_score;
			}
		}
	}
	state->target = target;
	dt = Q_clamp(cmd->msec * 0.001f, 0, 0.2f);
	step = PP_AimAssist_Value(assist_hip_speed, 40, 1, 180) * dt;
	if (state->ads)
	{
		/* The client moves the actual ADS view; hip offset is never also
 * applied to those shots, which would double the correction. */
		state->hip_pitch = state->hip_yaw = 0;
	}
	else
	{
		state->hip_pitch = PP_AimAssist_Approach(state->hip_pitch, target ? pitch : 0, step);
		state->hip_yaw = PP_AimAssist_Approach(state->hip_yaw, target ? yaw : 0, step);
	}
	client->ps.stats[STAT_AIMASSIST_FLAGS] = AIMASSIST_ACTIVE | (target ? AIMASSIST_TARGET : 0);
	client->ps.stats[STAT_AIMASSIST_PITCH] = (short)lroundf(pitch * 100);
	client->ps.stats[STAT_AIMASSIST_YAW] = (short)lroundf(yaw * 100);
	client->ps.stats[STAT_AIMASSIST_HIP_PITCH] = (short)lroundf(state->hip_pitch * 100);
	client->ps.stats[STAT_AIMASSIST_HIP_YAW] = (short)lroundf(state->hip_yaw * 100);
}

qboolean
PP_AimAssist_BeginShot(edict_t *ent, vec3_t saved_angles)
{
	pp_aimassist_state_t *state = PP_AimAssist_State(ent);
	if (!state || !state->active || state->ads) return false;
	VectorCopy(ent->client->v_angle, saved_angles);
	ent->client->v_angle[PITCH] += state->hip_pitch;
	ent->client->v_angle[YAW] += state->hip_yaw;
	return true;
}

void
PP_AimAssist_EndShot(edict_t *ent, const vec3_t saved_angles)
{
	if (ent && ent->client) VectorCopy(saved_angles, ent->client->v_angle);
}
