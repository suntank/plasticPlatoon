/*
 * Plastic Platoon campaign co-op rescue and redeployment.
 */
#include "../header/local.h"
#include "../monster/misc/player.h"

#define REVIVE_REACH 96.0f
#define USE_TIMEOUT_FRAMES 5

static cvar_t *bleedout_seconds;
static cvar_t *revive_seconds;
static cvar_t *revive_health_percent;

void
Coop_RescueInit(void)
{
	bleedout_seconds = gi.cvar("pp_coop_bleedout_seconds", "25", 0);
	revive_seconds = gi.cvar("pp_coop_revive_seconds", "2", 0);
	revive_health_percent = gi.cvar("pp_coop_revive_health_percent", "30", 0);
}

static float
RescueTuning(cvar_t *setting, float minimum, float maximum, float fallback)
{
	float value = setting->value;
	return isfinite(value) ? Q_max(minimum, Q_min(maximum, value)) : fallback;
}

qboolean
Coop_RescueActive(void)
{
	return coop->value && QM_Campaign();
}

static qboolean
SquadMember(const edict_t *ent)
{
	return ent->inuse && ent->client && ent->client->pers.connected &&
		!ent->client->pers.spectator;
}

qboolean
Coop_IsStanding(const edict_t *ent)
{
	return SquadMember(ent) && ent->health > 0 && !ent->deadflag &&
		!ent->client->resp.spectator;
}

qboolean
Coop_IsIncapacitated(const edict_t *ent)
{
	return ent->client && (ent->client->coop_rescue.bleedout_frame ||
		ent->client->coop_rescue.awaiting_redeploy);
}

static void
CancelRevive(gclient_t *client)
{
	coop_rescue_t *rescue = &client->coop_rescue;

	if (rescue->revive_target)
	{
		rescue->require_use_release = rescue->last_use_frame > 0;
		rescue->revive_target = 0;
	}
}

void
Coop_InterruptRevive(edict_t *ent)
{
	int i;

	CancelRevive(ent->client);
	if (!ent->client->coop_rescue.bleedout_frame)
	{
		return;
	}

	for (i = 1; i <= game.maxclients; ++i)
	{
		if (g_edicts[i].inuse &&
			g_edicts[i].client->coop_rescue.revive_target == ent - g_edicts)
		{
			CancelRevive(g_edicts[i].client);
		}
	}
}

qboolean
Coop_DownPlayer(edict_t *ent)
{
	gclient_t *client = ent->client;
	float seconds;

	if (!Coop_RescueActive() || level.intermissiontime || ent->deadflag ||
		!SquadMember(ent) || client->resp.spectator)
	{
		return false;
	}

	Coop_InterruptRevive(ent);
	seconds = RescueTuning(bleedout_seconds, FRAMETIME, 300, 25);
	client->coop_rescue.bleedout_frame = level.framenum +
		(int)ceilf(seconds * (1.0f / FRAMETIME));
	ent->health = 0;
	ent->flags &= ~FL_NO_KNOCKBACK;
	ent->s.modelindex2 = 0;
	ent->s.sound = 0;
	ent->velocity[0] = ent->velocity[1] = 0;
	ent->maxs[2] = 4;
	ent->viewheight = -2;
	client->ps.pmove.pm_flags &= ~PMF_TIME_WATERJUMP;
	client->ps.pmove.pm_flags |= PMF_COOP_DOWNED | PMF_DUCKED;
	client->ps.gunindex = 0;
	client->weapon_sound = 0;
	client->grenade_time = 0;
	client->grenade_blew_up = false;
	client->newweapon = NULL;
	client->buttons = client->latched_buttons = 0;
	client->coop_rescue.last_use_frame = 0;
	client->coop_rescue.require_use_release = false;
	client->showinventory = client->showscores = client->showhelp = false;
	client->anim_priority = ANIM_BASIC;
	client->anim_duck = true;
	ent->s.frame = FRAME_crstnd01;
	client->anim_end = FRAME_crstnd19;
	PP_AimAssist_ResetClient(ent);
	ClientUpdateWeaponFov(client);
	gi.linkentity(ent);
	return true;
}

void
Coop_RescueInput(edict_t *ent, const usercmd_t *cmd)
{
	coop_rescue_t *rescue = &ent->client->coop_rescue;

	if (cmd->buttons & BUTTON_USE)
	{
		rescue->last_use_frame = level.framenum + 1;
	}
	else
	{
		rescue->last_use_frame = 0;
		rescue->require_use_release = false;
		CancelRevive(ent->client);
	}
}

static qboolean
ReviveInReach(edict_t *rescuer, edict_t *patient)
{
	vec3_t delta, start;
	trace_t trace;

	VectorSubtract(patient->s.origin, rescuer->s.origin, delta);
	if (VectorLengthSquared(delta) > REVIVE_REACH * REVIVE_REACH)
	{
		return false;
	}

	VectorCopy(rescuer->s.origin, start);
	start[2] += rescuer->viewheight;
	trace = gi.trace(start, vec3_origin, vec3_origin, patient->s.origin,
		rescuer, MASK_SOLID);
	return trace.fraction == 1.0f;
}

static void
RevivePlayer(edict_t *patient)
{
	gclient_t *client = patient->client;
	float percent = RescueTuning(revive_health_percent, 1, 100, 30);
	gitem_t *lastweapon = client->pers.lastweapon;

	client->coop_rescue.bleedout_frame = 0;
	client->ps.pmove.pm_flags &= ~PMF_COOP_DOWNED;
	patient->health = Q_max(1, (int)(patient->max_health * (percent / 100.0f)));
	patient->enemy = NULL;
	patient->air_finished = level.time + 12;
	patient->s.modelindex2 = 255;
	client->newweapon = client->pers.weapon;
	ChangeWeapon(patient);
	client->pers.lastweapon = lastweapon;
}

static void
StartWaiting(edict_t *ent)
{
	gclient_t *client = ent->client;

	Coop_InterruptRevive(ent);
	client->coop_rescue.bleedout_frame = 0;
	client->coop_rescue.awaiting_redeploy = true;
	client->resp.spectator = true;
	ent->movetype = MOVETYPE_NOCLIP;
	ent->solid = SOLID_NOT;
	ent->svflags |= SVF_NOCLIENT;
	ent->takedamage = DAMAGE_NO;
	ent->groundentity = NULL;
	VectorClear(ent->velocity);
	ent->waterlevel = ent->watertype = 0;
	client->ps.pmove.pm_type = PM_FREEZE;
	client->ps.pmove.pm_flags = PMF_NO_PREDICTION;
	client->ps.pmove.pm_time = 0;
	gi.linkentity(ent);
}

static void
RetrySquad(void)
{
	int i;

	/* Remove downed bodies before any of the regular co-op spawns run. */
	for (i = 1; i <= game.maxclients; ++i)
	{
		edict_t *ent = &g_edicts[i];
		if (SquadMember(ent) && Coop_IsIncapacitated(ent))
		{
			StartWaiting(ent);
		}
	}
	gi.bprintf(PRINT_HIGH, "Squad wiped. Retrying from the mission start.\n");
	for (i = 1; i <= game.maxclients; ++i)
	{
		edict_t *ent = &g_edicts[i];
		if (SquadMember(ent) && Coop_IsIncapacitated(ent))
		{
			respawn(ent);
		}
	}
}

static qboolean
ReviveAvailable(const edict_t *ent)
{
	return SquadMember(ent) && ent->client->coop_rescue.bleedout_frame > level.framenum;
}

static void
WaitIfExpired(edict_t *ent)
{
	int deadline = ent->client->coop_rescue.bleedout_frame;

	if (deadline && level.framenum >= deadline)
	{
		StartWaiting(ent);
	}
}

static edict_t *
ReviveOwner(const edict_t *patient)
{
	int i;

	for (i = 1; i <= game.maxclients; ++i)
	{
		edict_t *ent = &g_edicts[i];
		if (Coop_IsStanding(ent) &&
			ent->client->coop_rescue.revive_target == patient - g_edicts)
		{
			return ent;
		}
	}
	return NULL;
}

/* Prefer a teammate this player can actually help. When none is in reach,
 * keep a marker on the nearest downed teammate. */
static edict_t *
FindDownedTeammate(edict_t *ent, qboolean *in_reach)
{
	edict_t *nearest = NULL;
	float best_distance = HUGE_VALF;
	int i;

	*in_reach = false;
	for (i = 1; i <= game.maxclients; ++i)
	{
		edict_t *candidate = &g_edicts[i];
		vec3_t delta;
		float distance;
		qboolean reachable;

		if (!ReviveAvailable(candidate))
		{
			continue;
		}
		VectorSubtract(candidate->s.origin, ent->s.origin, delta);
		distance = VectorLengthSquared(delta);
		if (distance >= best_distance && *in_reach)
		{
			continue;
		}
		reachable = distance <= REVIVE_REACH * REVIVE_REACH &&
			!ReviveOwner(candidate) && ReviveInReach(ent, candidate);
		if (reachable || (!*in_reach && distance < best_distance))
		{
			nearest = candidate;
			best_distance = distance;
			*in_reach = reachable;
		}
	}
	return nearest;
}

void
Coop_RescueFrame(void)
{
	int i, standing = 0, incapacitated = 0;

	if (!Coop_RescueActive() || level.intermissiontime)
	{
		return;
	}

	for (i = 1; i <= game.maxclients; ++i)
	{
		edict_t *ent = &g_edicts[i];

		standing += Coop_IsStanding(ent);
		incapacitated += SquadMember(ent) && Coop_IsIncapacitated(ent);
	}
	if (!incapacitated)
	{
		return;
	}
	if (!standing)
	{
		RetrySquad();
		return;
	}

	/* Expiry wins over a revive finishing on the same server frame. */
	for (i = 1; i <= game.maxclients; ++i)
	{
		edict_t *ent = &g_edicts[i];
		if (SquadMember(ent))
		{
			WaitIfExpired(ent);
		}
	}

	for (i = 1; i <= game.maxclients; ++i)
	{
		edict_t *ent = &g_edicts[i];
		coop_rescue_t *rescue = &ent->client->coop_rescue;
		edict_t *patient;
		qboolean in_reach;

		if (!SquadMember(ent))
		{
			continue;
		}
		if (rescue->awaiting_redeploy)
		{
			if (!ent->client->chase_target)
			{
				GetChaseTarget(ent);
			}
			else
			{
				UpdateChaseCam(ent);
			}
			continue;
		}
		if (!Coop_IsStanding(ent))
		{
			continue;
		}
		if (!rescue->last_use_frame || level.framenum - rescue->last_use_frame >= USE_TIMEOUT_FRAMES)
		{
			CancelRevive(ent->client);
			continue;
		}
		if (rescue->require_use_release)
		{
			continue;
		}
		if (rescue->revive_target)
		{
			patient = &g_edicts[rescue->revive_target];
			if (!ReviveAvailable(patient) || !ReviveInReach(ent, patient))
			{
				CancelRevive(ent->client);
			}
			else if (level.framenum - rescue->revive_start >= rescue->revive_frames)
			{
				RevivePlayer(patient);
				CancelRevive(ent->client);
			}
			continue;
		}
		patient = FindDownedTeammate(ent, &in_reach);
		if (in_reach)
		{
			float seconds = RescueTuning(revive_seconds, FRAMETIME, 60, 2);
			rescue->revive_target = patient - g_edicts;
			rescue->revive_start = level.framenum;
			rescue->revive_frames = (int)ceilf(seconds * (1.0f / FRAMETIME));
		}
	}
}

void
Coop_RescueStats(edict_t *ent)
{
	short *stats = ent->client->ps.stats;
	coop_rescue_t *rescue = &ent->client->coop_rescue;
	edict_t *patient = NULL, *rescuer = NULL;
	qboolean in_reach;

	stats[STAT_COOP_RESCUE] = COOP_RESCUE_NONE;
	stats[STAT_COOP_BLEEDOUT] = stats[STAT_COOP_REVIVE] = stats[STAT_COOP_TEAMMATE] = 0;
	if (level.intermissiontime || !Coop_RescueActive())
	{
		return;
	}
	if (rescue->awaiting_redeploy)
	{
		stats[STAT_COOP_RESCUE] = COOP_RESCUE_WAITING;
		return;
	}
	if (rescue->bleedout_frame)
	{
		patient = ent;
		rescuer = ReviveOwner(ent);
		stats[STAT_COOP_RESCUE] = COOP_RESCUE_DOWNED;
	}
	else if (Coop_IsStanding(ent))
	{
		if (rescue->revive_target)
		{
			patient = &g_edicts[rescue->revive_target];
			rescuer = ent;
			in_reach = true;
		}
		else
		{
			patient = FindDownedTeammate(ent, &in_reach);
		}
		if (patient)
		{
			stats[STAT_COOP_TEAMMATE] = patient - g_edicts;
			stats[STAT_COOP_RESCUE] = in_reach ?
				COOP_RESCUE_IN_REACH : COOP_RESCUE_TEAMMATE_DOWN;
		}
	}
	if (patient)
	{
		int remaining = patient->client->coop_rescue.bleedout_frame - level.framenum;
		stats[STAT_COOP_BLEEDOUT] = Q_max(1, (int)ceilf(remaining * FRAMETIME));
	}
	if (rescuer)
	{
		coop_rescue_t *active = &rescuer->client->coop_rescue;
		stats[STAT_COOP_REVIVE] = 1 + 100 * (level.framenum - active->revive_start) /
			active->revive_frames;
	}
}

/* Mission exits recover the existing client in place before the debrief,
 * where the usual campaign shop and next-level spawn take over. */
void
Coop_PrepareTransition(edict_t *ent)
{
	gclient_t *client = ent->client;

	if (Coop_IsIncapacitated(ent))
	{
		ent->health = ent->max_health;
		client->resp.spectator = false;
		client->chase_target = NULL;
		client->ps.pmove.pm_flags &= ~(PMF_COOP_DOWNED | PMF_NO_PREDICTION);
	}
	memset(&client->coop_rescue, 0, sizeof(client->coop_rescue));
}

/* Fire once the map has reached a safe position. "target" names a set of
 * info_notnull spawn pads, spaced like player starts. Each activation is
 * one-shot, including when the squad reaches it with everyone standing. */
void
platoon_checkpoint_use(edict_t *self, edict_t *other, edict_t *activator)
{
	int i;
	qboolean standing = false;

	if (self->count || level.intermissiontime ||
		(activator && activator->client && !Coop_IsStanding(activator)))
	{
		return;
	}
	for (i = 1; i <= game.maxclients; ++i)
	{
		if (Coop_IsStanding(&g_edicts[i]))
		{
			standing = true;
			break;
		}
	}
	if (!standing)
	{
		return;
	}
	self->count = 1;

	for (i = 1; i <= game.maxclients; ++i)
	{
		edict_t *ent = &g_edicts[i];
		edict_t *spot = NULL;

		if (!SquadMember(ent))
		{
			continue;
		}
		WaitIfExpired(ent);
		if (!ent->client->coop_rescue.awaiting_redeploy)
		{
			continue;
		}
		while ((spot = G_Find(spot, FOFS(targetname), self->target)) != NULL)
		{
			if (!strcmp(spot->classname, "info_notnull"))
			{
				Coop_RedeployAt(ent, spot);
				if (!ent->client->coop_rescue.awaiting_redeploy)
				{
					break;
				}
			}
		}
	}
}

void
SP_target_platoon_checkpoint(edict_t *ent)
{
	if (!Coop_RescueActive() || !ent->targetname || !ent->target)
	{
		G_FreeEdict(ent);
		return;
	}
	ent->use = platoon_checkpoint_use;
	ent->svflags = SVF_NOCLIENT;
}
