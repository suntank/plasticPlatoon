/* Shared organic gib burst for the giant ant and spider. */
#ifndef PP_INSECT_GIBS_H
#define PP_INSECT_GIBS_H

static void
InsectPrecacheGibs(qboolean spider)
{
	gi.modelindex(spider ? "models/objects/gibs/spider/chunk.md2" : "models/objects/gibs/ant/chunk.md2");
	gi.modelindex(spider ? "models/objects/gibs/spider/leg.md2" : "models/objects/gibs/ant/leg.md2");
	gi.soundindex("misc/udeath.wav");
}

static void
InsectGib(edict_t *self, int damage, qboolean spider)
{
	char *chunk = spider ? "models/objects/gibs/spider/chunk.md2" : "models/objects/gibs/ant/chunk.md2";
	char *leg = spider ? "models/objects/gibs/spider/leg.md2" : "models/objects/gibs/ant/leg.md2";
	vec3_t direction;
	int i;

	gi.sound(self, CHAN_VOICE, gi.soundindex("misc/udeath.wav"), 1, ATTN_NORM, 0);
	/* Multiple outward blood sprays give the rupturing shell a wet burst. */
	for (i = 0; i < 4; i++)
	{
		VectorSet(direction, crandom(), crandom(), .5 + random());
		VectorNormalize(direction);
		gi.WriteByte(svc_temp_entity);
		gi.WriteByte(TE_BLOOD);
		gi.WritePosition(self->s.origin);
		gi.WriteDir(direction);
		gi.multicast(self->s.origin, MULTICAST_PVS);
	}
	for (i = 0; i < (spider ? 4 : 3); i++)
		ThrowGib(self, chunk, damage, GIB_ORGANIC);
	for (i = 0; i < (spider ? 6 : 4); i++)
		ThrowGib(self, leg, damage, GIB_ORGANIC);
	ThrowHead(self, chunk, damage, GIB_ORGANIC);
	self->deadflag = DEAD_DEAD;
}
#endif
