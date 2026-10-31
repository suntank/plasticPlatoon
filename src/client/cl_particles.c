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
 * This file implements all generic particle stuff
 *
 * =======================================================================
 */

#include "header/client.h"

cparticle_t *active_particles, *free_particles;
cparticle_t particles[MAX_PARTICLES];
int cl_numparticles = MAX_PARTICLES;

cl_effect_stats_t cl_effect_stats;
unsigned int cl_particle_view_mask = ~0u;
static particle_t prepared_particles[MAX_PARTICLES];
static unsigned int prepared_view_masks[MAX_PARTICLES];
static int prepared_particle_count;
static int shared_effect_frame = -1;
static int shared_effect_time;

const cl_effect_stats_t *
CL_GetEffectStats(void)
{
	return &cl_effect_stats;
}

cparticle_t *
CL_AllocParticle(void)
{
	cparticle_t *p = free_particles;
	if (!p)
	{
		return NULL;
	}
	free_particles = p->next;
	p->next = active_particles;
	active_particles = p;
	p->view_mask = cl_particle_view_mask;
	if (cl_effect_only_slot)
	{
		p->view_mask &= 1u << (cl_effect_only_slot - 1);
	}
	if (cl_effect_exclude_slot)
	{
		p->view_mask &= ~(1u << (cl_effect_exclude_slot - 1));
	}
	++cl_effect_stats.particles_created;
	++cl_effect_stats.active_particles;
	return p;
}

/* Rendering any additional viewport or stereo eye is read-only. A paused
 * scene retains the complete prepared output, including instant particles. */
qboolean
CL_BeginSharedEffects(void)
{
	if (shared_effect_frame == cls.framecount)
	{
		return false;
	}
	if (shared_effect_frame >= 0 && cl_paused && cl_paused->value &&
		shared_effect_time == cl.time)
	{
		shared_effect_frame = cls.framecount;
		return false;
	}
	shared_effect_frame = cls.framecount;
	shared_effect_time = cl.time;
	++cl_effect_stats.shared_preparations;
	CL_ResetEntityEffectQueue();
	return true;
}

void
CL_ClearParticles(void)
{
	int i;

	prepared_particle_count = 0;
	shared_effect_frame = -1;
	cl_particle_view_mask = ~0u;
	cl_effect_stats.active_particles = 0;
	cl_effect_stats.prepared_particles = 0;

	cl_numparticles = Q_clamp(cl_numparticles, 0, MAX_PARTICLES);
	active_particles = free_particles = NULL;
	if (cl_numparticles == 0)
	{
		return;
	}
	free_particles = &particles[0];

	for (i = 0; i < cl_numparticles; i++)
	{
		particles[i].next = &particles[i + 1];
	}

	particles[cl_numparticles - 1].next = NULL;
}

void
CL_ParticleEffect(vec3_t org, vec3_t dir, int color, int count)
{
	int i, j;
	cparticle_t *p;
	float d;

	for (i = 0; i < count; i++)
	{
		if (!free_particles)
		{
			return;
		}

		p = CL_AllocParticle();

		p->time = cl.time;
		p->color = color + (randk() & 7);
		d = randk() & 31;

		for (j = 0; j < 3; j++)
		{
			p->org[j] = org[j] + ((randk() & 7) - 4) + d * dir[j];
			p->vel[j] = crandk() * 20;
		}

		p->accel[0] = p->accel[1] = 0;
		p->accel[2] = -PARTICLE_GRAVITY + 0.2f;
		p->alpha = 1.0;

		p->alphavel = -1.0 / (0.5 + frandk() * 0.3);
	}
}

void
CL_ParticleEffect2(vec3_t org, vec3_t dir, int color, int count)
{
	int i, j;
	cparticle_t *p;
	float d;
	float time;

	time = (float)cl.time;

	for (i = 0; i < count; i++)
	{
		if (!free_particles)
		{
			return;
		}

		p = CL_AllocParticle();

		p->time = time;
		p->color = color + (randk() & 7);

		d = randk() & 7;

		for (j = 0; j < 3; j++)
		{
			p->org[j] = org[j] + ((randk() & 7) - 4) + d * dir[j];
			p->vel[j] = crandk() * 20;
		}

		p->accel[0] = p->accel[1] = 0;
		p->accel[2] = -PARTICLE_GRAVITY;
		p->alpha = 1.0;

		p->alphavel = -1.0f / (0.5f + frandk() * 0.3f);
	}
}

void
CL_ParticleEffect3(vec3_t org, vec3_t dir, int color, int count)
{
	int i, j;
	cparticle_t *p;
	float d;
	float time;

	time = (float)cl.time;

	for (i = 0; i < count; i++)
	{
		if (!free_particles)
		{
			return;
		}

		p = CL_AllocParticle();

		p->time = time;
		p->color = color;

		d = randk() & 7;

		for (j = 0; j < 3; j++)
		{
			p->org[j] = org[j] + ((randk() & 7) - 4) + d * dir[j];
			p->vel[j] = crandk() * 20;
		}

		p->accel[0] = p->accel[1] = 0;
		p->accel[2] = PARTICLE_GRAVITY;
		p->alpha = 1.0;

		p->alphavel = -1.0f / (0.5f + frandk() * 0.3f);
	}
}

void
CL_PrepareParticles(void)
{
	cparticle_t *p, *next;
	float alpha;
	float time, time2;
	vec3_t org;
	int color;
	cparticle_t *active, *tail;

	active = NULL;
	tail = NULL;
	prepared_particle_count = 0;

	for (p = active_particles; p; p = next)
	{
		next = p->next;
		++cl_effect_stats.particle_updates;

		if (p->alphavel != INSTANT_PARTICLE)
		{
			time = (cl.time - p->time) * 0.001;
			alpha = p->alpha + time * p->alphavel;

			if (alpha <= 0)
			{
				/* faded out */
				p->next = free_particles;
				free_particles = p;
				++cl_effect_stats.particles_expired;
				--cl_effect_stats.active_particles;
				continue;
			}
		}
		else
		{
			time = 0.0f;
			alpha = p->alpha;
		}

		p->next = NULL;

		if (!tail)
		{
			active = tail = p;
		}

		else
		{
			tail->next = p;
			tail = p;
		}

		if (alpha > 1.0f)
		{
			alpha = 1;
		}

		color = p->color;
		time2 = time * time;

		org[0] = p->org[0] + p->vel[0] * time + p->accel[0] * time2;
		org[1] = p->org[1] + p->vel[1] * time + p->accel[1] * time2;
		org[2] = p->org[2] + p->vel[2] * time + p->accel[2] * time2;

		if (prepared_particle_count < MAX_PARTICLES)
		{
			particle_t *out = &prepared_particles[prepared_particle_count];
			VectorCopy(org, out->origin);
			out->color = color;
			out->alpha = alpha;
			prepared_view_masks[prepared_particle_count++] = p->view_mask;
		}

		if (p->alphavel == INSTANT_PARTICLE)
		{
			p->alphavel = 0.0;
			p->alpha = 0.0;
		}
	}

	active_particles = active;
	cl_effect_stats.prepared_particles = prepared_particle_count;
}

void
CL_AddParticles(void)
{
	int i;
	unsigned int mask = cl_effect_render_slot < 0 ? ~0u :
		1u << cl_effect_render_slot;

	for (i = 0; i < prepared_particle_count; ++i)
	{
		particle_t *p = &prepared_particles[i];
		if (prepared_view_masks[i] & mask)
		{
			V_AddParticle(p->origin, p->color, p->alpha);
		}
	}
}

void
CL_GenericParticleEffect(vec3_t org, vec3_t dir, int color,
		int count, int numcolors, int dirspread, float alphavel)
{
	int i, j;
	cparticle_t *p;
	float d;
	float time;

	time = (float)cl.time;

	for (i = 0; i < count; i++)
	{
		if (!free_particles)
		{
			return;
		}

		p = CL_AllocParticle();

		p->time = time;

		if (numcolors > 1)
		{
			p->color = color + (randk() & numcolors);
		}

		else
		{
			p->color = color;
		}

		d = (float)(randk() & dirspread);

		for (j = 0; j < 3; j++)
		{
			p->org[j] = org[j] + ((randk() & 7) - 4) + d * dir[j];
			p->vel[j] = crandk() * 20;
		}

		p->accel[0] = p->accel[1] = 0;
		p->accel[2] = -PARTICLE_GRAVITY;
		p->alpha = 1.0;

		p->alphavel = -1.0f / (0.5f + frandk() * alphavel);
	}
}

