/* Exercises the production MD2 loader/cache and visibility/size policies.
 * GPL-2.0-or-later. Run through tests/run_renderer_tests.py.
 */
#include <assert.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include "../src/client/refresh/ref_shared.h"
#include "../src/client/refresh/files/visibility_cache.h"
#include "../src/client/refresh/files/texture_policy.h"

static void *test_hunk;
static size_t test_hunk_size, test_hunk_used;
void *Hunk_Begin(int size)
{
	assert(!test_hunk && size > 0);
	test_hunk_size = (size_t)size + 64;
	test_hunk_used = 0;
	test_hunk = calloc(1, test_hunk_size);
	assert(test_hunk);
	return test_hunk;
}
void *Hunk_Alloc(int size)
{
	assert(size > 0 && test_hunk_used+(size_t)size <= test_hunk_size);
	void *result = (byte *)test_hunk+test_hunk_used;
	test_hunk_used += ((size_t)size+31)&~(size_t)31;
	return result;
}
int LittleLong(int value)
{
	const unsigned char *b = (const unsigned char *)&value;
	return (int)((uint32_t)b[0] | (uint32_t)b[1]<<8 | (uint32_t)b[2]<<16 | (uint32_t)b[3]<<24);
}
short LittleShort(short value)
{
	const unsigned char *b = (const unsigned char *)&value;
	return (short)((unsigned)b[0] | (unsigned)b[1]<<8);
}
float LittleFloat(float value)
{
	int bits;
	memcpy(&bits, &value, sizeof(bits));
	bits = LittleLong(bits);
	memcpy(&value, &bits, sizeof(value));
	return value;
}
void Com_Printf(const char *format, ...)
{
	va_list ap;
	va_start(ap, format);
	vfprintf(stderr, format, ap);
	va_end(ap);
}
static struct image_s *TestImage(const char *name, imagetype_t type)
{
	assert(name && type == it_skin);
	return (struct image_s *)(uintptr_t)1;
}
static void SetUV(int *words, float s, float t, int index)
{
	memcpy(words, &s, sizeof(s)); memcpy(words+1, &t, sizeof(t)); words[2] = index;
}
static void TestTopology(void)
{
	int words[40] = {0};
	words[0] = -4;
	for (int i = 0; i < 4; ++i) SetUV(words+1+i*3, i*.25f, 0, i);
	words[13] = 5;
	for (int i = 0; i < 5; ++i) SetUV(words+14+i*3, i*.125f, 1, i);
	pp_alias_topology_t *mesh = PP_BuildAliasTopology(words, 30, 5);
	const unsigned short expected[] = {0,1,2, 0,2,3, 4,5,6, 5,7,6, 6,7,8};
	assert(mesh && mesh->num_vertices == 9 && mesh->num_indices == 15);
	assert(!memcmp(mesh->indices, expected, sizeof(expected)));
	/* Same position with two UVs remains two render vertices. */
	assert(mesh->source[0] == mesh->source[4] && mesh->uv[1] != mesh->uv[9]);
	PP_FreeAliasTopology(mesh);
	assert(!PP_BuildAliasTopology(words, 29, 5)); /* missing terminator */
	words[3] = 5;
	assert(!PP_BuildAliasTopology(words, 30, 5)); /* out-of-range position */
	words[3] = 0;
	SetUV(words+1, NAN, 0, 0);
	assert(!PP_BuildAliasTopology(words, 30, 5));
	/* Identical command tuples across primitives share vertices and UVs. */
	int duplicates[21] = {0};
	duplicates[0] = duplicates[10] = 3;
	for (int i = 0; i < 3; ++i)
	{
		SetUV(duplicates+1+i*3, i*.25f, 0, i);
		SetUV(duplicates+11+i*3, i*.25f, 0, i);
	}
	mesh = PP_BuildAliasTopology(duplicates, 21, 3);
	assert(mesh && mesh->num_vertices == 3 && mesh->num_indices == 6);
	assert(!memcmp(mesh->indices, mesh->indices+3, 3*sizeof(unsigned short)));
	PP_FreeAliasTopology(mesh);
	words[0] = INT_MIN;
	assert(!PP_BuildAliasTopology(words, 30, 5));
	words[0] = 2;
	assert(!PP_BuildAliasTopology(words, 30, 5));
	/* Largest permitted ushort vertex domain, without index wrapping. */
	size_t count = 1+65535*3+1;
	int *large = calloc(count, sizeof(*large));
	assert(large);
	large[0] = -65535;
	for (int i = 0; i < 65535; ++i) SetUV(large+1+i*3, 0, 0, i);
	mesh = PP_BuildAliasTopology(large, count, 65535);
	assert(mesh && mesh->indices[mesh->num_indices-1] == 65534);
	PP_FreeAliasTopology(mesh);
	large[0] = -65536;
	assert(!PP_BuildAliasTopology(large, count, 65536));
	free(large);
}
static void TestVisibility(void)
{
	pp_visibility_cache_t cache = {0};
	mnode_t nodes[3] = {0};
	mleaf_t leaves[4] = {0};
	/* Camera A's cluster sees root/left and two leaves. */
	nodes[0].visframe = nodes[1].visframe = 1;
	leaves[0].visframe = leaves[1].visframe = 1;
	PP_SaveVisibility(&cache, 2, 3, nodes, 3, leaves, 4, 1);
	/* Camera B overwrites shared stamps for a different area. */
	nodes[0].visframe = nodes[2].visframe = 2;
	leaves[2].visframe = leaves[3].visframe = 2;
	PP_SaveVisibility(&cache, 8, 8, nodes, 3, leaves, 4, 2);
	assert(PP_RestoreVisibility(&cache, 2, 3, 3));
	assert(nodes[0].visframe == 3 && nodes[1].visframe == 3 && nodes[2].visframe != 3);
	assert(leaves[0].visframe == 3 && leaves[1].visframe == 3 && leaves[2].visframe != 3);
	assert(PP_RestoreVisibility(&cache, 8, 8, 4));
	assert(nodes[0].visframe == 4 && nodes[2].visframe == 4 && nodes[1].visframe != 4);
	assert(!PP_RestoreVisibility(&cache, 2, 4, 5)); /* second cluster matters */
	PP_ClearVisibilityCache(&cache); /* map/reconnect pointer invalidation */
	assert(!PP_RestoreVisibility(&cache, 8, 8, 6));
	PP_ClearVisibilityCache(&cache); /* idempotent cleanup */
}
static void TestTexturePolicy(void)
{
	assert(PP_TextureDimension(300, PP_PicmipLevels(1), 4096) == 150);
	assert(PP_TextureDimension(256, PP_PicmipLevels(1), 4096) == 128);
	assert(PP_TextureDimension(1, PP_PicmipLevels(999), 4096) == 1);
	assert(PP_TextureDimension(8192, PP_PicmipLevels(-1), 2048) == 2048);
	assert(PP_PicmipLevels(NAN) == 0 && PP_PicmipLevels(INFINITY) == 0);
}
static void TestModel(const char *path)
{
	FILE *f = fopen(path, "rb");
	assert(f);
	fseek(f, 0, SEEK_END);
	long length = ftell(f);
	rewind(f);
	assert(length >= (long)sizeof(dmdl_t) && length <= INT_MAX);
	void *bytes = malloc(length);
	assert(bytes && fread(bytes, 1, length, f) == (size_t)length);
	fclose(f);
	struct image_s *skins[MAX_MD2SKINS] = {0};
	vec3_t mins, maxs;
	modtype_t type;
	dmdl_t *header = Mod_LoadMD2(path, bytes, length, mins, maxs, skins, TestImage, &type);
	assert(header && type == mod_alias);
	pp_alias_cache_t *cache = Mod_BuildAliasCache(header);
	assert(cache && cache->topology);
	if (header->num_frames == 1)
	{
		assert(cache->static_xyz);
		const daliasframe_t *frame = (const daliasframe_t *)((const byte *)header+header->ofs_frames);
		for (unsigned i = 0; i < cache->topology->num_vertices; ++i)
			for (int j = 0; j < 3; ++j)
				assert(cache->static_xyz[i*3+j] == frame->translate[j]+frame->scale[j]*frame->verts[cache->topology->source[i]].v[j]);
	}
	else assert(!cache->static_xyz); /* animated models never use frame-zero shortcut */
	printf("%s: %d frames, %u render vertices, %u command triangles\n", path,
		header->num_frames, cache->topology->num_vertices, cache->topology->num_indices/3);
	/* Pose reuse must distinguish every interpolation/extrusion input. */
	pp_alias_pose_key_t key = {0}, different = {0};
	float *pose = calloc(header->num_xyz*4, sizeof(float));
	assert(pose);
	pose[0] = 7.0f;
	Mod_SaveAliasPose(cache, &key, pose);
	assert(Mod_FindAliasPose(cache, &key)[0] == 7.0f);
	different.frame = 1; assert(!Mod_FindAliasPose(cache, &different));
	different = key; different.oldframe = 1; assert(!Mod_FindAliasPose(cache, &different));
	different = key; different.shell = 1; assert(!Mod_FindAliasPose(cache, &different));
	for (int axis = 0; axis < 3; ++axis)
	{
		different = key; different.move[axis] = 1; assert(!Mod_FindAliasPose(cache, &different));
		different = key; different.front[axis] = .5f; assert(!Mod_FindAliasPose(cache, &different));
		different = key; different.back[axis] = .5f; assert(!Mod_FindAliasPose(cache, &different));
	}
	Mod_SaveAliasPose(cache, &different, pose);
	assert(Mod_FindAliasPose(cache, &key) && Mod_FindAliasPose(cache, &different));
	free(pose);
	Mod_FreeAliasCache(cache);
	free(test_hunk); test_hunk = NULL;
	free(bytes);
}
int main(int argc, char **argv)
{
	TestTopology(); TestVisibility(); TestTexturePolicy();
	for (int i = 1; i < argc; ++i) TestModel(argv[i]);
	printf("PASS: topology, UV seams, ushort bounds, malformed commands, visibility stamp restoration, texture policy, %d production MD2 loads/caches\n", argc-1);
	return 0;
}
