#include "../../src/game/header/local.h"
#include <assert.h>
#include <stdarg.h>
#include <unistd.h>

extern void SP_trigger_platoon_extract(edict_t *self);
extern void platoon_extract_think(edict_t *self);
extern void SP_misc_platoon_dropship(edict_t *self);
extern void platoon_dropship_think(edict_t *self);
extern void SP_trigger_counter(edict_t *self);
extern void SP_target_platoon_intermission(edict_t *self);

static cvar_t clients, entities, zero, cooperative;
static int center_calls[3];
static char center_text[3][128];
static char layouts[3][1024], layout_message[1024];
static char model_names[64][MAX_QPATH];
static int model_count;
static int capture_media_rebind, capture_ship_index, media_rebind_calls;
static edict_t before_media_rebind;
static void link_entity(edict_t *ent)
{
    VectorAdd(ent->s.origin, ent->mins, ent->absmin);
    VectorAdd(ent->s.origin, ent->maxs, ent->absmax);
    VectorSubtract(ent->maxs, ent->mins, ent->size);
}
static void set_model(edict_t *ent, char *model)
{
    (void)model;
    VectorSet(ent->mins, -128, -128, 0);
    VectorSet(ent->maxs, 128, 128, 128);
}
static int model_index(char *name)
{
    if(!name)return 0;
    if(capture_media_rebind&&(!strcmp(name,"models/vehicles/platoon_dropship/body.md2")||
            !strcmp(name,"models/vehicles/platoon_dropship/main_rotor.md2"))) {
        if(!media_rebind_calls)memcpy(&before_media_rebind,&g_edicts[capture_ship_index],sizeof(before_media_rebind));
        ++media_rebind_calls;
    }
    for (int i=1;i<=model_count;++i) if (!strcmp(model_names[i],name)) return i;
    assert(model_count<63);snprintf(model_names[++model_count],MAX_QPATH,"%s",name);return model_count;
}
static void no_free(int tag) { (void)tag; }
static void *allocate(int size, int tag) { (void)tag; return calloc(1, size); }
static void unlink_entity(edict_t *self) { (void)self; }
static char music_track[MAX_QPATH];
static void config_string(int index, char *value)
{
    if (index == CS_CDTRACK)
        Q_strlcpy(music_track, value, sizeof(music_track));
}
static void write_byte(int value) { (void)value; }
static void write_string(char *value) { Q_strlcpy(layout_message, value, sizeof(layout_message)); }
static void unicast(edict_t *ent, qboolean reliable)
{
    int index = ent - g_edicts;
    assert(index > 0 && index <= 2);
    Q_strlcpy(layouts[index], layout_message, sizeof(layouts[index]));
}
static void center_print(edict_t *ent, const char *format, ...)
{
    int index = ent - g_edicts;
    va_list args;
    assert(index > 0 && index <= 2);
    ++center_calls[index];
    va_start(args, format);
    vsnprintf(center_text[index], sizeof(center_text[index]), format, args);
    va_end(args);
}
static void print(const char *fmt, ...) { (void)fmt; }
static void client_print(edict_t *ent, int level, const char *fmt, ...) { (void)fmt; }
static YQ2_ATTR_NORETURN void error(const char *fmt, ...)
{
    va_list args;
    va_start(args, fmt); vfprintf(stderr, fmt, args); va_end(args);
    abort();
}
static void reset(void)
{
    int i;
    memset(g_edicts, 0, game.maxentities * sizeof(*g_edicts));
    memset(game.clients, 0, game.maxclients * sizeof(*game.clients));
    memset(&level, 0, sizeof(level));
    QM_ClearMapWeapons();
    music_track[0] = '\0';
    memset(center_calls, 0, sizeof(center_calls));
    memset(center_text, 0, sizeof(center_text));
    memset(layouts, 0, sizeof(layouts));
    memset(model_names,0,sizeof(model_names));model_count=0;
    capture_media_rebind=capture_ship_index=media_rebind_calls=0;
    globals.num_edicts = game.maxclients + 1;
    level.time = 10;
    g_edicts[0].inuse = true;
    g_edicts[0].classname = "worldspawn";
    for (i = 1; i <= game.maxclients; i++)
    {
        g_edicts[i].inuse = true;
        g_edicts[i].classname = "player";
        g_edicts[i].health = 100;
        g_edicts[i].max_health = 100;
        g_edicts[i].client = &game.clients[i - 1];
        game.clients[i - 1].pers.connected = true;
        VectorSet(g_edicts[i].s.origin, 0, i * 32, 24);
    }
}
static edict_t *counter(void)
{
    edict_t *self = G_Spawn();
    self->classname = "trigger_counter";
    self->targetname = "arrival";
    self->count = 99;
    self->spawnflags = 1;
    SP_trigger_counter(self);
    return self;
}
static edict_t *extract(int flags)
{
    edict_t *self = G_Spawn();
    self->classname = "trigger_platoon_extract";
    self->model = "*1";
    self->spawnflags = flags;
    self->target = "arrival";
    SP_trigger_platoon_extract(self);
    return self;
}
static void tick(edict_t *self)
{
    level.time += FRAMETIME;
    if (self->think && self->nextthink && self->nextthink <= level.time + .0001f)
    {
        self->nextthink = 0;
        self->think(self);
    }
}
static void test_extraction(void)
{
    edict_t *self, *event;
    reset(); event = counter(); self = extract(4);
    tick(self); platoon_extract_think(self);
    assert(!self->count && event->count == 99 && self->solid == SOLID_NOT);
    self->use(self, NULL, NULL);
    g_edicts[2].s.origin[0] = 200;
    tick(self);
    assert(!self->count && event->count == 99);
    /* Reusing an enabled trigger cannot bypass the squad check. */
    self->use(self, NULL, &g_edicts[1]); tick(self);
    assert(!self->count);
    g_edicts[2].s.origin[0] = 0;
    tick(self);
    assert(self->count == 1 && event->count == 98 && !self->use);
    platoon_extract_think(self); tick(self);
    assert(event->count == 98);

    reset(); event = counter(); self = extract(0);
    g_edicts[2].s.origin[0] = 200;
    g_edicts[2].health = 0;
    tick(self);
    assert(self->count && event->count == 98);

    reset(); event = counter(); self = extract(0);
    g_edicts[2].s.origin[0] = 200;
    g_edicts[2].client->pers.connected = false;
    tick(self);
    assert(self->count);

    reset(); event = counter(); self = extract(0);
    g_edicts[2].s.origin[0] = 200;
    g_edicts[2].client->resp.spectator = true;
    tick(self);
    assert(self->count);

    reset(); event = counter(); self = extract(0);
    g_edicts[1].health = g_edicts[2].health = 0;
    tick(self);
    assert(!self->count && event->count == 99);
    /* A reconnect/respawn can complete without another touch event. */
    g_edicts[1].health = 100; tick(self);
    assert(self->count);

    reset(); event = counter(); self = extract(0);
    g_edicts[1].s.origin[2] = 129;
    tick(self);
    assert(!self->count); /* Standing above the helipad does not count. */
}
static edict_t *corner(char *name, char *target, float x, float y, float z)
{
    edict_t *self = G_Spawn();
    self->classname = "path_corner";
    self->targetname = name;
    self->target = target;
    VectorSet(self->s.origin, x, y, z);
    return self;
}
static edict_t *dropship(int flags)
{
    edict_t *self = G_Spawn();
    self->classname = "misc_platoon_dropship";
    self->target = "takeoff";
    self->spawnflags = flags;
    self->speed = 100;
    SP_misc_platoon_dropship(self);
    assert(self->s.renderfx & RF_PP_FRIENDLY_COLOR);
    assert(!(self->s.renderfx & RF_PP_ENEMY_COLOR));
    return self;
}
static void test_dropship_spawn_contract(void)
{
    for(int hidden=0;hidden<2;++hidden) {
        reset();edict_t *self=G_Spawn();self->classname="misc_platoon_dropship";self->spawnflags=hidden;
        SP_misc_platoon_dropship(self);
        assert(!strcmp(model_names[self->s.modelindex],"models/vehicles/platoon_dropship/body.md2"));
        assert(!strcmp(model_names[self->s.modelindex2],"models/vehicles/platoon_dropship/main_rotor.md2"));
        assert(!strcmp(model_names[self->noise_index],"bosshovr/bhvengn1.wav"));
        assert(self->movetype==MOVETYPE_NONE&&self->solid==SOLID_NOT&&self->speed==240);
        assert((self->s.renderfx&(RF_FRAMELERP|RF_PP_FRIENDLY_COLOR))==(RF_FRAMELERP|RF_PP_FRIENDLY_COLOR));
        assert(!(self->s.renderfx&RF_PP_ENEMY_COLOR)&&!(self->svflags&SVF_MONSTER));
        assert(self->mins[0]==-114&&self->mins[1]==-68&&self->mins[2]==36);
        assert(self->maxs[0]==68&&self->maxs[1]==68&&self->maxs[2]==96);
        assert(!!(self->svflags&SVF_NOCLIENT)==hidden);
        assert(self->s.sound==(hidden?0:self->noise_index));
    }
}
static void test_flight_vector_speed(void)
{
    reset();corner("takeoff",NULL,30,40,30);edict_t *self=dropship(0);
    self->use(self,NULL,&g_edicts[1]);tick(self);
    vec3_t expected={30,40,30};VectorNormalize(expected);VectorScale(expected,10,expected);
    for(int axis=0;axis<3;++axis)assert(fabsf(self->s.origin[axis]-expected[axis])<.001f);
    assert(self->s.angles[YAW] > 13 && self->s.angles[YAW] <= 14);
    assert(self->s.angles[PITCH] == -5);
    for (int step = 0; step < 3; step++) tick(self);
    assert(self->s.angles[YAW] == 53); /* Native vectoyaw truncates degrees. */
    assert(fabsf(self->s.angles[PITCH]+30/sqrtf(3400)*12)<.001f);
    assert(VectorLength(self->velocity)==0&&self->nextthink>level.time);
}
static void test_flight(void)
{
    edict_t *first, *last, *self, *event;
    int i;
    reset(); event = counter();
    first = corner("takeoff", "landing", 0, 0, 30);
    first->wait = .5f; first->pathtarget = "arrival";
    last = corner("landing", NULL, 30, 0, 30);
    last->pathtarget = "arrival";
    self = dropship(1);
    assert(self->solid == SOLID_NOT && !(self->svflags & SVF_MONSTER));
    assert(self->s.modelindex2 && self->svflags & SVF_NOCLIENT && !self->s.sound);
    tick(self); assert(!self->s.origin[2]);
    self->use(self, NULL, &g_edicts[1]);
    assert(!(self->svflags & SVF_NOCLIENT) && self->s.sound);
    tick(self); assert(fabsf(self->s.origin[2] - 10) < .001f);
    self->use(self, NULL, &g_edicts[2]); /* No restarting or swapping activator. */
    assert(self->activator == &g_edicts[1]);
    tick(self); tick(self);
    assert(event->count == 98 && self->movetarget == last);
    for (i = 0; i < 3; i++) tick(self);
    assert(self->s.origin[0] == 0);
    assert(self->s.angles[PITCH] == 0);
    for (i = 0; i < 12; i++) tick(self);
    assert(self->s.origin[0] == 30 && self->s.origin[2] == 30);
    assert(!self->movetarget && !self->nextthink && event->count == 97);
    platoon_dropship_think(self); assert(event->count == 97);
    assert(!self->s.angles[PITCH]);
    self->use(self, NULL, &g_edicts[1]);
    assert(!self->nextthink && self->count == 2); /* No outbound path: one use. */

    reset(); self = dropship(0);
    self->use(self, NULL, &g_edicts[1]);
    assert(!self->count && !self->nextthink); /* Missing route is recoverable. */
    first = corner("takeoff", NULL, 20, 0, 0);
    self->use(self, NULL, &g_edicts[1]);
    G_FreeEdict(first); tick(self); assert(!self->nextthink);
}
static void restore(const char *path)
{
    int i;
    WriteLevel(path); ReadLevel(path);
    for (i = 0; i < game.maxclients; i++) game.clients[i].pers.connected = true;
}
static void test_dropship_turn(const char *path)
{
    reset();
    edict_t *event = counter();
    edict_t *landing = corner("takeoff", NULL, 10, 6, 0);
    landing->pathtarget = "arrival";
    edict_t *ship = dropship(0);
    int ship_index = ship - g_edicts;
    ship->s.angles[YAW] = 350;

    ship->use(ship, NULL, &g_edicts[1]);
    tick(ship);
    /* Take the short arc through zero while continuing along the route. */
    assert(ship->s.angles[YAW] > 3 && ship->s.angles[YAW] <= 4);
    assert(ship->s.origin[0] > 0 && ship->s.origin[0] < 10);
    tick(ship);
    assert(ship->count == 2 && !ship->movetarget && ship->nextthink);
    assert(ship->s.angles[YAW] > 17 && ship->s.angles[YAW] <= 18);
    assert(ship->s.origin[0] == 10 && ship->s.origin[1] == 6 && event->count == 98);

    restore(path);
    ship = &g_edicts[ship_index];
    tick(ship);
    assert(ship->s.angles[YAW] == 30 && !ship->nextthink);
    assert(ship->s.origin[0] == 10 && ship->s.origin[1] == 6 && event->count == 98);
}
static void test_legacy_dropship_media_restore(const char *path)
{
    for(int state=0;state<=4;++state) {
        reset();edict_t *inbound=corner("takeoff",NULL,30,40,30);
        edict_t *outbound=corner("outbound",NULL,80,20,90);
        edict_t *ship=dropship(state==0);ship->deathtarget="outbound";
        ship->count=state;ship->activator=&g_edicts[2];ship->speed=117;
        ship->timestamp=level.time+.35f;
        if(state==1||state==3) {
            ship->movetarget=state==1?inbound:outbound;
            ship->think=platoon_dropship_think;ship->nextthink=level.time+FRAMETIME;
        }
        VectorSet(ship->s.origin,15,23,42);VectorSet(ship->s.angles,-7,213,3);
        int old_body=gi.modelindex("models/monsters/boss2/tris.md2");
        int old_rotor=gi.modelindex("models/monsters/boss2/propeller.md2");
        ship->s.modelindex=old_body;ship->s.modelindex2=old_rotor;
        edict_t *enemy=G_Spawn();enemy->classname="monster_boss2";enemy->svflags=SVF_MONSTER;
        enemy->s.modelindex=old_body;enemy->s.modelindex2=old_rotor;
        int enemy_index=enemy-g_edicts;
        capture_ship_index=ship-g_edicts;capture_media_rebind=true;
        restore(path);capture_media_rebind=false;
        ship=&g_edicts[capture_ship_index];enemy=&g_edicts[enemy_index];
        assert(media_rebind_calls==2);
        assert(before_media_rebind.s.modelindex==old_body&&before_media_rebind.s.modelindex2==old_rotor);
        assert(!strcmp(model_names[ship->s.modelindex],"models/vehicles/platoon_dropship/body.md2"));
        assert(!strcmp(model_names[ship->s.modelindex2],"models/vehicles/platoon_dropship/main_rotor.md2"));
        edict_t expected;memcpy(&expected,&before_media_rebind,sizeof(expected));
        expected.s.modelindex=ship->s.modelindex;expected.s.modelindex2=ship->s.modelindex2;
        assert(!memcmp(&expected,ship,sizeof(expected))); /* Exactly two integers change. */
        assert(!strcmp(model_names[enemy->s.modelindex],"models/monsters/plastic_boss/body.md2"));
        assert(!strcmp(model_names[enemy->s.modelindex2],"models/monsters/plastic_boss/main_rotor.md2"));
    }
    unlink(path);
}
static void test_outbound_flight_and_camera(const char *path)
{
    edict_t *first, *outbound, *ship, *camera, *scene, *event;
    usercmd_t input;
    int ship_index, scene_index, i;

    reset();
    first = corner("takeoff", NULL, 0, 0, 30);
    outbound = corner("outbound", NULL, 80, 0, 90);
    ship = dropship(1);
    ship->deathtarget = "outbound";
    ship_index = ship - g_edicts;
    ship->use(ship, NULL, &g_edicts[1]);
    ship->use(ship, NULL, &g_edicts[2]); /* Cannot start the return while flying. */
    for (i = 0; i < 3; ++i) tick(ship);
    assert(ship->count == 2 && ship->s.origin[2] == 30);
    assert(ship->s.angles[PITCH] == -5 && ship->nextthink);
    tick(ship);
    assert(ship->s.angles[PITCH] == 0 && !ship->nextthink);

    /* The parked state, outbound route and callbacks survive save/load. */
    restore(path); ship = &g_edicts[ship_index];
    assert(ship->count == 2 && ship->deathtarget && ship->use);
    ship->use(ship, NULL, &g_edicts[1]);
    assert(ship->count == 3 && ship->movetarget == outbound);
    tick(ship);
    restore(path); ship = &g_edicts[ship_index];
    assert(ship->count == 3 && ship->think == platoon_dropship_think);
    for (i = 0; i < 15; ++i) tick(ship);
    assert(ship->count == 4 && !ship->nextthink && ship->s.origin[0] == 80);
    ship->use(ship, NULL, &g_edicts[1]);
    assert(ship->count == 4 && !ship->nextthink); /* Exactly one departure. */

    reset();
    coop->value = 1;
    Q_strlcpy(level.mapname, "pp_sandstorm", sizeof(level.mapname));
    event = counter();
    camera = G_Spawn();
    camera->classname = "info_player_intermission";
    VectorSet(camera->s.origin, 100, 200, 300);
    scene = G_Spawn();
    scene->classname = "target_platoon_intermission";
    scene->map = "*pp_sandstorm";
    scene->target = "arrival";
    scene->count = 12;
    scene->message = "MISSION COMPLETE";
    SP_target_platoon_intermission(scene);
    scene_index = scene - g_edicts;
    restore(path); scene = &g_edicts[scene_index];
    assert(scene->use); /* Savegame function table covers the new callback. */
    game.serverflags = SFL_CROSS_TRIGGER_MASK | 0x400;
    scene->use(scene, &g_edicts[1], &g_edicts[1]);
    assert(level.intermissiontime == 22 && !QM_IsOpen());
    assert(!strcmp(music_track, PP_MISSION_COMPLETE_MUSIC));
    assert(game.serverflags == 0x400);
    assert(event->count == 98);
    assert(center_calls[1] == 1 && center_calls[2] == 1);
    assert(!strcmp(center_text[1], "MISSION COMPLETE") && !strcmp(center_text[2], "MISSION COMPLETE"));
    assert(!strcmp(scene->message, "MISSION COMPLETE"));
    for (i = 1; i <= 2; ++i)
    {
        assert(g_edicts[i].s.origin[0] == 100 && g_edicts[i].s.origin[2] == 300);
        assert(!g_edicts[i].client->showscores && !g_edicts[i].client->showhelp);
        G_SetStats(&g_edicts[i]);
        assert(!(g_edicts[i].client->ps.stats[STAT_LAYOUTS] & 1));
    }
    restore(path);
    assert(level.intermissiontime == 22 && !QM_IsOpen());
    memset(&input, 0, sizeof(input));
    input.buttons = BUTTON_ANY;
    level.time = 21.9f;
    ClientThink(&g_edicts[1], &input);
    assert(!QM_IsOpen());
    level.time = 22.1f;
    ClientThink(&g_edicts[2], &input);
    assert(QM_IsOpen() && !QM_Frame());
    reset();
    camera = G_Spawn();
    camera->classname = "info_player_intermission";
    scene = G_Spawn();
    scene->classname = "target_platoon_intermission";
    scene->map = "*pp_sandstorm";
    SP_target_platoon_intermission(scene);
    scene->use(scene, &g_edicts[1], &g_edicts[1]);
    assert(center_calls[1] == 0 && center_calls[2] == 0);
    coop->value = 0;
    unlink(path);
}
static void shop_input(edict_t *player, short move, short jump, int buttons)
{
    usercmd_t input = {.forwardmove = move, .upmove = jump, .buttons = buttons};
    usercmd_t released = {0};
    ClientThink(player, &input);
    ClientThink(player, &released);
}

static void test_quartermaster(const char *path)
{
    edict_t *camera, *exit;
    edict_t *first = &g_edicts[1], *second = &g_edicts[2];
    gitem_t *light = FindItem("Light Bullets");
    edict_t specialist = {.max_health = 180};
    edict_t heavy = {.max_health = 500};
    gitem_t *sprues = FindItemByClassname("item_sprues");
    edict_t cache = {.item = sprues, .count = 20};

    reset();
    coop->value = 1;
    Q_strlcpy(level.mapname, "pp_garden_infiltration", sizeof(level.mapname));
    edict_t *saved_pickup = G_Spawn();
    int pickup_index = saved_pickup - g_edicts;
    saved_pickup->classname = "item_sprues";
    saved_pickup->item = sprues;
    saved_pickup->count = 37;
    saved_pickup->s.modelindex = gi.modelindex("models/items/armor/shard/tris.md2");
    restore(path);
    saved_pickup = &g_edicts[pickup_index];
    assert(saved_pickup->count == 37);
    assert(!strcmp(model_names[saved_pickup->s.modelindex], "models/items/sprues/tris.md2"));
    G_FreeEdict(saved_pickup);

    assert(Add_Ammo(first, light, 200));
    assert(first->client->pers.inventory[ITEM_INDEX(light)] == 150);
    assert(!Add_Ammo(first, light, 1));
    QM_KillReward(&specialist);
    QM_KillReward(&heavy);
    assert(sprues->pickup(&cache, second));
    assert(first->client->quartermaster.progress.sprues == 40);
    assert(second->client->quartermaster.progress.sprues == 40);
    QM_AwardSprues(900, false);
    first->health = 62;
    camera = G_Spawn();
    camera->classname = "info_player_intermission";
    exit = G_Spawn();
    exit->map = "pp_sandbox_assault";
    BeginIntermission(exit);
    assert(level.intermissiontime == 10 && QM_IsOpen());
    assert(!strcmp(music_track, PP_MISSION_COMPLETE_MUSIC));
    assert(first->client->ps.pmove.pm_type == PM_FREEZE);
    assert(!QM_Frame());
    assert(strstr(layouts[1], "qmup 00000"));
    assert(strstr(layouts[1], "940 Sprues") && strstr(layouts[1], "20 found"));
    shop_input(first, 0, 0, BUTTON_ATTACK); /* Held fire on entry is ignored. */
    for (int i = 0; i < 5; ++i)
        shop_input(first, 0, 0, BUTTON_ATTACK);
    assert(first->health == 162 && first->max_health == 200);
    assert(first->client->quartermaster.progress.tier[QM_HEALTH] == 4);
    assert(first->client->quartermaster.progress.sprues == 90);
    assert(!QM_Frame() && strstr(layouts[1], "qmup 40000"));
    assert(strstr(layouts[1], "Capacity   200"));
    shop_input(first, 0, 200, 0); /* Resupply tab. */
    assert(!QM_Frame() && strstr(layouts[1], "qmres"));
    shop_input(first, 0, 0, BUTTON_ATTACK);
    assert(first->health == 187 && first->client->quartermaster.progress.sprues == 75);
    shop_input(first, 0, 0, BUTTON_ATTACK);
    assert(first->health == 200 && first->client->quartermaster.progress.sprues == 67);
    shop_input(first, 0, 0, BUTTON_ATTACK);
    assert(first->client->quartermaster.progress.sprues == 67);
    shop_input(first, 200, 0, 0); /* Up wraps from Health to Ready. */
    shop_input(first, 0, 0, BUTTON_ATTACK);
    shop_input(second, 0, 0, BUTTON_ANY); /* Any-key exit must stay disabled. */
    assert(!QM_Frame() && strstr(layouts[2], "Squad ready 1/2"));
    assert(strstr(layouts[1], "67 Sprues") && strstr(layouts[2], "940 Sprues"));
    assert(strstr(layouts[1], "FIRE SELECT")); /* All resupply rows fit in the layout message. */
    shop_input(first, 0, 0, BUTTON_ATTACK); /* Unready while the squad shops. */
    assert(!QM_Frame() && strstr(layouts[2], "Squad ready 0/2"));
    shop_input(first, 0, 0, BUTTON_ATTACK);
    second->client->pers.connected = false;
    assert(QM_Frame()); /* A departed player cannot hold up the squad. */
    second->client->pers.connected = true;
    shop_input(second, -200, 0, 0); /* Vest. */
    shop_input(second, 0, 0, BUTTON_ATTACK);
    assert(QM_ArmorCap(second->client) == 125 && QM_ArmorPoints(second) == 25);
    shop_input(second, -200, 0, 0); /* Bandolier. */
    shop_input(second, 0, 0, BUTTON_ATTACK);
    assert(QM_AmmoCap(second->client, AMMO_LIGHT_BULLETS) == 200);
    shop_input(second, 0, 200, 0);
    shop_input(second, 200, 0, 0);
    shop_input(second, 0, 0, BUTTON_ATTACK);
    assert(QM_Frame()); /* Both co-op players are ready. */

    WriteGame(path, false);
    ReadGame(path);
    assert(game.clients[0].quartermaster.progress.sprues == 67);
    assert(game.clients[0].pers.health == 200 && game.clients[0].pers.max_health == 200);
    assert(game.clients[1].quartermaster.progress.tier[QM_BANDOLIER] == 1);
    assert(game.clients[1].quartermaster.progress.tier[QM_ARMOR] == 1);
    unlink(path);

    reset();
    coop->value = 0;
    Q_strlcpy(level.mapname, "PP_SANDSTORM_BRIEFING", sizeof(level.mapname));
    exit = G_Spawn();
    exit->map = "pp_garden_infiltration";
    BeginIntermission(exit);
    assert(level.intermission_state == INTERMISSION_EXIT && !music_track[0]);

    reset();
    Q_strlcpy(level.mapname, "pp_sandbreak", sizeof(level.mapname));
    exit = G_Spawn();
    exit->map = "pp_sandbreak_end";
    BeginIntermission(exit);
    assert(level.intermission_state == INTERMISSION_EXIT && !music_track[0]);
}
static void test_savegame(const char *path)
{
    edict_t *self, *first, *last;
    int i, index, event_index;
    reset(); event_index = counter() - g_edicts; self = extract(4);
    index = self - g_edicts;
    restore(path); self = &g_edicts[index];
    assert(self->use && !self->think && self->solid == SOLID_NOT);
    self->use(self, NULL, &g_edicts[1]);
    g_edicts[2].s.origin[0] = 200;
    restore(path); self = &g_edicts[index];
    assert(self->think == platoon_extract_think);
    tick(self); assert(!self->count);
    g_edicts[2].s.origin[0] = 0;
    tick(self); assert(self->count && g_edicts[event_index].count == 98);
    restore(path); self = &g_edicts[index];
    assert(self->count && !self->use && !self->think);

    reset(); event_index = counter() - g_edicts;
    first = corner("takeoff", "landing", 0, 0, 30);
    first->wait = .5f; first->pathtarget = "arrival";
    last = corner("landing", NULL, 50, 0, 30);
    last->pathtarget = "arrival";
    self = dropship(1); index = self - g_edicts;
    restore(path); self = &g_edicts[index];
    assert(self->use && !self->count && self->svflags & SVF_NOCLIENT);
    self->use(self, NULL, &g_edicts[1]); tick(self);
    restore(path); self = &g_edicts[index];
    assert(self->think == platoon_dropship_think && self->movetarget == first);
    assert(self->activator == &g_edicts[1]);
    tick(self); tick(self); restore(path); self = &g_edicts[index];
    assert(self->movetarget == last && g_edicts[event_index].count == 98);
    for (i = 0; i < 20; i++) tick(self);
    assert(g_edicts[event_index].count == 97 && !self->nextthink);
    restore(path); assert(!g_edicts[index].nextthink);
    unlink(path);
}
static void test_quartermaster_weapons(const char *path)
{
    edict_t *first = &g_edicts[1], *second = &g_edicts[2];
    gitem_t *shotgun = FindItem("Shotgun"), *smg = FindItem("SMG");
    gitem_t *rockets = FindItem("Rocket Launcher"), *light = FindItem("Light Bullets");
    int smg_index = ITEM_INDEX(smg), shotgun_index = ITEM_INDEX(shotgun);
    int light_index = ITEM_INDEX(light);

    reset();
    coop->value = 1;
    Q_strlcpy(level.mapname, "pp_quartermaster_test", sizeof(level.mapname));
    QM_RecordMapWeapon(shotgun);
    QM_RecordMapWeapon(shotgun);
    QM_RecordMapWeapon(smg);
    QM_RecordMapWeapon(rockets);
    QM_RecordMapWeapon(light);
    first->client->pers.inventory[shotgun_index] = 1;
    first->client->pers.inventory[ITEM_INDEX(rockets)] = 1;
    second->client->pers.inventory[ITEM_INDEX(rockets)] = 1;
    first->client->pers.inventory[light_index] = 145;
    first->client->quartermaster.progress.sprues = 174;
    second->client->quartermaster.progress.sprues = 350;
    G_Spawn()->classname = "info_player_intermission";
    edict_t *exit = G_Spawn();
    exit->map = "pp_garden_infiltration";
    BeginIntermission(exit);

    for (int i = 1; i <= 2; i++)
    {
        shop_input(&g_edicts[i], 0, 0, 0);
        shop_input(&g_edicts[i], 0, 200, 0);
        shop_input(&g_edicts[i], 0, 200, 0);
    }
    assert(!QM_Frame());
    assert(strstr(layouts[1], "qmweap weapon_smg") && strstr(layouts[1], "Includes 5 Light Bullets"));
    assert(!strstr(layouts[1], "Shotgun") && !strstr(layouts[1], "Rocket Launcher"));
    assert(!strstr(layouts[1], "Rifle"));
    assert(strstr(layouts[2], "qmweap weapon_shotgun"));

    shop_input(first, 0, 0, BUTTON_ATTACK);
    assert(first->client->quartermaster.progress.sprues == 174);
    assert(first->client->pers.inventory[smg_index] == 0);
    first->client->quartermaster.progress.sprues = 175;
    shop_input(first, 0, 0, BUTTON_ATTACK);
    assert(first->client->quartermaster.progress.sprues == 0);
    assert(first->client->pers.inventory[smg_index] == 1);
    assert(first->client->pers.inventory[light_index] == 150);
    assert(!QM_Frame() && strstr(layouts[1], "No missed weapons this mission"));
    assert(strstr(layouts[2], "SMG") && !second->client->pers.inventory[smg_index]);

    shop_input(second, 0, 0, BUTTON_ATTACK);
    assert(!QM_Frame() && strstr(layouts[2], "qmweap weapon_smg"));
    assert(second->client->pers.inventory[shotgun_index] == 1);
    shop_input(first, 0, 0, BUTTON_ATTACK);
    assert(!QM_Frame() && strstr(layouts[2], "Squad ready 1/2"));
    shop_input(second, 0, 0, BUTTON_ATTACK);
    assert(second->client->quartermaster.progress.sprues == 0);
    assert(second->client->pers.inventory[smg_index] == 1);
    shop_input(second, 0, 0, BUTTON_ATTACK);
    assert(QM_Frame());

    WriteGame(path, false);
    ReadGame(path);
    assert(game.clients[0].pers.inventory[smg_index] == 1);
    assert(game.clients[1].pers.inventory[shotgun_index] == 1);
    unlink(path);
}

static void test_quartermaster_resupply(void)
{
    edict_t *first = &g_edicts[1], *second = &g_edicts[2];
    gitem_t *mortar = FindItem("Mortar Rounds");
    const char *classes[] = {"weapon_blaster", "weapon_machinegun", "weapon_shotgun",
        "weapon_railgun", "weapon_grenadelauncher", "weapon_rocketlauncher",
        "weapon_hyperblaster", "weapon_bfg"};

    reset();
    coop->value = 1;
    Q_strlcpy(level.mapname, "pp_quartermaster_test", sizeof(level.mapname));
    first->client->pers.inventory[ITEM_INDEX(FindItemByClassname("weapon_blaster"))] = 1;
    first->client->pers.inventory[ITEM_INDEX(FindItem("Rockets"))] = 5;
    for (int i = 0; i < ARRLEN(classes); i++)
    {
        second->client->pers.inventory[ITEM_INDEX(FindItemByClassname(classes[i]))] = 1;
    }
    second->client->quartermaster.progress.sprues = 300;
    G_Spawn()->classname = "info_player_intermission";
    edict_t *exit = G_Spawn();
    exit->map = "pp_garden_infiltration";
    BeginIntermission(exit);

    QM_Shortcut(first, "prev");
    QM_Shortcut(second, "2");
    assert(!QM_Frame() && strstr(layouts[1], "qmweap") && strstr(layouts[2], "qmres"));
    QM_Shortcut(first, "next");
    QM_Shortcut(first, "2");
    QM_Shortcut(first, "down");
    QM_Shortcut(first, "down");
    assert(!QM_Frame() && strstr(layouts[1], "qmsupply light"));
    assert(strstr(layouts[1], "Grenades") && !strstr(layouts[1], "Rockets"));
    assert(!strstr(layouts[1], "Mortar Rounds") && !strstr(layouts[1], "Shells"));
    assert(strstr(layouts[2], "Mortar Rounds") && strstr(layouts[2], "FIRE SELECT"));
    QM_Shortcut(second, "up"); /* Ready. */
    QM_Shortcut(second, "up"); /* Mortar is the last supply. */
    assert(!QM_Frame() && strstr(layouts[2], "qmsupply mortar"));
    assert(strstr(layouts[2], " 300"));
    shop_input(second, 0, 0, 0);
    shop_input(second, 0, 0, BUTTON_ATTACK);
    assert(second->client->quartermaster.progress.sprues == 0);
    assert(second->client->pers.inventory[ITEM_INDEX(mortar)] == mortar->quantity);
}

int main(int argc, char **argv)
{
    assert(argc == 2);
    gi.linkentity = link_entity; gi.unlinkentity = unlink_entity;
    gi.setmodel = set_model; gi.modelindex = gi.soundindex = gi.imageindex = model_index;
    gi.configstring = config_string;
    gi.TagMalloc = allocate; gi.FreeTags = no_free;
    gi.dprintf = print; gi.error = error;
    gi.WriteByte = write_byte; gi.WriteString = write_string; gi.unicast = unicast;
    gi.centerprintf = center_print;
    gi.cprintf = client_print;
    game.maxclients = 2; game.maxentities = 96;
    clients.value = 2; maxclients = &clients;
    entities.value = 96; maxentities = &entities;
    deathmatch = &zero; coop = &cooperative;
    game.clients = calloc(game.maxclients, sizeof(*game.clients));
    g_edicts = calloc(game.maxentities, sizeof(*g_edicts));
    InitItems();
    SetItemNames();
    test_extraction(); test_dropship_spawn_contract(); test_flight_vector_speed(); test_flight(); test_savegame(argv[1]);
    test_dropship_turn(argv[1]);
    test_legacy_dropship_media_restore(argv[1]);
    test_outbound_flight_and_camera(argv[1]);
    test_quartermaster(argv[1]);
    test_quartermaster_weapons(argv[1]);
    test_quartermaster_resupply();
    puts("Sandstorm extraction, cinematic camera, Quartermaster purchases, co-op ready and save/load passed");
    return 0;
}
