/*
 * Plastic Platoon's tan molded attack helicopter.
 * Original game code, licensed under the GNU GPL, version 2 or later.
 */

#include "../../header/local.h"

void plastic_helicopter_stand(edict_t *self);
void plastic_helicopter_walk(edict_t *self);
void plastic_helicopter_run(edict_t *self);
void plastic_helicopter_idle(edict_t *self, float dist);
void plastic_helicopter_hover(edict_t *self, float dist);
void plastic_helicopter_face(edict_t *self, float dist);
void plastic_helicopter_machineguns(edict_t *self);
void plastic_helicopter_rockets(edict_t *self);
void plastic_helicopter_finish_attack(edict_t *self);
void plastic_helicopter_crash_fall_think(edict_t *self);
void plastic_helicopter_crash_burst_think(edict_t *self);

static mframe_t helicopter_frames_stand[] = {
	{plastic_helicopter_idle, 0, NULL},
	{plastic_helicopter_idle, 0, NULL},
	{plastic_helicopter_idle, 0, NULL},
	{plastic_helicopter_idle, 0, NULL}
};
mmove_t plastic_helicopter_move_stand = {
	0, 3, helicopter_frames_stand, NULL
};

static mframe_t helicopter_frames_run[] = {
	{plastic_helicopter_hover, 8, NULL},
	{plastic_helicopter_hover, 8, NULL},
	{plastic_helicopter_hover, 8, NULL},
	{plastic_helicopter_hover, 8, NULL}
};
mmove_t plastic_helicopter_move_run = {
	4, 7, helicopter_frames_run, NULL
};

static mframe_t helicopter_frames_machinegun[] = {
	{plastic_helicopter_face, 0, NULL},
	{plastic_helicopter_face, 0, NULL},
	{plastic_helicopter_face, 0, plastic_helicopter_machineguns},
	{plastic_helicopter_face, 0, plastic_helicopter_machineguns},
	{plastic_helicopter_face, 0, plastic_helicopter_machineguns},
	{plastic_helicopter_face, 0, plastic_helicopter_machineguns},
	{plastic_helicopter_face, 0, NULL},
	{plastic_helicopter_face, 0, NULL}
};
mmove_t plastic_helicopter_move_machinegun = {
	8, 15, helicopter_frames_machinegun, plastic_helicopter_finish_attack
};

static mframe_t helicopter_frames_rocket[] = {
	{plastic_helicopter_face, 0, NULL},
	{plastic_helicopter_face, 0, NULL},
	{plastic_helicopter_face, 0, NULL},
	{plastic_helicopter_face, 0, NULL},
	{plastic_helicopter_face, 0, plastic_helicopter_rockets},
	{plastic_helicopter_face, 0, NULL},
	{plastic_helicopter_face, 0, NULL},
	{plastic_helicopter_face, 0, NULL}
};
mmove_t plastic_helicopter_move_rocket = {
	16, 23, helicopter_frames_rocket, plastic_helicopter_finish_attack
};

static mframe_t helicopter_frames_pain[] = {
	{plastic_helicopter_face, 0, NULL},
	{plastic_helicopter_face, 0, NULL},
	{plastic_helicopter_face, 0, NULL},
	{plastic_helicopter_face, 0, NULL}
};
mmove_t plastic_helicopter_move_pain = {
	24, 27, helicopter_frames_pain, plastic_helicopter_run
};

static qboolean
helicopter_live_enemy(edict_t *self)
{
	return self && self->inuse && self->health > 0 &&
		self->deadflag != DEAD_DEAD && !(self->svflags & SVF_NOCLIENT) &&
		self->enemy && self->enemy->inuse && self->enemy->health > 0;
}

static void
helicopter_project(edict_t *body, const vec3_t local, vec3_t projected)
{
	vec3_t forward, right, up;
	AngleVectors(body->s.angles, forward, right, up);
	VectorMA(body->s.origin, local[0], forward, projected);
	VectorMA(projected, -local[1], right, projected);
	VectorMA(projected, local[2], up, projected);
}

static void
helicopter_transform_direction(edict_t *body, const vec3_t local, vec3_t projected)
{
	vec3_t forward, right, up;
	AngleVectors(body->s.angles, forward, right, up);
	VectorScale(forward, local[0], projected);
	VectorMA(projected, -local[1], right, projected);
	VectorMA(projected, local[2], up, projected);
}

static float
helicopter_angle_delta(float angle, float previous)
{
	float delta = anglemod(angle) - anglemod(previous);
	if (delta > 180)
	{
		delta -= 360;
	}
	if (delta < -180)
	{
		delta += 360;
	}
	return delta;
}

/* Compose the body tilt with the rotor's own axis instead of adding Euler
 * angles. In particular the tail rotor keeps its sideways axle during a crash. */
static void
helicopter_rotor_angles(edict_t *rotor, edict_t *body)
{
	vec3_t local, forward, right, world_forward, world_right, base_right, base_up;
	vec3_t angles, alternate;
	float primary_distance = 0, alternate_distance = 0, delta;
	int i;
	VectorClear(local);
	local[rotor->style ? PITCH : YAW] = rotor->speed;
	AngleVectors(local, forward, right, NULL);
	helicopter_transform_direction(body, forward, world_forward);
	helicopter_transform_direction(body, right, world_right);
	vectoangles(world_forward, angles);
	angles[ROLL] = 0;
	AngleVectors(angles, NULL, base_right, base_up);
	angles[ROLL] = atan2f(-DotProduct(world_right, base_up),
		DotProduct(world_right, base_right)) * (180.0f / M_PI);
	/* vectoangles folds pitch at +/-90 degrees. Select the equivalent Euler
	 * branch nearest the previous snapshot so the tail rotor interpolates
	 * through its sideways rotation instead of flipping yaw and roll by 180. */
	VectorSet(alternate, 180 - angles[PITCH], angles[YAW] + 180, angles[ROLL] + 180);
	for (i = 0; i < 3; i++)
	{
		delta = helicopter_angle_delta(angles[i], rotor->s.angles[i]);
		primary_distance += delta * delta;
		delta = helicopter_angle_delta(alternate[i], rotor->s.angles[i]);
		alternate_distance += delta * delta;
	}
	for (i = 0; i < 3; i++)
	{
		rotor->s.angles[i] = anglemod(alternate_distance < primary_distance ?
			alternate[i] : angles[i]);
	}
}

void
plastic_helicopter_rotor_think(edict_t *rotor)
{
	edict_t *body;
	vec3_t pivot;
	float power = 1;
	if (!rotor)
	{
		return;
	}
	body = rotor->owner;
	/* The pointer relationship also rejects an owner slot reused by a new enemy. */
	if (!body || !body->inuse || !body->classname ||
		strcmp(body->classname, "monster_plastic_helicopter") || !body->chain ||
		(!rotor->style && body->chain != rotor) ||
		(rotor->style && body->chain->chain != rotor))
	{
		G_FreeEdict(rotor);
		return;
	}
	rotor->svflags = body->svflags & SVF_NOCLIENT;
	if (body->deadflag == DEAD_DEAD)
	{
		power = Q_clamp(1 - (level.time - body->pain_debounce_time) / 2.5f, .12f, 1);
	}
	if (!(rotor->svflags & SVF_NOCLIENT))
	{
		rotor->speed = anglemod(rotor->speed + (rotor->style ? 114 : 66) * power);
	}
	if (rotor->style)
	{
		VectorSet(pivot, -88, 8, 16);
	}
	else
	{
		VectorSet(pivot, 0, 0, 48);
	}
	helicopter_project(body, pivot, rotor->s.origin);
	helicopter_rotor_angles(rotor, body);
	rotor->nextthink = level.time + FRAMETIME;
	gi.linkentity(rotor);
}

static qboolean
helicopter_step(edict_t *self, float yaw, float distance, float dz)
{
	vec3_t target;
	trace_t tr;
	float radians = yaw * (M_PI / 180.0f);
	VectorCopy(self->s.origin, target);
	target[0] += cosf(radians) * distance;
	target[1] += sinf(radians) * distance;
	target[2] += dz;
	tr = gi.trace(self->s.origin, self->mins, self->maxs, target,
		self, MASK_MONSTERSOLID);
	if (tr.startsolid || tr.allsolid || tr.fraction < 1)
	{
		return false;
	}
	/* Keep flying monsters from voluntarily entering water or lava. */
	target[2] += self->mins[2] + 1;
	if (gi.pointcontents(target) & MASK_WATER)
	{
		return false;
	}
	VectorCopy(tr.endpos, self->s.origin);
	self->groundentity = NULL;
	gi.linkentity(self);
	G_TouchTriggers(self);
	return true;
}

void
plastic_helicopter_stand(edict_t *self)
{
	self->monsterinfo.currentmove = &plastic_helicopter_move_stand;
}

void
plastic_helicopter_walk(edict_t *self)
{
	self->monsterinfo.currentmove = &plastic_helicopter_move_run;
}

void
plastic_helicopter_run(edict_t *self)
{
	self->monsterinfo.currentmove = (self->monsterinfo.aiflags & AI_STAND_GROUND) ?
		&plastic_helicopter_move_stand : &plastic_helicopter_move_run;
}

void
plastic_helicopter_idle(edict_t *self, float dist)
{
	float height;
	ai_stand(self, 0);
	if (!self->inuse || self->deadflag == DEAD_DEAD)
	{
		return;
	}
	height = self->pos1[2] + sinf(level.time * 2) * 3;
	helicopter_step(self, 0, 0, Q_clamp(height - self->s.origin[2], -1, 1));
}

void
plastic_helicopter_face(edict_t *self, float dist)
{
	vec3_t direction;
	if (helicopter_live_enemy(self) && visible(self, self->enemy))
	{
		VectorSubtract(self->enemy->s.origin, self->s.origin, direction);
		self->ideal_yaw = vectoyaw(direction);
		M_ChangeYaw(self);
	}
	self->s.angles[PITCH] *= .65f;
	self->s.angles[ROLL] *= .65f;
}

void
plastic_helicopter_hover(edict_t *self, float dist)
{
	vec3_t direction;
	float range, yaw, dz, height;
	qboolean seen;
	if (!self || self->health <= 0 || self->deadflag == DEAD_DEAD ||
		(self->svflags & SVF_NOCLIENT))
	{
		return;
	}
	if (!helicopter_live_enemy(self))
	{
		if (self->movetarget)
		{
			self->enemy = NULL;
			self->goalentity = self->movetarget;
			ai_walk(self, dist);
		}
		else
		{
			ai_run(self, dist);
		}
		return;
	}
	if (ai_checkattack(self))
	{
		return;
	}
	seen = visible(self, self->enemy);
	if (seen)
	{
		VectorCopy(self->enemy->s.origin, self->monsterinfo.last_sighting);
		self->monsterinfo.aiflags &= ~AI_LOST_SIGHT;
	}
	VectorSubtract(self->monsterinfo.last_sighting, self->s.origin, direction);
	direction[2] = 0;
	range = VectorLength(direction);
	self->ideal_yaw = vectoyaw(direction);
	M_ChangeYaw(self);
	yaw = self->ideal_yaw;
	height = Q_clamp(self->enemy->s.origin[2] + self->enemy->viewheight + 144,
		self->pos1[2] - 48, self->pos1[2] + 160);
	dz = Q_clamp(height + sinf(level.time * 2) * 4 - self->s.origin[2], -5, 5);
	self->s.angles[ROLL] *= .7f;
	self->s.angles[PITCH] *= .7f;
	if (seen && range < 300)
	{
		yaw += 180;
		self->s.angles[PITCH] = -4;
	}
	else if (seen && range < 650)
	{
		yaw += self->monsterinfo.lefty ? 90 : -90;
		self->s.angles[ROLL] = self->monsterinfo.lefty ? -6 : 6;
	}
	else
	{
		self->s.angles[PITCH] = 4;
	}
	if (!helicopter_step(self, yaw, dist, dz))
	{
		self->monsterinfo.lefty = !self->monsterinfo.lefty;
		/* Allow climbing under an obstruction before trying the opposite flank. */
		if (!helicopter_step(self, yaw + 180, dist, dz))
		{
			helicopter_step(self, yaw, 0, dz);
		}
	}
}

/* Trace both the path from the body to the real muzzle and the complete shot.
 * The rotating model's local Y is the opposite of G_ProjectSource's right. */
static qboolean
helicopter_shot(edict_t *self, int side, qboolean rocket,
		vec3_t start, vec3_t direction)
{
	vec3_t local, target, forward;
	trace_t tr;
	float distance;
	if (!helicopter_live_enemy(self) || !visible(self, self->enemy))
	{
		return false;
	}
	VectorSet(local, rocket ? 30 : 64, side * (rocket ? 46 : 24), rocket ? -2 : -10);
	helicopter_project(self, local, start);
	VectorCopy(self->enemy->s.origin, target);
	target[2] += self->enemy->viewheight;
	VectorSubtract(target, start, direction);
	distance = VectorNormalize(direction);
	AngleVectors(self->s.angles, forward, NULL, NULL);
	if (distance < (rocket ? 320 : 48) || distance > 1800 ||
		DotProduct(direction, forward) < (rocket ? .80f : .65f))
	{
		return false;
	}
	tr = gi.trace(self->s.origin, NULL, NULL, start, self, MASK_SHOT);
	if (tr.startsolid || tr.allsolid || tr.fraction < 1)
	{
		return false;
	}
	tr = gi.trace(start, NULL, NULL, target, self, MASK_SHOT);
	return !tr.startsolid && !tr.allsolid && (tr.fraction == 1 || tr.ent == self->enemy);
}

void
plastic_helicopter_machineguns(edict_t *self)
{
	vec3_t start, direction;
	if (helicopter_shot(self, 1, false, start, direction))
	{
		monster_fire_bullet(self, start, direction, 5, 3,
			DEFAULT_BULLET_HSPREAD, DEFAULT_BULLET_VSPREAD,
			MZ2_HELICOPTER_MACHINEGUN_L);
	}
	if (helicopter_shot(self, -1, false, start, direction))
	{
		monster_fire_bullet(self, start, direction, 5, 3,
			DEFAULT_BULLET_HSPREAD, DEFAULT_BULLET_VSPREAD,
			MZ2_HELICOPTER_MACHINEGUN_R);
	}
}

void
plastic_helicopter_rockets(edict_t *self)
{
	vec3_t left, right, left_direction, right_direction;
	/* A defeated salvo stays defeated, including on a held animation frame. */
	if (!self || !self->count)
	{
		return;
	}
	self->count = 0;
	if (!helicopter_shot(self, 1, true, left, left_direction) ||
		!helicopter_shot(self, -1, true, right, right_direction))
	{
		return;
	}
	monster_fire_rocket(self, left, left_direction, 40, 600, MZ2_HELICOPTER_ROCKET_L);
	monster_fire_rocket(self, right, right_direction, 40, 600, MZ2_HELICOPTER_ROCKET_R);
}

void
plastic_helicopter_finish_attack(edict_t *self)
{
	self->monsterinfo.attack_finished = level.time + 1.3f;
	plastic_helicopter_run(self);
}

void
plastic_helicopter_attack(edict_t *self)
{
	vec3_t start, direction;
	qboolean rockets;
	if (!helicopter_live_enemy(self) ||
		level.time < self->monsterinfo.attack_finished ||
		self->monsterinfo.currentmove == &plastic_helicopter_move_machinegun ||
		self->monsterinfo.currentmove == &plastic_helicopter_move_rocket)
	{
		return;
	}
	rockets = level.time >= self->wait &&
		helicopter_shot(self, 1, true, start, direction) &&
		helicopter_shot(self, -1, true, start, direction);
	if (!rockets && !helicopter_shot(self, 1, false, start, direction) &&
		!helicopter_shot(self, -1, false, start, direction))
	{
		return;
	}
	self->monsterinfo.currentmove = rockets ? &plastic_helicopter_move_rocket :
		&plastic_helicopter_move_machinegun;
	self->monsterinfo.attack_state = AS_STRAIGHT;
	self->monsterinfo.attack_finished = level.time + 1;
	self->count = rockets ? 1 : 0;
	if (rockets)
	{
		self->wait = level.time + 4.5f;
	}
	VectorClear(self->velocity);
}

qboolean
plastic_helicopter_checkattack(edict_t *self)
{
	mmove_t *before;
	if (!self)
	{
		return false;
	}
	before = self->monsterinfo.currentmove;
	plastic_helicopter_attack(self);
	return self->monsterinfo.currentmove != before;
}

void
plastic_helicopter_pain(edict_t *self, edict_t *other, float kick, int damage)
{
	if (self->deadflag == DEAD_DEAD || damage < 30 || level.time < self->pain_debounce_time)
	{
		return;
	}
	self->pain_debounce_time = level.time + 2;
	gi.sound(self, CHAN_VOICE, gi.soundindex("bosshovr/bhvpain1.wav"), 1, ATTN_NORM, 0);
	if (skill->value < SKILL_HARDPLUS)
	{
		self->count = 0;
		self->monsterinfo.attack_finished = level.time + 1;
		self->monsterinfo.currentmove = &plastic_helicopter_move_pain;
	}
}

static void
helicopter_crash_explosion(edict_t *self, float x, float y, float z)
{
	vec3_t local, origin;
	VectorSet(local, x + crandom() * 12, y + crandom() * 12, z);
	helicopter_project(self, local, origin);
	gi.WriteByte(svc_temp_entity);
	gi.WriteByte(TE_EXPLOSION1);
	gi.WritePosition(origin);
	gi.multicast(self->s.origin, MULTICAST_PVS);
}

static void
helicopter_free_rotors(edict_t *self)
{
	edict_t *main = self->chain, *tail;
	if (!main || !main->inuse || main->owner != self)
	{
		self->chain = NULL;
		return;
	}
	tail = main->chain;
	if (tail && tail->inuse && tail->owner == self)
	{
		G_FreeEdict(tail);
	}
	G_FreeEdict(main);
	self->chain = NULL;
}

static void
helicopter_begin_crash_burst(edict_t *self)
{
	self->s.sound = 0;
	self->solid = SOLID_NOT;
	self->movetype = MOVETYPE_NONE;
	self->touch = NULL;
	VectorClear(self->velocity);
	VectorClear(self->avelocity);
	self->count = 0;
	self->think = plastic_helicopter_crash_burst_think;
	self->nextthink = level.time + FRAMETIME;
	gi.linkentity(self);
}

void
plastic_helicopter_crash_burst_think(edict_t *self)
{
	helicopter_crash_explosion(self, 14, 20, 12);
	helicopter_crash_explosion(self, -18, -22, 16);
	if (!(self->count & 1))
	{
		helicopter_crash_explosion(self, 0, 0, 28);
	}
	if (++self->count >= 4)
	{
		helicopter_free_rotors(self);
		G_FreeEdict(self);
		return;
	}
	self->nextthink = level.time + FRAMETIME;
}

void
plastic_helicopter_crash_touch(edict_t *self, edict_t *other,
		cplane_t *plane, csurface_t *surface)
{
	/* Contact with any solid ends the fall; a deep void uses the timeout. */
	if (self->deadflag == DEAD_DEAD && other && other->solid != SOLID_TRIGGER)
	{
		helicopter_begin_crash_burst(self);
	}
}

void
plastic_helicopter_crash_fall_think(edict_t *self)
{
	if (level.time >= self->delay)
	{
		helicopter_crash_explosion(self, -12, 0, 24);
		self->delay = level.time + .2f;
	}
	if (self->groundentity || level.time >= self->wait)
	{
		helicopter_begin_crash_burst(self);
		return;
	}
	self->nextthink = level.time + FRAMETIME;
}

void
plastic_helicopter_die(edict_t *self, edict_t *inflictor, edict_t *attacker,
		int damage, vec3_t point)
{
	if (self->deadflag == DEAD_DEAD)
	{
		return;
	}
	self->deadflag = DEAD_DEAD;
	self->takedamage = DAMAGE_NO;
	self->count = 0;
	self->s.sound = 0;
	self->s.frame = 28;
	self->flags &= ~FL_FLY;
	self->svflags |= SVF_DEADMONSTER;
	self->movetype = MOVETYPE_TOSS;
	self->groundentity = NULL;
	self->velocity[2] = -120;
	VectorSet(self->avelocity, 18, 24, 25);
	self->pain_debounce_time = level.time;
	self->delay = level.time;
	self->wait = level.time + 2.5f;
	self->touch = plastic_helicopter_crash_touch;
	self->think = plastic_helicopter_crash_fall_think;
	self->nextthink = level.time + FRAMETIME;
	gi.sound(self, CHAN_VOICE, gi.soundindex("bosshovr/bhvdeth1.wav"), 1, ATTN_NORM, 0);
	gi.linkentity(self);
}

/* QUAKED monster_plastic_helicopter (0.76 0.62 0.39) (-72 -56 -32) (72 56 48) Ambush Trigger_Spawn Sight
 * Tan molded toy helicopter, 500 health. Four paired machinegun shots per
 * burst; two rockets per salvo. Place airborne with room for 184-unit rotors.
 * Crashes under gravity, then explodes on contact. Supports normal triggers.
 */
void
SP_monster_plastic_helicopter(edict_t *self)
{
	edict_t *main, *tail;
	if (deathmatch->value)
	{
		G_FreeEdict(self);
		return;
	}
	self->movetype = MOVETYPE_STEP;
	self->solid = SOLID_BBOX;
	self->s.modelindex = gi.modelindex("models/monsters/plastic_helicopter/body.md2");
	VectorSet(self->mins, -72, -56, -32);
	VectorSet(self->maxs, 72, 56, 48);
	VectorCopy(self->s.origin, self->pos1);
	VectorCopy(self->s.origin, self->monsterinfo.last_sighting);
	self->health = 500;
	self->gib_health = -200;
	self->mass = 500;
	self->yaw_speed = 7;
	self->viewheight = 16;
	self->flags |= FL_NO_KNOCKBACK;
	self->monsterinfo.scale = 1;
	self->monsterinfo.lefty = randk() & 1;
	self->pain = plastic_helicopter_pain;
	self->die = plastic_helicopter_die;
	self->monsterinfo.stand = plastic_helicopter_stand;
	self->monsterinfo.walk = plastic_helicopter_walk;
	self->monsterinfo.run = plastic_helicopter_run;
	self->monsterinfo.attack = plastic_helicopter_attack;
	self->monsterinfo.checkattack = plastic_helicopter_checkattack;
	self->s.sound = gi.soundindex("bosshovr/bhvengn1.wav");
	gi.soundindex("bosshovr/bhvpain1.wav");
	gi.soundindex("bosshovr/bhvdeth1.wav");
	gi.soundindex("weapons/machgf1b.wav");
	gi.soundindex("weapons/rocklf1a.wav");
	gi.soundindex("weapons/rockfly.wav");
	gi.soundindex("weapons/rocklr1b.wav");
	gi.modelindex("models/objects/rocket/tris.md2");
	plastic_helicopter_stand(self);
	gi.linkentity(self);
	flymonster_start(self);

	main = G_Spawn();
	tail = G_Spawn();
	self->chain = main;
	main->chain = tail;
	main->classname = "plastic_helicopter_main_rotor";
	tail->classname = "plastic_helicopter_tail_rotor";
	main->owner = tail->owner = self;
	main->style = 0;
	tail->style = 1;
	main->movetype = tail->movetype = MOVETYPE_NONE;
	main->solid = tail->solid = SOLID_NOT;
	main->s.modelindex = gi.modelindex("models/monsters/plastic_helicopter/main_rotor.md2");
	tail->s.modelindex = gi.modelindex("models/monsters/plastic_helicopter/tail_rotor.md2");
	main->think = tail->think = plastic_helicopter_rotor_think;
	/* Hide all three pieces immediately for trigger-spawned helicopters. */
	if (self->spawnflags & 2)
	{
		self->svflags |= SVF_NOCLIENT;
	}
	plastic_helicopter_rotor_think(main);
	plastic_helicopter_rotor_think(tail);
	VectorCopy(main->s.origin, main->s.old_origin);
	VectorCopy(tail->s.origin, tail->s.old_origin);
}
