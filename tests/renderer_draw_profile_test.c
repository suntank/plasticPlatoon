/* Exercise the production diagnostic state without requiring a GL context. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

typedef int qboolean;
enum { false = 0, true = 1 };
typedef unsigned int GLuint, GLenum;
typedef int GLsizei;
#define APIENTRY

typedef struct { char name[64], string[96]; float value; } cvar_t;
static cvar_t cvars[128];
static size_t cvar_count;

static cvar_t *TestGet(const char *name, const char *value, int flags)
{
	(void)flags;
	for (size_t i = 0; i < cvar_count; ++i)
		if (!strcmp(cvars[i].name, name)) return &cvars[i];
	assert(cvar_count < sizeof(cvars) / sizeof(cvars[0]));
	cvar_t *out = &cvars[cvar_count++];
	snprintf(out->name, sizeof(out->name), "%s", name);
	snprintf(out->string, sizeof(out->string), "%s", value);
	out->value = strtof(value, NULL);
	return out;
}
static void TestSet(const char *name, const char *value)
{
	cvar_t *out = TestGet(name, value, 0);
	snprintf(out->string, sizeof(out->string), "%s", value);
	out->value = strtof(value, NULL);
}
static struct {
	cvar_t *(*Cvar_Get)(const char *, const char *, int);
	void (*Cvar_Set)(const char *, const char *);
} ri = { TestGet, TestSet };


#ifdef USE_SDL3
#include <SDL3/SDL.h>
#else
#include <SDL2/SDL.h>
#endif
typedef struct { char name[128]; int type; } model_t;
typedef struct { int flags; } entity_t;
enum { mod_alias, mod_brush, mod_sprite };
#define RF_BEAM 128
#define RF_WEAPONMODEL 4
#define RF_PP_ENEMY_COLOR 0x00200000
static const char *PP_PickupLODPath(const char *name) {
 return !strcmp(name,"models/items/armor/shard/tris.md2") ? "lod1.md2" : NULL;
}
static cvar_t *r_perf;
static struct { qboolean multitexture, lightmapcopies; } gl_config = {1,0};
#include "../src/client/refresh/gl1/header/draw_profile.h"
#include "../src/client/refresh/gl1/draw_profile_impl.h"
static float value(const char *name) {return TestGet(name,"-999",0)->value;}
int main(void) {
 r_perf=TestGet("r_perf","1",0);
 PP_DPBegin(); PP_DPEnter(DP_WORLD,NULL); PP_DPDraw(); PP_DPLeave(); PP_DPEnd();
 assert(value("r_perf_dp_enabled")==0);
 TestSet("r_drawprofile","1"); PP_DPBegin();
 PP_DPEnter(DP_WORLD,NULL); for(int i=0;i<3;i++)PP_DPDraw(); PP_DPLeave();
 PP_DPEnter(DP_INLINE,"*11"); for(int i=0;i<7;i++)PP_DPDraw(); SDL_Delay(2); PP_DPLeave();
 PP_DPEnter(DP_INLINE,"*2"); for(int i=0;i<4;i++)PP_DPDraw(); PP_DPLeave();
 PP_DPEnter(DP_WORLD,NULL);
 PP_DPSetFlush(DP_FLUSH_TYPE|DP_FLUSH_COLOR); PP_DPFlush(); PP_DPFlush(); PP_DPLeave();
 PP_DP_WORLD_ADD(DPW_LM_BUILD_CALLS, 2); PP_DP_WORLD_ADD(DPW_LM_BUILD_TEXELS, 80);
 PP_DP_WORLD_ADD(DPW_LM_UPLOAD_BYTES, 320); PP_DP_WORLD_ADD(DPW_LM_ATLAS_COUNT, 4);
 for (int metric=DPW_LM_STATIC_MS;metric<DPW_METRICS;++metric) PP_DP_WORLD_ADD(metric, metric+1);
 model_t m={"models/items/armor/shard/tris.md2",mod_alias}; entity_t e={0};
 assert(PP_DPEntity(&e,&m)==DP_PICKUP);
 strcpy(m.name,"models/monsters/soldier/tall/weapon_machinegun.md2"); assert(PP_DPEntity(&e,&m)==DP_NPC_HELD);
 strcpy(m.name,"models/monsters/soldier/tall/tris.md2"); assert(PP_DPEntity(&e,&m)==DP_NPC_BODY);
 strcpy(m.name,"players/soldier/weapon.md2"); assert(PP_DPEntity(&e,&m)==DP_PLAYER_HELD);
 e.flags=RF_WEAPONMODEL; assert(PP_DPEntity(&e,&m)==DP_VIEWWEAPON);
 PP_DPEnd();
 assert(value("r_perf_dp_enabled")==1 && value("r_perf_dp_world_draws")==3);
 assert(value("r_perf_dp_inline_draws")==11 && value("r_perf_dp_inline_top0_model")==11);
 assert(value("r_perf_dp_inline_top0_draws")==7 && value("r_perf_dp_inline_top1_model")==2);
 assert(value("r_perf_dp_flush_type")==1 && value("r_perf_dp_flush_color")==1 && value("r_perf_dp_flush_explicit")==1);
 assert(value("r_perf_dp_world_flush_type")==1 && value("r_perf_dp_world_flush_color")==1);
 assert(value("r_perf_dp_lm_build_calls")==2 && value("r_perf_dp_lm_build_texels")==80 && value("r_perf_dp_lm_upload_bytes")==320);
 assert(value("r_perf_dp_mtex_enabled")==1 && value("r_perf_dp_lm_copy_enabled")==0 && value("r_perf_dp_lm_atlas_count")==4);
 for (int metric=DPW_LM_STATIC_MS;metric<DPW_METRICS;++metric) {
  char name[96];snprintf(name,sizeof(name),"r_perf_dp_%s",dp_world_names[metric]);
  assert(value(name)==metric+1);
 }
 assert(value("r_perf_dp_inline_ms")>0 && value("r_perf_dp_inline_top0_ms")>0);
 TestSet("r_drawprofile","0"); PP_DPBegin(); PP_DPDraw(); PP_DPEnd(); assert(value("r_perf_dp_enabled")==0);
 int evaluated=0; PP_DP_WORLD_ADD(DPW_LM_STATIC_MS, ++evaluated);assert(evaluated==0);
 puts("PASS: opt-in draw attribution, nonexclusive flush causes, inline top IDs, CPU scopes and disabled reset");
 return 0;
}
