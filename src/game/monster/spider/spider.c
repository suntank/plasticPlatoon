/*
 * Giant spider enemy for Plastic Platoon.
 *
 * This program is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License, version 2 or later.
 */
#include "../../header/local.h"
#include "../insect_gibs.h"

void spider_stand(edict_t *self);
void spider_walk(edict_t *self);
void spider_run(edict_t *self);
void spider_melee(edict_t *self);
void spider_dead(edict_t *self);

static void
spider_bite(edict_t *self)
{
	vec3_t aim;

	/* Damage is applied at the closing mandibles, once per attack. */
	VectorSet(aim, MELEE_DISTANCE, 0, 0);
	fire_hit(self, aim, 32, 55);
}

static mframe_t spider_frames_stand[] = {
	{ai_stand, 0, NULL}, {ai_stand, 0, NULL},
	{ai_stand, 0, NULL}, {ai_stand, 0, NULL},
	{ai_stand, 0, NULL}, {ai_stand, 0, NULL},
	{ai_stand, 0, NULL}, {ai_stand, 0, NULL}
};
mmove_t spider_move_stand = {0, 7, spider_frames_stand, NULL};

static mframe_t spider_frames_walk[] = {
	{ai_walk, 4, NULL}, {ai_walk, 4, NULL}, {ai_walk, 4, NULL},
	{ai_walk, 4, NULL}, {ai_walk, 4, NULL}, {ai_walk, 4, NULL},
	{ai_walk, 4, NULL}, {ai_walk, 4, NULL}, {ai_walk, 4, NULL},
	{ai_walk, 4, NULL}, {ai_walk, 4, NULL}, {ai_walk, 4, NULL}
};
mmove_t spider_move_walk = {8, 19, spider_frames_walk, NULL};

static mframe_t spider_frames_run[] = {
	{ai_run, 12, NULL}, {ai_run, 12, NULL}, {ai_run, 12, NULL},
	{ai_run, 12, NULL}, {ai_run, 12, NULL}, {ai_run, 12, NULL},
	{ai_run, 12, NULL}, {ai_run, 12, NULL}, {ai_run, 12, NULL},
	{ai_run, 12, NULL}, {ai_run, 12, NULL}, {ai_run, 12, NULL}
};
mmove_t spider_move_run = {20, 31, spider_frames_run, NULL};

static mframe_t spider_frames_attack[] = {
	{ai_charge, 1, NULL}, {ai_charge, 1, NULL},
	{ai_charge, 2, NULL}, {ai_charge, 2, NULL},
	{ai_charge, 0, spider_bite}, {ai_charge, 0, NULL},
	{ai_charge, 0, NULL}, {ai_charge, 0, NULL}
};
mmove_t spider_move_attack = {32, 39, spider_frames_attack, spider_run};

static mframe_t spider_frames_pain[] = {
	{ai_move, 0, NULL}, {ai_move, 0, NULL},
	{ai_move, 0, NULL}, {ai_move, 0, NULL}
};
mmove_t spider_move_pain = {40, 43, spider_frames_pain, spider_run};

static mframe_t spider_frames_death[] = {
	{ai_move, 0, NULL}, {ai_move, 0, NULL}, {ai_move, 0, NULL},
	{ai_move, 0, NULL}, {ai_move, 0, NULL}, {ai_move, 0, NULL}
};
mmove_t spider_move_death = {44, 49, spider_frames_death, spider_dead};

void spider_stand(edict_t *self) { self->monsterinfo.currentmove = &spider_move_stand; }
void spider_walk(edict_t *self) { self->monsterinfo.currentmove = &spider_move_walk; }
void spider_melee(edict_t *self) { self->monsterinfo.currentmove = &spider_move_attack; }

void
spider_run(edict_t *self)
{
	if (self->monsterinfo.aiflags & AI_STAND_GROUND)
		spider_stand(self);
	else
		self->monsterinfo.currentmove = &spider_move_run;
}

void
spider_pain(edict_t *self, edict_t *other, float kick, int damage)
{
	(void)other;
	(void)kick;
	(void)damage;
	if (level.time < self->pain_debounce_time)
		return;
	self->pain_debounce_time = level.time + 3;
	if (skill->value != SKILL_HARDPLUS)
		self->monsterinfo.currentmove = &spider_move_pain;
}

void
spider_dead(edict_t *self)
{
	self->maxs[2] = 0;
	self->movetype = MOVETYPE_TOSS;
	self->svflags |= SVF_DEADMONSTER;
	self->nextthink = 0;
	gi.linkentity(self);
}

void
spider_die(edict_t *self, edict_t *inflictor, edict_t *attacker,
		int damage, vec3_t point)
{
	(void)inflictor;
	(void)attacker;
	(void)point;
	if (self->health <= self->gib_health)
	{
		InsectGib(self, damage, true);
		return;
	}
	if (self->deadflag == DEAD_DEAD)
		return;
	self->deadflag = DEAD_DEAD;
	self->takedamage = DAMAGE_YES;
	self->monsterinfo.currentmove = &spider_move_death;
}

/* QUAKED monster_spider (1 .5 0) (-32 -32 -24) (32 32 24) Ambush Trigger_Spawn Sight */
void
SP_monster_spider(edict_t *self)
{
	if (deathmatch->value)
	{
		G_FreeEdict(self);
		return;
	}

	self->movetype = MOVETYPE_STEP;
	self->solid = SOLID_BBOX;
	InsectPrecacheGibs(true);
	self->s.modelindex = gi.modelindex("models/monsters/spider/tris.md2");
	VectorSet(self->mins, -32, -32, -24);
	VectorSet(self->maxs, 32, 32, 24);
	self->health = 300;
	self->gib_health = -120;
	self->mass = 350;
	self->pain = spider_pain;
	self->die = spider_die;
	self->monsterinfo.stand = spider_stand;
	self->monsterinfo.walk = spider_walk;
	self->monsterinfo.run = spider_run;
	self->monsterinfo.melee = spider_melee;
	gi.linkentity(self);
	self->monsterinfo.currentmove = &spider_move_stand;
	self->monsterinfo.scale = 1;
	walkmonster_start(self);
}
