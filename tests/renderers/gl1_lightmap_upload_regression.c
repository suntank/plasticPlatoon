/* Run the real atlas regeneration/upload path against controlled GPU memory.
 * Disjoint rectangles, atlas edges, camera scopes and copy history must deliver
 * current visible pixels while respecting stride and atlas bounds. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "../../src/client/refresh/gl1/gl1_surf.c"

enum { ATLASES = 3, SURFACES = 6, ATLAS_BYTES = BLOCK_WIDTH * BLOCK_HEIGHT * LIGHTMAP_BYTES };
glconfig_t gl_config;
glstate_t gl_state;
refdef_t r_newrefdef;
int r_framecount, cur_lm_copy, pp_drawprofile_active;
pp_refperf_t pp_refperf;
static cvar_t zero, one = {.value = 1}, optimization;
cvar_t *r_perf = &zero, *r_fullbright = &zero, *gl1_dynamic = &one,
	*r_gl1_lightmap_opt = &optimization;
static msurface_t faces[ATLASES][SURFACES];
static mtexinfo_t texture;
static lightstyle_t styles[MAX_LIGHTSTYLES];
static byte cpu[ATLASES][ATLAS_BYTES], gpu[3][ATLASES][ATLAS_BYTES];
static int bound_texture, unpack_stride, view_number, uploads;
static unsigned long upload_texels;
static const int rectangles[SURFACES][4] = {
	{2,3,2,3}, {90,100,3,4}, {36,48,5,7}, {48,2,16,1}, {15,15,17,17}, {120,4,8,5}
};

double PP_DPClock(void) { return 0; }
uint64_t PP_DPTotalDraws(void) { return 0; }
void PP_DPAddWorld(int metric, double value) { (void)metric; (void)value; }
qboolean R_Bind(int texnum) { bound_texture = texnum; return true; }
void R_SetCacheState(msurface_t *s)
{
	for (int i = 0; i < MAXLIGHTMAPS && s->styles[i] != 255; ++i)
		s->cached_light[i] = r_newrefdef.lightstyles[s->styles[i]].white;
}
static void expected_pixel(msurface_t *s, byte color[4])
{
	int local = 0;
	for (int i = 0; i < SURFACES; ++i) if (s->light_s == rectangles[i][0] && s->light_t == rectangles[i][1]) local = i;
	int lit = s->dlightframe == r_framecount;
	color[0] = (byte)(20 + s->lightmaptexturenum * 7 + local + (lit ? (view_number % 7) * 17 : 0));
	color[1] = (byte)(30 + local * 11 + (int)styles[0].white);
	color[2] = (byte)(40 + (lit ? 60 : 0)); color[3] = 255;
}
void R_BuildLightMap(msurface_t *s, byte *destination, int stride)
{
	byte color[4]; expected_pixel(s, color);
	int width = (s->extents[0] >> 4) + 1, height = (s->extents[1] >> 4) + 1;
	for (int y = 0; y < height; ++y)
		for (int x = 0; x < width; ++x) memcpy(destination + y * stride + x * 4, color, 4);
}
#ifndef YQ2_GL1_GLES
void glPixelStorei(GLenum name, GLint value)
{
	assert(name == GL_UNPACK_ROW_LENGTH); unpack_stride = value;
}
#endif
static void test_TexSubImage2D(GLenum target, GLint level, GLint x, GLint y, GLsizei width,
	GLsizei height, GLenum format, GLenum type, const GLvoid *pixels)
{
	assert(target == GL_TEXTURE_2D && level == 0 && format == GL_RGBA && type == GL_UNSIGNED_BYTE);
	int relative = bound_texture - gl_state.lightmap_textures;
	int copy = relative / MAX_LIGHTMAPS, atlas = relative % MAX_LIGHTMAPS - 1;
	assert(copy >= 0 && copy < 3 && atlas >= 0 && atlas < ATLASES);
	assert(x >= 0 && y >= 0 && width > 0 && height > 0 && x + width <= BLOCK_WIDTH && y + height <= BLOCK_HEIGHT);
	int pitch = (unpack_stride ? unpack_stride : width) * 4;
	const byte *source = pixels;
	assert(source >= cpu[atlas] && source + (height - 1) * pitch + width * 4 <= cpu[atlas] + ATLAS_BYTES);
	for (int row = 0; row < height; ++row)
		memcpy(gpu[copy][atlas] + ((y + row) * BLOCK_WIDTH + x) * 4, source + row * pitch, width * 4);
	++uploads; upload_texels += (unsigned long)width * height;
}
#ifdef YQ2_GL1_GLES
PFNGLTEXSUBIMAGE2DPROC glad_glTexSubImage2D = test_TexSubImage2D;
#else
void glTexSubImage2D(GLenum target, GLint level, GLint x, GLint y, GLsizei width,
	GLsizei height, GLenum format, GLenum type, const GLvoid *pixels)
{
	test_TexSubImage2D(target, level, x, y, width, height, format, type, pixels);
}
#endif
static void render_view(qboolean all_visible, qboolean unlit)
{
	++view_number; ++r_framecount;
	memset(gl_lms.lightmap_surfaces, 0, sizeof(gl_lms.lightmap_surfaces));
	for (int a = 0; a < ATLASES; ++a)
		for (int i = SURFACES - 1; i >= 0; --i)
		{
			msurface_t *s = &faces[a][i];
			if (!all_visible && (i + view_number) % 3 == 0) continue;
			s->dlightframe = !unlit && (i + view_number) % 2 ? r_framecount : 0;
			s->lightmapchain = gl_lms.lightmap_surfaces[a + 1]; gl_lms.lightmap_surfaces[a + 1] = s;
		}
	R_RegenAllLightmaps();
	int copy = gl_config.lightmapcopies ? cur_lm_copy : 0;
	for (int a = 0; a < ATLASES; ++a)
	{
		/* The complete selected GPU atlas, including currently invisible and
		 * unchanged pixels, must equal the authoritative CPU atlas. */
		assert(!memcmp(gpu[copy][a], cpu[a], ATLAS_BYTES));
		for (msurface_t *s = gl_lms.lightmap_surfaces[a + 1]; s; s = s->lightmapchain)
		{
			byte color[4]; expected_pixel(s, color);
			int width = (s->extents[0] >> 4) + 1, height = (s->extents[1] >> 4) + 1;
			for (int y = 0; y < height; ++y)
				for (int x = 0; x < width; ++x)
					assert(!memcmp(gpu[copy][a] + ((s->light_t + y) * BLOCK_WIDTH + s->light_s + x) * 4, color, 4));
		}
	}
	assert(!unpack_stride);
}
int main(void)
{
	gl_config.multitexture = true; gl_state.lightmap_textures = 1024;
	r_newrefdef.lightstyles = styles; styles[0].white = 3;
	unsigned long baseline_texels[2] = {0}; int baseline_uploads[2] = {0};
	for (int optimized = 0; optimized <= 1; ++optimized)
	for (int copies = 0; copies <= 1; ++copies)
	{
		optimization.value = optimized; int initial_uploads = uploads;
		unsigned long initial_texels = upload_texels;
		view_number = 0; cur_lm_copy = 0;
		gl_config.lightmapcopies = copies; memset(cpu, 7, sizeof(cpu)); memset(gpu, 7, sizeof(gpu));
		memset(faces, 0, sizeof(faces));
		for (int a = 0; a < ATLASES; ++a)
		{
			gl_lms.lightmap_buffer[a + 1] = cpu[a];
			for (int i = 0; i < SURFACES; ++i)
			{
				msurface_t *s = &faces[a][i]; s->texinfo = &texture; s->lightmaptexturenum = a + 1;
				s->light_s = rectangles[i][0]; s->light_t = rectangles[i][1];
				s->extents[0] = (rectangles[i][2] - 1) * 16; s->extents[1] = (rectangles[i][3] - 1) * 16;
				s->styles[0] = 0; s->styles[1] = 255; s->cached_light[0] = -1;
			}
		}
		for (int view = 0; view < 48; ++view)
		{
			styles[0].white = view / 8 % 2 ? 4 : 3;
			render_view(false, false);
		}
		for (int view = 0; view < 12; ++view) render_view(true, true);
		int quiet = uploads;
		for (int view = 0; view < 4; ++view) render_view(true, true);
		assert(uploads == quiet);
		if (!optimized)
		{
			baseline_texels[copies] = upload_texels - initial_texels;
			baseline_uploads[copies] = uploads - initial_uploads;
		}
		else
		{
			assert(baseline_texels[copies] == upload_texels - initial_texels);
			assert(baseline_uploads[copies] == uploads - initial_uploads);
		}
	}
	assert(uploads && upload_texels);
	puts("PASS real lightmap uploads: sparse/edge rectangles, atlas strides, 256 scoped views, changing styles, full GPU atlas bytes, optimization on/off, three-copy history and quiet restoration"
#ifdef YQ2_GL1_GLES
		" (GLES full-width strips)"
#else
		" (GL1 rectangles)"
#endif
	);
	return 0;
}
