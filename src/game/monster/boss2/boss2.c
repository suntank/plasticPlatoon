/*
 * Copyright (C) 1997-2001 Id Software, Inc.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or (at
 * your option) any later version.
 *
 * This program is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
 *
 * See the GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
 * 02111-1307, USA.
 *
 * =======================================================================
 *
 * Boss 2 aka Hornet. Found in biggun and inner hangar.
 *
 * =======================================================================
 */

#include "../../header/local.h"
#include "boss2.h"

static void Boss2CrashExplode(edict_t *self);
static void Boss2SpawnCrashExplosion(edict_t *self, float forward_bias,
		float right_bias, float up_bias, float spread);
static void boss2_begin_crash_burst(edict_t *self);
static void boss2_crash_burst_think(edict_t *self);
static void boss2_crash_fall_think(edict_t *self);
static void boss2_ai_run(edict_t *self, float dist);
static qboolean boss2_has_visible_enemy(edict_t *self);
static float boss2_horizontal_range(edict_t *self, edict_t *other);

qboolean infront(edict_t *self, edict_t *other);

static int sound_pain1;
static int sound_pain2;
static int sound_pain3;
static int sound_death;
static int sound_search1;

static qboolean
boss2_has_visible_enemy(edict_t *self)
{
	if (!self || !self->enemy || !self->enemy->inuse || (self->enemy->health <= 0))
	{
		return false;
	}

	return visible(self, self->enemy);
}

static float
boss2_horizontal_range(edict_t *self, edict_t *other)
{
	vec3_t delta;

	if (!self || !other)
	{
		return 0.0f;
	}

	VectorSubtract(other->s.origin, self->s.origin, delta);
	delta[2] = 0.0f;
	return VectorLength(delta);
}

static void
boss2_ai_run(edict_t *self, float dist)
{
	float horizontal_range;
	float yaw_offset;

	if (!self || !self->enemy || !self->enemy->inuse || (self->enemy->health <= 0))
	{
		ai_run(self, dist);
		return;
	}

	if (!boss2_has_visible_enemy(self))
	{
		ai_run(self, dist);
		return;
	}

	if (ai_checkattack(self))
	{
		return;
	}

	horizontal_range = boss2_horizontal_range(self, self->enemy);
	VectorSubtract(self->enemy->s.origin, self->s.origin, self->move_origin);
	self->ideal_yaw = vectoyaw(self->move_origin);
	M_ChangeYaw(self);

	VectorCopy(self->enemy->s.origin, self->monsterinfo.last_sighting);
	self->monsterinfo.trail_time = level.time;
	self->monsterinfo.aiflags &= ~AI_LOST_SIGHT;

	if (horizontal_range < 220.0f)
	{
		yaw_offset = (self->monsterinfo.lefty ? 140.0f : -140.0f) + (crandom() * 18.0f);

		if (!M_walkmove(self, self->ideal_yaw + yaw_offset, dist))
		{
			self->monsterinfo.lefty = 1 - self->monsterinfo.lefty;
			M_walkmove(self, self->ideal_yaw + 180.0f + (crandom() * 24.0f), dist);
		}
		return;
	}

	if (horizontal_range > 620.0f)
	{
		M_walkmove(self, self->ideal_yaw + (crandom() * 14.0f), dist);
		return;
	}

	if ((horizontal_range > 300.0f) && (horizontal_range < 540.0f) && (random() < 0.7f))
	{
		yaw_offset = (self->monsterinfo.lefty ? 90.0f : -90.0f) + (crandom() * 22.0f);

		if (!M_walkmove(self, self->ideal_yaw + yaw_offset, dist))
		{
			self->monsterinfo.lefty = 1 - self->monsterinfo.lefty;
			M_walkmove(self, self->ideal_yaw - yaw_offset, dist);
		}

		if (random() < 0.15f)
		{
			self->monsterinfo.lefty = 1 - self->monsterinfo.lefty;
		}

		return;
	}

	if (random() < 0.35f)
	{
		yaw_offset = (self->monsterinfo.lefty ? 55.0f : -55.0f) + (crandom() * 20.0f);
		M_walkmove(self, self->ideal_yaw + yaw_offset, dist);
		return;
	}

	M_walkmove(self, self->ideal_yaw + (crandom() * 10.0f), dist * 0.65f);
}

static void
Boss2SpawnCrashExplosion(edict_t *self, float forward_bias,
		float right_bias, float up_bias, float spread)
{
	vec3_t org;
	vec3_t forward;
	vec3_t right;

	if (!self)
	{
		return;
	}

	VectorCopy(self->s.origin, org);
	AngleVectors(self->s.angles, forward, right, NULL);
	VectorMA(org, forward_bias + (crandom() * spread), forward, org);
	VectorMA(org, right_bias + (crandom() * spread), right, org);
	org[2] += up_bias + (crandom() * spread * 0.35f);

	gi.WriteByte(svc_temp_entity);
	gi.WriteByte(TE_EXPLOSION1);
	gi.WritePosition(org);
	gi.multicast(self->s.origin, MULTICAST_PVS);
}

static void
Boss2CrashExplode(edict_t *self)
{
	if (!self)
	{
		return;
	}

	self->s.sound = 0;
	self->s.modelindex2 = 0;

	Boss2SpawnCrashExplosion(self, 0.0f, 0.0f, 24.0f, 18.0f);

	/*
	for (n = 0; n < 4; n++)
	{
		ThrowGib(self, "models/objects/gibs/sm_meat/tris.md2", 500, GIB_ORGANIC);
	}

	for (n = 0; n < 8; n++)
	{
		ThrowGib(self, "models/objects/gibs/sm_metal/tris.md2", 500, GIB_METALLIC);
	}

	ThrowGib(self, "models/objects/gibs/chest/tris.md2", 500, GIB_ORGANIC);
	ThrowHead(self, "models/objects/gibs/gear/tris.md2", 500, GIB_METALLIC);
	*/

	G_FreeEdict(self);
}

static void
boss2_begin_crash_burst(edict_t *self)
{
	if (!self)
	{
		return;
	}

	self->s.sound = 0;
	self->s.modelindex2 = 0;
	self->solid = SOLID_NOT;
	self->touch = NULL;
	self->movetype = MOVETYPE_NONE;
	VectorClear(self->velocity);
	VectorClear(self->avelocity);
	self->count = 0;
	self->timestamp = level.time + 0.35f;
	self->think = boss2_crash_burst_think;
	self->nextthink = level.time + FRAMETIME;
	gi.linkentity(self);
}

static void
boss2_crash_burst_think(edict_t *self)
{
	if (!self)
	{
		return;
	}

	Boss2SpawnCrashExplosion(self, 16.0f, 0.0f, 20.0f, 24.0f);
	Boss2SpawnCrashExplosion(self, -8.0f, 22.0f, 14.0f, 18.0f);

	if ((self->count & 1) == 0)
	{
		Boss2SpawnCrashExplosion(self, -8.0f, -22.0f, 12.0f, 18.0f);
	}

	self->count++;

	if ((self->count >= 4) || (level.time >= self->timestamp))
	{
		Boss2CrashExplode(self);
		return;
	}

	self->nextthink = level.time + FRAMETIME;
}

static void
boss2_crash_fall_think(edict_t *self)
{
	if (!self)
	{
		return;
	}

	if (level.time >= self->delay)
	{
		Boss2SpawnCrashExplosion(self, -10.0f, 0.0f, 26.0f, 14.0f);

		if (random() < 0.4f)
		{
			Boss2SpawnCrashExplosion(self, 8.0f, 0.0f, 18.0f, 10.0f);
		}

		self->delay = level.time + 0.15f;
	}

	if (self->groundentity || (level.time >= self->wait))
	{
		boss2_begin_crash_burst(self);
		return;
	}

	self->nextthink = level.time + FRAMETIME;
}

void
boss2_search(edict_t *self)
{
	if (!self)
	{
		return;
	}

	if (random() < 0.5)
	{
		gi.sound(self, CHAN_VOICE, sound_search1, 1, ATTN_NONE, 0);
	}
}

void boss2_run(edict_t *self);
void boss2_stand(edict_t *self);
void boss2_dead(edict_t *self);
void boss2_attack(edict_t *self);
void boss2_attack_mg(edict_t *self);
void boss2_reattack_mg(edict_t *self);
void boss2_die(edict_t *self, edict_t *inflictor, edict_t *attacker,
		int damage, vec3_t point);

void
Boss2Rocket(edict_t *self)
{
	vec3_t forward, right;
	vec3_t start;
	vec3_t dir;
	vec3_t vec;

	if (!self)
	{
		return;
	}

	AngleVectors(self->s.angles, forward, right, NULL);

	G_ProjectSource(self->s.origin, monster_flash_offset[MZ2_BOSS2_ROCKET_1],
			forward, right, start);
	VectorCopy(self->enemy->s.origin, vec);
	vec[2] += self->enemy->viewheight;
	VectorSubtract(vec, start, dir);
	VectorNormalize(dir);
	monster_fire_rocket(self, start, dir, 50, 500, MZ2_BOSS2_ROCKET_1);

	G_ProjectSource(self->s.origin, monster_flash_offset[MZ2_BOSS2_ROCKET_2],
			forward, right, start);
	VectorCopy(self->enemy->s.origin, vec);
	vec[2] += self->enemy->viewheight;
	VectorSubtract(vec, start, dir);
	VectorNormalize(dir);
	monster_fire_rocket(self, start, dir, 50, 500, MZ2_BOSS2_ROCKET_2);

	G_ProjectSource(self->s.origin, monster_flash_offset[MZ2_BOSS2_ROCKET_3],
			forward, right, start);
	VectorCopy(self->enemy->s.origin, vec);
	vec[2] += self->enemy->viewheight;
	VectorSubtract(vec, start, dir);
	VectorNormalize(dir);
	monster_fire_rocket(self, start, dir, 50, 500, MZ2_BOSS2_ROCKET_3);

	G_ProjectSource(self->s.origin, monster_flash_offset[MZ2_BOSS2_ROCKET_4],
			forward, right, start);
	VectorCopy(self->enemy->s.origin, vec);
	vec[2] += self->enemy->viewheight;
	VectorSubtract(vec, start, dir);
	VectorNormalize(dir);
	monster_fire_rocket(self, start, dir, 50, 500, MZ2_BOSS2_ROCKET_4);
}

void
boss2_firebullet_right(edict_t *self)
{
	vec3_t forward, right, target;
	vec3_t start;

	if (!self)
	{
		return;
	}

	AngleVectors(self->s.angles, forward, right, NULL);
	G_ProjectSource(self->s.origin, monster_flash_offset[MZ2_BOSS2_MACHINEGUN_R1],
			forward, right, start);

	VectorMA(self->enemy->s.origin, -0.2, self->enemy->velocity, target);
	target[2] += self->enemy->viewheight;
	VectorSubtract(target, start, forward);
	VectorNormalize(forward);

	monster_fire_bullet(self, start, forward,
			6, 4, DEFAULT_BULLET_HSPREAD, DEFAULT_BULLET_VSPREAD,
			MZ2_BOSS2_MACHINEGUN_R1);
}

void
boss2_firebullet_left(edict_t *self)
{
	vec3_t forward, right, target;
	vec3_t start;

	if (!self)
	{
		return;
	}

	AngleVectors(self->s.angles, forward, right, NULL);
	G_ProjectSource(self->s.origin, monster_flash_offset[MZ2_BOSS2_MACHINEGUN_L1],
			forward, right, start);

	VectorMA(self->enemy->s.origin, -0.2, self->enemy->velocity, target);

	target[2] += self->enemy->viewheight;
	VectorSubtract(target, start, forward);
	VectorNormalize(forward);

	monster_fire_bullet(self, start, forward, 6, 4,
			DEFAULT_BULLET_HSPREAD, DEFAULT_BULLET_VSPREAD,
			MZ2_BOSS2_MACHINEGUN_L1);
}

void
Boss2MachineGun(edict_t *self)
{
	if (!self)
	{
		return;
	}

	boss2_firebullet_left(self);
	boss2_firebullet_right(self);
}

static mframe_t boss2_frames_stand[] = {
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL}
};
mmove_t boss2_move_stand =
{
	FRAME_stand30,
   	FRAME_stand50,
	boss2_frames_stand,
	NULL
};

static mframe_t boss2_frames_fidget[] = {
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL},
	{ai_stand, 0, NULL}
};
mmove_t boss2_move_fidget =
{
	FRAME_stand1,
	FRAME_stand30,
	boss2_frames_fidget,
	NULL
};

static mframe_t boss2_frames_walk[] = {
	{ai_walk, 8, NULL},
	{ai_walk, 8, NULL},
	{ai_walk, 8, NULL},
	{ai_walk, 8, NULL},
	{ai_walk, 8, NULL},
	{ai_walk, 8, NULL},
	{ai_walk, 8, NULL},
	{ai_walk, 8, NULL},
	{ai_walk, 8, NULL},
	{ai_walk, 8, NULL},
	{ai_walk, 8, NULL},
	{ai_walk, 8, NULL},
	{ai_walk, 8, NULL},
	{ai_walk, 8, NULL},
	{ai_walk, 8, NULL},
	{ai_walk, 8, NULL},
	{ai_walk, 8, NULL},
	{ai_walk, 8, NULL},
	{ai_walk, 8, NULL},
	{ai_walk, 8, NULL}
};

mmove_t boss2_move_walk = {
	FRAME_walk1,
	FRAME_walk20,
	boss2_frames_walk,
	NULL
};

static mframe_t boss2_frames_run[] = {
	{boss2_ai_run, 8, NULL},
	{boss2_ai_run, 8, NULL},
	{boss2_ai_run, 8, NULL},
	{boss2_ai_run, 8, NULL},
	{boss2_ai_run, 8, NULL},
	{boss2_ai_run, 8, NULL},
	{boss2_ai_run, 8, NULL},
	{boss2_ai_run, 8, NULL},
	{boss2_ai_run, 8, NULL},
	{boss2_ai_run, 8, NULL},
	{boss2_ai_run, 8, NULL},
	{boss2_ai_run, 8, NULL},
	{boss2_ai_run, 8, NULL},
	{boss2_ai_run, 8, NULL},
	{boss2_ai_run, 8, NULL},
	{boss2_ai_run, 8, NULL},
	{boss2_ai_run, 8, NULL},
	{boss2_ai_run, 8, NULL},
	{boss2_ai_run, 8, NULL},
	{boss2_ai_run, 8, NULL}
};

mmove_t boss2_move_run = {
	FRAME_walk1,
	FRAME_walk20,
	boss2_frames_run,
	NULL};

static mframe_t boss2_frames_attack_pre_mg[] = {
	{ai_charge, 1, NULL},
	{ai_charge, 1, NULL},
	{ai_charge, 1, NULL},
	{ai_charge, 1, NULL},
	{ai_charge, 1, NULL},
	{ai_charge, 1, NULL},
	{ai_charge, 1, NULL},
	{ai_charge, 1, NULL},
	{ai_charge, 1, boss2_attack_mg}
};

mmove_t boss2_move_attack_pre_mg =
{
	FRAME_attack1,
	FRAME_attack9,
	boss2_frames_attack_pre_mg,
	NULL
};

/* Loop this */
static mframe_t boss2_frames_attack_mg[] = {
	{ai_charge, 1, Boss2MachineGun},
	{ai_charge, 1, Boss2MachineGun},
	{ai_charge, 1, Boss2MachineGun},
	{ai_charge, 1, Boss2MachineGun},
	{ai_charge, 1, Boss2MachineGun},
	{ai_charge, 1, boss2_reattack_mg}
};

mmove_t boss2_move_attack_mg =
{
	FRAME_attack10,
	FRAME_attack15,
	boss2_frames_attack_mg,
	NULL
};

static mframe_t boss2_frames_attack_post_mg[] = {
	{ai_charge, 1, NULL},
	{ai_charge, 1, NULL},
	{ai_charge, 1, NULL},
	{ai_charge, 1, NULL}
};

mmove_t boss2_move_attack_post_mg =
{
	FRAME_attack16,
	FRAME_attack19,
	boss2_frames_attack_post_mg,
	boss2_run
};

static mframe_t boss2_frames_attack_rocket[] = {
	{ai_charge, 1, NULL},
	{ai_charge, 1, NULL},
	{ai_charge, 1, NULL},
	{ai_charge, 1, NULL},
	{ai_charge, 1, NULL},
	{ai_charge, 1, NULL},
	{ai_charge, 1, NULL},
	{ai_charge, 1, NULL},
	{ai_charge, 1, NULL},
	{ai_charge, 1, NULL},
	{ai_charge, 1, NULL},
	{ai_charge, 1, NULL},
	{ai_move, -20, Boss2Rocket},
	{ai_charge, 1, NULL},
	{ai_charge, 1, NULL},
	{ai_charge, 1, NULL},
	{ai_charge, 1, NULL},
	{ai_charge, 1, NULL},
	{ai_charge, 1, NULL},
	{ai_charge, 1, NULL},
	{ai_charge, 1, NULL}
};

mmove_t boss2_move_attack_rocket =
{
	FRAME_attack20,
   	FRAME_attack40,
	boss2_frames_attack_rocket,
	boss2_run
};

static mframe_t boss2_frames_pain_heavy[] = {
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL}
};

mmove_t boss2_move_pain_heavy =
{
	FRAME_pain2,
	FRAME_pain19,
	boss2_frames_pain_heavy,
	boss2_run};

static mframe_t boss2_frames_pain_light[] = {
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL}
};

mmove_t boss2_move_pain_light =
{
	FRAME_pain20,
   	FRAME_pain23,
   	boss2_frames_pain_light,
   	boss2_run
};

static mframe_t boss2_frames_death[] = {
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL}
};

mmove_t boss2_move_death =
{
	FRAME_death2,
	FRAME_death10,
	boss2_frames_death,
	boss2_dead
};

static mframe_t boss2_frames_crash_wait[] = {
	{ai_move, 0, NULL}
};

mmove_t boss2_move_crash_wait =
{
	FRAME_death10,
	FRAME_death10,
	boss2_frames_crash_wait,
	NULL
};

void
boss2_stand(edict_t *self)
{
	if (!self)
	{
		return;
	}

	self->monsterinfo.currentmove = &boss2_move_stand;
}

void
boss2_run(edict_t *self)
{
	if (!self)
	{
		return;
	}

	if (self->monsterinfo.aiflags & AI_STAND_GROUND)
	{
		self->monsterinfo.currentmove = &boss2_move_stand;
	}
	else
	{
		self->monsterinfo.currentmove = &boss2_move_run;
	}
}

void
boss2_walk(edict_t *self)
{
	if (!self)
	{
		return;
	}

	self->monsterinfo.currentmove = &boss2_move_walk;
}

void
boss2_attack(edict_t *self)
{
	vec3_t vec;
	float range;

	if (!self)
	{
		return;
	}

	VectorSubtract(self->enemy->s.origin, self->s.origin, vec);
	range = VectorLength(vec);

	if (range <= 125)
	{
		self->monsterinfo.currentmove = &boss2_move_attack_pre_mg;
	}
	else
	{
		if (random() <= 0.6)
		{
			self->monsterinfo.currentmove = &boss2_move_attack_pre_mg;
		}
		else
		{
			self->monsterinfo.currentmove = &boss2_move_attack_rocket;
		}
	}
}

void
boss2_attack_mg(edict_t *self)
{
	if (!self)
	{
		return;
	}

	self->monsterinfo.currentmove = &boss2_move_attack_mg;
}

void
boss2_reattack_mg(edict_t *self)
{
	if (!self)
	{
		return;
	}

	if (infront(self, self->enemy))
	{
		if (random() <= 0.7)
		{
			self->monsterinfo.currentmove = &boss2_move_attack_mg;
		}
		else
		{
			self->monsterinfo.currentmove = &boss2_move_attack_post_mg;
		}
	}
	else
	{
		self->monsterinfo.currentmove = &boss2_move_attack_post_mg;
	}
}

void
boss2_pain(edict_t *self, edict_t *other /* unused */,
	   	float kick /* unused */, int damage)
{
	if (!self)
	{
		return;
	}

	if (self->health < (self->max_health / 2))
	{
		self->s.skinnum = 1;
	}

	if (level.time < self->pain_debounce_time)
	{
		return;
	}

	self->pain_debounce_time = level.time + 3;

	/* American wanted these at no attenuation */
	if (damage < 10)
	{
		gi.sound(self, CHAN_VOICE, sound_pain3, 1, ATTN_NONE, 0);
		self->monsterinfo.currentmove = &boss2_move_pain_light;
	}
	else if (damage < 30)
	{
		gi.sound(self, CHAN_VOICE, sound_pain1, 1, ATTN_NONE, 0);
		self->monsterinfo.currentmove = &boss2_move_pain_light;
	}
	else
	{
		gi.sound(self, CHAN_VOICE, sound_pain2, 1, ATTN_NONE, 0);
		self->monsterinfo.currentmove = &boss2_move_pain_heavy;
	}
}

void
boss2_dead(edict_t *self)
{
	if (!self)
	{
		return;
	}

	boss2_begin_crash_burst(self);
}

void
boss2_die(edict_t *self, edict_t *inflictor /* unused */, edict_t *attacker /* unused */,
		int damage /* unused */, vec3_t point /* unused */)
{
	if (!self)
	{
		return;
	}

	if (self->deadflag == DEAD_DEAD)
	{
		return;
	}

	gi.sound(self, CHAN_VOICE, sound_death, 1, ATTN_NONE, 0);
	self->deadflag = DEAD_DEAD;
	self->takedamage = DAMAGE_NO;
	self->s.sound = 0;
	self->s.frame = FRAME_death10;
	self->movetype = MOVETYPE_TOSS;
	self->svflags |= SVF_DEADMONSTER;
	self->delay = level.time + 0.05f;
	self->wait = level.time + 1.5f;
	self->velocity[2] -= 200.0f;
	VectorClear(self->avelocity);
	self->think = boss2_crash_fall_think;
	self->nextthink = level.time + FRAMETIME;
	gi.linkentity(self);
}

qboolean
Boss2_CheckAttack(edict_t *self)
{
	vec3_t spot1, spot2;
	vec3_t temp;
	float chance;
	trace_t tr;
	int enemy_range;
	float enemy_yaw;

	if (!self)
	{
		return false;
	}

	if (self->enemy->health > 0)
	{
		/* see if any entities are in the way of the shot */
		VectorCopy(self->s.origin, spot1);
		spot1[2] += self->viewheight;
		VectorCopy(self->enemy->s.origin, spot2);
		spot2[2] += self->enemy->viewheight;

		tr = gi.trace( spot1, NULL, NULL, spot2, self,
				CONTENTS_SOLID | CONTENTS_MONSTER | CONTENTS_SLIME |
				CONTENTS_LAVA);

		/* do we have a clear shot? */
		if (tr.ent != self->enemy)
		{
			return false;
		}
	}

	enemy_range = range(self, self->enemy);
	VectorSubtract(self->enemy->s.origin, self->s.origin, temp);
	enemy_yaw = vectoyaw(temp);

	self->ideal_yaw = enemy_yaw;

	/* melee attack */
	if (enemy_range == RANGE_MELEE)
	{
		if (self->monsterinfo.melee)
		{
			self->monsterinfo.attack_state = AS_MELEE;
		}
		else
		{
			self->monsterinfo.attack_state = AS_MISSILE;
		}

		return true;
	}

	/* missile attack */
	if (!self->monsterinfo.attack)
	{
		return false;
	}

	if (level.time < self->monsterinfo.attack_finished)
	{
		return false;
	}

	if (enemy_range == RANGE_FAR)
	{
		return false;
	}

	if (self->monsterinfo.aiflags & AI_STAND_GROUND)
	{
		chance = 0.4;
	}
	else if (enemy_range == RANGE_NEAR)
	{
		chance = 0.8;
	}
	else if (enemy_range == RANGE_MID)
	{
		chance = 0.8;
	}
	else
	{
		return false;
	}

	if (random() < chance)
	{
		self->monsterinfo.attack_state = AS_MISSILE;
		self->monsterinfo.attack_finished = level.time + 2 * random();
		return true;
	}

	if (self->flags & FL_FLY)
	{
		if (random() < 0.3)
		{
			self->monsterinfo.attack_state = AS_SLIDING;
		}
		else
		{
			self->monsterinfo.attack_state = AS_STRAIGHT;
		}
	}

	return false;
}

/*
 * QUAKED monster_boss2 (1 .5 0) (-56 -56 0) (56 56 80) Ambush Trigger_Spawn Sight
 */
void
SP_monster_boss2(edict_t *self)
{
	if (!self)
	{
		return;
	}

	if (deathmatch->value)
	{
		G_FreeEdict(self);
		return;
	}

	sound_pain1 = gi.soundindex("bosshovr/bhvpain1.wav");
	sound_pain2 = gi.soundindex("bosshovr/bhvpain2.wav");
	sound_pain3 = gi.soundindex("bosshovr/bhvpain3.wav");
	sound_death = gi.soundindex("bosshovr/bhvdeth1.wav");
	sound_search1 = gi.soundindex("bosshovr/bhvunqv1.wav");

	self->s.sound = gi.soundindex("bosshovr/bhvengn1.wav");

	self->movetype = MOVETYPE_STEP;
	self->solid = SOLID_BBOX;
	self->s.modelindex = gi.modelindex("models/monsters/boss2/tris.md2");
	self->s.modelindex2 = gi.modelindex("models/monsters/boss2/propeller.md2");
	VectorSet(self->mins, -56, -56, 0);
	VectorSet(self->maxs, 56, 56, 80);
	VectorCopy(self->s.origin, self->pos1);
	VectorCopy(self->s.origin, self->pos2);
	self->wait = level.time;
	self->monsterinfo.lefty = randk() & 1;

	self->health = 2000;
	self->gib_health = -200;
	self->mass = 1000;

	self->flags |= FL_IMMUNE_LASER;

	self->pain = boss2_pain;
	self->die = boss2_die;

	self->monsterinfo.stand = boss2_stand;
	self->monsterinfo.walk = boss2_walk;
	self->monsterinfo.run = boss2_run;
	self->monsterinfo.attack = boss2_attack;
	self->monsterinfo.search = boss2_search;
	self->monsterinfo.checkattack = Boss2_CheckAttack;
	gi.linkentity(self);

	self->monsterinfo.currentmove = &boss2_move_stand;
	self->monsterinfo.scale = MODEL_SCALE;

	flymonster_start(self);
}
