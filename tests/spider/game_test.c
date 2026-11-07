#include "../../src/game/header/local.h"
#include <assert.h>
#include <stdarg.h>
#include <stddef.h>
#include <unistd.h>

extern void SP_monster_spider(edict_t *self);
extern void M_MoveFrame(edict_t *self);

static cvar_t zero, one, max_clients;
static int blocked_sight, blocked_shots, shot_traces, links;
static char models[64][MAX_QPATH];
static int model_count;
static int blood_multicasts;


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
static void set_model(edict_t *ent, char *name) { ent->s.modelindex = model_index(name); }
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
    if (mask == MASK_SHOT) { shot_traces++; trace.fraction = 0.5f; trace.ent = &g_edicts[1]; }
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
    (void)point; (void)destination; blood_multicasts++;
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


static void test_player_pain(edict_t *ent, edict_t *other, float kick, int damage)
{ (void)ent; (void)other; (void)kick; (void)damage; }

static edict_t *spawn_spider(void)
{
    edict_t *spider = &g_edicts[2], *enemy = &g_edicts[1];
    memset(g_edicts, 0, game.maxentities * sizeof(*g_edicts));
    memset(game.clients, 0, game.maxclients * sizeof(*game.clients));
    memset(&level, 0, sizeof(level));
    memset(&st, 0, sizeof(st));
    globals.num_edicts = 3;
    level.time = 10;
    g_edicts[0].inuse = true;
    enemy->inuse = true;
    enemy->health = 100;
    enemy->takedamage = DAMAGE_YES;
    enemy->pain = test_player_pain;
    enemy->client = &game.clients[0];
    enemy->classname = "player";
    VectorSet(enemy->mins, -16, -16, -24);
    VectorSet(enemy->maxs, 16, 16, 32);
    VectorSet(enemy->s.origin, 60, 0, 24);
    link_entity(enemy);
    spider->inuse = true;
    spider->classname = "monster_spider";
    VectorSet(spider->s.origin, 0, 0, 24);
    ED_CallSpawn(spider);
    spider->enemy = enemy;
    return spider;
}

static void assert_spider_gib_burst(edict_t *spider)
{
    int i, chunks = 0, legs = 0;
    assert(spider->deadflag == DEAD_DEAD && !(spider->svflags & SVF_MONSTER));
    assert(spider->s.effects & EF_GIB);
    assert(!strcmp(models[spider->s.modelindex], "models/objects/gibs/spider/chunk.md2"));
    assert(blood_multicasts == 4);
    for (i = 3; i < globals.num_edicts; ++i) {
        edict_t *gib = &g_edicts[i];
        assert(gib->inuse && (gib->s.effects & EF_GIB));
        assert(gib->movetype == MOVETYPE_TOSS && gib->think && gib->nextthink > level.time);
        if (!strcmp(models[gib->s.modelindex], "models/objects/gibs/spider/chunk.md2")) chunks++;
        else if (!strcmp(models[gib->s.modelindex], "models/objects/gibs/spider/leg.md2")) legs++;
        else assert(!"unexpected gib model");
    }
    assert(chunks == 4 && legs == 6);
}

int main(int argc, char **argv)
{
    edict_t *spider, *enemy;
    mmove_t *attack;
    int i, bite_count = 0;
    assert(argc == 2);
    gi.modelindex = model_index; gi.setmodel = set_model; gi.soundindex = sound_index; gi.sound = sound_effect;
    gi.linkentity = link_entity; gi.unlinkentity = unlink_entity;
    gi.BoxEdicts = box_edicts; gi.trace = trace_world; gi.pointcontents = point_contents;
    gi.WriteByte = write_byte; gi.WriteShort = write_short; gi.WritePosition = write_vector;
    gi.WriteDir = write_vector; gi.multicast = multicast;
    gi.TagMalloc = allocate; gi.FreeTags = no_free; gi.dprintf = debug_print; gi.error = error;
    one.value = 1;
    deathmatch = coop = dmflags = skill = g_fix_triggered = g_monsterfootsteps = &zero;
    skill = &one;
    max_clients.value = 1; maxclients = &max_clients;
    game.maxclients = 1; game.maxentities = 64;
    game.clients = calloc(game.maxclients, sizeof(*game.clients));
    g_edicts = calloc(game.maxentities, sizeof(*g_edicts));
    spider = spawn_spider(); enemy = spider->enemy;
    assert(spider->svflags & SVF_MONSTER);
    assert(!strcmp(models[spider->s.modelindex], "models/monsters/spider/tris.md2"));
    assert(spider->maxs[2] - spider->mins[2] == 48 && spider->health == 300);
    assert(spider->monsterinfo.melee && !spider->monsterinfo.attack);
    spider->monsterinfo.melee(spider);
    attack = spider->monsterinfo.currentmove;
    assert(attack->firstframe == 32 && attack->lastframe == 39);
    for (i = 0; i <= attack->lastframe - attack->firstframe; ++i)
        if (attack->frame[i].thinkfunc) {
            ++bite_count;
            assert(i + attack->firstframe == 36);
            attack->frame[i].thinkfunc(spider);
        }
    assert(bite_count == 1 && enemy->health == 68);
    enemy->s.origin[0] = 100;
    attack->frame[4].thinkfunc(spider);
    assert(enemy->health == 68); /* No damage if the player escapes the bite. */
    enemy->s.origin[0] = 60;
    blocked_shots = 1;
    g_edicts[0].takedamage = DAMAGE_NO;
    attack->frame[4].thinkfunc(spider);
    assert(enemy->health == 68); /* A wall blocks the bite. */
    blocked_shots = 0;
    enemy->pain = NULL;
    WriteLevel(argv[1]); ReadLevel(argv[1]);
    spider = &g_edicts[2];
    assert(spider->monsterinfo.currentmove == attack && spider->monsterinfo.melee);
    assert(spider->pain && spider->die && spider->enemy == &g_edicts[1]);
    spider->die(spider, NULL, NULL, 300, vec3_origin);
    assert(spider->deadflag == DEAD_DEAD && spider->monsterinfo.currentmove->firstframe == 44);
    spider->monsterinfo.currentmove->endfunc(spider);
    assert(spider->svflags & SVF_DEADMONSTER);
    /* A corpse can still burst when sufficiently overkilled. */
    blood_multicasts = gibsthisframe = 0;
    spider->health = spider->gib_health;
    spider->die(spider, NULL, NULL, 200, vec3_origin);
    assert_spider_gib_burst(spider);
    /* A sufficiently powerful killing hit can gib it immediately, too. */
    spider = spawn_spider();
    blood_multicasts = gibsthisframe = 0;
    spider->health = spider->gib_health;
    spider->die(spider, NULL, NULL, 500, vec3_origin);
    assert_spider_gib_burst(spider);
    unlink(argv[1]);
    puts("spider spawn, melee, save/load, death and both gib paths passed");
    return 0;
}
