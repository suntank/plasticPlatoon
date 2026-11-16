/* Production health pickup/decay/respawn logic; engine I/O is stubbed. */
#include "../../src/game/g_items.c"
#include <assert.h>
#include <stdarg.h>

game_import_t gi;
game_export_t globals;
game_locals_t game;
level_locals_t level;
edict_t *g_edicts;
static edict_t entities[16];
static cvar_t zero, one={.value=1};
cvar_t *deathmatch=&zero,*coop=&zero,*maxclients=&one;
static int links,unlinks;

int randk(void) { return 0; }
static void link_entity(edict_t *e) { ++links; ++e->linkcount; }
static void unlink_entity(edict_t *e) { (void)e;++unlinks; }
static void near(float actual,float expected) { assert(fabsf(actual-expected)<.001f); }
static edict_t *reset(int count,int style,int health)
{
    memset(entities,0,sizeof(entities));memset(&level,0,sizeof(level));
    g_edicts=entities;level.time=20;deathmatch=&zero;coop=&zero;links=unlinks=0;
    entities[1].inuse=true;entities[1].health=health;entities[1].max_health=100;
    entities[10].inuse=true;entities[10].count=count;entities[10].style=style;entities[10].solid=SOLID_TRIGGER;
    return &entities[10];
}
static void test_regular_health_and_caps(void)
{
    edict_t *pickup=reset(10,0,55),*player=&entities[1];
    assert(Pickup_Health(pickup,player)&&player->health==65);
    assert(!pickup->think&&pickup->solid==SOLID_TRIGGER&&!links);
    pickup=reset(25,0,90);assert(Pickup_Health(pickup,player)&&player->health==100);
    pickup=reset(25,0,100);assert(!Pickup_Health(pickup,player)&&player->health==100);
    pickup=reset(10,0,115);assert(!Pickup_Health(pickup,player)&&player->health==115);
    pickup=reset(2,HEALTH_IGNORE_MAX,100);assert(Pickup_Health(pickup,player)&&player->health==102);
    pickup=reset(2,HEALTH_IGNORE_MAX,149);assert(Pickup_Health(pickup,player)&&player->health==151);
    assert(!Pickup_Health(NULL,player)&&!Pickup_Health(pickup,NULL));
    puts("PASS health amounts: capped +10/+25, uncapped +2, refusal at max and null handling");
}
static void test_deathmatch_respawn(void)
{
    edict_t *pickup=reset(25,0,90),*player=&entities[1];deathmatch=&one;
    assert(Pickup_Health(pickup,player)&&player->health==100);
    assert(pickup->flags&FL_RESPAWN);assert(pickup->svflags&SVF_NOCLIENT);
    assert(pickup->solid==SOLID_NOT&&pickup->think&&links==1);near(pickup->nextthink,50);
    level.time=50;pickup->think(pickup);
    assert(pickup->inuse&&pickup->solid==SOLID_TRIGGER&&!(pickup->svflags&SVF_NOCLIENT));
    assert(pickup->s.event==EV_ITEM_RESPAWN&&links==2);
    pickup=reset(10,0,90);deathmatch=&one;pickup->spawnflags=DROPPED_ITEM;
    assert(Pickup_Health(pickup,player)&&!pickup->think&&!links);
    puts("PASS regular health respawn: 30-second DM delay, visibility/trigger restoration and dropped-item exemption");
}
static void test_mega_decay(void)
{
    edict_t *pickup=reset(100,HEALTH_IGNORE_MAX|HEALTH_TIMED,100),*player=&entities[1];
    assert(Pickup_Health(pickup,player)&&player->health==200&&pickup->owner==player);
    assert(pickup->flags&FL_RESPAWN);assert(pickup->svflags&SVF_NOCLIENT);
    assert(pickup->solid==SOLID_NOT&&pickup->think);near(pickup->nextthink,25);
    level.time=25;pickup->think(pickup);assert(player->health==199);near(pickup->nextthink,26);
    for(int health=199;health>100;--health) { level.time+=1;pickup->think(pickup);assert(player->health==health-1); }
    assert(pickup->inuse);level.time+=1;pickup->think(pickup);assert(!pickup->inuse&&unlinks==1);
    pickup=reset(100,HEALTH_IGNORE_MAX|HEALTH_TIMED,90);deathmatch=&one;
    assert(Pickup_Health(pickup,player)&&player->health==190);
    player->health=100;level.time=25;pickup->think(pickup);
    assert(pickup->inuse&&pickup->solid==SOLID_NOT);near(pickup->nextthink,45);
    level.time=45;pickup->think(pickup);assert(pickup->solid==SOLID_TRIGGER&&pickup->s.event==EV_ITEM_RESPAWN);
    pickup=reset(100,HEALTH_IGNORE_MAX|HEALTH_TIMED,90);deathmatch=&one;pickup->spawnflags=DROPPED_ITEM;
    assert(Pickup_Health(pickup,player));player->health=100;pickup->think(pickup);assert(!pickup->inuse);
    puts("PASS mega health: uncapped +100, five-second grace, one HP/second decay, cleanup and 20-second DM respawn");
}
static void test_adrenaline(void)
{
    edict_t *pickup=reset(0,0,50),*player=&entities[1];gitem_t item={.quantity=60};pickup->item=&item;
    assert(Pickup_Adrenaline(pickup,player)&&player->max_health==101&&player->health==101);
    pickup=reset(0,0,120);pickup->item=&item;
    assert(Pickup_Adrenaline(pickup,player)&&player->max_health==101&&player->health==120);
    pickup=reset(0,0,50);pickup->item=&item;deathmatch=&one;
    assert(Pickup_Adrenaline(pickup,player)&&player->max_health==100&&player->health==100);
    assert(pickup->solid==SOLID_NOT&&pickup->think);near(pickup->nextthink,80);
    assert(!Pickup_Adrenaline(NULL,player)&&!Pickup_Adrenaline(pickup,NULL));
    puts("PASS adrenaline: permanent +1 max outside DM, refill without trimming overheal, unchanged 60-second DM respawn");
}
int main(void)
{
    gi.linkentity=link_entity;gi.unlinkentity=unlink_entity;
    test_regular_health_and_caps();test_deathmatch_respawn();test_mega_decay();test_adrenaline();return 0;
}
