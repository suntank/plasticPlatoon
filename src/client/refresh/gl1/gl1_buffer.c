/*
 * Copyright (C) 1997-2001 Id Software, Inc.
 * Copyright (C) 2024      Jaime Moreira
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
 * Drawing buffer: sort of a "Q3A shader" handler, allows to join multiple
 * draw calls into one, by grouping those which share the same
 * characteristics (mostly the same texture).
 *
 * =======================================================================
 */

#include "header/local.h"

#define GLBUFFER_RESET do { vtx_ptr = idx_ptr = 0; gl_buf.vt = gl_buf.tx = gl_buf.cl = 0; \
	gl_buf.external_xyz = gl_buf.external_st = NULL; gl_buf.external_indices = NULL; \
	gl_buf.xyz_vbo = gl_buf.st_vbo = gl_buf.index_ebo = 0; \
	gl_buf.external_index_count = gl_buf.external_vertex_count = 0; gl_buf.external_stride = 0; gl_buf.world_buffer = false; } while (0);

glbuffer_t gl_buf;	// our drawing buffer, used globally
int cur_lm_copy;	// which lightmap copy to use (when lightmapcopies=on)

static GLushort vtx_ptr, idx_ptr;	// pointers for array positions in gl_buf

extern void R_SetPerspective(GLdouble fovy);

void
R_ResetGLBuffer(void)
{
	GLBUFFER_RESET
}

/*
 * Draws what's stored in the buffer and clears it up
 */
void
R_ApplyGLBuffer(void)
{
	// Properties of batched draws here
	GLint vtx_size;
	qboolean texture, mtex, alpha, color, alias, texenv_set;

	if (!gl_buf.external_index_count && ((vtx_ptr == 0 && !gl_buf.world_buffer) || idx_ptr == 0))
	{
		return;
	}

	// defaults for drawing (mostly buf_singletex features)
	vtx_size = 3;
	texture = true;
	mtex = alpha = color = alias = texenv_set = false;

	// choosing features by type
	switch (gl_buf.type)
	{
		case buf_2d:
			vtx_size = 2;
			break;
		case buf_mtex:
			mtex = true;
			break;
		case buf_alpha:
			alpha = true;
			break;
		case buf_alias:
			alias = color = true;
			break;
		case buf_flash:
			color = true;
			/* fall through */
		case buf_shadow:
			texture = false;
			break;
		default:
			break;
	}

	R_EnableMultitexture(mtex);

	if (alias)
	{
		if (gl_buf.flags & RF_DEPTHHACK)
		{
			// hack the depth range to prevent view model from poking into walls
			glDepthRange(gldepthmin, gldepthmin + 0.3 * (gldepthmax - gldepthmin));
		}

		if (gl_buf.flags & RF_WEAPONMODEL)
		{
			glMatrixMode(GL_PROJECTION);
			glPushMatrix();
			glLoadIdentity();

			if (gl_lefthand->value == 1.0f)
			{
				glScalef(-1, 1, 1);
			}

			R_SetPerspective( (r_gunfov->value < 0) ? r_newrefdef.fov_y : r_gunfov->value );

			glMatrixMode(GL_MODELVIEW);

			if (gl_lefthand->value == 1.0f)
			{
				glCullFace(GL_BACK);
			}
		}

		glShadeModel(GL_SMOOTH);
		R_TexEnv(GL_MODULATE);

		if (gl_buf.flags & RF_TRANSLUCENT)
		{
			glEnable(GL_BLEND);
		}

		if (gl_buf.flags & (RF_SHELL_RED | RF_SHELL_GREEN |
			RF_SHELL_BLUE | RF_SHELL_DOUBLE | RF_SHELL_HALF_DAM))
		{
			texture = false;
			glDisable(GL_TEXTURE_2D);
		}
	}

	if (alpha)
	{
		// the textures are prescaled up for a better
		// lighting range, so scale it back down
		glColor4f(gl_state.inverse_intensity, gl_state.inverse_intensity,
				  gl_state.inverse_intensity, gl_buf.alpha);

	}
	else if (gl_buf.flags & SURF_DRAWTURB)
	{
		texenv_set = true;

		// This is a hack ontop of a hack. Warping surfaces like those generated
		// by R_EmitWaterPolys() don't have a lightmap. Original Quake II therefore
		// negated the global intensity on those surfaces, because otherwise they
		// would show up much too bright. When we implemented overbright bits this
		// hack modified the global GL state in an incompatible way. So implement
		// a new hack, based on overbright bits... Depending on the value set to
		// gl1_overbrightbits the result is different:

		//  0: Old behaviour.
		//  1: No overbright bits on the global scene but correct lighting on
		//     warping surfaces.
		//  2,4: Overbright bits on the global scene but not on warping surfaces.
		//       They oversaturate otherwise.

		if (gl1_overbrightbits->value)
		{
			R_TexEnv(GL_COMBINE);
			glTexEnvi(GL_TEXTURE_ENV, GL_RGB_SCALE, 1);
		}
		else
		{
			R_TexEnv(GL_MODULATE);
			glColor4f(gl_state.inverse_intensity, gl_state.inverse_intensity,
					  gl_state.inverse_intensity, 1.0f);
		}
	}

	glEnableClientState( GL_VERTEX_ARRAY );
	if (qglBindBuffer) qglBindBuffer(GL_ARRAY_BUFFER, gl_buf.xyz_vbo);
	glVertexPointer(vtx_size, GL_FLOAT, gl_buf.external_stride, gl_buf.xyz_vbo ? NULL :
		(gl_buf.external_xyz ? gl_buf.external_xyz : gl_buf.vtx));

	if (texture)
	{
		if (mtex)
		{
			// TMU 1: Lightmap texture
			int lmtexture = gl_state.lightmap_textures + gl_buf.texture[1];
			if (gl_config.lightmapcopies)
			{
				// Bind appropiate lightmap copy for this frame
				lmtexture += MAX_LIGHTMAPS * cur_lm_copy;
			}
			R_MBind(GL_TEXTURE1, lmtexture);

			if (gl1_overbrightbits->value)
			{
				R_TexEnv(GL_COMBINE);
				glTexEnvi(GL_TEXTURE_ENV, GL_RGB_SCALE, gl1_overbrightbits->value);
			}

			glEnableClientState(GL_TEXTURE_COORD_ARRAY);
			if (qglBindBuffer) qglBindBuffer(GL_ARRAY_BUFFER, gl_buf.world_buffer ? gl_buf.st_vbo : 0);
			glTexCoordPointer(2, GL_FLOAT, gl_buf.external_stride,
				gl_buf.world_buffer ? (const void *)(5*sizeof(float)) : gl_buf.tex[1]);

			// TMU 0: Color texture
			R_MBind(GL_TEXTURE0, gl_buf.texture[0]);
		}
		else
		{
			R_Bind(gl_buf.texture[0]);
		}

		glEnableClientState(GL_TEXTURE_COORD_ARRAY);
		if (qglBindBuffer) qglBindBuffer(GL_ARRAY_BUFFER, gl_buf.st_vbo);
		glTexCoordPointer(2, GL_FLOAT, gl_buf.external_stride, gl_buf.st_vbo ?
			(gl_buf.world_buffer ? (const void *)(3*sizeof(float)) : NULL) :
			(gl_buf.external_st ? gl_buf.external_st : gl_buf.tex[0]));
	}

	if (color)
	{
		glEnableClientState(GL_COLOR_ARRAY);
		if (qglBindBuffer) qglBindBuffer(GL_ARRAY_BUFFER, 0);
		glColorPointer(4, GL_UNSIGNED_BYTE, 0, gl_buf.clr);
	}

	// All set, we can finally draw
	GLsizei draw_count = gl_buf.external_index_count ? gl_buf.external_index_count : idx_ptr;
	if (qglBindBuffer) qglBindBuffer(GL_ELEMENT_ARRAY_BUFFER, gl_buf.index_ebo);
	PP_DrawElements(GL_TRIANGLES, draw_count, GL_UNSIGNED_SHORT, gl_buf.index_ebo ? NULL :
		(gl_buf.external_indices ? gl_buf.external_indices : gl_buf.idx));
	if (gl_buf.type == buf_alias || gl_buf.type == buf_shadow) PP_PERF(model_triangles, draw_count / 3);
	else if (gl_buf.type == buf_mtex || gl_buf.type == buf_singletex || gl_buf.type == buf_alpha)
		PP_PERF(world_triangles, draw_count / 3);
	if (!gl_buf.index_ebo) PP_PERF(client_index_bytes, draw_count * sizeof(GLushort));
	unsigned submitted_vertices = gl_buf.external_vertex_count ? gl_buf.external_vertex_count : vtx_ptr;
	if (!gl_buf.xyz_vbo) PP_PERF(client_vertex_bytes, submitted_vertices * vtx_size * sizeof(GLfloat));
	if (texture && !gl_buf.st_vbo) PP_PERF(client_vertex_bytes, submitted_vertices * 2 * sizeof(GLfloat));
	if (color) PP_PERF(client_vertex_bytes, submitted_vertices * 4);
	if (mtex && !gl_buf.world_buffer) PP_PERF(client_vertex_bytes, submitted_vertices * 2 * sizeof(GLfloat));
	if (qglBindBuffer)
	{
		qglBindBuffer(GL_ARRAY_BUFFER, 0);
		qglBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0);
	}
	// ... and now, turn back everything as it was

	if (color)
	{
		glDisableClientState(GL_COLOR_ARRAY);
	}

	if (texture)
	{
		glDisableClientState( GL_TEXTURE_COORD_ARRAY );
	}

	glDisableClientState( GL_VERTEX_ARRAY );

	if (texenv_set)
	{
		R_TexEnv(GL_REPLACE);
	}

	if (alias)
	{
		if (gl_buf.flags & (RF_SHELL_RED | RF_SHELL_GREEN |
			RF_SHELL_BLUE | RF_SHELL_DOUBLE | RF_SHELL_HALF_DAM))
		{
			glEnable(GL_TEXTURE_2D);
		}

		if (gl_buf.flags & RF_TRANSLUCENT)
		{
			glDisable(GL_BLEND);
		}

		R_TexEnv(GL_REPLACE);
		glShadeModel(GL_FLAT);

		if (gl_buf.flags & RF_WEAPONMODEL)
		{
			glMatrixMode(GL_PROJECTION);
			glPopMatrix();
			glMatrixMode(GL_MODELVIEW);
			if (gl_lefthand->value == 1.0F)
			{
				glCullFace(GL_FRONT);
			}
		}

		if (gl_buf.flags & RF_DEPTHHACK)
		{
			glDepthRange(gldepthmin, gldepthmax);
		}
	}

	GLBUFFER_RESET
}

/*
 * Sets current state of the buffer. Any change means "draw its contents now".
 */
void
R_UpdateGLBuffer(buffered_draw_t type, int colortex, int lighttex, int flags, float alpha)
{
	if ( gl_buf.type != type || gl_buf.texture[0] != colortex ||
		(gl_config.multitexture && type == buf_mtex && gl_buf.texture[1] != lighttex) ||
		((type == buf_singletex || type == buf_alias) && gl_buf.flags != flags) ||
		(type == buf_alpha && gl_buf.alpha != alpha))
	{
		R_ApplyGLBuffer();

		gl_buf.type = type;
		gl_buf.texture[0] = colortex;
		gl_buf.texture[1] = lighttex;
		gl_buf.flags = flags;
		gl_buf.alpha = alpha;
	}
}

/*
 * Stores a 2D drawing in the buffer.
 * ul = up-left corner, dr = down-right corner
 * v = vertex, t = texture, x/y = coordinates
 */
void
R_Buffer2DQuad(GLfloat ul_vx, GLfloat ul_vy, GLfloat dr_vx, GLfloat dr_vy,
	GLfloat ul_tx, GLfloat ul_ty, GLfloat dr_tx, GLfloat dr_ty)
{
	static const GLushort idx_max = MAX_INDICES - 7;
	static const GLushort vtx_max = MAX_VERTICES - 5;

	if (idx_ptr > idx_max || vtx_ptr > vtx_max)
	{
		R_ApplyGLBuffer();
	}

	// "Quad" = 2-triangle GL_TRIANGLE_FAN
	gl_buf.idx[idx_ptr]   = vtx_ptr;
	gl_buf.idx[idx_ptr+1] = vtx_ptr+1;
	gl_buf.idx[idx_ptr+2] = vtx_ptr+2;
	gl_buf.idx[idx_ptr+3] = vtx_ptr;
	gl_buf.idx[idx_ptr+4] = vtx_ptr+2;
	gl_buf.idx[idx_ptr+5] = vtx_ptr+3;
	idx_ptr += 6;

	// up left corner coords
	gl_buf.vtx[gl_buf.vt]   = ul_vx;
	gl_buf.vtx[gl_buf.vt+1] = ul_vy;
	// up right
	gl_buf.vtx[gl_buf.vt+2] = dr_vx;
	gl_buf.vtx[gl_buf.vt+3] = ul_vy;
	// down right
	gl_buf.vtx[gl_buf.vt+4] = dr_vx;
	gl_buf.vtx[gl_buf.vt+5] = dr_vy;
	// and finally, down left
	gl_buf.vtx[gl_buf.vt+6] = ul_vx;
	gl_buf.vtx[gl_buf.vt+7] = dr_vy;

	gl_buf.tex[0][gl_buf.tx]   = ul_tx;
	gl_buf.tex[0][gl_buf.tx+1] = ul_ty;
	gl_buf.tex[0][gl_buf.tx+2] = dr_tx;
	gl_buf.tex[0][gl_buf.tx+3] = ul_ty;
	gl_buf.tex[0][gl_buf.tx+4] = dr_tx;
	gl_buf.tex[0][gl_buf.tx+5] = dr_ty;
	gl_buf.tex[0][gl_buf.tx+6] = ul_tx;
	gl_buf.tex[0][gl_buf.tx+7] = dr_ty;

	vtx_ptr += 4;
	gl_buf.vt += 8;
	gl_buf.tx += 8;
}

/*
 * Set up indices with the proper shape for the next buffered vertices.
 * After calling this, GLBUFFER_VERTEX() must be called 'vertices_num' times.
 */
void
R_SetBufferIndices(GLenum primitive, GLuint vertices_num)
{
	int i;
	if (gl_buf.world_buffer) R_ApplyGLBuffer();

	if ( vtx_ptr + vertices_num >= MAX_VERTICES ||
		idx_ptr + ( (vertices_num - 2) * 3 ) >= MAX_INDICES )
	{
		R_ApplyGLBuffer();
	}

	switch (primitive)
	{
		case GL_TRIANGLE_FAN:
			for (i = 0; i < vertices_num-2; i++)
			{
				gl_buf.idx[idx_ptr]   = vtx_ptr;
				gl_buf.idx[idx_ptr+1] = vtx_ptr+i+1;
				gl_buf.idx[idx_ptr+2] = vtx_ptr+i+2;
				idx_ptr += 3;
			}
			break;
		case GL_TRIANGLE_STRIP:
			for (i = 0; i < vertices_num-2; i++)
			{
				if (i % 2 == 0)
				{
					gl_buf.idx[idx_ptr]   = vtx_ptr+i;
					gl_buf.idx[idx_ptr+1] = vtx_ptr+i+1;
					gl_buf.idx[idx_ptr+2] = vtx_ptr+i+2;
				}
				else	// backwards order
				{
					gl_buf.idx[idx_ptr]   = vtx_ptr+i+2;
					gl_buf.idx[idx_ptr+1] = vtx_ptr+i+1;
					gl_buf.idx[idx_ptr+2] = vtx_ptr+i;
				}
				idx_ptr += 3;
			}
			break;
		default:
			Com_DPrintf("%s: no such primitive %d\n", __func__, primitive);
			return;
	}

	// GLBUFFER_VERTEX() must be called as many times as vertices_num
	vtx_ptr += vertices_num;
}

void
R_CreateAliasBuffers(model_t *model)
{
	model->aliascache = Mod_BuildAliasCache(model->extradata);
	if (!model->aliascache) return;
	const pp_alias_topology_t *mesh = model->aliascache->topology;
	if (!qglGenBuffers) return;
	qglGenBuffers(1, &model->alias_ebo);
	qglBindBuffer(GL_ELEMENT_ARRAY_BUFFER, model->alias_ebo);
	qglBufferData(GL_ELEMENT_ARRAY_BUFFER, mesh->num_indices * sizeof(GLushort), mesh->indices, GL_STATIC_DRAW);
	pp_static_index_total += mesh->num_indices * sizeof(GLushort);
	qglGenBuffers(1, &model->alias_uv_vbo);
	qglBindBuffer(GL_ARRAY_BUFFER, model->alias_uv_vbo);
	qglBufferData(GL_ARRAY_BUFFER, mesh->num_vertices * 2 * sizeof(float), mesh->uv, GL_STATIC_DRAW);
	pp_static_vertex_total += mesh->num_vertices * 2 * sizeof(float);
	if (model->aliascache->static_xyz)
	{
		qglGenBuffers(1, &model->alias_xyz_vbo);
		qglBindBuffer(GL_ARRAY_BUFFER, model->alias_xyz_vbo);
		qglBufferData(GL_ARRAY_BUFFER, mesh->num_vertices * 3 * sizeof(float), model->aliascache->static_xyz, GL_STATIC_DRAW);
		pp_static_vertex_total += mesh->num_vertices * 3 * sizeof(float);
	}
	qglBindBuffer(GL_ARRAY_BUFFER, 0);
	qglBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0);
	if (glGetError() != GL_NO_ERROR)
	{
		qglDeleteBuffers(1, &model->alias_ebo);
		qglDeleteBuffers(1, &model->alias_uv_vbo);
		qglDeleteBuffers(1, &model->alias_xyz_vbo);
		model->alias_ebo = model->alias_uv_vbo = model->alias_xyz_vbo = 0;
		Com_Printf("%s: GPU allocation failed; using cached client arrays\n", model->name);
	}
}

void
R_FreeAliasBuffers(model_t *model)
{
	if (qglDeleteBuffers)
	{
		qglDeleteBuffers(1, &model->alias_ebo);
		qglDeleteBuffers(1, &model->alias_uv_vbo);
		qglDeleteBuffers(1, &model->alias_xyz_vbo);
	}
	Mod_FreeAliasCache(model->aliascache);
	model->aliascache = NULL;
	model->alias_ebo = model->alias_uv_vbo = model->alias_xyz_vbo = 0;
}

void
R_DrawAliasCache(const model_t *model, const float *positions, qboolean static_pose)
{
	const pp_alias_topology_t *mesh = model->aliascache->topology;
	gl_buf.external_xyz = positions;
	gl_buf.external_st = mesh->uv;
	gl_buf.external_indices = mesh->indices;
	gl_buf.external_vertex_count = mesh->num_vertices;
	gl_buf.external_index_count = mesh->num_indices;
	gl_buf.xyz_vbo = static_pose ? model->alias_xyz_vbo : 0;
	gl_buf.st_vbo = model->alias_uv_vbo;
	gl_buf.index_ebo = model->alias_ebo;
	R_ApplyGLBuffer();
}

/* A visible draw packet contains only precomputed ushort indices. Vertices stay
 * resident across cameras. Partition at 65535 vertices for GLES1 index limits. */
static model_t *world_buffer_owner;
static GLuint *world_buffers;
static int num_world_buffers;
static GLushort *world_indices;
static cvar_t *gl1_static_world;

void
R_FreeWorldBuffers(model_t *model)
{
	if (model != world_buffer_owner) return;
	R_ApplyGLBuffer();
	if (qglDeleteBuffers && num_world_buffers)
		qglDeleteBuffers(num_world_buffers, world_buffers);
	for (int i = 0; i < model->numsurfaces; ++i)
	{
		glpoly_t *p = model->surfaces[i].polys;
		if (!p) continue;
		p->static_vbo = 0; p->static_indices = NULL; p->static_index_count = 0;
	}
	free(world_buffers); free(world_indices);
	world_buffers = NULL; world_indices = NULL;
	num_world_buffers = 0; world_buffer_owner = NULL;
}

void
R_BuildWorldBuffers(model_t *model)
{
	size_t index_count = 0, index_cursor = 0;
	int vertices = 0;
	float *staging;
	if (!gl1_static_world) gl1_static_world = ri.Cvar_Get("gl1_static_world", "1", 0);
	if (!qglGenBuffers) return;
	for (int i = 0; i < model->numsurfaces; ++i)
	{
		msurface_t *surf = model->surfaces+i;
		if (!(surf->texinfo->flags & (SURF_SKY | SURF_WARP | SURF_FLOWING)) && surf->polys &&
			surf->polys->numverts >= 3 && surf->polys->numverts <= 65535)
			index_count += (surf->polys->numverts-2)*3;
	}
	if (!index_count) return;
	world_buffers = calloc(model->numsurfaces, sizeof(*world_buffers));
	world_indices = malloc(index_count * sizeof(*world_indices));
	staging = malloc(65535 * VERTEXSIZE * sizeof(*staging));
	world_buffer_owner = model;
	if (!world_buffers || !world_indices || !staging)
	{
		free(staging); R_FreeWorldBuffers(model); return;
	}
	for (int i = 0; i < model->numsurfaces; ++i)
	{
		msurface_t *surf = model->surfaces+i;
		glpoly_t *p = surf->polys;
		if ((surf->texinfo->flags & (SURF_SKY | SURF_WARP | SURF_FLOWING)) ||
			!p || p->numverts < 3 || p->numverts > 65535) continue;
		if (vertices && vertices + p->numverts > 65535)
		{
			qglBindBuffer(GL_ARRAY_BUFFER, world_buffers[num_world_buffers-1]);
			qglBufferData(GL_ARRAY_BUFFER, vertices * VERTEXSIZE * sizeof(float), staging, GL_STATIC_DRAW);
			pp_static_vertex_total += vertices * VERTEXSIZE * sizeof(float);
			vertices = 0;
		}
		if (!vertices) qglGenBuffers(1, &world_buffers[num_world_buffers++]);
		p->static_vbo = world_buffers[num_world_buffers-1];
		p->static_indices = world_indices + index_cursor;
		p->static_index_count = (p->numverts-2)*3;
		for (int triangle = 0; triangle < p->numverts-2; ++triangle)
		{
			world_indices[index_cursor++] = vertices;
			world_indices[index_cursor++] = vertices+triangle+1;
			world_indices[index_cursor++] = vertices+triangle+2;
		}
		memcpy(staging + vertices*VERTEXSIZE, p->verts, p->numverts * VERTEXSIZE * sizeof(float));
		vertices += p->numverts;
	}
	if (vertices)
	{
		qglBindBuffer(GL_ARRAY_BUFFER, world_buffers[num_world_buffers-1]);
		qglBufferData(GL_ARRAY_BUFFER, vertices * VERTEXSIZE * sizeof(float), staging, GL_STATIC_DRAW);
		pp_static_vertex_total += vertices * VERTEXSIZE * sizeof(float);
	}
	free(staging);
	qglBindBuffer(GL_ARRAY_BUFFER, 0);
	if (glGetError() != GL_NO_ERROR)
	{
		Com_Printf("Persistent world buffer unavailable; using scratch fallback.\n");
		R_FreeWorldBuffers(model);
	}
}

qboolean
R_BufferStaticPoly(const glpoly_t *poly)
{
	if (!poly->static_vbo || !gl1_static_world || !gl1_static_world->value) return false;
	if (vtx_ptr || (gl_buf.world_buffer && gl_buf.xyz_vbo != poly->static_vbo) ||
		idx_ptr + poly->static_index_count >= MAX_INDICES)
		R_ApplyGLBuffer();
	/* Very large individual faces keep the existing fallback; no ushort wrap. */
	if (poly->static_index_count >= MAX_INDICES) return false;
	gl_buf.world_buffer = true;
	gl_buf.xyz_vbo = gl_buf.st_vbo = poly->static_vbo;
	gl_buf.external_stride = VERTEXSIZE*sizeof(float);
	memcpy(gl_buf.idx+idx_ptr, poly->static_indices, poly->static_index_count*sizeof(GLushort));
	idx_ptr += poly->static_index_count;
	gl_buf.external_vertex_count += poly->numverts;
	return true;
}
