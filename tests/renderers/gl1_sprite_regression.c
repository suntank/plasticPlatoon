/* Exercise the actual GL1 sprite vertex generation with a stubbed GL context. */
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#include "../../src/client/refresh/gl1/header/local.h"

static const GLfloat (*vertices)[3];
static GLfloat drawn[4][3];
static GLboolean culling = GL_TRUE;
void R_EnableMultitexture(qboolean enabled) { (void)enabled; }
qboolean R_Bind(int texnum) { (void)texnum; return true; }
void R_TexEnv(GLenum mode) { (void)mode; }
void glVertexPointer(GLint size, GLenum type, GLsizei stride, const GLvoid *p)
{ (void)size; (void)type; (void)stride; vertices = p; }
void glDrawArrays(GLenum mode, GLint first, GLsizei count)
{ (void)mode; (void)first; assert(count == 4); memcpy(drawn, vertices, sizeof(drawn)); }
GLboolean glIsEnabled(GLenum what) { (void)what; return culling; }
void glDisable(GLenum what) { if (what == GL_CULL_FACE) culling = GL_FALSE; }
void glEnable(GLenum what) { if (what == GL_CULL_FACE) culling = GL_TRUE; }
void glColor4f(GLfloat r, GLfloat g, GLfloat b, GLfloat a) { (void)r; (void)g; (void)b; (void)a; }
void glEnableClientState(GLenum array) { (void)array; }
void glDisableClientState(GLenum array) { (void)array; }
void glTexCoordPointer(GLint size, GLenum type, GLsizei stride, const GLvoid *p)
{ (void)size; (void)type; (void)stride; (void)p; }
static float length_between(const GLfloat *a, const GLfloat *b)
{ float x=a[0]-b[0], y=a[1]-b[1], z=a[2]-b[2]; return sqrtf(x*x+y*y+z*z); }
int main(void)
{
    dsprite_t sprite = {0};
    model_t model = {0};
    image_t skin = {0};
    entity_t ent = {0};
    sprite.numframes = 1;
    sprite.frames[0].width = sprite.frames[0].height = 100;
    sprite.frames[0].origin_x = sprite.frames[0].origin_y = 50;
    model.extradata = &sprite;
    model.skins[0] = &skin;
    VectorSet(vup, 0, 0, 1);
    VectorSet(vright, 0, -1, 0);
    ent.skinnum = -26;
    R_DrawSpriteModel(&ent, &model);
    assert(fabsf(length_between(drawn[0], drawn[1]) - 100.0f * 26 / 255) < 0.001f);
    ent.skinnum = 0;
    R_DrawSpriteModel(&ent, &model);
    assert(fabsf(length_between(drawn[0], drawn[1]) - 100) < 0.001f);
    ent.flags = RF_ORIENTED_SPRITE;
    ent.skinnum = -26;
    ent.angles[1] = 90;
    R_DrawSpriteModel(&ent, &model);
    assert(fabsf(drawn[1][1] - drawn[0][1]) > 10.0f);
    assert(fabsf(drawn[1][2] - drawn[0][2]) < 0.001f);
    assert(culling == GL_TRUE);
    culling = GL_FALSE;
    R_DrawSpriteModel(&ent, &model);
    assert(culling == GL_FALSE);
    puts("GL1 sprites preserve tuned scale, orientation and culling state");
    return 0;
}
