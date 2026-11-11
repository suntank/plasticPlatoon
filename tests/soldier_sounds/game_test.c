#include "../../src/game/header/local.h"
#include <assert.h>
#include <stdarg.h>

extern void SP_monster_soldier_light(edict_t *self);
extern void SP_monster_soldier(edict_t *self);
extern void SP_monster_soldier_ss(edict_t *self);
extern void SP_monster_soldier_heavy(edict_t *self);
extern void SP_monster_soldier_rocket(edict_t *self);
extern void soldier_footstep(edict_t *self);
extern void soldier_cock(edict_t *self);
extern void soldier_idle(edict_t *self);
extern game_export_t *GetGameAPI(game_import_t *import);
extern mmove_t soldier_move_attack6;

static cvar_t zero, one;
static char sound_names[128][MAX_QPATH];
static int sound_count, last_sound, last_channel, played;
static int previous_alert_phrase = -1;

static const struct {
    const char *path;
    int phrase;
} alerts[] = {
    {"soldier/solsrch1.wav", 0},
    {"soldier/solsght1.wav", 1},
    {"soldier/callouts/contact_a.wav", 2},
    {"soldier/callouts/contact_b.wav", 2},
    {"soldier/callouts/enemy_spotted_a.wav", 1},
    {"soldier/callouts/enemy_spotted_b.wav", 1},
    {"soldier/callouts/over_here_a.wav", 3},
    {"soldier/callouts/over_here_b.wav", 3},
    {"soldier/callouts/contact_get_him_a.wav", 0},
    {"soldier/callouts/contact_get_him_b.wav", 0},
};

static int expect_alert(void)
{
    size_t i;
    assert(played == 1 && last_channel == CHAN_VOICE);
    for (i = 0; i < sizeof(alerts) / sizeof(alerts[0]); i++)
    {
        if (!strcmp(sound_names[last_sound], alerts[i].path))
        {
            assert(alerts[i].phrase != previous_alert_phrase);
            previous_alert_phrase = alerts[i].phrase;
            played = 0;
            return (int)i;
        }
    }
    assert(!"unknown soldier alert");
    return -1;
}

static int model_index(char *name) { (void)name; return 1; }
static void set_model(edict_t *ent, char *name)
{
    ent->s.modelindex = model_index(name);
}

static int sound_index(char *name)
{
    int i;
    /* NPCs must not enter the player-only sexed-sound resolver. */
    assert(name[0] != '*');
    for (i = 1; i <= sound_count; i++)
        if (!strcmp(name, sound_names[i])) return i;
    assert(++sound_count < 128);
    assert(strlen(name) < sizeof(sound_names[0]));
    strcpy(sound_names[sound_count], name);
    return sound_count;
}

static void sound_effect(edict_t *ent, int channel, int index,
        float volume, float attenuation, float offset)
{
    (void)ent;
    assert(index > 0 && index <= sound_count);
    assert(volume == 1 && (attenuation == ATTN_NORM || attenuation == ATTN_IDLE) && offset == 0);
    last_sound = index;
    last_channel = channel;
    played++;
}

static void link_entity(edict_t *ent)
{
    ent->linkcount++;
    VectorAdd(ent->s.origin, ent->mins, ent->absmin);
    VectorAdd(ent->s.origin, ent->maxs, ent->absmax);
    VectorSubtract(ent->maxs, ent->mins, ent->size);
}

static void debug_print(const char *fmt, ...) { (void)fmt; }
static YQ2_ATTR_NORETURN void error(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    vfprintf(stderr, fmt, ap);
    va_end(ap);
    abort();
}

struct soldier_case {
    char *classname;
    void (*spawn)(edict_t *);
    const char *pain;
    const char *death;
    const char *weapon;
    int variants;
};

static struct soldier_case cases[] = {
    {"monster_soldier_light", SP_monster_soldier_light,
        "soldier/player/pain25_1.wav", "soldier/player/death2.wav", "soldier/player/pistol%d.wav", 4},
    {"monster_soldier", SP_monster_soldier,
        "soldier/player/pain50_1.wav", "soldier/player/death1.wav", "soldier/player/shotgf1b.wav", 1},
    {"monster_soldier_ss", SP_monster_soldier_ss,
        "soldier/player/pain100_1.wav", "soldier/player/death3.wav", "soldier/player/machgf%db.wav", 5},
    {"monster_soldier_heavy", SP_monster_soldier_heavy,
        "soldier/player/pain100_1.wav", "soldier/player/death3.wav", "soldier/player/m60%d.wav", 5},
    {"monster_soldier_rocket", SP_monster_soldier_rocket,
        "soldier/player/pain100_1.wav", "soldier/player/death3.wav", "soldier/player/rocklf1a.wav", 1},
};

static edict_t *spawn_soldier_flags(struct soldier_case *test, int aiflags)
{
    edict_t *soldier = &g_edicts[2];
    memset(g_edicts, 0, game.maxentities * sizeof(*g_edicts));
    memset(&level, 0, sizeof(level));
    memset(&st, 0, sizeof(st));
    globals.num_edicts = 3;
    g_edicts[0].inuse = true;
    level.time = 10;
    gibsthisframe = 0;
    soldier->inuse = true;
    soldier->classname = test->classname;
    soldier->monsterinfo.aiflags = aiflags;
    sound_count = 0; /* Every variant must independently precache its sounds. */
    test->spawn(soldier);
    played = 0;
    return soldier;
}

static edict_t *spawn_soldier(struct soldier_case *test)
{
    return spawn_soldier_flags(test, 0);
}

static void expect_sound(const char *path, int channel)
{
    assert(played == 1);
    assert(last_channel == channel);
    assert(!strcmp(sound_names[last_sound], path));
    played = 0;
}

static void test_soldier(struct soldier_case *test)
{
    edict_t *soldier = spawn_soldier(test);
    vec3_t point = {0, 0, -1000};
    int i;

    assert(soldier->s.renderfx & RF_PP_ENEMY_COLOR);
    assert(!(soldier->s.renderfx & RF_PP_FRIENDLY_COLOR));

    /* Every random muzzle report must be registered by the spawning game. */
    for (i = 1; i <= test->variants; i++)
    {
        char path[MAX_QPATH];
        int before = sound_count;
        snprintf(path, sizeof(path), test->weapon, i);
        sound_index(path);
        assert(sound_count == before);
    }
    {
        const char *events[] = {"soldier/solidle1.wav", "soldier/solsght1.wav",
                               "soldier/solsrch1.wav", "infantry/infatck3.wav"};
        for (i = 0; i < 4; i++)
        {
            int before = sound_count;
            sound_index((char *)events[i]);
            assert(sound_count == before);
        }
    }
    for (i = 0; i < (int)(sizeof(alerts) / sizeof(alerts[0])); i++)
    {
        int before = sound_count;
        sound_index((char *)alerts[i].path);
        assert(sound_count == before);
    }
    soldier_cock(soldier);
    expect_sound("infantry/infatck3.wav", CHAN_WEAPON);
    for (i = 0; i < 200 && !played; i++) soldier_idle(soldier);
    expect_sound("soldier/solidle1.wav", CHAN_VOICE);
    soldier->monsterinfo.sight(soldier, &g_edicts[0]);
    expect_alert();
    {
        int before = sound_count;
        sound_index("soldier/player/death4.wav");
        assert(sound_count == before);
    }

    soldier->pain(soldier, &g_edicts[0], 1, 20);
    expect_sound(test->pain, CHAN_VOICE);
    soldier->pain(soldier, &g_edicts[0], 1, 20);
    assert(played == 0); /* Existing pain debounce remains effective. */

    g_monsterfootsteps = &zero;
    soldier_footstep(soldier);
    assert(played == 0);
    g_monsterfootsteps = &one;
    soldier_footstep(soldier);
    assert(played == 1 && last_channel == CHAN_BODY);
    assert(!strncmp(sound_names[last_sound], "soldier/player/step", strlen("soldier/player/step")));
    played = 0;

    soldier->health = 0;
    soldier->die(soldier, &g_edicts[0], &g_edicts[0], 20, point);
    expect_sound(test->death, CHAN_VOICE);
    soldier->die(soldier, &g_edicts[0], &g_edicts[0], 20, point);
    assert(played == 0); /* No duplicate regular-death voice. */

    soldier = spawn_soldier(test);
    soldier->health = soldier->gib_health;
    soldier->die(soldier, &g_edicts[0], &g_edicts[0], 100, point);
    expect_sound("soldier/player/death4.wav", CHAN_VOICE);
    for (i = 2; i < globals.num_edicts; i++)
    {
        edict_t *gib = &g_edicts[i];
        if (!gib->inuse || !(gib->s.effects & EF_GIB)) continue;
        assert(gib->s.renderfx & RF_PP_ENEMY_COLOR);
        assert(!(gib->s.renderfx & RF_PP_FRIENDLY_COLOR));
    }
}

static void test_debris_ownership(void)
{
    edict_t *ally = spawn_soldier_flags(&cases[0], AI_GOOD_GUY);
    edict_t *piece, *player;
    int i, found_gib = 0, found_debris = 0;
    assert(ally->s.renderfx & RF_PP_FRIENDLY_COLOR);
    assert(!(ally->s.renderfx & RF_PP_ENEMY_COLOR));
    ThrowGib(ally, "models/objects/gibs/arm/tris.md2", 20, GIB_ORGANIC);
    ThrowDebris(ally, "models/objects/debris1/tris.md2", 1, ally->s.origin);
    for (i = 3; i < globals.num_edicts; i++)
    {
        piece = &g_edicts[i];
        if (!piece->inuse) continue;
        assert(piece->s.renderfx & RF_PP_FRIENDLY_COLOR);
        assert(!(piece->s.renderfx & RF_PP_ENEMY_COLOR));
        if (piece->s.effects & EF_GIB) found_gib++;
        else found_debris++;
    }
    assert(found_gib == 1 && found_debris == 1);
    /* Player debris keeps its selected-skin marker and existing effects. */
    player = &g_edicts[1];
    player->inuse = true;
    player->client = &game.clients[0];
    ThrowGib(player, "models/objects/gibs/arm/tris.md2", 20, GIB_ORGANIC);
    piece = &g_edicts[globals.num_edicts - 1];
    assert(piece->s.skinnum & PP_GIB_PLAYER_SKIN_OVERRIDE);
    assert(piece->s.effects & EF_GREENGIB);
    assert(!(piece->s.renderfx & (RF_PP_ENEMY_COLOR | RF_PP_FRIENDLY_COLOR)));
}

static void test_frame_ownership_refresh(void)
{
    edict_t *actor, *pickup;
    game_export_t *api = GetGameAPI(&gi);
    memset(g_edicts, 0, game.maxentities * sizeof(*g_edicts));
    memset(&level, 0, sizeof(level));
    globals.num_edicts = 4;
    password = spectator_password = &zero;
    actor = &g_edicts[2];
    actor->inuse = true;
    actor->svflags = SVF_MONSTER;
    actor->s.renderfx = RF_GLOW; /* An old save has no ownership bits. */
    pickup = &g_edicts[3];
    pickup->inuse = true;
    pickup->s.renderfx = RF_FULLBRIGHT;
    api->RunFrame();
    assert(actor->s.renderfx == (RF_GLOW | RF_PP_ENEMY_COLOR));
    assert(pickup->s.renderfx == RF_FULLBRIGHT);
    actor->monsterinfo.aiflags |= AI_GOOD_GUY;
    api->RunFrame();
    assert(actor->s.renderfx == (RF_GLOW | RF_PP_FRIENDLY_COLOR));
    actor->monsterinfo.aiflags &= ~AI_GOOD_GUY;
    api->RunFrame();
    assert(actor->s.renderfx == (RF_GLOW | RF_PP_ENEMY_COLOR));
}

static void test_alert_variations(struct soldier_case *test)
{
    edict_t *soldier = spawn_soldier(test);
    mmove_t *move = soldier->monsterinfo.currentmove;
    int i, seen[sizeof(alerts) / sizeof(alerts[0])] = {0};
    int attacks = 0, before = sound_count;
    qboolean specialist = test->spawn == SP_monster_soldier_heavy ||
                          test->spawn == SP_monster_soldier_rocket;

    skill = &one;
    soldier->enemy = &g_edicts[1];
    soldier->enemy->s.origin[0] = 800;
    soldier->monsterinfo.nextframe = 17;
    soldier->monsterinfo.pausetime = 23;
    soldier->monsterinfo.attack_finished = 42;
    for (i = 0; i < 512; i++)
    {
        soldier->monsterinfo.currentmove = move;
        soldier->monsterinfo.sight(soldier, soldier->enemy);
        seen[expect_alert()]++;
        assert(sound_count == before); /* No late unregistered samples. */
        assert(soldier->monsterinfo.nextframe == 17);
        assert(soldier->monsterinfo.pausetime == 23);
        assert(soldier->monsterinfo.attack_finished == 42);
        if (specialist)
            assert(soldier->monsterinfo.currentmove == move);
        else if (soldier->monsterinfo.currentmove != move)
        {
            assert(soldier->monsterinfo.currentmove == &soldier_move_attack6);
            attacks++;
        }
    }
    for (i = 0; i < (int)(sizeof(alerts) / sizeof(alerts[0])); i++)
        assert(seen[i] > 0);
    if (!specialist) assert(attacks > 0 && attacks < 512);
    skill = &zero;
}

int main(void)
{
    size_t i;
    gi.modelindex = model_index;
    gi.setmodel = set_model;
    gi.soundindex = sound_index;
    gi.sound = sound_effect;
    gi.linkentity = link_entity;
    gi.dprintf = debug_print;
    gi.error = error;
    deathmatch = coop = skill = g_fix_triggered = g_monsterfootsteps = &zero;
    one.value = 1;
    maxclients = &one;
    game.maxclients = 1;
    game.maxentities = 32;
    game.clients = calloc(game.maxclients, sizeof(*game.clients));
    g_edicts = calloc(game.maxentities, sizeof(*g_edicts));
    for (i = 0; i < sizeof(cases) / sizeof(cases[0]); i++)
    {
        test_soldier(&cases[i]);
        test_alert_variations(&cases[i]);
    }
    test_debris_ownership();
    test_frame_ownership_refresh();
    free(game.clients);
    free(g_edicts);
    puts("five soldier variants: all ten alerts, no repeated wording, sight combat behavior, precaches, pain, death, gibs and footsteps passed");
    return 0;
}
