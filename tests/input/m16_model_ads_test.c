/* Aim transition, slot isolation, and sight alignment regressions. */
#include "../../src/client/header/m16_model_ads.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>

static float aim_for(pp_m16_ads_state_t *s, int held, int steps, float dt)
{
    float value = 0;
    for (int i = 0; i < steps; ++i)
        value = PP_M16ADSUpdate(s, 1, held, 34, 1, s->last_time + dt, dt);
    return value;
}

int main(void)
{
    pp_m16_ads_state_t a = {0}, b = {0}, slots[4] = {{0}};
    float coarse = aim_for(&a, 1, 3, .03f);
    float fine = aim_for(&b, 1, 9, .01f);
    assert(fabsf(coarse - .5f) < 1e-5f);
    assert(fabsf(coarse - fine) < 1e-5f);
    assert(aim_for(&a, 1, 3, .03f) > .99999f);
    assert(aim_for(&b, 1, 9, .01f) > .99999f);
    assert(aim_for(&a, 0, 18, .01f) < 1e-5f);

    /* Releasing partway through reverses continuously, without snapping. */
    float halfway = aim_for(&a, 1, 9, .01f);
    float reversing = aim_for(&a, 0, 1, .01f);
    assert(reversing > 0 && reversing < halfway);
    assert(aim_for(&a, 0, 9, .01f) == 0);

    /* Two players can aim while two stay at hip, then exchange roles. */
    for (int i = 0; i < 4; ++i) aim_for(&slots[i], !(i & 1), 30, .01f);
    assert(slots[0].progress == 1 && slots[2].progress == 1);
    assert(slots[1].progress == 0 && slots[3].progress == 0);
    for (int i = 0; i < 4; ++i) aim_for(&slots[i], i & 1, 30, .01f);
    assert(slots[0].progress == 0 && slots[2].progress == 0);
    assert(slots[1].progress == 1 && slots[3].progress == 1);

    /* Scoped muzzle effects encode local slots one-based, including slot 4. */
    assert(PP_M16ADSSlotForEffectScope(0) == -1);
    for (int i = 0; i < 4; ++i)
        assert(PP_M16ADSSlotForEffectScope(i + 1) == i);

    /* A screenshot or slow frame cannot pull a held, aligned weapon out of aim. */
    a = slots[1];
    assert(PP_M16ADSUpdate(&a, 1, 1, 34, 1, a.last_time + 1.0f, 1.0f) == 1);

    /* A new weapon/map, reversed clock, or unsupported weapon cannot inherit aim. */
    a = slots[1];
    assert(PP_M16ADSUpdate(&a, 1, 0, 34, 2, .5f, .01f) == 0);
    aim_for(&a, 1, 30, .01f);
    assert(PP_M16ADSUpdate(&a, 0, 1, 2, 1, .9f, .01f) == 0);
    aim_for(&a, 1, 30, .01f);
    assert(PP_M16ADSUpdate(&a, 1, 0, 34, 1, 0, .01f) == 0);

    /* Both authored sight points lie on the center ray at full aim. Quake's
     * local Y has the opposite sign from AngleVectors' right vector. */
    const float rear[3] = {11.91760964f, -7.95f, -.140213786f};
    const float front[3] = {44.69740007f, -7.95f, -.140213786f};
    assert(fabsf(rear[0] + PP_M16_ADS_FORWARD - 9.5f) < .001f);
    assert(front[0] + PP_M16_ADS_FORWARD > rear[0] + PP_M16_ADS_FORWARD);
    assert(fabsf(-rear[1] + PP_M16_ADS_RIGHT) < .001f);
    assert(fabsf(-front[1] + PP_M16_ADS_RIGHT) < .001f);
    assert(fabsf(rear[2] + PP_M16_ADS_UP) < .001f);
    assert(fabsf(front[2] + PP_M16_ADS_UP) < .001f);
    assert(fabsf(PP_M16_MUZZLE_RIGHT + PP_M16_ADS_RIGHT) < .001f);
    puts("M16 actual-model ADS transitions, independent slots and sight alignment passed");
    return 0;
}
