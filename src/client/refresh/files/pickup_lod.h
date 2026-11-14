/* Original close-up pickups retain their canonical geometry. Only the five
 * explicitly authored siblings below may be substituted for small distant
 * pickups. This policy has no entity/model mutation or draw-time file access.
 * GPL-2.0-or-later.
 */
#ifndef PP_PICKUP_LOD_H
#define PP_PICKUP_LOD_H

#include <math.h>
#include <stddef.h>
#include <string.h>

typedef struct
{
	int enabled;
	float origin[3], forward[3];
	double projection_scale;
} pp_pickup_lod_view_t;

static inline const char *
PP_PickupLODPath(const char *name)
{
	static const char *const paths[][2] = {
		{"models/items/ammo/bullets/medium/tris.md2", "models/items/ammo/bullets/medium/lod1.md2"},
		{"models/items/ammo/shells/medium/tris.md2", "models/items/ammo/shells/medium/lod1.md2"},
		{"models/items/ammo/grenades/medium/tris.md2", "models/items/ammo/grenades/medium/lod1.md2"},
		{"models/items/armor/shard/tris.md2", "models/items/armor/shard/lod1.md2"},
		{"models/items/healing/stimpack/tris.md2", "models/items/healing/stimpack/lod1.md2"}
	};
	if (!name) return NULL;
	for (unsigned i = 0; i < sizeof(paths) / sizeof(paths[0]); ++i)
		if (!strcmp(name, paths[i][0])) return paths[i][1];
	return NULL;
}

static inline float
PP_PickupLODRadius(const dmdl_t *header)
{
	/* Mod_LoadMD2 retains legacy +/-32 culling bounds. Derive the LOD sphere
	 * from the loaded canonical frame instead of treating every pickup alike. */
	const size_t frame_header = offsetof(daliasframe_t, verts);
	if (!header || header->num_frames != 1 || header->num_xyz <= 0 ||
		header->ofs_frames < (int)sizeof(*header) || header->ofs_frames > header->ofs_end ||
		(size_t)(header->ofs_end - header->ofs_frames) < frame_header ||
		(size_t)header->num_xyz > ((size_t)(header->ofs_end - header->ofs_frames) - frame_header) / sizeof(dtrivertx_t))
		return 0;
	const daliasframe_t *frame = (const daliasframe_t *)((const byte *)header + header->ofs_frames);
	double radius2 = 0;
	for (int i = 0; i < header->num_xyz; ++i)
	{
		double distance2 = 0;
		for (int axis = 0; axis < 3; ++axis)
		{
			double coordinate = frame->translate[axis] + (double)frame->scale[axis] * frame->verts[i].v[axis];
			if (!isfinite(coordinate)) return 0;
			distance2 += coordinate * coordinate;
		}
		if (distance2 > radius2) radius2 = distance2;
	}
	return (float)sqrt(radius2);
}

static inline pp_pickup_lod_view_t
PP_PickupLODView(int enabled, const float *origin, const float *forward,
	int height, float fov_y)
{
	pp_pickup_lod_view_t view = {0};
	if (!enabled || height <= 0 || !isfinite(fov_y) || fov_y <= 0 || fov_y >= 179)
		return view;
	for (int axis = 0; axis < 3; ++axis)
	{
		if (!isfinite(origin[axis]) || !isfinite(forward[axis])) return view;
		view.origin[axis] = origin[axis];
		view.forward[axis] = forward[axis];
	}
	view.projection_scale = height / tan(fov_y * 0.008726646259971648);
	view.enabled = isfinite(view.projection_scale) && view.projection_scale > 0;
	return view;
}

static inline int
PP_PickupLODUse(const pp_pickup_lod_view_t *view, int flags,
	const float *origin, float radius, int frame, int oldframe)
{
	const int excluded = RF_WEAPONMODEL | RF_VIEWERMODEL | RF_DEPTHHACK |
		RF_TRANSLUCENT | RF_BEAM | RF_SHELL_RED | RF_SHELL_GREEN |
		RF_SHELL_BLUE | RF_SHELL_DOUBLE | RF_SHELL_HALF_DAM;
	double distance2 = 0, depth = 0;
	if (!view->enabled || (flags & excluded) || frame || oldframe ||
		!isfinite(radius) || radius <= 0) return 0;
	for (int axis = 0; axis < 3; ++axis)
	{
		double delta = (double)origin[axis] - view->origin[axis];
		if (!isfinite(delta)) return 0;
		distance2 += delta * delta;
		depth += delta * view->forward[axis];
	}
	if (distance2 < 256.0 * 256.0 || depth <= radius) return 0;
	/* Project the canonical bounding sphere, including the off-axis enlargement.
	 * Its largest projected diameter is r*h/tan(fovy/2) *
	 * sqrt(distance^2-r^2)/(depth^2-r^2). Compare squared values to avoid a
	 * square root per pickup. A larger framebuffer or zoom retains the original.
	 */
	double radius2 = (double)radius * radius;
	double scaled_radius = radius * view->projection_scale;
	double denominator = depth * depth - radius2;
	return scaled_radius * scaled_radius * (distance2 - radius2) <=
		12.0 * 12.0 * denominator * denominator;
}

#endif
