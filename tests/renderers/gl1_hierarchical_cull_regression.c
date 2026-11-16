/* Compare the production recursive traversal with its legacy switch, including
 * compiler-rounded child bounds, PVS/areas, map reloads and allocation failure. */
#include "../../src/client/refresh/gl1/header/local.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>

static unsigned plane_tests;
static int counted_box(const vec3_t mins, const vec3_t maxs, const cplane_t *p)
{
	++plane_tests;
	return BOX_ON_PLANE_SIDE(mins,maxs,p);
}
#undef BOX_ON_PLANE_SIDE
#define BOX_ON_PLANE_SIDE(a,b,p) counted_box((a),(b),(p))
#define main unused_inline_main
#include "gl1_inline_batch_regression.c"
#undef main
#include "../../src/client/refresh/files/surf.c"

cplane_t frustum[4];
int r_visframecount, registration_sequence;
static cvar_t culling = {.value=1}, hierarchical = {.value=1};
cvar_t *r_cull = &culling;
static unsigned sky_count;
static msurface_t *sky_capture[8192];
void R_AddSkySurface(msurface_t *s) { assert(sky_count<8192);sky_capture[sky_count++]=s; }
static cvar_t *cull_cvar(const char *name,const char *value,int flags)
{
	if (!strcmp(name,"r_gl1_hierarchical_cull")) return &hierarchical;
	return test_cvar(name,value,flags);
}

typedef struct {
	mnode_t *nodes;
	mleaf_t *leaves;
	cplane_t *planes;
	msurface_t *marks;
	msurface_t **mark_pointers;
	int node_count, leaf_count;
} tree_t;

static void activate(tree_t *t)
{
	R_ClearWorldCullData(world_cull_owner);
	world.nodes=t->nodes;world.numnodes=t->node_count;
	world.leafs=t->leaves;world.numleafs=t->leaf_count;
	world.surfaces=t->marks;world.numsurfaces=t->leaf_count;
	r_worldmodel=&world;ri.Cvar_Get=cull_cvar;
	++registration_sequence;r_visframecount=8;r_framecount=16;
	culling.value=hierarchical.value=1;
	fail_allocation=-1;allocation_number=0;
	r_newrefdef.areabits=NULL;
	for(int i=0;i<3;++i){textures[i].image=images+i;images[i].texturechain=NULL;}
	textures[0].flags=0;textures[1].flags=SURF_SKY;textures[2].flags=SURF_TRANS33;
	gl_config.multitexture=false;
	for(int i=0;i<t->node_count;++i){t->nodes[i].visframe=r_visframecount;t->nodes[i].firstsurface=i;t->nodes[i].numsurfaces=1;}
	for(int i=0;i<t->leaf_count;++i) {
		t->leaves[i].visframe=r_visframecount;
		t->leaves[i].firstmarksurface=t->mark_pointers+i;
		t->leaves[i].nummarksurfaces=1;t->mark_pointers[i]=t->marks+i;
		t->marks[i].texinfo=textures+i%3;t->marks[i].flags=i&1?SURF_PLANEBACK:0;
	}
}
static unsigned capture_chains(msurface_t **out,unsigned max)
{
	unsigned n=0;
	for(int image=0;image<4;++image){
		for(msurface_t *s=image<3?images[image].texturechain:r_alpha_surfaces;s;s=s->texturechain){assert(n<max);out[n++]=s;}
		assert(n<max);out[n++]=NULL;
	}
	for(unsigned i=0;i<sky_count;++i){assert(n<max);out[n++]=sky_capture[i];}
	return n;
}
static void clear_chains(void)
{
	for(int i=0;i<3;++i)images[i].texturechain=NULL;
	r_alpha_surfaces=NULL;sky_count=0;
}
static void compare(tree_t *t)
{
	byte *legacy=calloc((size_t)t->leaf_count,1);assert(legacy);
	unsigned max=(unsigned)t->leaf_count*2+8;
	msurface_t **old_chain=malloc(max*sizeof(*old_chain)),**new_chain=malloc(max*sizeof(*new_chain));assert(old_chain&&new_chain);
	clear_chains();
	for(int i=0;i<t->leaf_count;++i)t->marks[i].visframe=-1;
	hierarchical.value=0;
	R_RecursiveWorldNode(&entity,t->nodes,R_WorldClipFlags());
	for(int i=0;i<t->leaf_count;++i)legacy[i]=t->marks[i].visframe==r_framecount;
	unsigned old_count=capture_chains(old_chain,max);clear_chains();
	for(int i=0;i<t->leaf_count;++i)t->marks[i].visframe=-1;
	hierarchical.value=1;
	R_RecursiveWorldNode(&entity,t->nodes,R_WorldClipFlags());
	for(int i=0;i<t->leaf_count;++i)assert(legacy[i]==(t->marks[i].visframe==r_framecount));
	unsigned new_count=capture_chains(new_chain,max);
	assert(old_count==new_count&&!memcmp(old_chain,new_chain,old_count*sizeof(*old_chain)));
	clear_chains();free(old_chain);free(new_chain);free(legacy);
}
static tree_t allocate_tree(int nodes,int leaves)
{
	tree_t t={0};t.node_count=nodes;t.leaf_count=leaves;
	t.nodes=calloc((size_t)nodes,sizeof(*t.nodes));t.planes=calloc((size_t)nodes,sizeof(*t.planes));
	t.leaves=calloc((size_t)leaves,sizeof(*t.leaves));t.marks=calloc((size_t)leaves,sizeof(*t.marks));
	t.mark_pointers=calloc((size_t)leaves,sizeof(*t.mark_pointers));
	assert(t.nodes&&t.planes&&t.leaves&&t.marks&&t.mark_pointers);return t;
}
static void destroy_tree(tree_t *t)
{
	R_ClearWorldCullData(world_cull_owner);
	free(t->nodes);free(t->planes);free(t->leaves);free(t->marks);free(t->mark_pointers);
	memset(t,0,sizeof(*t));
}
static void frusta(unsigned number)
{
	for(unsigned p=0;p<4;++p) {
		cplane_t *f=frustum+p;memset(f,0,sizeof(*f));f->type=PLANE_ANYZ;
		for(unsigned a=0;a<3;++a) {
			f->normal[a]=((number>>(a+p))&1 ? -1.f:1.f)*(a+1)*.17f;
			if(f->normal[a]<0)f->signbits|=1u<<a;
		}
		f->dist=((int)((number*109+p*97)%1200)-600)*2.f;
	}
	modelorg[0]=(number%17)*37.f-300;modelorg[1]=(number%23)*19.f-200;modelorg[2]=(number%31)*13.f-100;
}
static void fill_tree(tree_t *t,int node,int depth,const float bounds[6],int *next_leaf)
{
	mnode_t *n=t->nodes+node;n->contents=CONTENTS_NODE;n->plane=t->planes+node;
	memcpy(n->minmaxs,bounds,6*sizeof(float));int axis=depth%3;
	n->plane->type=axis;n->plane->normal[axis]=1;
	n->plane->dist=(bounds[axis]+bounds[axis+3])*.5f;
	for(int side=0;side<2;++side) {
		float child[6];memcpy(child,bounds,sizeof(child));
		child[axis+(side?3:0)]=n->plane->dist;
		if(depth<8) {
			int index=2*node+1+side;n->children[side]=t->nodes+index;
			fill_tree(t,index,depth+1,child,next_leaf);
		} else {
			mleaf_t *l=t->leaves+(*next_leaf)++;l->contents=0;
			memcpy(l->minmaxs,child,sizeof(child));n->children[side]=(mnode_t *)l;
		}
	}
}
static void synthetic(void)
{
	tree_t t=allocate_tree(511,512);int next=0;float bounds[6]={-1024,-1024,-1024,1024,1024,1024};
	fill_tree(&t,0,0,bounds,&next);assert(next==512);activate(&t);
	for(unsigned i=0;i<256;++i) { frusta(i);compare(&t); }
	/* A fully inside subtree needs only four plane tests for the entire tree. */
	for(int p=0;p<4;++p) { memset(frustum+p,0,sizeof(*frustum));frustum[p].type=PLANE_X;frustum[p].normal[0]=1;frustum[p].dist=-2048; }
	hierarchical.value=0;plane_tests=0;R_RecursiveWorldNode(&entity,t.nodes,R_WorldClipFlags());unsigned before=plane_tests;
	hierarchical.value=1;plane_tests=0;R_RecursiveWorldNode(&entity,t.nodes,R_WorldClipFlags());assert(plane_tests==4&&before==4*1023);
	/* Invisible PVS nodes and closed areas remain invisible. */
	t.nodes[1].visframe=0;byte areas[1]={1};r_newrefdef.areabits=areas;
	for(int i=0;i<t.leaf_count;++i)t.leaves[i].area=i&1;
	compare(&t);r_newrefdef.areabits=NULL;t.nodes[1].visframe=r_visframecount;
	/* Disabling culling bypasses even cached unsafe child edges. */
	t.nodes[1].minmaxs[0]=-3000;++registration_sequence;culling.value=0;
	assert(R_WorldClipFlags()==WORLD_CLIP_DISABLED);compare(&t);culling.value=1;
	/* Registration invalidation rebuilds metadata even when pointers/counts match. */
	unsigned flags=R_WorldClipFlags();assert(flags==WORLD_CLIP_ALL&&!(world_cull_edges[0]&1));
	t.nodes[1].minmaxs[0]=0;++registration_sequence;R_WorldClipFlags();assert(world_cull_edges[0]&1);
	/* Allocation failure retains the old culler and never retries each camera. */
	R_ClearWorldCullData(&world);fail_allocation=0;allocation_number=0;
	assert(R_WorldClipFlags()==WORLD_CLIP_LEGACY&&allocation_number==1);
	assert(R_WorldClipFlags()==WORLD_CLIP_LEGACY&&allocation_number==1);compare(&t);
	fail_allocation=-1;R_FreeWorldSurfaceBatches(&world);assert(!world_cull_owner&&!world_cull_edges);
	destroy_tree(&t);
	/* A non-contained leaf wholly outside a plane must not inherit its parent's
	 * fully-inside decision. This detects the real BSP compiler-rounding hazard. */
	t=allocate_tree(1,2);t.nodes[0].contents=CONTENTS_NODE;t.nodes[0].plane=t.planes;
	t.planes[0].type=PLANE_X;t.planes[0].normal[0]=1;
	for(int a=0;a<3;++a){t.nodes[0].minmaxs[a]=0;t.nodes[0].minmaxs[a+3]=1;}
	for(int i=0;i<2;++i){memcpy(t.leaves[i].minmaxs,t.nodes[0].minmaxs,6*sizeof(float));t.nodes[0].children[i]=(mnode_t *)(t.leaves+i);}
	t.leaves[0].minmaxs[0]=-2;t.leaves[0].minmaxs[3]=-1;activate(&t);
	for(int p=0;p<4;++p){memset(frustum+p,0,sizeof(*frustum));frustum[p].type=PLANE_X;frustum[p].normal[0]=1;frustum[p].dist=0;}
	compare(&t);assert(t.marks[0].visframe!=r_framecount&&t.marks[1].visframe==r_framecount);
	/* A malformed parent or child bound must never authorize inherited plane
	 * skips. Keep the frustum axial in X so these Y-only defects exercise the
	 * metadata guard independently of floating-point NaN plane arithmetic. */
	for(int bad_parent=0;bad_parent<2;++bad_parent)for(int inverted=0;inverted<2;++inverted) {
		for(int a=0;a<3;++a){t.nodes[0].minmaxs[a]=0;t.nodes[0].minmaxs[a+3]=1;}
		for(int i=0;i<2;++i)memcpy(t.leaves[i].minmaxs,t.nodes[0].minmaxs,6*sizeof(float));
		float *bad=bad_parent?t.nodes[0].minmaxs:t.leaves[0].minmaxs;
		bad[1]=inverted?2.f:NAN;
		++registration_sequence;
		assert(R_WorldClipFlags()==WORLD_CLIP_ALL);
		assert(!(world_cull_edges[0]&1));
		assert((world_cull_edges[0]&2)==(bad_parent?0:2));
		compare(&t);
	}
	destroy_tree(&t);
}

/* Read only the real BSP node/leaf/plane data needed by production traversal.
 * Each nonsolid leaf marks its own surface, witnessing the complete accepted
 * leaf set; runtime PVS/area filtering and source traversal still execute. */
static uint16_t u16(const byte *p){return (uint16_t)(p[0]|p[1]<<8);}
static int16_t i16(const byte *p){return (int16_t)u16(p);}
static int32_t i32(const byte *p){return (int32_t)((uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24);}
static float f32(const byte *p){uint32_t u=(uint32_t)i32(p);float f;memcpy(&f,&u,4);return f;}
static void real_bsp(const char *path)
{
	FILE *f=fopen(path,"rb");assert(f);assert(!fseek(f,0,SEEK_END));long size=ftell(f);rewind(f);
	byte *raw=malloc((size_t)size);assert(raw&&fread(raw,1,(size_t)size,f)==(size_t)size);fclose(f);
	assert(size>=160&&!memcmp(raw,"IBSP",4)&&i32(raw+4)==38);
	int offsets[19],lengths[19];for(int i=0;i<19;++i){offsets[i]=i32(raw+8+8*i);lengths[i]=i32(raw+12+8*i);assert(offsets[i]>=0&&lengths[i]>=0&&(long)offsets[i]+lengths[i]<=size);}
	assert(!(lengths[4]%28)&&!(lengths[8]%28)&&!(lengths[1]%20));
	tree_t t=allocate_tree(lengths[4]/28,lengths[8]/28);int planes=lengths[1]/20;
	free(t.planes);t.planes=calloc((size_t)planes,sizeof(*t.planes));assert(t.planes);
	for(int i=0;i<planes;++i){const byte *p=raw+offsets[1]+20*i;for(int a=0;a<3;++a){t.planes[i].normal[a]=f32(p+4*a);if(t.planes[i].normal[a]<0)t.planes[i].signbits|=1u<<a;}t.planes[i].dist=f32(p+12);t.planes[i].type=i32(p+16);}
	for(int i=0;i<t.leaf_count;++i){const byte *p=raw+offsets[8]+28*i;t.leaves[i].contents=i32(p);t.leaves[i].cluster=i16(p+4);t.leaves[i].area=i16(p+6);for(int a=0;a<6;++a)t.leaves[i].minmaxs[a]=i16(p+8+2*a);}
	for(int i=0;i<t.node_count;++i){const byte *p=raw+offsets[4]+28*i;int plane=i32(p);assert(plane>=0&&plane<planes);mnode_t *n=t.nodes+i;n->contents=CONTENTS_NODE;n->plane=t.planes+plane;for(int a=0;a<6;++a)n->minmaxs[a]=i16(p+12+2*a);for(int c=0;c<2;++c){int index=i32(p+4+4*c);assert(index<t.node_count&&-1-index<t.leaf_count);n->children[c]=index>=0?t.nodes+index:(mnode_t *)(t.leaves-1-index);}}
	activate(&t);unsigned unsafe=0;R_WorldClipFlags();
	for(int i=0;i<t.node_count;++i)for(int s=0;s<2;++s)if(!(world_cull_edges[i]&(1u<<s)))++unsafe;
	for(unsigned i=0;i<256;++i){frusta(i);compare(&t);}
	for(unsigned i=0;i<128;++i) {
		vec3_t angles={(int)(i*29%121)-60,(int)(i*137%360),0},forward,right,up;
		for(int a=0;a<3;++a)modelorg[a]=t.nodes[0].minmaxs[a]+
			(t.nodes[0].minmaxs[a+3]-t.nodes[0].minmaxs[a])*(float)((i*31+a*19)%101)/100.f;
		AngleVectors(angles,forward,right,up);
		R_SetFrustum(up,forward,right,modelorg,80,80,frustum);compare(&t);
	}
	printf("PASS real BSP %s: %d nodes, %u unsafe edges, 384 frusta exact leaf sets/chains\n",path,t.node_count,unsafe);
	destroy_tree(&t);free(raw);
}
int main(int argc,char **argv)
{
	synthetic();puts("PASS hierarchical culling: exact sets, 4092→4 plane tests, PVS/areas, invalid bounds, disabled culling, reload/free and allocation fallback");
	for(int i=1;i<argc;++i)real_bsp(argv[i]);return 0;
}
