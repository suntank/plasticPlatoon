#include "../../src/game/header/local.h"
#include <assert.h>
#include <stdarg.h>
#include <stddef.h>
#include <unistd.h>

extern void SP_monster_plastic_helicopter(edict_t *self);
extern void M_MoveFrame(edict_t *self);
extern void plastic_helicopter_machineguns(edict_t *self);
extern void plastic_helicopter_rockets(edict_t *self);

static cvar_t zero, one, max_clients, gravity, max_velocity;
static int blocked_sight, blocked_shots, blocked_motion, no_floor;
static int bullet_rays, explosions, message_byte, message_type, shots_traced;
static char models[64][MAX_QPATH];
static int model_count;
static csurface_t floor_surface = {"floor", 0, 0};

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
    trace_t tr = {0};
    vec3_t delta;
    float bottom = mins ? mins[2] : 0;
    (void)maxs; (void)passent;
    tr.fraction = 1;
    tr.plane.normal[2] = 1;
    VectorCopy(end, tr.endpos);
    VectorSubtract(end, start, delta);
    if (mask == MASK_SHOT || mask == (MASK_SHOT | MASK_WATER)) shots_traced++;
    if (mask == (MASK_SHOT | MASK_WATER) && VectorLength(delta) > 8000)
        bullet_rays++;
    if ((blocked_motion && mask == MASK_MONSTERSOLID) ||
            (blocked_sight && mask == MASK_OPAQUE) ||
            (blocked_shots && (mask == MASK_SHOT || mask == (MASK_SHOT | MASK_WATER))))
    {
        tr.fraction = .5f;
        tr.ent = &g_edicts[0];
        VectorMA(start, .5f, delta, tr.endpos);
    }
    else if (!no_floor && end[2] + bottom < 0 && end[2] < start[2] &&
            mask != MASK_OPAQUE && mask != MASK_SHOT &&
            mask != (MASK_SHOT | MASK_WATER))
    {
        tr.fraction = fmaxf(0, (start[2] + bottom) / (start[2] - end[2]));
        tr.ent = &g_edicts[0];
        tr.surface = &floor_surface;
        VectorMA(start, tr.fraction, delta, tr.endpos);
    }
    return tr;
}
static int point_contents(vec3_t point) { (void)point; return 0; }
static void write_byte(int value)
{
    if (!message_byte) message_type = value;
    else if (message_byte == 1 && message_type == svc_temp_entity &&
            (value == TE_EXPLOSION1 || value == TE_EXPLOSION2 ||
             value == TE_ROCKET_EXPLOSION)) explosions++;
    message_byte++;
}
static void write_short(int value) { (void)value; }
static void write_vector(vec3_t value) { (void)value; }
static void multicast(vec3_t point, multicast_t destination)
{
    (void)point; (void)destination;
    message_byte = 0;
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

static edict_t *spawn_helicopter(int spawnflags)
{
    int number = deathmatch->value ? game.maxclients + BODY_QUEUE_SIZE + 1 : 2;
    edict_t *self = &g_edicts[number], *enemy = &g_edicts[1];
    memset(g_edicts, 0, game.maxentities * sizeof(*g_edicts));
    memset(&level, 0, sizeof(level));
    memset(&st, 0, sizeof(st));
    memset(game.clients, 0, game.maxclients * sizeof(*game.clients));
    blocked_sight = blocked_shots = blocked_motion = no_floor = 0;
    bullet_rays = explosions = message_byte = message_type = shots_traced = 0;
    level.time = 10;
    globals.num_edicts = number + 1;
    level.sight_entity_framenum = level.sound_entity_framenum =
        level.sound2_entity_framenum = -10;
    g_edicts[0].inuse = true;
    g_edicts[0].solid = SOLID_BSP;
    enemy->inuse = true;
    enemy->health = 100;
    enemy->classname = "player";
    enemy->viewheight = 22;
    enemy->light_level = 128;
    enemy->client = &game.clients[0];
    VectorSet(enemy->s.origin, 640, 0, 24);
    G_InitEdict(self);
    self->classname = "monster_plastic_helicopter";
    self->spawnflags = spawnflags;
    if (spawnflags & 2) self->targetname = "helicopter_trigger";
    VectorSet(self->s.origin, 0, 0, 288);
    SP_monster_plastic_helicopter(self);
    self->enemy = self->goalentity = enemy;
    return self;
}
static edict_t *new_helicopter(void) { return spawn_helicopter(0); }
static edict_t *rotor(edict_t *self, const char *part)
{
    int i;
    for (i = 3; i < globals.num_edicts; i++)
    {
        edict_t *ent = &g_edicts[i];
        if (ent->inuse && ent->owner == self && ent->classname &&
                !strcmp(ent->classname, part)) return ent;
    }
    return NULL;
}
#define MAIN_ROTOR "plastic_helicopter_main_rotor"
#define TAIL_ROTOR "plastic_helicopter_tail_rotor"
static int rockets(void)
{
    int i, count = 0;
    for (i = 3; i < globals.num_edicts; i++)
        if (g_edicts[i].inuse && g_edicts[i].classname &&
                !strcmp(g_edicts[i].classname, "rocket")) count++;
    return count;
}
static void advance(void)
{
    level.framenum++;
    level.time = 10 + level.framenum * FRAMETIME;
}
static void rotor_thinks(void)
{
    int i;
    for (i = 3; i < globals.num_edicts; i++)
    {
        edict_t *ent = &g_edicts[i];
        if (ent->inuse && ent->think && ent->classname &&
                (!strcmp(ent->classname, MAIN_ROTOR) || !strcmp(ent->classname, TAIL_ROTOR)))
            ent->think(ent);
    }
}
static void tick(edict_t *self)
{
    advance();
    if (self->inuse)
    {
        if (self->deadflag == DEAD_DEAD) G_RunEntity(self);
        else M_MoveFrame(self);
    }
    rotor_thinks();
}
static void begin_attack(edict_t *self)
{
    self->monsterinfo.attack(self);
    self->s.frame = -1;
}
static void test_spawn_and_rotors(void)
{
    edict_t *self = new_helicopter();
    edict_t *main = rotor(self, MAIN_ROTOR), *tail = rotor(self, TAIL_ROTOR);
    vec3_t before_main, before_tail, forward, right, up, expected;
    int i;
    assert(self->inuse && self->health >= 400 && self->mass >= 300);
    assert(self->solid == SOLID_BBOX && self->movetype == MOVETYPE_STEP);
    assert(self->flags & FL_FLY);
    assert(self->svflags & SVF_MONSTER);
    assert(level.total_monsters == 1);
    assert(self->monsterinfo.stand && self->monsterinfo.walk && self->monsterinfo.run);
    assert(self->monsterinfo.attack && self->monsterinfo.checkattack && self->pain && self->die);
    assert(main && tail && main != tail);
    assert(main->s.modelindex != self->s.modelindex && tail->s.modelindex != main->s.modelindex);
    assert(main->solid == SOLID_NOT && tail->solid == SOLID_NOT);
    assert(!(main->svflags & SVF_MONSTER) && !(tail->svflags & SVF_MONSTER));
    VectorCopy(main->s.angles, before_main);
    VectorCopy(tail->s.angles, before_tail);
    advance(); rotor_thinks();
    assert(!VectorCompare(main->s.angles, before_main));
    assert(!VectorCompare(tail->s.angles, before_tail));
    VectorSet(self->s.origin, 123, -78, 320);
    VectorSet(self->s.angles, 12, 135, 17);
    advance(); rotor_thinks();
    AngleVectors(self->s.angles, forward, right, up);
    VectorMA(self->s.origin, 48, up, expected);
    for (i = 0; i < 3; i++) assert(fabsf(main->s.origin[i] - expected[i]) < .02f);
    VectorMA(self->s.origin, -88, forward, expected);
    VectorMA(expected, -8, right, expected);
    VectorMA(expected, 16, up, expected);
    for (i = 0; i < 3; i++) assert(fabsf(tail->s.origin[i] - expected[i]) < .02f);
}
static float angle_delta(float a, float b)
{
    return fmodf(a - b + 540, 360) - 180;
}
static void test_tail_rotor_axis_and_interpolation(void)
{
    edict_t *self = new_helicopter(), *tail = rotor(self, TAIL_ROTOR);
    vec3_t local, forward, right, up, expected, actual;
    int i;
    self->s.angles[YAW] = 90;
    tail->speed = 80;
    VectorSet(tail->s.angles, 80, 90, 0);
    for (i = 0; i < 8; i++)
    {
        advance(); rotor_thinks();
        assert(fabsf(angle_delta(tail->s.angles[YAW],90)) < 1.1f);
        assert(fabsf(angle_delta(tail->s.angles[ROLL],0)) < 1.1f);
        VectorSet(local,tail->speed,0,0);
        AngleVectors(local,actual,NULL,NULL);
        AngleVectors(self->s.angles,forward,right,up);
        VectorScale(forward,actual[0],expected);
        VectorMA(expected,-actual[1],right,expected);
        VectorMA(expected,actual[2],up,expected);
        AngleVectors(tail->s.angles,actual,NULL,NULL);
        assert(DotProduct(expected,actual) > .999f);
    }
}
static void test_acquisition_flight_and_patrol(void)
{
    edict_t *self = new_helicopter(), *enemy = self->enemy, *corner;
    vec3_t before;
    int i;
    self->think(self); /* The real flying monster startup and target acquisition. */
    self->enemy = self->goalentity = NULL;
    level.sight_client = enemy;
    tick(self);
    assert(self->enemy == enemy && self->goalentity == enemy);
    self->monsterinfo.attack_finished = level.time + 100;
    self->monsterinfo.run(self);
    VectorCopy(self->s.origin,before);
    for (i = 0; i < 6; i++) tick(self);
    assert(!VectorCompare(before,self->s.origin));
    assert(self->s.origin[2] >= self->pos1[2]-48 && !self->groundentity);
    assert(!rockets() && !bullet_rays);
    self = new_helicopter();
    self->enemy->s.origin[0] = 120;
    self->enemy->s.origin[2] = self->s.origin[2];
    self->monsterinfo.attack_finished = level.time + 100;
    self->monsterinfo.run(self);
    for (i = 0; i < 5; i++) tick(self);
    assert(self->s.origin[0] < -20); /* Retreat from nearby splash range. */
    blocked_motion = 1;
    VectorCopy(self->s.origin,before);
    for (i = 0; i < 5; i++) tick(self);
    assert(VectorCompare(before,self->s.origin)); /* Traces reject blocked movement. */
    self = new_helicopter();
    self->enemy = NULL;
    corner = G_Spawn();
    corner->classname = "path_corner";
    VectorSet(corner->s.origin,512,0,288);
    self->goalentity = self->movetarget = corner;
    self->monsterinfo.walk(self);
    for (i = 0; i < 5; i++) tick(self);
    assert(self->s.origin[0] > 20);
}
static void test_machinegun_burst(void)
{
    edict_t *self = new_helicopter();
    mmove_t *attack;
    float started = level.time;
    int i;
    self->wait = level.time + 20; /* Force guns while the rocket pods reload. */
    assert(self->monsterinfo.checkattack(self));
    begin_attack(self);
    attack = self->monsterinfo.currentmove;
    for (i = 0; i < 20 && self->monsterinfo.currentmove == attack; i++) tick(self);
    assert(bullet_rays == 8); /* Four short volleys from both guns. */
    assert(rockets() == 0 && shots_traced > bullet_rays);
    assert(level.time - started >= .7f);
    assert(self->monsterinfo.currentmove != attack);
    assert(self->monsterinfo.attack_finished > level.time);
    assert(!self->monsterinfo.checkattack(self));
}
static void test_paired_rockets(void)
{
    edict_t *self = new_helicopter();
    mmove_t *attack;
    int i, count = 0;
    float started = level.time;
    assert(self->monsterinfo.checkattack(self));
    begin_attack(self);
    attack = self->monsterinfo.currentmove;
    for (i = 0; i < 20 && self->monsterinfo.currentmove == attack; i++) tick(self);
    assert(rockets() == 2 && bullet_rays == 0);
    assert(level.time - started >= .7f && self->wait > level.time);
    for (i = 3; i < globals.num_edicts; i++)
    {
        edict_t *rocket = &g_edicts[i];
        vec3_t aim, direction;
        if (!rocket->inuse || !rocket->classname || strcmp(rocket->classname, "rocket")) continue;
        count++;
        assert(rocket->owner == self && rocket->movetype == MOVETYPE_FLYMISSILE);
        assert(rocket->s.effects & EF_ROCKET);
        assert(!strcmp(models[rocket->s.modelindex], "models/objects/rocket/tris.md2"));
        assert(rocket->touch && rocket->think == G_FreeEdict);
        assert(rocket->dmg > 0 && rocket->radius_dmg > 0 && rocket->dmg_radius > 0);
        VectorCopy(self->enemy->s.origin, aim);
        aim[2] += self->enemy->viewheight;
        VectorSubtract(aim, rocket->s.origin, aim);
        VectorNormalize(aim);
        VectorCopy(rocket->velocity, direction);
        assert(VectorNormalize(direction) >= 400);
        assert(DotProduct(aim, direction) > .98f);
    }
    assert(count == 2 && !self->monsterinfo.checkattack(self));
}
static void test_attack_safety(void)
{
    int state, i;
    for (state = 0; state < 7; state++)
    {
        edict_t *self = new_helicopter();
        begin_attack(self);
        switch (state)
        {
            case 0: blocked_sight = 1; break;
            case 1: blocked_shots = 1; break;
            case 2: self->enemy->health = 0; break;
            case 3: self->enemy->inuse = false; break;
            case 4: self->enemy = NULL; break;
            case 5: self->health = 0; self->deadflag = DEAD_DEAD; break;
            case 6: self->enemy->s.origin[0] = 4000; break;
        }
        assert(!self->monsterinfo.checkattack(self));
        plastic_helicopter_machineguns(self);
        plastic_helicopter_rockets(self);
        for (i = 0; i < 12 && self->deadflag != DEAD_DEAD; i++) tick(self);
        assert(rockets() == 0 && bullet_rays == 0);
    }
    {
        edict_t *self = new_helicopter();
        self->enemy->s.origin[0] = 120;
        self->enemy->s.origin[2] = self->s.origin[2];
        plastic_helicopter_rockets(self);
        assert(!rockets());
        self->wait = 0;
        begin_attack(self);
        for (i = 0; i < 9; i++) tick(self);
        assert(!rockets() && bullet_rays == 8);
    }
    {
        edict_t *self = new_helicopter();
        self->monsterinfo.attack_finished = level.time + 10;
        assert(!self->monsterinfo.checkattack(self));
        begin_attack(self);
        for (i = 0; i < 9; i++) tick(self);
        assert(!rockets() && !bullet_rays);
    }
}
static void test_triggered_and_owner_removal(void)
{
    edict_t *replacement_main, *replacement_tail;
    edict_t *self = spawn_helicopter(2);
    edict_t *main = rotor(self, MAIN_ROTOR), *tail = rotor(self, TAIL_ROTOR);
    assert(main && tail && (main->svflags & SVF_NOCLIENT) && (tail->svflags & SVF_NOCLIENT));
    self->think(self);
    advance(); rotor_thinks();
    assert(self->svflags & SVF_NOCLIENT);
    assert((main->svflags & SVF_NOCLIENT) && (tail->svflags & SVF_NOCLIENT));
    assert(self->solid == SOLID_NOT && self->nextthink == 0);
    self->use(self, &g_edicts[1], &g_edicts[1]);
    self->think(self);
    advance(); rotor_thinks();
    assert(!(self->svflags & SVF_NOCLIENT));
    assert(!(main->svflags & SVF_NOCLIENT) && !(tail->svflags & SVF_NOCLIENT));
    assert(self->solid == SOLID_BBOX && self->enemy == &g_edicts[1]);
    self = new_helicopter();
    main = rotor(self, MAIN_ROTOR); tail = rotor(self, TAIL_ROTOR);
    G_FreeEdict(self);
    advance(); rotor_thinks();
    assert(!main->inuse && !tail->inuse);
    self = new_helicopter();
    main = rotor(self, MAIN_ROTOR); tail = rotor(self, TAIL_ROTOR);
    G_FreeEdict(self);
    G_InitEdict(self);
    self->classname = "monster_plastic_helicopter";
    VectorSet(self->s.origin,0,0,288);
    SP_monster_plastic_helicopter(self);
    replacement_main = rotor(self,MAIN_ROTOR);
    replacement_tail = rotor(self,TAIL_ROTOR);
    /* rotor() finds the old attachments first until they reject the reused owner. */
    assert(replacement_main == main && replacement_tail == tail);
    replacement_main = self->chain;
    replacement_tail = replacement_main->chain;
    assert(replacement_main != main && replacement_tail != tail);
    advance(); rotor_thinks();
    assert(!main->inuse && !tail->inuse);
    assert(replacement_main->inuse && replacement_tail->inuse);
    assert(self->chain == replacement_main && replacement_main->chain == replacement_tail);
    deathmatch = &one;
    self = spawn_helicopter(0);
    assert(!self->inuse && !rotor(self, MAIN_ROTOR) && !rotor(self, TAIL_ROTOR));
    assert(level.total_monsters == 0);
    deathmatch = &zero;
}
static void kill_helicopter(edict_t *self)
{
    vec3_t direction = {1, 0, 0};
    T_Damage(self, self->enemy, self->enemy, direction, self->s.origin,
            vec3_origin, self->health + 100, 0, DAMAGE_NO_ARMOR, MOD_ROCKET);
}
static void test_crash_and_cleanup(void)
{
    edict_t *self = new_helicopter();
    edict_t *main = rotor(self, MAIN_ROTOR), *tail = rotor(self, TAIL_ROTOR);
    float height = self->s.origin[2], started = level.time;
    int i, fell = 0, landed = 0;
    kill_helicopter(self);
    assert(level.killed_monsters == 1);
    assert(self->deadflag == DEAD_DEAD && self->movetype == MOVETYPE_TOSS);
    assert(!(self->flags & FL_FLY));
    assert(main->inuse && tail->inuse); /* Rotors remain visible during the fall. */
    plastic_helicopter_machineguns(self); plastic_helicopter_rockets(self);
    assert(!rockets() && !bullet_rays);
    for (i = 0; i < 50 && self->inuse; i++)
    {
        tick(self);
        if (self->inuse && self->s.origin[2] < height - 8) fell = 1;
        if (self->inuse && self->movetype == MOVETYPE_NONE) landed = 1;
    }
    assert(fell && landed && !self->inuse);
    assert(!main->inuse && !tail->inuse);
    assert(explosions >= 5 && level.time - started < 4);
    assert(level.killed_monsters == 1);
    self = new_helicopter();
    no_floor = 1;
    self->s.origin[2] = 8192;
    kill_helicopter(self);
    for (i = 0; i < 45 && self->inuse; i++) tick(self);
    assert(!self->inuse && !rotor(self, MAIN_ROTOR) && !rotor(self, TAIL_ROTOR));
}
static void save_and_restore(const char *filename, edict_t *self)
{
    edict_t *main = rotor(self, MAIN_ROTOR), *tail = rotor(self, TAIL_ROTOR);
    ptrdiff_t main_id = main - g_edicts, tail_id = tail - g_edicts;
    mmove_t *move = self->monsterinfo.currentmove;
    void (*think)(edict_t *) = self->think;
    void (*rotor_think)(edict_t *) = main->think;
    WriteLevel(filename);
    ReadLevel(filename);
    self = &g_edicts[2];
    assert(self->monsterinfo.currentmove == move && self->think == think);
    assert(self->monsterinfo.attack && self->monsterinfo.checkattack && self->pain && self->die);
    assert(self->enemy == &g_edicts[1]);
    main = rotor(self, MAIN_ROTOR); tail = rotor(self, TAIL_ROTOR);
    assert(main == &g_edicts[main_id] && tail == &g_edicts[tail_id]);
    assert(main->owner == self && tail->owner == self && main->think == rotor_think);
}
static void test_savegame(const char *filename)
{
    edict_t *self = new_helicopter();
    int i;
    save_and_restore(filename, self);
    self->monsterinfo.walk(self); save_and_restore(filename, self);
    self->monsterinfo.run(self); save_and_restore(filename, self);
    self = new_helicopter();
    begin_attack(self);
    {
        vec3_t direction = {1,0,0};
        int health = self->health;
        mmove_t *attack = self->monsterinfo.currentmove;
        T_Damage(self,self->enemy,self->enemy,direction,self->s.origin,
                vec3_origin,45,0,DAMAGE_NO_ARMOR,MOD_BLASTER);
        assert(self->health == health-45 && self->monsterinfo.currentmove != attack);
        assert(self->count == 0);
        save_and_restore(filename,self);
        for (i = 0; i < 5; i++) tick(self);
        assert(!rockets() && !bullet_rays);
    }
    self = new_helicopter();
    begin_attack(self);
    for (i = 0; i < 3; i++) tick(self);
    save_and_restore(filename, self);
    for (i = 0; i < 8; i++) tick(self);
    assert(rockets() == 2);
    self = new_helicopter();
    self->wait = level.time + 20;
    begin_attack(self);
    for (i = 0; i < 4; i++) tick(self);
    save_and_restore(filename, self);
    for (i = 0; i < 6; i++) tick(self);
    assert(bullet_rays == 8);
    self = new_helicopter();
    kill_helicopter(self);
    tick(self); save_and_restore(filename, self);
    for (i = 0; i < 40 && self->inuse && self->movetype != MOVETYPE_NONE; i++) tick(self);
    assert(self->inuse && self->movetype == MOVETYPE_NONE);
    save_and_restore(filename, self);
    for (i = 0; i < 15 && self->inuse; i++) tick(self);
    assert(!self->inuse);
    unlink(filename);
}
int main(int argc, char **argv)
{
    assert(argc == 2);
    gi.modelindex = model_index; gi.soundindex = sound_index; gi.sound = sound_effect;
    gi.linkentity = link_entity; gi.unlinkentity = unlink_entity; gi.BoxEdicts = box_edicts;
    gi.trace = trace_world; gi.pointcontents = point_contents;
    gi.WriteByte = write_byte; gi.WriteShort = write_short;
    gi.WritePosition = write_vector; gi.WriteDir = write_vector; gi.multicast = multicast;
    gi.TagMalloc = allocate; gi.FreeTags = no_free; gi.dprintf = debug_print; gi.error = error;
    one.value = 1; gravity.value = 800; max_velocity.value = 2000;
    sv_gravity = &gravity; sv_maxvelocity = &max_velocity;
    deathmatch = coop = dmflags = skill = g_fix_triggered = g_monsterfootsteps = &zero;
    max_clients.value = 1; maxclients = &max_clients;
    game.maxclients = 1; game.maxentities = 96;
    game.clients = calloc(game.maxclients, sizeof(*game.clients));
    g_edicts = calloc(game.maxentities, sizeof(*g_edicts));
    test_spawn_and_rotors();
    test_tail_rotor_axis_and_interpolation();
    test_acquisition_flight_and_patrol();
    test_machinegun_burst();
    test_paired_rockets();
    test_attack_safety();
    test_triggered_and_owner_removal();
    test_crash_and_cleanup();
    test_savegame(argv[1]);
    puts("helicopter flight, rotating attachments, guns, rockets, attack safety, crash physics and save/load passed");
    return 0;
}
