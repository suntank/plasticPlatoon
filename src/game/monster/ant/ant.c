/*
 * Giant ant enemy for Plastic Platoon.
 *
 * This program is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License, version 2 or later.
 */
#include "../../header/local.h"
#include "../insect_gibs.h"
#include "../insect_sounds.h"

void ant_stand(edict_t *self);
void ant_walk(edict_t *self);
void ant_run(edict_t *self);
void ant_melee(edict_t *self);
void ant_dead(edict_t *self);

static insect_sound_t ant_sounds[] = {
	INSECT_SOUND("ant", "idle"),
	INSECT_SOUND("ant", "pain"),
	INSECT_SOUND("ant", "attack"),
	INSECT_SOUND("ant", "scuttle"),
	INSECT_SOUND("ant", "sight"),
};

extern mmove_t ant_move_walk, ant_move_run;

void
ant_idle(edict_t *self)
{
	if (!self->enemy || !self->enemy->inuse || self->enemy->health <= 0)
		InsectSound(self, &ant_sounds[INSECT_IDLE], CHAN_VOICE,
				0.65f, ATTN_IDLE);
}

void
ant_sight(edict_t *self, edict_t *other)
{
	(void)other;
	InsectSound(self, &ant_sounds[INSECT_SIGHT], CHAN_VOICE, 1, ATTN_NORM);
}

static void
ant_walk_step(edict_t *self, float dist)
{
	vec3_t before;
	VectorCopy(self->s.origin, before);
	ai_walk(self, dist);
	if (self->monsterinfo.currentmove == &ant_move_walk)
		InsectScuttle(self, before, &ant_sounds[INSECT_SCUTTLE], 0.55f);
}

static void
ant_run_step(edict_t *self, float dist)
{
	vec3_t before;
	VectorCopy(self->s.origin, before);
	ai_run(self, dist);
	if (self->monsterinfo.currentmove == &ant_move_run)
		InsectScuttle(self, before, &ant_sounds[INSECT_SCUTTLE], 0.55f);
}

static void
ant_bite(edict_t *self)
{
	vec3_t aim;

	/* Damage is applied at the closing mandibles, once per attack. */
	VectorSet(aim, MELEE_DISTANCE, 0, 0);
	fire_hit(self, aim, 20, 40);
}

static mframe_t ant_frames_stand[] = {
	{ai_stand, 0, NULL}, {ai_stand, 0, NULL},
	{ai_stand, 0, NULL}, {ai_stand, 0, NULL},
	{ai_stand, 0, NULL}, {ai_stand, 0, NULL},
	{ai_stand, 0, NULL}, {ai_stand, 0, NULL}
};
mmove_t ant_move_stand = {0, 7, ant_frames_stand, NULL};

static mframe_t ant_frames_walk[] = {
	{ant_walk_step, 4, NULL}, {ant_walk_step, 4, NULL}, {ant_walk_step, 4, NULL},
	{ant_walk_step, 4, NULL}, {ant_walk_step, 4, NULL}, {ant_walk_step, 4, NULL},
	{ant_walk_step, 4, NULL}, {ant_walk_step, 4, NULL}, {ant_walk_step, 4, NULL},
	{ant_walk_step, 4, NULL}, {ant_walk_step, 4, NULL}, {ant_walk_step, 4, NULL}
};
mmove_t ant_move_walk = {8, 19, ant_frames_walk, NULL};

static mframe_t ant_frames_run[] = {
	{ant_run_step, 12, NULL}, {ant_run_step, 12, NULL}, {ant_run_step, 12, NULL},
	{ant_run_step, 12, NULL}, {ant_run_step, 12, NULL}, {ant_run_step, 12, NULL},
	{ant_run_step, 12, NULL}, {ant_run_step, 12, NULL}, {ant_run_step, 12, NULL},
	{ant_run_step, 12, NULL}, {ant_run_step, 12, NULL}, {ant_run_step, 12, NULL}
};
mmove_t ant_move_run = {20, 31, ant_frames_run, NULL};

static mframe_t ant_frames_attack[] = {
	{ai_charge, 1, NULL}, {ai_charge, 1, NULL},
	{ai_charge, 2, NULL}, {ai_charge, 2, NULL},
	{ai_charge, 0, ant_bite}, {ai_charge, 0, NULL},
	{ai_charge, 0, NULL}, {ai_charge, 0, NULL}
};
mmove_t ant_move_attack = {32, 39, ant_frames_attack, ant_run};

static mframe_t ant_frames_pain[] = {
	{ai_move, 0, NULL}, {ai_move, 0, NULL},
	{ai_move, 0, NULL}, {ai_move, 0, NULL}
};
mmove_t ant_move_pain = {40, 43, ant_frames_pain, ant_run};

static mframe_t ant_frames_death[] = {
	{ai_move, 0, NULL}, {ai_move, 0, NULL}, {ai_move, 0, NULL},
	{ai_move, 0, NULL}, {ai_move, 0, NULL}, {ai_move, 0, NULL}
};
mmove_t ant_move_death = {44, 49, ant_frames_death, ant_dead};

void ant_stand(edict_t *self) { self->monsterinfo.currentmove = &ant_move_stand; }
void ant_walk(edict_t *self) { self->monsterinfo.currentmove = &ant_move_walk; }
void
ant_melee(edict_t *self)
{
	self->monsterinfo.currentmove = &ant_move_attack;
	/* Start the 0.8-second windup/bite clip with the existing attack. */
	InsectSound(self, &ant_sounds[INSECT_ATTACK], CHAN_WEAPON, 1, ATTN_NORM);
}

void
ant_run(edict_t *self)
{
	if (self->monsterinfo.aiflags & AI_STAND_GROUND)
		ant_stand(self);
	else
		self->monsterinfo.currentmove = &ant_move_run;
}

void
ant_pain(edict_t *self, edict_t *other, float kick, int damage)
{
	(void)other;
	(void)kick;
	(void)damage;
	if (level.time < self->pain_debounce_time)
		return;
	self->pain_debounce_time = level.time + 3;
	InsectSound(self, &ant_sounds[INSECT_PAIN], CHAN_VOICE, 1, ATTN_NORM);
	if (skill->value != SKILL_HARDPLUS)
		self->monsterinfo.currentmove = &ant_move_pain;
}

void
ant_dead(edict_t *self)
{
	self->maxs[2] = 0;
	self->movetype = MOVETYPE_TOSS;
	self->svflags |= SVF_DEADMONSTER;
	self->nextthink = 0;
	gi.linkentity(self);
}

void
ant_die(edict_t *self, edict_t *inflictor, edict_t *attacker,
		int damage, vec3_t point)
{
	(void)inflictor;
	(void)attacker;
	(void)point;
	if (self->health <= self->gib_health)
	{
		InsectGib(self, damage, false);
		return;
	}
	if (self->deadflag == DEAD_DEAD)
		return;
	self->deadflag = DEAD_DEAD;
	self->takedamage = DAMAGE_YES;
	self->monsterinfo.currentmove = &ant_move_death;
}

/* QUAKED monster_ant (1 .5 0) (-24 -24 -24) (24 24 16) Ambush Trigger_Spawn Sight */
void
SP_monster_ant(edict_t *self)
{
	if (deathmatch->value)
	{
		G_FreeEdict(self);
		return;
	}

	self->movetype = MOVETYPE_STEP;
	self->solid = SOLID_BBOX;
	InsectPrecacheGibs(false);
	InsectPrecacheSounds(ant_sounds, sizeof(ant_sounds) / sizeof(ant_sounds[0]));
	self->s.modelindex = gi.modelindex("models/monsters/ant/tris.md2");
	VectorSet(self->mins, -24, -24, -24);
	VectorSet(self->maxs, 24, 24, 16);
	self->health = 120;
	self->gib_health = -100;
	self->mass = 200;
	self->pain = ant_pain;
	self->die = ant_die;
	self->monsterinfo.stand = ant_stand;
	self->monsterinfo.idle = ant_idle;
	self->monsterinfo.search = ant_idle;
	self->monsterinfo.sight = ant_sight;
	self->monsterinfo.walk = ant_walk;
	self->monsterinfo.run = ant_run;
	self->monsterinfo.melee = ant_melee;
	gi.linkentity(self);
	self->monsterinfo.currentmove = &ant_move_stand;
	self->monsterinfo.scale = 1;
	walkmonster_start(self);
}
