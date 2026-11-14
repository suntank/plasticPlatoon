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
 * Surface generation and drawing
 *
 * =======================================================================
 */

#include <assert.h>

#include "header/local.h"
#include "../files/visibility_cache.h"

typedef struct
{
	int top, bottom, left, right;
} lmrect_t;

int c_visible_lightmaps;
int c_visible_textures;
static pp_visibility_cache_t visibility_cache;
static cvar_t *r_viscache;
static qboolean previous_allvisible;
void R_ClearVisibilityCache(void) { PP_ClearVisibilityCache(&visibility_cache); previous_allvisible = true; }

static cvar_t *r_gl1_batch_inline, *inline_static_world;
static cvar_t *r_gl1_batch_world, *world_static_world;
static void R_RenderLightmappedPoly(msurface_t *surf);

typedef struct
{
	qboolean eligible, barrier;
	vec3_t mins, maxs;
} inline_batch_info_t;

/* Sort only immutable, ordinary multitextured faces. Special surfaces remain
 * source-order barriers; their animation, scrolling and ordered passes retain
 * the legacy path. The existing buffer still enforces its ushort capacities. */
static qboolean
R_InlineBatchEligible(const msurface_t *surface)
{
	const glpoly_t *poly = surface->polys;
	return !(surface->texinfo->flags &
		(SURF_SKY | SURF_TRANS33 | SURF_TRANS66 | SURF_WARP | SURF_FLOWING)) &&
		!(surface->flags & (SURF_DRAWTURB | SURF_DRAWSKY)) &&
		!surface->texinfo->next && poly && poly->static_vbo &&
		poly->static_indices && poly->static_index_count > 0 &&
		poly->static_index_count < MAX_INDICES;
}

static int
R_InlineMaterialCompare(const msurface_t *a, const msurface_t *b)
{
	int color_a = a->texinfo->image->texnum, color_b = b->texinfo->image->texnum;
	if (color_a != color_b) return color_a < color_b ? -1 : 1;
	if (a->lightmaptexturenum != b->lightmaptexturenum)
		return a->lightmaptexturenum < b->lightmaptexturenum ? -1 : 1;
	if (a->polys->static_vbo != b->polys->static_vbo)
		return a->polys->static_vbo < b->polys->static_vbo ? -1 : 1;
	return 0;
}

static int
R_InlineOrderCompare(const void *left, const void *right)
{
	const msurface_t *a = *(msurface_t *const *)left;
	const msurface_t *b = *(msurface_t *const *)right;
	int material = R_InlineMaterialCompare(a, b);
	/* Every entry belongs to one surface array. Preserve equal-key source order. */
	return material ? material : (a > b) - (a < b);
}

static qboolean
R_InlineSamePlane(const msurface_t *a, const msurface_t *b)
{
	float sign_a = a->flags & SURF_PLANEBACK ? -1.0f : 1.0f;
	float sign_b = b->flags & SURF_PLANEBACK ? -1.0f : 1.0f;
	for (int axis = 0; axis < 3; ++axis)
		if (a->plane->normal[axis] * sign_a != b->plane->normal[axis] * sign_b)
			return false;
	return a->plane->dist * sign_a == b->plane->dist * sign_b;
}

static qboolean
R_InlinePlaneOverlap(const msurface_t *surface, const inline_batch_info_t *a,
	const inline_batch_info_t *b)
{
	int dropped = 0;
	for (int axis = 1; axis < 3; ++axis)
		if (fabsf(surface->plane->normal[axis]) > fabsf(surface->plane->normal[dropped]))
			dropped = axis;
	for (int axis = 0; axis < 3; ++axis)
	{
		if (axis == dropped) continue;
		/* Touching edges have zero area. AABB false positives are conservative. */
		if (a->maxs[axis] <= b->mins[axis] || b->maxs[axis] <= a->mins[axis])
			return false;
	}
	return true;
}

void
R_FreeInlineSurfaceOrders(model_t *world)
{
	if (!world || !world->submodels) return;
	for (int i = 1; i < world->numsubmodels; ++i)
	{
		free(world->submodels[i].inline_surface_order);
		world->submodels[i].inline_surface_order = NULL;
	}
}

void
R_BuildInlineSurfaceOrders(model_t *world)
{
	if (!r_gl1_batch_inline) r_gl1_batch_inline = ri.Cvar_Get("r_gl1_batch_inline", "1", 0);
	if (!inline_static_world) inline_static_world = ri.Cvar_Get("gl1_static_world", "1", 0);
	R_FreeInlineSurfaceOrders(world);
	if (!world || !world->submodels) return;
	for (int model_index = 1; model_index < world->numsubmodels; ++model_index)
	{
		model_t *model = &world->submodels[model_index];
		int count = model->nummodelsurfaces, eligible = 0;
		if (count < 2) continue;
		inline_batch_info_t *info = calloc((size_t)count, sizeof(*info));
		if (!info) continue; /* Allocation failure leaves the original order. */
		msurface_t *surfaces = model->surfaces + model->firstmodelsurface;
		for (int i = 0; i < count; ++i)
		{
			msurface_t *surface = &surfaces[i];
			info[i].eligible = R_InlineBatchEligible(surface);
			if (!info[i].eligible) continue;
			++eligible;
			for (int axis = 0; axis < 3; ++axis)
				info[i].mins[axis] = info[i].maxs[axis] = surface->polys->verts[0][axis];
			for (int vertex = 1; vertex < surface->polys->numverts; ++vertex)
				for (int axis = 0; axis < 3; ++axis)
				{
					float value = surface->polys->verts[vertex][axis];
					if (value < info[i].mins[axis]) info[i].mins[axis] = value;
					if (value > info[i].maxs[axis]) info[i].maxs[axis] = value;
				}
		}
		if (eligible < 2) { free(info); continue; }
		/* Preserve source-order depth ties on overlapping coplanar materials.
		 * This registration-only scan also permits adjacent wall/train panels. */
		for (int i = 0; i < count; ++i)
		{
			if (!info[i].eligible) continue;
			for (int j = 0; j < i; ++j)
				if (info[j].eligible && R_InlineMaterialCompare(&surfaces[i], &surfaces[j]) &&
					R_InlineSamePlane(&surfaces[i], &surfaces[j]) &&
					R_InlinePlaneOverlap(&surfaces[i], &info[i], &info[j]))
					info[i].barrier = info[j].barrier = true;
		}
		msurface_t **order = malloc((size_t)count * sizeof(*order));
		if (!order) { free(info); continue; }
		for (int i = 0; i < count; ++i) order[i] = &surfaces[i];
		for (int start = 0; start < count; )
		{
			if (!info[start].eligible || info[start].barrier) { ++start; continue; }
			int end = start + 1;
			while (end < count && info[end].eligible && !info[end].barrier) ++end;
			if (end - start > 1)
				qsort(order + start, (size_t)(end - start), sizeof(*order), R_InlineOrderCompare);
			start = end;
		}
		model->inline_surface_order = order;
		free(info);
	}
}

typedef struct { msurface_t *head, *tail; int next_active; } world_batch_group_t;
typedef struct { int first, count, active_first, active_last; } world_batch_range_t;
typedef struct
{
	msurface_t *surface;
	vec3_t normal, mins, maxs;
	float distance;
	int image, dropped;
	qboolean barrier;
} world_batch_info_t;

static world_batch_group_t *world_batch_groups;
static world_batch_range_t world_batch_ranges[MAX_GLTEXTURES];
static model_t *world_batch_owner;
static int world_batch_count;

static qboolean
R_WorldSurfaceRange(const model_t *world, int *first, int *count)
{
	if (!world || !world->submodels || world->numsubmodels < 1) return false;
	*first = world->submodels[0].firstmodelsurface;
	*count = world->submodels[0].nummodelsurfaces;
	return *first >= 0 && *count >= 0 && *first <= world->numsurfaces &&
		*count <= world->numsurfaces - *first;
}

void
R_FreeWorldSurfaceBatches(model_t *world)
{
	int first, count;
	if (world != world_batch_owner) return;
	if (R_WorldSurfaceRange(world, &first, &count))
		for (int i = first; i < first + count; ++i)
		{
			world->surfaces[i].world_batch_group = 0;
			world->surfaces[i].world_batch_next = NULL;
		}
	free(world_batch_groups); world_batch_groups = NULL;
	memset(world_batch_ranges, 0, sizeof(world_batch_ranges));
	world_batch_owner = NULL; world_batch_count = 0;
}

static int
R_WorldImageIndex(const image_t *image)
{
	uintptr_t at = (uintptr_t)image, start = (uintptr_t)gltextures;
	if (at < start || at >= start + sizeof(gltextures) || (at - start) % sizeof(*image))
		return -1;
	return (int)((at - start) / sizeof(*image));
}

static int
R_WorldPlaneKeyCompare(const world_batch_info_t *a, const world_batch_info_t *b)
{
	if (a->image != b->image) return a->image < b->image ? -1 : 1;
	for (int axis = 0; axis < 3; ++axis)
		if (a->normal[axis] != b->normal[axis]) return a->normal[axis] < b->normal[axis] ? -1 : 1;
	if (a->distance != b->distance) return a->distance < b->distance ? -1 : 1;
	return 0;
}

static int
R_WorldPlaneOrderCompare(const void *left, const void *right)
{
	const world_batch_info_t *a = left, *b = right;
	int plane = R_WorldPlaneKeyCompare(a, b);
	if (plane) return plane;
	int sweep = a->dropped == 0 ? 1 : 0;
	if (a->mins[sweep] != b->mins[sweep]) return a->mins[sweep] < b->mins[sweep] ? -1 : 1;
	return (a->surface > b->surface) - (a->surface < b->surface);
}

static int
R_WorldMaterialOrderCompare(const void *left, const void *right)
{
	const world_batch_info_t *a = left, *b = right;
	if (a->image != b->image) return a->image < b->image ? -1 : 1;
	int material = R_InlineMaterialCompare(a->surface, b->surface);
	return material ? material : (a->surface > b->surface) - (a->surface < b->surface);
}

void
R_BuildWorldSurfaceBatches(model_t *world)
{
	int first, count, eligible = 0;
	if (!r_gl1_batch_world) r_gl1_batch_world = ri.Cvar_Get("r_gl1_batch_world", "1", 0);
	if (!world_static_world) world_static_world = ri.Cvar_Get("gl1_static_world", "1", 0);
	R_FreeWorldSurfaceBatches(world_batch_owner);
	if (!R_WorldSurfaceRange(world, &first, &count)) return;
	for (int i = first; i < first + count; ++i)
	{
		msurface_t *surface = &world->surfaces[i];
		surface->world_batch_group = 0; surface->world_batch_next = NULL;
		if (R_InlineBatchEligible(surface) && R_WorldImageIndex(surface->texinfo->image) >= 0)
			++eligible;
	}
	if (eligible < 2) return;
	world_batch_info_t *info = calloc((size_t)eligible, sizeof(*info));
	if (!info) return;
	int used = 0;
	for (int i = first; i < first + count; ++i)
	{
		msurface_t *surface = &world->surfaces[i];
		int image = R_WorldImageIndex(surface->texinfo->image);
		if (!R_InlineBatchEligible(surface) || image < 0) continue;
		world_batch_info_t *item = &info[used++];
		item->surface = surface; item->image = image;
		float sign = surface->flags & SURF_PLANEBACK ? -1.0f : 1.0f;
		item->distance = sign * surface->plane->dist;
		for (int axis = 0; axis < 3; ++axis)
		{
			item->normal[axis] = sign * surface->plane->normal[axis];
			if (fabsf(item->normal[axis]) > fabsf(item->normal[item->dropped])) item->dropped = axis;
			item->mins[axis] = item->maxs[axis] = surface->polys->verts[0][axis];
		}
		for (int vertex = 1; vertex < surface->polys->numverts; ++vertex)
			for (int axis = 0; axis < 3; ++axis)
			{
				float value = surface->polys->verts[vertex][axis];
				if (value < item->mins[axis]) item->mins[axis] = value;
				if (value > item->maxs[axis]) item->maxs[axis] = value;
			}
	}
	/* Registration-only coplanar sweep, rather than an all-face quadratic scan.
	 * Image order is unchanged; guard depth ties only within the same image. */
	qsort(info, (size_t)eligible, sizeof(*info), R_WorldPlaneOrderCompare);
	for (int start = 0; start < eligible; )
	{
		int end = start + 1;
		while (end < eligible && !R_WorldPlaneKeyCompare(&info[start], &info[end])) ++end;
		int sweep = info[start].dropped == 0 ? 1 : 0;
		int other = 3 - info[start].dropped - sweep;
		for (int i = start; i < end; ++i)
			for (int j = i + 1; j < end && info[j].mins[sweep] < info[i].maxs[sweep]; ++j)
				if (R_InlineMaterialCompare(info[i].surface, info[j].surface) &&
					info[i].maxs[other] > info[j].mins[other] && info[j].maxs[other] > info[i].mins[other])
					info[i].barrier = info[j].barrier = true;
		start = end;
	}
	world_batch_group_t *groups = calloc((size_t)eligible + 1, sizeof(*groups));
	if (!groups) { free(info); return; }
	qsort(info, (size_t)eligible, sizeof(*info), R_WorldMaterialOrderCompare);
	msurface_t *previous = NULL;
	int previous_image = -1;
	for (int i = 0; i < eligible; ++i)
	{
		if (info[i].barrier) continue;
		msurface_t *surface = info[i].surface;
		world_batch_range_t *range = &world_batch_ranges[info[i].image];
		if (!previous || previous_image != info[i].image || R_InlineMaterialCompare(previous, surface))
		{
			++world_batch_count;
			if (!range->count) range->first = world_batch_count;
			++range->count;
		}
		surface->world_batch_group = world_batch_count;
		previous = surface;
		previous_image = info[i].image;
	}
	world_batch_groups = groups; world_batch_owner = world;
	free(info);
}

static void
R_DrawWorldBucketRange(image_t *image, world_batch_range_t *range)
{
	/* First-seen group order needs no sort and visits only visible state keys.
	 * Equal-key faces keep their original chain order within each bucket. */
	int group = range->active_first;
	while (group)
	{
		world_batch_group_t *bucket = &world_batch_groups[group];
		int next_group = bucket->next_active;
		msurface_t *surface = bucket->head;
		while (surface)
		{
			msurface_t *next = surface->world_batch_next;
			surface->world_batch_next = NULL;
			R_UpdateGLBuffer(buf_mtex, image->texnum, surface->lightmaptexturenum, 0, 1);
			R_RenderLightmappedPoly(surface);
			surface = next;
		}
		bucket->head = bucket->tail = NULL;
		bucket->next_active = 0;
		group = next_group;
	}
	range->active_first = range->active_last = 0;
}

static vec3_t modelorg; /* relative to viewpoint */
msurface_t *r_alpha_surfaces;

gllightmapstate_t gl_lms;
extern int cur_lm_copy;

void LM_InitBlock(void);
void LM_UploadBlock(qboolean dynamic);
qboolean LM_AllocBlock(int w, int h, int *x, int *y);

void R_SetCacheState(msurface_t *surf);
void R_BuildLightMap(msurface_t *surf, byte *dest, int stride);

static void
R_DrawGLPoly(msurface_t *fa)
{
	int i, nv;
	float *v, scroll;
	if (R_BufferStaticPoly(fa->polys)) return;

	v = fa->polys->verts[0];
	nv = fa->polys->numverts;

	if (fa->texinfo->flags & SURF_FLOWING)
	{
		scroll = -64 * ((r_newrefdef.time / 40.0) - (int)(r_newrefdef.time / 40.0));

		if (scroll == 0.0)
		{
			scroll = -64.0;
		}
	}
	else
	{
		scroll = 0.0;
	}

	R_SetBufferIndices(GL_TRIANGLE_FAN, nv);

	for ( i = 0; i < nv; i++, v += VERTEXSIZE )
	{
		GLBUFFER_VERTEX( v[0], v[1], v[2] )
		GLBUFFER_SINGLETEX( v[3] + scroll, v[4] )
	}
}

static void
R_DrawTriangleOutlines(void)
{
	int i, j;
	glpoly_t *p;

	if (!gl_showtris->value)
	{
		return;
	}

	glDisable(GL_TEXTURE_2D);
	glDisable(GL_DEPTH_TEST);
	glColor4f(1, 1, 1, 1);

	for (i = 0; i < MAX_LIGHTMAPS; i++)
	{
		msurface_t *surf;

		for (surf = gl_lms.lightmap_surfaces[i];
			 surf != 0;
			 surf = surf->lightmapchain)
		{
			p = surf->polys;

			for ( ; p; p = p->chain)
			{
				for (j = 2; j < p->numverts; j++)
				{
                    GLfloat vtx[12];
                    unsigned int k;

                    for (k=0; k<3; k++)
                    {
                        vtx[0+k] = p->verts [ 0 ][ k ];
                        vtx[3+k] = p->verts [ j - 1 ][ k ];
                        vtx[6+k] = p->verts [ j ][ k ];
                        vtx[9+k] = p->verts [ 0 ][ k ];
                    }

                    glEnableClientState( GL_VERTEX_ARRAY );

                    glVertexPointer( 3, GL_FLOAT, 0, vtx );
                    PP_DrawArrays( GL_LINE_STRIP, 0, 4 );

                    glDisableClientState( GL_VERTEX_ARRAY );
				}
			}
		}
	}

	glEnable(GL_DEPTH_TEST);
	glEnable(GL_TEXTURE_2D);
}

static void
R_DrawGLPolyChain(glpoly_t *p, float soffset, float toffset)
{
	if ((soffset == 0) && (toffset == 0))
	{
		for ( ; p != 0; p = p->chain)
		{
			float *v;

			v = p->verts[0];

            glEnableClientState( GL_VERTEX_ARRAY );
            glEnableClientState( GL_TEXTURE_COORD_ARRAY );

            glVertexPointer( 3, GL_FLOAT, VERTEXSIZE*sizeof(GLfloat), v );
            glTexCoordPointer( 2, GL_FLOAT, VERTEXSIZE*sizeof(GLfloat), v+5 );
            PP_DrawArrays( GL_TRIANGLE_FAN, 0, p->numverts );

            glDisableClientState( GL_VERTEX_ARRAY );
            glDisableClientState( GL_TEXTURE_COORD_ARRAY );
		}
	}
	else
	{
		// workaround for lack of VLAs (=> our workaround uses alloca() which is bad in loops)
#ifdef _MSC_VER
		int maxNumVerts = 0;
		for (glpoly_t* tmp = p; tmp; tmp = tmp->chain)
		{
			if ( tmp->numverts > maxNumVerts )
				maxNumVerts = tmp->numverts;
		}

		YQ2_VLA( GLfloat, tex, 2 * maxNumVerts );
#endif

		for ( ; p != 0; p = p->chain)
		{
			float *v;
			int j;

			v = p->verts[0];
#ifndef _MSC_VER // we have real VLAs, so it's safe to use one in this loop
            YQ2_VLA(GLfloat, tex, 2*p->numverts);
#endif

            unsigned int index_tex = 0;

			for ( j = 0; j < p->numverts; j++, v += VERTEXSIZE )
			{
			    tex[index_tex++] = v [ 5 ] - soffset;
			    tex[index_tex++] = v [ 6 ] - toffset;
			}

			v = p->verts [ 0 ];

            glEnableClientState( GL_VERTEX_ARRAY );
            glEnableClientState( GL_TEXTURE_COORD_ARRAY );

            glVertexPointer( 3, GL_FLOAT, VERTEXSIZE*sizeof(GLfloat), v );
            glTexCoordPointer( 2, GL_FLOAT, 0, tex );
            PP_DrawArrays( GL_TRIANGLE_FAN, 0, p->numverts );

            glDisableClientState( GL_VERTEX_ARRAY );
            glDisableClientState( GL_TEXTURE_COORD_ARRAY );
		}

		YQ2_VLAFREE( tex );
	}
}

/*
 * This routine takes all the given light mapped surfaces
 * in the world and blends them into the framebuffer.
 */
static void
R_BlendLightmaps(const model_t *currentmodel)
{
	int i;
	msurface_t *surf, *newdrawsurf = 0;

	/* don't bother if we're set to fullbright or multitexture is enabled */
	if (gl_config.multitexture || r_fullbright->value || !r_worldmodel->lightdata)
	{
		return;
	}

	/* don't bother writing Z */
	glDepthMask(GL_FALSE);

	/* set the appropriate blending mode unless
	   we're only looking at the lightmaps. */
	if (!gl_lightmap->value)
	{
		glEnable(GL_BLEND);

		if (gl1_saturatelighting->value)
		{
			glBlendFunc(GL_ONE, GL_ONE);
		}
		else
		{
			glBlendFunc(GL_ZERO, GL_SRC_COLOR);
		}
	}

	if (currentmodel == r_worldmodel)
	{
		c_visible_lightmaps = 0;
	}

	/* render static lightmaps first */
	for (i = 1; i < MAX_LIGHTMAPS; i++)
	{
		if (gl_lms.lightmap_surfaces[i])
		{
			if (currentmodel == r_worldmodel)
			{
				c_visible_lightmaps++;
			}

			R_Bind(gl_state.lightmap_textures + i);

			for (surf = gl_lms.lightmap_surfaces[i];
				 surf != 0;
				 surf = surf->lightmapchain)
			{
				if (surf->polys)
				{
					// Apply overbright bits to the static lightmaps
					if (gl1_overbrightbits->value)
					{
						R_TexEnv(GL_COMBINE);
						glTexEnvi(GL_TEXTURE_ENV, GL_RGB_SCALE, gl1_overbrightbits->value);
					}

					R_DrawGLPolyChain(surf->polys, 0, 0);
				}
			}
		}
	}

	/* render dynamic lightmaps */
	if (gl1_dynamic->value)
	{
		LM_InitBlock();

		R_Bind(gl_state.lightmap_textures + 0);

		if (currentmodel == r_worldmodel)
		{
			c_visible_lightmaps++;
		}

		newdrawsurf = gl_lms.lightmap_surfaces[0];

		for (surf = gl_lms.lightmap_surfaces[0];
			 surf != 0;
			 surf = surf->lightmapchain)
		{
			int smax, tmax;
			byte *base;

			smax = (surf->extents[0] >> 4) + 1;
			tmax = (surf->extents[1] >> 4) + 1;

			if (LM_AllocBlock(smax, tmax, &surf->dlight_s, &surf->dlight_t))
			{
				base = gl_lms.lightmap_buffer[0];
				base += (surf->dlight_t * BLOCK_WIDTH +
						surf->dlight_s) * LIGHTMAP_BYTES;

				R_BuildLightMap(surf, base, BLOCK_WIDTH * LIGHTMAP_BYTES);
			}
			else
			{
				msurface_t *drawsurf;

				/* upload what we have so far */
				LM_UploadBlock(true);

				/* draw all surfaces that use this lightmap */
				for (drawsurf = newdrawsurf;
					 drawsurf != surf;
					 drawsurf = drawsurf->lightmapchain)
				{
					if (drawsurf->polys)
					{
						// Apply overbright bits to the dynamic lightmaps
						if (gl1_overbrightbits->value)
						{
							R_TexEnv(GL_COMBINE);
							glTexEnvi(GL_TEXTURE_ENV, GL_RGB_SCALE, gl1_overbrightbits->value);
						}

						R_DrawGLPolyChain(drawsurf->polys,
								(drawsurf->light_s - drawsurf->dlight_s) * (float)(1.0 / BLOCK_WIDTH),
								(drawsurf->light_t - drawsurf->dlight_t) * (float)(1.0 / BLOCK_HEIGHT));
					}
				}

				newdrawsurf = drawsurf;

				/* clear the block */
				LM_InitBlock();

				/* try uploading the block now */
				if (!LM_AllocBlock(smax, tmax, &surf->dlight_s, &surf->dlight_t))
				{
					Com_Error(ERR_FATAL,
							"%s: Consecutive calls to LM_AllocBlock(%d,%d) failed (dynamic)\n",
							__func__, smax, tmax);
				}

				base = gl_lms.lightmap_buffer[0];
				base += (surf->dlight_t * BLOCK_WIDTH +
						surf->dlight_s) * LIGHTMAP_BYTES;

				R_BuildLightMap(surf, base, BLOCK_WIDTH * LIGHTMAP_BYTES);
			}
		}

		/* draw remainder of dynamic lightmaps that haven't been uploaded yet */
		if (newdrawsurf)
		{
			LM_UploadBlock(true);
		}

		for (surf = newdrawsurf; surf != 0; surf = surf->lightmapchain)
		{
			if (surf->polys)
			{
				// Apply overbright bits to the remainder lightmaps
				if (gl1_overbrightbits->value)
				{
					R_TexEnv(GL_COMBINE);
					glTexEnvi(GL_TEXTURE_ENV, GL_RGB_SCALE, gl1_overbrightbits->value);
				}

				R_DrawGLPolyChain(surf->polys,
						(surf->light_s - surf->dlight_s) * (float)(1.0 / BLOCK_WIDTH),
						(surf->light_t - surf->dlight_t) * (float)(1.0 / BLOCK_HEIGHT));
			}
		}
	}

	/* restore state */
	glDisable(GL_BLEND);
	glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
	glDepthMask(GL_TRUE);
}

static void
R_RenderBrushPoly(msurface_t *fa)
{
	int maps;
	qboolean is_dynamic = false;

	c_brush_polys++;

	if (fa->flags & SURF_DRAWTURB)
	{
		R_EmitWaterPolys(fa);
		return;
	}

	R_DrawGLPoly(fa);

	if (gl_config.multitexture)
	{
		return;	// lighting already done at this point for mtex
	}

	/* check for lightmap modification */
	for (maps = 0; maps < MAXLIGHTMAPS && fa->styles[maps] != 255; maps++)
	{
		if (r_newrefdef.lightstyles[fa->styles[maps]].white !=
			fa->cached_light[maps])
		{
			goto dynamic;
		}
	}

	/* dynamic this frame or dynamic previously */
	if (fa->dlightframe == r_framecount)
	{
	dynamic:

		if (gl1_dynamic->value)
		{
			if (!(fa->texinfo->flags &
				  (SURF_SKY | SURF_TRANS33 |
				   SURF_TRANS66 | SURF_WARP)))
			{
				is_dynamic = true;
			}
		}
	}

	if (is_dynamic)
	{
		if (maps < MAXLIGHTMAPS &&
			((fa->styles[maps] >= 32) ||
			 (fa->styles[maps] == 0)) &&
			  (fa->dlightframe != r_framecount))
		{
			unsigned temp[34 * 34];
			int smax, tmax;

			smax = (fa->extents[0] >> 4) + 1;
			tmax = (fa->extents[1] >> 4) + 1;

			R_BuildLightMap(fa, (void *)temp, smax * 4);
			R_SetCacheState(fa);

			{
				double setup_started = pp_drawprofile_active ? PP_DPClock() : 0;
				R_Bind(gl_state.lightmap_textures + fa->lightmaptexturenum);
				PP_DP_WORLD_ADD(DPW_LM_UPLOAD_SETUP_MS, PP_DPClock() - setup_started);
				double upload_started = PP_DPClock();
				glTexSubImage2D(GL_TEXTURE_2D, 0, fa->light_s, fa->light_t,
					smax, tmax, GL_LIGHTMAP_FORMAT, GL_UNSIGNED_BYTE, temp);
				PP_DP_WORLD_ADD(DPW_LM_UPLOAD_MS, PP_DPClock() - upload_started);
				PP_DP_WORLD_ADD(DPW_LM_UPLOAD_CALLS, 1);
				PP_DP_WORLD_ADD(DPW_LM_UPLOAD_BYTES, smax*tmax*LIGHTMAP_BYTES);
			}
			PP_PERF(lightmap_bytes, smax*tmax*LIGHTMAP_BYTES);

			fa->lightmapchain = gl_lms.lightmap_surfaces[fa->lightmaptexturenum];
			gl_lms.lightmap_surfaces[fa->lightmaptexturenum] = fa;
		}
		else
		{
			fa->lightmapchain = gl_lms.lightmap_surfaces[0];
			gl_lms.lightmap_surfaces[0] = fa;
		}
	}
	else
	{
		fa->lightmapchain = gl_lms.lightmap_surfaces[fa->lightmaptexturenum];
		gl_lms.lightmap_surfaces[fa->lightmaptexturenum] = fa;
	}
}

/*
 * Draw water surfaces and windows.
 * The BSP tree is waled front to back, so unwinding the chain
 * of alpha_surfaces will draw back to front, giving proper ordering.
 */
void
R_DrawAlphaSurfaces(void)
{
	msurface_t *s;
	float alpha;

	/* go back to the world matrix */
	glLoadMatrixf(r_world_matrix);

	glEnable(GL_BLEND);
	R_TexEnv(GL_MODULATE);

	for (s = r_alpha_surfaces; s; s = s->texturechain)
	{
		c_brush_polys++;

		if (s->texinfo->flags & SURF_TRANS33)
		{
			alpha = 0.33f;
		}
		else if (s->texinfo->flags & SURF_TRANS66)
		{
			alpha = 0.66f;
		}
		else
		{
			alpha = 1.0f;
		}

		R_UpdateGLBuffer(buf_alpha, s->texinfo->image->texnum, 0, 0, alpha);

		if (s->flags & SURF_DRAWTURB)
		{
			R_EmitWaterPolys(s);
		}
		else
		{
			R_DrawGLPoly(s);
		}
	}
	R_ApplyGLBuffer();	// Flush the last batched array

	R_TexEnv(GL_REPLACE);
	glColor4f(1, 1, 1, 1);
	glDisable(GL_BLEND);

	r_alpha_surfaces = NULL;
}

static void
R_RenderLightmappedPoly(msurface_t *surf)
{
	const int nv = surf->polys->numverts;
	int i;
	float scroll;
	float *v;

	c_brush_polys++;
	if (R_BufferStaticPoly(surf->polys)) return;
	v = surf->polys->verts[0];

	if (surf->texinfo->flags & SURF_FLOWING)
	{
		scroll = -64 * ((r_newrefdef.time / 40.0) - (int) (r_newrefdef.time / 40.0));

		if (scroll == 0.0)
		{
			scroll = -64.0;
		}
	}
	else
	{
		scroll = 0.0;
	}

	R_SetBufferIndices(GL_TRIANGLE_FAN, nv);

	for (i = 0; i < nv; i++, v += VERTEXSIZE)
	{
		GLBUFFER_VERTEX( v[0], v[1], v[2] )
		GLBUFFER_MULTITEX( v[3] + scroll, v[4], v[5], v[6] )
	}
}

/* Add "adding" area to "obj" */
static void
R_JoinAreas(lmrect_t *adding, lmrect_t *obj)
{
	if (adding->top < obj->top)
	{
		obj->top = adding->top;
	}
	if (adding->bottom > obj->bottom)
	{
		obj->bottom = adding->bottom;
	}
	if (adding->left < obj->left)
	{
		obj->left = adding->left;
	}
	if (adding->right > obj->right)
	{
		obj->right = adding->right;
	}
}

/* Upload dynamic lights to each lightmap texture (multitexture path only) */
static void
R_RegenAllLightmaps()
{
	static lmrect_t lmchange[MAX_LIGHTMAPS][MAX_LIGHTMAP_COPIES];
	static qboolean altered[MAX_LIGHTMAPS][MAX_LIGHTMAP_COPIES];

	int i, lmtex;
#ifndef YQ2_GL1_GLES
	qboolean pixelstore_set = false;
#endif

	if ( !gl_config.multitexture || r_fullbright->value || !gl1_dynamic->value )
	{
		return;
	}

	PP_DP_WORLD_ADD(DPW_LM_REGEN_RUNS, 1);

	if (gl_config.lightmapcopies)
	{
		cur_lm_copy = (cur_lm_copy + 1) % MAX_LIGHTMAP_COPIES;	// select the next lightmap copy
		lmtex = MAX_LIGHTMAPS * cur_lm_copy;	// ...and its corresponding texture
	}
	else
	{
		lmtex = 0;
	}

	for (i = 1; i < MAX_LIGHTMAPS; i++)
	{
		lmrect_t current, best;
		msurface_t *surf;
		byte *base;
		qboolean affected_lightmap;
		unsigned dp_useful_texels = 0;
		double dp_setup_started;

		if (!gl_lms.lightmap_surfaces[i] || !gl_lms.lightmap_buffer[i])
		{
			continue;
		}

		PP_DP_WORLD_ADD(DPW_LM_ATLASES_SCANNED, 1);
		affected_lightmap = false;
		best.top = BLOCK_HEIGHT;
		best.left = BLOCK_WIDTH;
		best.bottom = best.right = 0;

		for (surf = gl_lms.lightmap_surfaces[i];
			 surf != 0;
			 surf = surf->lightmapchain)
		{
			int map;
			PP_DP_WORLD_ADD(DPW_LM_SURFACES_SCANNED, 1);

			if (surf->texinfo->flags & (SURF_SKY | SURF_TRANS33 | SURF_TRANS66 | SURF_WARP))
			{
				continue;
			}

			// Any dynamic lights on this surface?
			for (map = 0; map < MAXLIGHTMAPS && surf->styles[map] != 255; map++)
			{
				if (r_newrefdef.lightstyles[surf->styles[map]].white != surf->cached_light[map])
				{
					goto dynamic_surf;
				}
			}

			// Surface is considered to have dynamic lights if it had them in the previous frame
			if ( surf->dlightframe != r_framecount && !surf->dirty_lightmap )
			{
				continue;	// no dynamic lights affect this surface in this frame
			}

dynamic_surf:
			PP_DP_WORLD_ADD(DPW_LM_CHANGED_SURFACES, 1);
			affected_lightmap = true;

			current.left = surf->light_s;
			current.right = surf->light_s + (surf->extents[0] >> 4) + 1;	// + smax
			current.top = surf->light_t;
			current.bottom = surf->light_t + (surf->extents[1] >> 4) + 1;	// + tmax
			if (pp_drawprofile_active)
				dp_useful_texels += (current.right-current.left)*(current.bottom-current.top);

			base = gl_lms.lightmap_buffer[i];
			base += (current.top * BLOCK_WIDTH + current.left) * LIGHTMAP_BYTES;

			R_BuildLightMap(surf, base, BLOCK_WIDTH * LIGHTMAP_BYTES);

			surf->dirty_lightmap = (surf->dlightframe == r_framecount);
			if (!surf->dirty_lightmap || gl_config.lightmapcopies)
			{
				for (map = 0; map < MAXLIGHTMAPS && surf->styles[map] != 255; map++)
				{
					if ( (surf->styles[map] >= 32) || (surf->styles[map] == 0) )
					{
						R_SetCacheState(surf);
						break;
					}
				}
			}
			R_JoinAreas(&current, &best);
		}

		if (!gl_config.lightmapcopies && !affected_lightmap)
		{
			continue;
		}

		if (gl_config.lightmapcopies)
		{
			// Add all the changes that have happened in the last few frames,
			// at least just for consistency between them.
			qboolean apply_changes = affected_lightmap;
			current = best;		// save state for next frames... +

			for (int k = 0; k < MAX_LIGHTMAP_COPIES; k++)
			{
				if (altered[i][k])
				{
					apply_changes = true;
					R_JoinAreas(&lmchange[i][k], &best);
				}
			}

			altered[i][cur_lm_copy] = affected_lightmap;
			if (affected_lightmap)
			{
				lmchange[i][cur_lm_copy] = current;	// + ...here
			}

			if (!apply_changes)
			{
				continue;
			}
		}

		/* Useful area is this view's rebuilds, excluding any older copy history. */
		PP_DP_WORLD_ADD(DPW_LM_REGEN_USEFUL_TEXELS, dp_useful_texels);
		PP_DP_WORLD_ADD(DPW_LM_REGEN_RECT_TEXELS, (best.right-best.left)*(best.bottom-best.top));
		dp_setup_started = pp_drawprofile_active ? PP_DPClock() : 0;
#ifndef YQ2_GL1_GLES
		if (!pixelstore_set)
		{
			glPixelStorei(GL_UNPACK_ROW_LENGTH, BLOCK_WIDTH);
			pixelstore_set = true;
		}
#endif

		// upload changes
		base = gl_lms.lightmap_buffer[i];

#ifdef YQ2_GL1_GLES
		base += (best.top * BLOCK_WIDTH) * LIGHTMAP_BYTES;

		R_Bind(gl_state.lightmap_textures + i + lmtex);
		PP_DP_WORLD_ADD(DPW_LM_UPLOAD_SETUP_MS, PP_DPClock() - dp_setup_started);
		PP_DP_WORLD_ADD(DPW_LM_REGEN_UPLOAD_TEXELS, BLOCK_WIDTH*(best.bottom-best.top));

		{
			double upload_started = PP_DPClock();
			glTexSubImage2D(GL_TEXTURE_2D, 0, 0, best.top,
			BLOCK_WIDTH, best.bottom - best.top,
			GL_LIGHTMAP_FORMAT, GL_UNSIGNED_BYTE, base);
			PP_DP_WORLD_ADD(DPW_LM_UPLOAD_MS, PP_DPClock() - upload_started);
			PP_DP_WORLD_ADD(DPW_LM_UPLOAD_CALLS, 1);
			PP_DP_WORLD_ADD(DPW_LM_UPLOAD_BYTES, BLOCK_WIDTH*(best.bottom-best.top)*LIGHTMAP_BYTES);
		}
		PP_PERF(lightmap_bytes, BLOCK_WIDTH*(best.bottom-best.top)*LIGHTMAP_BYTES);
#else
		base += (best.top * BLOCK_WIDTH + best.left) * LIGHTMAP_BYTES;

		R_Bind(gl_state.lightmap_textures + i + lmtex);
		PP_DP_WORLD_ADD(DPW_LM_UPLOAD_SETUP_MS, PP_DPClock() - dp_setup_started);
		PP_DP_WORLD_ADD(DPW_LM_REGEN_UPLOAD_TEXELS, (best.right-best.left)*(best.bottom-best.top));

		{
			double upload_started = PP_DPClock();
			glTexSubImage2D(GL_TEXTURE_2D, 0, best.left, best.top,
			best.right - best.left, best.bottom - best.top,
			GL_LIGHTMAP_FORMAT, GL_UNSIGNED_BYTE, base);
			PP_DP_WORLD_ADD(DPW_LM_UPLOAD_MS, PP_DPClock() - upload_started);
			PP_DP_WORLD_ADD(DPW_LM_UPLOAD_CALLS, 1);
			PP_DP_WORLD_ADD(DPW_LM_UPLOAD_BYTES, (best.right-best.left)*(best.bottom-best.top)*LIGHTMAP_BYTES);
		}
		PP_PERF(lightmap_bytes, (best.right-best.left)*(best.bottom-best.top)*LIGHTMAP_BYTES);
#endif
	}

#ifndef YQ2_GL1_GLES
	if (pixelstore_set)
	{
		double started = pp_drawprofile_active ? PP_DPClock() : 0;
		glPixelStorei(GL_UNPACK_ROW_LENGTH, 0);
		PP_DP_WORLD_ADD(DPW_LM_UPLOAD_SETUP_MS, PP_DPClock() - started);
	}
#endif
}

static void
R_DrawTextureChains(void)
{
	int i;
	msurface_t *s;
	image_t *image;
	qboolean batch_world = r_gl1_batch_world && r_gl1_batch_world->value &&
		world_static_world && world_static_world->value &&
		world_batch_owner == r_worldmodel && world_batch_groups && world_batch_count;

	c_visible_textures = 0;

	if (!gl_config.multitexture)	// classic path
	{
		for (i = 0, image = gltextures; i < numgltextures; i++, image++)
		{
			if (!image->registration_sequence)
			{
				continue;
			}

			s = image->texturechain;

			if (!s)
			{
				continue;
			}

			c_visible_textures++;

			for ( ; s; s = s->texturechain)
			{
				R_UpdateGLBuffer(buf_singletex, image->texnum, 0, s->flags, 1);
				R_RenderBrushPoly(s);
			}

			image->texturechain = NULL;
		}
		R_ApplyGLBuffer();	// Flush the last batched array
	}
	else	// multitexture
	{
		R_BeginWorldArrayScope();
		for (i = 0, image = gltextures; i < numgltextures; i++, image++)
		{
			if (!image->registration_sequence || !image->texturechain)
			{
				continue;
			}

			c_visible_textures++;

			world_batch_range_t range = batch_world ? world_batch_ranges[i] : (world_batch_range_t){0};
			for (s = image->texturechain; s; s = s->texturechain)
			{
				int group = s->world_batch_group;
				if (range.count && group >= range.first && group < range.first + range.count)
				{
					world_batch_group_t *bucket = &world_batch_groups[group];
					s->world_batch_next = NULL;
					if (bucket->tail) bucket->tail->world_batch_next = s;
					else
					{
						bucket->head = s;
						if (range.active_last) world_batch_groups[range.active_last].next_active = group;
						else range.active_first = group;
						range.active_last = group;
					}
					bucket->tail = s;
					continue;
				}
				/* Preserve each visible special/coplanar barrier in chain order. */
				if (range.active_first) R_DrawWorldBucketRange(image, &range);
				if (!(s->flags & SURF_DRAWTURB))
				{
					R_UpdateGLBuffer(buf_mtex, image->texnum, s->lightmaptexturenum, 0, 1);
					R_RenderLightmappedPoly(s);
				}
			}
			if (range.active_first) R_DrawWorldBucketRange(image, &range);
		}
		R_EndWorldArrayScope();

		R_EnableMultitexture(false);	// force disabling, SURF_DRAWTURB surfaces may not exist

		for (i = 0, image = gltextures; i < numgltextures; i++, image++)
		{
			if (!image->registration_sequence || !image->texturechain)
			{
				continue;
			}

			for (s = image->texturechain; s; s = s->texturechain)
			{
				if (s->flags & SURF_DRAWTURB)
				{
					R_UpdateGLBuffer(buf_singletex, image->texnum, 0, s->flags, 1);
					R_RenderBrushPoly(s);
				}
			}

			image->texturechain = NULL;
		}
		R_ApplyGLBuffer();
	}
}

static void
R_DrawInlineBModel(entity_t *currententity, const model_t *currentmodel)
{
	int i, k;
	cplane_t *pplane;
	float dot;
	msurface_t *psurf;
	dlight_t *lt;
	image_t *image;
	msurface_t **order = r_gl1_batch_inline && r_gl1_batch_inline->value &&
		inline_static_world && inline_static_world->value && gl_config.multitexture &&
		!(currententity->flags & RF_TRANSLUCENT) ? currentmodel->inline_surface_order : NULL;

	/* calculate dynamic lighting for bmodel */
	if (!gl_config.multitexture && !gl1_flashblend->value)
	{
		lt = r_newrefdef.dlights;

		for (k = 0; k < r_newrefdef.num_dlights; k++, lt++)
		{
			R_MarkLights(lt, 1 << k,
				currentmodel->nodes + currentmodel->firstnode,
				r_dlightframecount, R_MarkSurfaceLights);
		}
	}

	if (currententity->flags & RF_TRANSLUCENT)
	{
		glEnable(GL_BLEND);
		glColor4f(1, 1, 1, 0.25);
		R_TexEnv(GL_MODULATE);
	}
	else R_BeginWorldArrayScope();

	/* draw texture */
	for (i = 0; i < currentmodel->nummodelsurfaces; i++)
	{
		psurf = order ? order[i] : &currentmodel->surfaces[currentmodel->firstmodelsurface + i];
		/* find which side of the node we are on */
		pplane = psurf->plane;

		dot = DotProduct(modelorg, pplane->normal) - pplane->dist;

		/* draw the polygon */
		if (((psurf->flags & SURF_PLANEBACK) && (dot < -BACKFACE_EPSILON)) ||
			(!(psurf->flags & SURF_PLANEBACK) && (dot > BACKFACE_EPSILON)))
		{
			if (psurf->texinfo->flags & (SURF_TRANS33 | SURF_TRANS66))
			{
				/* add to the translucent chain */
				psurf->texturechain = r_alpha_surfaces;
				r_alpha_surfaces = psurf;
			}
			else
			{
				image = R_TextureAnimation(currententity, psurf->texinfo);

				if (gl_config.multitexture && !(psurf->flags & SURF_DRAWTURB))
				{
					// Dynamic lighting already generated in R_GetBrushesLighting()
					R_UpdateGLBuffer(buf_mtex, image->texnum, psurf->lightmaptexturenum, 0, 1);
					R_RenderLightmappedPoly(psurf);
				}
				else
				{
					R_UpdateGLBuffer(buf_singletex, image->texnum, 0, psurf->flags, 1);
					R_RenderBrushPoly(psurf);
				}
			}
		}
	}
	if (currententity->flags & RF_TRANSLUCENT) R_ApplyGLBuffer();
	else R_EndWorldArrayScope();

	if (!(currententity->flags & RF_TRANSLUCENT))
	{
		R_BlendLightmaps(currentmodel);
	}
	else
	{
		glDisable(GL_BLEND);
		glColor4f(1, 1, 1, 1);
		R_TexEnv(GL_REPLACE);
	}
}

void
R_DrawBrushModel(entity_t *currententity, const model_t *currentmodel)
{
	vec3_t mins, maxs;
	int i;
	qboolean rotated;

	if (currentmodel->nummodelsurfaces == 0)
	{
		return;
	}

	gl_state.currenttextures[0] = gl_state.currenttextures[1] = -1;

	if (currententity->angles[0] || currententity->angles[1] || currententity->angles[2])
	{
		rotated = true;

		for (i = 0; i < 3; i++)
		{
			mins[i] = currententity->origin[i] - currentmodel->radius;
			maxs[i] = currententity->origin[i] + currentmodel->radius;
		}
	}
	else
	{
		rotated = false;
		VectorAdd(currententity->origin, currentmodel->mins, mins);
		VectorAdd(currententity->origin, currentmodel->maxs, maxs);
	}

	if (r_cull->value && R_CullBox(mins, maxs, frustum))
	{
		return;
	}

	if (gl_zfix->value)
	{
		glEnable(GL_POLYGON_OFFSET_FILL);
	}

	glColor4f(1, 1, 1, 1);
	memset(gl_lms.lightmap_surfaces, 0, sizeof(gl_lms.lightmap_surfaces));

	VectorSubtract(r_newrefdef.vieworg, currententity->origin, modelorg);

	if (rotated)
	{
		vec3_t temp;
		vec3_t forward, right, up;

		VectorCopy(modelorg, temp);
		AngleVectors(currententity->angles, forward, right, up);
		modelorg[0] = DotProduct(temp, forward);
		modelorg[1] = -DotProduct(temp, right);
		modelorg[2] = DotProduct(temp, up);
	}

	glPushMatrix();
	currententity->angles[0] = -currententity->angles[0];
	currententity->angles[2] = -currententity->angles[2];
	R_RotateForEntity(currententity);
	currententity->angles[0] = -currententity->angles[0];
	currententity->angles[2] = -currententity->angles[2];

	if (gl_lightmap->value)
	{
		R_TexEnv(GL_REPLACE);
	}
	else
	{
		R_TexEnv(GL_MODULATE);
	}

	R_DrawInlineBModel(currententity, currentmodel);

	glPopMatrix();

	if (gl_zfix->value)
	{
		glDisable(GL_POLYGON_OFFSET_FILL);
	}
}

static void
R_RecursiveWorldNode(entity_t *currententity, mnode_t *node)
{
	int c, side, sidebit;
	cplane_t *plane;
	msurface_t *surf, **mark;
	mleaf_t *pleaf;
	float dot;
	image_t *image;

	if (node->contents == CONTENTS_SOLID)
	{
		return; /* solid */
	}

	if (node->visframe != r_visframecount)
	{
		return;
	}

	if (r_cull->value && R_CullBox(node->minmaxs, node->minmaxs + 3, frustum))
	{
		return;
	}

	/* if a leaf node, draw stuff */
	if (node->contents != CONTENTS_NODE)
	{
		pleaf = (mleaf_t *)node;

		/* check for door connected areas */
		if (!R_AreaVisible(r_newrefdef.areabits, pleaf))
			return;	// not visible

		mark = pleaf->firstmarksurface;
		c = pleaf->nummarksurfaces;

		if (c)
		{
			do
			{
				(*mark)->visframe = r_framecount;
				mark++;
			}
			while (--c);
		}

		return;
	}

	/* node is just a decision point, so go down the apropriate
	   sides find which side of the node we are on */
	plane = node->plane;

	switch (plane->type)
	{
		case PLANE_X:
			dot = modelorg[0] - plane->dist;
			break;
		case PLANE_Y:
			dot = modelorg[1] - plane->dist;
			break;
		case PLANE_Z:
			dot = modelorg[2] - plane->dist;
			break;
		default:
			dot = DotProduct(modelorg, plane->normal) - plane->dist;
			break;
	}

	if (dot >= 0)
	{
		side = 0;
		sidebit = 0;
	}
	else
	{
		side = 1;
		sidebit = SURF_PLANEBACK;
	}

	/* recurse down the children, front side first */
	R_RecursiveWorldNode(currententity, node->children[side]);

	/* draw stuff */
	for (c = node->numsurfaces,
		 surf = r_worldmodel->surfaces + node->firstsurface;
		 c; c--, surf++)
	{
		if (surf->visframe != r_framecount)
		{
			continue;
		}

		if ((surf->flags & SURF_PLANEBACK) != sidebit)
		{
			continue; /* wrong side */
		}

		PP_DP_WORLD_ADD(DPW_WORLD_VISIBLE_SURFACES, 1);
		if (surf->texinfo->flags & SURF_SKY)
		{
			/* just adds to visible sky bounds */
			R_AddSkySurface(surf);
		}
		else if (surf->texinfo->flags & (SURF_TRANS33 | SURF_TRANS66))
		{
			/* add to the translucent chain */
			surf->texturechain = r_alpha_surfaces;
			r_alpha_surfaces = surf;
			r_alpha_surfaces->texinfo->image = R_TextureAnimation(currententity, surf->texinfo);
		}
		else
		{
			/* the polygon is visible, so add it to the texture sorted chain */
			image = R_TextureAnimation(currententity, surf->texinfo);
			surf->texturechain = image->texturechain;
			image->texturechain = surf;

			if (gl_config.multitexture && !(surf->texinfo->flags & SURF_WARP))	// needed for R_RegenAllLightmaps()
			{
				surf->lightmapchain = gl_lms.lightmap_surfaces[surf->lightmaptexturenum];
				gl_lms.lightmap_surfaces[surf->lightmaptexturenum] = surf;
			}
		}
	}

	/* recurse down the back side */
	R_RecursiveWorldNode(currententity, node->children[!side]);
}

/*
 * This is for the RegenAllLightmaps() function to be able to regenerate
 * lighting not only for the world, but also for the brushes in the entity list.
 * Logic extracted from R_DrawBrushModel() & R_DrawInlineBModel().
 */
static void
R_GetBrushesLighting(void)
{
	int i, k;
	vec3_t mins, maxs;
	msurface_t *surf;
	cplane_t *pplane;
	dlight_t *lt;
	float dot;

	if (!gl_config.multitexture || !r_drawentities->value || gl1_flashblend->value)
	{
		return;
	}

	for (i = 0; i < r_newrefdef.num_entities; i++)
	{
		entity_t *currententity = &r_newrefdef.entities[i];

		if (currententity->flags & RF_BEAM)
		{
			continue;
		}

		const model_t *currentmodel = currententity->model;

		if (!currentmodel || currentmodel->type != mod_brush || currentmodel->nummodelsurfaces == 0)
		{
			continue;
		}

		PP_DP_WORLD_ADD(DPW_BRUSH_LIGHT_MODELS, 1);
		// from R_DrawBrushModel()
		if (currententity->angles[0] || currententity->angles[1] || currententity->angles[2])
		{
			for (k = 0; k < 3; k++)
			{
				mins[k] = currententity->origin[k] - currentmodel->radius;
				maxs[k] = currententity->origin[k] + currentmodel->radius;
			}
		}
		else
		{
			VectorAdd(currententity->origin, currentmodel->mins, mins);
			VectorAdd(currententity->origin, currentmodel->maxs, maxs);
		}

		if (r_cull->value && R_CullBox(mins, maxs, frustum))
		{
			continue;
		}

		// from R_DrawInlineBModel()
		lt = r_newrefdef.dlights;

		for (k = 0; k < r_newrefdef.num_dlights; k++, lt++)
		{
			PP_DP_WORLD_ADD(DPW_BRUSH_LIGHT_DLIGHT_TESTS, 1);
			R_MarkLights(lt, 1 << k,
				currentmodel->nodes + currentmodel->firstnode,
				r_dlightframecount, R_MarkSurfaceLights);
		}

		surf = &currentmodel->surfaces[currentmodel->firstmodelsurface];

		for (k = 0; k < currentmodel->nummodelsurfaces; k++, surf++)
		{
			PP_DP_WORLD_ADD(DPW_BRUSH_LIGHT_SURFACE_TESTS, 1);
			if (surf->texinfo->flags & (SURF_TRANS33 | SURF_TRANS66 | SURF_WARP)
				|| surf->flags & SURF_DRAWTURB || surf->lmchain_frame == r_framecount)
			{
				continue;	// either not affected by light, or already in the chain
			}

			// find which side of the node we are on
			pplane = surf->plane;
			dot = DotProduct(modelorg, pplane->normal) - pplane->dist;

			if (((surf->flags & SURF_PLANEBACK) && (dot < -BACKFACE_EPSILON)) ||
				(!(surf->flags & SURF_PLANEBACK) && (dot > BACKFACE_EPSILON)))
			{
				surf->lmchain_frame = r_framecount;	// don't add this twice to the chain
				surf->lightmapchain = gl_lms.lightmap_surfaces[surf->lightmaptexturenum];
				gl_lms.lightmap_surfaces[surf->lightmaptexturenum] = surf;
			}
		}
	}
}

void
R_DrawWorld(void)
{
	entity_t ent;

	if (!r_drawworld->value)
	{
		return;
	}

	if (r_newrefdef.rdflags & RDF_NOWORLDMODEL)
	{
		return;
	}

	PP_DP_WORLD_ADD(DPW_LM_ATLAS_COUNT, gl_lms.current_lightmap_texture > 0 ? gl_lms.current_lightmap_texture - 1 : 0);

	VectorCopy(r_newrefdef.vieworg, modelorg);

	/* auto cycle the world frame for texture animation */
	memset(&ent, 0, sizeof(ent));
	ent.frame = (int)(r_newrefdef.time * 2);

	gl_state.currenttextures[0] = gl_state.currenttextures[1] = -1;

	glColor4f(1, 1, 1, 1);
	memset(gl_lms.lightmap_surfaces, 0, sizeof(gl_lms.lightmap_surfaces));

	R_ClearSkyBox();
	{
		double started = PP_DPClock();
		R_RecursiveWorldNode(&ent, r_worldmodel->nodes);
		PP_DP_WORLD_ADD(DPW_WORLD_MARK_MS, PP_DPClock() - started);
	}
	{
		double started = PP_DPClock();
		R_GetBrushesLighting();
		PP_DP_WORLD_ADD(DPW_BRUSH_LIGHT_MS, PP_DPClock() - started);
	}
	{
		double started = PP_DPClock();
		R_RegenAllLightmaps();
		PP_DP_WORLD_ADD(DPW_LM_REGEN_MS, PP_DPClock() - started);
	}
	{
		double started = PP_DPClock();
		uint64_t draws = PP_DPTotalDraws();
		R_DrawTextureChains();
		PP_DP_WORLD_ADD(DPW_WORLD_CHAIN_MS, PP_DPClock() - started);
		PP_DP_WORLD_ADD(DPW_WORLD_CHAIN_DRAWS, PP_DPTotalDraws() - draws);
	}
	{
		double started = PP_DPClock();
		uint64_t draws = PP_DPTotalDraws();
		R_BlendLightmaps(r_worldmodel);
		PP_DP_WORLD_ADD(DPW_WORLD_BLEND_MS, PP_DPClock() - started);
		PP_DP_WORLD_ADD(DPW_WORLD_BLEND_DRAWS, PP_DPTotalDraws() - draws);
	}
	{
		double started = PP_DPClock();
		uint64_t draws = PP_DPTotalDraws();
		R_DrawSkyBox();
		PP_DP_WORLD_ADD(DPW_WORLD_SKY_MS, PP_DPClock() - started);
		PP_DP_WORLD_ADD(DPW_WORLD_SKY_DRAWS, PP_DPTotalDraws() - draws);
	}
	R_DrawTriangleOutlines();
}

/*
 * Mark the leaves and nodes that are
 * in the PVS for the current cluster
 */
void
R_MarkLeaves(void)
{
	const byte *vis;
	YQ2_ALIGNAS_TYPE(int) byte fatvis[MAX_MAP_LEAFS / 8];
	mnode_t *node;
	int i, c;
	mleaf_t *leaf;
	int cluster;
	if (!r_viscache) r_viscache = ri.Cvar_Get("r_viscache", "1", 0);

	if ((r_oldviewcluster == r_viewcluster) &&
		(r_oldviewcluster2 == r_viewcluster2) &&
		!r_novis->value && !previous_allvisible &&
		(r_viewcluster != -1))
	{
		PP_PERF(pvs_hits, 1);
		return;
	}

	/* development aid to let you run around
	   and see exactly where the pvs ends */
	if (r_lockpvs->value)
	{
		return;
	}

	r_visframecount++;
	r_oldviewcluster = r_viewcluster;
	r_oldviewcluster2 = r_viewcluster2;
	previous_allvisible = r_novis->value || (r_viewcluster == -1) || !r_worldmodel->vis;
	if (!previous_allvisible && r_viscache->value &&
		PP_RestoreVisibility(&visibility_cache, r_viewcluster, r_viewcluster2, r_visframecount))
	{
		PP_PERF(pvs_hits, 1);
		return;
	}
	PP_PERF(pvs_builds, 1);

	if (r_novis->value || (r_viewcluster == -1) || !r_worldmodel->vis)
	{
		/* mark everything */
		for (i = 0; i < r_worldmodel->numleafs; i++)
		{
			r_worldmodel->leafs[i].visframe = r_visframecount;
		}

		for (i = 0; i < r_worldmodel->numnodes; i++)
		{
			r_worldmodel->nodes[i].visframe = r_visframecount;
		}

		return;
	}

	vis = Mod_ClusterPVS(r_viewcluster, r_worldmodel);

	/* may have to combine two clusters because of solid water boundaries */
	if (r_viewcluster2 != r_viewcluster)
	{
		memcpy(fatvis, vis, (r_worldmodel->numleafs + 7) / 8);
		vis = Mod_ClusterPVS(r_viewcluster2, r_worldmodel);
		c = (r_worldmodel->numleafs + 31) / 32;

		for (i = 0; i < c; i++)
		{
			((int *)fatvis)[i] |= ((int *)vis)[i];
		}

		vis = fatvis;
	}

	for (i = 0, leaf = r_worldmodel->leafs;
		 i < r_worldmodel->numleafs;
		 i++, leaf++)
	{
		cluster = leaf->cluster;

		if (cluster == -1)
		{
			continue;
		}

		if (vis[cluster >> 3] & (1 << (cluster & 7)))
		{
			node = (mnode_t *)leaf;

			do
			{
				if (node->visframe == r_visframecount)
				{
					break;
				}

				node->visframe = r_visframecount;
				node = node->parent;
			}
			while (node);
		}
	}
	if (r_viscache->value)
		PP_SaveVisibility(&visibility_cache, r_viewcluster, r_viewcluster2,
			r_worldmodel->nodes, r_worldmodel->numnodes, r_worldmodel->leafs, r_worldmodel->numleafs, r_visframecount);
}
