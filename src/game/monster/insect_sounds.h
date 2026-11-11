/* Shared, save-compatible sound playback for Plastic Platoon's insects. */
#ifndef PP_INSECT_SOUNDS_H
#define PP_INSECT_SOUNDS_H

typedef struct
{
	char *names[2];
	unsigned int next;
} insect_sound_t;

#define INSECT_SOUND(species, role) \
	{{species "/" role "_01.wav", species "/" role "_02.wav"}, 0}

enum
{
	INSECT_IDLE,
	INSECT_PAIN,
	INSECT_ATTACK,
	INSECT_SCUTTLE,
	INSECT_SIGHT
};

static void
InsectPrecacheSounds(insect_sound_t *sounds, size_t count)
{
	size_t i;
	for (i = 0; i < count; i++)
	{
		gi.soundindex(sounds[i].names[0]);
		gi.soundindex(sounds[i].names[1]);
	}
}

static void
InsectSound(edict_t *self, insect_sound_t *sound, int channel,
		float volume, float attenuation)
{
	if (self->health <= 0 || self->deadflag == DEAD_DEAD)
		return;

	/* Alternate takes per species/event without consuming the AI's random
	 * sequence. Cosmetic history can restart with a new game module. Resolve
	 * by name on playback, including when loading saves from an older build. */
	gi.sound(self, channel, gi.soundindex(sound->names[sound->next++ % 2]),
			volume, attenuation, 0);
}

static void
InsectScuttle(edict_t *self, const vec3_t before, insect_sound_t *sound,
		float volume)
{
	vec3_t moved;

	/* Combat texture, not the optional legacy footstep effect. The supplied
	 * clips are 1.2-second gait bursts, not footfalls or seamless loops. */
	if (self->health <= 0 || self->deadflag == DEAD_DEAD ||
			!self->enemy || !self->enemy->inuse || self->enemy->health <= 0 ||
			!self->groundentity || self->waterlevel > 1 ||
			(self->monsterinfo.aiflags & (AI_STAND_GROUND | AI_HOLD_FRAME)) ||
			level.time < self->last_move_time)
		return;

	VectorSubtract(self->s.origin, before, moved);
	moved[2] = 0;
	if (DotProduct(moved, moved) < 0.25f)
		return;

	/* This existing edict field is otherwise unused by ants/spiders and is
	 * already saved. No entity-layout or save-format change is needed. */
	self->last_move_time = level.time + 1.5f;
	InsectSound(self, sound, CHAN_BODY, volume, ATTN_NORM);
}
#endif
