#include "../../src/game/header/local.h"
#include <assert.h>
#include <stdarg.h>
#include <stddef.h>
#include <unistd.h>

extern void SP_monster_plastic_tank(edict_t *self);
extern void M_MoveFrame(edict_t *self);

#include "../vehicle_objectives/targets.h"

static cvar_t zero, one, max_clients;
static int blocked_sight, blocked_shots, shot_traces, links;
static char models[64][MAX_QPATH];
static int model_count;

static float angle_difference(float a, float b)
{
    return fmodf(a - b + 540, 360) - 180;
}

static int model_index(char *name)
{
    int i;
    for (i = 1; i <= model_count; i++)
        if (!strcmp(models[i], name)) return i;
    assert(model_count + 1 < 64);
    snprintf(models[++model_count], MAX_QPATH, "%s", name);
    return model_count;
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
    links++;
    ent->linkcount++;
    VectorAdd(ent->s.origin, ent->mins, ent->absmin);
    VectorAdd(ent->s.origin, ent->maxs, ent->absmax);
    VectorSubtract(ent->maxs, ent->mins, ent->size);
}

static void unlink_entity(edict_t *ent) { (void)ent; }
static int box_edicts(vec3_t mins, vec3_t maxs, edict_t **list,
        int maxcount, int areatype)
{
    (void)mins; (void)maxs; (void)list; (void)maxcount; (void)areatype;
    return 0;
}

static trace_t trace_world(vec3_t start, vec3_t mins, vec3_t maxs,
        vec3_t end, edict_t *passent, int mask)
{
    trace_t trace = {0};
    (void)start; (void)mins; (void)maxs; (void)passent;
    trace.fraction = 1;
    trace.plane.normal[2] = 1;
    VectorCopy(end, trace.endpos);
    if (mask == MASK_SHOT) shot_traces++;
    if ((blocked_sight && mask == MASK_OPAQUE) ||
            (blocked_shots && mask == MASK_SHOT))
    {
        trace.fraction = 0.5f;
        trace.ent = &g_edicts[0];
    }
    return trace;
}

static int point_contents(vec3_t point) { (void)point; return 0; }
static void write_byte(int value) { (void)value; }
static void write_short(int value) { (void)value; }
static void write_vector(vec3_t value) { (void)value; }
static void multicast(vec3_t point, multicast_t destination)
{
    (void)point; (void)destination;
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

static edict_t *spawn_tank(int spawnflags)
{
    edict_t *tank = &g_edicts[2], *enemy = &g_edicts[1];
    memset(g_edicts, 0, game.maxentities * sizeof(*g_edicts));
    memset(&level, 0, sizeof(level));
    memset(&st, 0, sizeof(st));
    memset(game.clients, 0, game.maxclients * sizeof(*game.clients));
    blocked_sight = blocked_shots = shot_traces = links = 0;
    level.time = 10;
    globals.num_edicts = 3;
    g_edicts[0].inuse = true;
    enemy->inuse = true;
    enemy->health = 100;
    enemy->classname = "player";
    enemy->viewheight = 22;
    enemy->light_level = 128;
    enemy->client = &game.clients[0];
    VectorSet(enemy->s.origin, 512, 0, 24);
    tank->inuse = true;
    tank->classname = "monster_plastic_tank";
    tank->spawnflags = spawnflags;
    if (spawnflags & 2) tank->targetname = "tank_trigger";
    VectorSet(tank->s.origin, 0, 0, 24);
    SP_monster_plastic_tank(tank);
    tank->enemy = tank->goalentity = enemy;
    tank->groundentity = &g_edicts[0];
    return tank;
}

static edict_t *new_tank(void) { return spawn_tank(0); }

static edict_t *turret_of(edict_t *tank)
{
    int i;
    for (i = 3; i < globals.num_edicts; i++)
    {
        edict_t *ent = &g_edicts[i];
        if (ent->inuse && ent->owner == tank && ent->think &&
                (!ent->classname || strcmp(ent->classname, "rocket")))
            return ent;
    }
    return NULL;
}

static edict_t *last_rocket(void)
{
    int i;
    edict_t *rocket = NULL;
    for (i = 3; i < globals.num_edicts; i++)
        if (g_edicts[i].inuse && g_edicts[i].classname &&
                !strcmp(g_edicts[i].classname, "rocket"))
            rocket = &g_edicts[i];
    return rocket;
}

static int rockets(void)
{
    int i, count = 0;
    for (i = 3; i < globals.num_edicts; i++)
        if (g_edicts[i].inuse && g_edicts[i].classname &&
                !strcmp(g_edicts[i].classname, "rocket")) count++;
    return count;
}

static void turret_tick(edict_t *tank)
{
    edict_t *turret = turret_of(tank);
    level.framenum++;
    level.time = 10 + level.framenum * FRAMETIME;
    if (turret) turret->think(turret);
}

static void tick(edict_t *tank)
{
    turret_tick(tank);
    M_MoveFrame(tank);
}

static void align_turret(edict_t *tank)
{
    int i;
    for (i = 0; i < 30; i++) turret_tick(tank);
}

static void begin_attack(edict_t *tank)
{
    tank->monsterinfo.attack(tank);
    tank->s.frame = -1;
}

static void test_spawn_and_slow_motion(void)
{
    edict_t *tank = new_tank(), *turret = turret_of(tank);
    int i;
    assert(tank->inuse && tank->health >= 500 && tank->mass >= 500);
    assert(tank->solid == SOLID_BBOX && tank->movetype == MOVETYPE_STEP);
    assert(tank->mins[0] == -56 && tank->mins[1] == -42 && tank->mins[2] == -24);
    assert(tank->maxs[0] == 56 && tank->maxs[1] == 42 && tank->maxs[2] == 48);
    assert(tank->monsterinfo.stand && tank->monsterinfo.walk && tank->monsterinfo.run);
    assert(tank->monsterinfo.attack && tank->monsterinfo.checkattack && tank->pain && tank->die);
    assert(tank->svflags & SVF_MONSTER);
    assert(tank->s.renderfx & RF_PP_ENEMY_COLOR);
    assert(level.total_monsters == 1);
    assert(turret && turret->s.modelindex && turret->s.modelindex != tank->s.modelindex);
    assert(turret->solid == SOLID_NOT && !(turret->svflags & SVF_MONSTER));
    assert(turret->s.origin[0] == tank->s.origin[0]);
    assert(turret->s.origin[1] == tank->s.origin[1]);
    assert(turret->s.origin[2] == tank->s.origin[2] + 24);
    turret_tick(tank);
    assert(turret->s.renderfx & RF_PP_ENEMY_COLOR);
    turret->s.renderfx |= RF_GLOW;
    tank->s.renderfx = (tank->s.renderfx & ~RF_PP_ENEMY_COLOR) | RF_PP_FRIENDLY_COLOR;
    turret_tick(tank);
    assert((turret->s.renderfx & RF_PP_FRIENDLY_COLOR) && !(turret->s.renderfx & RF_PP_ENEMY_COLOR));
    assert(turret->s.renderfx & RF_GLOW);
    tank->s.renderfx = (tank->s.renderfx & ~RF_PP_FRIENDLY_COLOR) | RF_PP_ENEMY_COLOR;
    turret_tick(tank);
    assert((turret->s.renderfx & RF_PP_ENEMY_COLOR) && !(turret->s.renderfx & RF_PP_FRIENDLY_COLOR));
    tank->monsterinfo.walk(tank);
    for (i = 0; i <= tank->monsterinfo.currentmove->lastframe -
            tank->monsterinfo.currentmove->firstframe; i++)
        assert(fabsf(tank->monsterinfo.currentmove->frame[i].dist) <= 4);
    tank->monsterinfo.run(tank);
    for (i = 0; i <= tank->monsterinfo.currentmove->lastframe -
            tank->monsterinfo.currentmove->firstframe; i++)
        assert(fabsf(tank->monsterinfo.currentmove->frame[i].dist) <= 4);
}

static void test_independent_turret(void)
{
    edict_t *tank = new_tank(), *turret = turret_of(tank);
    float yaw;
    assert(turret);
    VectorSet(tank->enemy->s.origin, 0, 512, 128);
    yaw = tank->s.angles[YAW];
    turret_tick(tank);
    assert(turret->s.angles[YAW] > 0 && turret->s.angles[YAW] < 90);
    align_turret(tank);
    assert(fabsf(angle_difference(turret->s.angles[YAW], 90)) < 2);
    assert(fabsf(angle_difference(turret->s.angles[PITCH], 0)) > 2);
    assert(tank->s.angles[YAW] == yaw);
    VectorSet(tank->s.origin, 123, -78, 44);
    tank->s.angles[YAW] = 135;
    turret_tick(tank);
    assert(turret->s.origin[0] == 123 && turret->s.origin[1] == -78);
    assert(turret->s.origin[2] == 68);
    assert(tank->s.angles[YAW] == 135);
    assert(fabsf(angle_difference(turret->s.angles[YAW], 135)) > 10);
}

static void test_rocket_and_recovery(void)
{
    edict_t *tank = new_tank(), *rocket;
    vec3_t aim, direction, offset;
    mmove_t *attack;
    int i;
    float started, first_shot, second_shot = 0;
    align_turret(tank);
    assert(tank->monsterinfo.checkattack(tank));
    begin_attack(tank);
    started = level.time;
    attack = tank->monsterinfo.currentmove;
    for (i = 0; i < 40 && !last_rocket(); i++) tick(tank);
    rocket = last_rocket();
    first_shot = level.time;
    assert(first_shot - started >= .69f && first_shot - started <= .81f);
    assert(rocket && rocket->owner == tank);
    assert(!strcmp(models[rocket->s.modelindex], "models/objects/rocket/tris.md2"));
    assert(rocket->movetype == MOVETYPE_FLYMISSILE && rocket->s.effects & EF_ROCKET);
    assert(rocket->touch && rocket->think == G_FreeEdict);
    assert(rocket->dmg > 0 && rocket->radius_dmg > 0 && rocket->dmg_radius > 0);
    VectorCopy(tank->enemy->s.origin, aim);
    aim[2] += tank->enemy->viewheight;
    VectorSubtract(aim, rocket->s.origin, aim);
    VectorNormalize(aim);
    VectorCopy(rocket->velocity, direction);
    assert(VectorNormalize(direction) >= 300);
    assert(DotProduct(aim, direction) > .98f);
    VectorSubtract(rocket->s.origin, tank->s.origin, offset);
    assert(offset[0] > tank->maxs[0]);
    assert(shot_traces > 0);
    tank->monsterinfo.aiflags |= AI_STAND_GROUND;
    for (i = 0; i < 60 && tank->monsterinfo.currentmove == attack; i++)
    {
        tick(tank);
        if (rockets() == 2 && !second_shot) second_shot = level.time;
    }
    assert(rockets() == 2);
    assert(second_shot - first_shot >= .49f && second_shot - first_shot <= .61f);
    assert(level.time - second_shot >= 1.99f);
    assert(tank->monsterinfo.currentmove != attack);
    assert(tank->monsterinfo.attack_finished > level.time);
    assert(!tank->monsterinfo.checkattack(tank));
}

static void test_ai_acquisition_and_independent_fire(void)
{
    edict_t *tank = new_tank();
    int i;
    /* Start through the real walkmonster initializer and sight acquisition. */
    tank->think(tank);
    tank->enemy = tank->goalentity = NULL;
    level.sight_client = &g_edicts[1];
    level.sight_entity_framenum = level.sound_entity_framenum =
        level.sound2_entity_framenum = -10;
    tick(tank);
    assert(tank->enemy == &g_edicts[1] && tank->goalentity == tank->enemy);
    for (i = 0; i < 50 && !rockets(); i++) tick(tank);
    assert(rockets() > 0);

    tank = new_tank();
    align_turret(tank);
    tank->s.angles[YAW] = 180;
    tank->monsterinfo.run(tank);
    /* Enter through ai_run/checkattack, not a direct attack call. */
    tick(tank);
    for (i = 0; i < 20 && !rockets(); i++) tick(tank);
    assert(rockets() > 0);
    assert(fabsf(angle_difference(tank->s.angles[YAW], 0)) > 90);
    assert(last_rocket()->velocity[0] > 500);
}

static void test_triggered_visibility_and_owner_reuse(void)
{
    edict_t *tank = spawn_tank(2), *turret = turret_of(tank), *replacement;
    assert(turret->svflags & SVF_NOCLIENT);
    tank->think(tank);
    turret_tick(tank);
    assert(tank->svflags & SVF_NOCLIENT);
    assert(turret->svflags & SVF_NOCLIENT);
    assert(tank->solid == SOLID_NOT && tank->nextthink == 0);
    tank->use(tank, &g_edicts[1], &g_edicts[1]);
    assert(tank->svflags & SVF_NOCLIENT);
    tank->think(tank);
    turret_tick(tank);
    assert(!(tank->svflags & SVF_NOCLIENT));
    assert(!(turret->svflags & SVF_NOCLIENT));
    assert(tank->solid == SOLID_BBOX && tank->enemy == &g_edicts[1]);

    tank = new_tank();
    turret = turret_of(tank);
    G_FreeEdict(tank);
    /* Reusing the owner's address for a new tank must not adopt its old child. */
    tank->inuse = true;
    tank->classname = "monster_plastic_tank";
    tank->health = 650;
    replacement = G_Spawn();
    replacement->owner = tank;
    tank->chain = replacement;
    turret->think(turret);
    assert(!turret->inuse && replacement->inuse);
    assert(tank->chain == replacement);

    deathmatch = &one;
    memset(g_edicts, 0, game.maxentities * sizeof(*g_edicts));
    memset(&level, 0, sizeof(level));
    globals.num_edicts = game.maxclients + BODY_QUEUE_SIZE + 2;
    tank = &g_edicts[globals.num_edicts - 1];
    tank->inuse = true;
    tank->classname = "monster_plastic_tank";
    SP_monster_plastic_tank(tank);
    assert(!tank->inuse && !turret_of(tank));
    assert(level.total_monsters == 0);
    deathmatch = &zero;
}

static void test_attack_guards(void)
{
    int state, i;
    for (state = 0; state < 9; state++)
    {
        edict_t *tank = new_tank();
        align_turret(tank);
        switch (state)
        {
            case 0: blocked_sight = 1; break;
            case 1: blocked_shots = 1; break;
            case 2: tank->enemy->health = 0; break;
            case 3: tank->enemy->inuse = false; break;
            case 4: tank->enemy = NULL; break;
            case 5: tank->monsterinfo.attack_finished = level.time + 10; break;
            case 6: tank->health = 0; tank->deadflag = DEAD_DEAD; break;
            case 7: tank->enemy->s.origin[0] = 100; break;
            case 8: tank->enemy->s.origin[0] = 2500; break;
        }
        assert(!tank->monsterinfo.checkattack(tank));
        begin_attack(tank);
        /* Direct attack callbacks must also respect the same safety guards. */
        for (i = 0; i < 15; i++) tick(tank);
        assert(rockets() == 0);
    }
    /* A barrier appearing after windup must prevent a shot from the muzzle. */
    {
        edict_t *tank = new_tank();
        align_turret(tank);
        begin_attack(tank);
        blocked_shots = 1;
        for (i = 0; i < 15; i++) tick(tank);
        assert(rockets() == 0);
    }
}

static void test_damage_and_cleanup(void)
{
    edict_t *tank = new_tank(), *turret = turret_of(tank);
    int health = tank->health, i;
    vec3_t direction = {1, 0, 0};
    T_Damage(tank, tank->enemy, tank->enemy, direction, tank->s.origin,
            vec3_origin, 25, 0, DAMAGE_NO_ARMOR, MOD_BLASTER);
    assert(tank->health == health - 25);
    T_Damage(tank, tank->enemy, tank->enemy, direction, tank->s.origin,
            vec3_origin, health + 100, 0, DAMAGE_NO_ARMOR, MOD_ROCKET);
    assert(!tank->inuse || (tank->health <= 0 && tank->deadflag == DEAD_DEAD));
    assert(level.killed_monsters == 1);
    assert(!turret->inuse);
    for (i = 0; i < 20 && tank->inuse && tank->monsterinfo.currentmove; i++) tick(tank);
    assert(rockets() == 0);
    tank = new_tank();
    turret = turret_of(tank);
    G_FreeEdict(tank);
    turret_tick(tank);
    /* A parent removed by a map target or administrative command cannot leak. */
    if (turret->inuse && turret->think) turret->think(turret);
    assert(!turret->inuse);
}

static void save_and_restore(const char *filename, edict_t *tank)
{
    edict_t *turret = turret_of(tank);
    ptrdiff_t turret_number = turret - g_edicts;
    mmove_t *move = tank->monsterinfo.currentmove;
    void (*attack)(edict_t *) = tank->monsterinfo.attack;
    void (*think)(edict_t *) = turret->think;
    WriteLevel(filename);
    ReadLevel(filename);
    tank = &g_edicts[2];
    turret = &g_edicts[turret_number];
    assert(tank->monsterinfo.currentmove == move);
    assert(tank->monsterinfo.attack == attack);
    assert(tank->monsterinfo.checkattack && tank->pain && tank->die);
    assert(tank->enemy == &g_edicts[1]);
    assert(turret_of(tank) == turret && turret->think == think);
    assert(turret->owner == tank);
}

static void test_savegame(const char *filename)
{
    edict_t *tank = new_tank();
    int i;
    save_and_restore(filename, tank);
    tank->monsterinfo.walk(tank);
    save_and_restore(filename, tank);
    tank->monsterinfo.run(tank);
    save_and_restore(filename, tank);
    align_turret(tank);
    begin_attack(tank);
    save_and_restore(filename, tank);
    for (i = 0; i < 40 && !rockets(); i++) tick(tank);
    assert(rockets() > 0);
    save_and_restore(filename, tank);
    unlink(filename);
}

static void test_death_objective_after_attack(const char *filename)
{
    int delayed, saved;
    for (delayed = 0; delayed < 2; delayed++)
    for (saved = 0; saved < 2; saved++)
    {
        edict_t *tank = new_tank(), *gate = objective_gate(tank), *use;
        ptrdiff_t gate_number = gate - g_edicts;
        vec3_t direction = {1, 0, 0};
        float authored_delay = delayed ? 3 : 0;
        level.time = 120; /* Reproduce a kill well into a mission, after aiming. */
        tank->delay = authored_delay;
        begin_attack(tank);
        if (saved)
        {
            save_and_restore(filename, tank);
            tank = &g_edicts[2];
            gate = &g_edicts[gate_number];
        }
        T_Damage(tank, tank->enemy, tank->enemy, direction, tank->s.origin,
                vec3_origin, tank->health + 100, 0, DAMAGE_NO_ARMOR, MOD_ROCKET);
        use = G_Find(NULL, FOFS(classname), "DelayedUse");
        if (delayed)
        {
            assert(gate->moveinfo.state == OBJECTIVE_GATE_BOTTOM);
            assert(use && fabsf(use->nextthink - (level.time + authored_delay)) < .001f);
            level.time = use->nextthink;
            use->think(use);
        }
        else
            assert(!use);
        assert_objective_opens(gate);
    }
    unlink(filename);
}

int main(int argc, char **argv)
{
    assert(argc == 2);
    gi.modelindex = model_index;
    gi.soundindex = sound_index;
    gi.sound = sound_effect;
    gi.linkentity = link_entity;
    gi.unlinkentity = unlink_entity;
    gi.BoxEdicts = box_edicts;
    gi.trace = trace_world;
    gi.pointcontents = point_contents;
    gi.WriteByte = write_byte;
    gi.WriteShort = write_short;
    gi.WritePosition = write_vector;
    gi.WriteDir = write_vector;
    gi.multicast = multicast;
    gi.TagMalloc = allocate;
    gi.FreeTags = no_free;
    gi.dprintf = debug_print;
    gi.error = error;
    one.value = 1;
    deathmatch = coop = dmflags = skill = g_fix_triggered = g_monsterfootsteps = &zero;
    max_clients.value = 1;
    maxclients = &max_clients;
    game.maxclients = 1;
    game.maxentities = 64;
    game.clients = calloc(game.maxclients, sizeof(*game.clients));
    g_edicts = calloc(game.maxentities, sizeof(*g_edicts));
    test_spawn_and_slow_motion();
    test_independent_turret();
    test_rocket_and_recovery();
    test_ai_acquisition_and_independent_fire();
    test_triggered_visibility_and_owner_reuse();
    test_attack_guards();
    test_damage_and_cleanup();
    test_savegame(argv[1]);
    test_death_objective_after_attack(argv[1]);
    puts("heavy tank spawn, independent turret, rockets, death objectives, authored delays and save/load passed");
    return 0;
}
