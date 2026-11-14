/* Exercise the production world registry and visible-chain bucket consumer.
 * Reuse only the existing headless GL/buffer fixture, not its inline assertions.
 * No map/BSP/PVS data or GL context is required. GPL-2.0-or-later. */
#include <stdlib.h>
static int sort_calls;
static void counted_sort(void *base, size_t count, size_t size,
	int (*compare)(const void *, const void *))
{
	++sort_calls;
	qsort(base, count, size, compare);
}
#define qsort counted_sort
#define main unused_inline_regression_main
#include "gl1_inline_batch_regression.c"
#undef main
#undef qsort

image_t gltextures[MAX_GLTEXTURES];
int numgltextures;
static cvar_t world_setting = {.value = 1};
static cplane_t duplicate_plane;

static cvar_t *world_cvar(const char *name, const char *value, int flags)
{
	if (!strcmp(name, "r_gl1_batch_world")) return &world_setting;
	return test_cvar(name, value, flags);
}
static void world_setup(void)
{
	R_FreeWorldSurfaceBatches(world_batch_owner);
	setup();
	ri.Cvar_Get = world_cvar; world_setting.value = 1;
	world.surfaces = surfaces; world.numsurfaces = FACES;
	models[0].firstmodelsurface = 0; models[0].nummodelsurfaces = FACES;
	memset(gltextures, 0, sizeof(gltextures)); numgltextures = 2;
	for (int i = 0; i < numgltextures; ++i)
	{
		gltextures[i].registration_sequence = 1;
		gltextures[i].texnum = 90 + i;
	}
	for (int i = 0; i < FACES; ++i) textures[i].image = &gltextures[0];
}
static void world_build(void)
{
	allocation_number = 0;
	R_BuildWorldSurfaceBatches(&world);
}
static void world_draw(const int *visible, int visible_count)
{
	clear_capture();
	msurface_t **tails[MAX_GLTEXTURES] = {0};
	for (int i = 0; i < numgltextures; ++i) tails[i] = &gltextures[i].texturechain;
	for (int i = 0; i < visible_count; ++i)
	{
		int index = visible[i];
		int image = R_WorldImageIndex(textures[index].image);
		assert(image >= 0 && image < numgltextures);
		*tails[image] = &surfaces[index]; tails[image] = &surfaces[index].texturechain;
	}
	for (int i = 0; i < numgltextures; ++i) *tails[i] = NULL;
	int sorts = sort_calls, allocations = allocation_number;
	R_DrawTextureChains();
	assert(sort_calls == sorts && allocation_number == allocations);
	assert(!pending);
	for (int i = 0; i < numgltextures; ++i) assert(!gltextures[i].texturechain);
	for (int i = 0; i < FACES; ++i) assert(!surfaces[i].world_batch_next);
}
static void visible_set(const int *visible, int visible_count)
{
	assert(count == visible_count && c_brush_polys == visible_count);
	unsigned expected = 0, actual = 0;
	for (int i = 0; i < visible_count; ++i) expected |= 1u << visible[i];
	for (int i = 0; i < count; ++i)
	{
		int index = (int)(submitted[i] - polys);
		assert(index >= 0 && index < FACES && !(actual & (1u << index)));
		actual |= 1u << index;
		assert(colors[i] == textures[index].image->texnum);
		assert(lightmaps[i] == surfaces[index].lightmaptexturenum);
	}
	assert(actual == expected);
}
static void exact_order(const int *visible, int visible_count)
{
	assert(count == visible_count);
	for (int i = 0; i < count; ++i) assert(submitted[i] == &polys[visible[i]]);
}

int main(void)
{
	const int all[] = {0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15};
	const int reverse[] = {15,14,13,12,11,10,9,8,7,6,5,4,3,2,1,0};
	const int camera_a[] = {0,3,6,9,12,15}, camera_b[] = {1,4,7,10,13};
	world_setup(); world_build(); assert(world_batch_count == 4);
	world_setting.value = 0; world_draw(all, FACES); exact_order(all, FACES); int baseline = draws;
	world_setting.value = 1; world_draw(all, FACES); visible_set(all, FACES);
	assert(draws == 4 && draws < baseline);
	world_draw(reverse, FACES); visible_set(reverse, FACES);
	/* Equal keys preserve the actual visible-chain order, not source-face order. */
	for (int group = 1; group <= world_batch_count; ++group)
	{
		int next = 0;
		for (int i = 0; i < count; ++i)
		{
			int index = (int)(submitted[i] - polys);
			if (surfaces[index].world_batch_group != group) continue;
			while (next < FACES && surfaces[reverse[next]].world_batch_group != group) ++next;
			assert(next < FACES && reverse[next++] == index);
		}
	}
	for (int i = 0; i < 8; ++i)
	{
		const int *camera = i % 2 ? camera_a : camera_b;
		int size = i % 2 ? 6 : 5;
		world_draw(camera, size); visible_set(camera, size);
	}
	static_setting.value = 0; world_draw(reverse, FACES); exact_order(reverse, FACES);
	static_setting.value = 1; gl_config.multitexture = false;
	world_draw(reverse, FACES); exact_order(reverse, FACES); gl_config.multitexture = true;

	/* Different image objects have separate ranges even if GL texture IDs alias. */
	world_setup(); gltextures[1].texnum = gltextures[0].texnum;
	for (int i = 0; i < FACES; ++i) textures[i].image = &gltextures[i % 2];
	world_build(); assert(world_batch_ranges[0].count && world_batch_ranges[1].count);
	assert(world_batch_ranges[1].first >= world_batch_ranges[0].first + world_batch_ranges[0].count);
	world_draw(reverse, FACES); visible_set(reverse, FACES);

	world_setup(); textures[3].flags = SURF_FLOWING;
	textures[7].next = &animated; textures[7].numframes = 2; animated.image = &gltextures[1];
	textures[12].flags = SURF_WARP; surfaces[12].flags = SURF_DRAWTURB; polys[12].static_vbo = 0;
	textures[5].flags = SURF_TRANS33; textures[9].flags = SURF_SKY;
	world_build();
	for (int i = 0; i < FACES; ++i)
		if (i == 3 || i == 5 || i == 7 || i == 9 || i == 12) assert(!surfaces[i].world_batch_group);
	/* Alpha/sky never enter the opaque world chain; the warp pass stays last. */
	const int special[] = {0,1,2,3,4,6,7,8,10,11,12,13,14,15};
	world_draw(special, 14); visible_set(special, 14);
	assert(submitted[count - 1] == &polys[12]);
	int flow = -1, animation = -1;
	for (int i = 0; i < count; ++i)
	{
		if (submitted[i] == &polys[3]) flow = i;
		if (submitted[i] == &polys[7]) animation = i;
	}
	assert(flow == 3 && animation == 6);

	/* Equivalent oppositely stored planes also preserve overlapping LM ties. */
	world_setup(); duplicate_plane = plane; duplicate_plane.normal[0] = -1;
	surfaces[2].plane = &duplicate_plane; surfaces[2].flags = SURF_PLANEBACK;
	for (int v = 0; v < 4; ++v) polys[2].verts[v][1] = polys[0].verts[v][1] + .25f;
	world_build(); assert(!surfaces[0].world_batch_group && !surfaces[2].world_batch_group);
	world_draw(all, FACES); visible_set(all, FACES);
	assert(submitted[0] == &polys[0] && submitted[2] == &polys[2]);

	/* Only world submodel-zero faces are registered; no inline cache mixing. */
	world_setup(); models[0].nummodelsurfaces = 8; world_build();
	for (int i = 8; i < FACES; ++i) assert(!surfaces[i].world_batch_group);
	world_draw(all + 8, 8); exact_order(all + 8, 8);
	R_FreeWorldSurfaceBatches(&world); R_FreeWorldSurfaceBatches(&world);
	for (int i = 0; i < FACES; ++i) assert(!surfaces[i].world_batch_group);
	for (int fail = 0; fail < 2; ++fail)
	{
		fail_allocation = fail; world_build(); assert(!world_batch_groups && !world_batch_owner);
		world_draw(all, FACES); exact_order(all, FACES);
	}
	fail_allocation = -1; models[0].nummodelsurfaces = FACES; world_build();
	assert(world_batch_groups); world_draw(reverse, FACES); visible_set(reverse, FACES);
	R_FreeWorldSurfaceBatches(&world);
	puts("PASS world batches: exact visible sets/materials/LMs, fewer draws, stable chain order, camera isolation, no frame allocation/sort, special/warp barriers, coplanar LM ties, image ranges, fallback, OOM and lifecycle");
	return 0;
}
