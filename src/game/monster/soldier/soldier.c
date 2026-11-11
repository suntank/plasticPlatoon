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
 * Soldier aka "Guard". This is the most complex enemy in Quake 2, since
 * it uses all AI features (dodging, sight, crouching, etc) and comes
 * in a myriad of variants.
 *
 * =======================================================================
 */

#include "../../header/local.h"
#include "soldier.h"
#include "../../../common/header/soldier_dimensions.h"

static int sound_idle;

/* Shared by every soldier type, including the heavy and rocket specialists. */
enum soldier_alert_phrase {
	SOLDIER_ALERT_CONTACT_GET_HIM,
	SOLDIER_ALERT_CONTACT,
	SOLDIER_ALERT_ENEMY_SPOTTED,
	SOLDIER_ALERT_OVER_HERE
};

static const struct {
	char *path;
	enum soldier_alert_phrase phrase;
} soldier_alerts[] = {
	{"soldier/solsrch1.wav", SOLDIER_ALERT_CONTACT_GET_HIM},
	{"soldier/solsght1.wav", SOLDIER_ALERT_ENEMY_SPOTTED},
	{"soldier/callouts/contact_a.wav", SOLDIER_ALERT_CONTACT},
	{"soldier/callouts/contact_b.wav", SOLDIER_ALERT_CONTACT},
	{"soldier/callouts/enemy_spotted_a.wav", SOLDIER_ALERT_ENEMY_SPOTTED},
	{"soldier/callouts/enemy_spotted_b.wav", SOLDIER_ALERT_ENEMY_SPOTTED},
	{"soldier/callouts/over_here_a.wav", SOLDIER_ALERT_OVER_HERE},
	{"soldier/callouts/over_here_b.wav", SOLDIER_ALERT_OVER_HERE},
	{"soldier/callouts/contact_get_him_a.wav", SOLDIER_ALERT_CONTACT_GET_HIM},
	{"soldier/callouts/contact_get_him_b.wav", SOLDIER_ALERT_CONTACT_GET_HIM}
};

/* Cosmetic history only: no entity fields or savegame callbacks change. */
static int soldier_last_alert_phrase = -1;

static int sound_pain_light;
static int sound_pain;
static int sound_pain_ss;
static int sound_death_light;
static int sound_death;
static int sound_death_ss;
static int sound_cock;
static int sound_step;
static int sound_step2;
static int sound_step3;
static int sound_step4;
static int soldier_weapon_model_blaster;
static int soldier_weapon_model_shotgun;
static int soldier_weapon_model_machinegun;

/*
 * Linked soldier weapon models are expected to use the exact same frame
 * layout as models/monsters/soldier/tris.md2.
 */
#define SOLDIER_WEAPON_MODEL_BLASTER "models/monsters/soldier/tall/weapon_blaster.md2"
#define SOLDIER_WEAPON_MODEL_SHOTGUN "models/monsters/soldier/tall/weapon_shotgun.md2"
#define SOLDIER_WEAPON_MODEL_MACHINEGUN "models/monsters/soldier/tall/weapon_machinegun.md2"

static void
soldier_precache_weapon_models(void)
{
	if ((soldier_weapon_model_blaster == 0) ||
		(soldier_weapon_model_shotgun == 0) ||
		(soldier_weapon_model_machinegun == 0))
	{
		soldier_weapon_model_blaster = gi.modelindex(SOLDIER_WEAPON_MODEL_BLASTER);
		soldier_weapon_model_shotgun = gi.modelindex(SOLDIER_WEAPON_MODEL_SHOTGUN);
		soldier_weapon_model_machinegun = gi.modelindex(SOLDIER_WEAPON_MODEL_MACHINEGUN);
	}
}

static void
soldier_set_weapon_model(edict_t *self)
{
	if (!self)
	{
		return;
	}

	soldier_precache_weapon_models();
	if (self->classname && !strcmp(self->classname, "monster_soldier_rocket"))
	{
		self->s.modelindex2 = gi.modelindex("models/monsters/soldier/tall/weapon_rocket.md2");
		return;
	}
	if (self->classname && !strcmp(self->classname, "monster_soldier_heavy"))
	{
		self->s.modelindex2 = gi.modelindex("models/monsters/soldier/tall/weapon_heavy.md2");
		return;
	}

	if (self->s.skinnum < 2)
	{
		self->s.modelindex2 = soldier_weapon_model_blaster;
	}
	else if (self->s.skinnum < 4)
	{
		self->s.modelindex2 = soldier_weapon_model_shotgun;
	}
	else
	{
		self->s.modelindex2 = soldier_weapon_model_machinegun;
	}
}

/* Upgrade older saved levels without changing the serialized edict layout.
 * All authored frame/animation state survives the model path substitution. */
void
Soldier_RefreshDimensions(edict_t *self)
{
	int body;
	if (!self || !self->inuse || !self->classname ||
		strncmp(self->classname, "monster_soldier", 15) ||
		!(self->svflags & SVF_MONSTER) || (self->s.effects & EF_GIB))
	{
		return;
	}
	body = gi.modelindex("models/monsters/soldier/tall/tris.md2");
	if (self->s.modelindex != body)
	{
		self->s.modelindex = body;
		if (self->svflags & SVF_DEADMONSTER)
		{
			self->maxs[2] = PP_SOLDIER_DEAD_MAX_Z;
		}
		else if (self->monsterinfo.aiflags & AI_DUCKED)
		{
			self->maxs[2] = PP_SOLDIER_DUCK_MAX_Z;
		}
		else
		{
			self->maxs[2] = PP_SOLDIER_STAND_MAX_Z;
		}
		self->viewheight = (self->monsterinfo.aiflags & AI_DUCKED) ?
			PP_SOLDIER_DUCK_VIEW_Z : PP_SOLDIER_STAND_VIEW_Z;
	}
	/* Cached indices can belong to the temporary map loaded before ReadLevel. */
	soldier_weapon_model_blaster = soldier_weapon_model_shotgun =
		soldier_weapon_model_machinegun = 0;
	soldier_set_weapon_model(self);
}


void
soldier_footstep(edict_t *self)
{
	if (!g_monsterfootsteps->value)
		return;

	// Lazy loading for savegame compatibility.
	if (sound_step == 0 || sound_step2 == 0 || sound_step3 == 0 || sound_step4 == 0)
	{
		sound_step = gi.soundindex("soldier/player/step1.wav");
		sound_step2 = gi.soundindex("soldier/player/step2.wav");
		sound_step3 = gi.soundindex("soldier/player/step3.wav");
		sound_step4 = gi.soundindex("soldier/player/step4.wav");
	}

	int i;
	i = randk() % 4;

	if (i == 0)
	{
		gi.sound(self, CHAN_BODY, sound_step, 1, ATTN_NORM, 0);
	}
	else if (i == 1)
	{
		gi.sound(self, CHAN_BODY, sound_step2, 1, ATTN_NORM, 0);
	}
	else if (i == 2)
	{
		gi.sound(self, CHAN_BODY, sound_step3, 1, ATTN_NORM, 0);
	}
	else if (i == 3)
	{
		gi.sound(self, CHAN_BODY, sound_step4, 1, ATTN_NORM, 0);
	}
}


void
soldier_idle(edict_t *self)
{
	if (!self)
	{
		return;
	}

	if (random() > 0.8)
	{
		gi.sound(self, CHAN_VOICE, sound_idle, 1, ATTN_IDLE, 0);
	}
}

void
soldier_cock(edict_t *self)
{
	if (!self)
	{
		return;
	}

	if (self->s.frame == FRAME_stand322)
	{
		gi.sound(self, CHAN_WEAPON, sound_cock, 1, ATTN_IDLE, 0);
	}
	else
	{
		gi.sound(self, CHAN_WEAPON, sound_cock, 1, ATTN_NORM, 0);
	}
}

void soldier_stand(edict_t *self);

static mframe_t soldier_frames_stand1[] = {
	{ai_stand, 0, soldier_idle},
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

mmove_t soldier_move_stand1 =
{
	FRAME_stand101,
   	FRAME_stand130,
	soldier_frames_stand1,
	soldier_stand
};

static mframe_t soldier_frames_stand3[] = {
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
	{ai_stand, 0, soldier_cock},
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

mmove_t soldier_move_stand3 =
{
	FRAME_stand301,
   	FRAME_stand339,
   	soldier_frames_stand3,
   	soldier_stand
};

void
soldier_stand(edict_t *self)
{
	if (!self)
	{
		return;
	}

	soldier_set_weapon_model(self);

	if ((self->monsterinfo.currentmove == &soldier_move_stand3) ||
		(random() < 0.8))
	{
		self->monsterinfo.currentmove = &soldier_move_stand1;
	}
	else
	{
		self->monsterinfo.currentmove = &soldier_move_stand3;
	}
}

void
soldier_walk1_random(edict_t *self)
{
	if (!self)
	{
		return;
	}

	if (random() > 0.1)
	{
		self->monsterinfo.nextframe = FRAME_walk101;
	}
}

static mframe_t soldier_frames_walk1[] = {
	{ai_walk, 3, NULL},
	{ai_walk, 6, NULL},
	{ai_walk, 2, NULL},
	{ai_walk, 2, soldier_footstep},
	{ai_walk, 2, NULL},
	{ai_walk, 1, NULL},
	{ai_walk, 6, NULL},
	{ai_walk, 5, NULL},
	{ai_walk, 3, soldier_footstep},
	{ai_walk, -1, soldier_walk1_random},
	{ai_walk, 0, NULL},
	{ai_walk, 0, NULL},
	{ai_walk, 0, NULL},
	{ai_walk, 0, NULL},
	{ai_walk, 0, NULL},
	{ai_walk, 0, NULL},
	{ai_walk, 0, NULL},
	{ai_walk, 0, NULL},
	{ai_walk, 0, NULL},
	{ai_walk, 0, NULL},
	{ai_walk, 0, NULL},
	{ai_walk, 0, NULL},
	{ai_walk, 0, NULL},
	{ai_walk, 0, NULL},
	{ai_walk, 0, NULL},
	{ai_walk, 0, NULL},
	{ai_walk, 0, NULL},
	{ai_walk, 0, NULL},
	{ai_walk, 0, NULL},
	{ai_walk, 0, NULL},
	{ai_walk, 0, NULL},
	{ai_walk, 0, NULL},
	{ai_walk, 0, NULL}
};

mmove_t soldier_move_walk1 =
{
	FRAME_walk101,
	FRAME_walk133,
	soldier_frames_walk1,
	NULL
};

static mframe_t soldier_frames_walk2[] = {
	{ai_walk, 4, soldier_footstep},
	{ai_walk, 4, NULL},
	{ai_walk, 9, NULL},
	{ai_walk, 8, NULL},
	{ai_walk, 5, soldier_footstep},
	{ai_walk, 1, NULL},
	{ai_walk, 3, NULL},
	{ai_walk, 7, NULL},
	{ai_walk, 6, NULL},
	{ai_walk, 7, NULL}
};

mmove_t soldier_move_walk2 =
{
	FRAME_walk209,
   	FRAME_walk218,
	soldier_frames_walk2,
   	NULL
};

void
soldier_walk(edict_t *self)
{
	if (!self)
	{
		return;
	}

	if (random() < 0.5)
	{
		self->monsterinfo.currentmove = &soldier_move_walk1;
	}
	else
	{
		self->monsterinfo.currentmove = &soldier_move_walk2;
	}
}

void soldier_run(edict_t *self);

static mframe_t soldier_frames_start_run[] = {
	{ai_run, 7, NULL},
	{ai_run, 5, NULL}
};

mmove_t soldier_move_start_run =
{
	FRAME_run01,
   	FRAME_run02,
   	soldier_frames_start_run,
   	soldier_run
};

static mframe_t soldier_frames_run[] = {
	{ai_run, 10, NULL},
	{ai_run, 11, soldier_footstep},
	{ai_run, 11, NULL},
	{ai_run, 16, NULL},
	{ai_run, 10, soldier_footstep},
	{ai_run, 15, NULL}
};

mmove_t soldier_move_run =
{
	FRAME_run03,
	FRAME_run08,
	soldier_frames_run,
   	NULL
};

void
soldier_run(edict_t *self)
{
	if (!self)
	{
		return;
	}

	if (self->monsterinfo.aiflags & AI_STAND_GROUND)
	{
		self->monsterinfo.currentmove = &soldier_move_stand1;
		return;
	}

	if ((self->monsterinfo.currentmove == &soldier_move_walk1) ||
		(self->monsterinfo.currentmove == &soldier_move_walk2) ||
		(self->monsterinfo.currentmove == &soldier_move_start_run))
	{
		self->monsterinfo.currentmove = &soldier_move_run;
	}
	else
	{
		self->monsterinfo.currentmove = &soldier_move_start_run;
	}
}

static mframe_t soldier_frames_pain1[] = {
	{ai_move, -3, NULL},
	{ai_move, 4, NULL},
	{ai_move, 1, NULL},
	{ai_move, 1, NULL},
	{ai_move, 0, NULL}
};

mmove_t soldier_move_pain1 =
{
	FRAME_pain101,
   	FRAME_pain105,
   	soldier_frames_pain1,
   	soldier_run
};

static mframe_t soldier_frames_pain2[] = {
	{ai_move, -13, NULL},
	{ai_move, -1, NULL},
	{ai_move, 2, NULL},
	{ai_move, 4, NULL},
	{ai_move, 2, NULL},
	{ai_move, 3, NULL},
	{ai_move, 2, NULL}
};

mmove_t soldier_move_pain2 =
{
	FRAME_pain201,
	FRAME_pain207,
   	soldier_frames_pain2,
   	soldier_run
};

static mframe_t soldier_frames_pain3[] = {
	{ai_move, -8, NULL},
	{ai_move, 10, NULL},
	{ai_move, -4, soldier_footstep},
	{ai_move, -1, NULL},
	{ai_move, -3, NULL},
	{ai_move, 0, NULL},
	{ai_move, 3, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 1, NULL},
	{ai_move, 0, NULL},
	{ai_move, 1, NULL},
	{ai_move, 2, NULL},
	{ai_move, 4, NULL},
	{ai_move, 3, NULL},
	{ai_move, 2, soldier_footstep}
};

mmove_t soldier_move_pain3 =
{
	FRAME_pain301,
   	FRAME_pain318,
   	soldier_frames_pain3,
   	soldier_run
};

static mframe_t soldier_frames_pain4[] = {
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, -10, NULL},
	{ai_move, -6, NULL},
	{ai_move, 8, NULL},
	{ai_move, 4, NULL},
	{ai_move, 1, NULL},
	{ai_move, 0, NULL},
	{ai_move, 2, NULL},
	{ai_move, 5, NULL},
	{ai_move, 2, NULL},
	{ai_move, -1, NULL},
	{ai_move, -1, NULL},
	{ai_move, 3, NULL},
	{ai_move, 2, NULL},
	{ai_move, 0, NULL}
};

mmove_t soldier_move_pain4 =
{
	FRAME_pain401,
	FRAME_pain417,
	soldier_frames_pain4,
   	soldier_run
};

void
soldier_pain(edict_t *self, edict_t *other /* unused */,
		float kick /* unused */, int damage /* unused */)
{
	float r;
	int n;

	if (!self)
	{
		return;
	}

	if (self->health < (self->max_health / 2))
	{
		self->s.skinnum |= 1;
	}

	if (level.time < self->pain_debounce_time)
	{
		if ((self->velocity[2] > 100) &&
			((self->monsterinfo.currentmove == &soldier_move_pain1) ||
			 (self->monsterinfo.currentmove == &soldier_move_pain2) ||
			 (self->monsterinfo.currentmove == &soldier_move_pain3)))
		{
			self->monsterinfo.currentmove = &soldier_move_pain4;
		}

		return;
	}

	self->pain_debounce_time = level.time + 3;

	n = self->s.skinnum | 1;

	if (n == 1)
	{
		gi.sound(self, CHAN_VOICE, sound_pain_light, 1, ATTN_NORM, 0);
	}
	else if (n == 3)
	{
		gi.sound(self, CHAN_VOICE, sound_pain, 1, ATTN_NORM, 0);
	}
	else
	{
		gi.sound(self, CHAN_VOICE, sound_pain_ss, 1, ATTN_NORM, 0);
	}

	if (self->velocity[2] > 100)
	{
		self->monsterinfo.currentmove = &soldier_move_pain4;
		return;
	}

	if (skill->value == SKILL_HARDPLUS)
	{
		return; /* no pain anims in nightmare */
	}

	r = random();

	if (r < 0.33)
	{
		self->monsterinfo.currentmove = &soldier_move_pain1;
	}
	else if (r < 0.66)
	{
		self->monsterinfo.currentmove = &soldier_move_pain2;
	}
	else
	{
		self->monsterinfo.currentmove = &soldier_move_pain3;
	}
}

static int blaster_flash[] =
{
	MZ2_SOLDIER_BLASTER_1,
   	MZ2_SOLDIER_BLASTER_2,
   	MZ2_SOLDIER_BLASTER_3,
	MZ2_SOLDIER_BLASTER_4,
	MZ2_SOLDIER_BLASTER_5,
	MZ2_SOLDIER_BLASTER_6,
	MZ2_SOLDIER_BLASTER_7,
   	MZ2_SOLDIER_BLASTER_8
};

static int shotgun_flash[] =
{
	MZ2_SOLDIER_SHOTGUN_1,
	MZ2_SOLDIER_SHOTGUN_2,
	MZ2_SOLDIER_SHOTGUN_3,
	MZ2_SOLDIER_SHOTGUN_4,
	MZ2_SOLDIER_SHOTGUN_5,
	MZ2_SOLDIER_SHOTGUN_6,
	MZ2_SOLDIER_SHOTGUN_7,
	MZ2_SOLDIER_SHOTGUN_8
};

static int machinegun_flash[] =
{
	MZ2_SOLDIER_MACHINEGUN_1,
	MZ2_SOLDIER_MACHINEGUN_2,
	MZ2_SOLDIER_MACHINEGUN_3,
	MZ2_SOLDIER_MACHINEGUN_4,
	MZ2_SOLDIER_MACHINEGUN_5,
	MZ2_SOLDIER_MACHINEGUN_6,
	MZ2_SOLDIER_MACHINEGUN_7,
	MZ2_SOLDIER_MACHINEGUN_8
};

void
soldier_fire(edict_t *self, int flash_number)
{
	vec3_t start;
	vec3_t forward, right, up;
	vec3_t aim;
	vec3_t dir;
	vec3_t end;
	float r, u;
	int flash_index;

	if (!self)
	{
		return;
	}
	/* Legacy soldier moves include standing, running and death shots. */
	if (self->classname && (!strcmp(self->classname, "monster_soldier_heavy") ||
		!strcmp(self->classname, "monster_soldier_rocket")))
	{
		return;
	}

	if (self->s.skinnum < 2)
	{
		flash_index = blaster_flash[flash_number];
	}
	else if (self->s.skinnum < 4)
	{
		flash_index = shotgun_flash[flash_number];
	}
	else
	{
		flash_index = machinegun_flash[flash_number];
	}

	AngleVectors(self->s.angles, forward, right, NULL);
	G_ProjectSource(self->s.origin, monster_flash_offset[flash_index],
			forward, right, start);

	if ((flash_number == 5) || (flash_number == 6))
	{
		VectorCopy(forward, aim);
	}
	else
	{
		VectorCopy(self->enemy->s.origin, end);
		end[2] += self->enemy->viewheight;
		VectorSubtract(end, start, aim);
		vectoangles(aim, dir);
		AngleVectors(dir, forward, right, up);

		r = crandom() * 1000;
		u = crandom() * 500;
		VectorMA(start, 8192, forward, end);
		VectorMA(end, r, right, end);
		VectorMA(end, u, up, end);

		VectorSubtract(end, start, aim);
		VectorNormalize(aim);
	}

	if (self->s.skinnum <= 1)
	{
		monster_fire_bullet(self, start, aim, 5, 1,
				DEFAULT_BULLET_HSPREAD, DEFAULT_BULLET_VSPREAD,
				flash_index);
	}
	else if (self->s.skinnum <= 3)
	{
		monster_fire_shotgun(self, start, aim, 2, 1,
				DEFAULT_SHOTGUN_HSPREAD, DEFAULT_SHOTGUN_VSPREAD,
				DEFAULT_SHOTGUN_COUNT, flash_index);
	}
	else
	{
		if (!(self->monsterinfo.aiflags & AI_HOLD_FRAME))
		{
			self->monsterinfo.pausetime = level.time + (3 + randk() % 8) * FRAMETIME;
		}

		monster_fire_bullet(self, start, aim, 2, 4,
				DEFAULT_BULLET_HSPREAD, DEFAULT_BULLET_VSPREAD,
				flash_index);

		if (level.time >= self->monsterinfo.pausetime)
		{
			self->monsterinfo.aiflags &= ~AI_HOLD_FRAME;
		}
		else
		{
			self->monsterinfo.aiflags |= AI_HOLD_FRAME;
		}
	}
}

/* ATTACK1 (blaster/shotgun) */
void
soldier_fire1(edict_t *self)
{
	if (!self)
	{
		return;
	}

	soldier_fire(self, 0);
}

void
soldier_attack1_refire1(edict_t *self)
{
	if (!self)
	{
		return;
	}

	if (self->s.skinnum > 1)
	{
		return;
	}

	if (self->enemy->health <= 0)
	{
		return;
	}

	if (((skill->value == SKILL_HARDPLUS) &&
		 (random() < 0.5)) || (range(self, self->enemy) == RANGE_MELEE))
	{
		self->monsterinfo.nextframe = FRAME_attak102;
	}
	else
	{
		self->monsterinfo.nextframe = FRAME_attak110;
	}
}

void
soldier_attack1_refire2(edict_t *self)
{
	if (!self)
	{
		return;
	}

	if (self->s.skinnum < 2)
	{
		return;
	}

	if (self->enemy->health <= 0)
	{
		return;
	}

	if (((skill->value == SKILL_HARDPLUS) &&
		 (random() < 0.5)) || (range(self, self->enemy) == RANGE_MELEE))
	{
		self->monsterinfo.nextframe = FRAME_attak102;
	}
}

static mframe_t soldier_frames_attack1[] = {
	{ai_charge, 0, NULL},
	{ai_charge, 0, NULL},
	{ai_charge, 0, soldier_fire1},
	{ai_charge, 0, NULL},
	{ai_charge, 0, NULL},
	{ai_charge, 0, soldier_attack1_refire1},
	{ai_charge, 0, NULL},
	{ai_charge, 0, soldier_cock},
	{ai_charge, 0, soldier_attack1_refire2},
	{ai_charge, 0, NULL},
	{ai_charge, 0, NULL},
	{ai_charge, 0, NULL}
};

mmove_t soldier_move_attack1 =
{
	FRAME_attak101,
	FRAME_attak112,
	soldier_frames_attack1,
   	soldier_run
};

/* ATTACK2 (blaster/shotgun) */
void
soldier_fire2(edict_t *self)
{
	if (!self)
	{
		return;
	}

	soldier_fire(self, 1);
}

void
soldier_attack2_refire1(edict_t *self)
{
	if (!self)
	{
		return;
	}

	if (self->s.skinnum > 1)
	{
		return;
	}

	if (self->enemy->health <= 0)
	{
		return;
	}

	if (((skill->value == SKILL_HARDPLUS) &&
		 (random() < 0.5)) || (range(self, self->enemy) == RANGE_MELEE))
	{
		self->monsterinfo.nextframe = FRAME_attak204;
	}
	else
	{
		self->monsterinfo.nextframe = FRAME_attak216;
	}
}

void
soldier_attack2_refire2(edict_t *self)
{
	if (!self)
	{
		return;
	}

	if (self->s.skinnum < 2)
	{
		return;
	}

	if (self->enemy->health <= 0)
	{
		return;
	}

	if (((skill->value == SKILL_HARDPLUS) &&
		 (random() < 0.5)) || (range(self, self->enemy) == RANGE_MELEE))
	{
		self->monsterinfo.nextframe = FRAME_attak204;
	}
}

static mframe_t soldier_frames_attack2[] = {
	{ai_charge, 0, NULL},
	{ai_charge, 0, NULL},
	{ai_charge, 0, NULL},
	{ai_charge, 0, NULL},
	{ai_charge, 0, soldier_fire2},
	{ai_charge, 0, NULL},
	{ai_charge, 0, NULL},
	{ai_charge, 0, soldier_attack2_refire1},
	{ai_charge, 0, NULL},
	{ai_charge, 0, NULL},
	{ai_charge, 0, NULL},
	{ai_charge, 0, NULL},
	{ai_charge, 0, soldier_cock},
	{ai_charge, 0, NULL},
	{ai_charge, 0, soldier_attack2_refire2},
	{ai_charge, 0, NULL},
	{ai_charge, 0, NULL},
	{ai_charge, 0, NULL}
};

mmove_t soldier_move_attack2 =
{
	FRAME_attak201,
   	FRAME_attak218,
   	soldier_frames_attack2,
   	soldier_run
};

/* ATTACK3 (duck and shoot) */
void
soldier_duck_down(edict_t *self)
{
	if (!self)
	{
		return;
	}

	if (self->monsterinfo.aiflags & AI_DUCKED)
	{
		return;
	}

	self->monsterinfo.aiflags |= AI_DUCKED;
	self->maxs[2] -= PP_SOLDIER_DUCK_DROP;
	self->viewheight = PP_SOLDIER_DUCK_VIEW_Z;
	self->takedamage = DAMAGE_YES;
	self->monsterinfo.pausetime = level.time + 1;
	gi.linkentity(self);
}

void
soldier_duck_up(edict_t *self)
{
	if (!self)
	{
		return;
	}

	self->monsterinfo.aiflags &= ~AI_DUCKED;
	self->maxs[2] += PP_SOLDIER_DUCK_DROP;
	self->viewheight = PP_SOLDIER_STAND_VIEW_Z;
	self->takedamage = DAMAGE_AIM;
	gi.linkentity(self);
}

void
soldier_fire3(edict_t *self)
{
	if (!self)
	{
		return;
	}

	soldier_duck_down(self);
	soldier_fire(self, 2);
}

void
soldier_attack3_refire(edict_t *self)
{
	if (!self)
	{
		return;
	}

	if ((level.time + 0.4) < self->monsterinfo.pausetime)
	{
		self->monsterinfo.nextframe = FRAME_attak303;
	}
}

static mframe_t soldier_frames_attack3[] = {
	{ai_charge, 0, NULL},
	{ai_charge, 0, NULL},
	{ai_charge, 0, soldier_fire3},
	{ai_charge, 0, NULL},
	{ai_charge, 0, NULL},
	{ai_charge, 0, soldier_attack3_refire},
	{ai_charge, 0, soldier_duck_up},
	{ai_charge, 0, NULL},
	{ai_charge, 0, NULL}
};

mmove_t soldier_move_attack3 =
{
	FRAME_attak301,
	FRAME_attak309,
	soldier_frames_attack3,
	soldier_run
};

/* ATTACK4 (machinegun) */
void
soldier_fire4(edict_t *self)
{
	if (!self)
	{
		return;
	}

	soldier_fire(self, 3);
}

static mframe_t soldier_frames_attack4[] = {
	{ai_charge, 0, NULL},
	{ai_charge, 0, soldier_footstep},
	{ai_charge, 0, soldier_fire4},
	{ai_charge, 0, NULL},
	{ai_charge, 0, NULL},
	{ai_charge, 0, soldier_footstep}
};

mmove_t soldier_move_attack4 =
{
	FRAME_attak401,
   	FRAME_attak406,
   	soldier_frames_attack4,
   	soldier_run
};

/* ATTACK6 (run & shoot) */
void
soldier_fire8(edict_t *self)
{
	if (!self)
	{
		return;
	}

	soldier_fire(self, 7);
}

void
soldier_attack6_refire(edict_t *self)
{
	if (!self)
	{
		return;
	}

	if (self->enemy->health <= 0)
	{
		return;
	}

	if (range(self, self->enemy) < RANGE_MID)
	{
		return;
	}

	if (skill->value == SKILL_HARDPLUS)
	{
		self->monsterinfo.nextframe = FRAME_runs03;
	}
}

static mframe_t soldier_frames_attack6[] = {
	{ai_charge, 10, NULL},
	{ai_charge, 4, NULL},
	{ai_charge, 12, soldier_footstep},
	{ai_charge, 11, soldier_fire8},
	{ai_charge, 13, NULL},
	{ai_charge, 18, NULL},
	{ai_charge, 15, soldier_footstep},
	{ai_charge, 14, NULL},
	{ai_charge, 11, NULL},
	{ai_charge, 8, soldier_footstep},
	{ai_charge, 11, NULL},
	{ai_charge, 12, NULL},
	{ai_charge, 12, soldier_footstep},
	{ai_charge, 17, soldier_attack6_refire}
};

mmove_t soldier_move_attack6 =
{
	FRAME_runs01,
	FRAME_runs14,
	soldier_frames_attack6,
	soldier_run
};

void
soldier_attack(edict_t *self)
{
	if (!self)
	{
		return;
	}

	if (self->s.skinnum < 4)
	{
		if (random() < 0.5)
		{
			self->monsterinfo.currentmove = &soldier_move_attack1;
		}
		else
		{
			self->monsterinfo.currentmove = &soldier_move_attack2;
		}
	}
	else
	{
		self->monsterinfo.currentmove = &soldier_move_attack4;
	}
}

static void
soldier_alert(edict_t *self)
{
	size_t i;
	int available = 0, choice;

	if (!self)
	{
		return;
	}

	/* Exclude the last wording, not just its take, across all soldiers. */
	for (i = 0; i < sizeof(soldier_alerts) / sizeof(soldier_alerts[0]); i++)
	{
		if ((int)soldier_alerts[i].phrase != soldier_last_alert_phrase)
		{
			available++;
		}
	}
	choice = (randk() & 0x7fff) % available;
	for (i = 0; i < sizeof(soldier_alerts) / sizeof(soldier_alerts[0]); i++)
	{
		if ((int)soldier_alerts[i].phrase == soldier_last_alert_phrase)
		{
			continue;
		}
		if (choice-- == 0)
		{
			soldier_last_alert_phrase = soldier_alerts[i].phrase;
			/* Resolve by name so an old save cannot leave a stale cached index. */
			gi.sound(self, CHAN_VOICE, gi.soundindex(soldier_alerts[i].path),
					1, ATTN_NORM, 0);
			return;
		}
	}
}

void
soldier_sight(edict_t *self, edict_t *other /* unused */)
{
	if (!self)
	{
		return;
	}

	soldier_alert(self);

	if ((skill->value > SKILL_EASY) && (range(self, self->enemy) >= RANGE_MID))
	{
		if (random() > 0.5)
		{
			self->monsterinfo.currentmove = &soldier_move_attack6;
		}
	}
}

void
soldier_duck_hold(edict_t *self)
{
	if (!self)
	{
		return;
	}

	if (level.time >= self->monsterinfo.pausetime)
	{
		self->monsterinfo.aiflags &= ~AI_HOLD_FRAME;
	}
	else
	{
		self->monsterinfo.aiflags |= AI_HOLD_FRAME;
	}
}

static mframe_t soldier_frames_duck[] = {
	{ai_move, 5, soldier_duck_down},
	{ai_move, -1, soldier_duck_hold},
	{ai_move, 1, NULL},
	{ai_move, 0, soldier_duck_up},
	{ai_move, 5, NULL}
};

mmove_t soldier_move_duck =
{
	FRAME_duck01,
   	FRAME_duck05,
   	soldier_frames_duck,
   	soldier_run
};

void
soldier_dodge(edict_t *self, edict_t *attacker, float eta)
{
	float r;

	if (!self || !attacker)
	{
		return;
	}

	r = random();

	if (r > 0.25)
	{
		return;
	}

	if (!self->enemy)
	{
		self->enemy = attacker;
		FoundTarget(self);
	}

	if (skill->value == SKILL_EASY)
	{
		self->monsterinfo.currentmove = &soldier_move_duck;
		return;
	}

	self->monsterinfo.pausetime = level.time + eta + 0.3;
	r = random();

	if (skill->value == SKILL_MEDIUM)
	{
		if (r > 0.33)
		{
			self->monsterinfo.currentmove = &soldier_move_duck;
		}
		else
		{
			self->monsterinfo.currentmove = &soldier_move_attack3;
		}

		return;
	}

	if (skill->value >= SKILL_HARD)
	{
		if (r > 0.66)
		{
			self->monsterinfo.currentmove = &soldier_move_duck;
		}
		else
		{
			self->monsterinfo.currentmove = &soldier_move_attack3;
		}

		return;
	}

	self->monsterinfo.currentmove = &soldier_move_attack3;
}

void
soldier_fire6(edict_t *self)
{
	if (!self)
	{
		return;
	}

	soldier_fire(self, 5);
}

void
soldier_fire7(edict_t *self)
{
	if (!self)
	{
		return;
	}

	soldier_fire(self, 6);
}

void
soldier_dead(edict_t *self)
{
	if (!self)
	{
		return;
	}

	VectorSet(self->mins, -16, -16, -24);
	VectorSet(self->maxs, 16, 16, PP_SOLDIER_DEAD_MAX_Z);
	self->movetype = MOVETYPE_TOSS;
	self->svflags |= SVF_DEADMONSTER;
	self->nextthink = 0;
	gi.linkentity(self);
}

static mframe_t soldier_frames_death1[] = {
	{ai_move, 0, NULL},
	{ai_move, -10, NULL},
	{ai_move, -10, NULL},
	{ai_move, -10, NULL},
	{ai_move, -5, NULL},
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
	{ai_move, 0, soldier_fire6},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, soldier_fire7},
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

mmove_t soldier_move_death1 =
{
	FRAME_death101,
	FRAME_death136,
	soldier_frames_death1,
	soldier_dead
};

static mframe_t soldier_frames_death2[] = {
	{ai_move, -5, NULL},
	{ai_move, -5, NULL},
	{ai_move, -5, NULL},
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

mmove_t soldier_move_death2 =
{
	FRAME_death201,
	FRAME_death235,
   	soldier_frames_death2,
   	soldier_dead
};

static mframe_t soldier_frames_death3[] = {
	{ai_move, -5, NULL},
	{ai_move, -5, NULL},
	{ai_move, -5, NULL},
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
};

mmove_t soldier_move_death3 =
{
	FRAME_death301,
   	FRAME_death345,
   	soldier_frames_death3,
   	soldier_dead
};

static mframe_t soldier_frames_death4[] = {
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
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},

	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL}
};

mmove_t soldier_move_death4 =
{
	FRAME_death401,
   	FRAME_death453,
   	soldier_frames_death4,
	soldier_dead
};

static mframe_t soldier_frames_death5[] = {
	{ai_move, -5, NULL},
	{ai_move, -5, NULL},
	{ai_move, -5, NULL},
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

mmove_t soldier_move_death5 =
{
	FRAME_death501,
   	FRAME_death524,
   	soldier_frames_death5,
   	soldier_dead
};

static mframe_t soldier_frames_death6[] = {
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

mmove_t soldier_move_death6 =
{
	FRAME_death601,
	FRAME_death610,
	soldier_frames_death6,
	soldier_dead
};

void
soldier_die(edict_t *self, edict_t *inflictor /* unused */,
		edict_t *attacker /* unused */, int damage,
		vec3_t point /* unused */)
{
	int n;

	/* check for gib */
	if (self->health <= self->gib_health)
	{
		gi.sound(self, CHAN_VOICE, gi.soundindex("soldier/player/death4.wav"), 1, ATTN_NORM, 0);

		for (n = 0; n < 3; n++)
		{
			ThrowGib(self, "models/objects/gibs/sm_meat/tris.md2",
					damage, GIB_ORGANIC);
		}

		ThrowGib(self, "models/objects/gibs/chest/tris.md2",
				damage, GIB_ORGANIC);
		ThrowHead(self, "models/objects/gibs/head2/tris.md2",
				damage, GIB_ORGANIC);
		self->deadflag = DEAD_DEAD;
		return;
	}

	if (self->deadflag == DEAD_DEAD)
	{
		return;
	}

	/* regular death */
	self->deadflag = DEAD_DEAD;
	self->takedamage = DAMAGE_YES;
	self->s.skinnum |= 1;

	if (self->s.skinnum == 1)
	{
		gi.sound(self, CHAN_VOICE, sound_death_light, 1, ATTN_NORM, 0);
	}
	else if (self->s.skinnum == 3)
	{
		gi.sound(self, CHAN_VOICE, sound_death, 1, ATTN_NORM, 0);
	}
	else
	{
		gi.sound(self, CHAN_VOICE, sound_death_ss, 1, ATTN_NORM, 0);
	}

	if (fabs((self->s.origin[2] + self->viewheight) - point[2]) <= 4)
	{
		/* head shot */
		self->monsterinfo.currentmove = &soldier_move_death3;
		return;
	}

	n = randk() % 5;

	if (n == 0)
	{
		self->monsterinfo.currentmove = &soldier_move_death1;
	}
	else if (n == 1)
	{
		self->monsterinfo.currentmove = &soldier_move_death2;
	}
	else if (n == 2)
	{
		self->monsterinfo.currentmove = &soldier_move_death4;
	}
	else if (n == 3)
	{
		self->monsterinfo.currentmove = &soldier_move_death5;
	}
	else
	{
		self->monsterinfo.currentmove = &soldier_move_death6;
	}
}

void
SP_monster_soldier_x(edict_t *self)
{
	size_t i;

	if (!self)
	{
		return;
	}

	// Force recaching at next footstep to ensure
	// that the sound indices are correct.
	sound_step = 0;
	sound_step2 = 0;
	sound_step3 = 0;
	sound_step4 = 0;
	soldier_weapon_model_blaster = 0;
	soldier_weapon_model_shotgun = 0;
	soldier_weapon_model_machinegun = 0;

	self->s.modelindex = gi.modelindex("models/monsters/soldier/tall/tris.md2");
	soldier_precache_weapon_models();
	self->monsterinfo.scale = MODEL_SCALE;
	VectorSet(self->mins, -16, -16, -24);
	VectorSet(self->maxs, 16, 16, PP_SOLDIER_STAND_MAX_Z);
	self->viewheight = PP_SOLDIER_STAND_VIEW_Z;
	self->movetype = MOVETYPE_STEP;
	self->solid = SOLID_BBOX;

	/* Mono player-sound aliases spatialize NPCs without changing player audio. */
	gi.soundindex("soldier/player/death4.wav");
	sound_idle = gi.soundindex("soldier/solidle1.wav");
	for (i = 0; i < sizeof(soldier_alerts) / sizeof(soldier_alerts[0]); i++)
	{
		gi.soundindex(soldier_alerts[i].path);
	}
	sound_cock = gi.soundindex("infantry/infatck3.wav");

	self->mass = 100;

	self->pain = soldier_pain;
	self->die = soldier_die;

	self->monsterinfo.stand = soldier_stand;
	self->monsterinfo.walk = soldier_walk;
	self->monsterinfo.run = soldier_run;
	self->monsterinfo.dodge = soldier_dodge;
	self->monsterinfo.attack = soldier_attack;
	self->monsterinfo.melee = NULL;
	self->monsterinfo.sight = soldier_sight;

	gi.linkentity(self);

	self->monsterinfo.stand(self);

	walkmonster_start(self);
}

/*
 * QUAKED monster_soldier_light (1 .5 0) (-16 -16 -24) (16 16 32) Ambush Trigger_Spawn Sight
 */
void
SP_monster_soldier_light(edict_t *self)
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

	self->health = 20;
	self->gib_health = -30;

	SP_monster_soldier_x(self);

	sound_pain_light = gi.soundindex("soldier/player/pain25_1.wav");
	sound_death_light = gi.soundindex("soldier/player/death2.wav");
	sound_step = gi.soundindex("soldier/player/step1.wav");
	sound_step2 = gi.soundindex("soldier/player/step2.wav");
	sound_step3 = gi.soundindex("soldier/player/step3.wav");
	sound_step4 = gi.soundindex("soldier/player/step4.wav");
	gi.modelindex("models/objects/laser/tris.md2");
	gi.soundindex("misc/lasfly.wav");
	gi.soundindex("soldier/player/pistol1.wav");
	gi.soundindex("soldier/player/pistol2.wav");
	gi.soundindex("soldier/player/pistol3.wav");
	gi.soundindex("soldier/player/pistol4.wav");

	self->s.skinnum = 0;
	soldier_set_weapon_model(self);
}

/*
 * QUAKED monster_soldier (1 .5 0) (-16 -16 -24) (16 16 32) Ambush Trigger_Spawn Sight
 */
void
SP_monster_soldier(edict_t *self)
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

	self->health = 30;
	self->gib_health = -30;

	SP_monster_soldier_x(self);

	sound_pain = gi.soundindex("soldier/player/pain50_1.wav");
	sound_death = gi.soundindex("soldier/player/death1.wav");
	sound_step = gi.soundindex("soldier/player/step1.wav");
	sound_step2 = gi.soundindex("soldier/player/step2.wav");
	sound_step3 = gi.soundindex("soldier/player/step3.wav");
	sound_step4 = gi.soundindex("soldier/player/step4.wav");
	gi.soundindex("soldier/player/shotgf1b.wav");

	self->s.skinnum = 2;
	soldier_set_weapon_model(self);
}

/*
 * QUAKED monster_soldier_ss (1 .5 0) (-16 -16 -24) (16 16 32) Ambush Trigger_Spawn Sight
 */
void
SP_monster_soldier_ss(edict_t *self)
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

	self->health = 40;
	self->gib_health = -30;

	SP_monster_soldier_x(self);

	sound_pain_ss = gi.soundindex("soldier/player/pain100_1.wav");
	sound_death_ss = gi.soundindex("soldier/player/death3.wav");
	sound_step = gi.soundindex("soldier/player/step1.wav");
	sound_step2 = gi.soundindex("soldier/player/step2.wav");
	sound_step3 = gi.soundindex("soldier/player/step3.wav");
	sound_step4 = gi.soundindex("soldier/player/step4.wav");
	gi.soundindex("soldier/player/machgf1b.wav");
	gi.soundindex("soldier/player/machgf2b.wav");
	gi.soundindex("soldier/player/machgf3b.wav");
	gi.soundindex("soldier/player/machgf4b.wav");
	gi.soundindex("soldier/player/machgf5b.wav");

	self->s.skinnum = 4;
	soldier_set_weapon_model(self);
}

/*
 * The M60 gunner uses the soldier's authored crouch attack. Walking, lowering,
 * firing and raising are separate phases; only the planted crouch can shoot.
 * Timers and stance live in the existing, saved monsterinfo/edict fields.
 */
void soldier_heavy_stand(edict_t *self);
void soldier_heavy_walk(edict_t *self);
void soldier_heavy_run(edict_t *self);
void soldier_heavy_recover(edict_t *self);

static qboolean
soldier_is_rocket(edict_t *self)
{
	return self && self->classname && !strcmp(self->classname, "monster_soldier_rocket");
}

static qboolean
soldier_heavy_target(edict_t *self)
{
	return self && self->health > 0 && self->deadflag == DEAD_NO &&
		self->enemy && self->enemy->inuse && self->enemy->health > 0;
}

void
soldier_heavy_lower(edict_t *self)
{
	if (!(self->monsterinfo.aiflags & AI_DUCKED))
	{
		self->monsterinfo.aiflags |= AI_DUCKED;
		self->maxs[2] = PP_SOLDIER_DUCK_MAX_Z;
		self->viewheight = PP_SOLDIER_DUCK_VIEW_Z;
		self->takedamage = DAMAGE_YES;
		gi.linkentity(self);
	}
}

/* Never expand the standing hull through a ceiling or another actor. */
void
soldier_heavy_raise(edict_t *self)
{
	vec3_t maxs;
	trace_t tr;

	self->monsterinfo.aiflags &= ~AI_HOLD_FRAME;
	if (!(self->monsterinfo.aiflags & AI_DUCKED))
	{
		return;
	}

	VectorCopy(self->maxs, maxs);
	maxs[2] = PP_SOLDIER_STAND_MAX_Z;
	tr = gi.trace(self->s.origin, self->mins, maxs, self->s.origin,
		self, MASK_MONSTERSOLID);
	if (tr.startsolid || tr.allsolid)
	{
		self->monsterinfo.nextframe = FRAME_attak306;
		return;
	}

	self->monsterinfo.aiflags &= ~AI_DUCKED;
	self->maxs[2] = PP_SOLDIER_STAND_MAX_Z;
	self->viewheight = PP_SOLDIER_STAND_VIEW_Z;
	self->takedamage = DAMAGE_AIM;
	gi.linkentity(self);
}

static void
soldier_heavy_idle(edict_t *self)
{
	/* Resolve on demand as well, for a spawner-created gunner restored from save. */
	if (random() > 0.8f)
	{
		gi.sound(self, CHAN_VOICE, gi.soundindex("soldier/solidle1.wav"), 1, ATTN_IDLE, 0);
	}
}

static mframe_t soldier_heavy_frames_stand[] = {
	{ai_stand, 0, soldier_heavy_idle},
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

mmove_t soldier_heavy_move_stand = {
	FRAME_stand101, FRAME_stand110, soldier_heavy_frames_stand, NULL
};

/* The same deliberate gait is used when patrolling and chasing (33 u/s). */
static mframe_t soldier_heavy_frames_walk[] = {
	{ai_walk, 3, soldier_footstep},
	{ai_walk, 3, NULL},
	{ai_walk, 4, NULL},
	{ai_walk, 4, NULL},
	{ai_walk, 3, soldier_footstep},
	{ai_walk, 2, NULL},
	{ai_walk, 3, NULL},
	{ai_walk, 4, NULL},
	{ai_walk, 3, NULL},
	{ai_walk, 4, NULL}
};

mmove_t soldier_heavy_move_walk = {
	FRAME_walk209, FRAME_walk218, soldier_heavy_frames_walk, NULL
};

static void
soldier_heavy_advance(edict_t *self, float dist)
{
	vec3_t delta;

	if (soldier_is_rocket(self) && soldier_heavy_target(self))
	{
		VectorSubtract(self->enemy->s.origin, self->s.origin, delta);
		if (VectorLength(delta) < 224 && visible(self, self->enemy))
		{
			/* Make room for the blast instead of chasing into our own splash. */
			ai_charge(self, 0);
			M_walkmove(self, self->s.angles[YAW] + 180, dist);
			return;
		}
	}
	ai_run(self, dist);
}

static mframe_t soldier_heavy_frames_run[] = {
	{soldier_heavy_advance, 3, soldier_footstep},
	{soldier_heavy_advance, 3, NULL},
	{soldier_heavy_advance, 4, NULL},
	{soldier_heavy_advance, 4, NULL},
	{soldier_heavy_advance, 3, soldier_footstep},
	{soldier_heavy_advance, 2, NULL},
	{soldier_heavy_advance, 3, NULL},
	{soldier_heavy_advance, 4, NULL},
	{soldier_heavy_advance, 3, NULL},
	{soldier_heavy_advance, 4, NULL}
};

mmove_t soldier_heavy_move_run = {
	FRAME_walk209, FRAME_walk218, soldier_heavy_frames_run, NULL
};

void
soldier_heavy_fire(edict_t *self)
{
	vec3_t start, end, aim, forward, right, delta;
	trace_t tr;
	qboolean ready;
	qboolean rocket = soldier_is_rocket(self);
	int flash = rocket ? MZ2_SOLDIER_ROCKET : MZ2_SOLDIER_HEAVY;

	if (!self)
	{
		return;
	}

	ready = soldier_heavy_target(self) &&
		(self->monsterinfo.aiflags & AI_DUCKED) && self->groundentity &&
		self->s.frame == FRAME_attak303 &&
		fabsf(self->velocity[0]) < 1 && fabsf(self->velocity[1]) < 1 &&
		fabsf(self->velocity[2]) < 1 &&
		(rocket ? self->monsterinfo.pausetime > 0 : level.time < self->monsterinfo.pausetime);

	if (ready)
	{
		AngleVectors(self->s.angles, forward, right, NULL);
		VectorSubtract(self->enemy->s.origin, self->s.origin, delta);
		delta[2] = 0;
		if (rocket && VectorLength(delta) < 224)
		{
			self->monsterinfo.aiflags &= ~AI_HOLD_FRAME;
			return;
		}
		VectorNormalize(delta);
		ready = DotProduct(forward, delta) > 0.8f;
	}

	if (ready)
	{
		G_ProjectSource(self->s.origin, monster_flash_offset[flash],
			forward, right, start);
		/* Check the muzzle as well as the target: low cover can block a crouch. */
		tr = gi.trace(self->s.origin, NULL, NULL, start, self, MASK_SHOT);
		ready = !tr.startsolid && !tr.allsolid && tr.fraction == 1;
		if (ready)
		{
			VectorCopy(self->enemy->s.origin, end);
			end[2] += self->enemy->viewheight;
			tr = gi.trace(start, NULL, NULL, end, self, MASK_SHOT);
			ready = !tr.startsolid && !tr.allsolid &&
				(tr.fraction == 1 || tr.ent == self->enemy);
		}
	}

	if (!ready)
	{
		self->monsterinfo.aiflags &= ~AI_HOLD_FRAME;
		return;
	}

	VectorSubtract(end, start, aim);
	VectorNormalize(aim);
	if (rocket)
	{
		if (level.time < self->monsterinfo.pausetime)
		{
			/* A visible crouched windup gives the player time to react. */
			self->monsterinfo.aiflags |= AI_HOLD_FRAME;
			return;
		}
		monster_fire_rocket(self, start, aim, 60, 450, flash);
		self->monsterinfo.pausetime = 0; /* One rocket per deployment. */
		self->monsterinfo.aiflags &= ~AI_HOLD_FRAME;
		return;
	}
	/* Ten rounds/sec, short bursts, with enough spread to cross between cover. */
	monster_fire_bullet(self, start, aim, 6, 4, 350, 250, MZ2_SOLDIER_HEAVY);
	self->monsterinfo.aiflags |= AI_HOLD_FRAME;
}

static mframe_t soldier_heavy_frames_attack[] = {
	{ai_charge, 0, soldier_heavy_lower},
	{ai_charge, 0, NULL},
	{ai_charge, 0, soldier_heavy_fire},
	{ai_charge, 0, NULL},
	{ai_charge, 0, NULL},
	{ai_charge, 0, NULL},
	{ai_charge, 0, soldier_heavy_raise},
	{ai_charge, 0, NULL},
	{ai_charge, 0, NULL}
};

mmove_t soldier_heavy_move_attack = {
	FRAME_attak301, FRAME_attak309, soldier_heavy_frames_attack, soldier_heavy_recover
};

void
soldier_heavy_stand(edict_t *self)
{
	if (self->monsterinfo.aiflags & AI_DUCKED)
	{
		self->monsterinfo.currentmove = &soldier_heavy_move_attack;
		self->monsterinfo.nextframe = FRAME_attak307;
		self->monsterinfo.aiflags &= ~AI_HOLD_FRAME;
		return;
	}
	self->monsterinfo.currentmove = &soldier_heavy_move_stand;
}

void
soldier_heavy_walk(edict_t *self)
{
	if (self->monsterinfo.aiflags & AI_DUCKED)
	{
		soldier_heavy_stand(self);
		return;
	}
	self->monsterinfo.currentmove = &soldier_heavy_move_walk;
}

void
soldier_heavy_run(edict_t *self)
{
	if (self->monsterinfo.aiflags & (AI_DUCKED | AI_STAND_GROUND))
	{
		soldier_heavy_stand(self);
		return;
	}
	self->monsterinfo.currentmove = &soldier_heavy_move_run;
}

void
soldier_heavy_recover(edict_t *self)
{
	/* Reload only after a launched rocket, once the recovery animation ends.
	 * pausetime is zeroed by the successful launch and saved with the monster.
	 * Consume that marker so repeated recovery calls cannot replay the effect. */
	if (soldier_is_rocket(self) && self->health > 0 && self->deadflag == DEAD_NO &&
		self->monsterinfo.currentmove == &soldier_heavy_move_attack &&
		self->monsterinfo.pausetime == 0)
	{
		gi.sound(self, CHAN_WEAPON, gi.soundindex("soldier/rocket_reload.wav"),
			1, ATTN_NORM, 0);
		self->monsterinfo.pausetime = -1;
	}
	self->monsterinfo.aiflags &= ~AI_HOLD_FRAME;
	self->monsterinfo.attack_finished = level.time + (soldier_is_rocket(self) ? 2.5f : 1.0f);
	soldier_heavy_run(self);
}

qboolean
soldier_heavy_checkattack(edict_t *self)
{
	vec3_t delta;

	if (!soldier_heavy_target(self) || !self->groundentity ||
		level.time < self->monsterinfo.attack_finished ||
		(self->monsterinfo.aiflags & AI_DUCKED) || !visible(self, self->enemy))
	{
		return false;
	}
	VectorSubtract(self->enemy->s.origin, self->s.origin, delta);
	if (VectorLength(delta) > 1400 || (soldier_is_rocket(self) && VectorLength(delta) < 224))
	{
		return false;
	}
	self->monsterinfo.attack_state = AS_MISSILE;
	return true;
}

void
soldier_heavy_attack(edict_t *self)
{
	if (!soldier_heavy_target(self) || !self->groundentity ||
		level.time < self->monsterinfo.attack_finished)
	{
		return;
	}
	self->monsterinfo.aiflags &= ~AI_HOLD_FRAME;
	self->monsterinfo.pausetime = level.time + (soldier_is_rocket(self) ? 0.7f : 1.7f);
	self->monsterinfo.currentmove = &soldier_heavy_move_attack;
	self->monsterinfo.nextframe = FRAME_attak301;
}

void
soldier_heavy_sight(edict_t *self, edict_t *other)
{
	/* Soldier sight can select a run-and-fire move; this variant only alerts. */
	soldier_alert(self);
}

static mframe_t soldier_heavy_frames_pain[] = {
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL},
	{ai_move, 0, NULL}
};

mmove_t soldier_heavy_move_pain = {
	FRAME_pain101, FRAME_pain105, soldier_heavy_frames_pain, soldier_heavy_run
};

void
soldier_heavy_pain(edict_t *self, edict_t *other, float kick, int damage)
{
	if (self->health < self->max_health / 2)
	{
		self->s.skinnum |= 1;
	}
	if (level.time < self->pain_debounce_time)
	{
		return;
	}
	self->pain_debounce_time = level.time + 2;
	gi.sound(self, CHAN_VOICE, gi.soundindex("soldier/player/pain100_1.wav"), 1, ATTN_NORM, 0);
	/* Heavier hits interrupt a planted burst even on nightmare. */
	if (damage < 15)
	{
		return;
	}
	self->monsterinfo.aiflags &= ~AI_HOLD_FRAME;
	self->monsterinfo.attack_finished = level.time + 1;
	if (self->monsterinfo.aiflags & AI_DUCKED)
	{
		soldier_heavy_stand(self);
	}
	else
	{
		self->monsterinfo.currentmove = &soldier_heavy_move_pain;
	}
}

void
soldier_heavy_die(edict_t *self, edict_t *inflictor, edict_t *attacker,
		int damage, vec3_t point)
{
	qboolean was_dead = self->deadflag == DEAD_DEAD;

	self->monsterinfo.aiflags &= ~(AI_HOLD_FRAME | AI_DUCKED);
	self->monsterinfo.nextframe = 0;
	self->s.sound = 0;
	sound_death_ss = gi.soundindex("soldier/player/death3.wav");
	soldier_die(self, inflictor, attacker, damage, point);
	if (!was_dead && self->health > self->gib_health)
	{
		/* The ordinary soldier can fire during death1; the heavy never does. */
		self->monsterinfo.currentmove = &soldier_move_death2;
	}
}

/*
 * QUAKED monster_soldier_heavy (1 .5 0) (-16 -16 -24) (16 16 32) Ambush Trigger_Spawn Sight
 * Slow M60 support gunner: 180 health, crouched bursts with a recovery gap.
 */
void
SP_monster_soldier_heavy(edict_t *self)
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

	self->health = 180;
	self->gib_health = -60;
	SP_monster_soldier_x(self);
	self->mass = 250;
	self->yaw_speed = 10;
	self->viewheight = PP_SOLDIER_STAND_VIEW_Z;
	self->s.skinnum = 4;
	soldier_set_weapon_model(self);
	sound_pain_ss = gi.soundindex("soldier/player/pain100_1.wav");
	sound_death_ss = gi.soundindex("soldier/player/death3.wav");
	gi.soundindex("soldier/player/m601.wav");
	gi.soundindex("soldier/player/m602.wav");
	gi.soundindex("soldier/player/m603.wav");
	gi.soundindex("soldier/player/m604.wav");
	gi.soundindex("soldier/player/m605.wav");

	self->pain = soldier_heavy_pain;
	self->die = soldier_heavy_die;
	self->monsterinfo.stand = soldier_heavy_stand;
	self->monsterinfo.walk = soldier_heavy_walk;
	self->monsterinfo.run = soldier_heavy_run;
	self->monsterinfo.dodge = NULL;
	self->monsterinfo.attack = soldier_heavy_attack;
	self->monsterinfo.checkattack = soldier_heavy_checkattack;
	self->monsterinfo.sight = soldier_heavy_sight;
	soldier_heavy_stand(self);
}

/*
 * QUAKED monster_soldier_rocket (1 .5 0) (-16 -16 -24) (16 16 32) Ambush Trigger_Spawn Sight
 * Slow launcher specialist. Shares the heavy's crouch, movement and reactions,
 * but launches one dodgeable rocket before rising and reloading.
 */
void
SP_monster_soldier_rocket(edict_t *self)
{
	if (!self)
	{
		return;
	}
	SP_monster_soldier_heavy(self);
	if (!self->inuse)
	{
		return;
	}
	gi.modelindex("models/objects/rocket/tris.md2");
	gi.soundindex("weapons/rockfly.wav");
	gi.soundindex("soldier/rocket_reload.wav");
	gi.soundindex("soldier/player/rocklf1a.wav");
	gi.soundindex("weapons/rocklx1a.wav");
}
