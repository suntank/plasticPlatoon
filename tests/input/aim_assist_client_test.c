#include "../../src/client/header/client.h"
#include "../../src/client/input/header/aim_assist.h"
#include <assert.h>

static void setup(player_state_t *ps)
{
	memset(ps, 0, sizeof(*ps));
	ps->stats[STAT_AIMASSIST_FLAGS] = AIMASSIST_ACTIVE | AIMASSIST_TARGET;
}

static void test_close_low_targets(void)
{
	const int pitches[] = {1900, 2900, 4500, 4700};
	player_state_t ps;
	vec3_t angles;
	int i;
	for (i = 0; i < sizeof(pitches) / sizeof(pitches[0]); ++i)
	{
		setup(&ps);
		VectorClear(angles);
		ps.stats[STAT_AIMASSIST_PITCH] = pitches[i];
		PP_AimAssistADS(angles, &ps, 0.016f, 8, 30, true);
		assert(!angles[PITCH]); /* Extra pitch requires a server-selected close target. */
		ps.stats[STAT_AIMASSIST_FLAGS] |= AIMASSIST_CLOSE_TARGET;
		PP_AimAssistADS(angles, &ps, 0.016f, 8, 30, true);
		assert(angles[PITCH] > 0 && angles[PITCH] <= 0.4801f);
		assert(!angles[YAW]);
	}

	/* Refresh snapshots as the camera settles all the way down onto an ant. */
	setup(&ps);
	ps.stats[STAT_AIMASSIST_FLAGS] |= AIMASSIST_CLOSE_TARGET;
	VectorClear(angles);
	for (i = 0; i < 120; ++i)
	{
		ps.viewangles[PITCH] = angles[PITCH];
		ps.stats[STAT_AIMASSIST_PITCH] = (short)lroundf((29 - angles[PITCH]) * 100);
		PP_AimAssistADS(angles, &ps, 1.0f / 60, 8, 30, true);
	}
	assert(fabsf(angles[PITCH] - 29) < 0.01f);
	ps.viewangles[PITCH] = 29;
	ps.stats[STAT_AIMASSIST_PITCH] = 0;
	angles[PITCH] = 30; /* A small overshoot can settle upward again. */
	PP_AimAssistADS(angles, &ps, 0.016f, 8, 30, true);
	assert(angles[PITCH] < 30 && angles[PITCH] > 29);

	setup(&ps);
	ps.stats[STAT_AIMASSIST_FLAGS] |= AIMASSIST_CLOSE_TARGET;
	ps.stats[STAT_AIMASSIST_PITCH] = 2900;
	VectorSet(angles, 10, -1, 0);
	ps.pmove.delta_angles[PITCH] = ANGLE2SHORT(15);
	VectorSet(ps.viewangles, 25, 359, 0);
	PP_AimAssistADS(angles, &ps, 0.016f, 8, 30, true);
	assert(angles[PITCH] > 10 && angles[PITCH] <= 10.4801f);
	assert(fabsf(angles[YAW] + 1) < 0.001f);

	/* Manual look input still outruns the assist on both axes. */
	setup(&ps);
	ps.stats[STAT_AIMASSIST_FLAGS] |= AIMASSIST_CLOSE_TARGET;
	ps.stats[STAT_AIMASSIST_PITCH] = 2900;
	VectorClear(angles);
	for (i = 0; i < 12; ++i)
	{
		angles[PITCH] -= 55.0f / 60;
		angles[YAW] -= 55.0f / 60;
		PP_AimAssistADS(angles, &ps, 1.0f / 60, 8, 30, true);
	}
	assert(angles[PITCH] < -4.9f && angles[YAW] < -4.9f);
}

static void test_close_snapshot_guards(void)
{
	player_state_t ps;
	vec3_t angles, before;
	int i;
	for (i = 0; i < 10; ++i)
	{
		setup(&ps);
		ps.stats[STAT_AIMASSIST_FLAGS] |= AIMASSIST_CLOSE_TARGET;
		ps.stats[STAT_AIMASSIST_PITCH] = 2900;
		VectorClear(angles);
		switch (i)
		{
			case 0: angles[PITCH] = -15; break; /* Stale after looking up. */
			case 1: angles[PITCH] = 15; break;  /* Stale after looking down. */
			case 2: angles[YAW] = 15; break;
			case 3: ps.stats[STAT_AIMASSIST_YAW] = 1500; break;
			case 4: ps.stats[STAT_AIMASSIST_PITCH] = 4800; break;
			case 5: ps.stats[STAT_AIMASSIST_PITCH] = -1500; break;
			case 6: ps.stats[STAT_AIMASSIST_FLAGS] &= ~AIMASSIST_TARGET; break;
			case 7: ps.stats[STAT_AIMASSIST_FLAGS] &= ~AIMASSIST_ACTIVE; break;
			case 8: ps.pmove.pm_type = PM_DEAD; break;
			case 9: ps.viewangles[PITCH] = NAN; break;
		}
		VectorCopy(angles, before);
		PP_AimAssistADS(angles, &ps, 0.016f, 8, 30, true);
		assert(VectorCompare(angles, before));
	}
	setup(&ps);
	ps.stats[STAT_AIMASSIST_FLAGS] |= AIMASSIST_CLOSE_TARGET;
	ps.stats[STAT_AIMASSIST_PITCH] = 2900;
	VectorClear(angles);
	PP_AimAssistADS(angles, &ps, 0.016f, 8, 30, false);
	PP_AimAssistADS(angles, &ps, NAN, 8, 30, true);
	PP_AimAssistADS(angles, &ps, 0.016f, NAN, 30, true);
	PP_AimAssistADS(angles, &ps, 0.016f, 8, NAN, true);
	assert(!angles[PITCH] && !angles[YAW]);
}

static void test_close_hip_reticle(void)
{
	player_state_t ps;
	float x, y;
	setup(&ps);
	ps.stats[STAT_AIMASSIST_HIP_PITCH] = 2900;
	PP_AimAssistReticle(&ps, 240, 240, 90, 90, true, &x, &y);
	assert(fabsf(x) < 0.001f);
	assert(fabsf(y - 120 * tanf(29 * (float)(M_PI / 180.0))) < 0.001f);
	ps.stats[STAT_AIMASSIST_HIP_PITCH] = 4500;
	PP_AimAssistReticle(&ps, 240, 240, 90, 90, true, &x, &y);
	assert(fabsf(x) < 0.001f && fabsf(y - 120) < 0.001f);
	ps.stats[STAT_AIMASSIST_HIP_PITCH] = 6000; /* Below the visible view. */
	PP_AimAssistReticle(&ps, 320, 180, 90, 90, true, &x, &y);
	assert(fabsf(x) < 0.001f && y == 90);
	ps.stats[STAT_AIMASSIST_HIP_PITCH] = 0;
	ps.stats[STAT_AIMASSIST_HIP_YAW] = 6000;
	PP_AimAssistReticle(&ps, 320, 180, 90, 90, true, &x, &y);
	assert(x == -160 && fabsf(y) < 0.001f);
	ps.stats[STAT_AIMASSIST_HIP_YAW] = 18000; /* An old/invalid behind-view offset. */
	PP_AimAssistReticle(&ps, 320, 180, 90, 90, true, &x, &y);
	assert(!x && !y);
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
	test_close_low_targets();
	test_close_snapshot_guards();
	test_close_hip_reticle();
	puts("Client aim assistance: low close targets, stale snapshot guards, smooth timing, manual escape, delta angles, gating and shot-aligned reticle passed");
	return 0;
}
