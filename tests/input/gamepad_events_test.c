#include "../../src/client/header/client.h"
#include "../../src/client/cl_splitscreen.h"
#include "../../src/client/input/header/controller_registry.h"
#include <assert.h>

client_static_t cls;
client_state_t cl;
console_t con;
qboolean joy_altselector_pressed;
int abort_cinematic;
extern qboolean menubound[K_LAST];

static qboolean lobby, session, secondary_attack;
static ss_local_player_t primary;
static int menu_events[SS_MAX_LOCAL_PLAYERS + 1], last_menu_key;
static int starts[SS_MAX_LOCAL_PLAYERS], commands;
static char command_text[2048];

int Sys_Milliseconds(void) { return 1; }
void Cbuf_AddText(char *text)
{
    ++commands;
    Q_strlcat(command_text, text, sizeof(command_text));
}
void Com_Printf(const char *fmt, ...) {}
void M_Keydown(int key)
{
    ++menu_events[Key_GetEventGamepadIndex() + 1];
    last_menu_key = key;
}
qboolean SS_IsLobbyActive(void) { return lobby; }
qboolean SS_IsSessionActive(void) { return session; }
ss_local_player_t *SS_GetSlot(int index) { return index == 0 ? &primary : NULL; }
qboolean SS_HandleSessionKey(int key, qboolean down)
{
    if (!session) return false;
    if (key == K_BTN_START || key == K_ESCAPE)
    {
        if (down && Key_GetEventGamepadIndex() >= 0)
            ++starts[Key_GetEventGamepadIndex()];
        return true;
    }
    /* Confirm release is consumed by the menu as well as stopping a jump. */
    return primary.menu_open && key == K_BTN_SOUTH;
}
qboolean SS_HandleGameplayKey(int key, qboolean down)
{
    if (session && Key_GetEventGamepadIndex() == 1 && key == K_TRIG_RIGHT)
    {
        secondary_attack = down;
        return true;
    }
    return false;
}
int IN_SetClipboardText(const char *text) { return 0; }
void IN_GetClipboardText(char *out, size_t size) { if (size) *out = 0; }
const char *Cmd_CompleteCommand(const char *partial) { return NULL; }
const char *Cmd_CompleteMapCommand(const char *partial) { return NULL; }
qboolean Cmd_IsComplete(const char *partial) { return false; }
void Key_ClearTyping(void) {}
void SCR_UpdateScreen(void) {}
cvar_t *Cvar_Get(const char *name, const char *value, int flags)
{
    static cvar_t var;
    return &var;
}
cvar_t *Cvar_Set(const char *name, const char *value) { return Cvar_Get(name, value, 0); }
void Con_ToggleConsole_f(void) {}
void M_Menu_Main_f(void) {}
void CL_ReleaseGameBirdKeys(void) {}

static void event(int pad, int key, qboolean down)
{
    Key_SetEventGamepadIndex(pad);
    Key_Event(key, down, true);
    Key_SetEventGamepadIndex(-1);
}

static void test_lobby(void)
{
    lobby = true;
    cls.key_dest = key_menu;
    event(0, K_BTN_SOUTH, true);
    event(1, K_BTN_SOUTH, true);
    assert(menu_events[1] == 1 && menu_events[2] == 1);
    assert(!keydown[K_BTN_SOUTH]);
    event(0, K_BTN_SOUTH, true); /* only the same device's repeat is ignored */
    assert(menu_events[1] == 1);
    event(0, K_BTN_SOUTH, false);
    event(0, K_BTN_SOUTH, true);
    assert(menu_events[1] == 2);
    event(1, K_DOWNARROW, true); /* virtual stick arrows retain pad identity */
    assert(menu_events[2] == 2 && last_menu_key == K_DOWNARROW);
    event(0, K_BTN_START, true);
    event(1, K_BTN_START, true);
    assert(menu_events[1] == 3 && menu_events[2] == 3);

    keybindings[K_F10] = "menu_quit";
    keybindings[K_F12] = "screenshot";
    menubound[K_F10] = menubound[K_F12] = true;
    event(-1, K_F10, true);
    assert(menu_events[0] == 1 && last_menu_key == K_F10 && commands == 0);
    event(-1, K_F12, true);
    assert(strstr(command_text, "screenshot") && !strstr(command_text, "menu_quit"));
    Key_MarkAllUp();
}

static void test_session(void)
{
    int before;
    lobby = false;
    session = true;
    cls.key_dest = key_game;
    cls.state = ca_active;
    primary.active = true;
    primary.device_index = 2;
    primary.state = SS_SLOT_ACTIVE;
    commands = 0;
    command_text[0] = 0;
    keybindings[K_TRIG_RIGHT] = "+attack";
    event(0, K_TRIG_RIGHT, true);
    assert(Key_UsingGamepad());
    event(1, K_TRIG_RIGHT, true);
    assert(secondary_attack && keydown[K_TRIG_RIGHT]);
    assert(commands == 1 && strstr(command_text, "+attack"));
    event(1, K_TRIG_RIGHT, false);
    assert(!secondary_attack && keydown[K_TRIG_RIGHT] && commands == 1);
    event(1, K_TRIG_RIGHT, true);
    Key_ClearGamepadStates(0);
    assert(secondary_attack && !keydown[K_TRIG_RIGHT] && commands == 2);
    assert(strstr(command_text, "-attack"));
    Key_ClearGamepadStates(1);
    assert(!secondary_attack);

    event(0, K_ESCAPE, true);
    event(1, K_ESCAPE, true);
    assert(starts[0] == 1 && starts[1] == 1);

    keybindings[K_BTN_NORTH] = "quickgrenade";
    before = commands;
    event(2, K_BTN_NORTH, true); /* unassigned controller cannot fire for P1 */
    keybindings['w'] = "+forward";
    event(-1, 'w', true); /* unassigned keyboard cannot move P1 */
    assert(commands == before);

    keybindings[K_BTN_SOUTH] = "+moveup";
    event(0, K_BTN_SOUTH, true);
    primary.menu_open = true;
    event(0, K_BTN_SOUTH, false);
    assert(!keydown[K_BTN_SOUTH] && strstr(command_text, "-moveup"));
    primary.menu_open = false;
    Key_MarkAllUp();

    /* The primary controller is chosen by assignment, not registry index 0. */
    primary.device_index = 3;
    before = commands;
    event(1, K_BTN_NORTH, true);
    assert(commands == before + 2); /* command plus trailing newline */
    event(0, K_BTN_NORTH, true);
    assert(commands == before + 2);
}

static void test_lobby_confirm_boundary(void)
{
    int before;
    session = lobby = false;
    cls.key_dest = key_menu;
    Key_MarkAllUp();
    event(0, K_BTN_SOUTH, true); /* ordinary menu confirm opens the lobby */
    assert(keydown[K_BTN_SOUTH]);
    lobby = true;
    event(1, K_BTN_SOUTH, true); /* another player's independent held confirm */
    event(0, K_BTN_SOUTH, false);
    assert(!keydown[K_BTN_SOUTH]);
    before = menu_events[2];
    event(1, K_BTN_SOUTH, true);
    assert(menu_events[2] == before); /* other pad's held repeat stays owned */
    lobby = false; /* cancel returns to ordinary menu handling */
    before = menu_events[1];
    event(0, K_BTN_SOUTH, true);
    assert(menu_events[1] == before + 1); /* first new press is accepted */
    event(0, K_BTN_SOUTH, false);
    event(1, K_BTN_SOUTH, false);
    Key_MarkAllUp();
}

static void test_registry(void)
{
    int old[4] = {10, 20, 30, 40}, devices[4] = {20, 30, 40, 50}, slots[4];
    IN_MapControllerSlots(old, devices, 4, slots);
    assert(slots[0] == 1 && slots[1] == 2 && slots[2] == 3 && slots[3] == 0);
    devices[0] = 50; devices[1] = 20;
    IN_MapControllerSlots(old, devices, 2, slots);
    assert(slots[0] == 0 && slots[1] == 1); /* newcomer cannot take survivor's index */
    devices[0] = 40;
    IN_MapControllerSlots(old, devices, 1, slots);
    assert(slots[0] == 3); /* last connected pad remains pad 4 */
}

static void test_input_source(void)
{
    session = lobby = false;
    cls.key_dest = key_game;
    cls.state = ca_active;
    Key_MarkAllUp();
    keybindings[K_TRIG_RIGHT] = "+attack";
    event(0, K_TRIG_RIGHT, true);
    assert(Key_UsingGamepad());
    event(-1, 'w', true);
    assert(!Key_UsingGamepad());
    event(0, K_TRIG_RIGHT, false); /* release cannot steal mouse/keyboard mode */
    assert(!Key_UsingGamepad());
    Key_SetInputGamepad(2); /* analog motion on primary pad 3 */
    assert(Key_UsingGamepad());
    Key_ClearGamepadStates(1);
    assert(Key_UsingGamepad());
    Key_ClearGamepadStates(2);
    assert(!Key_UsingGamepad());
}

int main(void)
{
    test_lobby();
    test_lobby_confirm_boundary();
    test_session();
    test_registry();
    test_input_source();
    puts("gamepad event isolation, launch shortcut, releases, ownership and hotplug slots passed");
    return 0;
}
