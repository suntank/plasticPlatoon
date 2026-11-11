/* Exercise the same attachment transform used for client rendering. */
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include "../../src/client/header/helicopter_rotor.h"

static void check(const vec3_t body_origin, const vec3_t body_angles, float phase, qboolean tail)
{
    vec3_t origin, angles, forward, right, up, rf, rr, ru, expected;
    int i;
    PP_HelicopterRotorTransform(body_origin, body_angles, phase, tail, origin, angles);
    AngleVectors(body_angles, forward, right, up);
    AngleVectors(angles, rf, rr, ru);
    for (i = 0; i < 3; i++)
    {
        expected[i] = body_origin[i] + (tail ? -88 * forward[i] - 8 * right[i] + 16 * up[i] : 48 * up[i]);
        assert(fabsf(origin[i] - expected[i]) < .001f);
    }
    /* The spin must never move the axle away from the body. */
    if (tail) assert(DotProduct(rr, right) > .9999f);
    else assert(DotProduct(ru, up) > .9999f);
}

static void check_dropship(const vec3_t body_origin, const vec3_t body_angles, float phase)
{
    vec3_t origin, angles, forward, right, up, rotor_right, rotor_up, socket, hub;
    int i;
    VectorCopy(body_origin, origin);
    VectorCopy(body_angles, angles);
    PP_Boss2RotorTransform(phase, origin, angles);
    AngleVectors(body_angles, forward, right, up);
    AngleVectors(angles, NULL, rotor_right, rotor_up);
    VectorMA(body_origin, -3.9f, forward, socket);
    VectorMA(socket, -0.5f, right, socket);
    VectorMA(socket, 81.3f, up, socket);
    VectorMA(origin, -0.25f, rotor_right, hub);
    VectorMA(hub, 81.3f, rotor_up, hub);
    for (i = 0; i < 3; i++)
        assert(fabsf(hub[i] - socket[i]) < .001f);
    assert(DotProduct(rotor_up, up) > .9999f);
}

int main(void)
{
    vec3_t origin = {123, -78, 320};
    vec3_t angles;
    int i, phase, tail;
    for (i = 0; i <= 100; i++)
    {
        /* Turning, banking, and tumbling through the tail's pitch poles. */
        VectorSet(origin, 123 + i * 3, -78 + i, 320 - i * 2);
        VectorSet(angles, -80 + i * 1.6f, 5 + i * 2.1f, -70 + i * 1.4f);
        for (phase = 0; phase < 360; phase += 3)
        {
            for (tail = 0; tail < 2; tail++)
                check(origin, angles, (float)phase, tail);
            check_dropship(origin, angles, (float)phase);
        }
    }
    puts("helicopter rotor render transforms passed");
    return 0;
}
