/* Exercise software sprite geometry and texture gradients without a display. */
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include "../../src/client/refresh/soft/header/local.h"

polydesc_t r_polydesc;
vec5_t r_clip_verts[2][MAXWORKINGVERTS+2];
vec3_t vup = {0, 0, 1}, vright = {0, -1, 0}, vpn = {1, 0, 0};
vec3_t modelorg = {-20, 0, 0}, r_entorigin = {20, 0, 0};
image_t *r_notexture_mip;
static int draws;
void R_ClipAndDrawPoly(float alpha, int turbulent, qboolean textured)
{
    (void)alpha; (void)turbulent; (void)textured;
    draws++;
}
static float length_between(const vec5_t a, const vec5_t b)
{
    float x = a[0]-b[0], y = a[1]-b[1], z = a[2]-b[2];
    return sqrtf(x*x+y*y+z*z);
}
int main(void)
{
    dsprite_t sprite = {0};
    model_t model = {0};
    image_t skin = {0};
    entity_t ent = {0};
    sprite.numframes = 1;
    sprite.frames[0].width = sprite.frames[0].height = 100;
    sprite.frames[0].origin_x = sprite.frames[0].origin_y = 50;
    skin.width = skin.height = 100;
    model.extradata = &sprite;
    model.skins[0] = &skin;
    ent.skinnum = -26; /* about 10% */
    R_DrawSprite(&ent, &model);
    assert(draws == 1);
    assert(fabsf(length_between(r_clip_verts[0][0], r_clip_verts[0][1]) - 100.0f * 26 / 255) < 0.001f);
    assert(fabsf(VectorLength(r_polydesc.vright) - 255.0f / 26) < 0.001f);
    assert(fabsf(VectorLength(r_polydesc.vup) - 255.0f / 26) < 0.001f);
    ent.skinnum = 0;
    R_DrawSprite(&ent, &model);
    assert(fabsf(length_between(r_clip_verts[0][0], r_clip_verts[0][1]) - 100) < 0.001f);
    ent.flags = RF_ORIENTED_SPRITE;
    ent.skinnum = -26;
    ent.angles[1] = 90;
    R_DrawSprite(&ent, &model);
    assert(fabsf(r_polydesc.vpn[2]) > 0.99f);
    assert(fabsf(length_between(r_clip_verts[0][0], r_clip_verts[0][1]) - 100.0f * 26 / 255) < 0.001f);
    puts("software sprites preserve tuned scale, texture gradients and orientation");
    return 0;
}
