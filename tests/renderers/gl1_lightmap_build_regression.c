/* Compare the production full lightmap builder with its frozen scalar reference.
 * Synthetic inputs cover style/modulation/gamma ordering, fractional cutoffs,
 * negative/overbright channels, 31-light masks, per-view inputs and odd strides.
 * No GL context, game assets, maps or renderer test hooks are needed. */
#include <assert.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#if defined(__GNUC__)
/* Keep the legacy size guard unchanged in both compared implementations. */
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wsign-compare"
#endif
#include "../../src/client/refresh/gl1/gl1_light.c"
#include "gl1_lightmap_scalar_reference.inc"
#if defined(__GNUC__)
#pragma GCC diagnostic pop
#endif

refdef_t r_newrefdef;
glstate_t gl_state;
int r_framecount, pp_drawprofile_active;
unsigned char gammatable[256];
static cvar_t modulation = {.value = 1};
static cvar_t optimization;
cvar_t *r_modulate = &modulation, *r_gl1_lightmap_opt = &optimization;
double PP_DPClock(void) { return 0; }
void PP_DPAddWorld(int metric, double value) { (void)metric; (void)value; }
void Com_Error(int code, const char *format, ...)
{
	va_list args; va_start(args, format); vfprintf(stderr, format, args); va_end(args);
	fprintf(stderr, " (code %d)\n", code); abort();
}

static unsigned random_state = 0x3467b921;
static unsigned next_random(void)
{
	random_state = random_state * 1664525u + 1013904223u;
	return random_state;
}

/* Compare the adder's raw floats directly, including rejection boundaries that
 * gamma/clamping could conceal. Extreme finite coordinates stay below the
 * legacy signed-distance overflow range; INT_MIN negation is undefined in the
 * original scalar code and is deliberately not treated as a supported input. */
static void test_dynamic_float_outputs(void)
{
	static const int dimensions[][2] = {{1,1},{2,3},{5,7},{17,13},{29,29},{33,26},{83,10},{867,1}};
	static const float coordinates[] = {-.75f,-.25f,0,.25f,.75f,63.75f,-64.75f,0x1p29f,-0x1p29f};
	static const float intensities[] = {64,64.000008f,79.99999f,80,80.000008f,128,256,0x1p30f};
	for (int test = 0; test < 256; ++test)
	{
		msurface_t surface = {0}; mtexinfo_t texture = {0}; cplane_t plane = {0};
		dlight_t lights[MAX_DLIGHTS] = {0}; float initial[34 * 34 * 3];
		int width = dimensions[test % 8][0], height = dimensions[test % 8][1], floats = width * height * 3;
		surface.texinfo = &texture; surface.plane = &plane; plane.normal[2] = 1;
		texture.vecs[0][0] = 1; texture.vecs[1][1] = 1;
		surface.extents[0] = (short)((width - 1) * 16); surface.extents[1] = (short)((height - 1) * 16);
		r_newrefdef.dlights = lights; r_newrefdef.num_dlights = test % 3 ? 1 : 31;
		for (int i = 0; i < r_newrefdef.num_dlights; ++i)
		{
			surface.dlightbits |= 1u << i;
			lights[i].origin[0] = coordinates[(test + i) % 9];
			lights[i].origin[1] = coordinates[(test / 3 + i) % 9];
			lights[i].origin[2] = test % 2 ? .25f : -.75f;
			lights[i].intensity = intensities[(test + i) % 8];
			lights[i].color[0] = i % 2 ? -.25f : 1;
			lights[i].color[1] = .5f; lights[i].color[2] = -.125f;
		}
		for (int i = 0; i < floats; ++i) initial[i] = ((int)(next_random() % 1000) - 500) * .125f;
		memcpy(reference_blocklights, initial, (size_t)floats * sizeof(float));
		Reference_R_AddDynamicLights(&surface);
		for (int optimized = 0; optimized <= 1; ++optimized)
		{
			optimization.value = optimized; memcpy(s_blocklights, initial, (size_t)floats * sizeof(float));
			R_AddDynamicLights(&surface);
			assert(!memcmp(s_blocklights, reference_blocklights, (size_t)floats * sizeof(float)));
		}
	}
	puts("PASS raw dynamic floats: 256 boundary/off-axis/extreme-finite cases, optimization0/1, exact float bits");
}

int main(void)
{
	static const int dimensions[][2] = {{1,1},{2,3},{5,7},{17,13},{29,29},{33,26},{83,10},{867,1}};
	static const float modulations[] = {0,.5f,1,1.25f,3};
	static const float scales[][3] = {{1,1,1},{.5f,.25f,.75f},{2,1,.5f},{-.25f,.5f,1},{1,0,0},{0,1,0}};
	static const int light_counts[] = {0,1,2,4,8,31};
	static const float fractions[] = {-.75f,-.25f,0,.25f,.75f};
	static const float intensities[] = {0,63.999996f,64,64.000008f,127.5f,200,480};
	unsigned long compared_texels = 0;
	test_dynamic_float_outputs();
	for (int optimized = 0; optimized <= 1; ++optimized)
	for (int test = 0; test < 720; ++test)
	{
		optimization.value = optimized;
		msurface_t surface = {0}; mtexinfo_t texture = {0}; cplane_t plane = {0};
		lightstyle_t styles[MAX_LIGHTSTYLES] = {0}; dlight_t lights[MAX_DLIGHTS] = {0};
		int width = dimensions[test % 8][0], height = dimensions[test % 8][1];
		int texels = width * height, layers = test % 5;
		int stride = width * 4 + (test % 3 == 0 ? 0 : test % 3 == 1 ? 13 : 64);
		size_t prefix = 32 + (size_t)(test % 4), length = prefix + (size_t)stride * height + 32;
		byte *actual = malloc(length), *expected = malloc(length);
		byte *samples = malloc((size_t)texels * 3 * (layers ? layers : 1));
		assert(actual && expected && samples);
		memset(actual, 0xad, length); memset(expected, 0xad, length);
		for (int i = 0; i < texels * 3 * (layers ? layers : 1); ++i) samples[i] = (byte)(next_random() >> 24);
		for (int i = 0; i < MAXLIGHTMAPS; ++i) surface.styles[i] = 255;
		for (int i = 0; i < layers; ++i)
		{
			int style = i == 0 ? 0 : i == 1 ? 1 : i == 2 ? 31 : 32;
			surface.styles[i] = (byte)style;
			for (int c = 0; c < 3; ++c) styles[style].rgb[c] = scales[(test + i) % 6][c];
			styles[style].white = styles[style].rgb[0] + styles[style].rgb[1] + styles[style].rgb[2];
		}
		surface.plane = &plane; surface.texinfo = &texture;
		surface.extents[0] = (short)((width - 1) * 16); surface.extents[1] = (short)((height - 1) * 16);
		surface.texturemins[0] = -48; surface.texturemins[1] = 32;
		surface.samples = test % 17 ? samples : NULL;
		if (test % 3 == 0) { plane.normal[2] = 1; texture.vecs[0][0] = 1; texture.vecs[1][1] = 1; }
		else if (test % 3 == 1) { plane.normal[0] = 1; texture.vecs[0][1] = 1; texture.vecs[1][2] = 1; }
		else { plane.normal[0] = .6f; plane.normal[2] = .8f; texture.vecs[0][0] = .8f; texture.vecs[0][2] = -.6f; texture.vecs[1][1] = 1; }
		plane.dist = test % 2 ? 63.5f : 0;
		texture.vecs[0][3] = fractions[test % 5]; texture.vecs[1][3] = fractions[(test + 2) % 5];
		modulation.value = modulations[(test / 3) % 5];
		pp_drawprofile_active = test % 2;
		r_newrefdef.lightstyles = styles; r_newrefdef.dlights = lights;
		r_newrefdef.num_dlights = light_counts[(test / 5) % 6];
		r_framecount = 100 + test; surface.dlightframe = test % 4 ? r_framecount : 0;
		for (int i = 0; i < r_newrefdef.num_dlights; ++i)
		{
			if ((i + test) % 3) surface.dlightbits |= 1u << i;
			for (int axis = 0; axis < 3; ++axis)
				lights[i].origin[axis] = (int)(next_random() % 1024) - 256 + fractions[(test + i + axis) % 5];
			lights[i].intensity = intensities[(test + i) % 7];
			for (int c = 0; c < 3; ++c) lights[i].color[c] = scales[(test + i + 1) % 6][c];
		}
		gl_state.minlight_set = test % 2;
		for (int i = 0; i < 256; ++i)
		{
			gammatable[i] = test % 3 ? (byte)i : (byte)(i * 37 + 11);
			minlight[i] = test % 4 ? (byte)(48 + i * 207 / 255) : (byte)(255 - i);
		}
		Reference_R_BuildLightMap(&surface, expected + prefix, stride);
		R_BuildLightMap(&surface, actual + prefix, stride);
		/* Check float bits before packing/gamma could hide a numerical change. */
		assert(!memcmp(s_blocklights, reference_blocklights, (size_t)texels * 3 * sizeof(float)));
		if (memcmp(actual, expected, length))
		{
			for (size_t i = 0; i < length; ++i)
				if (actual[i] != expected[i])
				{
					fprintf(stderr, "Lightmap case %d (%dx%d, layers=%d lights=%d) byte %zu: %u != %u\n",
						test, width, height, layers, r_newrefdef.num_dlights, i, actual[i], expected[i]);
					abort();
				}
		}
		compared_texels += (unsigned)texels;
		free(samples); free(expected); free(actual);
	}
	printf("PASS production lightmap float-bit/byte equality: optimization0/1, 1440 cases, %lu texels; styles/modulation, fractional cutoffs, negative/overbright, gamma/minlight, per-view lights, dimensions/unaligned strides and redzones\n", compared_texels);
	return 0;
}
