/* Render helicopter attachments in the interpolated body coordinate system. */
#ifndef PP_HELICOPTER_ROTOR_H
#define PP_HELICOPTER_ROTOR_H

#include <math.h>
#include "../../common/header/shared.h"

static void
PP_ComposeRotorAngles(const vec3_t forward, const vec3_t right, const vec3_t up,
	float phase, qboolean tail, vec3_t angles)
{
	vec3_t local_angles, local_forward, local_right;
	vec3_t world_forward, world_right, base_right, base_up;
	int i;

	VectorClear(local_angles);
	local_angles[tail ? PITCH : YAW] = phase;
	AngleVectors(local_angles, local_forward, local_right, NULL);
	for (i = 0; i < 3; i++)
	{
		world_forward[i] = local_forward[0] * forward[i] - local_forward[1] * right[i]
			+ local_forward[2] * up[i];
		world_right[i] = local_right[0] * forward[i] - local_right[1] * right[i]
			+ local_right[2] * up[i];
	}
	AngleVectors2(world_forward, angles);
	AngleVectors(angles, NULL, base_right, base_up);
	angles[ROLL] = atan2f(-DotProduct(world_right, base_up),
		DotProduct(world_right, base_right)) * (180.0f / M_PI);
}

static void
PP_HelicopterRotorTransform(const vec3_t body_origin, const vec3_t body_angles,
	float phase, qboolean tail, vec3_t origin, vec3_t angles)
{
	vec3_t forward, right, up;
	int i;

	AngleVectors(body_angles, forward, right, up);
	for (i = 0; i < 3; i++)
	{
		origin[i] = body_origin[i] + (tail ? -88.0f * forward[i] - 8.0f * right[i]
			+ 16.0f * up[i] : 48.0f * up[i]);
	}
	PP_ComposeRotorAngles(forward, right, up, phase, tail, angles);
}

static void
PP_Boss2RotorTransform(float phase, vec3_t origin, vec3_t angles)
{
	vec3_t forward, right, up, rotor_right;

	AngleVectors(angles, forward, right, up);
	PP_ComposeRotorAngles(forward, right, up, phase, false, angles);
	AngleVectors(angles, NULL, rotor_right, NULL);

	/* The MD2 mast socket is at (-3.9, 0.5) in body XY. The blade
	 * mesh's axle is at (0, 0.25) and already matches the socket height.
	 * Bring the rotated axle onto the socket for every spin phase. */
	VectorMA(origin, -3.9f, forward, origin);
	VectorMA(origin, -0.5f, right, origin);
	VectorMA(origin, 0.25f, rotor_right, origin);
}

#endif
