/* Exercise split-screen server delivery and guest sound/event parsing against
 * production code, reusing the existing isolated engine fixture. */
#define main shared_effect_fixture_main
#include "../performance/effects_regression.c"
#undef main

static void ResetAudioDelivery(void)
{
    int i;
    ResetEffects(); ResetRecipients();
    memset(ss_entity_event_frames, 0, sizeof(ss_entity_event_frames));
    cl.servercount=7;
    cl.sound_precache[7]=(struct sfx_s *)(uintptr_t)1;
    for(i=0;i<2;++i) {
        ss_state.slots[i].entities=test_entities[i];
        ss_state.slots[i].entity_count=16;
        ss_state.slots[i].servercount=7;
        ss_state.slots[i].snapshot_valid=true;
        memset(test_entities[i],0,sizeof(test_entities[i]));
    }
    cl_entities=test_entities[0]; cl_numentities=16;
}

static void SendTestSound(int channel, float attenuation)
{
    vec3_t origin={1,0,0};
    SV_StartSound(origin,&test_edicts[2],channel,7,0.75f,attenuation,0.02f);
}

static void DeliverSounds(int slot, qboolean reliable)
{
    sizebuf_t *msg=reliable?&test_clients[slot].netchan.message:&test_clients[slot].datagram;
    MSG_BeginReading(msg);
    while(msg->readcount<msg->cursize) {
        assert(MSG_ReadByte(msg)==svc_sound);
        SS_ParseSoundPacket(&ss_state.slots[slot],msg);
    }
    assert(msg->readcount==msg->cursize);
    assert(cl_entities==test_entities[0] && cl_numentities==16);
    SZ_Clear(msg);
}

static void TestSoundOccurrences(void)
{
    ResetAudioDelivery(); SendTestSound(CHAN_WEAPON,ATTN_NORM);
    assert(test_clients[0].datagram.cursize>0 && test_clients[1].datagram.cursize==0);
    assert(test_clients[2].datagram.cursize==test_clients[0].datagram.cursize);
    DeliverSounds(0,false); DeliverSounds(1,false); assert(sound_calls==1);

    ResetAudioDelivery(); test_pvs=2;
    SendTestSound(CHAN_BODY,ATTN_NORM);
    assert(test_clients[0].datagram.cursize==0 && test_clients[1].datagram.cursize>0);
    DeliverSounds(0,false); DeliverSounds(1,false); assert(sound_calls==1);
    /* Two byte-identical occurrences in one tick remain two sounds. */
    SendTestSound(CHAN_AUTO,ATTN_NORM); SendTestSound(CHAN_AUTO,ATTN_NORM);
    DeliverSounds(1,false); assert(sound_calls==3);

    ResetAudioDelivery(); test_pvs=2;
    SendTestSound(CHAN_VOICE,ATTN_NONE);
    assert(test_clients[0].datagram.cursize>0 && test_clients[1].datagram.cursize==0);
    assert(test_clients[2].datagram.cursize>0);
    DeliverSounds(0,false); assert(sound_calls==1);

    ResetAudioDelivery(); test_pvs=2;
    SendTestSound(CHAN_RELIABLE|CHAN_ITEM,ATTN_NORM);
    assert(test_clients[0].netchan.message.cursize==0 && test_clients[1].netchan.message.cursize>0);
    DeliverSounds(1,true); assert(sound_calls==1);

    ResetAudioDelivery(); test_clients[0].datagram.overflowed=true;
    SendTestSound(CHAN_WEAPON,ATTN_NORM); DeliverSounds(1,false); assert(sound_calls==1);
    puts("PASS sound delivery: shared/guest-only PHS, identical events, global, reliable, overflow fallback");
}

static void SendTestMuzzle(qboolean monster, multicast_t mode)
{
    vec3_t origin={1,0,0};
    MSG_WriteByte(&sv.multicast,monster?svc_muzzleflash2:svc_muzzleflash);
    MSG_WriteShort(&sv.multicast,monster?3:2);
    MSG_WriteByte(&sv.multicast,monster?MZ2_INFANTRY_MACHINEGUN_1:MZ_MACHINEGUN);
    SV_Multicast(origin,mode);
}

static void DeliverMuzzles(int observer)
{
    sizebuf_t *msg=&test_clients[observer].datagram;
    MSG_BeginReading(msg);
    while(msg->readcount<msg->cursize) {
        int command=MSG_ReadByte(msg);
        qboolean monster=command==svc_muzzleflash2 || command==svc_muzzleflash2_silent;
        qboolean silent=command==svc_muzzleflash_silent || command==svc_muzzleflash2_silent;
        if(!observer) {
            net_message=*msg; CL_ParseMuzzleFlash(monster,silent); *msg=net_message;
        } else if(monster) {
            SS_ParseSharedMuzzleFlash(&ss_state.slots[observer],msg,true,silent);
        } else {
            int entnum=MSG_ReadShort(msg), weapon=MSG_ReadByte(msg);
            SS_ParseLocalSlotMuzzleFlash(&ss_state.slots[observer],entnum,weapon,silent);
        }
    }
    SZ_Clear(msg);
}

static void TestMuzzleAudioOccurrences(void)
{
    int monster;
    load_muzzle_profile=false; CL_InitMuzzleFlashCvars();
    for(monster=0;monster<2;++monster) {
        ResetAudioDelivery(); SendTestMuzzle(monster,MULTICAST_ALL);
        assert(test_clients[0].datagram.data[0]==(monster?svc_muzzleflash2:svc_muzzleflash));
        assert(test_clients[1].datagram.data[0]==(monster?svc_muzzleflash2_silent:svc_muzzleflash_silent));
        assert(test_clients[2].datagram.data[0]==(monster?svc_muzzleflash2:svc_muzzleflash));
        DeliverMuzzles(1); DeliverMuzzles(0); assert(sound_calls==1);
        SendTestMuzzle(monster,MULTICAST_ALL); SendTestMuzzle(monster,MULTICAST_ALL);
        DeliverMuzzles(0); DeliverMuzzles(1); assert(sound_calls==3);

        ResetAudioDelivery(); test_pvs=2; SendTestMuzzle(monster,MULTICAST_PVS);
        assert(test_clients[0].datagram.cursize==0);
        assert(test_clients[1].datagram.data[0]==(monster?svc_muzzleflash2:svc_muzzleflash));
        DeliverMuzzles(1); assert(sound_calls==1);
        ResetAudioDelivery(); test_clients[0].datagram.overflowed=true;
        SendTestMuzzle(monster,MULTICAST_ALL);
        assert(test_clients[1].datagram.data[0]==(monster?svc_muzzleflash2:svc_muzzleflash));
        DeliverMuzzles(1); assert(sound_calls==1);
    }
    puts("PASS muzzle audio: player/monster once per occurrence, reverse receive order, identical shots, guest-only PVS, overflow fallback");
}

static void SetEventSnapshot(int observer, int frame, int event)
{
    frame_t *snapshot;
    entity_state_t *state;
    if(!observer) {
        snapshot=&cl.frame;
        memset(snapshot,0,sizeof(*snapshot));
        snapshot->valid=true; snapshot->serverframe=frame; snapshot->num_entities=1;
        snapshot->parse_entities=frame;
        state=&cl_parse_entities[frame & (MAX_PARSE_ENTITIES-1)];
        cl.parse_entities=frame+1;
        cl.frames[frame & UPDATE_MASK]=*snapshot;
    } else {
        ss_local_player_t *slot=&ss_state.slots[observer];
        snapshot=&slot->frame;
        memset(snapshot,0,sizeof(*snapshot));
        snapshot->valid=true; snapshot->serverframe=frame; snapshot->num_entities=1;
        snapshot->parse_entities=frame;
        state=&slot->parse_entities[frame & (MAX_PARSE_ENTITIES-1)];
        slot->parse_entities_num=frame+1;
        slot->frames[frame & UPDATE_MASK]=*snapshot;
    }
    memset(state,0,sizeof(*state)); state->number=2; state->event=event;
}

static void EmitEventSnapshot(int observer)
{
    if(!observer) SS_FireEntityEvents(0,&cl.frame,cl_parse_entities);
    else SS_FireEntityEvents(observer,&ss_state.slots[observer].frame,ss_state.slots[observer].parse_entities);
}

static void TestGuestEntityEvents(void)
{
    ResetAudioDelivery();
    SetEventSnapshot(0,30,EV_FALLSHORT); EmitEventSnapshot(0); assert(sound_calls==1);
    SetEventSnapshot(1,30,EV_FALLSHORT); EmitEventSnapshot(1); assert(sound_calls==1);
    EmitEventSnapshot(1); assert(sound_calls==1);
    SetEventSnapshot(1,31,EV_FALLSHORT); EmitEventSnapshot(1); assert(sound_calls==2);
    SetEventSnapshot(0,31,EV_FALLSHORT); EmitEventSnapshot(0); assert(sound_calls==2);
    /* A later guest packet can still carry a distinct earlier-tick event. */
    SetEventSnapshot(0,33,EV_FALLSHORT); EmitEventSnapshot(0); assert(sound_calls==3);
    SetEventSnapshot(1,32,EV_FALLSHORT); EmitEventSnapshot(1); assert(sound_calls==4);
    SetEventSnapshot(1,33,EV_FALLSHORT); EmitEventSnapshot(1); assert(sound_calls==4);

    ResetAudioDelivery();
    SetEventSnapshot(1,40,EV_FOOTSTEP); EmitEventSnapshot(1); assert(sound_calls==1);
    SetEventSnapshot(0,40,EV_FOOTSTEP); EmitEventSnapshot(0); assert(sound_calls==1);
    SetEventSnapshot(1,41,EV_PLAYER_TELEPORT); EmitEventSnapshot(1); assert(sound_calls==2);
    SetEventSnapshot(0,41,EV_PLAYER_TELEPORT); EmitEventSnapshot(0); assert(sound_calls==2);
    SetEventSnapshot(1,42,EV_ITEM_RESPAWN); EmitEventSnapshot(1); assert(sound_calls==3);
    SetEventSnapshot(0,42,EV_ITEM_RESPAWN); EmitEventSnapshot(0); assert(sound_calls==3);
    /* History from a prior map generation cannot consume a new map's event. */
    ++cl.servercount; ss_state.slots[1].servercount=cl.servercount;
    SetEventSnapshot(1,42,EV_ITEM_RESPAWN); EmitEventSnapshot(1); assert(sound_calls==4);
    puts("PASS guest entity audio: footsteps, landing, teleport/respawn, order/delay, same-frame dedup, generation reset");
}

int main(void)
{
    Swap_Init();
    TestSoundOccurrences();
    TestMuzzleAudioOccurrences();
    TestGuestEntityEvents();
    puts("All split-screen sound-delivery regressions passed.");
    return 0;
}
