/* Exercise the actual SDL flick clock, without opening a controller/device. */
#include "../../src/client/input/sdl2.c"
#include <assert.h>

client_static_t cls;
client_state_t cl;
static float ads_scale;
float CL_ADSLookScale(void) { return ads_scale; }

static void begin(float angle, float scale)
{
    memset(&cl, 0, sizeof(cl));
    ads_scale = scale;
    target_angle = angle;
    flick_progress = flick_elapsed = frame_flick_yaw = 0;
    flick_update_time = sys_frame_time = 1000;
}

static void advance(int milliseconds)
{
    sys_frame_time += milliseconds;
    IN_AdvanceFlickStick();
}

int main(void)
{
    begin(180, 0.5f);
    advance(100);
    assert(flick_progress < 1 && fabsf(cl.viewangles[YAW] - 135) < 0.001f);
    advance(100);
    assert(flick_progress == 1 && fabsf(cl.viewangles[YAW] - 180) < 0.001f);
    assert(fabsf(frame_flick_yaw - 180) < 0.001f);
    begin(-180, 0.5f);
    for (int i = 0; i < 8; ++i) advance(25);
    assert(flick_progress == 1 && fabsf(cl.viewangles[YAW] + 180) < 0.001f);
    begin(90, 1);
    advance(100);
    assert(flick_progress == 1 && cl.viewangles[YAW] == 90);
    /* Entering ADS partway through a turn slows it without reversing it. */
    begin(180, 1);
    advance(50);
    ads_scale = 0.5f;
    advance(50);
    assert(cl.viewangles[YAW] > 135 && cl.viewangles[YAW] < 180);
    advance(50);
    assert(flick_progress == 1 && cl.viewangles[YAW] == 180);
    puts("ADS flick-stick timing preserves 90/180 degree destinations passed");
    return 0;
}
