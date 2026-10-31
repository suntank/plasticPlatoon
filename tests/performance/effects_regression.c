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

client_state_t cl;
client_static_t cls;
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
cvar_t *cl_paused = &zero, *cl_r1q2_lightstyle = &zero;
cvar_t *cl_limitsparksounds = &zero, *cl_laseralpha = &one;
cvar_t *maxclients = &three, *hand = &zero, *cl_vwep = &one;
static unsigned int random_state = 1, random_calls;
static unsigned int sound_calls, submitted_particles, submitted_entities, submitted_lights;
static particle_t submissions[MAX_PARTICLES];
static entity_t entity_submissions[MAX_ENTITIES];
static byte test_pvs = 0xff;
static qboolean connected_areas[4] = {true, true, true, true};
static int test_loopback_slot, transmitted_slot;
static unsigned int transmit_calls;
static byte transmitted_command[MAX_MSGLEN];
static int transmitted_length;

int randk(void) { ++random_calls; random_state = random_state * 1664525u + 1013904223u; return (int)(random_state & 0x7fffffffu); }
float frandk(void) { return (randk() & 32767) * (1.0f / 32767.0f); }
float crandk(void) { return (randk() & 32767) * (2.0f / 32767.0f) - 1.0f; }
void Com_Error(int code, const char *fmt, ...) { va_list args; (void)code; va_start(args,fmt); vfprintf(stderr,fmt,args); va_end(args); abort(); }
void Com_Printf(const char *fmt, ...) { (void)fmt; }
void Com_DPrintf(const char *fmt, ...) { (void)fmt; }
void V_AddParticle(vec3_t origin, unsigned int color, float alpha) { particle_t *p = &submissions[submitted_particles++]; assert(submitted_particles <= MAX_PARTICLES); VectorCopy(origin,p->origin); p->color=color; p->alpha=alpha; }
void V_AddEntity(entity_t *ent) { assert(submitted_entities < MAX_ENTITIES); entity_submissions[submitted_entities++]=*ent; }
void V_AddLight(vec3_t org, float intensity, float r, float g, float b) { (void)org;(void)intensity;(void)r;(void)g;(void)b; ++submitted_lights; }
struct model_s *R_RegisterModel(const char *name) { (void)name; return (struct model_s *)(uintptr_t)1; }
struct image_s *R_RegisterSkin(const char *name) { (void)name; return (struct image_s *)(uintptr_t)1; }
struct sfx_s *S_RegisterSound(const char *name) { (void)name; return (struct sfx_s *)(uintptr_t)1; }
void S_StartSound(vec3_t org, int entnum, int channel, struct sfx_s *sfx, float volume, float attenuation, float offset) { (void)org;(void)entnum;(void)channel;(void)sfx;(void)volume;(void)attenuation;(void)offset; ++sound_calls; }
int CM_PointLeafnum(vec3_t p) { return (int)p[0]; }
int CM_LeafCluster(int leaf) { return leaf; }
int CM_LeafArea(int leaf) { return leaf; }
int CM_PointContents(vec3_t p, int headnode) { (void)p; (void)headnode; return 0; }
byte *CM_ClusterPVS(int cluster) { (void)cluster; return &test_pvs; }
byte *CM_ClusterPHS(int cluster) { (void)cluster; return &test_pvs; }
qboolean CM_AreasConnected(int a, int b) { (void)a; return connected_areas[b]; }
cvar_t *Cvar_Get(const char *name, const char *value, int flags) { (void)name;(void)value;(void)flags; return &zero; }
void *Z_Realloc(void *ptr,int size) { (void)ptr; (void)size; assert(!"fixture entity buffers are preallocated"); return NULL; }
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
    random_state=1; random_calls=sound_calls=0; ResetOutput();
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

static centity_t test_entities[2][16];
static entity_state_t test_streams[2][MAX_PARSE_ENTITIES];
static void SetupTrail(int view, int number, float lerp)
{
    centity_t *c=&test_entities[view][number];
    memset(c,0,sizeof(*c)); c->current.number=number; c->current.modelindex=1;
    c->current.effects=EF_ROCKET; c->current.origin[0]=100;
    c->prev=c->current; c->prev.origin[0]=80;
    c->serverframe=10; c->trailcount=1024; c->lerp_origin[0]=80;
    test_streams[view][0]=c->current;
    cl_entities=test_entities[view]; cl_numentities=16;
    cl_entity_parse_stream=test_streams[view]; cl.playernum=view; cl.lerpfrac=lerp;
    cl.frame.num_entities=1; cl.frame.parse_entities=0;
    CL_QueueEntityEffects(&cl.frame,view);
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
    slot->cmds[5].forwardmove=123; slot->muzzle_flash_seq=44; slot->viewmodel_valid=true;
    slot->axis_left_x=12345; slot->attack_down=true;
    transmit_calls=0; test_loopback_slot=0;
    SS_HandleStuffText(slot,"changing\n");
    assert(!slot->snapshot_valid && slot->servercount==0 && slot->connection_state==ca_connected);
    assert(!slot->frame.valid && !slot->frames[8].valid && !slot->parse_entities_num);
    assert(!slot->parse_entities[37].modelindex && !slot->entities[9].current.modelindex);
    assert(!slot->inventory[7] && !slot->layout[0] && !slot->cmds[5].forwardmove);
    assert(!slot->muzzle_flash_seq && !slot->viewmodel_valid && transmit_calls==0);
    assert(slot->axis_left_x==12345 && slot->attack_down); /* held input survives */
    SS_HandleStuffText(slot,"reconnect\n");
    assert(transmit_calls==1 && transmitted_slot==1 && test_loopback_slot==0);
    assert(transmitted_length==5 && transmitted_command[0]==clc_stringcmd && !strcmp((char *)transmitted_command+1,"new"));
    /* Even serverdata without a preceding changing command clears all delta
     * history, so a recycled server tick cannot refer to the old map. */
    slot->frames[8].valid=true; slot->frames[8].serverframe=8;
    MSG_WriteLong(&msg,PROTOCOL_VERSION); MSG_WriteLong(&msg,101);
    MSG_WriteByte(&msg,0); MSG_WriteString(&msg,"baseq2");
    MSG_WriteShort(&msg,1); MSG_WriteString(&msg,"new map");
    MSG_BeginReading(&msg); SS_ParseServerData(slot,&msg);
    assert(slot->servercount==101 && slot->playernum==1 && !slot->frames[8].valid);
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
    TestOccurrences(); TestParticleFrame(); TestTrailInputs(); TestSpritePreparation(); TestBeamViews(); TestMapTransition();
    puts("All shared-effect production regressions passed.");
    return 0;
}
