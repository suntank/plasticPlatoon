/* Executable regressions over the production effect/parser/routing functions.
 * SDL, audio, graphics and BSP I/O are stubbed; effect algorithms are not.
 * GPL-2.0-or-later. */
#include <assert.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../../src/client/cl_splitscreen.c"
#include "../../src/client/cl_tempentities.c"
#include "../../src/client/header/player_muzzle_points.h"

client_state_t cl;
client_static_t cls;
char cl_weaponmodels[MAX_CLIENTWEAPONMODELS][MAX_QPATH];
int num_cl_weaponmodels;
centity_t *cl_entities;
int cl_numentities;
entity_state_t *cl_entity_parse_stream;
entity_state_t cl_parse_entities[MAX_PARSE_ENTITIES];
sizebuf_t net_message;
int num_power_sounds;
server_t sv;
server_static_t svs;
game_export_t *ge;
static game_export_t test_game;
static client_t test_clients[3];
static edict_t test_edicts[4];
static cvar_t zero = {.string = "0", .value = 0};
static cvar_t one = {.string = "1", .value = 1};
static cvar_t three = {.string = "3", .value = 3};
static cvar_t renderer = {.string = "gl1"};
cvar_t *vid_renderer = &renderer;
cvar_t *cl_paused = &zero, *cl_r1q2_lightstyle = &zero, *cl_timedemo = &zero, *cl_footsteps = &one;
cvar_t *cl_limitsparksounds = &zero, *cl_laseralpha = &one;
cvar_t *maxclients = &three, *hand = &zero, *cl_vwep = &one;
static unsigned int random_state = 1, random_calls;
static unsigned int sound_calls, submitted_particles, submitted_entities, submitted_lights;
static vec3_t last_light_color;
static float last_light_intensity;
static char last_sound_name[MAX_QPATH];
static char last_model_name[MAX_QPATH];
static particle_t submissions[MAX_PARTICLES];
static entity_t entity_submissions[MAX_ENTITIES];
static byte test_pvs = 0xff;
static qboolean connected_areas[4] = {true, true, true, true};
static int test_loopback_slot, transmitted_slot;
static unsigned int transmit_calls;
static byte transmitted_command[MAX_MSGLEN];
static int transmitted_length;
static qboolean load_muzzle_profile;
static const char *test_lerpmodels="1";
const char *Cvar_VariableString(const char *name) { return !strcmp(name,"r_lerpmodels") ? test_lerpmodels : ""; }

int randk(void) { ++random_calls; random_state = random_state * 1664525u + 1013904223u; return (int)(random_state & 0x7fffffffu); }
float frandk(void) { return (randk() & 32767) * (1.0f / 32767.0f); }
float crandk(void) { return (randk() & 32767) * (2.0f / 32767.0f) - 1.0f; }
void Com_Error(int code, const char *fmt, ...) { va_list args; (void)code; va_start(args,fmt); vfprintf(stderr,fmt,args); va_end(args); abort(); }
void Com_Printf(const char *fmt, ...) { (void)fmt; }
void Com_DPrintf(const char *fmt, ...) { (void)fmt; }
void V_AddParticle(vec3_t origin, unsigned int color, float alpha) { particle_t *p = &submissions[submitted_particles++]; assert(submitted_particles <= MAX_PARTICLES); VectorCopy(origin,p->origin); p->color=color; p->alpha=alpha; }
void V_AddEntity(entity_t *ent) { assert(submitted_entities < MAX_ENTITIES); entity_submissions[submitted_entities++]=*ent; }
void V_AddLight(vec3_t org, float intensity, float r, float g, float b) { (void)org;last_light_intensity=intensity;VectorSet(last_light_color,r,g,b);++submitted_lights; }
struct model_s *R_RegisterModel(const char *name) { snprintf(last_model_name,sizeof(last_model_name),"%s",name); return (struct model_s *)(uintptr_t)1; }
struct image_s *R_RegisterSkin(const char *name) { (void)name; return (struct image_s *)(uintptr_t)1; }
struct image_s *Draw_FindPic(const char *name) { (void)name; return (struct image_s *)(uintptr_t)1; }
float CalcFov(float fov, float width, float height) { return atan(height / (width / tan(fov * M_PI / 360))) * 360 / M_PI; }
/* Material selection is covered by color_skins_test; this fixture stubs
 * graphics resources while exercising the real effect submission paths. */
struct image_s *CL_EnemyModelSkin(const char *path, int skin, int flags) { (void)path; (void)skin; (void)flags; return NULL; }
struct image_s *CL_PlayerWeaponSkin(const clientinfo_t *ci, const char *path) { (void)ci; (void)path; return NULL; }
struct image_s *CL_PlayerLinkedWeaponSkin(const clientinfo_t *owner, const clientinfo_t *source, int weapon) { (void)owner; (void)source; (void)weapon; return NULL; }
struct sfx_s *S_RegisterSound(const char *name) { snprintf(last_sound_name,sizeof(last_sound_name),"%s",name); return (struct sfx_s *)(uintptr_t)1; }
void S_StartSound(vec3_t org, int entnum, int channel, struct sfx_s *sfx, float volume, float attenuation, float offset) { (void)org;(void)entnum;(void)channel;(void)sfx;(void)volume;(void)attenuation;(void)offset; ++sound_calls; }
int CM_PointLeafnum(vec3_t p) { return (int)p[0]; }
int CM_LeafCluster(int leaf) { return leaf; }
int CM_LeafArea(int leaf) { return leaf; }
int CM_PointContents(vec3_t p, int headnode) { (void)p; (void)headnode; return 0; }
byte *CM_ClusterPVS(int cluster) { (void)cluster; return &test_pvs; }
byte *CM_ClusterPHS(int cluster) { (void)cluster; return &test_pvs; }
qboolean CM_AreasConnected(int a, int b) { (void)a; return connected_areas[b]; }
cvar_t *Cvar_Get(const char *name, const char *value, int flags) { (void)name;(void)value;(void)flags; return &zero; }
int FS_FOpenFile(const char *name, fileHandle_t *f, qboolean game_only) { (void)name; (void)f; (void)game_only; return -1; }
void FS_FCloseFile(fileHandle_t f) { (void)f; }
const char *FS_GetFilenameForHandle(fileHandle_t f) { (void)f; return NULL; }
int FS_LoadFile(const char *path, void **buffer)
{
    FILE *f; long size;
    *buffer=NULL;
    if (!load_muzzle_profile || strcmp(path,"tuning/default.json")) return -1;
    f=fopen("baseq2/tuning/default.json","rb"); assert(f);
    assert(!fseek(f,0,SEEK_END)); size=ftell(f); assert(size>0);
    rewind(f); *buffer=malloc((size_t)size+1); assert(*buffer);
    assert(fread(*buffer,1,(size_t)size,f)==(size_t)size); fclose(f);
    ((char *)*buffer)[size]='\0'; return (int)size;
}
void FS_FreeFile(void *buffer) { free(buffer); }
void *Z_Realloc(void *ptr,int size) { (void)ptr; (void)size; assert(!"fixture entity buffers are preallocated"); return NULL; }
centity_t *CL_AllocEntity(int entnum) { assert(entnum>=0 && entnum<cl_numentities); return &cl_entities[entnum]; }
qboolean NET_CompareAdr(netadr_t a, netadr_t b) { return a.type==b.type && a.port==b.port && !memcmp(a.ip,b.ip,sizeof(a.ip)); }
int NET_GetLoopbackSlot(netsrc_t sock) { assert(sock==NS_CLIENT); return test_loopback_slot; }
void NET_SetLoopbackSlot(netsrc_t sock,int slot) { assert(sock==NS_CLIENT); test_loopback_slot=slot; }
void Netchan_Transmit(netchan_t *chan,int length,byte *data)
{
    assert(length==0 && data==NULL);
    ++transmit_calls; transmitted_slot=test_loopback_slot;
    transmitted_length=chan->message.cursize;
    assert(transmitted_length<=(int)sizeof(transmitted_command));
    memcpy(transmitted_command,chan->message.data,transmitted_length);
    SZ_Clear(&chan->message);
}

static void ResetOutput(void) { submitted_particles=submitted_entities=submitted_lights=0; memset(submissions,0,sizeof(submissions)); }
static void ResetEffects(void)
{
    CL_ResetEntityEffectQueue();
    memset(&cl,0,sizeof(cl)); memset(&cls,0,sizeof(cls));
    memset(&cl_effect_stats,0,sizeof(cl_effect_stats));
    zero.value=0; cl.time=1000; cls.framecount=10; cls.state=ca_active;
    cl.frame.valid=true; cl.frame.serverframe=10; cl.frame.servertime=1000;
    cl.lerpfrac=0.5f; cl_effect_render_slot=-1;
    cl_effect_only_slot=cl_effect_exclude_slot=0;
    CL_ClearEffects(); CL_ClearTEnts();
    random_state=1; random_calls=sound_calls=0; last_sound_name[0]=0; ResetOutput();
}

static void ResetRecipients(void)
{
    int i;
    memset(&sv,0,sizeof(sv)); memset(&svs,0,sizeof(svs));
    memset(&ss_state,0,sizeof(ss_state));
    memset(test_clients,0,sizeof(test_clients)); memset(test_edicts,0,sizeof(test_edicts));
    ss_state.session_active=true; ss_state.requested_players=2;
    svs.clients=test_clients; ge=&test_game;
    test_game.edicts=test_edicts; test_game.edict_size=sizeof(test_edicts[0]);
    SZ_Init(&sv.multicast,sv.multicast_buf,sizeof(sv.multicast_buf));
    for(i=0;i<3;++i) {
        test_clients[i].state=cs_spawned;
        test_clients[i].netchan.remote_address.type=i<2?NA_LOOPBACK:NA_IP;
        test_clients[i].netchan.remote_address.port=(unsigned short)BigShort(i+1);
        SZ_Init(&test_clients[i].datagram,test_clients[i].datagram_buf,sizeof(test_clients[i].datagram_buf));
        SZ_Init(&test_clients[i].netchan.message,test_clients[i].netchan.message_buf,sizeof(test_clients[i].netchan.message_buf));
        test_edicts[i+1].s.origin[0]=(float)i;
        connected_areas[i]=true;
        if(i<2) { ss_state.slots[i].active=true; ss_state.slots[i].state=SS_SLOT_ACTIVE;
            ss_state.slots[i].local_index=i; ss_state.slots[i].loopback_slot=i;
            ss_state.slots[i].playernum=i; ss_state.slots[i].connection_state=ca_active;
            ss_state.slots[i].frame=cl.frame; }
    }
    test_pvs=0xff;
}

static void SendExplosion(multicast_t mode)
{
    vec3_t origin={0,0,0};
    MSG_WriteByte(&sv.multicast,svc_temp_entity);
    MSG_WriteByte(&sv.multicast,TE_ROCKET_EXPLOSION);
    MSG_WritePos(&sv.multicast,origin);
    SV_Multicast(origin,mode);
}

static void Deliver(int slot, qboolean reliable)
{
    sizebuf_t *msg=reliable?&test_clients[slot].netchan.message:&test_clients[slot].datagram;
    MSG_BeginReading(msg);
    while(msg->readcount<msg->cursize) {
        assert(MSG_ReadByte(msg)==svc_temp_entity);
        if(slot==0) { net_message=*msg; CL_ParseTEnt(); *msg=net_message; }
        else SS_ParseSharedTempEntity(&ss_state.slots[slot],msg);
    }
    SZ_Clear(msg);
}

static void TestOccurrences(void)
{
    ResetEffects(); ResetRecipients();
    SendExplosion(MULTICAST_PVS);
    assert(test_clients[0].datagram.cursize==8 && test_clients[1].datagram.cursize==0 && test_clients[2].datagram.cursize==8);
    Deliver(0,false); Deliver(1,false);
    assert(cl_effect_stats.temp_events_parsed==1 && cl_effect_stats.particles_created==296 && sound_calls==1);
    ResetEffects(); ResetRecipients(); test_pvs=2;
    SendExplosion(MULTICAST_PVS); Deliver(0,false); Deliver(1,false);
    assert(cl_effect_stats.temp_events_parsed==1 && cl_effect_stats.particles_created==296);
    ResetEffects(); ResetRecipients();
    SendExplosion(MULTICAST_ALL); SendExplosion(MULTICAST_ALL);
    Deliver(0,false); Deliver(1,false);
    assert(cl_effect_stats.temp_events_parsed==2 && cl_effect_stats.particles_created==592);
    ++sv.framenum; ++cl.frame.serverframe; SendExplosion(MULTICAST_ALL);
    cls.framecount+=37; cl.time+=100; Deliver(1,false); Deliver(0,false);
    assert(cl_effect_stats.temp_events_parsed==3 && cl_effect_stats.particles_created==888);
    /* Session/map resets introduce no cached occurrence identity to collide. */
    ResetEffects(); ResetRecipients(); SendExplosion(MULTICAST_ALL_R);
    Deliver(0,true); Deliver(1,true); assert(cl_effect_stats.temp_events_parsed==1);
    /* Reliable delivery includes clients still loading/reconnecting, exactly
     * as the ordinary multicast send path does. Unreliable requires spawned. */
    ResetEffects(); ResetRecipients();
    test_clients[0].state=test_clients[1].state=cs_connected;
    cls.state=ca_connected;
    ss_state.slots[1].connection_state=ca_connected;
    SendExplosion(MULTICAST_ALL_R);
    assert(test_clients[0].netchan.message.cursize==8 && test_clients[1].netchan.message.cursize==0);
    Deliver(0,true); assert(cl_effect_stats.temp_events_parsed==1);
    SendExplosion(MULTICAST_ALL);
    assert(test_clients[0].datagram.cursize==0 && test_clients[1].datagram.cursize==0);
    ResetEffects(); ResetRecipients(); ss_state.slots[1].state=SS_SLOT_DROPPED;
    test_pvs=2; SendExplosion(MULTICAST_PVS); assert(test_clients[1].datagram.cursize==0);
    ResetEffects(); ResetRecipients(); test_clients[0].datagram.cursize=test_clients[0].datagram.maxsize;
    SendExplosion(MULTICAST_ALL); assert(test_clients[1].datagram.cursize==8); Deliver(1,false);
    assert(cl_effect_stats.temp_events_parsed==1);
    /* SZ_Write can reset cursize after overflow, but packet sending discards
     * the entire buffer while overflowed remains true. Never select it. */
    ResetEffects(); ResetRecipients(); test_clients[0].datagram.overflowed=true;
    SendExplosion(MULTICAST_ALL);
    assert(test_clients[0].datagram.cursize==0 && test_clients[1].datagram.cursize==8);
    Deliver(1,false); assert(cl_effect_stats.temp_events_parsed==1);
    ResetEffects(); ResetRecipients(); test_clients[0].netchan.message.overflowed=true;
    SendExplosion(MULTICAST_ALL_R);
    assert(test_clients[0].netchan.message.cursize==0 && test_clients[1].netchan.message.cursize==8);
    Deliver(1,true); assert(cl_effect_stats.temp_events_parsed==1);
    ResetEffects(); ResetRecipients(); connected_areas[0]=false;
    SendExplosion(MULTICAST_PVS); assert(test_clients[0].datagram.cursize==0 && test_clients[1].datagram.cursize==8);
    Deliver(1,false); assert(cl_effect_stats.particles_created==296);
    /* A dropped primary still owns and consumes the host connection. */
    ResetEffects(); ResetRecipients(); ss_state.slots[0].state=SS_SLOT_DROPPED;
    SendExplosion(MULTICAST_ALL); Deliver(0,false); assert(cl_effect_stats.particles_created==296);
    /* Remote and non-temp commands keep their original recipients/bytes. */
    ResetEffects(); ResetRecipients();
    MSG_WriteByte(&sv.multicast,svc_muzzleflash); MSG_WriteShort(&sv.multicast,1); MSG_WriteByte(&sv.multicast,MZ_BLASTER);
    { vec3_t org={0,0,0}; SV_Multicast(org,MULTICAST_ALL); }
    assert(test_clients[0].datagram.cursize==4 && test_clients[1].datagram.cursize==4 && test_clients[2].datagram.cursize==4);
    /* Reconnect may reorder server slots; primary demo bytes stay present. */
    ResetEffects(); ResetRecipients();
    test_clients[0].netchan.remote_address.port=(unsigned short)BigShort(2);
    test_clients[1].netchan.remote_address.port=(unsigned short)BigShort(1);
    SendExplosion(MULTICAST_ALL);
    assert(test_clients[0].datagram.cursize==0 && test_clients[1].datagram.cursize==8);
    /* Standard server-demo storage records one original multicast. */
    ResetEffects(); ResetRecipients();
    { byte recorded[32]; FILE *marker=tmpfile(); assert(marker); svs.demofile=marker;
      SZ_Init(&svs.demo_multicast,recorded,sizeof(recorded)); SendExplosion(MULTICAST_ALL);
      assert(svs.demo_multicast.cursize==8 && !memcmp(recorded,test_clients[2].datagram.data,8));
      fclose(marker); svs.demofile=NULL; }
    puts("PASS event occurrences: shared, secondary-only, identical/successive, delayed, resets, reliability, area gating, overflow fallback");
}

static cparticle_t *AddTestParticle(qboolean instant)
{
    cparticle_t *p=CL_AllocParticle(); assert(p);
    memset(p->org,0,sizeof(p->org)); memset(p->vel,0,sizeof(p->vel)); memset(p->accel,0,sizeof(p->accel));
    p->time=cl.time; p->alpha=1; p->alphavel=instant?INSTANT_PARTICLE:-1; p->color=7;
    return p;
}

static void TestParticleFrame(void)
{
    uint64_t updates; unsigned int rng;
    particle_t first[2];
    ResetEffects(); AddTestParticle(false); AddTestParticle(true);
    assert(CL_BeginSharedEffects()); CL_PrepareParticles();
    updates=cl_effect_stats.particle_updates; rng=random_calls;
    cl_effect_render_slot=1; CL_AddParticles(); assert(submitted_particles==2); memcpy(first,submissions,sizeof(first));
    ResetOutput(); cl_effect_render_slot=0; CL_AddParticles(); assert(submitted_particles==2 && !memcmp(first,submissions,sizeof(first)));
    assert(cl_effect_stats.particle_updates==updates && random_calls==rng && !CL_BeginSharedEffects());
    zero.value=1; ++cls.framecount; assert(!CL_BeginSharedEffects()); ResetOutput(); CL_AddParticles(); assert(submitted_particles==2);
    zero.value=0; ++cls.framecount; cl.time+=17; assert(CL_BeginSharedEffects()); CL_PrepareParticles();
    ResetOutput(); CL_AddParticles(); assert(submitted_particles==1 && cl_effect_stats.particles_expired==1);
    ++cls.framecount; cl.time+=2000; assert(CL_BeginSharedEffects()); CL_PrepareParticles();
    assert(cl_effect_stats.active_particles==0 && cl_effect_stats.prepared_particles==0);
    puts("PASS particles: identical instant output in both orders, read-only draw, pause/resume, irregular cadence");
}

static centity_t test_entities[4][16];

static void TestAuthoredWeaponADS(void)
{
    const char *models[] = {"v_machn", "v_blast", "v_shotg", "v_shotg2", "v_chain", "v_launch", "v_rocket", "v_rail", "v_hyperb", "v_bfg"};
    const int configs[] = {PP_MODEL_ADS_RIFLE, PP_MODEL_ADS_PISTOL,
        PP_MODEL_ADS_SHOTGUN, PP_MODEL_ADS_SSHOTGUN, PP_MODEL_ADS_M60, PP_MODEL_ADS_GLAUNCHER,
        PP_MODEL_ADS_RLAUNCHER, PP_MODEL_ADS_SNIPER, PP_MODEL_ADS_FLAMETHROWER, PP_MODEL_ADS_MORTAR};
    ResetEffects();
    cl.frame.playerstate.gunindex=1;
    for (unsigned weapon=0; weapon<sizeof(models)/sizeof(*models); ++weapon) {
        pp_model_ads_config_t expected=PP_ModelADSConfig(configs[weapon]);
        pp_model_ads_config_t actual;
        snprintf(cl.configstrings[CS_MODELS+1],MAX_QPATH,
            "models/weapons/%s/tris.md2",models[weapon]);
        cl.frame.playerstate.fov=configs[weapon]==PP_MODEL_ADS_SNIPER ? 90.f/8.f : 45.f;
        assert(CL_UsesModelADS(&cl.frame.playerstate));
        assert(!CL_GetADSOverlayPicName());
        assert(!SS_GetADSOverlayPicName(&cl.frame.playerstate));
        actual=CL_GetModelADSConfig(&cl.frame.playerstate);
        assert(actual.forward==expected.forward && actual.right==expected.right && actual.up==expected.up);
        assert(actual.muzzle_forward==expected.muzzle_forward &&
            actual.muzzle_right==expected.muzzle_right && actual.muzzle_up==expected.muzzle_up);
        assert(actual.animated==expected.animated);
        assert(actual.recoil_back==expected.recoil_back);
        assert(cl.frame.playerstate.fov==(configs[weapon]==PP_MODEL_ADS_SNIPER ? 90.f/8.f : 45.f));
    }
    strcpy(cl.configstrings[CS_MODELS+1],"models/weapons/v_handgr/tris.md2");
    assert(!CL_UsesModelADS(&cl.frame.playerstate));
    assert(!strcmp(CL_GetADSOverlayPicName(),"ads_handgrenade.png"));
    assert(!strcmp(SS_GetADSOverlayPicName(&cl.frame.playerstate),"ads_handgrenade.png"));
    puts("PASS authored weapon ADS: all ten guns select model sights/offsets in single/split views; sniper zoom and hand-grenade overlay remain");
}

static void TestPlayerMuzzleFlashes(void)
{
    const int weapons[] = {MZ_BLASTER, MZ_HYPERBLASTER, MZ_MACHINEGUN,
        MZ_CHAINGUN1, MZ_CHAINGUN2, MZ_CHAINGUN3, MZ_SHOTGUN, MZ_SHOTGUN2,
        MZ_SSHOTGUN, MZ_RAILGUN, MZ_ETF_RIFLE, MZ_ROCKET, MZ_GRENADE, MZ_BFG};
    byte data[8];
    size_t i;
    int thirdperson;
    extern cvar_t *cl_mflash_thirdperson_up, *cl_mflash_thirdperson_crouch_down;

    load_muzzle_profile=false; CL_InitMuzzleFlashCvars();
    assert(!strcmp(CL_GetMuzzleFlashConfig(MZ_BLASTER,false)->image,"sprites/muzzleFlashSmall.png"));
    assert(!strcmp(CL_GetMuzzleFlashConfig(MZ_SHOTGUN2,false)->image,"sprites/muzzleFlashSmall.png"));
    CL_RegisterTEntModels();
    assert(!strcmp(last_model_name,"sprites/muzzleFlashSmall.png"));
    load_muzzle_profile=true; CL_InitMuzzleFlashCvars();
    assert(CL_GetMuzzleFlashConfig(MZ_HYPERBLASTER,false)->forward==20);
    assert(CL_GetMuzzleFlashConfig(MZ_HYPERBLASTER,true)->forward==27);
    assert(CL_GetMuzzleFlashConfig(MZ_SHOTGUN2,true)->forward==CL_GetMuzzleFlashConfig(MZ_SHOTGUN,true)->forward);

    cl_mflash_thirdperson_up = &zero;
    cl_mflash_thirdperson_crouch_down = &zero;
    for (i = 0; i < sizeof(weapons)/sizeof(weapons[0]); ++i) {
        for (thirdperson = 0; thirdperson < 2; ++thirdperson) {
            muzzle_flash_config_t *cfg;
            ResetEffects();
            cl_entities = test_entities[0]; cl_numentities = 16;
            memset(test_entities[0], 0, sizeof(test_entities[0]));
            cfg = CL_GetMuzzleFlashConfig(weapons[i], thirdperson);
            memset(cfg, 0, sizeof(*cfg));
            cfg->enabled = true; cfg->forward = thirdperson ? 20 : 10;
            cfg->scale = 2; cfg->duration_ms = 50;
            strcpy(cfg->image, "sprites/muzzleFlashSmall.png");
            cl.playernum = thirdperson ? 0 : 1;
            SZ_Init(&net_message, data, sizeof(data));
            MSG_WriteShort(&net_message, 2); MSG_WriteByte(&net_message, weapons[i]);
            MSG_BeginReading(&net_message); CL_AddMuzzleFlash();
            assert(net_message.readcount == 3);
            assert(cl_explosions[0].type == (thirdperson ? ex_mflash_billboard : ex_mflash_cone_h));
            if (!thirdperson && (weapons[i]==MZ_BLASTER || weapons[i]==MZ_MACHINEGUN ||
                weapons[i]==MZ_SHOTGUN || weapons[i]==MZ_SSHOTGUN || weapons[i]==MZ_ROCKET || weapons[i]==MZ_RAILGUN ||
                weapons[i]==MZ_HYPERBLASTER || weapons[i]==MZ_BFG ||
                weapons[i]==MZ_CHAINGUN1 || weapons[i]==MZ_CHAINGUN2 || weapons[i]==MZ_CHAINGUN3)) {
                /* Authored weapons share their actual model muzzle with the
                 * renderer, overriding the legacy tuning-only eye offset. */
                pp_model_ads_config_t pose=PP_ModelADSConfig(weapons[i]==MZ_BFG ? PP_MODEL_ADS_MORTAR :
                    weapons[i]==MZ_HYPERBLASTER ? PP_MODEL_ADS_FLAMETHROWER :
                    weapons[i]==MZ_RAILGUN ? PP_MODEL_ADS_SNIPER : weapons[i]==MZ_ROCKET ?
                    PP_MODEL_ADS_RLAUNCHER : (weapons[i]==MZ_CHAINGUN1 ||
                    weapons[i]==MZ_CHAINGUN2 || weapons[i]==MZ_CHAINGUN3) ? PP_MODEL_ADS_M60 : weapons[i]==MZ_SSHOTGUN ?
                    PP_MODEL_ADS_SSHOTGUN : weapons[i]==MZ_SHOTGUN ?
                    PP_MODEL_ADS_SHOTGUN : weapons[i]==MZ_BLASTER ?
                    PP_MODEL_ADS_PISTOL : PP_MODEL_ADS_RIFLE);
                float blend=CL_GetModelADSBlend(-1);
                assert(fabsf(cl_explosions[0].ent.origin[0] -
                    (pose.muzzle_forward+blend*pose.forward)) < .001f);
                assert(fabsf(cl_explosions[0].ent.origin[1] +
                    (pose.muzzle_right+blend*pose.right)) < .001f);
                assert(fabsf(cl_explosions[0].ent.origin[2] -
                    (pose.muzzle_up+blend*pose.up)) < .001f);
            } else {
                assert(fabsf(cl_explosions[0].ent.origin[0] - (thirdperson ? 20 : 10)) < 0.001f);
            }
            if (!thirdperson) assert(cl_explosions[1].type == ex_mflash_cone_v);
        }
    }
    puts("PASS player muzzle flashes: every weapon event spawns first- and third-person sprites");
}

static void SetupSplitMuzzleObservers(int players, int entnum)
{
    int view, history;
    ResetEffects(); ResetRecipients();
    ss_state.transport=SS_TRANSPORT_SPLITSCREEN;
    ss_state.requested_players=players;
    memset(test_entities,0,sizeof(test_entities));
    for (history=0; history<2; ++history) {
        centity_t *ent=&test_entities[history][entnum];
        ent->serverframe=cl.frame.serverframe;
        ent->current.number=entnum; ent->current.modelindex=1;
        ent->current.origin[0]=100; ent->prev=ent->current;
    }
    for (view=0; view<players; ++view) {
        ss_local_player_t *slot=&ss_state.slots[view];
        slot->local_index=view; slot->playernum=view;
        slot->active=slot->snapshot_valid=true; slot->state=SS_SLOT_ACTIVE;
        slot->connection_state=ca_active; slot->frame=cl.frame;
        slot->frame.playerstate.fov=90;
        slot->entities=test_entities[view?1:0]; slot->entity_count=16;
    }
    cl_entities=test_entities[0]; cl_numentities=16; cl.playernum=0;
}

static void TestScopedModelMuzzleFlashes(void)
{
    const int events[] = {MZ_CHAINGUN1, MZ_CHAINGUN2, MZ_CHAINGUN3, MZ_ROCKET, MZ_RAILGUN, MZ_HYPERBLASTER, MZ_BFG};
    vec3_t origin={0,0,0}, forward={1,0,0}, right={0,-1,0}, up={0,0,1}, velocity={0,0,0};
    for (unsigned event=0; event<sizeof(events)/sizeof(*events); ++event) {
        pp_model_ads_config_t pose=PP_ModelADSConfig(events[event]==MZ_BFG ? PP_MODEL_ADS_MORTAR :
            events[event]==MZ_HYPERBLASTER ? PP_MODEL_ADS_FLAMETHROWER :
            events[event]==MZ_RAILGUN ? PP_MODEL_ADS_SNIPER : events[event]==MZ_ROCKET ?
            PP_MODEL_ADS_RLAUNCHER : PP_MODEL_ADS_M60);
        for (int slot=0; slot<4; ++slot) {
            muzzle_flash_config_t *cfg;
            float blend;
            SetupSplitMuzzleObservers(4,slot+1);
            cl.frame.playerstate.fov=events[event]==MZ_RAILGUN ? 90.f/8.f : 45.f;
            /* Distinct aim amounts expose accidental one-based scope indexing. */
            for (int player=0; player<4; ++player)
                ss_state.slots[player].model_ads.progress=player/3.f;
            blend=PP_ModelADSAmount(&ss_state.slots[slot].model_ads);
            cfg=CL_GetMuzzleFlashConfig(events[event],false);
            memset(cfg,0,sizeof(*cfg));
            cfg->enabled=true; cfg->scale=2; cfg->duration_ms=50;
            strcpy(cfg->image,"sprites/muzzleFlashSmall.png");
            CL_SetEffectScope(slot,-1,false);
            CL_SpawnMuzzleFlashSprite(origin,forward,right,up,velocity,
                events[event],false,blend>0.f,slot+1);
            assert(cl_explosions[0].type==ex_mflash_cone_h);
            assert(fabsf(cl_explosions[0].ent.origin[0]-(pose.muzzle_forward+blend*pose.forward))<.001f);
            assert(fabsf(cl_explosions[0].ent.origin[1]+(pose.muzzle_right+blend*pose.right))<.001f);
            assert(fabsf(cl_explosions[0].ent.origin[2]-(pose.muzzle_up+blend*pose.up))<.001f);
            assert(cl.frame.playerstate.fov==(events[event]==MZ_RAILGUN ? 90.f/8.f : 45.f));
        }
    }
    puts("PASS M60/rocket/sniper/flame/mortar muzzle ADS: all seven fire events follow four independent scoped aim blends with sniper zoom intact");
}

static void TestFlamethrowerAndMortarPresentation(void)
{
    const int events[]={MZ_HYPERBLASTER,MZ_BFG};
    for (int weapon=0; weapon<2; ++weapon) {
        pp_model_ads_config_t pose=PP_ModelADSConfig(weapon ? PP_MODEL_ADS_MORTAR : PP_MODEL_ADS_FLAMETHROWER);
        for (int players=1; players<=4; players+=3) {
            for (int player=0; player<players; ++player) {
                for (int aimed=0; aimed<2; ++aimed) {
                    muzzle_flash_config_t *cfg;
                    SetupSplitMuzzleObservers(players,player+1);
                    strcpy(cl.configstrings[CS_MODELS+1],weapon ? "models/weapons/v_bfg/tris.md2" : "models/weapons/v_hyperb/tris.md2");
                    ss_local_player_t *slot=&ss_state.slots[player];
                    slot->frame.playerstate.gunindex=1;
                    slot->ads_down=aimed;
                    slot->model_ads.progress=aimed;
                    cfg=CL_GetMuzzleFlashConfig(events[weapon],false);
                    memset(cfg,0,sizeof(*cfg));
                    cfg->enabled=true; cfg->scale=2; cfg->duration_ms=50;
                    strcpy(cfg->image,"sprites/muzzleFlashSmall.png");
                    SS_ParseLocalSlotMuzzleFlash(slot,player+1,events[weapon],false);
                    assert(sound_calls==1 && !strcmp(last_sound_name,weapon ? "weapons/bfg__f1y.wav" : "weapons/hyprbf1a.wav"));
                    assert(cl_dlights[0].color[0]==1.f && cl_dlights[0].color[1]==.5f && cl_dlights[0].color[2]==(weapon ? .2f : .1f));
                    assert(cl_dlights[0].radius>=(weapon ? 200.f : 150.f) && cl_dlights[0].radius<=(weapon ? 231.f : 181.f));
                    assert(cl_explosions[0].type==ex_mflash_cone_h && cl_explosions[1].type==ex_mflash_cone_v);
                    assert(fabsf(cl_explosions[0].ent.origin[0]-(pose.muzzle_forward+aimed*pose.forward))<.001f);
                    assert(fabsf(cl_explosions[0].ent.origin[1]+(pose.muzzle_right+aimed*pose.right))<.001f);
                    assert(fabsf(cl_explosions[0].ent.origin[2]-(pose.muzzle_up+aimed*pose.up))<.001f);
                }
            }
        }
    }
    ResetEffects();
    vec3_t start={0,0,0}, end={32,0,0};
    CL_FlameTrail(start,end);
    assert(cl_effect_stats.particles_created==4);
    CL_PrepareParticles();
    CL_AddParticles();
    assert(submitted_particles==4);
    puts("PASS flamethrower/mortar effects: actual single/four-player hip/ADS muzzle positions, orange lights, fire reports and flame trail remain");
}

static void TestSniperSplitZoom(void)
{
    SetupSplitMuzzleObservers(4,1);
    strcpy(cl.configstrings[CS_MODELS+1],"models/weapons/v_rail/tris.md2");
    strcpy(cl.configstrings[CS_MODELS+2],"models/weapons/v_blast/tris.md2");
    for (int released=0; released<2; ++released) {
        for (int player=0; player<4; ++player) {
            ss_local_player_t *slot=&ss_state.slots[player];
            ss_viewport_t viewport={.x=(player%2)*640,.y=(player/2)*360,.w=640,.h=360};
            player_state_t *ps=&slot->frame.playerstate;
            refdef_t view={0};
            ps->gunindex=player%2 ? 2 : 1;
            ps->fov=released ? 90.f : player%2 ? 45.f : 90.f/8.f;
            /* Slot zero starts from the main view's already calculated FOV;
             * secondary views derive theirs from their own playerstate. */
            view.fov_x=player ? 90.f : ps->fov;
            SS_ApplyPlayerView(&view,slot,ps,NULL,&viewport);
            assert(view.fov_x==ps->fov);
            assert(view.fov_y==CalcFov(ps->fov,640.f,360.f));
            assert(CL_UsesModelADS(ps));
            assert(!SS_GetADSOverlayPicName(ps));
        }
    }
    puts("PASS sniper zoom: actual four-player view setup preserves independent 8x/2x aim and release FOV with model scopes");
}

static void TestGrenadeLauncherAndHandGrenadeFlashes(void)
{
    pp_model_ads_config_t pose=PP_ModelADSConfig(PP_MODEL_ADS_GLAUNCHER);
    for (int hand=0; hand<2; ++hand) {
        for (int slot=0; slot<4; ++slot) {
            for (int aimed=0; aimed<2; ++aimed) {
                muzzle_flash_config_t *cfg;
                float blend;
                SetupSplitMuzzleObservers(4,slot+1);
                strcpy(cl.configstrings[CS_MODELS+1],"models/weapons/v_launch/tris.md2");
                strcpy(cl.configstrings[CS_MODELS+2],"models/weapons/v_handgr/tris.md2");
                for (int player=0; player<4; ++player) {
                    ss_state.slots[player].frame.playerstate.gunindex=player%2+1;
                    ss_state.slots[player].model_ads.progress=aimed ? player/3.f : 0.f;
                    ss_state.slots[player].ads_down=aimed;
                }
                ss_state.slots[slot].frame.playerstate.gunindex=hand ? 2 : 1;
                /* The primary state deliberately differs from the shooter.
                 * The actual local parser must use the shooter's model. */
                cl.frame.playerstate.gunindex=hand ? 1 : 2;
                blend=PP_ModelADSAmount(&ss_state.slots[slot].model_ads);
                cfg=CL_GetMuzzleFlashConfig(MZ_GRENADE,false);
                memset(cfg,0,sizeof(*cfg));
                cfg->enabled=true; cfg->scale=2; cfg->duration_ms=50;
                cfg->forward=10; cfg->right=4; cfg->up=-3; cfg->ads_up=-1;
                strcpy(cfg->image,"sprites/muzzleFlashSmall.png");
                SS_ParseLocalSlotMuzzleFlash(&ss_state.slots[slot],slot+1,MZ_GRENADE,true);
                assert(cl_explosions[0].type==ex_mflash_cone_h);
                if (hand) {
                    /* Legacy split-screen offsets and image-ADS centering. */
                    assert(fabsf(cl_explosions[0].ent.origin[0]-20.f)<.001f);
                    assert(fabsf(cl_explosions[0].ent.origin[1]-(aimed ? 1.6f : -2.4f))<.001f);
                    assert(fabsf(cl_explosions[0].ent.origin[2]-(aimed ? 1.08f : -.76f))<.001f);
                } else {
                    assert(fabsf(cl_explosions[0].ent.origin[0]-(pose.muzzle_forward+blend*pose.forward))<.001f);
                    assert(fabsf(cl_explosions[0].ent.origin[1]+(pose.muzzle_right+blend*pose.right))<.001f);
                    assert(fabsf(cl_explosions[0].ent.origin[2]-(pose.muzzle_up+blend*pose.up))<.001f);
                }
                assert(cl.frame.playerstate.gunindex==(hand ? 1 : 2));
            }
        }
    }
    puts("PASS grenade muzzle selection: scoped launcher model ADS and unchanged hand-grenade legacy hip/ADS in all four slots");
}

static void TestSplitMuzzleScopes(void)
{
    byte data[8];
    int players, shooter, view, thirdperson;
    for (thirdperson=0; thirdperson<2; ++thirdperson) {
        muzzle_flash_config_t *cfg=CL_GetMuzzleFlashConfig(MZ_MACHINEGUN,thirdperson);
        memset(cfg,0,sizeof(*cfg));
        cfg->enabled=true; cfg->scale=20; cfg->duration_ms=50;
        strcpy(cfg->image,"sprites/muzzleFlashSmall.png");
    }
    /* Each connection receives the same shot. The shooter gets only its
     * first-person pair of crossed planes; each other camera gets exactly
     * one attached third-person billboard and its own light. */
    for (players=2; players<=4; ++players) {
        for (shooter=0; shooter<players; ++shooter) {
            SetupSplitMuzzleObservers(players,shooter+1);
            SZ_Init(&net_message,data,sizeof(data));
            MSG_WriteShort(&net_message,shooter+1); MSG_WriteByte(&net_message,MZ_MACHINEGUN);
            MSG_BeginReading(&net_message); CL_ParseMuzzleFlash(false,false);
            for (view=1; view<players; ++view) {
                ss_local_player_t *slot=&ss_state.slots[view];
                if (view==shooter) SS_ParseLocalSlotMuzzleFlash(slot,shooter+1,MZ_MACHINEGUN,true);
                else {
                    sizebuf_t msg;
                    SZ_Init(&msg,data,sizeof(data));
                    MSG_WriteShort(&msg,shooter+1); MSG_WriteByte(&msg,MZ_MACHINEGUN);
                    MSG_BeginReading(&msg); SS_ParseSharedMuzzleFlash(slot,&msg,false,true);
                }
                assert(!cl_effect_only_slot && !cl_effect_exclude_slot && !cl_effect_force_unique_dlight_keys);
            }
            assert(sound_calls==1);
            CL_PrepareTEnts();
            for (view=0; view<players; ++view) {
                ResetOutput(); cl_effect_render_slot=view;
                cl_entities=test_entities[view?1:0];
                CL_AddTEnts(); CL_AddDLights();
                assert(submitted_entities==(view==shooter?2u:1u));
                assert(submitted_lights==1);
            }
        }
        /* Monster flash sprites, lights and particles must also remain
         * with the observer whose packet spawned them. */
        SetupSplitMuzzleObservers(players,10);
        cl_mod_smoke=cl_mod_flash=NULL;
        cl_mod_smoke_sprite=(struct model_s *)(uintptr_t)1;
        cl_mod_explosion_sprite=(struct model_s *)(uintptr_t)2;
        SZ_Init(&net_message,data,sizeof(data));
        MSG_WriteShort(&net_message,10); MSG_WriteByte(&net_message,MZ2_INFANTRY_MACHINEGUN_1);
        MSG_BeginReading(&net_message); CL_ParseMuzzleFlash(true,false);
        for (view=1; view<players; ++view) {
            sizebuf_t msg;
            SZ_Init(&msg,data,sizeof(data));
            MSG_WriteShort(&msg,10); MSG_WriteByte(&msg,MZ2_INFANTRY_MACHINEGUN_1);
            MSG_BeginReading(&msg); SS_ParseSharedMuzzleFlash(&ss_state.slots[view],&msg,true,true);
        }
        assert(sound_calls==1);
        CL_PrepareTEnts(); CL_PrepareParticles();
        for (view=0; view<players; ++view) {
            ResetOutput(); cl_effect_render_slot=view;
            CL_AddTEnts(); CL_AddDLights(); CL_AddParticles();
            assert(submitted_entities==2 && submitted_lights==1 && submitted_particles==40);
        }
    }
    memset(&ss_state,0,sizeof(ss_state));
    puts("PASS split muzzle scopes: every shooter in 2/3/4 views sees only first-person flashes; observers and monster sprites/lights/particles have one copy");
}
/* Independent reproduction of the GL alias matrix, without AngleVectors. */
static void AliasMatrixPoint(const vec3_t angles, const vec3_t point, vec3_t result)
{
    const double r=angles[ROLL]*M_PI/180, p=angles[PITCH]*M_PI/180;
    const double y=angles[YAW]*M_PI/180;
    const double x1=point[0], y1=cos(r)*point[1]+sin(r)*point[2];
    const double z1=-sin(r)*point[1]+cos(r)*point[2];
    const double x2=cos(p)*x1+sin(p)*z1, z2=-sin(p)*x1+cos(p)*z1;
    result[0]=cos(y)*x2-sin(y)*y1;result[1]=sin(y)*x2+cos(y)*y1;result[2]=z2;
}

static void TestMuzzleModelMatrix(void)
{
    static const struct { const char *filename; int event; } events[]={
        {"w_blaster.md2",MZ_BLASTER},{"w_shotgun.md2",MZ_SHOTGUN},
        {"w_sshotgun.md2",MZ_SSHOTGUN},{"w_machinegun.md2",MZ_MACHINEGUN},
        {"w_chaingun.md2",MZ_CHAINGUN1},{"w_glauncher.md2",MZ_GRENADE},
        {"w_rlauncher.md2",MZ_ROCKET},{"w_hyperblaster.md2",MZ_HYPERBLASTER},
        {"w_railgun.md2",MZ_RAILGUN},{"w_bfg.md2",MZ_BFG},{"weapon.md2",MZ_MACHINEGUN}
    };
    unsigned checks=0;
    ResetEffects();ss_state.session_active=false;
    cl_entities=test_entities[0];cl_numentities=16;memset(test_entities,0,sizeof(test_entities));
    cl.frame.serverframe=8;cl.playernum=0;cl_vwep=&one;
    cl_entities[2].serverframe=8;cl_entities[2].current.number=2;
    cl_entities[2].current.modelindex=cl_entities[2].current.modelindex2=255;
    cl_entities[2].current.skinnum=1<<PP_PLAYER_SKINNUM_WEAPON_SHIFT;
    num_cl_weaponmodels=2;strcpy(cl_weaponmodels[0],"weapon.md2");
    cl.clientinfo[0].weaponmodel[0]=cl.clientinfo[0].weaponmodel[1]=(struct model_s *)(uintptr_t)1;
    VectorSet(cl_entities[2].prev.origin,10,20,30);VectorSet(cl_entities[2].current.origin,50,-10,20);
    for(int model=0;model<PP_PLAYER_MUZZLE_MODEL_COUNT;++model) {
        const pp_player_muzzle_model_t *m=&pp_player_muzzle_models[model];
        int event=-1;
        for(unsigned e=0;e<sizeof(events)/sizeof(*events);++e)
            if(!strcmp(m->filename,events[e].filename)) event=events[e].event;
        assert(event>=0);strcpy(cl_weaponmodels[1],m->filename);
        cl_entities[2].current.skinnum=!strcmp(m->filename,"weapon.md2")?0:1<<PP_PLAYER_SKINNUM_WEAPON_SHIFT;
        for(int frame=0;frame<m->num_frames;++frame) for(int rotation=0;rotation<3;++rotation) {
            vec3_t position,local,expected,angles,f,r,u;
            int oldframe=frame?frame-1:0;
            cl.lerpfrac=.37f;cl_entities[2].current.frame=frame;cl_entities[2].prev.frame=oldframe;
            VectorSet(cl_entities[2].prev.angles,-30+30*rotation,350,25-25*rotation);
            VectorSet(cl_entities[2].current.angles,-25+30*rotation,10,20-25*rotation);
            for(int mode=0;mode<2;++mode) {
                float frame_lerp=mode?1:cl.lerpfrac;
                test_lerpmodels=mode?"0":"1";
                for(int axis=0;axis<3;++axis) {
                    local[axis]=m->points[oldframe][axis]*(1-frame_lerp)+m->points[frame][axis]*frame_lerp;
                    angles[axis]=cl_entities[2].prev.angles[axis]+cl.lerpfrac*(cl_entities[2].current.angles[axis]-cl_entities[2].prev.angles[axis]);
                }
                angles[YAW]=350+20*cl.lerpfrac; /* shortest wrap, independently specified */
                AliasMatrixPoint(angles,local,expected);
                assert(CL_GetThirdPersonMuzzle(2,event,position,f,r,u));
                for(int axis=0;axis<3;++axis) {
                    expected[axis]+=cl_entities[2].prev.origin[axis]+cl.lerpfrac*(cl_entities[2].current.origin[axis]-cl_entities[2].prev.origin[axis]);
                    assert(fabsf(position[axis]-expected[axis])<.0002f);
                }
                ++checks;
            }
        }
    }
    test_lerpmodels="1";
    printf("PASS muzzle attachment matrix: %u poses across all models/frames, pitch/roll/yaw wrap and interpolation off\n",checks);
}

static void TestAttachedPlayerMuzzleFlashes(void)
{
    static const struct { int event; const char *model; } weapons[] = {
        {MZ_BLASTER,"w_blaster.md2"}, {MZ_SHOTGUN,"w_shotgun.md2"},
        {MZ_SHOTGUN2,"w_shotgun.md2"}, {MZ_SSHOTGUN,"w_sshotgun.md2"},
        {MZ_MACHINEGUN,"w_machinegun.md2"}, {MZ_ETF_RIFLE,"w_machinegun.md2"},
        {MZ_CHAINGUN1,"w_chaingun.md2"}, {MZ_CHAINGUN2,"w_chaingun.md2"},
        {MZ_CHAINGUN3,"w_chaingun.md2"}, {MZ_GRENADE,"w_glauncher.md2"},
        {MZ_ROCKET,"w_rlauncher.md2"}, {MZ_HYPERBLASTER,"w_hyperblaster.md2"},
        {MZ_RAILGUN,"w_railgun.md2"}, {MZ_BFG,"w_bfg.md2"}
    };
    byte data[8];
    vec3_t expected, forward, right, up;
    cvar_t legacy_height = {.value=123}, legacy_crouch = {.value=77};
    cvar_t legacy_lag = {.value=1};
    extern cvar_t *cl_mflash_thirdperson_up, *cl_mflash_thirdperson_crouch_down;
    extern cvar_t *cl_mflash_thirdperson_model_lag_comp;
    cl_mflash_thirdperson_up=&legacy_height;
    cl_mflash_thirdperson_crouch_down=&legacy_crouch;
    cl_mflash_thirdperson_model_lag_comp=&legacy_lag;
    for (unsigned w=0;w<sizeof(weapons)/sizeof(*weapons);++w) {
        centity_t *shooter;
        explosion_t saved;
        uint64_t updates;
        unsigned rng;
        muzzle_flash_config_t *cfg;
        ResetEffects(); ss_state.session_active=false;
        cl_entities=test_entities[0]; cl_numentities=16;
        memset(test_entities,0,sizeof(test_entities));
        cl.frame.serverframe=5; cl.frame.servertime=1050; cl.lerpfrac=.35f;
        cl.playernum=0; cl_vwep=&one;
        num_cl_weaponmodels=3;
        strcpy(cl_weaponmodels[0],"weapon.md2");
        strcpy(cl_weaponmodels[1],weapons[w].model);
        strcpy(cl_weaponmodels[2],"w_shotgun.md2");
        cl.clientinfo[0].weaponmodel[0]=(struct model_s *)(uintptr_t)1;
        cl.clientinfo[0].weaponmodel[1]=(struct model_s *)(uintptr_t)1;
        cl.clientinfo[0].weaponmodel[2]=(struct model_s *)(uintptr_t)1;
        shooter=&cl_entities[2]; shooter->serverframe=5;
        shooter->current.number=2;
        shooter->current.modelindex=shooter->current.modelindex2=255;
        shooter->current.skinnum=1<<PP_PLAYER_SKINNUM_WEAPON_SHIFT;
        shooter->prev.frame=169; shooter->current.frame=170; /* crouched firing */
        VectorSet(shooter->prev.origin,20,30,40);
        VectorSet(shooter->current.origin,70,10,60);
        VectorSet(shooter->prev.angles,20,350,7);
        VectorSet(shooter->current.angles,30,10,-9);
        cfg=CL_GetMuzzleFlashConfig(weapons[w].event,true);
        memset(cfg,0,sizeof(*cfg));cfg->enabled=true;cfg->scale=2;cfg->duration_ms=50;
        cfg->forward=200;cfg->right=300;cfg->up=400;cfg->velocity_scale=99;
        strcpy(cfg->image,"sprites/muzzleFlashSmall.png");
        assert(CL_GetThirdPersonMuzzle(2,weapons[w].event,expected,forward,right,up));
        SZ_Init(&net_message,data,sizeof(data));
        MSG_WriteShort(&net_message,2);MSG_WriteByte(&net_message,weapons[w].event);
        MSG_BeginReading(&net_message);CL_AddMuzzleFlash();
        assert(cl_explosions[0].muzzle_attached && cl_explosions[0].muzzle_entity==2);
        for(int axis=0;axis<3;++axis) {
            assert(fabsf(cl_explosions[0].ent.origin[axis]-expected[axis])<.001f);
            assert(fabsf(cl_dlights[0].origin[axis]-expected[axis])<.001f);
            assert(cl_explosions[0].velocity[axis]==0);
        }
        cl.time+=25;CL_PrepareTEnts();
        saved=cl_explosions[0];updates=cl_effect_stats.sprite_updates;rng=random_calls;
        test_entities[1][2]=test_entities[0][2];
        test_entities[1][2].current.origin[0]+=100;
        test_entities[1][2].current.frame=171;
        /* Observer order must not affect the other view or mutate shared state. */
        for(int pass=0;pass<4;++pass) {
            int observer=pass==0||pass==3?1:0;
            cl_entities=test_entities[observer];cl.lerpfrac=observer?.8f:.35f;
            assert(CL_GetThirdPersonMuzzle(2,weapons[w].event,expected,forward,right,up));
            ResetOutput();CL_AddTEnts();assert(submitted_entities==1);
            for(int axis=0;axis<3;++axis)
                assert(fabsf(entity_submissions[0].origin[axis]-expected[axis])<.001f);
            assert(!memcmp(&saved,&cl_explosions[0],sizeof(saved)));
            assert(cl_effect_stats.sprite_updates==updates && random_calls==rng);
        }
        /* An event parsed before its snapshot can attach once the pose arrives. */
        cl_explosions[0].muzzle_attached=false;
        ResetOutput();CL_AddTEnts();assert(submitted_entities==1);
        for(int axis=0;axis<3;++axis)
            assert(fabsf(entity_submissions[0].origin[axis]-expected[axis])<.001f);
        cl_explosions[0]=saved;
        cl_entities[2].serverframe=4;ResetOutput();CL_AddTEnts();assert(!submitted_entities);
        cl_entities[2].serverframe=5;
        cl_entities[2].current.modelindex=0;ResetOutput();CL_AddTEnts();assert(!submitted_entities);
        cl_entities[2].current.modelindex=255;
        cl_entities[2].current.skinnum=2<<PP_PLAYER_SKINNUM_WEAPON_SHIFT;
        ResetOutput();CL_AddTEnts();assert(!submitted_entities);
        cl_entities[2].current.skinnum=1<<PP_PLAYER_SKINNUM_WEAPON_SHIFT;
        cl.time+=25;CL_PrepareTEnts();ResetOutput();CL_AddTEnts();assert(!submitted_entities);
    }
    cl_mflash_thirdperson_up=&zero;cl_mflash_thirdperson_crouch_down=&zero;
    cl_mflash_thirdperson_model_lag_comp=&zero;
    puts("PASS attached player muzzle flashes: all weapon events, live model pose, observer histories, no legacy lift/lag/drift, expiration and removed/switched shooters");
}

static entity_state_t test_streams[4][MAX_PARSE_ENTITIES];

static void TestSoldierPlayerReports(void)
{
    static const int flashes[3][8]={
        {MZ2_SOLDIER_BLASTER_1,MZ2_SOLDIER_BLASTER_2,MZ2_SOLDIER_BLASTER_3,MZ2_SOLDIER_BLASTER_4,
         MZ2_SOLDIER_BLASTER_5,MZ2_SOLDIER_BLASTER_6,MZ2_SOLDIER_BLASTER_7,MZ2_SOLDIER_BLASTER_8},
        {MZ2_SOLDIER_SHOTGUN_1,MZ2_SOLDIER_SHOTGUN_2,MZ2_SOLDIER_SHOTGUN_3,MZ2_SOLDIER_SHOTGUN_4,
         MZ2_SOLDIER_SHOTGUN_5,MZ2_SOLDIER_SHOTGUN_6,MZ2_SOLDIER_SHOTGUN_7,MZ2_SOLDIER_SHOTGUN_8},
        {MZ2_SOLDIER_MACHINEGUN_1,MZ2_SOLDIER_MACHINEGUN_2,MZ2_SOLDIER_MACHINEGUN_3,MZ2_SOLDIER_MACHINEGUN_4,
         MZ2_SOLDIER_MACHINEGUN_5,MZ2_SOLDIER_MACHINEGUN_6,MZ2_SOLDIER_MACHINEGUN_7,MZ2_SOLDIER_MACHINEGUN_8}
    };
    byte data[8];
    char expected[MAX_QPATH];
    unsigned int variants[3]={0,0,0};
    int kind,i,seed,variant,count;
    for(kind=0;kind<3;++kind) for(i=0;i<8;++i) for(seed=1;seed<=32;++seed) {
        const float *offset=monster_flash_offset[flashes[kind][i]];
        ResetEffects(); random_state=(unsigned int)seed*0x9e3779b9u;
        CL_RegisterTEntModels();
        cl_entities=test_entities[0]; cl_numentities=16;
        memset(test_entities[0],0,sizeof(test_entities[0]));
        VectorSet(cl_entities[2].current.origin,120,40,36);
        cl_entities[2].current.angles[YAW]=90;
        SZ_Init(&net_message,data,sizeof(data));
        MSG_WriteShort(&net_message,2); MSG_WriteByte(&net_message,flashes[kind][i]);
        MSG_BeginReading(&net_message); CL_AddMuzzleFlash2();
        assert(net_message.readcount==3 && sound_calls==1);
        count=kind==0?4:kind==1?1:5;
        for(variant=1;variant<=count;++variant) {
            if(kind==0) snprintf(expected,sizeof(expected),"soldier/player/pistol%d.wav",variant);
            else if(kind==1) strcpy(expected,"soldier/player/shotgf1b.wav");
            else snprintf(expected,sizeof(expected),"soldier/player/machgf%db.wav",variant);
            if(!strcmp(last_sound_name,expected)) break;
        }
        assert(variant<=count);
        variants[kind]|=1u<<(variant-1);
        assert(cl_dlights[0].key==2 && cl_dlights[0].radius>=200 && cl_dlights[0].die==cl.time);
        assert(cl_dlights[0].color[0]==1 && cl_dlights[0].color[1]==1 && cl_dlights[0].color[2]==0);
        assert(fabsf(cl_dlights[0].origin[0]-(120+offset[1]))<0.001f);
        assert(fabsf(cl_dlights[0].origin[1]-(40+offset[0]))<0.001f);
        assert(fabsf(cl_dlights[0].origin[2]-(36+offset[2]))<0.001f);
        assert(cl_effect_stats.particles_created==(kind==2?40u:0u));
        assert(cl_explosions[0].type!=ex_free && cl_explosions[1].type!=ex_free);
    }
    assert(variants[0]==15 && variants[1]==1 && variants[2]==31);
    ResetEffects();
    SZ_Init(&net_message,data,sizeof(data));
    MSG_WriteShort(&net_message,2); MSG_WriteByte(&net_message,MZ2_TURRET_BLASTER);
    MSG_BeginReading(&net_message); CL_AddMuzzleFlash2();
    assert(sound_calls==1 && !strcmp(last_sound_name,"soldier/solatck2.wav"));
    puts("PASS soldier player reports: all 24 light/shotgun/SS flashes and randomized reports; turret report unchanged");
}

static void TestHeavyMuzzleFlash(void)
{
    byte data[8];
    cdlight_t lights[MAX_DLIGHTS];
    unsigned int rng;
    const float *offset=monster_flash_offset[MZ2_SOLDIER_HEAVY];
    ResetEffects();
    cl_entities=test_entities[0]; cl_numentities=16;
    memset(test_entities[0],0,sizeof(test_entities[0]));
    VectorSet(cl_entities[2].current.origin,120,40,36);
    cl_entities[2].current.angles[YAW]=90;
    SZ_Init(&net_message,data,sizeof(data));
    MSG_WriteShort(&net_message,2); MSG_WriteByte(&net_message,MZ2_SOLDIER_HEAVY);
    MSG_BeginReading(&net_message); CL_AddMuzzleFlash2();
    assert(net_message.readcount==3 && MZ2_SOLDIER_HEAVY==211);
    assert(cl_dlights[0].key==2 && cl_dlights[0].radius>=200);
    assert(fabsf(cl_dlights[0].origin[0]-(120+offset[1]))<0.001f);
    assert(fabsf(cl_dlights[0].origin[1]-(40+offset[0]))<0.001f);
    assert(fabsf(cl_dlights[0].origin[2]-(36+offset[2]))<0.001f);
    assert(sound_calls==1 && !strncmp(last_sound_name,"soldier/player/m60",18));
    assert(last_sound_name[18]>='1' && last_sound_name[18]<='5');
    assert(!strcmp(last_sound_name+19,".wav"));
    assert(cl_effect_stats.particles_created==0);
    SZ_Clear(&net_message);
    MSG_WriteShort(&net_message,2); MSG_WriteByte(&net_message,MZ2_SOLDIER_ROCKET);
    MSG_BeginReading(&net_message); CL_AddMuzzleFlash2();
    offset=monster_flash_offset[MZ2_SOLDIER_ROCKET];
    assert(MZ2_SOLDIER_ROCKET==212 && sound_calls==2);
    assert(!strcmp(last_sound_name,"soldier/player/rocklf1a.wav"));
    assert(fabsf(cl_dlights[0].origin[0]-(120+offset[1]))<0.001f);
    assert(fabsf(cl_dlights[0].origin[1]-(40+offset[0]))<0.001f);
    assert(fabsf(cl_dlights[0].origin[2]-(36+offset[2]))<0.001f);
    assert(cl_dlights[0].color[1]==0.5f && cl_effect_stats.particles_created==0);
    memcpy(lights,cl_dlights,sizeof(lights)); rng=random_calls;
    SZ_Clear(&net_message);
    MSG_WriteShort(&net_message,2); MSG_WriteByte(&net_message,MZ2_HELICOPTER_ROCKET_R+1);
    MSG_BeginReading(&net_message); CL_AddMuzzleFlash2();
    assert(net_message.readcount==3 && sound_calls==2 && random_calls==rng);
    assert(!memcmp(lights,cl_dlights,sizeof(lights)) && cl_effect_stats.particles_created==0);
    puts("PASS soldier muzzle flashes: M60/rocket barrel offsets and reports, no particle flood; invalid flash ignored");
}

static void TestHelicopterMuzzleFlash(void)
{
    byte data[8];
    const int flashes[]={MZ2_HELICOPTER_MACHINEGUN_L,MZ2_HELICOPTER_MACHINEGUN_R,
        MZ2_HELICOPTER_ROCKET_L,MZ2_HELICOPTER_ROCKET_R};
    const vec3_t local[]={{64,24,-10},{64,-24,-10},{30,46,-2},{30,-46,-2}};
    const vec3_t poses[]={{0,90,0},{12,135,17}};
    vec3_t forward,right,up,expected;
    int i,p,axis;
    for(p=0;p<2;++p) for(i=0;i<4;++i) {
        ResetEffects();
        cl_entities=test_entities[0]; cl_numentities=16;
        memset(test_entities[0],0,sizeof(test_entities[0]));
        VectorSet(cl_entities[2].current.origin,120,40,200);
        VectorCopy(poses[p],cl_entities[2].current.angles);
        SZ_Init(&net_message,data,sizeof(data));
        MSG_WriteShort(&net_message,2); MSG_WriteByte(&net_message,flashes[i]);
        MSG_BeginReading(&net_message); CL_AddMuzzleFlash2();
        assert(net_message.readcount==3 && sound_calls==1);
        AngleVectors(poses[p],forward,right,up);
        VectorMA(cl_entities[2].current.origin,local[i][0],forward,expected);
        VectorMA(expected,-local[i][1],right,expected);
        VectorMA(expected,local[i][2],up,expected);
        for(axis=0;axis<3;++axis)
            assert(fabsf(cl_dlights[0].origin[axis]-expected[axis])<0.001f);
        assert(!strcmp(last_sound_name,i<2?"infantry/infatck1.wav":"weapons/rocklf1a.wav"));
        assert(cl_dlights[0].color[1]==(i<2?1.0f:0.5f));
    }
    puts("PASS helicopter muzzle flashes: both guns and rocket pods match rotated model endpoints and play reports");
}

static void SetupProjectileTrail(int view, int number, float lerp, unsigned effects)
{
    centity_t *c=&test_entities[view][number];
    memset(c,0,sizeof(*c)); c->current.number=number; c->current.modelindex=1;
    c->current.effects=effects; c->current.origin[0]=100;
    c->prev=c->current; c->prev.origin[0]=80;
    c->serverframe=10; c->trailcount=1024; c->lerp_origin[0]=80;
    test_streams[view][0]=c->current;
    cl_entities=test_entities[view]; cl_numentities=16;
    cl_entity_parse_stream=test_streams[view]; cl.playernum=view; cl.lerpfrac=lerp;
    cl.frame.num_entities=1; cl.frame.parse_entities=0;
    CL_QueueEntityEffects(&cl.frame,view);
}

static void SetupTrail(int view, int number, float lerp)
{ SetupProjectileTrail(view,number,lerp,EF_ROCKET); }

static void TestFriendlyDropshipPresentation(void)
{
    const char *backends[]={"gl1","gl3","soft"};
    const char *bodies[]={"models/monsters/boss2/tris.md2","models/vehicles/platoon_dropship/body.md2","models/monsters/plastic_boss/body.md2"};
    const char *rotors[]={"models/monsters/boss2/propeller.md2","models/vehicles/platoon_dropship/main_rotor.md2","models/monsters/plastic_boss/main_rotor.md2"};
    for(int backend=0;backend<3;++backend) for(int view=0;view<4;++view) for(int moving=0;moving<2;++moving) {
        entity_t legacy[2];
        for(int family=0;family<3;++family) {
            ResetEffects();ss_state.session_active=false;renderer.string=(char *)backends[backend];
            strcpy(cl.configstrings[CS_MODELS+1],bodies[family]);
            strcpy(cl.configstrings[CS_MODELS+2],rotors[family]);
            cl.model_draw[1]=(struct model_s *)(uintptr_t)1;cl.model_draw[2]=(struct model_s *)(uintptr_t)2;
            centity_t *cent=&test_entities[view][10];memset(cent,0,sizeof(*cent));
            cent->current.number=10;cent->current.modelindex=1;cent->current.modelindex2=2;
            cent->current.frame=62;
            cent->current.renderfx=RF_FRAMELERP|RF_PP_FRIENDLY_COLOR;
            VectorSet(cent->current.origin,140,36,56);VectorSet(cent->current.old_origin,900,800,700);
            VectorSet(cent->current.angles,10,10,14);cent->prev=cent->current;
            if(moving)VectorSet(cent->prev.origin,100,20,40);
            VectorSet(cent->prev.angles,-8,350,-12);cent->serverframe=10;
            test_streams[view][0]=cent->current;
            cl_entities=test_entities[view];cl_numentities=16;cl_entity_parse_stream=test_streams[view];
            cl.playernum=view;cl.lerpfrac=.5f;cl.frame.num_entities=1;cl.frame.parse_entities=0;
            CL_AddPacketEntities(&cl.frame);
            assert(submitted_entities==2&&entity_submissions[0].model==cl.model_draw[1]&&entity_submissions[1].model==cl.model_draw[2]);
            entity_t *body=&entity_submissions[0],*rotor=&entity_submissions[1];
            assert(body->frame==0&&body->oldframe==0&&body->backlerp==0);
            float bob=moving?0.f:sinf(cl.time*.0125f+10*.37f)*2.f;
            assert(fabsf(body->origin[0]-(moving?120.f:140.f))<.001f);
            assert(fabsf(body->origin[1]-(moving?28.f:36.f))<.001f);
            assert(fabsf(body->origin[2]-(moving?48.f:56.f)-bob)<.001f);
            assert(rotor->frame==0&&rotor->oldframe==0&&rotor->backlerp==0);
            if(!family)memcpy(legacy,entity_submissions,sizeof(legacy));
            else for(int part=0;part<2;++part) {
                for(int axis=0;axis<3;++axis) {
                    assert(fabsf(entity_submissions[part].origin[axis]-legacy[part].origin[axis])<.001f);
                    assert(fabsf(entity_submissions[part].angles[axis]-legacy[part].angles[axis])<.001f);
                    assert(fabsf(entity_submissions[part].oldorigin[axis]-legacy[part].oldorigin[axis])<.001f);
                }
                assert(entity_submissions[part].flags==legacy[part].flags);
            }
        }
    }
    renderer.string="gl1";
    puts("PASS friendly dropship presentation: dedicated body/rotor retain legacy snapshot interpolation, bob, local spin and GL1/GL3/software attachment in four views");
}

static void TestProjectilePresentation(void)
{
    const char *paths[]={"models/objects/rocket/tris.md2","models/objects/grenade/tris.md2",
        "models/objects/grenade2/tris.md2","models/objects/grenade/tris.md2"};
    for(int kind=0;kind<4;++kind) for(int views=1;views<=4;views+=3) {
        ResetEffects();ss_state.session_active=false;
        strcpy(cl.configstrings[CS_MODELS+1],paths[kind]);
        cl.model_draw[1]=(struct model_s *)(uintptr_t)1;
        assert(CL_BeginSharedEffects());
        for(int view=0;view<views;++view)
            SetupProjectileTrail(view,10,.5f,kind?EF_GRENADE:EF_ROCKET);
        CL_EmitQueuedEntityEffects();CL_PrepareParticles();
        assert(cl_effect_stats.particles_created>0&&cl_effect_stats.entity_effect_evaluations==1);
        assert(cl_effect_stats.entity_effect_reuses==(unsigned)(views-1));
        for(int view=0;view<views;++view) {
            ResetOutput();cl_effect_render_slot=view;
            cl_entities=test_entities[view];cl_entity_parse_stream=test_streams[view];cl.playernum=view;
            CL_AddPacketEntities(&cl.frame);CL_AddParticles();
            assert(submitted_entities==1&&submitted_particles>0);
            assert(entity_submissions[0].model==cl.model_draw[1]&&entity_submissions[0].frame==0);
            assert(submitted_lights==(kind?0u:1u));
            if(!kind) {
                assert(last_light_intensity==200.f&&last_light_color[0]==1.f&&
                    last_light_color[1]==1.f&&last_light_color[2]==0.f);
            }
        }
    }
    puts("PASS flying projectile presentation: static rocket/GL/hand-grenade/mortar models, smoke, rocket light, shared single/four-view trails");
}

static void TestTrailInputs(void)
{
    uint64_t single;
    unsigned int rng;
    ResetEffects(); ss_state.session_active=false;
    assert(CL_BeginSharedEffects()); SetupTrail(0,10,0.5f); CL_EmitQueuedEntityEffects(); single=cl_effect_stats.particles_created;
    assert(single>0);
    ResetEffects(); assert(CL_BeginSharedEffects());
    SetupTrail(1,10,0.5f); SetupTrail(0,10,0.5f); CL_EmitQueuedEntityEffects(); CL_PrepareParticles();
    assert(cl_effect_stats.particles_created==single && cl_effect_stats.entity_effect_evaluations==1 && cl_effect_stats.entity_effect_reuses==1);
    assert(!memcmp(&test_entities[0][10],&test_entities[1][10],sizeof(centity_t)));
    rng=random_calls;
    { centity_t saved=test_entities[0][10];
      cl.model_draw[1]=(struct model_s *)(uintptr_t)1;
      cl_effect_render_slot=1; CL_AddPacketEntities(&cl.frame); CL_AddTEnts(); CL_AddParticles(); assert(submitted_particles==single);
      ResetOutput(); cl_effect_render_slot=0; CL_AddPacketEntities(&cl.frame); CL_AddTEnts(); CL_AddParticles();
      assert(submitted_particles==single && random_calls==rng && !memcmp(&saved,&test_entities[0][10],sizeof(saved)));
      assert(cl_effect_stats.particles_created==single); }
    ResetEffects(); assert(CL_BeginSharedEffects());
    SetupTrail(0,10,0.25f); SetupTrail(1,10,0.75f); CL_EmitQueuedEntityEffects(); CL_PrepareParticles();
    assert(cl_effect_stats.entity_effect_evaluations==2 && cl_effect_stats.entity_effect_reuses==0);
    cl_effect_render_slot=0; CL_AddParticles(); assert(submitted_particles>0 && submitted_particles<cl_effect_stats.prepared_particles);
    ResetOutput(); cl_effect_render_slot=1; CL_AddParticles(); assert(submitted_particles>0 && submitted_particles<cl_effect_stats.prepared_particles);
    ResetEffects(); assert(CL_BeginSharedEffects());
    SetupTrail(0,10,0.5f); SetupTrail(1,11,0.5f); CL_EmitQueuedEntityEffects(); CL_PrepareParticles();
    assert(cl_effect_stats.entity_effect_evaluations==2 && cl_effect_stats.entity_effect_reuses==0);
    cl_effect_render_slot=0; CL_AddParticles(); assert(submitted_particles==cl_effect_stats.prepared_particles);
    printf("PASS trails: one/two equivalent views both create %llu particles; differing interpolation and disjoint snapshot union retained\n",(unsigned long long)single);
}

static void TestSpritePreparation(void)
{
    explosion_t *e; unsigned int rng; uint64_t updates;
    ResetEffects(); ss_state.session_active=false;
    e=CL_AllocExplosion(); e->type=ex_mflash_billboard; e->duration=1000; e->start=cl.time;
    e->ent.oldorigin[0]=10; e->velocity[0]=20; e->effect_only_slot=2;
    cl.time+=100; CL_PrepareTEnts(); assert(fabsf(e->ent.origin[0]-12)<0.001f);
    updates=cl_effect_stats.sprite_updates; rng=random_calls;
    cl_effect_render_slot=0; CL_AddTEnts(); assert(submitted_entities==0);
    cl_effect_render_slot=1; CL_AddTEnts(); assert(submitted_entities==1 && fabsf(entity_submissions[0].origin[0]-12)<0.001f);
    assert(cl_effect_stats.sprite_updates==updates && random_calls==rng);
    cl.time+=100; CL_PrepareTEnts(); assert(fabsf(e->ent.origin[0]-14)<0.001f);
    puts("PASS sprites: scoped submission, shared update once, immutable spawn origin prevents accumulated velocity drift");
}

static void TestBulletImpacts(void)
{
    const int types[] = {TE_GUNSHOT, TE_SHOTGUN, TE_BULLET_SPARKS, TE_BLOOD};
    const unsigned int particle_counts[] = {40, 20, 6, 60};
    vec3_t pos = {5, 6, 7}, normal = {0, 0, 1};
    byte buffer[64]; size_t i;
    struct model_s *smoke=(struct model_s *)(uintptr_t)2;
    struct model_s *flash=(struct model_s *)(uintptr_t)3;

    for (i=0; i<sizeof(types)/sizeof(types[0]); ++i) {
        ResetEffects();
        cl_mod_smoke_sprite=smoke; cl_mod_explosion_sprite=flash;
        SZ_Init(&net_message,buffer,sizeof(buffer));
        MSG_WriteByte(&net_message,types[i]); MSG_WritePos(&net_message,pos); MSG_WriteDir(&net_message,normal);
        MSG_BeginReading(&net_message); CL_ParseTEnt();
        assert(cl_effect_stats.particles_created==particle_counts[i]);
        if (types[i]==TE_BLOOD) {
            assert(cl_explosions[0].type==ex_free);
            continue;
        }
        assert(cl_explosions[0].type==ex_impact_sprite && cl_explosions[0].ent.model==smoke);
        assert(cl_explosions[1].type==ex_impact_sprite && cl_explosions[1].ent.model==flash);
        assert(cl_explosions[0].ent.skinnum==-24 && cl_explosions[1].ent.skinnum==-16);
        CL_PrepareTEnts(); CL_AddTEnts(); assert(submitted_entities==2);
        cl.time+=100; ResetOutput(); CL_PrepareTEnts(); CL_AddTEnts();
        assert(submitted_entities==1 && entity_submissions[0].model==smoke);
        cl.time+=201; ResetOutput(); CL_PrepareTEnts(); CL_AddTEnts(); assert(submitted_entities==0);
    }
    /* Existing stock impact models still take precedence when installed. */
    ResetEffects(); cl_mod_smoke=smoke; cl_mod_flash=flash;
    cl_mod_smoke_sprite=flash; cl_mod_explosion_sprite=smoke;
    CL_SmokeAndFlash(pos);
    assert(cl_explosions[0].type==ex_misc && cl_explosions[0].ent.model==smoke);
    assert(cl_explosions[1].type==ex_flash && cl_explosions[1].ent.model==flash);
    ResetEffects(); CL_SmokeAndFlash(pos);
    assert(cl_explosions[0].type==ex_free); /* no missing-model submissions */
    puts("PASS bullet impacts: wall, shotgun, sparks and blood particles; standalone sprite fallback and stock model preference");
}

static void TestBeamViews(void)
{
    vec3_t offset={0,0,0}, origin;
    unsigned int rng, owner_particles;
    uint64_t created;
    ResetEffects(); ResetRecipients();
    cl_effect_render_slot=1; cl.playernum=1; cl.refdef.vieworg[0]=100;
    cl.frame.serverframe=10; cl.frame.playerstate.gunoffset[0]=10;
    ss_state.slots[1].frames[9].serverframe=9;
    ss_state.slots[1].frames[9].valid=true;
    ss_state.slots[1].frames[9].playerstate.gunoffset[0]=0;
    cl.frames[9].serverframe=9; cl.frames[9].valid=true;
    cl.frames[9].playerstate.gunoffset[0]=1000;
    AngleVectors(vec3_origin,cl.v_forward,cl.v_right,cl.v_up);
    AdjustToWeapon(offset,1,origin);
    assert(fabsf(origin[0]-105)<0.001f);
    cl_heatbeams[0].model=(struct model_s *)(uintptr_t)1;
    cl_heatbeams[0].entity=2; cl_heatbeams[0].endtime=cl.time+100;
    cl_heatbeams[0].start[0]=100; cl_heatbeams[0].end[0]=200;
    assert(CL_BeginSharedEffects()); CL_PrepareViewBeamParticles(); CL_PrepareTEnts(); CL_PrepareParticles();
    rng=random_calls; created=cl_effect_stats.particles_created;
    CL_AddHeatBeams(); CL_AddParticles(); owner_particles=submitted_particles; assert(owner_particles>0);
    ResetOutput(); cl_effect_render_slot=0; cl.playernum=0; CL_AddHeatBeams(); CL_AddParticles();
    assert(submitted_particles>0 && owner_particles+submitted_particles==cl_effect_stats.prepared_particles);
    assert(random_calls==rng && cl_effect_stats.particles_created==created);
    puts("PASS beams: secondary snapshot history, owner-scoped rings, one shared world shell, read-only per-view submission");
}

static void WriteEmptyFrame(sizebuf_t *msg,int frame,int delta)
{
    SZ_Clear(msg);
    MSG_WriteLong(msg,frame); MSG_WriteLong(msg,delta); MSG_WriteByte(msg,0);
    MSG_WriteByte(msg,1); MSG_WriteByte(msg,0xaa);
    MSG_WriteByte(msg,svc_playerinfo); MSG_WriteShort(msg,PS_FOV); MSG_WriteByte(msg,90);
    MSG_WriteLong(msg,0); MSG_WriteByte(msg,svc_packetentities); MSG_WriteShort(msg,0);
    MSG_BeginReading(msg);
}

static void TestMapTransition(void)
{
    static centity_t entities[32];
    ss_local_player_t *slot;
    const player_state_t *ps=NULL;
    byte bytes[256]; sizebuf_t msg;
    ResetEffects(); ResetRecipients(); slot=&ss_state.slots[1];
    SZ_Init(&slot->netchan.message,slot->netchan.message_buf,sizeof(slot->netchan.message_buf));
    SZ_Init(&msg,bytes,sizeof(bytes));
    slot->entities=entities; slot->entity_count=32;
    cl.servercount=slot->servercount=100;
    slot->snapshot_valid=true; slot->frame.valid=true;
    assert(SS_GetSlotPlayerState(1,NULL,&ps) && ps==&slot->frame.playerstate);
    ++cl.servercount;
    assert(!SS_GetSlotPlayerState(1,NULL,&ps)); /* stale model indices cannot render */
    --cl.servercount;
    slot->snapshot_valid=false;
    assert(!SS_GetSlotPlayerState(1,NULL,&ps)); /* no server-playerstate/old-entity mix */
    slot->snapshot_valid=true;
    slot->frames[8].valid=true; slot->frames[8].serverframe=8;
    slot->parse_entities[37].modelindex=5; slot->parse_entities_num=38;
    slot->entities[9].current.modelindex=5;
    slot->inventory[7]=9; strcpy(slot->layout,"old-map");
    strcpy(slot->screen_image.pic,"old-map-image"); slot->screen_image.endtime=5000;
    slot->cmds[5].forwardmove=123; slot->muzzle_flash_seq=44; slot->viewmodel_valid=true;
    slot->axis_left_x=12345; slot->attack_down=true;
    transmit_calls=0; test_loopback_slot=0;
    SS_HandleStuffText(slot,"changing\n");
    assert(!slot->snapshot_valid && slot->servercount==0 && slot->connection_state==ca_connected);
    assert(!slot->frame.valid && !slot->frames[8].valid && !slot->parse_entities_num);
    assert(!slot->parse_entities[37].modelindex && !slot->entities[9].current.modelindex);
    assert(!slot->inventory[7] && !slot->layout[0] && !slot->cmds[5].forwardmove);
    assert(!slot->screen_image.pic[0] && !slot->screen_image.endtime);
    assert(!slot->muzzle_flash_seq && !slot->viewmodel_valid && transmit_calls==0);
    assert(slot->axis_left_x==12345 && slot->attack_down); /* held input survives */
    strcpy(slot->screen_image.pic,"old-map-image"); slot->screen_image.endtime=5000;
    SS_HandleStuffText(slot,"reconnect\n");
    assert(!slot->screen_image.pic[0] && !slot->screen_image.endtime);
    assert(transmit_calls==1 && transmitted_slot==1 && test_loopback_slot==0);
    assert(transmitted_length==5 && transmitted_command[0]==clc_stringcmd && !strcmp((char *)transmitted_command+1,"new"));
    /* Even serverdata without a preceding changing command clears all delta
     * history, so a recycled server tick cannot refer to the old map. */
    slot->frames[8].valid=true; slot->frames[8].serverframe=8;
    strcpy(slot->screen_image.pic,"old-map-image"); slot->screen_image.endtime=5000;
    MSG_WriteLong(&msg,PROTOCOL_VERSION); MSG_WriteLong(&msg,101);
    MSG_WriteByte(&msg,0); MSG_WriteString(&msg,"baseq2");
    MSG_WriteShort(&msg,1); MSG_WriteString(&msg,"new map");
    MSG_BeginReading(&msg); SS_ParseServerData(slot,&msg);
    assert(slot->servercount==101 && slot->playernum==1 && !slot->frames[8].valid);
    assert(!slot->screen_image.pic[0] && !slot->screen_image.endtime);
    assert(!slot->snapshot_valid && slot->connection_state==ca_connected);
    SS_HandleStuffText(slot,"precache 101\n");
    assert(transmit_calls==2 && !strcmp((char *)transmitted_command+1,"begin 101"));
    assert(slot->connection_state==ca_active && !SS_GetSlotPlayerState(1,NULL,&ps));
    WriteEmptyFrame(&msg,9,8); SS_ParseFrame(slot,&msg);
    assert(!slot->snapshot_valid && !SS_GetSlotPlayerState(1,NULL,&ps));
    WriteEmptyFrame(&msg,1,-1); SS_ParseFrame(slot,&msg);
    assert(slot->snapshot_valid && slot->frame.valid && slot->frame.areabits[0]==0xaa);
    assert(!SS_GetSlotPlayerState(1,NULL,&ps)); /* primary has not registered new map */
    cl.servercount=101;
    assert(SS_GetSlotPlayerState(1,NULL,&ps) && ps->fov==90);
    slot->connection_state=ca_connected;
    assert(!SS_GetSlotPlayerState(1,NULL,&ps));
    puts("PASS map changes: secondary changing/reconnect handshake, full history reset, held input preserved, generation/connection/snapshot presentation gates");
}

int main(void)
{
    Swap_Init();
    TestOccurrences(); TestParticleFrame(); TestAuthoredWeaponADS(); TestPlayerMuzzleFlashes(); TestScopedModelMuzzleFlashes(); TestFlamethrowerAndMortarPresentation(); TestSniperSplitZoom(); TestGrenadeLauncherAndHandGrenadeFlashes(); TestSplitMuzzleScopes(); TestMuzzleModelMatrix(); TestAttachedPlayerMuzzleFlashes(); TestSoldierPlayerReports(); TestHeavyMuzzleFlash(); TestHelicopterMuzzleFlash(); TestFriendlyDropshipPresentation(); TestProjectilePresentation(); TestTrailInputs(); TestSpritePreparation(); TestBulletImpacts(); TestBeamViews(); TestMapTransition();
    puts("All shared-effect production regressions passed.");
    return 0;
}
