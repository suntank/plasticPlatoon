#include "../../src/game/header/local.h"
#include <assert.h>
#include <stdarg.h>
#include <unistd.h>

extern void SP_target_screen_image(edict_t *ent);
static int sends, write_index, sent_width, sent_height, sent_duration;
static edict_t *recipient;
static void write_byte(int value) { assert(value == 21); write_index = 0; }
static void write_string(char *value) { assert(!strcmp(value, "/pics/test.png")); }
static void write_short(int value)
{
    if (write_index == 0) sent_width = value;
    if (write_index == 1) sent_height = value;
    if (write_index == 2) sent_duration = value;
    write_index++;
}
static void unicast(edict_t *ent, qboolean reliable) { assert(reliable); recipient = ent; sends++; }
static void no_free(int tag) {}
static void *allocate(int bytes, int tag) { return calloc(1, bytes); }
static void link_entity(edict_t *ent) {}
static YQ2_ATTR_NORETURN void error(const char *fmt, ...) { va_list ap; va_start(ap, fmt); vfprintf(stderr, fmt, ap); va_end(ap); abort(); }

int main(int argc, char **argv)
{
    cvar_t max = {0};
    edict_t *target;
    assert(argc == 2);
    gi.WriteByte = write_byte; gi.WriteString = write_string; gi.WriteShort = write_short;
    gi.unicast = unicast; gi.FreeTags = no_free; gi.TagMalloc = allocate;
    gi.linkentity = link_entity; gi.error = error;
    game.maxclients = 2; game.maxentities = 4;
    max.value = 2; maxclients = &max;
    game.clients = calloc(2, sizeof(*game.clients));
    g_edicts = calloc(4, sizeof(*g_edicts));
    globals.num_edicts = 4;
    g_edicts[1].inuse = true; g_edicts[1].client = &game.clients[0];
    g_edicts[2].inuse = true; g_edicts[2].client = &game.clients[1];
    target = &g_edicts[3]; target->inuse = true;
    target->classname = "target_screen_image";
    st.pic = "/pics/test.png"; st.distance = 100000; st.height = -2;
    SP_target_screen_image(target);
    target->count = 100000;
    target->use(target, NULL, &g_edicts[1]);
    assert(sends == 2 && sent_width == 32767 && sent_height == 0 && sent_duration == 32767);
    target->spawnflags = 1;
    target->use(target, NULL, &g_edicts[1]);
    assert(sends == 3 && recipient == &g_edicts[1]);
    WriteLevel(argv[1]);
    ReadLevel(argv[1]);
    target = &g_edicts[3];
    assert(!strcmp(target->message, "/pics/test.png"));
    assert(target->style == 32767 && target->health == 0 && target->use);
    target->count = 0;
    target->use(target, NULL, &g_edicts[2]);
    assert(sends == 4 && recipient == &g_edicts[2] && sent_duration == 1);
    unlink(argv[1]);
    puts("screen-image target delivery, wire bounds and save/load callback passed");
    return 0;
}
