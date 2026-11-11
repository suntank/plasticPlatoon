/* Exercise the production input path with deterministic frame/key timing. */
#include "../../src/client/cl_input.c"
#include <assert.h>

client_static_t cls;
client_state_t cl;
int sys_frame_time;

static char key_arg[24], time_arg[24];
static char commands[1024];
static float joy_pitch = 120.0f;
static cvar_t forward_speed, side_speed, up_speed, yaw_speed, pitch_speed;
static cvar_t run, angle_speed, center_time;
static cvar_t ads_sensitivity, autolevel, autolevel_time;

char *Cmd_Argv(int index)
{
    return index == 1 ? key_arg : index == 2 ? time_arg : "";
}

float Cvar_VariableValue(const char *name)
{
    assert(!strcmp(name, "joy_pitchspeed"));
    return joy_pitch;
}

void Cbuf_AddText(char *text)
{
    assert(strlen(commands) + strlen(text) < sizeof(commands));
    strcat(commands, text);
}

void Com_Printf(const char *fmt, ...) {}

static void key(void (*handler)(void), int number)
{
    snprintf(key_arg, sizeof(key_arg), "%d", number);
    snprintf(time_arg, sizeof(time_arg), "%d", sys_frame_time);
    handler();
}

static usercmd_t frame(void)
{
    usercmd_t cmd;
    vec3_t before;
    VectorCopy(cl.viewangles, before);
    sys_frame_time += 100;
    frame_msec = 100;
    cls.nframetime = 0.1f;
    CL_BaseMove(&cmd);
    CL_UpdateGameBirdLevel(before);
    return cmd;
}

static void reset(void)
{
    CL_ClearGameBirdInput();
    memset(&cl, 0, sizeof(cl));
    memset(&cls, 0, sizeof(cls));
    memset(&in_ads, 0, sizeof(in_ads));
    memset(&in_up, 0, sizeof(in_up));
    memset(&in_down, 0, sizeof(in_down));
    memset(&in_forward, 0, sizeof(in_forward));
    commands[0] = '\0';
    sys_frame_time = 1000;
    joy_pitch = 120.0f;
    forward_speed.value = side_speed.value = up_speed.value = 200;
    yaw_speed.value = 110;
    pitch_speed.value = 150;
    run.value = 0;
    angle_speed.value = 1.5f;
    center_time.value = 0;
    ads_sensitivity.value = 0.5f;
    autolevel.value = 0;
    autolevel_time.value = 0.25f;
    cl_forwardspeed = &forward_speed;
    cl_sidespeed = &side_speed;
    cl_upspeed = &up_speed;
    cl_yawspeed = &yaw_speed;
    cl_pitchspeed = &pitch_speed;
    cl_run = &run;
    cl_anglespeedkey = &angle_speed;
    cl_centertime = &center_time;
    cl_ads_sensitivity = &ads_sensitivity;
    cl_gamebird_autolevel = &autolevel;
    cl_gamebird_autolevel_time = &autolevel_time;
    cls.state = ca_active;
    cls.key_dest = key_game;
}

static void test_movement_and_aim(void)
{
    usercmd_t cmd;
    float yaw, pitch;

    reset();
    key(IN_GameBirdUpDown, 100);
    key(IN_GameBirdLeftDown, 102);
    cmd = frame();
    assert(cmd.forwardmove > 0 && cmd.sidemove == 0);
    assert(cl.viewangles[YAW] > 0 && cl.viewangles[PITCH] == 0);

    /* Changing ADS with Up still held changes its action immediately. */
    key(IN_ADSDown, 110);
    yaw = cl.viewangles[YAW];
    cmd = frame();
    assert(cmd.forwardmove == 0 && cl.viewangles[PITCH] < 0);
    assert(cl.viewangles[YAW] > yaw);
    pitch = cl.viewangles[PITCH];
    joy_pitch = -120.0f;
    cmd = frame();
    assert(cmd.forwardmove == 0 && cl.viewangles[PITCH] > pitch);

    key(IN_ADSUp, 110);
    pitch = cl.viewangles[PITCH];
    cmd = frame();
    assert(cmd.forwardmove > 0 && cl.viewangles[PITCH] == pitch);
    key(IN_GameBirdUpUp, 100);
    key(IN_GameBirdLeftUp, 102);
    yaw = cl.viewangles[YAW];
    cmd = frame();
    assert(cmd.forwardmove == 0 && cl.viewangles[YAW] == yaw);

    reset();
    key(IN_GameBirdDownDown, 101);
    key(IN_GameBirdRightDown, 103);
    cmd = frame();
    assert(cmd.forwardmove < 0 && cl.viewangles[YAW] < 0);
    key(IN_ADSDown, 110);
    cmd = frame();
    assert(cmd.forwardmove == 0 && cl.viewangles[PITCH] > 0);
    pitch = cl.viewangles[PITCH];
    joy_pitch = -120;
    cmd = frame();
    assert(cmd.forwardmove == 0 && cl.viewangles[PITCH] < pitch);
    key(IN_GameBirdDownUp, 101);
    key(IN_GameBirdRightUp, 103);
    pitch = cl.viewangles[PITCH];
    yaw = cl.viewangles[YAW];
    cmd = frame();
    assert(cmd.forwardmove == 0 && cl.viewangles[PITCH] == pitch);
    assert(cl.viewangles[YAW] == yaw);
}

static void test_modifier_and_crouch(void)
{
    usercmd_t cmd;
    float yaw, pitch;

    reset();
    key(IN_GameBirdModifierDown, 120);
    key(IN_GameBirdUpDown, 100);
    assert(!strcmp(commands, "help\n"));
    key(IN_GameBirdUpDown, 100);
    assert(!strcmp(commands, "help\n"));
    key(IN_GameBirdUpUp, 100);
    key(IN_GameBirdUpDown, 100);
    assert(!strcmp(commands, "help\nhelp\n"));
    key(IN_GameBirdUpUp, 100);
    commands[0] = '\0';
    key(IN_GameBirdLeftDown, 102);
    key(IN_GameBirdRightDown, 103);
    cmd = frame();
    assert(strstr(commands, "weapprev\n") && strstr(commands, "weapnext\n"));
    assert(cmd.forwardmove == 0 && cmd.sidemove == 0);
    assert(cl.viewangles[YAW] == 0 && cl.viewangles[PITCH] == 0);
    /* Neither a repeat nor a held direction repeatedly changes weapons. */
    commands[0] = '\0';
    key(IN_GameBirdLeftDown, 102);
    key(IN_GameBirdRightDown, 103);
    frame();
    assert(commands[0] == '\0');
    key(IN_GameBirdLeftUp, 102);
    key(IN_GameBirdRightUp, 103);

    key(IN_GameBirdDownDown, 101);
    cmd = frame();
    assert(gb_crouched && cmd.upmove < 0 && cmd.forwardmove == 0);
    key(IN_GameBirdDownDown, 101);
    frame();
    assert(gb_crouched);
    key(IN_GameBirdDownUp, 101);
    key(IN_GameBirdModifierUp, 120);
    cmd = frame();
    assert(gb_crouched && cmd.upmove < 0);

    key(IN_UpDown, 130);
    cmd = frame();
    assert(!gb_crouched && cmd.upmove > 0);
    key(IN_UpUp, 130);
    cmd = frame();
    assert(cmd.upmove == 0);

    key(IN_GameBirdModifierDown, 120);
    key(IN_GameBirdDownDown, 101);
    frame();
    key(IN_GameBirdDownUp, 101);
    assert(gb_crouched);
    key(IN_GameBirdDownDown, 101);
    frame();
    assert(!gb_crouched);
    key(IN_GameBirdDownUp, 101);

    /* ADS + modifier uses weapon/crouch actions, without moving the view. */
    key(IN_ADSDown, 110);
    key(IN_GameBirdUpDown, 100);
    key(IN_GameBirdRightDown, 103);
    yaw = cl.viewangles[YAW];
    pitch = cl.viewangles[PITCH];
    cmd = frame();
    assert(cmd.forwardmove == 0 && cl.viewangles[YAW] == yaw);
    assert(cl.viewangles[PITCH] == pitch);
    key(IN_GameBirdModifierUp, 120);
    cmd = frame();
    assert(cmd.forwardmove == 0 && cl.viewangles[YAW] < yaw);
    assert(cl.viewangles[PITCH] < pitch);
    key(IN_GameBirdUpUp, 100);
    key(IN_GameBirdRightUp, 103);
    yaw = cl.viewangles[YAW];
    pitch = cl.viewangles[PITCH];
    frame();
    assert(cl.viewangles[YAW] == yaw && cl.viewangles[PITCH] == pitch);
}

static void test_held_direction_and_reset(void)
{
    usercmd_t cmd;

    reset();
    key(IN_GameBirdDownDown, 101);
    frame();
    key(IN_GameBirdModifierDown, 120);
    cmd = frame();
    assert(!gb_crouched && cmd.forwardmove == 0);
    /* A direction held before the modifier does not trigger a toggle. */
    key(IN_GameBirdModifierUp, 120);
    cmd = frame();
    assert(!gb_crouched && cmd.forwardmove < 0);
    key(IN_GameBirdDownUp, 101);

    key(IN_GameBirdModifierDown, 120);
    key(IN_GameBirdDownDown, 101);
    frame();
    assert(gb_crouched);
    CL_ReleaseGameBirdKeys();
    cmd = frame();
    assert(gb_crouched && cmd.forwardmove == 0 && cmd.upmove < 0);
    assert(!(in_gb_modifier.state & 1));
    /* Pausing/options release the held controls, retaining the crouch toggle. */
    CL_ClearGameBirdInput();
    cmd = frame();
    assert(!gb_crouched && cmd.forwardmove == 0 && cmd.upmove == 0);
    assert(!(in_gb_modifier.state & 1));
    /* Late releases after a level reset are harmless. */
    key(IN_GameBirdDownUp, 101);
    key(IN_GameBirdModifierUp, 120);
    cmd = frame();
    assert(cmd.forwardmove == 0 && cmd.upmove == 0);
}

static void test_death_and_keyboard(void)
{
    usercmd_t cmd;

    reset();
    key(IN_GameBirdModifierDown, 120);
    key(IN_GameBirdDownDown, 101);
    frame();
    assert(gb_crouched);
    cl.frame.playerstate.pmove.pm_type = PM_DEAD;
    cmd = frame();
    assert(!gb_crouched && cmd.upmove == 0);
    cl.frame.playerstate.pmove.pm_type = PM_NORMAL;
    cmd = frame();
    assert(!gb_crouched && cmd.upmove == 0);

    reset();
    key(IN_ADSDown, 110);
    key(IN_ForwardDown, 140);
    cmd = frame();
    assert(cmd.forwardmove > 0 && cl.viewangles[PITCH] == 0);
    /* ADS only changes the handheld D-pad, preserving keyboard movement. */
    key(IN_GameBirdModifierDown, 120);
    cmd = frame();
    assert(cmd.forwardmove > 0 && cl.viewangles[PITCH] == 0);
    key(IN_ForwardUp, 140);
    cmd = frame();
    assert(cmd.forwardmove == 0);
}

static void test_ads_slowdown_and_linear_return(void)
{
    float normal_yaw, pitched;
    vec3_t before = {20, 350, 0}, angles = {30, 370, 0};
    reset();
    key(IN_GameBirdLeftDown, 102);
    frame();
    normal_yaw = cl.viewangles[YAW];
    key(IN_ADSDown, 110);
    frame();
    assert(fabsf((cl.viewangles[YAW] - normal_yaw) - normal_yaw * 0.5f) < 0.001f);
    key(IN_GameBirdUpDown, 100);
    frame();
    assert(fabsf(cl.viewangles[PITCH] + 6) < 0.001f);
    /* The backend's boundary scales mouse/stick/gyro deltas, including yaw
     * crossing 360 degrees, while preserving the angle before input. */
    PP_ScaleADSLook(before, angles, CL_ADSLookScale());
    assert(angles[PITCH] == 25 && angles[YAW] == 360);

    reset();
    autolevel.value = 1;
    cl.viewangles[PITCH] = 30;
    key(IN_ADSDown, 110);
    frame();
    key(IN_ADSUp, 110);
    frame();
    assert(fabsf(cl.viewangles[PITCH] - 18) < 0.001f);
    frame();
    assert(fabsf(cl.viewangles[PITCH] - 6) < 0.001f);
    frame();
    assert(fabsf(cl.viewangles[PITCH]) < 0.001f && !gb_autolevel.active);

    /* Level is relative to the server's delta angle, not local pitch zero. */
    cl.frame.playerstate.pmove.delta_angles[PITCH] = ANGLE2SHORT(20);
    cl.viewangles[PITCH] = 10;
    key(IN_ADSDown, 110); frame();
    key(IN_ADSUp, 110); frame(); frame(); frame();
    assert(fabsf(cl.viewangles[PITCH] + SHORT2ANGLE(cl.frame.playerstate.pmove.delta_angles[PITCH])) < 0.001f);

    cl.frame.playerstate.pmove.delta_angles[PITCH] = 0;
    cl.viewangles[PITCH] = -30;
    key(IN_ADSDown, 110); frame();
    key(IN_ADSUp, 110); frame();
    assert(cl.viewangles[PITCH] < 0 && cl.viewangles[PITCH] > -30);
    key(IN_LookdownDown, 141); frame();
    assert(!gb_autolevel.active);
    key(IN_LookdownUp, 141);
    pitched = cl.viewangles[PITCH]; frame();
    assert(cl.viewangles[PITCH] == pitched);

    cl.viewangles[PITCH] = 30;
    key(IN_ADSDown, 110); frame();
    key(IN_ADSUp, 110); frame();
    key(IN_ADSDown, 110); frame();
    assert(!gb_autolevel.active);
    key(IN_ADSUp, 110);
    CL_ReleaseGameBirdKeys();
    pitched = cl.viewangles[PITCH]; frame();
    assert(cl.viewangles[PITCH] == pitched);

    /* Desktop is unchanged on release unless the handheld option is enabled. */
    reset();
    cl.viewangles[PITCH] = 30;
    key(IN_ADSDown, 110); frame();
    key(IN_ADSUp, 110); frame(); frame(); frame();
    assert(cl.viewangles[PITCH] == 30);
}

int main(void)
{
    test_movement_and_aim();
    test_modifier_and_crouch();
    test_held_direction_and_reset();
    test_death_and_keyboard();
    test_ads_slowdown_and_linear_return();
    puts("Game Bird movement, ADS inversion, modifier, crouch, jump and reset passed");
    return 0;
}
