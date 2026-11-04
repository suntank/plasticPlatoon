#include "../../src/game/header/local.h"
#include "../../src/game/monster/soldier/soldier.h"
#include <assert.h>
#include <stdarg.h>
#include <unistd.h>

extern void SP_monster_soldier_heavy(edict_t *self);
extern void M_MoveFrame(edict_t *self);
extern void soldier_heavy_fire(edict_t *self);
extern void soldier_heavy_raise(edict_t *self);
extern void soldier_heavy_recover(edict_t *self);
extern void soldier_fire(edict_t *self, int flash_number);
extern mmove_t soldier_move_death2;

static cvar_t zero, max_clients;
static int shots, message_bytes, message_type;
static int blocked_sight, blocked_muzzle, blocked_ceiling, ceiling_checks;
static int linked, last_shot_frame;
static float last_shot_time;
static float minimum_shot_interval;

static int model_index(char *name)
{
    if (!strcmp(name, "models/monsters/soldier/tris.md2")) return 100;
    if (!strcmp(name, "models/monsters/soldier/weapon_heavy.md2")) return 104;
    return 101;
}

static int sound_index(char *name) { (void)name; return 1; }
static void sound_effect(edict_t *ent, int channel, int index,
        float volume, float attenuation, float offset)
{
    (void)ent; (void)channel; (void)index;
    (void)volume; (void)attenuation; (void)offset;
}

static void link_entity(edict_t *ent)
{
    linked++;
    ent->linkcount++;
    VectorAdd(ent->s.origin, ent->mins, ent->absmin);
    VectorAdd(ent->s.origin, ent->maxs, ent->absmax);
    VectorSubtract(ent->maxs, ent->mins, ent->size);
}

static trace_t trace_world(vec3_t start, vec3_t mins, vec3_t maxs,
        vec3_t end, edict_t *passent, int mask)
{
    trace_t trace = {0};
    vec3_t delta;
    (void)mins; (void)passent;
    trace.fraction = 1;
    trace.ent = &g_edicts[0];
    trace.plane.normal[2] = 1;
    VectorCopy(end, trace.endpos);
    VectorSubtract(end, start, delta);
    if (maxs && maxs[2] > 0 && VectorCompare(start, end))
    {
        ceiling_checks++;
        if (blocked_ceiling)
        {
            trace.fraction = 0;
            trace.startsolid = trace.allsolid = true;
        }
    }
    if ((blocked_sight && (mask == MASK_OPAQUE ||
                    (mask == MASK_SHOT && VectorLength(delta) >= 100 &&
                     VectorLength(delta) < 2000))) ||
            (blocked_muzzle && mask == MASK_SHOT && VectorLength(delta) < 100))
    {
        trace.fraction = 0.5;
    }
    return trace;
}

static int point_contents(vec3_t point) { (void)point; return 0; }
static void write_byte(int value)
{
    if (!message_bytes) message_type = value;
    message_bytes++;
}
static void write_short(int value) { (void)value; message_bytes++; }
static void multicast(vec3_t point, multicast_t destination)
{
    (void)point; (void)destination;
    if (message_type == svc_muzzleflash2)
    {
        edict_t *heavy = &g_edicts[2];
        assert(message_bytes == 3);
        assert(heavy->monsterinfo.aiflags & AI_DUCKED);
        assert(heavy->groundentity);
        assert(heavy->maxs[2] == 0 && heavy->viewheight == 0);
        assert(heavy->velocity[0] == 0 && heavy->velocity[1] == 0);
        if (shots && level.time > last_shot_time)
        {
            float interval = level.time - last_shot_time;
            if (interval < minimum_shot_interval) minimum_shot_interval = interval;
        }
        last_shot_time = level.time;
        last_shot_frame = heavy->s.frame;
        shots++;
    }
    message_bytes = 0;
}

static void no_free(int tag) { (void)tag; }
static void *allocate(int bytes, int tag) { (void)tag; return calloc(1, bytes); }
static void debug_print(const char *fmt, ...) { (void)fmt; }
static YQ2_ATTR_NORETURN void error(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    vfprintf(stderr, fmt, ap);
    va_end(ap);
    abort();
}

static edict_t *new_heavy(void)
{
    edict_t *heavy = &g_edicts[2], *enemy = &g_edicts[1];
    memset(g_edicts, 0, game.maxentities * sizeof(*g_edicts));
    memset(&level, 0, sizeof(level));
    memset(&st, 0, sizeof(st));
    shots = message_bytes = blocked_sight = blocked_muzzle = blocked_ceiling = 0;
    ceiling_checks = linked = 0;
    last_shot_time = 0;
    minimum_shot_interval = 1000;
    level.time = 10;
    globals.num_edicts = 3;
    g_edicts[0].inuse = true;
    enemy->inuse = true;
    enemy->health = 100;
    enemy->viewheight = 22;
    enemy->client = &game.clients[0];
    VectorSet(enemy->s.origin, 512, 0, 24);
    heavy->inuse = true;
    heavy->classname = "monster_soldier_heavy";
    VectorSet(heavy->s.origin, 0, 0, 24);
    SP_monster_soldier_heavy(heavy);
    heavy->enemy = heavy->goalentity = enemy;
    heavy->groundentity = &g_edicts[0];
    return heavy;
}

static void tick(edict_t *heavy)
{
    level.framenum++;
    level.time = 10 + level.framenum * FRAMETIME;
    M_MoveFrame(heavy);
}

static void begin_attack(edict_t *heavy)
{
    heavy->monsterinfo.attack(heavy);
    heavy->s.frame = -1;
}

static void begin_firing(edict_t *heavy)
{
    int i;
    begin_attack(heavy);
    for (i = 0; i < 12 && !shots; i++) tick(heavy);
    assert(shots == 1);
    assert(heavy->monsterinfo.aiflags & AI_DUCKED);
    assert(heavy->maxs[2] == 0 && heavy->viewheight == 0);
    assert(last_shot_frame == FRAME_attak303);
}

static void test_spawn_and_movement(void)
{
    edict_t *heavy = new_heavy();
    int i;
    assert(heavy->health == 180 && heavy->mass == 250);
    assert(heavy->s.modelindex == 100 && heavy->s.modelindex2 == 104);
    assert(heavy->maxs[2] == 32 && heavy->viewheight == 25);
    assert(heavy->monsterinfo.checkattack && heavy->pain && heavy->die);
    heavy->monsterinfo.walk(heavy);
    for (i = 0; i <= heavy->monsterinfo.currentmove->lastframe -
            heavy->monsterinfo.currentmove->firstframe; i++)
        assert(fabsf(heavy->monsterinfo.currentmove->frame[i].dist) <= 4);
    heavy->monsterinfo.run(heavy);
    for (i = 0; i <= heavy->monsterinfo.currentmove->lastframe -
            heavy->monsterinfo.currentmove->firstframe; i++)
        assert(fabsf(heavy->monsterinfo.currentmove->frame[i].dist) <= 4);
    soldier_heavy_fire(heavy);
    soldier_fire(heavy, 5);
    soldier_fire(heavy, 6);
    assert(shots == 0);
}

static void test_burst_and_recovery(void)
{
    edict_t *heavy = new_heavy();
    mmove_t *attack;
    int i;
    float first_shot;
    begin_firing(heavy);
    first_shot = level.time;
    attack = heavy->monsterinfo.currentmove;
    /* Finish through the actual animation engine, including held fire frames. */
    heavy->monsterinfo.aiflags |= AI_STAND_GROUND;
    for (i = 0; i < 50 && heavy->monsterinfo.currentmove == attack; i++) tick(heavy);
    assert(heavy->monsterinfo.currentmove != attack);
    assert(shots >= 14 && shots <= 17);
    assert(last_shot_time - first_shot >= 1.3f && last_shot_time - first_shot <= 1.7f);
    assert(minimum_shot_interval >= FRAMETIME - 0.001f);
    assert(!(heavy->monsterinfo.aiflags & (AI_DUCKED | AI_HOLD_FRAME)));
    assert(heavy->maxs[2] == 32 && heavy->viewheight == 25);
    assert(ceiling_checks > 0);
    assert(heavy->monsterinfo.attack_finished > level.time);
    assert(!heavy->monsterinfo.checkattack(heavy));
    soldier_heavy_raise(heavy);
    soldier_heavy_recover(heavy);
    assert(heavy->maxs[2] == 32 && heavy->viewheight == 25);
}

static void test_fire_guards(void)
{
    int state;
    for (state = 0; state < 12; state++)
    {
        edict_t *heavy = new_heavy();
        int before;
        begin_firing(heavy);
        before = shots;
        switch (state)
        {
            case 0: heavy->monsterinfo.aiflags &= ~AI_DUCKED; break;
            case 1: heavy->groundentity = NULL; break;
            case 2: heavy->velocity[0] = 5; break;
            case 3: heavy->enemy->health = 0; break;
            case 4: heavy->enemy->inuse = false; break;
            case 5: heavy->enemy = NULL; break;
            case 6: heavy->s.angles[YAW] = 180; break;
            case 7: blocked_sight = 1; break;
            case 8: blocked_muzzle = 1; break;
            case 9: heavy->health = 0; heavy->deadflag = DEAD_DEAD; break;
            case 10: heavy->velocity[2] = 5; break;
            case 11: heavy->s.frame = FRAME_runs01; break;
        }
        level.time += FRAMETIME;
        soldier_heavy_fire(heavy);
        assert(shots == before);
    }
}

static void test_attack_selection(void)
{
    edict_t *heavy = new_heavy();
    mmove_t *idle = heavy->monsterinfo.currentmove;
    assert(heavy->monsterinfo.checkattack(heavy));
    blocked_sight = 1;
    assert(!heavy->monsterinfo.checkattack(heavy));
    blocked_sight = 0;
    heavy->enemy->s.origin[0] = 1600;
    assert(!heavy->monsterinfo.checkattack(heavy));
    heavy->enemy->s.origin[0] = 512;
    heavy->groundentity = NULL;
    assert(!heavy->monsterinfo.checkattack(heavy));
    heavy->monsterinfo.attack(heavy);
    assert(heavy->monsterinfo.currentmove == idle);
    heavy->groundentity = &g_edicts[0];
    heavy->monsterinfo.attack_finished = level.time + 1;
    assert(!heavy->monsterinfo.checkattack(heavy));
    heavy->monsterinfo.attack(heavy);
    assert(heavy->monsterinfo.currentmove == idle);
    heavy->monsterinfo.attack_finished = 0;
    heavy->enemy->health = 0;
    assert(!heavy->monsterinfo.checkattack(heavy));
    heavy->monsterinfo.attack(heavy);
    assert(heavy->monsterinfo.currentmove == idle);
    assert(shots == 0);
}

static void test_ceiling_and_interruptions(void)
{
    edict_t *heavy = new_heavy();
    int i, before;
    begin_firing(heavy);
    before = shots;
    blocked_ceiling = 1;
    soldier_heavy_raise(heavy);
    assert(ceiling_checks > 0);
    assert(heavy->monsterinfo.aiflags & AI_DUCKED);
    assert(heavy->monsterinfo.nextframe == FRAME_attak306 ||
            (heavy->monsterinfo.aiflags & AI_HOLD_FRAME));
    assert(heavy->maxs[2] == 0 && heavy->viewheight == 0);
    for (i = 0; i < 8; i++) tick(heavy);
    assert(heavy->maxs[2] == 0);
    assert(shots == before);
    blocked_ceiling = 0;
    soldier_heavy_raise(heavy);
    assert(!(heavy->monsterinfo.aiflags & AI_DUCKED));
    assert(heavy->maxs[2] == 32 && heavy->viewheight == 25);
    soldier_heavy_fire(heavy);
    assert(shots == before);

    heavy = new_heavy();
    begin_firing(heavy);
    heavy->pain(heavy, heavy->enemy, 1, 20);
    assert(!(heavy->monsterinfo.aiflags & AI_HOLD_FRAME));
    assert(heavy->monsterinfo.attack_finished > level.time);
    for (i = 0; i < 4 && (heavy->monsterinfo.aiflags & AI_DUCKED); i++) tick(heavy);
    assert(!(heavy->monsterinfo.aiflags & AI_DUCKED));
    assert(heavy->maxs[2] == 32 && heavy->viewheight == 25);
    before = shots;
    soldier_heavy_fire(heavy);
    assert(shots == before);

    heavy = new_heavy();
    begin_firing(heavy);
    heavy->health = 0;
    heavy->die(heavy, heavy->enemy, heavy->enemy, 20, heavy->s.origin);
    assert(heavy->deadflag == DEAD_DEAD);
    assert(heavy->monsterinfo.currentmove == &soldier_move_death2);
    assert(!(heavy->monsterinfo.aiflags & AI_HOLD_FRAME));
    before = shots;
    heavy->s.frame = -1;
    for (i = 0; i < 40 && !(heavy->svflags & SVF_DEADMONSTER); i++) tick(heavy);
    soldier_fire(heavy, 5);
    soldier_fire(heavy, 6);
    assert(shots == before);
}

static void save_and_restore(const char *filename, edict_t *heavy)
{
    mmove_t *move = heavy->monsterinfo.currentmove;
    void (*stand)(edict_t *) = heavy->monsterinfo.stand;
    void (*attack)(edict_t *) = heavy->monsterinfo.attack;
    qboolean (*checkattack)(edict_t *) = heavy->monsterinfo.checkattack;
    WriteLevel(filename);
    ReadLevel(filename);
    heavy = &g_edicts[2];
    assert(heavy->monsterinfo.currentmove == move);
    assert(heavy->monsterinfo.stand == stand);
    assert(heavy->monsterinfo.attack == attack);
    assert(heavy->monsterinfo.checkattack == checkattack);
    assert(heavy->pain && heavy->die);
    assert(heavy->enemy == &g_edicts[1]);
}

static void test_savegame(const char *filename)
{
    edict_t *heavy = new_heavy();
    int before;
    save_and_restore(filename, heavy);
    heavy->monsterinfo.walk(heavy);
    save_and_restore(filename, heavy);
    heavy->monsterinfo.run(heavy);
    save_and_restore(filename, heavy);
    begin_firing(heavy);
    save_and_restore(filename, heavy);
    assert(heavy->monsterinfo.aiflags & AI_DUCKED);
    assert(heavy->maxs[2] == 0);
    before = shots;
    tick(heavy);
    assert(shots == before + 1);
    heavy->health = 0;
    heavy->die(heavy, heavy->enemy, heavy->enemy, 20, heavy->s.origin);
    save_and_restore(filename, heavy);
    heavy = new_heavy();
    heavy->pain(heavy, heavy->enemy, 1, 20);
    save_and_restore(filename, heavy);
    unlink(filename);
}

int main(int argc, char **argv)
{
    assert(argc == 2);
    gi.modelindex = model_index;
    gi.soundindex = sound_index;
    gi.sound = sound_effect;
    gi.linkentity = link_entity;
    gi.trace = trace_world;
    gi.pointcontents = point_contents;
    gi.WriteByte = write_byte;
    gi.WriteShort = write_short;
    gi.multicast = multicast;
    gi.TagMalloc = allocate;
    gi.FreeTags = no_free;
    gi.dprintf = debug_print;
    gi.error = error;
    deathmatch = coop = skill = g_fix_triggered = g_monsterfootsteps = &zero;
    max_clients.value = 1;
    maxclients = &max_clients;
    game.maxclients = 1;
    game.maxentities = 16;
    game.clients = calloc(game.maxclients, sizeof(*game.clients));
    g_edicts = calloc(game.maxentities, sizeof(*g_edicts));
    test_spawn_and_movement();
    test_burst_and_recovery();
    test_fire_guards();
    test_attack_selection();
    test_ceiling_and_interruptions();
    test_savegame(argv[1]);
    puts("heavy gunner spawn, deployed bursts, fire guards, recovery, death and save/load passed");
    return 0;
}
