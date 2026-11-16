/* Actual production palette cache versus the prior per-normal arithmetic. */
#include <assert.h>
#include <stdio.h>
#include "../../src/client/refresh/gl1/gl1_mesh.c"

glbuffer_t gl_buf;
glstate_t gl_state;
pp_refperf_t pp_refperf;
cvar_t *r_perf;
static cvar_t enabled = {.value=1};
cvar_t *r_gl1_normal_colors = &enabled;
unsigned char minlight[256], gammatable[256];

static const byte *palette_colors(float alpha, qboolean shell)
{
    alias_normal_entry_t *p=R_AliasNormalPalette(alpha,shell);
    if (!p) return NULL;
    for (unsigned n=0;n<256;++n) R_AliasNormalColor(p,n,alpha,shell);
    return &p->colors[0][0];
}

static void reference(byte result[256][4], float alpha, qboolean color_only)
{
    for (unsigned n=0;n<256;++n) {
        float brightness=color_only?1.0f:shadedots[n];
        for (int c=0;c<3;++c) {
            int v=brightness*shadelight[c]*255;
            v=v<0?0:v>255?255:v;
            result[n][c]=gl_state.minlight_set?minlight[v]:v;
        }
        result[n][3]=alpha*255;
    }
}

int main(void)
{
    byte expected[256][4];
    const float lights[][3]={{0,0,0},{.2f,.7f,.9f},{-1,2,.5f},{.999f,.001f,1.5f}};
    const float alphas[]={0,.25f,.5f,1};
    unsigned cases=0;
    for (unsigned i=0;i<256;++i) minlight[i]=32+i*223/255;
    for (unsigned row=0;row<16;++row)
    for (unsigned light=0;light<4;++light)
    for (unsigned a=0;a<4;++a)
    for (int minimum=0;minimum<2;++minimum)
    for (int shell=0;shell<2;++shell) {
        shadedots=r_avertexnormal_dots[row]; VectorCopy(lights[light],shadelight);
        gl_state.minlight_set=minimum; R_ClearAliasColorCache();
        reference(expected,alphas[a],shell);
        const byte *first=palette_colors(alphas[a],shell);
        assert(first && !memcmp(first,expected,sizeof(expected)));
        uint64_t hits=pp_alias_normal_hits;
        assert(palette_colors(alphas[a],shell)==first && pp_alias_normal_hits==hits+1);
        ++cases;
    }
    /* Every exact input bit remains part of the key, including signed zero. */
    shadedots=r_avertexnormal_dots[0]; gl_state.minlight_set=0;
    for (int c=0;c<3;++c) {
        VectorClear(shadelight); R_ClearAliasColorCache();
        palette_colors(1,0); uint64_t misses=pp_alias_normal_misses;
        shadelight[c]=-0.0f; palette_colors(1,0);
        assert(pp_alias_normal_misses==misses+1);
    }
    /* Collision/eviction must never reuse a different palette. */
    for (unsigned i=0;i<4096;++i) {
        VectorSet(shadelight,(float)i/2048,.3f,.4f);
        reference(expected,.5f,0);
        assert(!memcmp(palette_colors(.5f,0),expected,sizeof(expected)));
    }
    gl_state.minlight_set=1;
    palette_colors(1,0);
    for (unsigned i=0;i<256;++i) minlight[i]=255-minlight[i];
    R_ClearAliasColorCache(); reference(expected,1,0);
    assert(!memcmp(palette_colors(1,0),expected,sizeof(expected)));
    /* Small pickups only evaluate normals actually present in their mesh.
     * Expanded-color arena eviction must not discard this independent palette. */
    R_ClearAliasColorCache(); VectorSet(shadelight,.2f,.3f,.4f);
    alias_normal_entry_t *p=R_AliasNormalPalette(.5f,0);
    uint64_t evaluations=pp_alias_normal_evaluations;
    R_AliasNormalColor(p,7,.5f,0); R_AliasNormalColor(p,7,.5f,0);
    assert(pp_alias_normal_evaluations==evaluations+1);
    R_ResetAliasPreparedColors();
    assert(R_AliasNormalPalette(.5f,0)==p && p->ready[7]);
    R_AliasNormalColor(p,7,.5f,0); assert(pp_alias_normal_evaluations==evaluations+1);
    enabled.value=0; assert(!palette_colors(1,0)); enabled.value=1;
    assert(!palette_colors(NAN,0)); shadelight[0]=INFINITY;
    assert(!palette_colors(1,0));
    printf("PASS %u exact 256-color palettes; animated frame-independent reuse, input keys, collisions, minlight invalidation and fallback\n",cases);
}
