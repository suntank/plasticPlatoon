/* Test the actual production prepared-color cache against independent original
 * per-expanded-vertex arithmetic, with adversarial keys and bounded capacity. */
#include <assert.h>
#include <stdio.h>
#include "../../src/client/refresh/gl1/gl1_mesh.c"
glbuffer_t gl_buf;
glstate_t gl_state;
pp_refperf_t pp_refperf;
cvar_t *r_perf;
static cvar_t enabled = {.value = 1}, shadows;
cvar_t *r_gl1_alias_colors = &enabled, *gl_shadows = &shadows;
unsigned char minlight[256], gammatable[256];

static void reference(byte *out, const pp_alias_topology_t *mesh,
    const dtrivertx_t *verts, float alpha, qboolean color_only)
{
    for (unsigned k = 0; k < mesh->num_vertices; ++k)
    {
        float brightness = color_only ? 1.0f : shadedots[verts[mesh->source[k]].lightnormalindex];
        for (int c = 0; c < 3; ++c)
        {
            int color = brightness * shadelight[c] * 255;
            if (color < 0) color = 0;
            if (color > 255) color = 255;
            out[k*4+c] = gl_state.minlight_set ? minlight[color] : color;
        }
        out[k*4+3] = alpha * 255;
    }
}

int main(void)
{
    dtrivertx_t verts[256], other_verts[256];
    unsigned short *indices = malloc(MAX_VERTICES * sizeof(*indices));
    byte *expected = malloc(MAX_VERTICES * 4u); assert(indices && expected);
    for (unsigned i = 0; i < 256; ++i)
    {
        verts[i].lightnormalindex = i;
        other_verts[i].lightnormalindex = 255-i;
        minlight[i] = 40 + i*215/255;
    }
    for (unsigned i = 0; i < MAX_VERTICES; ++i) indices[i] = i % 256;
    pp_alias_topology_t mesh = {0}, other_mesh = {0};
    mesh.source = indices; mesh.num_vertices = 257; other_mesh = mesh;
    model_t model = {0}, other_model = {0};
    const float alpha[] = {0, .25f, .5f, 1};
    const float lights[][3] = {{.2f,.7f,.9f},{-1,2,.5f},{0,0,0}};
    unsigned comparisons = 0;
    for (unsigned n = 0; n < 4; ++n)
    for (unsigned row = 0; row < 16; ++row)
    for (int minimum = 0; minimum < 2; ++minimum)
    for (int color_only = 0; color_only < 2; ++color_only)
    for (unsigned light = 0; light < 3; ++light)
    for (unsigned count = 0; count < 4; ++count)
    {
        const unsigned sizes[] = {1,255,256,257}; mesh.num_vertices = sizes[count];
        shadedots = r_avertexnormal_dots[row]; VectorCopy(lights[light], shadelight);
        gl_state.minlight_set = minimum; R_ClearAliasColorCache();
        reference(expected,&mesh,verts,alpha[n],color_only);
        uint64_t hits = pp_alias_color_hits, misses = pp_alias_color_misses;
        const byte *a = R_AliasPreparedColors(&model,&mesh,verts,alpha[n],color_only,true);
        assert(a && !memcmp(a,expected,mesh.num_vertices*4u));
        const byte *b = R_AliasPreparedColors(&model,&mesh,verts,alpha[n],color_only,true);
        assert(a == b && pp_alias_color_hits == hits+1 && pp_alias_color_misses == misses+1);
        comparisons++;
    }
    mesh.num_vertices = 257; gl_state.minlight_set = false;
    VectorSet(shadelight,.1f,.2f,.3f); R_ClearAliasColorCache();
    const byte *first = R_AliasPreparedColors(&model,&mesh,verts,1,false,true); assert(first);
    uint64_t misses = pp_alias_color_misses;
    assert(R_AliasPreparedColors(&other_model,&mesh,verts,1,false,true) != first);
    assert(R_AliasPreparedColors(&model,&other_mesh,verts,1,false,true) != first);
    assert(R_AliasPreparedColors(&model,&mesh,other_verts,1,false,true) != first);
    shadedots = r_avertexnormal_dots[7]; assert(R_AliasPreparedColors(&model,&mesh,verts,1,false,true) != first);
    assert(pp_alias_color_misses == misses+4);
    /* Different exact float inputs stay different keys even when their bytes
     * quantize to the same output. All three RGB bits and alpha participate. */
    for (int c=0;c<3;++c)
    {
        R_ClearAliasColorCache(); VectorSet(shadelight,0,0,0);
        R_AliasPreparedColors(&model,&mesh,verts,0,false,true); misses=pp_alias_color_misses;
        shadelight[c] = -0.0f; R_AliasPreparedColors(&model,&mesh,verts,0,false,true);
        assert(pp_alias_color_misses == misses+1);
    }
    misses=pp_alias_color_misses; R_AliasPreparedColors(&model,&mesh,verts,-0.0f,false,true);
    assert(pp_alias_color_misses==misses+1);
    /* Find and exercise a genuine open-addressing collision without assuming
     * anything about this process's model pointer addresses. */
    R_ClearAliasColorCache(); VectorSet(shadelight,.1f,.2f,.3f);
    first=R_AliasPreparedColors(&model,&mesh,verts,1,false,true);
    alias_color_key_t key={0}; unsigned home=0;
    for(unsigned i=0;i<ALIAS_COLOR_KEYS;++i)if(alias_color_entries[i].valid){key=alias_color_entries[i].key;home=R_AliasColorHash(&key);break;}
    float original=shadelight[0], collision=0; qboolean found=false;
    uint32_t original_bits;memcpy(&original_bits,&original,4);
    for(unsigned i=1;i<65536;++i){uint32_t bits=original_bits+i;float f;memcpy(&f,&bits,4);memcpy(&key.light[0],&f,4);if(R_AliasColorHash(&key)==home&&f!=original){collision=f;found=true;break;}}
    assert(found);shadelight[0]=collision;const byte *second=R_AliasPreparedColors(&model,&mesh,verts,1,false,true);
    assert(second && second!=first);reference(expected,&mesh,verts,1,false);assert(!memcmp(second,expected,mesh.num_vertices*4u));
    shadelight[0]=original;assert(R_AliasPreparedColors(&model,&mesh,verts,1,false,true)==first);
    /* Both metadata saturation and byte-arena exhaustion clear safely. */
    R_ClearAliasColorCache();uint64_t epoch=alias_color_epoch;
    for(unsigned i=0;i<=ALIAS_COLOR_KEYS;++i){shadelight[0]=(float)i/1024;assert(R_AliasPreparedColors(&model,&mesh,verts,1,false,true));}
    assert(alias_color_epoch==epoch+1 && alias_color_used==257*4u);
    mesh.num_vertices=MAX_VERTICES;R_ClearAliasColorCache();epoch=alias_color_epoch;
    for(unsigned i=0;i<ALIAS_COLOR_BYTES/(MAX_VERTICES*4u)+1;++i){shadelight[0]=(float)i/1024;assert(R_AliasPreparedColors(&model,&mesh,verts,1,false,true));}
    assert(alias_color_epoch==epoch+1 && alias_color_used==MAX_VERTICES*4u);
    /* Reusing the same addresses after model/minlight generation invalidation
     * cannot return earlier colors. The arena is not memset on clear. */
    mesh.num_vertices=257;R_ClearAliasColorCache();gl_state.minlight_set=true;VectorSet(shadelight,.2f,.3f,.4f);
    first=R_AliasPreparedColors(&model,&mesh,verts,1,false,true);byte before=first[0];
    for(unsigned i=0;i<256;++i)minlight[i]=255-minlight[i];R_ClearAliasColorCache();
    second=R_AliasPreparedColors(&model,&mesh,verts,1,false,true);reference(expected,&mesh,verts,1,false);
    assert(!memcmp(second,expected,mesh.num_vertices*4u)&&second[0]!=before);
    misses=pp_alias_color_misses;enabled.value=0;assert(!R_AliasPreparedColors(&model,&mesh,verts,1,false,true));enabled.value=1;
    shadows.value=1;assert(!R_AliasPreparedColors(&model,&mesh,verts,1,false,true));shadows.value=0;
    assert(!R_AliasPreparedColors(&model,&mesh,verts,1,false,false));
    mesh.num_vertices=MAX_VERTICES+1u;assert(!R_AliasPreparedColors(&model,&mesh,verts,1,false,true));mesh.num_vertices=0;assert(!R_AliasPreparedColors(&model,&mesh,verts,1,false,true));
    mesh.num_vertices=257;assert(!R_AliasPreparedColors(&model,&mesh,verts,NAN,false,true));
    shadelight[0]=INFINITY;assert(!R_AliasPreparedColors(&model,&mesh,verts,1,false,true));assert(pp_alias_color_misses==misses);
    free(expected);free(indices);printf("PASS %u byte-exact cache/reference cases; raw input/identity keys, collisions, metadata/arena capacity, lifecycle/minlight invalidation and disabled/shadows/nonstatic/nonfinite fallbacks\n",comparisons);
    return 0;
}
