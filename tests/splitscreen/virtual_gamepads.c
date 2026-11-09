/* Real SDL2 input smoke fixture. Loaded only by smoke_lobby.py into its
 * isolated client process; no engine test commands or source hooks needed. */
#define _GNU_SOURCE
#include <SDL.h>
#include <dlfcn.h>
#include <link.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#undef EV_NONE /* elf.h and the game protocol use the same name. */
#include "../../src/client/cl_splitscreen.h"

typedef struct { unsigned time; char op[32], a[64], b[64], c[64]; } action_t;
static action_t actions[256];
static int action_count, next_action, initialized, attached;
static unsigned started, next_due;
static SDL_Joystick *pads[4];
static SDL_JoystickID pad_ids[4];
static ss_state_t *state;
static client_state_t *primary;
static client_static_t *client_static;

static int find_main(struct dl_phdr_info *info, size_t size, void *data)
{
    if (!info->dlpi_name[0]) {
        state = (ss_state_t *)(info->dlpi_addr + strtoull(getenv("PP_SMOKE_STATE_OFFSET"), NULL, 16));
        primary = (client_state_t *)(info->dlpi_addr + strtoull(getenv("PP_SMOKE_CLIENT_OFFSET"), NULL, 16));
        client_static = (client_static_t *)(info->dlpi_addr + strtoull(getenv("PP_SMOKE_STATIC_OFFSET"), NULL, 16));
        return 1;
    }
    return 0;
}

static void attach_pad(int index)
{
    static const char *names[] = {"Split-screen Test Pad 1", "Split-screen Test Pad 2",
                                 "Split-screen Test Pad 3", "Split-screen Test Pad 4"};
    SDL_VirtualJoystickDesc desc;
    memset(&desc, 0, sizeof(desc));
    desc.version = SDL_VIRTUAL_JOYSTICK_DESC_VERSION;
    desc.type = SDL_JOYSTICK_TYPE_GAMECONTROLLER;
    desc.naxes = SDL_CONTROLLER_AXIS_MAX;
    desc.nbuttons = SDL_CONTROLLER_BUTTON_MAX;
    desc.button_mask = (1U << SDL_CONTROLLER_BUTTON_MAX) - 1;
    desc.axis_mask = (1U << SDL_CONTROLLER_AXIS_MAX) - 1;
    desc.name = names[index];
    int device = SDL_JoystickAttachVirtualEx(&desc);
    if (device < 0 || !(pads[index] = SDL_JoystickOpen(device))) {
        fprintf(stderr, "PP_SMOKE_ERROR attach: %s\n", SDL_GetError());
        exit(90);
    }
    pad_ids[index] = SDL_JoystickInstanceID(pads[index]);
    SDL_JoystickSetVirtualAxis(pads[index], SDL_CONTROLLER_AXIS_TRIGGERLEFT, -32768);
    SDL_JoystickSetVirtualAxis(pads[index], SDL_CONTROLLER_AXIS_TRIGGERRIGHT, -32768);
    fprintf(stderr, "PP_SMOKE_ATTACH %d id=%d\n", index, (int)pad_ids[index]);
}

int SDL_Init(Uint32 flags)
{
    static int (*real_init)(Uint32);
    if (!real_init) real_init = dlsym(RTLD_NEXT, "SDL_Init");
    int result = real_init(flags);
    if (!result && (flags & SDL_INIT_GAMECONTROLLER) && !attached) {
        attached = 1;
        int count = atoi(getenv("PP_SMOKE_PADS") ? getenv("PP_SMOKE_PADS") : "2");
        for (int i = 0; i < count && i < 4; i++) attach_pad(i);
    }
    return result;
}

static void snapshot(const char *label)
{
    fprintf(stderr, "PP_SMOKE_STATE {\"label\":\"%s\",\"lobby\":%d,\"session\":%d,\"players\":%d,\"primary_connection\":%d,\"slots\":[",
            label, state->lobby_active, state->session_active, state->requested_players, client_static->state);
    for (int i = 0; i < state->requested_players; i++) {
        ss_local_player_t *slot = &state->slots[i];
        fprintf(stderr, "%s{\"device\":%d,\"ready\":%d,\"connection\":%d,\"snapshot\":%d,\"forward\":%d,\"side\":%d,\"attack\":%d,\"buttons\":%d,\"up\":%d}",
                i ? "," : "", slot->device_index, slot->ready, slot->connection_state,
                slot->snapshot_valid, i ? slot->cmd.forwardmove : primary->cmd.forwardmove,
                i ? slot->cmd.sidemove : primary->cmd.sidemove, slot->attack_down,
                i ? slot->cmd.buttons : primary->cmd.buttons,
                i ? slot->cmd.upmove : primary->cmd.upmove);
    }
    fprintf(stderr, "]}\n");
    fflush(stderr);
}

static void run_action(action_t *a)
{
    SDL_Event event;
    memset(&event, 0, sizeof(event));
    fprintf(stderr, "PP_SMOKE_ACTION %u %s %s %s %s\n", a->time, a->op, a->a, a->b, a->c);
    if (!strcmp(a->op, "keydown") || !strcmp(a->op, "keyup")) {
        event.type = !strcmp(a->op, "keydown") ? SDL_KEYDOWN : SDL_KEYUP;
        event.key.state = event.type == SDL_KEYDOWN ? SDL_PRESSED : SDL_RELEASED;
        event.key.keysym.sym = SDL_GetKeyFromName(a->a);
        event.key.keysym.scancode = SDL_GetScancodeFromKey(event.key.keysym.sym);
        SDL_PushEvent(&event);
    } else if (!strcmp(a->op, "button")) {
        SDL_JoystickSetVirtualButton(pads[atoi(a->a)], atoi(a->b), atoi(a->c));
        SDL_JoystickUpdate();
    } else if (!strcmp(a->op, "axis")) {
        SDL_JoystickSetVirtualAxis(pads[atoi(a->a)], atoi(a->b), atoi(a->c));
        SDL_JoystickUpdate();
    } else if (!strcmp(a->op, "detach")) {
        int index = atoi(a->a);
        for (int i = 0; i < SDL_NumJoysticks(); i++) {
            if (SDL_JoystickGetDeviceInstanceID(i) == pad_ids[index]) {
                SDL_JoystickClose(pads[index]);
                pads[index] = NULL;
                SDL_JoystickDetachVirtual(i);
                break;
            }
        }
    } else if (!strcmp(a->op, "attach")) {
        attach_pad(atoi(a->a));
    } else if (!strcmp(a->op, "state")) {
        snapshot(a->a);
    } else if (!strcmp(a->op, "quit")) {
        event.type = SDL_QUIT;
        SDL_PushEvent(&event);
    }
}

int SDL_PollEvent(SDL_Event *event)
{
    static int (*real_poll)(SDL_Event *);
    if (!real_poll) real_poll = dlsym(RTLD_NEXT, "SDL_PollEvent");
    if (!initialized) {
        initialized = 1;
        FILE *script = fopen(getenv("PP_SMOKE_SCRIPT"), "r");
        if (!script) exit(91);
        char line[256];
        while (action_count < 256 && fgets(line, sizeof(line), script)) {
            action_t *a = &actions[action_count];
            if (sscanf(line, "%u %31s %63s %63s %63s", &a->time, a->op, a->a, a->b, a->c) >= 2)
                action_count++;
        }
        fclose(script);
        dl_iterate_phdr(find_main, NULL);
        if (!state) exit(92);
        started = SDL_GetTicks();
        next_due = actions[0].time;
    }
    if (real_poll(event)) {
        if (event->type == SDL_CONTROLLERBUTTONDOWN || event->type == SDL_CONTROLLERBUTTONUP)
            fprintf(stderr, "PP_SMOKE_EVENT %u type=%u id=%d button=%d\n", SDL_GetTicks() - started, event->type, event->cbutton.which, event->cbutton.button);
        return 1;
    }
    unsigned elapsed = SDL_GetTicks() - started;
    /* A software-rendered screenshot can take seconds. Never replay several
     * overdue actions before the engine has consumed the preceding input. */
    if (next_action < action_count && elapsed >= next_due) {
        unsigned previous_time = actions[next_action].time;
        run_action(&actions[next_action++]);
        if (next_action < action_count)
            next_due = SDL_GetTicks() - started + actions[next_action].time - previous_time;
    }
    int result = real_poll(event);
    if (result && (event->type == SDL_CONTROLLERBUTTONDOWN || event->type == SDL_CONTROLLERBUTTONUP))
        fprintf(stderr, "PP_SMOKE_EVENT %u type=%u id=%d button=%d\n", SDL_GetTicks() - started, event->type, event->cbutton.which, event->cbutton.button);
    return result;
}
