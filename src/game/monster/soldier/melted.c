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
 */

#include "../../header/local.h"
#include "soldier.h"

extern mmove_t soldier_move_death6;

#define MELTED_HUNT_SOUND "attic/hunt.wav"
#define MELTED_IMPACT_SOUND "attic/impact.wav"
#define MELTED_SWIPE_SOUND "attic/swipe.wav"
#define MELTED_DEATH_SOUND "attic/slag.wav"
#define MELTED_SIGHT_GRACE 0.25f
#define MELTED_QUIET_DURATION 2.25f
#define MELTED_NAV_RANGE 768.0f
#define MELTED_NAV_STEP 18.0f
#define MELTED_NAV_MASK (MASK_SOLID | CONTENTS_MONSTERCLIP)

/* The attic's waypoints form a tree. A node names its parent and stores its
 * depth, so the stalker can take turns around walls even after losing sight. */
void
SP_info_melted_path(edict_t *self)
{
	self->svflags = SVF_NOCLIENT;
}

static edict_t *
melted_parent(edict_t *node)
{
	if (!node->movetarget && node->target)
	{
		node->movetarget = G_Find(NULL, FOFS(targetname), node->target);
	}

	edict_t *parent = node->movetarget;
	return parent && parent->inuse && parent->count == node->count - 1 ? parent : NULL;
}

static edict_t *
melted_next_node(edict_t *from, edict_t *to)
{
	if (!from || !to || from == to)
	{
		return from;
	}

	/* A route into our own subtree starts at the child above the target. */
	edict_t *child = to;
	while (child && child->count > from->count)
	{
		edict_t *parent = melted_parent(child);
		if (parent == from)
		{
			return child;
		}
		child = parent;
	}

	return melted_parent(from);
}

static qboolean
melted_walkable(edict_t *self, vec3_t start, vec3_t end, qboolean fit_hull)
{
	vec3_t delta, from, to;
	VectorSubtract(end, start, delta);
	float length = hypotf(delta[0], delta[1]);
	if (length > MELTED_NAV_RANGE || fabsf(delta[2]) > length + MELTED_NAV_STEP)
	{
		return false;
	}

	VectorCopy(start, from);
	VectorCopy(end, to);
	/* Sweep above the floor to account for the front of the hull touching
	 * a rising ramp or shallow step before the origin reaches it. */
	from[2] += 1;
	to[2] += 1;
	float *mins = fit_hull ? self->mins : vec3_origin;
	float *maxs = fit_hull ? self->maxs : vec3_origin;
	trace_t tr = gi.trace(from, mins, maxs, to, self, MELTED_NAV_MASK);
	if (tr.startsolid || tr.fraction < 1)
	{
		from[2] += MELTED_NAV_STEP - 1;
		to[2] += MELTED_NAV_STEP - 1;
		tr = gi.trace(from, mins, maxs, to, self, MELTED_NAV_MASK);
		if (tr.startsolid || tr.fraction < 1)
		{
			return false;
		}
	}

	/* A clear sweep by itself can cross a drop, or see a shortcut from the
	 * upper deck to the lower floor. Require support near the whole route. */
	int samples = (int)ceilf(fmaxf(length, 1) / 24.0f);
	for (int i = 0; i <= samples; ++i)
	{
		VectorMA(start, (float)i / samples, delta, from);
		from[2] += self->mins[2] + MELTED_NAV_STEP;
		VectorCopy(from, to);
		to[2] -= 2 * MELTED_NAV_STEP;
		tr = gi.trace(from, vec3_origin, vec3_origin, to, self, MELTED_NAV_MASK);
		if (tr.startsolid || tr.fraction == 1 || tr.plane.normal[2] < 0.7f)
		{
			return false;
		}
	}

	return true;
}

static edict_t *
melted_nearest_node(edict_t *self, vec3_t origin, qboolean fit_hull)
{
	edict_t *node = NULL;
	edict_t *nearest = NULL;
	float best = MELTED_NAV_RANGE * MELTED_NAV_RANGE;
	vec3_t delta;

	while ((node = G_Find(node, FOFS(classname), "info_melted_path")) != NULL)
	{
		VectorSubtract(node->s.origin, origin, delta);
		float distance = DotProduct(delta, delta);
		if (distance < best && melted_walkable(self, origin, node->s.origin, fit_hull))
		{
			nearest = node;
			best = distance;
		}
	}

	return nearest;
}

static void
melted_update_hunt_sound(edict_t *self)
{
	if (!self->enemy || !self->enemy->inuse || self->enemy->health <= 0)
	{
		self->s.sound = 0;
		return;
	}

	/* Keep the resume time in the saved edict. Brief occlusions at a
	 * doorway get a grace period, and a clear view ends the silence. */
	if (visible(self, self->enemy))
	{
		self->fly_sound_debounce_time = level.time + MELTED_SIGHT_GRACE + MELTED_QUIET_DURATION;
	}

	float until_resume = self->fly_sound_debounce_time - level.time;
	if (until_resume > 0 && until_resume <= MELTED_QUIET_DURATION)
	{
		self->s.sound = 0;
	}
	else if (!self->s.sound)
	{
		self->s.sound = gi.soundindex(MELTED_HUNT_SOUND);
	}
}

static void
melted_chase(edict_t *self, float distance)
{
	qboolean attacking = ai_checkattack(self);
	melted_update_hunt_sound(self);
	if (attacking || !self->enemy)
	{
		return;
	}

	if (self->timestamp > level.time)
	{
		distance *= 0.25f;
	}

	vec3_t destination, direction;
	VectorCopy(self->enemy->s.origin, destination);
	destination[2] += self->enemy->mins[2] - self->mins[2];
	if (!self->enemy->groundentity)
	{
		/* Keep tracking a player who jumps between grounded positions. */
		vec3_t start, end;
		VectorCopy(self->enemy->s.origin, start);
		start[2] += self->enemy->mins[2] + 1;
		VectorCopy(start, end);
		end[2] -= 64;
		trace_t tr = gi.trace(start, vec3_origin, vec3_origin, end, self, MELTED_NAV_MASK);
		if (!tr.startsolid && tr.fraction < 1)
		{
			destination[2] = tr.endpos[2] - self->mins[2];
		}
	}

	qboolean direct = melted_walkable(self, self->s.origin, destination, true);
	if (!direct)
	{
		if (level.time >= self->last_move_time || !self->target_ent)
		{
			self->last_move_time = level.time + 0.3f;
			edict_t *from = melted_nearest_node(self, self->s.origin, true);
			edict_t *to = melted_nearest_node(self, destination, false);
			edict_t *next = melted_next_node(from, to);
			if (next && next != from &&
				melted_walkable(self, self->s.origin, next->s.origin, true))
			{
				self->target_ent = next;
			}
			else
			{
				self->target_ent = from;
			}
		}

		if (!self->target_ent)
		{
			ai_run(self, distance);
			return;
		}

		VectorCopy(self->target_ent->s.origin, destination);
	}

	VectorSubtract(destination, self->s.origin, direction);
	direction[2] = 0;
	float remaining = VectorLength(direction);
	if (remaining < 0.5f)
	{
		self->last_move_time = 0;
		return;
	}

	self->ideal_yaw = vectoyaw(direction);
	M_ChangeYaw(self);
	if (!M_walkmove(self, self->ideal_yaw, fminf(distance, remaining)))
	{
		edict_t *goal = self->goalentity;
		self->goalentity = direct ? self->enemy : self->target_ent;
		M_MoveToGoal(self, distance);
		self->goalentity = goal;
	}
}

static mframe_t melted_frames_stand[] = {
	{ai_stand, 0, NULL}, {ai_stand, 0, NULL}, {ai_stand, 0, NULL},
	{ai_stand, 0, NULL}, {ai_stand, 0, NULL}, {ai_stand, 0, NULL}
};
mmove_t melted_move_stand = {FRAME_stand101, FRAME_stand106, melted_frames_stand, NULL};

static mframe_t melted_frames_run[] = {
	{melted_chase, 23, NULL}, {melted_chase, 26, NULL}, {melted_chase, 24, NULL},
	{melted_chase, 27, NULL}, {melted_chase, 23, NULL}, {melted_chase, 26, NULL}
};
mmove_t melted_move_run = {FRAME_run03, FRAME_run08, melted_frames_run, NULL};

void
melted_stand(edict_t *self)
{
	self->monsterinfo.currentmove = &melted_move_stand;
	self->s.sound = 0;
	self->fly_sound_debounce_time = 0;
	self->target_ent = NULL;
}

void
melted_run(edict_t *self)
{
	self->monsterinfo.currentmove = &melted_move_run;
	melted_update_hunt_sound(self);
}

static void
melted_charge(edict_t *self, float distance)
{
	melted_update_hunt_sound(self);
	ai_charge(self, distance);
}

static void
melted_swipe(edict_t *self)
{
	vec3_t reach = {76, 0, 8};
	if (self->enemy && self->enemy->inuse && self->enemy->health > 0 && infront(self, self->enemy))
	{
		fire_hit(self, reach, 38, 65);
	}
}

static mframe_t melted_frames_melee[] = {
	{melted_charge, 7, NULL}, {melted_charge, 8, NULL}, {melted_charge, 8, NULL},
	{melted_charge, 5, melted_swipe}, {melted_charge, 0, NULL}, {melted_charge, 0, NULL},
	{melted_charge, 0, NULL}, {melted_charge, 0, NULL}, {melted_charge, 0, NULL}
};
mmove_t melted_move_melee = {FRAME_attak301, FRAME_attak309, melted_frames_melee, melted_run};

void
melted_melee(edict_t *self)
{
	self->monsterinfo.currentmove = &melted_move_melee;
	gi.sound(self, CHAN_VOICE, gi.soundindex(MELTED_SWIPE_SOUND), 1, ATTN_NORM, 0);
}

void
melted_pain(edict_t *self, edict_t *other, float kick, int damage)
{
	int mod = meansOfDeath & ~MOD_FRIENDLY_FIRE;
	if (mod == MOD_FLAME || mod == MOD_FLAME_SPLASH || level.time < self->touch_debounce_time)
	{
		return;
	}

	/* A burst gives a short opening. Continuous fire can't keep it pinned. */
	self->timestamp = level.time + 0.5f;
	self->touch_debounce_time = level.time + 1.25f;
	self->monsterinfo.attack_state = AS_STRAIGHT;
	melted_run(self);
	gi.sound(self, CHAN_VOICE, gi.soundindex(MELTED_IMPACT_SOUND), 1, ATTN_NORM, 0);
}

qboolean
melted_checkattack(edict_t *self)
{
	return self->timestamp <= level.time && M_CheckAttack(self);
}

void
melted_die(edict_t *self, edict_t *inflictor, edict_t *attacker, int damage, vec3_t point)
{
	self->deadflag = DEAD_DEAD;
	self->takedamage = DAMAGE_NO;
	self->s.sound = 0;
	self->monsterinfo.currentmove = &soldier_move_death6;
	gi.sound(self, CHAN_VOICE, gi.soundindex(MELTED_DEATH_SOUND), 1, ATTN_NORM, 0);
}

/* QUAKED monster_melted (0.3 0.1 0.1) (-16 -16 -24) (16 16 61) Ambush Trigger_Spawn */
void
SP_monster_melted(edict_t *self)
{
	if (deathmatch->value)
	{
		G_FreeEdict(self);
		return;
	}

	gi.soundindex(MELTED_HUNT_SOUND);
	gi.soundindex(MELTED_IMPACT_SOUND);
	gi.soundindex(MELTED_SWIPE_SOUND);
	gi.soundindex(MELTED_DEATH_SOUND);
	self->s.modelindex = gi.modelindex("models/monsters/melted/tris.md2");
	VectorSet(self->mins, -16, -16, -24);
	VectorSet(self->maxs, 16, 16, 61);
	self->viewheight = 50;
	self->movetype = MOVETYPE_STEP;
	self->solid = SOLID_BBOX;
	self->flags |= FL_FIRE_ONLY | FL_NO_KNOCKBACK;
	if (self->health <= 0)
	{
		self->health = 250;
	}
	self->mass = 260;
	self->yaw_speed = 45;
	self->pain = melted_pain;
	self->die = melted_die;
	self->monsterinfo.stand = melted_stand;
	self->monsterinfo.walk = melted_stand;
	self->monsterinfo.run = melted_run;
	self->monsterinfo.melee = melted_melee;
	self->monsterinfo.checkattack = melted_checkattack;
	self->monsterinfo.scale = MODEL_SCALE;
	melted_stand(self);
	gi.linkentity(self);
	walkmonster_start(self);
}
