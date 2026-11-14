/* Execute the production buffer with a stateful fake GL implementation. Compare
 * effective draw inputs, not just call counts, across scoped/legacy dispatch. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "../../src/client/refresh/gl1/gl1_buffer.c"

glconfig_t gl_config;
glstate_t gl_state;
refdef_t r_newrefdef;
pp_refperf_t pp_refperf;
float gldepthmin, gldepthmax;
static cvar_t zero, one = {.value=1}, feature;
cvar_t *r_perf=&zero, *gl_lefthand=&zero, *r_gunfov=&zero;
cvar_t *gl1_overbrightbits=&zero, *r_gl1_world_arrays=&feature;
typedef struct { int enabled,size,type,stride; const void *pointer; GLuint vbo; } attrib_t;
typedef struct {
	attrib_t vertex,st[2],color;
	GLuint ebo;
	int texture[2],mtex,flags,count,matrix;
	GLushort indices[12];
} draw_t;
typedef struct { unsigned enable,disable,bind,vertex,st,select; } calls_t;
static attrib_t vertex,st[2],color;
static GLuint array_buffer,element_buffer;
static int client_tmu,server_tmu,mtex_enabled,draws,matrix;
static draw_t capture[256];
static calls_t calls;
static GLfloat xyz[9],uv[6];
static GLushort elements[3]={1,2,0};
static byte colors[12];

static void APIENTRY bind_buffer(GLenum target,GLuint value)
{
	++calls.bind;
	if(target==GL_ARRAY_BUFFER) array_buffer=value;
	else { assert(target==GL_ELEMENT_ARRAY_BUFFER);element_buffer=value; }
}
void (APIENTRY *qglBindBuffer)(GLenum,GLuint)=bind_buffer;
void (APIENTRY *qglDeleteBuffers)(GLsizei,const GLuint *);
void R_SelectTexture(GLenum target)
{
	assert(target==GL_TEXTURE0 || target==GL_TEXTURE1);
	if(gl_state.currenttarget==target)return;
	++calls.select;
	client_tmu=server_tmu=target-GL_TEXTURE0;
	gl_state.currenttarget=target;gl_state.currenttmu=server_tmu;
}
qboolean R_Bind(int texture)
{
	gl_state.currenttextures[server_tmu]=texture;return true;
}
void R_MBind(GLenum target,int texture) { R_SelectTexture(target);R_Bind(texture); }
void R_EnableMultitexture(qboolean value)
{
	if(mtex_enabled==value)return;
	mtex_enabled=value;R_SelectTexture(GL_TEXTURE1);R_SelectTexture(GL_TEXTURE0);
}
void R_TexEnv(GLenum value) { (void)value; }
void R_SetPerspective(GLdouble value) { (void)value; }
double PP_PerfNow(void) { return 0; }
void PP_DPDraw(void) { }
void PP_DPFlush(void) { }
void PP_DPSetFlush(unsigned value) { (void)value; }
void Com_DPrintf(const char *format, ...) { (void)format;assert(!"Unexpected primitive"); }
void glEnable(GLenum value) { (void)value; }
void glDisable(GLenum value) { (void)value; }
static attrib_t *attribute(GLenum type)
{
	if(type==GL_VERTEX_ARRAY)return &vertex;
	if(type==GL_TEXTURE_COORD_ARRAY)return &st[client_tmu];
	assert(type==GL_COLOR_ARRAY);return &color;
}
void glEnableClientState(GLenum type) { ++calls.enable;attribute(type)->enabled=1; }
void glDisableClientState(GLenum type) { ++calls.disable;attribute(type)->enabled=0; }
static void pointer(attrib_t *a,int size,GLenum type,int stride,const void *p)
{
	a->size=size;a->type=type;a->stride=stride;a->pointer=p;a->vbo=array_buffer;
}
void glVertexPointer(GLint n,GLenum type,GLsizei stride,const GLvoid *p)
{ ++calls.vertex;pointer(&vertex,n,type,stride,p); }
void glTexCoordPointer(GLint n,GLenum type,GLsizei stride,const GLvoid *p)
{ ++calls.st;pointer(&st[client_tmu],n,type,stride,p); }
void glColorPointer(GLint n,GLenum type,GLsizei stride,const GLvoid *p)
{ pointer(&color,n,type,stride,p); }
void glDrawElements(GLenum mode,GLsizei count,GLenum type,const GLvoid *p)
{
	assert(mode==GL_TRIANGLES && type==GL_UNSIGNED_SHORT && count>0 && count<=12);
	assert(vertex.enabled && draws<256);
	draw_t *d=&capture[draws++];
	d->vertex=vertex;d->st[0]=st[0];d->st[1]=st[1];d->color=color;
	/* Disabled arrays are not draw inputs. Their stale pointer values may differ
	 * without changing GL semantics, so exclude those from the comparison. */
	if(!color.enabled)memset(&d->color,0,sizeof(d->color));
	if(!st[0].enabled)memset(&d->st[0],0,sizeof(d->st[0]));
	if(!mtex_enabled)memset(&d->st[1],0,sizeof(d->st[1]));
	d->ebo=element_buffer;d->count=count;d->matrix=matrix;
	d->texture[0]=gl_state.currenttextures[0];d->texture[1]=gl_state.currenttextures[1];
	d->mtex=mtex_enabled;d->flags=gl_buf.flags;
	if(element_buffer) { assert(element_buffer==55 && !p && count==3);p=elements; }
	assert(p);memcpy(d->indices,p,count*sizeof(GLushort));
}
void glShadeModel(GLenum v) { (void)v; }
void glMatrixMode(GLenum v) { (void)v; }
void glCullFace(GLenum v) { (void)v; }
void glPushMatrix(void) { }
void glPopMatrix(void) { }
void glLoadIdentity(void) { }
void glScalef(GLfloat x,GLfloat y,GLfloat z) { (void)x;(void)y;(void)z; }
void glDepthRange(GLclampd a,GLclampd b) { (void)a;(void)b; }
void glColor4f(GLfloat a,GLfloat b,GLfloat c,GLfloat d) { (void)a;(void)b;(void)c;(void)d; }
void glTexEnvi(GLenum a,GLenum b,GLint c) { (void)a;(void)b;(void)c; }

static void static_packet(GLuint vbo,int image,int lm)
{
	glpoly_t p={0};p.static_vbo=vbo;p.static_indices=elements;
	p.static_index_count=p.numverts=3;
	R_UpdateGLBuffer(buf_mtex,image,lm,0,1);assert(R_BufferStaticPoly(&p));
}
static void scratch_packet(buffered_draw_t type,int flags)
{
	R_UpdateGLBuffer(type,82,5,flags,1);R_SetBufferIndices(GL_TRIANGLE_FAN,3);
	for(int i=0;i<3;++i) { GLBUFFER_VERTEX(i,i+1,i+2);GLBUFFER_MULTITEX(0,0,0,0); }
}
static void alias_packet(void)
{
	pp_alias_topology_t topology={0};topology.num_vertices=topology.num_indices=3;
	topology.indices=elements;topology.uv=uv;
	pp_alias_cache_t cache={0};cache.topology=&topology;
	model_t model={0};model.aliascache=&cache;model.alias_ebo=55;
	R_UpdateGLBuffer(buf_alias,90,0,0,1);R_DrawAliasCacheColors(&model,xyz,false,colors);
}
static void boundary(void)
{
	assert(!world_arrays_active && !world_array_scope);
	assert(!vertex.enabled && !st[0].enabled && !color.enabled);
	assert(!array_buffer && !element_buffer && !client_tmu && !server_tmu);
}
static void run(int enabled,draw_t *result,calls_t *counts,int *n)
{
	R_ResetGLBuffer();memset(&gl_buf,0,sizeof(gl_buf));memset(&gl_state,0,sizeof(gl_state));
	memset(&vertex,0,sizeof(vertex));memset(st,0,sizeof(st));memset(&color,0,sizeof(color));
	memset(capture,0,sizeof(capture));memset(&calls,0,sizeof(calls));
	array_buffer=element_buffer=0;client_tmu=server_tmu=mtex_enabled=draws=matrix=0;
	gl_state.currenttarget=GL_TEXTURE0;gl_config.multitexture=true;
	gl1_static_world=&one;feature.value=enabled;pp_world_array_reuses=0;
	R_BeginWorldArrayScope();
	for(int i=0;i<60;++i)static_packet(77,30+i%3,1+i%5);
	R_EndWorldArrayScope();boundary();assert(st[1].enabled);
	unsigned expected_reuses=enabled?59:0;assert(pp_world_array_reuses==expected_reuses);
	/* A new inline transform gets a fresh owner; changed VBOs cannot reuse old pointers. */
	++matrix;R_BeginWorldArrayScope();
	static_packet(77,41,2);static_packet(78,42,3);static_packet(78,43,4);
	R_EndWorldArrayScope();boundary();
	/* Mixed scratch, warp, alpha and alias packets tear down before legacy GL. */
	++matrix;R_BeginWorldArrayScope();static_packet(77,30,1);
	scratch_packet(buf_mtex,0);static_packet(77,31,2);
	scratch_packet(buf_singletex,SURF_DRAWTURB);static_packet(77,32,3);
	scratch_packet(buf_alpha,0);static_packet(77,33,4);alias_packet();
	static_packet(77,34,5);R_EndWorldArrayScope();boundary();
	/* Disabled cvar mid-owner must restore before fallback; reenable starts fresh. */
	R_BeginWorldArrayScope();static_packet(77,30,1);R_ApplyGLBuffer();
	feature.value=0;static_packet(77,31,2);R_ApplyGLBuffer();
	feature.value=enabled;static_packet(77,32,3);R_EndWorldArrayScope();boundary();
	/* Empty flush must not discard active ownership or cached pointers. */
	R_BeginWorldArrayScope();static_packet(77,30,1);R_ApplyGLBuffer();R_ApplyGLBuffer();
	static_packet(77,31,2);R_EndWorldArrayScope();boundary();
	R_BeginWorldArrayScope();R_EndWorldArrayScope();boundary();
	/* Reset and map-free release valid-context arrays before dropping metadata. */
	R_BeginWorldArrayScope();static_packet(77,30,1);R_ApplyGLBuffer();
	static_packet(77,30,1);int before_reset=draws;R_ResetGLBuffer();
	assert(draws==before_reset);boundary(); /* Reset discards the pending packet. */
	R_BeginWorldArrayScope();static_packet(78,31,2);R_ApplyGLBuffer();
	model_t world={0};world_buffer_owner=&world;R_FreeWorldBuffers(&world);boundary();
	/* Classic and static-disabled scratch paths never enter reuse. */
	gl_config.multitexture=false;R_BeginWorldArrayScope();scratch_packet(buf_singletex,0);
	R_EndWorldArrayScope();boundary();gl_config.multitexture=true;
	one.value=0;R_BeginWorldArrayScope();scratch_packet(buf_mtex,0);R_EndWorldArrayScope();boundary();one.value=1;
	*n=draws;*counts=calls;memcpy(result,capture,sizeof(capture));
	if(!enabled)assert(pp_world_array_reuses==0);
}
int main(void)
{
	static draw_t legacy[256],optimized[256];calls_t old_calls,new_calls;int old_n,new_n;
	run(0,legacy,&old_calls,&old_n);run(1,optimized,&new_calls,&new_n);
	assert(old_n==new_n && old_n>70);
	for(int i=0;i<old_n;++i)assert(!memcmp(&legacy[i],&optimized[i],sizeof(draw_t)));
	assert(new_calls.vertex<old_calls.vertex/2 && new_calls.st<old_calls.st/2);
	assert(new_calls.bind<old_calls.bind/2 && new_calls.enable<old_calls.enable/2);
	assert(new_calls.select==old_calls.select); /* First version preserves coupled selection. */
	printf("PASS %d exact ordered draw/state snapshots; vertex pointers %u->%u, ST pointers %u->%u, binds %u->%u\n",
		old_n,old_calls.vertex,new_calls.vertex,old_calls.st,new_calls.st,old_calls.bind,new_calls.bind);
	puts("PASS VBO/transform boundaries, scratch/warp/alpha/alias interruptions, empty/reset/free/classic/disabled/cvar transitions");
	return 0;
}
