/* Stateless pickup LOD policy regression checks. GPL-2.0-or-later. */
#include <assert.h>
#include <stdio.h>
#include "../../src/client/refresh/ref_shared.h"
#include "../../src/client/refresh/files/pickup_lod.h"

static void TestWhitelist(void)
{
	const char *paths[] = {
		"models/items/ammo/bullets/medium/tris.md2",
		"models/items/ammo/shells/medium/tris.md2",
		"models/items/ammo/grenades/medium/tris.md2",
		"models/items/armor/shard/tris.md2",
		"models/items/healing/stimpack/tris.md2"
	};
	for (unsigned i = 0; i < sizeof(paths) / sizeof(paths[0]); ++i)
	{
		const char *sibling = PP_PickupLODPath(paths[i]);
		assert(sibling && strstr(sibling, "/lod1.md2"));
		assert(!PP_PickupLODPath(sibling)); /* no recursive sibling chains */
		assert(strrchr(sibling, '/') - sibling == strrchr(paths[i], '/') - paths[i]);
	}
	assert(!PP_PickupLODPath(NULL));
	assert(!PP_PickupLODPath("models/items/healing/medium/tris.md2"));
	assert(!PP_PickupLODPath("models/monsters/soldier/tris.md2"));
	assert(!PP_PickupLODPath("models/weapons/v_grenad/tris.md2"));
	assert(!PP_PickupLODPath("models/items/armor/shard/tris.md2.extra"));
	assert(!PP_PickupLODPath("models/items/armor/shard/../shard/tris.md2"));
}

static void TestViews(void)
{
	const vec3_t zero = {0, 0, 0}, forward = {1, 0, 0};
	const vec3_t far_origin = {512, 0, 0}, near_camera = {500, 0, 0};
	pp_pickup_lod_view_t far_view = PP_PickupLODView(1, zero, forward, 120, 90);
	pp_pickup_lod_view_t near_view = PP_PickupLODView(1, near_camera, forward, 120, 90);
	/* The same shared object can be close to one player and distant to another.
	 * Neither decision writes entity state or persists a last-camera LOD. */
	for (int i = 0; i < 4; ++i)
	{
		assert(PP_PickupLODUse(&far_view, RF_GLOW, far_origin, 10, 0, 0));
		assert(!PP_PickupLODUse(&near_view, RF_GLOW, far_origin, 10, 0, 0));
	}
	pp_pickup_lod_view_t disabled = PP_PickupLODView(0, zero, forward, 120, 90);
	assert(!PP_PickupLODUse(&disabled, 0, far_origin, 10, 0, 0));
	pp_pickup_lod_view_t large_view = PP_PickupLODView(1, zero, forward, 1080, 90);
	assert(!PP_PickupLODUse(&large_view, 0, far_origin, 10, 0, 0));
	pp_pickup_lod_view_t zoom = PP_PickupLODView(1, zero, forward, 120, 20);
	assert(!PP_PickupLODUse(&zoom, 0, far_origin, 10, 0, 0));
	vec3_t origin = {255, 0, 0};
	assert(!PP_PickupLODUse(&far_view, 0, origin, 5, 0, 0));
	origin[0] = 256;
	assert(PP_PickupLODUse(&far_view, 0, origin, 5, 0, 0));
	/* Off-axis sphere projection, not Euclidean distance alone, sets size. */
	origin[0] = 100; origin[1] = 250;
	assert(!PP_PickupLODUse(&far_view, 0, origin, 10, 0, 0));
	assert(!PP_PickupLODUse(&far_view, 0, far_origin, 200, 0, 0));
	origin[0] = -512; origin[1] = 0;
	assert(!PP_PickupLODUse(&far_view, 0, origin, 10, 0, 0));
	const int excluded[] = {RF_WEAPONMODEL, RF_VIEWERMODEL, RF_DEPTHHACK, RF_TRANSLUCENT,
		RF_BEAM, RF_SHELL_RED, RF_SHELL_GREEN, RF_SHELL_BLUE, RF_SHELL_DOUBLE, RF_SHELL_HALF_DAM};
	for (unsigned i = 0; i < sizeof(excluded) / sizeof(excluded[0]); ++i)
		assert(!PP_PickupLODUse(&far_view, excluded[i], far_origin, 10, 0, 0));
	assert(!PP_PickupLODUse(&far_view, 0, far_origin, 10, 1, 0));
	assert(!PP_PickupLODUse(&far_view, 0, far_origin, 10, 0, 1));
	assert(!PP_PickupLODUse(&far_view, 0, far_origin, NAN, 0, 0));
	assert(!PP_PickupLODUse(&far_view, 0, far_origin, 0, 0, 0));
	origin[0] = NAN;
	assert(!PP_PickupLODUse(&far_view, 0, origin, 10, 0, 0));
	assert(!PP_PickupLODView(1, zero, forward, 0, 90).enabled);
	assert(!PP_PickupLODView(1, zero, forward, 120, NAN).enabled);
	assert(!PP_PickupLODView(1, zero, forward, 120, 0).enabled);
	assert(!PP_PickupLODView(1, zero, forward, 120, 180).enabled);
}

static void TestCanonicalRadius(void)
{
	const size_t size = sizeof(dmdl_t) + offsetof(daliasframe_t, verts) + 2 * sizeof(dtrivertx_t);
	dmdl_t *header = calloc(1, size);
	assert(header);
	header->num_frames = 1;
	header->num_xyz = 2;
	header->ofs_frames = sizeof(dmdl_t);
	header->ofs_end = size;
	daliasframe_t *frame = (daliasframe_t *)((byte *)header + header->ofs_frames);
	for (int axis = 0; axis < 3; ++axis) frame->scale[axis] = 1;
	frame->verts[0].v[0] = 3; frame->verts[0].v[1] = 4;
	frame->verts[1].v[0] = 6; frame->verts[1].v[1] = 8;
	assert(PP_PickupLODRadius(header) == 10);
	frame->translate[0] = 1;
	assert(fabsf(PP_PickupLODRadius(header) - sqrtf(113)) < .00001f);
	header->num_frames = 2;
	assert(PP_PickupLODRadius(header) == 0);
	header->num_frames = 1; header->num_xyz = 3;
	assert(PP_PickupLODRadius(header) == 0);
	header->num_xyz = 2; frame->scale[0] = NAN;
	assert(PP_PickupLODRadius(header) == 0);
	assert(PP_PickupLODRadius(NULL) == 0);
	free(header);
}

int main(void)
{
	TestWhitelist();
	TestViews();
	TestCanonicalRadius();
	puts("PASS: five-path whitelist, close/high detail, per-camera LOD, projection/zoom, flags and invalid inputs");
	return 0;
}
