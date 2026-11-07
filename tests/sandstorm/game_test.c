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

static cvar_t clients, zero, cooperative;
static int center_calls[3];
static char center_text[3][128];
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
static int model_index(char *name) { (void)name; return 1; }
static void no_free(int tag) { (void)tag; }
static void *allocate(int size, int tag) { (void)tag; return calloc(1, size); }
static void unlink_entity(edict_t *self) { (void)self; }
static void write_byte(int value) { (void)value; }
static void write_string(char *value) { (void)value; }
static void unicast(edict_t *ent, qboolean reliable) { (void)ent; (void)reliable; }
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
    memset(center_calls, 0, sizeof(center_calls));
    memset(center_text, 0, sizeof(center_text));
    globals.num_edicts = game.maxclients + 1;
    level.time = 10;
    g_edicts[0].inuse = true;
    g_edicts[0].classname = "worldspawn";
    for (i = 1; i <= game.maxclients; i++)
    {
        g_edicts[i].inuse = true;
        g_edicts[i].classname = "player";
        g_edicts[i].health = 100;
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
    return self;
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
    assert(ship->count == 2 && !ship->nextthink && ship->s.origin[2] == 30);

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
    assert(level.intermissiontime == 17 && !level.exitintermission);
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
    assert(level.intermissiontime == 17 && !level.exitintermission);
    memset(&input, 0, sizeof(input));
    input.buttons = BUTTON_ANY;
    level.time = 21.9f;
    ClientThink(&g_edicts[1], &input);
    assert(!level.exitintermission);
    level.time = 22.1f;
    ClientThink(&g_edicts[2], &input);
    assert(level.exitintermission);
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
int main(int argc, char **argv)
{
    assert(argc == 2);
    gi.linkentity = link_entity; gi.unlinkentity = unlink_entity;
    gi.setmodel = set_model; gi.modelindex = gi.soundindex = gi.imageindex = model_index;
    gi.TagMalloc = allocate; gi.FreeTags = no_free;
    gi.dprintf = print; gi.error = error;
    gi.WriteByte = write_byte; gi.WriteString = write_string; gi.unicast = unicast;
    gi.centerprintf = center_print;
    game.maxclients = 2; game.maxentities = 96;
    clients.value = 2; maxclients = &clients;
    deathmatch = &zero; coop = &cooperative;
    game.clients = calloc(game.maxclients, sizeof(*game.clients));
    g_edicts = calloc(game.maxentities, sizeof(*g_edicts));
    test_extraction(); test_flight(); test_savegame(argv[1]);
    test_outbound_flight_and_camera(argv[1]);
    puts("Sandstorm extraction, dropship round trip, cinematic camera and save/load passed");
    return 0;
}
