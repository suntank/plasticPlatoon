#ifndef PP_CLIENT_AIM_ASSIST_H
#define PP_CLIENT_AIM_ASSIST_H

/* Server-selected targets keep friendly/dead/occluded filtering authoritative.
 * Snapshot viewangles are in world space; input angles exclude pmove deltas. */
static inline float
PP_AimAngleDelta(float angle)
{
	angle = fmodf(angle, 360.0f);
	if (angle > 180.0f) angle -= 360.0f;
	if (angle < -180.0f) angle += 360.0f;
	return angle;
}

static inline void
PP_AimAssistADS(vec3_t angles, const player_state_t *ps, float seconds,
	float strength, float max_speed, qboolean enabled)
{
	float error[2], drift[2], length, fraction;
	int axis;
	if (!enabled || !ps || ps->pmove.pm_type >= PM_DEAD ||
		!(ps->stats[STAT_AIMASSIST_FLAGS] & AIMASSIST_ACTIVE) ||
		!(ps->stats[STAT_AIMASSIST_FLAGS] & AIMASSIST_TARGET) ||
		!isfinite(seconds) || seconds <= 0 || !isfinite(strength) || strength <= 0 ||
		!isfinite(max_speed) || max_speed <= 0)
	{
		return;
	}
	seconds = Q_min(seconds, 0.1f);
	for (axis = PITCH; axis <= YAW; axis++)
	{
		int stat = axis == PITCH ? STAT_AIMASSIST_PITCH : STAT_AIMASSIST_YAW;
		float target = ps->viewangles[axis] + ps->stats[stat] * 0.01f;
		float view = angles[axis] + SHORT2ANGLE(ps->pmove.delta_angles[axis]);
		error[axis] = PP_AimAngleDelta(target - view);
		drift[axis] = PP_AimAngleDelta(view - ps->viewangles[axis]);
	}
	length = sqrtf(error[PITCH] * error[PITCH] + error[YAW] * error[YAW]);
	if (!isfinite(length)) return;
	if (ps->stats[STAT_AIMASSIST_FLAGS] & AIMASSIST_CLOSE_TARGET)
	{
		float snapshot_pitch = ps->stats[STAT_AIMASSIST_PITCH] * 0.01f;
		/* A nearby low enemy can be well below the crosshair. Keep its yaw
		 * narrow and reject stale views independently of that extra pitch. */
		if (hypotf(drift[PITCH], drift[YAW]) > 14.0f ||
			fabsf(error[YAW]) > 14.0f || error[PITCH] < -14.0f ||
			error[PITCH] > AIMASSIST_CLOSE_PITCH + 2.01f ||
			snapshot_pitch < -14.0f || snapshot_pitch > AIMASSIST_CLOSE_PITCH + 2.01f)
		{
			return;
		}
	}
	else if (length > 14.0f)
	{
		/* Reject stale snapshots after a deliberate turn or a teleport. */
		return;
	}
	fraction = 1.0f - expf(-Q_min(strength, 30.0f) * seconds);
	if (length * fraction > max_speed * seconds && length > 0)
	{
		fraction = max_speed * seconds / length;
	}
	angles[PITCH] += error[PITCH] * fraction;
	angles[YAW] += error[YAW] * fraction;
}

static inline void
PP_AimAssistReticle(const player_state_t *ps, int width, int height,
	float fov_x, float fov_y, qboolean enabled, float *x, float *y)
{
	vec3_t shot_angles, forward, right, up, direction;
	float depth;
	*x = *y = 0;
	if (!enabled || !ps || width <= 0 || height <= 0 ||
		ps->pmove.pm_type >= PM_DEAD ||
		!(ps->stats[STAT_AIMASSIST_FLAGS] & AIMASSIST_ACTIVE) ||
		!isfinite(fov_x) || !isfinite(fov_y) ||
		fov_x <= 1 || fov_x >= 179 || fov_y <= 1 || fov_y >= 179)
	{
		return;
	}
	VectorCopy(ps->viewangles, shot_angles);
	shot_angles[PITCH] += ps->stats[STAT_AIMASSIST_HIP_PITCH] * 0.01f;
	shot_angles[YAW] += ps->stats[STAT_AIMASSIST_HIP_YAW] * 0.01f;
	AngleVectors(ps->viewangles, forward, right, up);
	AngleVectors(shot_angles, direction, NULL, NULL);
	depth = DotProduct(direction, forward);
	if (!isfinite(depth) || depth <= 0.01f) return;
	*x = DotProduct(direction, right) / depth *
		width / (2 * tanf(fov_x * (float)(M_PI / 360.0)));
	*y = -DotProduct(direction, up) / depth *
		height / (2 * tanf(fov_y * (float)(M_PI / 360.0)));
	/* Preserve shot alignment for low enemies throughout the visible view;
	 * offscreen or malformed offsets stop at its edges. */
	*x = Q_clamp(*x, -width * 0.5f, width * 0.5f);
	*y = Q_clamp(*y, -height * 0.5f, height * 0.5f);
}

#endif
