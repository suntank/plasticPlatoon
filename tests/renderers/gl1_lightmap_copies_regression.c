/* Exercise the existing production regeneration/copy history across four views.
 * Controlled lightmap samples and stub GPU memory isolate copy/upload semantics;
 * actual lighting arithmetic and native pixels have separate renderer QA. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "../../src/client/refresh/gl1/gl1_surf.c"

glconfig_t gl_config;
glstate_t gl_state;
refdef_t r_newrefdef;
int r_framecount, cur_lm_copy;
pp_refperf_t pp_refperf;
int pp_drawprofile_active;
static cvar_t zero, one = {.value = 1};
cvar_t *r_perf = &zero, *r_fullbright = &zero, *gl1_dynamic = &one,
	*r_gl1_lightmap_opt = &zero;
static msurface_t surface;
static mtexinfo_t texture;
static lightstyle_t styles[MAX_LIGHTSTYLES];
static byte atlas[BLOCK_WIDTH * BLOCK_HEIGHT * LIGHTMAP_BYTES];
static byte gpu[3][BLOCK_WIDTH * BLOCK_HEIGHT * LIGHTMAP_BYTES];
static int binding, row_length, uploads, builds, view_color;

double PP_DPClock(void) { return 0; }
uint64_t PP_DPTotalDraws(void) { return 0; }
void PP_DPAddWorld(int metric, double value) { (void)metric; (void)value; }
qboolean R_Bind(int texnum) { binding = texnum; return true; }
void R_SetCacheState(msurface_t *s)
{
	for (int i = 0; i < MAXLIGHTMAPS && s->styles[i] != 255; ++i)
		s->cached_light[i] = r_newrefdef.lightstyles[s->styles[i]].white;
}
void R_BuildLightMap(msurface_t *s, byte *destination, int stride)
{
	++builds;
	int color = s->dlightframe == r_framecount ? view_color : 10;
	for (int y = 0; y < 2; ++y)
		for (int x = 0; x < 2; ++x)
			for (int c = 0; c < 4; ++c) destination[y * stride + x * 4 + c] = (byte)color;
}
void glPixelStorei(GLenum name, GLint value)
{
	assert(name == GL_UNPACK_ROW_LENGTH); row_length = value;
}
void glTexSubImage2D(GLenum target, GLint level, GLint x, GLint y, GLsizei width,
	GLsizei height, GLenum format, GLenum type, const GLvoid *pixels)
{
	assert(target == GL_TEXTURE_2D && level == 0 && format == GL_RGBA && type == GL_UNSIGNED_BYTE);
	int copy = (binding - gl_state.lightmap_textures - 1) / MAX_LIGHTMAPS;
	assert(copy >= 0 && copy < 3 && x >= 0 && y >= 0);
	assert(x + width <= BLOCK_WIDTH && y + height <= BLOCK_HEIGHT);
	int pitch = (row_length ? row_length : width) * 4;
	const byte *source = pixels;
	for (int row = 0; row < height; ++row)
		memcpy(gpu[copy] + ((y + row) * BLOCK_WIDTH + x) * 4, source + row * pitch, width * 4);
	++uploads;
}
static void render_view(int color, qboolean lit)
{
	++r_framecount; view_color = color;
	surface.dlightframe = lit ? r_framecount : 0;
	R_RegenAllLightmaps();
	int copy = gl_config.lightmapcopies ? cur_lm_copy : 0;
	byte expected = (byte)(lit ? color : 10);
	for (int y = 0; y < 2; ++y)
		for (int x = 0; x < 2; ++x)
			for (int c = 0; c < 4; ++c)
				assert(gpu[copy][((surface.light_t + y) * BLOCK_WIDTH + surface.light_s + x) * 4 + c] == expected);
	assert(!row_length);
}
int main(void)
{
	memset(atlas, 10, sizeof(atlas)); memset(gpu, 10, sizeof(gpu));
	surface.texinfo = &texture; surface.light_s = 3; surface.light_t = 4;
	surface.extents[0] = surface.extents[1] = 16;
	surface.styles[0] = 0; surface.styles[1] = 255; surface.cached_light[0] = 3;
	styles[0].white = 3; r_newrefdef.lightstyles = styles;
	gl_config.multitexture = true; gl_config.lightmapcopies = true;
	gl_state.lightmap_textures = 1024;
	gl_lms.lightmap_surfaces[1] = &surface; gl_lms.lightmap_buffer[1] = atlas;
	for (int i = 0; i < 4; ++i) render_view(20 + i, true);
	assert(cur_lm_copy == 1); /* Fourth view safely reuses the first of three copies. */
	for (int i = 0; i < 7; ++i) render_view(0, false);
	assert(uploads >= 4 && builds >= 5);
	int quiet_uploads = uploads;
	for (int i = 0; i < 4; ++i) render_view(0, false);
	assert(uploads == quiet_uploads);
	gl_config.lightmapcopies = false;
	render_view(37, true); render_view(0, false);
	quiet_uploads = uploads; render_view(0, false); assert(uploads == quiet_uploads);
	int previous_copy = cur_lm_copy, previous_builds = builds;
	one.value = 0; R_RegenAllLightmaps();
	assert(cur_lm_copy == previous_copy && uploads == quiet_uploads && builds == previous_builds);
	puts("PASS lightmap copies: four camera colors, three-copy reuse, baked restore, history drain, quiet frames and single-copy/disabled fallback");
	return 0;
}
