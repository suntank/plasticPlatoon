/* Test production static-buffer submission and ushort boundaries with stub GL.
 * No display, GL context, GPU synchronization or renderer test hooks required. */
#include <assert.h>
#include <stdio.h>
#include "../../src/client/refresh/gl1/gl1_buffer.c"

glconfig_t gl_config;
glstate_t gl_state;
refdef_t r_newrefdef;
pp_refperf_t pp_refperf;
float gldepthmin, gldepthmax;
static cvar_t zero, one = {.value = 1};
cvar_t *r_perf = &zero, *gl_lefthand = &zero, *r_gunfov = &zero, *gl1_overbrightbits = &zero;
cvar_t *r_gl1_world_arrays = &zero;
static GLuint bound_vbo, draw_vbo[32];
static int draws, indices, maximum_index, draw_count[32];
static const byte *expected_alias_colors;
static const float *expected_alias_xyz, *expected_alias_uv;
static int color_pointer_calls;

static void APIENTRY bind_buffer(GLenum target, GLuint buffer)
{
	if (target == GL_ARRAY_BUFFER) bound_vbo = buffer;
}
void (APIENTRY *qglBindBuffer)(GLenum, GLuint) = bind_buffer;
void glDrawElements(GLenum mode, GLsizei count, GLenum type, const GLvoid *data)
{
	assert(mode == GL_TRIANGLES && type == GL_UNSIGNED_SHORT);
	assert(count > 0 && count < MAX_INDICES && draws < 32);
	draw_vbo[draws] = bound_vbo; draw_count[draws++] = count; indices += count;
	const GLushort *elements = data;
	for (int i = 0; i < count; ++i)
	{
		assert(elements[i] < 65535);
		if (elements[i] > maximum_index) maximum_index = elements[i];
	}
}
qboolean R_Bind(int n) { (void)n; return true; }
void R_MBind(GLenum target, int n) { (void)target; (void)n; }
void R_SelectTexture(GLenum target) { (void)target; }
void R_EnableMultitexture(qboolean value) { (void)value; }
void R_TexEnv(GLenum value) { (void)value; }
void R_SetPerspective(GLdouble value) { (void)value; }
double PP_PerfNow(void) { return 0; }
void PP_DPDraw(void) { }
void PP_DPFlush(void) { }
void PP_DPSetFlush(unsigned reasons) { (void)reasons; }
void glEnable(GLenum value) { (void)value; }
void glDisable(GLenum value) { (void)value; }
void glEnableClientState(GLenum value) { (void)value; }
void glDisableClientState(GLenum value) { (void)value; }
void glShadeModel(GLenum value) { (void)value; }
void glMatrixMode(GLenum value) { (void)value; }
void glCullFace(GLenum value) { (void)value; }
void glPushMatrix(void) { }
void glPopMatrix(void) { }
void glLoadIdentity(void) { }
void glScalef(GLfloat x, GLfloat y, GLfloat z) { (void)x; (void)y; (void)z; }
void glDepthRange(GLclampd low, GLclampd high) { (void)low; (void)high; }
void glColor4f(GLfloat r, GLfloat g, GLfloat b, GLfloat a) { (void)r; (void)g; (void)b; (void)a; }
void glTexEnvi(GLenum target, GLenum name, GLint value) { (void)target; (void)name; (void)value; }
void glVertexPointer(GLint size, GLenum type, GLsizei stride, const GLvoid *pointer)
{
	if (gl_buf.type == buf_alias || gl_buf.type == buf_shadow)
	{
		assert(size == 3 && type == GL_FLOAT && stride == 0 && pointer == expected_alias_xyz);
		return;
	}
	assert(size == 3 && type == GL_FLOAT && stride == VERTEXSIZE * sizeof(float) && !pointer);
}
void glTexCoordPointer(GLint size, GLenum type, GLsizei stride, const GLvoid *pointer)
{
	if (gl_buf.type == buf_alias)
	{
		assert(size == 2 && type == GL_FLOAT && stride == 0 && pointer == expected_alias_uv);
		return;
	}
	assert(size == 2 && type == GL_FLOAT && stride == VERTEXSIZE * sizeof(float));
	assert(pointer == (const void *)(3 * sizeof(float)) || pointer == (const void *)(5 * sizeof(float)));
}
void glColorPointer(GLint size, GLenum type, GLsizei stride, const GLvoid *pointer)
{
	assert(gl_buf.type == buf_alias && size == 4 && type == GL_UNSIGNED_BYTE && stride == 0);
	assert(bound_vbo == 0 && pointer == expected_alias_colors);
	++color_pointer_calls;
}

int main(void)
{
	GLushort triangle[3] = {65532, 65533, 65534};
	glpoly_t poly = {0};
	gl1_static_world = &one; gl_config.multitexture = true;
	poly.static_vbo = 77; poly.static_indices = triangle;
	poly.static_index_count = 3; poly.numverts = 3;
	R_ResetGLBuffer(); R_UpdateGLBuffer(buf_mtex, 8, 2, 0, 1);
	assert(R_BufferStaticPoly(&poly)); poly.static_vbo = 78;
	assert(R_BufferStaticPoly(&poly)); R_ApplyGLBuffer();
	assert(draws == 2 && draw_vbo[0] == 77 && draw_vbo[1] == 78);
	assert(indices == 6 && maximum_index == 65534);

	draws = indices = 0; poly.static_vbo = 77;
	for (int i = 0; i < 21846; ++i)
	{
		R_UpdateGLBuffer(buf_mtex, 8, 2, 0, 1);
		assert(R_BufferStaticPoly(&poly));
	}
	R_ApplyGLBuffer();
	assert(draws == 2 && draw_count[0] == 65535 && draw_count[1] == 3 && indices == 65538);
	poly.static_index_count = MAX_INDICES;
	assert(!R_BufferStaticPoly(&poly) && draws == 2);
	one.value = 0; poly.static_index_count = 3;
	assert(!R_BufferStaticPoly(&poly));
	/* Execute real cached-alias dispatch with a stable external color pointer.
	 * The draw uses client colors with ARRAY_BUFFER0, does not copy gl_buf.clr,
	 * and cannot leave that pointer for legacy/shadow/empty-buffer paths. */
	float xyz[9] = {0}, uv[6] = {0}; byte colors[12] = {1,2,3,255};
	GLushort elements[3] = {0,1,2};
	pp_alias_topology_t mesh = {0}; mesh.num_vertices = 3; mesh.num_indices = 3;
	mesh.indices = elements; mesh.uv = uv;
	pp_alias_cache_t cache = {0}; cache.topology = &mesh;
	model_t model = {0}; model.aliascache = &cache;
	expected_alias_xyz = xyz; expected_alias_uv = uv; expected_alias_colors = colors;
	memset(gl_buf.clr,0xA5,12);
	R_ResetGLBuffer();R_UpdateGLBuffer(buf_alias,8,0,0,1);
	R_DrawAliasCacheColors(&model,xyz,true,colors);
	assert(color_pointer_calls == 1 && !alias_external_colors && !gl_buf.external_index_count);
	for (int i=0;i<12;++i)assert(gl_buf.clr[i] == 0xA5);
	expected_alias_colors = gl_buf.clr;
	R_UpdateGLBuffer(buf_alias,8,0,0,1);R_DrawAliasCache(&model,xyz,false);
	assert(color_pointer_calls == 2 && !alias_external_colors);
	R_UpdateGLBuffer(buf_shadow,0,0,0,1);R_DrawAliasCache(&model,xyz,false);
	assert(color_pointer_calls == 2 && !alias_external_colors);
	alias_external_colors = colors;R_ApplyGLBuffer();assert(!alias_external_colors);
	alias_external_colors = colors;R_ResetGLBuffer();assert(!alias_external_colors);
	/* A previous world packet must flush before the alias pointer is assigned. */
	one.value = 1;poly.static_vbo = 77;poly.static_index_count = 3;
	R_UpdateGLBuffer(buf_mtex,8,2,0,1);assert(R_BufferStaticPoly(&poly));
	R_UpdateGLBuffer(buf_alias,8,0,0,1);assert(!alias_external_colors);
	expected_alias_colors = colors;R_DrawAliasCacheColors(&model,xyz,true,colors);
	assert(color_pointer_calls == 3 && !alias_external_colors);
	puts("PASS real static buffer: ushort 65534, VBO switches, 65535-index capacity, oversized-face and disabled fallback");
	puts("PASS alias external colors: exact pointer/ARRAY_BUFFER0, no copy, legacy/shadow/reset/empty fallback and prior-packet flush");
	return 0;
}
