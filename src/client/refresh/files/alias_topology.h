/* Immutable MD2 command topology, shared by GL1/GLES1 and GL3/GLES3.
 * Kept independent of OpenGL so the parser can be regression tested directly.
 * Copyright (C) 2026 Plastic Platoon contributors. GPL-2.0-or-later.
 */
#ifndef PP_ALIAS_TOPOLOGY_H
#define PP_ALIAS_TOPOLOGY_H

#include <limits.h>
#include <math.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

typedef struct pp_alias_topology_s
{
	unsigned num_vertices, num_indices;
	unsigned short *source;
	unsigned short *indices;
	float *uv;
} pp_alias_topology_t;

static inline void
PP_FreeAliasTopology(pp_alias_topology_t *mesh)
{
	if (!mesh) return;
	free(mesh->source);
	free(mesh->indices);
	free(mesh->uv);
	free(mesh);
}

static inline pp_alias_topology_t *
PP_BuildAliasTopology(const int *commands, size_t command_count, unsigned positions)
{
	size_t cursor = 0;
	unsigned nv = 0, ni = 0, vbase = 0, ibase = 0, unique = 0;
	unsigned *hash_table = NULL, hash_size = 1;
	unsigned short *expanded = NULL;
	int terminated = 0;
	pp_alias_topology_t *mesh;

	/* Validate before allocating or touching any coordinate/index payload. */
	while (cursor < command_count)
	{
		int primitive = commands[cursor++];
		unsigned n;
		if (!primitive) { terminated = 1; break; }
		if (primitive == INT_MIN) return NULL;
		n = primitive < 0 ? (unsigned)-primitive : (unsigned)primitive;
		if (n < 3 || n > 65535 || n > (command_count - cursor) / 3 ||
			nv > 65535 - n || ni > UINT_MAX - (n - 2) * 3) return NULL;
		for (unsigned i = 0; i < n; ++i)
		{
			float s, t;
			memcpy(&s, commands + cursor + i*3, sizeof(s));
			memcpy(&t, commands + cursor + i*3 + 1, sizeof(t));
			if (!isfinite(s) || !isfinite(t) || commands[cursor + i*3 + 2] < 0 ||
				(unsigned)commands[cursor + i*3 + 2] >= positions) return NULL;
		}
		nv += n;
		ni += (n - 2) * 3;
		cursor += n * 3;
	}
	if (!terminated || !nv || !ni) return NULL;
	mesh = (pp_alias_topology_t *)calloc(1, sizeof(*mesh));
	if (!mesh) return NULL;
	mesh->source = (unsigned short *)malloc(nv * sizeof(*mesh->source));
	mesh->indices = (unsigned short *)malloc(ni * sizeof(*mesh->indices));
	mesh->uv = (float *)malloc(nv * 2 * sizeof(*mesh->uv));
	if (!mesh->source || !mesh->indices || !mesh->uv)
	{
		PP_FreeAliasTopology(mesh);
		return NULL;
	}
	/* Commands often repeat an identical position/UV tuple in several strips.
	 * Merge only exact tuples: distinct UV seams always remain distinct. */
	while (hash_size < nv*2) hash_size <<= 1;
	hash_table = (unsigned *)calloc(hash_size, sizeof(*hash_table));
	expanded = (unsigned short *)malloc(nv*sizeof(*expanded));
	if (!hash_table || !expanded)
	{
		free(hash_table); free(expanded); PP_FreeAliasTopology(mesh); return NULL;
	}
	mesh->num_indices = ni;
	cursor = 0;
	while (commands[cursor])
	{
		int primitive = commands[cursor++];
		unsigned n = primitive < 0 ? (unsigned)-primitive : (unsigned)primitive;
		for (unsigned i = 0; i < n; ++i)
		{
			unsigned source = (unsigned)commands[cursor+2];
			unsigned hash = ((unsigned)commands[cursor] * 16777619u ^ (unsigned)commands[cursor+1]) * 16777619u ^ source;
			unsigned slot = hash & (hash_size-1), vertex;
			while (hash_table[slot])
			{
				vertex = hash_table[slot]-1;
				if (mesh->source[vertex] == source && !memcmp(mesh->uv+vertex*2, commands+cursor, 2*sizeof(float))) break;
				slot = (slot+1) & (hash_size-1);
			}
			if (!hash_table[slot])
			{
				vertex = unique++;
				memcpy(mesh->uv+vertex*2, commands+cursor, 2*sizeof(float));
				mesh->source[vertex] = (unsigned short)source;
				hash_table[slot] = vertex+1;
			}
			expanded[vbase+i] = (unsigned short)(hash_table[slot]-1);
			cursor += 3;
		}
		for (unsigned i = 0; i < n-2; ++i)
		{
			mesh->indices[ibase++] = expanded[vbase + (primitive < 0 ? 0 : i)];
			mesh->indices[ibase++] = expanded[vbase + i + (primitive > 0 && (i&1) ? 2 : 1)];
			mesh->indices[ibase++] = expanded[vbase + i + (primitive > 0 && (i&1) ? 1 : 2)];
		}
		vbase += n;
	}
	free(expanded); free(hash_table);
	mesh->num_vertices = unique;
	unsigned short *source = (unsigned short *)realloc(mesh->source, unique*sizeof(*mesh->source));
	float *uv = (float *)realloc(mesh->uv, unique*2*sizeof(*mesh->uv));
	if (source) mesh->source = source;
	if (uv) mesh->uv = uv;
	return mesh;
}

#endif
