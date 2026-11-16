/* Close-up weapon clipping, shared by the hardware and software renderers. */
#ifndef PP_VIEW_WEAPON_CLIP_H
#define PP_VIEW_WEAPON_CLIP_H

#define PP_WEAPON_NEAR_CLIP 0.1f
#define PP_ALIAS_NEAR_CLIP 4.0f

static inline double PP_RenderNearClip(double world_near, int weapon_model)
{
    return weapon_model ? PP_WEAPON_NEAR_CLIP :
        (world_near > PP_WEAPON_NEAR_CLIP ? world_near : PP_WEAPON_NEAR_CLIP);
}

/* Software aliases store inverse depth in a signed fixed-point integer.
 * Map weapon depth into the upper half of its established representable
 * range. An affine function of 1/z preserves screen-space interpolation and
 * self-occlusion; XY projection still uses the actual unmodified distance. */
static inline float PP_AliasDepthKey(float inverse_distance, float depth_scale, int weapon_model)
{
    if (weapon_model)
        return (depth_scale / PP_ALIAS_NEAR_CLIP) *
            (0.5f + 0.5f * PP_WEAPON_NEAR_CLIP * inverse_distance);
    return inverse_distance * depth_scale;
}
#endif
