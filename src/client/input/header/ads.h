#ifndef PP_ADS_INPUT_H
#define PP_ADS_INPUT_H

/* Shared by primary and split-screen input. Angles here exclude kick/recoil. */
typedef struct
{
	qboolean was_ads;
	qboolean active;
	qboolean manual_pitch_pending;
	float start_pitch;
	float target_pitch;
	float delta_pitch;
	float elapsed;
} pp_ads_level_t;

static inline float
PP_ADSLookScale(qboolean ads, float configured)
{
	if (!ads)
	{
		return 1.0f;
	}
	return isfinite(configured) ? Q_clamp(configured, 0.05f, 1.0f) : 0.5f;
}

static inline void
PP_ScaleADSLook(const vec3_t before, vec3_t angles, float scale)
{
	angles[YAW] = before[YAW] + (angles[YAW] - before[YAW]) * scale;
	angles[PITCH] = before[PITCH] + (angles[PITCH] - before[PITCH]) * scale;
}

static inline float
PP_ADSAngleDelta(float angle)
{
	angle = fmodf(angle, 360.0f);
	if (angle > 180.0f) angle -= 360.0f;
	if (angle < -180.0f) angle += 360.0f;
	return angle;
}

static inline void
PP_UpdateADSLevel(pp_ads_level_t *state, vec3_t angles, qboolean ads,
	qboolean enabled, qboolean manual_pitch, float delta_pitch, float seconds,
	float duration)
{
	if (!enabled || !isfinite(duration) || duration <= 0)
	{
		memset(state, 0, sizeof(*state));
		return;
	}

	delta_pitch = PP_ADSAngleDelta(delta_pitch);
	manual_pitch = manual_pitch || state->manual_pitch_pending;
	state->manual_pitch_pending = false;
	if (state->was_ads && !ads && !manual_pitch)
	{
		state->active = true;
		state->start_pitch = angles[PITCH];
		state->target_pitch = angles[PITCH] +
			PP_ADSAngleDelta(-delta_pitch - angles[PITCH]);
		state->delta_pitch = delta_pitch;
		state->elapsed = 0;
	}
	state->was_ads = ads;
	if (ads || manual_pitch ||
		fabsf(PP_ADSAngleDelta(delta_pitch - state->delta_pitch)) > 0.01f)
	{
		state->active = false;
	}
	if (state->active)
	{
		float fraction;
		state->elapsed += Q_max(seconds, 0.0f);
		fraction = Q_clamp(state->elapsed / duration, 0.0f, 1.0f);
		angles[PITCH] = state->start_pitch +
			(state->target_pitch - state->start_pitch) * fraction;
		if (fraction >= 1.0f) state->active = false;
	}
}

#endif
