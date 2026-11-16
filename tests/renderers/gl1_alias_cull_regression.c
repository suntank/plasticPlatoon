/* Compare the production early-out predicate with the prior corner masks. */
#include <assert.h>
#include <stdio.h>
#include "../../src/client/refresh/gl1/gl1_mesh.c"

cplane_t frustum[4];
static cvar_t enabled={.value=1};
cvar_t *r_gl1_fast_alias_cull=&enabled;
static uint32_t seed=0x13ab4d89;
static float coordinate(void)
{
    seed=seed*1664525u+1013904223u;
    return ((int)(seed>>8)%200001-100000)*.03125f;
}
static qboolean predecessor(vec3_t points[8])
{
    int aggregate=~0;
    for (int p=0;p<8;++p) {
        int mask=0;
        for (int f=0;f<4;++f) {
            float dp=DotProduct(frustum[f].normal,points[p]);
            if ((dp-frustum[f].dist)<0) mask|=1<<f;
        }
        aggregate&=mask;
    }
    return aggregate!=0;
}
int main(void)
{
    vec3_t box[8];
    for (unsigned trial=0;trial<100000;++trial) {
        for (int f=0;f<4;++f) {
            for (int c=0;c<3;++c) frustum[f].normal[c]=coordinate();
            frustum[f].dist=coordinate();
        }
        for (int p=0;p<8;++p)
            for (int c=0;c<3;++c) box[p][c]=coordinate();
        /* Exact plane contacts, infinities and NaNs exercise comparison signs. */
        if (trial%11==0) VectorClear(frustum[0].normal);
        if (trial%13==0) frustum[0].dist=0;
        if (trial%17==0) box[trial%8][trial%3]=NAN;
        if (trial%19==0) frustum[trial%4].dist=INFINITY;
        if (trial%23==0) frustum[trial%4].dist=-INFINITY;
        qboolean expected=predecessor(box);
        enabled.value=0; assert(R_AliasBoxOutsideFrustum(box)==expected);
        enabled.value=1; assert(R_AliasBoxOutsideFrustum(box)==expected);
    }
    puts("PASS 100000 production alias-frustum comparisons against original masks, including plane contacts and nonfinite inputs");
}
