/* Execute production GL1 MD2 interpolation/color generation without a GL context.
 * The reference reproduces the former per-vertex formula, independently of the
 * lookup path, and verifies both colors and positions on actual project MD2s. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#ifndef PP_GL1_MESH_SOURCE
#define PP_GL1_MESH_SOURCE "../../src/client/refresh/gl1/gl1_mesh.c"
#endif
#include PP_GL1_MESH_SOURCE

glbuffer_t gl_buf;
glstate_t gl_state;
pp_refperf_t pp_refperf;
cvar_t *r_perf;
static cvar_t shadows;
cvar_t *gl_shadows = &shadows;
unsigned char minlight[256], gammatable[256];
static volatile unsigned checksum;
static const float *submitted_positions;
static qboolean submitted_static;

double PP_PerfNow(void) { return 0; }
void R_SetBufferIndices(GLenum mode, GLuint count)
{ (void)mode; (void)count; assert(!"Unexpected legacy topology fallback"); }
void R_DrawAliasCache(const model_t *model, const float *positions, qboolean static_pose)
{
    submitted_positions = positions;
    submitted_static = static_pose;
    checksum += gl_buf.clr[model->aliascache->topology->num_vertices*4-4];
}

static void verify(const model_t *model, dmdl_t *header, entity_t *entity)
{
    const pp_alias_topology_t *mesh = model->aliascache->topology;
    const daliasframe_t *frame = (const void *)((const byte *)header + header->ofs_frames + entity->frame*header->framesize);
    const daliasframe_t *old = (const void *)((const byte *)header + header->ofs_frames + entity->oldframe*header->framesize);
    float alpha = entity->flags & RF_TRANSLUCENT ? entity->alpha : 1.0f;
    qboolean color_only = entity->flags & (RF_SHELL_RED | RF_SHELL_GREEN | RF_SHELL_BLUE);
    qboolean shell = entity->flags & (RF_SHELL_RED | RF_SHELL_GREEN | RF_SHELL_BLUE | RF_SHELL_DOUBLE | RF_SHELL_HALF_DAM);
    vec3_t delta, vectors[3], move;
    VectorSubtract(entity->oldorigin, entity->origin, delta);
    AngleVectors(entity->angles, vectors[0], vectors[1], vectors[2]);
    move[0] = DotProduct(delta, vectors[0]);
    move[1] = -DotProduct(delta, vectors[1]);
    move[2] = DotProduct(delta, vectors[2]);
    for (unsigned k = 0; k < mesh->num_vertices; ++k)
    {
        int source = mesh->source[k];
        float brightness = color_only ? 1.0f : shadedots[frame->verts[source].lightnormalindex];
        for (int c = 0; c < 3; ++c)
        {
            int color = brightness * shadelight[c] * 255;
            if (color < 0) color = 0;
            if (color > 255) color = 255;
            assert(gl_buf.clr[k*4+c] == (gl_state.minlight_set ? minlight[color] : color));
            float back = entity->backlerp, front = 1.0f-back;
            float expected = back*(move[c]+old->translate[c]) + front*frame->translate[c]
                + old->verts[source].v[c]*(back*old->scale[c])
                + frame->verts[source].v[c]*(front*frame->scale[c]);
            if (shell) expected += r_avertexnormals[frame->verts[source].lightnormalindex][c]*POWERSUIT_SCALE;
            assert(fabsf(submitted_positions[k*3+c]-expected) < .0001f);
        }
        assert(gl_buf.clr[k*4+3] == (byte)(alpha*255));
    }
}

static double seconds(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec*1e-9;
}

int main(int argc, char **argv)
{
    assert(argc >= 2);
    for (int n = 0; n < 256; ++n) minlight[n] = (byte)(48 + n*207/255);
    for (int arg = 1; arg < argc; ++arg)
    {
        FILE *f = fopen(argv[arg], "rb"); assert(f);
        assert(!fseek(f, 0, SEEK_END)); long size = ftell(f); rewind(f);
        dmdl_t *header = malloc(size); assert(header);
        assert(fread(header, 1, size, f) == (size_t)size); fclose(f);
        assert(header->ident == IDALIASHEADER && header->version == ALIAS_VERSION);
        model_t model = {0};
        model.aliascache = Mod_BuildAliasCache(header); assert(model.aliascache);
        const pp_alias_topology_t *mesh = model.aliascache->topology;
        assert(mesh->num_vertices <= MAX_VERTICES);
        entity_t entity = {0};
        entity.frame = header->num_frames > 1 ? 1 : 0;
        const int flags[] = {0, RF_TRANSLUCENT, RF_SHELL_RED, RF_SHELL_GREEN|RF_SHELL_BLUE,
                            RF_SHELL_DOUBLE, RF_SHELL_HALF_DAM|RF_TRANSLUCENT};
        const float fractions[] = {0, .33f, 1};
        const float lights[][3] = {{.2f,.6f,.9f}, {-1, 2, .5f}, {0,0,0}};
        for (unsigned flag = 0; flag < sizeof(flags)/sizeof(*flags); ++flag)
        for (unsigned lerp = 0; lerp < 3; ++lerp)
        for (unsigned light = 0; light < 3; ++light)
        for (int minimum = 0; minimum < 2; ++minimum)
        {
            entity.flags = flags[flag];
            entity.backlerp = fractions[lerp];
            entity.alpha = fractions[(lerp+1)%3];
            entity.oldorigin[0] = lerp == 1 ? 1.5f : 0;
            entity.angles[YAW] = 37;
            VectorCopy(lights[light], shadelight);
            shadedots = r_avertexnormal_dots[light];
            gl_state.minlight_set = minimum;
            R_DrawAliasFrameLerp(&entity, &model, header, entity.backlerp);
            verify(&model, header, &entity);
        }
        /* Exercise the threshold and all 256 byte lighting indices independently
         * of the normals present in the asset. Shell extrusion is disabled here. */
        daliasframe_t *frame = (void *)((byte *)header + header->ofs_frames + entity.frame*header->framesize);
        entity.flags = 0;
        unsigned original_vertices = model.aliascache->topology->num_vertices;
        for (unsigned n = 0; n < 256; ++n)
        {
            for (int v = 0; v < header->num_xyz; ++v) frame->verts[v].lightnormalindex = n;
            unsigned counts[] = {1, 255, 256, original_vertices};
            for (unsigned c = 0; c < 4; ++c)
            {
                if (counts[c] > original_vertices) continue;
                model.aliascache->topology->num_vertices = counts[c];
                R_DrawAliasFrameLerp(&entity, &model, header, entity.backlerp);
                verify(&model, header, &entity);
            }
        }
        model.aliascache->topology->num_vertices = original_vertices;
        entity.flags = 0;
        VectorSet(shadelight, .4f, .7f, .9f);
        gl_state.minlight_set = false;
        const int iterations = 20000;
        double started = seconds();
        for (int i = 0; i < iterations; ++i)
            R_DrawAliasFrameLerp(&entity, &model, header, entity.backlerp);
        printf("%s: %u expanded vertices, %.3f us/draw (%u)\n", argv[arg], mesh->num_vertices,
               (seconds()-started)*1e6/iterations, checksum);
        Mod_FreeAliasCache(model.aliascache);
        free(header);
    }
    puts("GL1 alias colors and positions match the original formula across shells, alpha, interpolation and minimum-light cases");
}
