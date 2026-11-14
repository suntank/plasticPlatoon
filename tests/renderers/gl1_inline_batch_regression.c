/* Exercise the production inline registration/draw paths without a GL context.
 * The buffer stub records polygon/state order; independent real-buffer boundary
 * coverage lives in gl1_static_buffer_regression.c. GPL-2.0-or-later. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include "../../src/client/refresh/gl1/header/local.h"

static int fail_allocation = -1, allocation_number;
static void *test_malloc(size_t size)
{
	if (allocation_number++ == fail_allocation) return NULL;
	return malloc(size);
}
static void *test_calloc(size_t count, size_t size)
{
	if (allocation_number++ == fail_allocation) return NULL;
	return calloc(count, size);
}
#define malloc test_malloc
#define calloc test_calloc
#include "../../src/client/refresh/gl1/gl1_surf.c"
#undef malloc
#undef calloc

refimport_t ri;
glbuffer_t gl_buf;
glconfig_t gl_config;
glstate_t gl_state;
refdef_t r_newrefdef;
model_t *r_worldmodel;
float r_world_matrix[16];
int c_brush_polys, r_framecount, r_dlightframecount;
pp_refperf_t pp_refperf;
static cvar_t zero, one = {.value = 1}, batch_setting = {.value = 1}, static_setting = {.value = 1};
cvar_t *r_perf = &zero, *gl1_flashblend = &one, *gl1_dynamic = &zero,
	*r_fullbright = &one, *gl_lightmap = &zero, *gl1_saturatelighting = &zero,
	*gl1_overbrightbits = &zero, *gl_showtris = &zero;

static const glpoly_t *submitted[256];
static int colors[256], lightmaps[256], count, draws, pending;
static GLuint pending_vbo;
static qboolean blending;

static cvar_t *test_cvar(const char *name, const char *value, int flags)
{
	(void)value; (void)flags;
	if (!strcmp(name, "r_gl1_batch_inline")) return &batch_setting;
	assert(!strcmp(name, "gl1_static_world"));
	return &static_setting;
}
void R_ApplyGLBuffer(void) { if (pending) ++draws; pending = 0; }
void R_BeginWorldArrayScope(void) { }
void R_EndWorldArrayScope(void) { R_ApplyGLBuffer(); }
void R_UpdateGLBuffer(buffered_draw_t type, int color, int lm, int flags, float alpha)
{
	if (gl_buf.type != type || gl_buf.texture[0] != color ||
		(type == buf_mtex && gl_buf.texture[1] != lm)) R_ApplyGLBuffer();
	gl_buf.type = type; gl_buf.texture[0] = color; gl_buf.texture[1] = lm;
	gl_buf.flags = flags; gl_buf.alpha = alpha;
}
qboolean R_BufferStaticPoly(const glpoly_t *poly)
{
	if (pending && pending_vbo != poly->static_vbo) R_ApplyGLBuffer();
	assert(count < 256);
	submitted[count] = poly; colors[count] = gl_buf.texture[0]; lightmaps[count] = gl_buf.texture[1];
	++count; pending = 1; pending_vbo = poly->static_vbo;
	return true;
}
void R_SetBufferIndices(GLenum type, GLuint vertices) { (void)type; (void)vertices; assert(0); }
void R_EmitWaterPolys(msurface_t *surface) { (void)R_BufferStaticPoly(surface->polys); }
void R_MarkSurfaceLights(dlight_t *l, int b, mnode_t *n, int f) { (void)l; (void)b; (void)n; (void)f; }
void R_BuildLightMap(msurface_t *s, byte *d, int stride) { (void)s; (void)d; (void)stride; }
void R_SetCacheState(msurface_t *s) { (void)s; }
qboolean R_Bind(int n) { (void)n; return true; }
void R_TexEnv(GLenum n) { (void)n; }
void R_EnableMultitexture(qboolean n) { (void)n; }
double PP_PerfNow(void) { return 0; }
void PP_DPDraw(void) { }
int pp_drawprofile_active;
double PP_DPClock(void) { return 0; }
uint64_t PP_DPTotalDraws(void) { return (uint64_t)draws; }
void PP_DPAddWorld(int metric, double value) { (void)metric; (void)value; }
void LM_InitBlock(void) { assert(0); }
void LM_UploadBlock(qboolean d) { (void)d; assert(0); }
qboolean LM_AllocBlock(int w, int h, int *x, int *y) { (void)w; (void)h; (void)x; (void)y; assert(0); return false; }
void Com_Error(int code, const char *format, ...) { (void)code; (void)format; abort(); }
void glEnable(GLenum what) { if (what == GL_BLEND) blending = true; }
void glDisable(GLenum what) { if (what == GL_BLEND) blending = false; }
void glColor4f(GLfloat r, GLfloat g, GLfloat b, GLfloat a) { (void)r; (void)g; (void)b; (void)a; }
void glDepthMask(GLboolean value) { (void)value; }
void glBlendFunc(GLenum a, GLenum b) { (void)a; (void)b; }
void glLoadMatrixf(const GLfloat *matrix) { (void)matrix; }
void glTexEnvi(GLenum target, GLenum name, GLint value) { (void)target; (void)name; (void)value; }
void glEnableClientState(GLenum array) { (void)array; }
void glDisableClientState(GLenum array) { (void)array; }
void glVertexPointer(GLint size, GLenum type, GLsizei stride, const GLvoid *p) { (void)size; (void)type; (void)stride; (void)p; }
void glTexCoordPointer(GLint size, GLenum type, GLsizei stride, const GLvoid *p) { (void)size; (void)type; (void)stride; (void)p; }
void glDrawArrays(GLenum mode, GLint first, GLsizei vertices) { (void)mode; (void)first; (void)vertices; assert(0); }
void glTexSubImage2D(GLenum t, GLint l, GLint x, GLint y, GLsizei w, GLsizei h, GLenum f, GLenum type, const GLvoid *p)
{ (void)t; (void)l; (void)x; (void)y; (void)w; (void)h; (void)f; (void)type; (void)p; assert(0); }

enum { FACES = 16 };
static msurface_t surfaces[FACES];
static glpoly_t polys[FACES];
static mtexinfo_t textures[FACES], animated;
static image_t images[3];
static cplane_t plane;
static GLushort indices[3] = {0, 1, 2};
static model_t world, models[2];
static entity_t entity;

static void clear_capture(void)
{
	memset(&gl_buf, 0, sizeof(gl_buf)); count = draws = pending = 0; pending_vbo = 0;
	r_alpha_surfaces = NULL; c_brush_polys = 0;
}
static void build(void)
{
	allocation_number = 0;
	R_BuildInlineSurfaceOrders(&world);
}
static void setup(void)
{
	R_FreeInlineSurfaceOrders(&world);
	memset(surfaces, 0, sizeof(surfaces)); memset(polys, 0, sizeof(polys));
	memset(textures, 0, sizeof(textures)); memset(models, 0, sizeof(models));
	memset(&world, 0, sizeof(world)); memset(&entity, 0, sizeof(entity));
	memset(&plane, 0, sizeof(plane)); plane.normal[0] = 1;
	world.submodels = models; world.numsubmodels = 2;
	models[1].surfaces = surfaces; models[1].nummodelsurfaces = FACES;
	r_worldmodel = &world; modelorg[0] = 32; modelorg[1] = modelorg[2] = 0;
	gl_config.multitexture = true; batch_setting.value = static_setting.value = 1;
	fail_allocation = -1; ri.Cvar_Get = test_cvar;
	for (int i = 0; i < 3; ++i) images[i].texnum = 10 + i;
	for (int i = 0; i < FACES; ++i)
	{
		surfaces[i].plane = &plane; surfaces[i].polys = &polys[i]; surfaces[i].texinfo = &textures[i];
		surfaces[i].lightmaptexturenum = (i / 2) % 2; surfaces[i].styles[0] = 255;
		textures[i].image = &images[i % 2]; polys[i].static_vbo = 1 + (i / 4) % 2;
		polys[i].static_indices = indices; polys[i].static_index_count = 3; polys[i].numverts = 4;
		for (int v = 0; v < 4; ++v)
		{
			polys[i].verts[v][0] = 0;
			polys[i].verts[v][1] = i * 3 + (v == 1 || v == 2);
			polys[i].verts[v][2] = v >= 2;
		}
	}
	clear_capture();
}
static void draw(void) { clear_capture(); R_DrawInlineBModel(&entity, &models[1]); }
static void source_order(void)
{
	assert(count == FACES);
	for (int i = 0; i < FACES; ++i) assert(submitted[i] == &polys[i]);
}
static void same_visible_set(void)
{
	assert(count == FACES && c_brush_polys == FACES);
	unsigned seen = 0;
	for (int i = 0; i < count; ++i)
	{
		int source = (int)(submitted[i] - polys);
		assert(source >= 0 && source < FACES && !(seen & (1u << source)));
		seen |= 1u << source;
		assert(colors[i] == images[source % 2].texnum);
		assert(lightmaps[i] == surfaces[source].lightmaptexturenum);
	}
	assert(seen == (1u << FACES) - 1);
}

int main(void)
{
	setup(); build(); assert(models[1].inline_surface_order);
	batch_setting.value = 0; draw(); source_order(); int legacy_draws = draws;
	batch_setting.value = 1; draw(); same_visible_set(); assert(draws == 8 && draws < legacy_draws);
	assert(!pending);
	R_DrawInlineBModel(&entity, &models[1]);
	assert(count == FACES * 2 && draws == 16 && !pending); /* Entity-end flush. */
	for (int i = 1; i < FACES; ++i)
	{
		msurface_t *a = models[1].inline_surface_order[i - 1], *b = models[1].inline_surface_order[i];
		assert(R_InlineMaterialCompare(a, b) <= 0);
		if (!R_InlineMaterialCompare(a, b)) assert(a < b);
	}
	static_setting.value = 0; draw(); source_order(); static_setting.value = 1;
	gl_config.multitexture = false; draw(); source_order(); gl_config.multitexture = true;
	entity.flags = RF_TRANSLUCENT; draw(); source_order(); assert(!blending); entity.flags = 0;
	/* Every view repeats visibility checks against its own transformed camera. */
	surfaces[1].flags = SURF_PLANEBACK; modelorg[0] = -32; draw();
	assert(count == 1 && submitted[0] == &polys[1]); surfaces[1].flags = 0;

	setup(); textures[5].flags = SURF_TRANS33; textures[9].flags = SURF_TRANS66;
	build(); draw(); assert(count == FACES - 2);
	assert(r_alpha_surfaces == &surfaces[9] && r_alpha_surfaces->texturechain == &surfaces[5]);
	assert(models[1].inline_surface_order[5] == &surfaces[5] && models[1].inline_surface_order[9] == &surfaces[9]);
	R_DrawAlphaSurfaces(); assert(count == FACES && submitted[FACES - 2] == &polys[9] && submitted[FACES - 1] == &polys[5]);
	assert(!r_alpha_surfaces && !blending);

	setup(); textures[3].flags = SURF_SKY; textures[5].flags = SURF_FLOWING;
	textures[9].next = &animated; textures[9].numframes = 2; animated.image = &images[2];
	textures[12].flags = SURF_WARP; surfaces[12].flags = SURF_DRAWTURB; polys[12].static_vbo = 0;
	build(); entity.frame = 1; draw(); assert(count == FACES);
	const int barriers[] = {3, 5, 9, 12};
	for (unsigned i = 0; i < sizeof(barriers) / sizeof(*barriers); ++i)
		assert(models[1].inline_surface_order[barriers[i]] == &surfaces[barriers[i]]);
	for (int i = 0; i < count; ++i) if (submitted[i] == &polys[9]) assert(colors[i] == images[2].texnum);

	setup(); /* Different lightmaps overlap on the same plane: keep BOTH barriers. */
	for (int v = 0; v < 4; ++v) polys[2].verts[v][1] = polys[0].verts[v][1] + .25f;
	build(); assert(models[1].inline_surface_order[0] == &surfaces[0]);
	assert(models[1].inline_surface_order[2] == &surfaces[2]); draw(); same_visible_set();
	R_FreeInlineSurfaceOrders(&world); assert(!models[1].inline_surface_order);
	R_FreeInlineSurfaceOrders(&world); build(); assert(models[1].inline_surface_order);
	for (int fail = 0; fail < 2; ++fail)
	{
		fail_allocation = fail; build(); assert(!models[1].inline_surface_order);
		draw(); source_order();
	}
	fail_allocation = -1; build(); assert(models[1].inline_surface_order);
	R_FreeInlineSurfaceOrders(&world);
	puts("PASS inline batches: visible set/state, stable keys, fewer draws, per-view culling, alpha order, special/animation barriers, coplanar overlaps, fallback, allocation failure and lifecycle");
	return 0;
}
