/* Production armor pickup/protection logic; only engine I/O is stubbed. */
#include "../../src/game/g_items.c"
#include <assert.h>

extern int CheckArmor(edict_t *,vec3_t,vec3_t,int,int,int);
game_import_t gi;
game_export_t globals;
game_locals_t game;
level_locals_t level;
edict_t *g_edicts;
static edict_t entities[16];
static gclient_t client;
static cvar_t zero,one={.value=1};
cvar_t *deathmatch=&zero,*coop=&zero,*maxclients=&one;
static int links,sparks;
int randk(void) { return 0; }
static void link_entity(edict_t *e) { ++links;++e->linkcount; }
static void unlink_entity(edict_t *e) { (void)e; }
static void write_byte(int n) { if(n==TE_SPARKS)++sparks; }
static void write_vector(vec3_t v) { (void)v; }
static void multicast(vec3_t v,multicast_t mode) { (void)v;(void)mode; }

static edict_t *reset(int kind)
{
    memset(entities,0,sizeof(entities));memset(&client,0,sizeof(client));memset(itemlist,0,sizeof(itemlist));
    memset(&level,0,sizeof(level));level.time=20;g_edicts=entities;game.num_items=5;
    jacket_armor_index=1;combat_armor_index=2;body_armor_index=3;
    itemlist[1]=(gitem_t){.info=&jacketarmor_info,.tag=ARMOR_JACKET};
    itemlist[2]=(gitem_t){.info=&combatarmor_info,.tag=ARMOR_COMBAT};
    itemlist[3]=(gitem_t){.info=&bodyarmor_info,.tag=ARMOR_BODY};
    itemlist[4]=(gitem_t){.tag=ARMOR_SHARD};
    entities[1].inuse=true;entities[1].client=&client;
    entities[10].inuse=true;entities[10].item=&itemlist[kind];entities[10].solid=SOLID_TRIGGER;
    deathmatch=&zero;coop=&zero;links=sparks=0;return &entities[10];
}
static void test_base_counts_caps_and_shard(void)
{
    const int base[]={0,25,50,100},cap[]={0,50,100,200};
    for(int kind=1;kind<=3;++kind) {
        edict_t *pickup=reset(kind),*player=&entities[1];
        gitem_armor_t *info=itemlist[kind].info;
        assert(info->base_count==base[kind]&&info->max_count==cap[kind]);
        assert(Pickup_Armor(pickup,player)&&client.pers.inventory[kind]==base[kind]);
        assert(ArmorIndex(player)==kind);
        client.pers.inventory[kind]=cap[kind];assert(!Pickup_Armor(pickup,player));
        pickup->item=&itemlist[4];assert(Pickup_Armor(pickup,player));
        assert(client.pers.inventory[kind]==cap[kind]+2);
    }
    edict_t *pickup=reset(4),*player=&entities[1];
    assert(Pickup_Armor(pickup,player)&&client.pers.inventory[1]==2&&ArmorIndex(player)==1);
    assert(!Pickup_Armor(NULL,player)&&!Pickup_Armor(pickup,NULL));
    assert(ArmorIndex(NULL)==0);edict_t no_client={0};assert(ArmorIndex(&no_client)==0);
    puts("PASS armor counts: jacket25/50, combat50/100, body100/200; shard+2 to current or jacket, including above cap");
}
static void test_upgrades_and_salvage(void)
{
    edict_t *pickup=reset(2),*player=&entities[1];client.pers.inventory[1]=25;
    assert(Pickup_Armor(pickup,player)&&client.pers.inventory[1]==0&&client.pers.inventory[2]==62);
    pickup=reset(3);client.pers.inventory[2]=50;
    assert(Pickup_Armor(pickup,player)&&client.pers.inventory[2]==0&&client.pers.inventory[3]==137);
    pickup=reset(1);client.pers.inventory[3]=150;
    assert(Pickup_Armor(pickup,player)&&client.pers.inventory[1]==0&&client.pers.inventory[3]==159);
    pickup=reset(2);client.pers.inventory[3]=199;
    assert(Pickup_Armor(pickup,player)&&client.pers.inventory[3]==200);
    assert(!Pickup_Armor(pickup,player)&&client.pers.inventory[3]==200);
    pickup=reset(3);client.pers.inventory[1]=500;
    assert(Pickup_Armor(pickup,player)&&client.pers.inventory[1]==0&&client.pers.inventory[3]==200);
    puts("PASS armor salvage: protection-weighted upgrades, weaker pickups, clamping and maxed-out refusal");
}
static void test_protection_and_damage_effects(void)
{
    vec3_t point={0,0,0},normal={0,0,1};
    const int normal_save[]={0,3,6,8},energy_save[]={0,0,3,6};
    for(int kind=1;kind<=3;++kind) for(int energy=0;energy<2;++energy) {
        reset(kind);client.pers.inventory[kind]=100;
        int expected=energy?energy_save[kind]:normal_save[kind];
        int save=CheckArmor(&entities[1],point,normal,10,TE_SPARKS,energy?DAMAGE_ENERGY:0);
        assert(save==expected&&client.pers.inventory[kind]==100-expected&&sparks==(expected?1:0));
    }
    reset(2);client.pers.inventory[2]=50;
    assert(CheckArmor(&entities[1],point,normal,7,TE_SPARKS,0)==5&&client.pers.inventory[2]==45);
    assert(CheckArmor(&entities[1],point,normal,20,TE_SPARKS,DAMAGE_NO_ARMOR)==0&&client.pers.inventory[2]==45);
    client.pers.inventory[2]=2;
    assert(CheckArmor(&entities[1],point,normal,100,TE_SPARKS,0)==2&&client.pers.inventory[2]==0);
    assert(CheckArmor(&entities[1],point,normal,100,TE_SPARKS,0)==0);
    assert(CheckArmor(NULL,point,normal,100,TE_SPARKS,0)==0);
    puts("PASS armor protection: normal30/60/80 percent, energy0/30/60 percent, rounded savings, depletion, bypass and sparks");
}
static void test_respawn(void)
{
    edict_t *pickup=reset(4);deathmatch=&one;
    assert(Pickup_Armor(pickup,&entities[1]));
    assert(pickup->flags&FL_RESPAWN);assert(pickup->svflags&SVF_NOCLIENT);
    assert(pickup->solid==SOLID_NOT&&pickup->think&&pickup->nextthink==40&&links==1);
    level.time=40;pickup->think(pickup);
    assert(pickup->solid==SOLID_TRIGGER&&!(pickup->svflags&SVF_NOCLIENT)&&pickup->s.event==EV_ITEM_RESPAWN);
    pickup=reset(1);deathmatch=&one;pickup->spawnflags=DROPPED_ITEM;
    assert(Pickup_Armor(pickup,&entities[1])&&!pickup->think&&!links);
    puts("PASS armor respawn: unchanged20-second DM delay, restored visibility and dropped-item exemption");
}
int main(void)
{
    gi.linkentity=link_entity;gi.unlinkentity=unlink_entity;gi.WriteByte=write_byte;
    gi.WritePosition=write_vector;gi.WriteDir=write_vector;gi.multicast=multicast;
    test_base_counts_caps_and_shard();test_upgrades_and_salvage();test_protection_and_damage_effects();test_respawn();return 0;
}
