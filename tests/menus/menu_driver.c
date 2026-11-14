/* Runtime visual fixture. This is preloaded only into smoke_menus.py's isolated
 * SDL2 process. Calls use the executable's ELF offsets, with no test hooks or
 * state modifications in the shipped engine. */
#define _GNU_SOURCE
#include <SDL.h>
#include <dlfcn.h>
#include <link.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#undef EV_NONE
#include "../../src/client/header/keyboard.h"
#include "../../src/client/menu/header/qmenu.h"

typedef struct { unsigned delay; char op[24], text[480]; } action_t;
static action_t actions[1024];
static int count, next, initialized;
static unsigned due;
static uintptr_t image_base;
static void (*add_text)(const char *);
static void (*close_menu)(void);
static void (*menu_key)(int);
static int *menu_depth;
static char **popup_text;

static uintptr_t offset(const char *name)
{
    const char *value = getenv(name);
    if (!value) { fprintf(stderr, "PP_MENU_ERROR missing %s\n", name); exit(90); }
    return strtoull(value, NULL, 16);
}

static int find_main(struct dl_phdr_info *info, size_t size, void *data)
{
    (void)size;
    (void)data;
    if (info->dlpi_name[0]) return 0;
    image_base = info->dlpi_addr;
    add_text = (void *)(image_base + offset("PP_MENU_ADD_OFFSET"));
    close_menu = (void *)(image_base + offset("PP_MENU_CLOSE_OFFSET"));
    menu_key = (void *)(image_base + offset("PP_MENU_KEY_OFFSET"));
    menu_depth = (void *)(image_base + offset("PP_MENU_DEPTH_OFFSET"));
    popup_text = (void *)(image_base + offset("PP_MENU_POPUP_OFFSET"));
    return 1;
}

static void json_string(const char *text)
{
    fputc('"', stderr);
    for (; text && *text; text++) {
        unsigned char c = *text;
        if (c == '"' || c == '\\') fputc('\\', stderr);
        if (c >= 32 && c < 127) fputc(c, stderr);
    }
    fputc('"', stderr);
}

static menuframework_s *menu_from_text(const char *text)
{
    uintptr_t value = strtoull(text, NULL, 16);
    return value ? (menuframework_s *)(image_base + value) : NULL;
}

static void snapshot(char *text)
{
    char label[128], menu_offset[32];
    if (sscanf(text, "%127s %31s", label, menu_offset) != 2) exit(93);
    menuframework_s *menu = menu_from_text(menu_offset);
    menucommon_s *focus = menu && menu->cursor >= 0 && menu->cursor < menu->nitems ?
                         menu->items[menu->cursor] : NULL;
    fprintf(stderr, "PP_MENU_STATE {\"label\":"); json_string(label);
    fprintf(stderr, ",\"depth\":%d,\"cursor\":%d,\"items\":%d,\"top\":%d,\"title\":",
            *menu_depth, menu ? menu->cursor : -1, menu ? menu->nitems : 0,
            menu ? menu->compact_top : 0);
    json_string(menu ? menu->title : "custom");
    fprintf(stderr, ",\"selected\":"); json_string(focus ? focus->name : "");
    fprintf(stderr, ",\"value\":");
    json_string(focus && focus->compact_value ? focus->compact_value(focus) : "");
    fprintf(stderr, ",\"popup\":"); json_string(*popup_text);
    fprintf(stderr, "}\n");
    fflush(stderr);
}

static void run_action(action_t *action)
{
    char command[512];
    fprintf(stderr, "PP_MENU_ACTION %s %s\n", action->op, action->text);
    if (!strcmp(action->op, "cmd")) {
        snprintf(command, sizeof(command), "%s\n", action->text);
        add_text(command);
    } else if (!strcmp(action->op, "open")) {
        close_menu();
        snprintf(command, sizeof(command), "%s\n", action->text);
        add_text(command);
    } else if (!strcmp(action->op, "key")) {
        int key = !strcmp(action->text, "up") ? K_UPARROW :
                  !strcmp(action->text, "down") ? K_DOWNARROW :
                  !strcmp(action->text, "left") ? K_LEFTARROW :
                  !strcmp(action->text, "right") ? K_RIGHTARROW :
                  !strcmp(action->text, "enter") ? K_ENTER :
                  !strcmp(action->text, "backspace") ? K_BACKSPACE : K_ESCAPE;
        menu_key(key);
    } else if (!strcmp(action->op, "bottom") || !strcmp(action->op, "top")) {
        menuframework_s *menu = menu_from_text(action->text);
        int last = !strcmp(action->op, "bottom");
        int target = last ? menu->nitems - 1 : 0;
        while (target >= 0) {
            menucommon_s *item = menu->items[target];
            if (item->type != MTYPE_SEPARATOR && !(item->flags & QMF_INACTIVE)) break;
            target += last ? -1 : 1;
            if (target >= menu->nitems) { target = -1; break; }
        }
        for (int attempts = 0; target >= 0 && menu->cursor != target && attempts < menu->nitems; attempts++)
            menu_key(last ? K_DOWNARROW : K_UPARROW);
    } else if (!strcmp(action->op, "state")) {
        snapshot(action->text);
    } else if (!strcmp(action->op, "quit")) {
        SDL_Event event = { .type = SDL_QUIT };
        SDL_PushEvent(&event);
    } else {
        fprintf(stderr, "PP_MENU_ERROR unknown action %s\n", action->op);
        exit(94);
    }
}

int SDL_PollEvent(SDL_Event *event)
{
    static int (*real_poll)(SDL_Event *);
    if (!real_poll) real_poll = dlsym(RTLD_NEXT, "SDL_PollEvent");
    if (!initialized) {
        initialized = 1;
        FILE *input = fopen(getenv("PP_MENU_SCRIPT"), "r");
        if (!input) exit(91);
        char line[560];
        while (count < 1024 && fgets(line, sizeof(line), input)) {
            action_t *action = &actions[count];
            if (sscanf(line, "%u %23s %479[^\n]", &action->delay, action->op, action->text) >= 2) count++;
        }
        fclose(input);
        dl_iterate_phdr(find_main, NULL);
        if (!add_text || !count) exit(92);
        due = SDL_GetTicks() + actions[0].delay;
    }
    if (real_poll(event)) return 1;
    if (next < count && SDL_TICKS_PASSED(SDL_GetTicks(), due)) {
        run_action(&actions[next++]);
        if (next < count) due = SDL_GetTicks() + actions[next].delay;
    }
    return real_poll(event);
}
