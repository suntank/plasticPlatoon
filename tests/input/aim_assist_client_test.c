#include "../../src/client/header/client.h"
#include "../../src/client/input/header/aim_assist.h"
#include <assert.h>

static void setup(player_state_t *ps)
{
	memset(ps, 0, sizeof(*ps));
	ps->stats[STAT_AIMASSIST_FLAGS] = AIMASSIST_ACTIVE | AIMASSIST_TARGET;
}

int main(void)
{
	player_state_t ps;
	vec3_t angles = {0}, slow = {0}, fast = {0};
	float x, y;
	int i;
	setup(&ps);
	ps.stats[STAT_AIMASSIST_YAW] = 200;
	for (i = 0; i < 30; i++) PP_AimAssistADS(slow, &ps, 1.0f / 30, 8, 30, true);
	for (i = 0; i < 60; i++) PP_AimAssistADS(fast, &ps, 1.0f / 60, 8, 30, true);
	assert(fabsf(slow[YAW] - fast[YAW]) < 0.0001f);
	assert(slow[YAW] > 1.9f && slow[YAW] < 2);

	/* Full-speed Pi ADS input can always turn away from an assisted target. */
	ps.stats[STAT_AIMASSIST_YAW] = 800;
	for (i = 0; i < 12; i++)
	{
		angles[YAW] -= 55.0f / 60;
		PP_AimAssistADS(angles, &ps, 1.0f / 60, 8, 30, true);
	}
	assert(angles[YAW] < -4.9f);

	setup(&ps);
	VectorSet(angles, 10, 5, 0);
	ps.pmove.delta_angles[PITCH] = ANGLE2SHORT(15);
	ps.pmove.delta_angles[YAW] = ANGLE2SHORT(90);
	VectorSet(ps.viewangles, 25, 95, 0);
	ps.stats[STAT_AIMASSIST_PITCH] = -500;
	ps.stats[STAT_AIMASSIST_YAW] = 500;
	PP_AimAssistADS(angles, &ps, 0.016f, 8, 30, true);
	assert(angles[PITCH] < 10 && angles[YAW] > 5);
	assert(fabsf(angles[PITCH] - 10) < 0.48f && fabsf(angles[YAW] - 5) < 0.48f);
	VectorClear(angles);
	PP_AimAssistADS(angles, &ps, 0.016f, 8, 30, false);
	assert(!angles[PITCH] && !angles[YAW]);
	ps.pmove.pm_type = PM_DEAD;
	PP_AimAssistADS(angles, &ps, 0.016f, 8, 30, true);
	assert(!angles[PITCH] && !angles[YAW]);

	setup(&ps);
	ps.viewangles[YAW] = 359;
	ps.stats[STAT_AIMASSIST_YAW] = 200;
	angles[YAW] = 359;
	PP_AimAssistADS(angles, &ps, 0.016f, 8, 30, true);
	assert(angles[YAW] > 359 && angles[YAW] < 360);
	VectorClear(angles);
	ps.stats[STAT_AIMASSIST_YAW] = 0;
	PP_AimAssistADS(angles, &ps, 0.016f, 8, 30, true);
	assert(angles[YAW] < 0 && angles[YAW] > -1);
	ps.viewangles[YAW] = 90; /* teleport / intentionally abandoned target */
	VectorClear(angles);
	PP_AimAssistADS(angles, &ps, 0.016f, 8, 30, true);
	assert(!angles[YAW]);

	setup(&ps);
	ps.stats[STAT_AIMASSIST_HIP_PITCH] = 400;
	ps.stats[STAT_AIMASSIST_HIP_YAW] = 400;
	PP_AimAssistReticle(&ps, 240, 240, 90, 90, true, &x, &y);
	assert(x < -8 && x > -9 && y > 8 && y < 9);
	/* World yaw at steep pitch occupies less screen space, just like shots. */
	ps.viewangles[PITCH] = 60;
	ps.stats[STAT_AIMASSIST_HIP_PITCH] = 0;
	PP_AimAssistReticle(&ps, 240, 240, 90, 90, true, &x, &y);
	assert(x < -4 && x > -4.5f && fabsf(y) < 0.2f);
	PP_AimAssistReticle(&ps, 240, 240, 90, 90, false, &x, &y);
	assert(!x && !y);
	PP_AimAssistReticle(&ps, 240, 240, 0, 0, true, &x, &y);
	assert(!x && !y);
	puts("Client aim assistance: smooth timing, manual escape, delta angles, gating and shot-aligned reticle passed");
	return 0;
}
