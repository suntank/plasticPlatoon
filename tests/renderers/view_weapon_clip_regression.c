/* Exercise production GL projections and software alias clipping without a GPU. */
#include <assert.h>
#include <limits.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#if defined(TEST_GL1)
#include "../../src/client/refresh/gl1/gl1_main.c"
refdef_t r_newrefdef;
static double projection[6];
void glFrustum(GLdouble left, GLdouble right, GLdouble bottom, GLdouble top,
    GLdouble near_clip, GLdouble far_clip)
{
    projection[0]=2*near_clip/(right-left);
    projection[1]=2*near_clip/(top-bottom);
    projection[2]=(right+left)/(right-left);
    projection[3]=(top+bottom)/(top-bottom);
    projection[4]=near_clip;
    projection[5]=far_clip;
}
static void TestProjection(void)
{
    cvar_t near_value={.value=4}, zero={0}, convergence={.value=1};
    gl_znear=&near_value; r_farsee=&zero; gl1_waterwarp=&zero;
    gl1_stereo_convergence=&convergence;
    r_newrefdef.width=1280; r_newrefdef.height=720;
    for (int near_index=0; near_index<3; ++near_index) {
        near_value.value=near_index==0 ? 4.f : near_index==1 ? 12.f : .01f;
        for (int stereo=0; stereo<2; ++stereo) {
            double world[6], weapon[6];
            gl_state.camera_separation=stereo ? .25f : 0.f;
            R_SetPerspective(75,false); memcpy(world,projection,sizeof(world));
            R_SetPerspective(75,true); memcpy(weapon,projection,sizeof(weapon));
            assert(fabs(world[4]-PP_RenderNearClip(near_value.value,0))<1e-8);
            assert(fabs(weapon[4]-PP_WEAPON_NEAR_CLIP)<1e-8);
            for (int row=0; row<4; ++row) assert(fabs(world[row]-weapon[row])<1e-9);
            assert(world[5]==weapon[5]);
            R_SetPerspective(75,false);
            for (int row=0; row<6; ++row) assert(world[row]==projection[row]);
        }
    }
    near_value.value=4;
    R_SetPerspective(75,true);
    for (double depth=.15; depth<3.9; depth+=.15) {
        assert(depth>=projection[4]); /* Tube/recoil faces survive weapon clipping. */
        assert(depth<PP_RenderNearClip(near_value.value,0));
    }
    assert(near_value.value==4.f);
    puts("GL1 weapon near plane preserves configured world depth and XY/stereo projection");
}
#elif defined(TEST_GL3)
#include "../../src/client/refresh/gl3/gl3_main.c"
refdef_t r_newrefdef;
static void TestProjection(void)
{
    cvar_t near_value={.value=4}, zero={0};
    gl_znear=&near_value; r_farsee=&zero;
    r_newrefdef.width=1280; r_newrefdef.height=720;
    for (int near_index=0; near_index<3; ++near_index) {
        near_value.value=near_index==0 ? 4.f : near_index==1 ? 12.f : .01f;
        hmm_mat4 world=GL3_SetPerspective(75,false), weapon=GL3_SetPerspective(75,true);
        for (int column=0; column<4; ++column)
            for (int row=0; row<2; ++row)
                assert(world.Elements[column][row]==weapon.Elements[column][row]);
        for (double depth=.15; depth<3.9; depth+=.15) {
            double weapon_z=weapon.Elements[2][2]*-depth+weapon.Elements[3][2];
            assert(weapon_z>=-depth && weapon_z<=depth);
            if (near_value.value>=4.f) {
                double world_z=world.Elements[2][2]*-depth+world.Elements[3][2];
                assert(world_z < -depth);
            }
        }
        hmm_mat4 restored=GL3_SetPerspective(75,false);
        assert(!memcmp(&world,&restored,sizeof(world)));
    }
    assert(near_value.value==.01f);
    puts("GL3 weapon near plane retains close tube/recoil faces with unchanged world/XY projection");
}
#else
#include "../../src/client/refresh/soft/sw_alias.c"
#include "../../src/client/refresh/soft/sw_aclip.c"
oldrefdef_t r_refdef;
clipplane_t view_clipplanes[4];
float aliasxscale=1, aliasyscale=1, aliasxcenter=32, aliasycenter=32;
static int triangles;
void R_DrawTriangle(const entity_t *entity, const finalvert_t *a,
    const finalvert_t *b, const finalvert_t *c)
{
    const finalvert_t *vertices[]={a,b,c};
    ++triangles;
    for (int i=0; i<3; ++i) {
        assert(vertices[i]->xyz[2]>=PP_RenderNearClip(ALIAS_Z_CLIP_PLANE,entity->flags & RF_WEAPONMODEL));
        assert(vertices[i]->cv.zi>0 && vertices[i]->cv.zi<INT_MAX);
    }
}
static finalvert_t Vertex(entity_t *entity, float x, float y, float z)
{
    finalvert_t vertex={0};
    vertex.xyz[0]=x; vertex.xyz[1]=y; vertex.xyz[2]=z;
    if (z<PP_RenderNearClip(ALIAS_Z_CLIP_PLANE,entity->flags & RF_WEAPONMODEL))
        vertex.flags=ALIAS_Z_CLIP;
    else R_AliasProjectAndClipTestFinalVert(entity,&vertex);
    return vertex;
}
static void TestProjection(void)
{
    entity_t weapon={.flags=RF_WEAPONMODEL|RF_DEPTHHACK}, world={0};
    entity_t depthhack={.flags=RF_DEPTHHACK};
    r_refdef.aliasvrect.width=r_refdef.aliasvrect.height=64;
    r_refdef.aliasvrectright=r_refdef.aliasvrectbottom=63;
    s_ziscale=(float)0x8000*(float)SHIFT16XYZ_MULT*3.f;
    for (int axis=0; axis<3; ++axis) aliastransform[axis][axis]=1.f;
    daliasframe_t frame={.translate={0,0,.2f},.scale={.001f,.001f,.001f}};
    assert(R_AliasCheckFrameBBox(&weapon,&frame,aliastransform)==BBOX_TRIVIAL_ACCEPT);
    assert(R_AliasCheckFrameBBox(&world,&frame,aliastransform)==BBOX_TRIVIAL_REJECT);
    assert(R_AliasCheckFrameBBox(&depthhack,&frame,aliastransform)==BBOX_TRIVIAL_REJECT);
    dtrivertx_t sample={.v={0,0,1}};
    finalvert_t transformed={0};
    r_lerp_frontv[2]=.2f;
    R_AliasTransformFinalVerts(&weapon,1,&transformed,&sample,&sample);
    assert(!(transformed.flags & ALIAS_Z_CLIP));
    R_AliasTransformFinalVerts(&world,1,&transformed,&sample,&sample);
    assert(transformed.flags & ALIAS_Z_CLIP);
    R_AliasTransformFinalVerts(&depthhack,1,&transformed,&sample,&sample);
    assert(transformed.flags & ALIAS_Z_CLIP);
    finalvert_t a=Vertex(&weapon,-.02f,0,.05f), b=Vertex(&weapon,.02f,.02f,.2f),
        c=Vertex(&weapon,.02f,-.02f,2.f);
    R_AliasClipTriangle(&weapon,&a,&b,&c);
    assert(triangles==2); /* Crossing the .1 plane retains a clipped quad. */
    triangles=0;
    a=Vertex(&world,-.02f,0,.05f); b=Vertex(&world,.02f,.02f,.2f); c=Vertex(&world,.02f,-.02f,2.f);
    R_AliasClipTriangle(&world,&a,&b,&c);
    assert(triangles==0); /* Same face is wholly behind the world near plane. */
    int previous=INT_MAX;
    for (int i=0; i<1000; ++i) {
        float depth=.1f+i*.1f;
        finalvert_t vertex=Vertex(&weapon,.5f,.25f,depth);
        assert(vertex.cv.zi>0 && vertex.cv.zi<previous);
        previous=vertex.cv.zi;
        assert(vertex.cv.u==(int)(.5f/depth+aliasxcenter));
    }
    /* Screen-space interpolation must preserve the true reciprocal depth
     * ordering across a long tube face; 1/(z+bias) reverses this example. */
    float edge=(PP_AliasDepthKey(1/.2f,s_ziscale,1)+PP_AliasDepthKey(1/20.f,s_ziscale,1))*.5f;
    float expected=PP_AliasDepthKey((1/.2f+1/20.f)*.5f,s_ziscale,1);
    assert(fabsf(edge-expected)<128.f);
    assert(edge>PP_AliasDepthKey(1/2.f,s_ziscale,1));
    for (int i=4; i<100; ++i)
        assert(PP_AliasDepthKey(1.f/i,s_ziscale,0)==(1.f/i)*s_ziscale);
    puts("Software weapon clipping retains close faces with bounded, correctly ordered depth and true XY projection");
}
#endif

int main(void)
{
    TestProjection();
    return 0;
}
