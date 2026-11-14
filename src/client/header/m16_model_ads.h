/* Actual-model M16 sight alignment. GPL-2.0-or-later. */
#ifndef PP_M16_MODEL_ADS_H
#define PP_M16_MODEL_ADS_H

/* The procedural asset generator exports the rear sight at
 * [11.917610, -7.950000, -0.140214] in viewmodel coordinates. Local +Y is
 * the viewer's left, while AngleVectors' right vector points the other way.
 * Pull the rear sight to 9.5 units from the eye and place the common sight
 * line at screen center. These are visual model units, not weapon ballistics. */
#define PP_M16_ADS_FORWARD (-2.417610f)
#define PP_M16_ADS_RIGHT   (-7.950000f)
#define PP_M16_ADS_UP      (0.140214f)
#define PP_M16_ADS_SECONDS (0.18f)
#define PP_M16_MUZZLE_FORWARD (56.498125f)
#define PP_M16_MUZZLE_RIGHT (7.950000f)
#define PP_M16_MUZZLE_UP (-5.778338f)

typedef struct {
	float progress;
	float last_time;
	int gunindex;
	int servercount;
	int valid;
} pp_m16_ads_state_t;

static inline int
PP_M16ADSSlotForEffectScope(int effect_scope)
{
	/* Effect scopes reserve zero for the main unscoped view. */
	return effect_scope > 0 ? effect_scope - 1 : -1;
}

static inline float
PP_M16ADSAmount(const pp_m16_ads_state_t *state)
{
	return state->progress * state->progress * (3.0f - 2.0f * state->progress);
}

static inline float
PP_M16ADSUpdate(pp_m16_ads_state_t *state, int supported, int held,
	int gunindex, int servercount, float now, float dt)
{
	if (!state->valid || state->gunindex != gunindex ||
		state->servercount != servercount || now < state->last_time || !supported)
	{
		state->progress = 0.0f;
	}
	state->valid = 1;
	state->gunindex = gunindex;
	state->servercount = servercount;
	state->last_time = now;
	if (!supported) return 0.0f;
	if (dt < 0.0f) dt = 0.0f;
	if (dt > 0.1f) dt = 0.1f;
	state->progress += (held ? dt : -dt) / PP_M16_ADS_SECONDS;
	if (state->progress < 0.0f) state->progress = 0.0f;
	if (state->progress > 1.0f) state->progress = 1.0f;
	/* Smooth endpoints, with identical motion at different frame rates. */
	return PP_M16ADSAmount(state);
}

#endif
