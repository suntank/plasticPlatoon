/* Prepared client-array colors for immutable one-frame MD2 poses.
 * LightPoint and every lighting modifier still run before this lookup.
 * This header is included once by gl1_mesh.c; no shared object layouts change.
 */
#define ALIAS_COLOR_BYTES (512u * 1024u)
#define ALIAS_COLOR_KEYS 128u
typedef struct
{
	const model_t *model;
	const pp_alias_topology_t *mesh;
	const dtrivertx_t *verts;
	const float *dots;
	uint64_t epoch;
	uint32_t light[3], alpha;
	unsigned vertices, color_only, minimum;
} alias_color_key_t;
typedef struct
{
	alias_color_key_t key;
	unsigned offset;
	qboolean valid;
} alias_color_entry_t;
static alias_color_entry_t alias_color_entries[ALIAS_COLOR_KEYS];
static byte alias_color_bytes[ALIAS_COLOR_BYTES];
static unsigned alias_color_used;
static uint64_t alias_color_epoch = 1;
/* Read-only native QA can locate these symbols without a diagnostic UI. */
uint64_t pp_alias_color_hits, pp_alias_color_misses;

/* Animated MD2 colors also use only a byte normal index. Cache that small
 * palette independently of geometry, frame and UV seams. Exact lighting inputs
 * are keys; each caller still samples current static/dynamic lighting first. */
#define ALIAS_NORMAL_KEYS 64u
typedef struct
{
	const float *dots;
	uint32_t light[3], alpha;
	unsigned minimum, color_only;
} alias_normal_key_t;
typedef struct
{
	alias_normal_key_t key;
	byte colors[256][4];
	byte ready[256];
	qboolean valid;
} alias_normal_entry_t;
static alias_normal_entry_t alias_normal_entries[ALIAS_NORMAL_KEYS];
uint64_t pp_alias_normal_hits, pp_alias_normal_misses;
uint64_t pp_alias_normal_evaluations;

static alias_normal_entry_t *
R_AliasNormalPalette(float alpha, qboolean color_only)
{
	if (!r_gl1_normal_colors || !r_gl1_normal_colors->value || !isfinite(alpha) ||
		!isfinite(shadelight[0]) || !isfinite(shadelight[1]) || !isfinite(shadelight[2])) return NULL;
	alias_normal_key_t key;
	memset(&key, 0, sizeof(key));
	key.dots = shadedots;
	memcpy(key.light, shadelight, sizeof(key.light));
	memcpy(&key.alpha, &alpha, sizeof(key.alpha));
	key.minimum = !!gl_state.minlight_set; key.color_only = !!color_only;
	uint32_t hash = (uint32_t)((uintptr_t)key.dots >> 4);
	for (unsigned i = 0; i < 3; ++i) hash = (hash ^ key.light[i]) * 16777619u;
	hash = (hash ^ key.alpha) * 16777619u;
	hash ^= key.minimum * 2246822519u ^ key.color_only * 3266489917u;
	/* Fold high float mantissa/exponent bits and shadedot-row addresses into
	 * the small table index, including common exactly representable lights. */
	hash ^= hash >> 16;
	hash *= 0x7feb352du;
	hash ^= hash >> 15;
	alias_normal_entry_t *entry = &alias_normal_entries[hash & (ALIAS_NORMAL_KEYS - 1u)];
	if (entry->valid && !memcmp(&entry->key, &key, sizeof(key)))
	{
		++pp_alias_normal_hits;
		return entry;
	}
	++pp_alias_normal_misses;
	entry->key = key;
	memset(entry->ready, 0, sizeof(entry->ready));
	entry->valid = true;
	return entry;
}

static const byte *
R_AliasNormalColor(alias_normal_entry_t *entry, unsigned normal, float alpha, qboolean color_only)
{
	if (!entry->ready[normal])
	{
		float brightness = color_only ? 1.0f : shadedots[normal];
		for (int c = 0; c < 3; ++c)
		{
			int value = brightness * shadelight[c] * 255;
			value = Q_clamp(value, 0, 255);
			entry->colors[normal][c] = gl_state.minlight_set ? minlight[value] : value;
		}
		entry->colors[normal][3] = alpha * 255;
		entry->ready[normal] = 1;
		++pp_alias_normal_evaluations;
	}
	return entry->colors[normal];
}

static void
R_ResetAliasPreparedColors(void)
{
	memset(alias_color_entries, 0, sizeof(alias_color_entries));
	alias_color_used = 0;
	++alias_color_epoch;
}

void
R_ClearAliasColorCache(void)
{
	R_ResetAliasPreparedColors();
	memset(alias_normal_entries, 0, sizeof(alias_normal_entries));
}

static unsigned
R_AliasColorHash(const alias_color_key_t *key)
{
	uintptr_t pointers = ((uintptr_t)key->model >> 4) ^
		((uintptr_t)key->mesh >> 4) ^ ((uintptr_t)key->verts >> 4) ^
		((uintptr_t)key->dots >> 4);
	uint32_t hash = (uint32_t)pointers;
	for (unsigned i = 0; i < 3; ++i) hash = (hash ^ key->light[i]) * 16777619u;
	hash = (hash ^ key->alpha) * 16777619u;
	hash ^= key->vertices * 2246822519u;
	hash ^= key->color_only * 3266489917u ^ key->minimum * 668265263u;
	return hash & (ALIAS_COLOR_KEYS - 1u);
}

static void
R_BuildAliasColors(byte *out, const pp_alias_topology_t *mesh,
	const dtrivertx_t *verts, float alpha, qboolean color_only)
{
	byte normal_colors[256][4];
	alias_normal_entry_t *palette = R_AliasNormalPalette(alpha, color_only);
	if (palette)
	{
		for (unsigned k = 0; k < mesh->num_vertices; ++k)
			memcpy(out + k*4, R_AliasNormalColor(palette,
				verts[mesh->source[k]].lightnormalindex, alpha, color_only), 4);
		return;
	}
	qboolean table = mesh->num_vertices >= 256;
	if (table)
	{
		for (unsigned normal = 0; normal < 256; ++normal)
		{
			float brightness = color_only ? 1.0f : shadedots[normal];
			for (int component = 0; component < 3; ++component)
			{
				int color = brightness * shadelight[component] * 255;
				color = Q_clamp(color, 0, 255);
				normal_colors[normal][component] = gl_state.minlight_set ? minlight[color] : color;
			}
			normal_colors[normal][3] = alpha * 255;
		}
	}
	for (unsigned k = 0; k < mesh->num_vertices; ++k)
	{
		unsigned normal = verts[mesh->source[k]].lightnormalindex;
		if (table) memcpy(out + k*4, normal_colors[normal], 4);
		else
		{
			float brightness = color_only ? 1.0f : shadedots[normal];
			for (int component = 0; component < 3; ++component)
			{
				int color = brightness * shadelight[component] * 255;
				color = Q_clamp(color, 0, 255);
				out[k*4+component] = gl_state.minlight_set ? minlight[color] : color;
			}
			out[k*4+3] = alpha * 255;
		}
	}
}

static const byte *
R_AliasPreparedColors(const model_t *model, const pp_alias_topology_t *mesh,
	const dtrivertx_t *verts, float alpha, qboolean color_only, qboolean static_pose)
{
	if (!r_gl1_alias_colors || !r_gl1_alias_colors->value || !static_pose ||
		gl_shadows->value || !mesh || !mesh->num_vertices ||
		mesh->num_vertices > MAX_VERTICES ||
		mesh->num_vertices > ALIAS_COLOR_BYTES / 4u)
		return NULL;
	/* Nonfinite values keep the original renderer path and its behavior. */
	if (!isfinite(alpha) || !isfinite(shadelight[0]) ||
		!isfinite(shadelight[1]) || !isfinite(shadelight[2])) return NULL;
	alias_color_key_t key;
	memset(&key, 0, sizeof(key));
	key.model = model; key.mesh = mesh; key.verts = verts; key.dots = shadedots;
	key.epoch = alias_color_epoch; key.vertices = mesh->num_vertices;
	key.color_only = !!color_only; key.minimum = !!gl_state.minlight_set;
	memcpy(key.light, shadelight, sizeof(key.light));
	memcpy(&key.alpha, &alpha, sizeof(key.alpha));
	unsigned slot = R_AliasColorHash(&key), probes;
	for (probes = 0; probes < ALIAS_COLOR_KEYS; ++probes,
		slot = (slot + 1u) & (ALIAS_COLOR_KEYS - 1u))
	{
		alias_color_entry_t *entry = &alias_color_entries[slot];
		if (!entry->valid) break;
		if (!memcmp(&entry->key, &key, sizeof(key)))
		{
			++pp_alias_color_hits;
			return alias_color_bytes + entry->offset;
		}
	}
	++pp_alias_color_misses;
	unsigned bytes = mesh->num_vertices * 4u;
	if (probes == ALIAS_COLOR_KEYS || bytes > ALIAS_COLOR_BYTES - alias_color_used)
	{
		/* The previous alias draw has already consumed its client arrays.
		 * Reset metadata only; never clear the half-MiB arena per draw. */
		R_ResetAliasPreparedColors();
		key.epoch = alias_color_epoch;
		slot = R_AliasColorHash(&key);
	}
	alias_color_entry_t *entry = &alias_color_entries[slot];
	entry->key = key; entry->offset = alias_color_used;
	byte *colors = alias_color_bytes + alias_color_used;
	R_BuildAliasColors(colors, mesh, verts, alpha, color_only);
	alias_color_used += bytes;
	entry->valid = true;
	return colors;
}
