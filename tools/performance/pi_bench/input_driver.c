/* Test-only local-player input driver. Never install this in the game package.
 * Preload into an isolated, unstripped build made with matching source headers.
 * It queues normal client commands and changes only normal held-input fields;
 * it does not change simulation, rendering, networking, or weapon behavior.
 */
#define _GNU_SOURCE
#include <SDL.h>
#include <dlfcn.h>
#include <link.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#undef EV_NONE
#include "src/client/cl_splitscreen.h"
#include "src/client/refresh/gl1/header/local.h"

static int initialized;
static void (*add_command)(const char *, void (*)(void));
static int (*argc_fn)(void);
static char *(*argv_fn)(int);
static void (*add_text)(const char *);
static ss_local_player_t *(*get_slot)(int);
static void (*send_slot_command)(ss_local_player_t *, const char *);
static qboolean (*device_connected)(int);
static client_state_t *primary;
static SDL_Joystick *virtual_pads[3];
static int attached;

static uintptr_t offset(const char *name)
{
    const char *value = getenv(name);
    char *end;
    unsigned long long result;
    if (!value || !*value) {
        fprintf(stderr, "PP_TEST_ERROR missing %s\n", name);
        exit(90);
    }
    result = strtoull(value, &end, 16);
    if (*end || !result) {
        fprintf(stderr, "PP_TEST_ERROR invalid %s\n", name);
        exit(90);
    }
    return (uintptr_t)result;
}

static int find_main(struct dl_phdr_info *info, size_t size, void *data)
{
    (void)size;
    (void)data;
    if (info->dlpi_name[0]) return 0;
    uintptr_t base = info->dlpi_addr;
    add_command = (void *)(base + offset("PP_TEST_CMD_ADD_OFFSET"));
    argc_fn = (void *)(base + offset("PP_TEST_CMD_ARGC_OFFSET"));
    argv_fn = (void *)(base + offset("PP_TEST_CMD_ARGV_OFFSET"));
    add_text = (void *)(base + offset("PP_TEST_CBUF_ADD_OFFSET"));
    get_slot = (void *)(base + offset("PP_TEST_GET_SLOT_OFFSET"));
    send_slot_command = (void *)(base + offset("PP_TEST_SEND_SLOT_OFFSET"));
    if (getenv("PP_TEST_CLIENT_OFFSET"))
        primary = (void *)(base + offset("PP_TEST_CLIENT_OFFSET"));
    if (getenv("PP_TEST_DEVICE_CONNECTED_OFFSET"))
        device_connected = (void *)(base + offset("PP_TEST_DEVICE_CONNECTED_OFFSET"));
    return 1;
}

static void attach_pad(int index)
{
    static const char *names[] = {"Pi Four-player Test Pad 1", "Pi Four-player Test Pad 2",
                                 "Pi Four-player Test Pad 3"};
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
    if (device < 0 || !(virtual_pads[index] = SDL_JoystickOpen(device))) {
        fprintf(stderr, "PP_TEST_ERROR virtual controller attach: %s\n", SDL_GetError());
        exit(93);
    }
    for (int axis = 0; axis < SDL_CONTROLLER_AXIS_MAX; axis++) {
        Sint16 value = axis == SDL_CONTROLLER_AXIS_TRIGGERLEFT ||
                       axis == SDL_CONTROLLER_AXIS_TRIGGERRIGHT ? -32768 : 0;
        if (SDL_JoystickSetVirtualAxis(virtual_pads[index], axis, value) < 0) {
            fprintf(stderr, "PP_TEST_ERROR virtual controller axis: %s\n", SDL_GetError());
            exit(94);
        }
    }
    fprintf(stderr, "PP_TEST_ATTACH index=%d instance=%d name=%s controller=%d\n", index,
            (int)SDL_JoystickInstanceID(virtual_pads[index]), names[index], SDL_IsGameController(device));
    fflush(stderr);
}

int SDL_Init(Uint32 flags)
{
    static int (*real_init)(Uint32);
    if (!real_init) real_init = dlsym(RTLD_NEXT, "SDL_Init");
    if (!real_init) {
        fprintf(stderr, "PP_TEST_ERROR cannot resolve SDL_Init\n");
        exit(91);
    }
    int result = real_init(flags);
    if (!result && (flags & SDL_INIT_GAMECONTROLLER) && !attached) {
        attached = 1;
        for (int i = 0; i < 3; i++) attach_pad(i);
        SDL_JoystickUpdate();
    }
    return result;
}

static int slot_index(void)
{
    char *end;
    const char *value = argv_fn(1);
    long index = strtol(value, &end, 10);
    return !*value || *end || index < 0 || index >= SS_MAX_LOCAL_PLAYERS ? -1 : (int)index;
}

static ss_local_player_t *active_slot(int index)
{
    ss_local_player_t *slot = get_slot(index);
    if (!slot || !slot->active || slot->connection_state < ca_active || !slot->snapshot_valid) {
        fprintf(stderr, "PP_TEST_ERROR slot %d has no active snapshot\n", index);
        return NULL;
    }
    if (slot->menu_open || (device_connected && !device_connected(slot->device_index))) {
        fprintf(stderr, "PP_TEST_ERROR slot %d paused or has no connected controller\n", index);
        return NULL;
    }
    return slot;
}

static void json_string(const char *value)
{
    fputc('"', stderr);
    for (size_t i = 0; value && value[i] && i < MAX_QPATH; ++i) {
        unsigned char c = (unsigned char)value[i];
        if (c == '"' || c == '\\') { fputc('\\', stderr); fputc(c, stderr); }
        else if (c < 32) fprintf(stderr, "\\u%04x", c);
        else fputc(c, stderr);
    }
    fputc('"', stderr);
}

static void slot_state(void)
{
    fprintf(stderr, "PP_TEST_STATE {\"virtual_pads\":%d,\"primary_data_available\":%d,\"device_check_available\":%d,\"slots\":[",
            attached ? 3 : 0, primary != NULL, device_connected != NULL);
    for (int i = 0; i < SS_MAX_LOCAL_PLAYERS; i++) {
        ss_local_player_t *slot = get_slot(i);
        if (!slot) {
            fprintf(stderr, "%s{\"slot\":%d,\"active\":0}", i ? "," : "", i);
            continue;
        }
        const usercmd_t *cmd = !i && primary ? &primary->cmd : &slot->cmd;
        const player_state_t *ps = !i && primary ? &primary->frame.playerstate : &slot->frame.playerstate;
        const float *angles = !i && primary ? primary->viewangles : slot->viewangles;
        int snapshot = !i && primary ? primary->frame.valid : slot->snapshot_valid;
        int attack = i ? slot->attack_down : !!(cmd->buttons & BUTTON_ATTACK);
        int connected = device_connected ? device_connected(slot->device_index) : -1;
        /* All split clients share the server's model configstrings, as the
         * production secondary-view weapon renderer does. Indices differ by
         * map, so retain the resolved path for weapon identity assertions. */
        const char *gunmodel = primary && ps->gunindex > 0 && ps->gunindex < MAX_MODELS ?
                               primary->configstrings[CS_MODELS + ps->gunindex] : "";
        fprintf(stderr, "%s{\"slot\":%d,\"active\":%d,\"device\":%d,\"device_connected\":%d,\"menu_open\":%d,\"connection\":%d,\"snapshot\":%d,\"attack_down\":%d,\"cmd_buttons\":%d,\"cmd_forward\":%d,\"cmd_sidemove\":%d,\"cmd_upmove\":%d,\"viewangles\":[%.5f,%.5f,%.5f],\"gunindex\":%d,\"gunframe\":%d,\"gunmodel\":",
                i ? "," : "", i, slot->active, slot->device_index, connected,
                slot->menu_open, slot->connection_state, snapshot, attack, cmd->buttons,
                cmd->forwardmove, cmd->sidemove, cmd->upmove,
                angles[0], angles[1], angles[2], ps->gunindex, ps->gunframe);
        json_string(gunmodel);
        fputc('}', stderr);
    }
    fprintf(stderr, "]}\n");
    fflush(stderr);
}

/* Read-only registration proof. Re-resolve after every renderer reload. */
static model_t *registered_models;
static int *registered_model_count;

static int find_renderer_models(struct dl_phdr_info *info, size_t size, void *data)
{
    (void)size;
    (void)data;
    const char *name = strrchr(info->dlpi_name, '/');
    name = name ? name + 1 : info->dlpi_name;
    if (strcmp(name, "ref_gl1.so")) return 0;
    registered_models = (void *)(info->dlpi_addr + offset("PP_TEST_GL1_MODELS_OFFSET"));
    registered_model_count = (void *)(info->dlpi_addr + offset("PP_TEST_GL1_NUM_MODELS_OFFSET"));
    return 1;
}

static void model_state(void)
{
    registered_models = NULL;
    registered_model_count = NULL;
    if (!getenv("PP_TEST_GL1_MODELS_OFFSET") || !getenv("PP_TEST_GL1_NUM_MODELS_OFFSET")) {
        fprintf(stderr, "PP_TEST_MODELS {\"available\":false,\"error\":\"missing renderer symbol offsets\",\"models\":[]}\n");
        fflush(stderr);
        return;
    }
    dl_iterate_phdr(find_renderer_models, NULL);
    if (!registered_models || !registered_model_count || *registered_model_count < 0 || *registered_model_count > 512) {
        fprintf(stderr, "PP_TEST_MODELS {\"available\":false,\"error\":\"renderer registry unavailable or invalid\",\"models\":[]}\n");
        fflush(stderr);
        return;
    }
    fprintf(stderr, "PP_TEST_MODELS {\"available\":true,\"registered_count\":%d,\"model_struct_bytes\":%zu,\"models\":[",
            *registered_model_count, sizeof(model_t));
    int emitted = 0, invalid_headers = 0;
    for (int i = 0; i < *registered_model_count; i++) {
        const model_t *model = &registered_models[i];
        if (!model->name[0] || model->type != mod_alias || !model->extradata ||
            model->extradatasize < (int)sizeof(dmdl_t) || !memchr(model->name, 0, MAX_QPATH)) continue;
        const dmdl_t *header = model->extradata;
        if (header->ident != IDALIASHEADER || header->version != ALIAS_VERSION ||
            header->num_xyz < 1 || header->num_xyz > 2048 || header->num_tris < 1 || header->num_tris > 4096 ||
            header->num_frames < 1 || header->num_frames > 512) {
            invalid_headers++;
            continue;
        }
        if (emitted++) fputc(',', stderr);
        fprintf(stderr, "{\"name\":");
        json_string(model->name);
        fprintf(stderr, ",\"num_xyz\":%d,\"num_tris\":%d,\"num_frames\":%d}",
                header->num_xyz, header->num_tris, header->num_frames);
    }
    fprintf(stderr, "],\"invalid_headers\":%d}\n", invalid_headers);
    if (invalid_headers) fprintf(stderr, "PP_TEST_ERROR invalid registered MD2 headers: %d\n", invalid_headers);
    fflush(stderr);
}

static void slot_command(void)
{
    char command[1024] = {0};
    size_t used = 0;
    int index = slot_index();
    if (argc_fn() < 3 || index < 0) {
        fprintf(stderr, "PP_TEST_ERROR usage: pp_test_slot <0..3> <game command>\n");
        return;
    }
    for (int i = 2; i < argc_fn(); i++) {
        const char *arg = argv_fn(i);
        size_t length = strlen(arg);
        if (strchr(arg, '\n') || strchr(arg, '\r') || used + length + 3 >= sizeof(command)) {
            fprintf(stderr, "PP_TEST_ERROR invalid or overlong game command\n");
            return;
        }
        if (i > 2) command[used++] = ' ';
        memcpy(command + used, arg, length + 1);
        used += length;
    }
    if (!index) {
        command[used++] = '\n';
        command[used] = '\0';
        add_text(command);
    } else {
        ss_local_player_t *slot = active_slot(index);
        if (!slot) return;
        send_slot_command(slot, command);
    }
    fprintf(stderr, "PP_TEST_SLOT %d %s%s", index, command, index ? "\n" : "");
    fflush(stderr);
}

static void slot_input(void)
{
    int index = slot_index();
    const char *name = argv_fn(2), *value = argv_fn(3);
    qboolean down;
    ss_local_player_t *slot;
    qboolean *held = NULL;
    const char *primary = NULL;
    if (argc_fn() != 4 || index < 0 || (strcmp(value, "0") && strcmp(value, "1"))) {
        fprintf(stderr, "PP_TEST_ERROR usage: pp_test_input <0..3> <attack|forward|back|left|right|moveleft|moveright|jump> <0|1>\n");
        return;
    }
    down = value[0] == '1';
    slot = index ? active_slot(index) : NULL;
    if (index && !slot) return;
#define INPUT(label, field, binding) \
    if (!strcmp(name, label)) { if (slot) held = &slot->field; primary = binding; }
    INPUT("attack", attack_down, "attack")
    else INPUT("forward", forward_down, "forward")
    else INPUT("back", back_down, "back")
    else INPUT("left", turnleft_down, "left")
    else INPUT("right", turnright_down, "right")
    else INPUT("moveleft", moveleft_down, "moveleft")
    else INPUT("moveright", moveright_down, "moveright")
    else INPUT("jump", jump_down, "moveup")
#undef INPUT
    if (!primary) {
        fprintf(stderr, "PP_TEST_ERROR unsupported input %s\n", name);
        return;
    }
    if (index) *held = down;
    else {
        char command[48];
        snprintf(command, sizeof(command), "%c%s\n", down ? '+' : '-', primary);
        add_text(command);
    }
    fprintf(stderr, "PP_TEST_INPUT %d %s %d\n", index, name, down);
    fflush(stderr);
}

int SDL_PollEvent(SDL_Event *event)
{
    static int (*real_poll)(SDL_Event *);
    if (!real_poll) real_poll = dlsym(RTLD_NEXT, "SDL_PollEvent");
    if (!real_poll) {
        fprintf(stderr, "PP_TEST_ERROR cannot resolve SDL_PollEvent\n");
        exit(91);
    }
    if (!initialized) {
        initialized = 1;
        dl_iterate_phdr(find_main, NULL);
        if (!add_command || !argc_fn || !argv_fn || !add_text || !get_slot || !send_slot_command) exit(92);
        add_command("pp_test_slot", slot_command);
        add_command("pp_test_input", slot_input);
        add_command("pp_test_state", slot_state);
        add_command("pp_test_models", model_state);
        fprintf(stderr, "PP_TEST_READY input-only driver; sizeof(slot)=%zu\n", sizeof(ss_local_player_t));
        fflush(stderr);
    }
    return real_poll(event);
}
