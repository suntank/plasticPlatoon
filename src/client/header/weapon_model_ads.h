/* Shared model ADS transitions and weapon-specific alignment. */
#ifndef PP_WEAPON_MODEL_ADS_H
#define PP_WEAPON_MODEL_ADS_H
#include "m16_model_ads.h"
#include "smg_model_ads.h"
#include "thunderhead_model_ads.h"
#include "pistol_model_ads.h"
#include "shotgun_model_ads.h"
#include "sshotgun_model_ads.h"
#include "m60_model_ads.h"
#include "glauncher_model_ads.h"
#include "rlauncher_model_ads.h"
#include "sniper_model_ads.h"
#include "flamethrower_model_ads.h"
#include "mortar_model_ads.h"

typedef pp_m16_ads_state_t pp_model_ads_state_t;
#define PP_ModelADSAmount PP_M16ADSAmount
#define PP_ModelADSUpdate PP_M16ADSUpdate
#define PP_ModelADSSlotForEffectScope PP_M16ADSSlotForEffectScope

enum {
    PP_MODEL_ANIM_DRUM = -1,
    PP_MODEL_ANIM_PUMP = 40
};

typedef struct {
    float forward, right, up;
    float muzzle_forward, muzzle_right, muzzle_up;
    int animated; /* Authored frame count, zero for a rigid model, or PP_MODEL_ANIM_DRUM. */
    float recoil_back; /* ADS travel limit; zero preserves the M16's motion. */
} pp_model_ads_config_t;

enum {
    PP_MODEL_ADS_RIFLE,
    PP_MODEL_ADS_PISTOL,
    PP_MODEL_ADS_SHOTGUN,
    PP_MODEL_ADS_SSHOTGUN,
    PP_MODEL_ADS_M60,
    PP_MODEL_ADS_GLAUNCHER,
    PP_MODEL_ADS_RLAUNCHER,
    PP_MODEL_ADS_SNIPER,
    PP_MODEL_ADS_FLAMETHROWER,
    PP_MODEL_ADS_MORTAR,
    PP_MODEL_ADS_SMG,
    PP_MODEL_ADS_THUNDERHEAD
};

static inline pp_model_ads_config_t PP_ModelADSConfig(int weapon)
{
    const pp_model_ads_config_t rifle = {PP_M16_ADS_FORWARD, PP_M16_ADS_RIGHT,
        PP_M16_ADS_UP, PP_M16_MUZZLE_FORWARD, PP_M16_MUZZLE_RIGHT, PP_M16_MUZZLE_UP, 0, 0};
    const pp_model_ads_config_t sidearm = {PP_PISTOL_ADS_FORWARD, PP_PISTOL_ADS_RIGHT,
        PP_PISTOL_ADS_UP, PP_PISTOL_MUZZLE_FORWARD, PP_PISTOL_MUZZLE_RIGHT, PP_PISTOL_MUZZLE_UP, 0, .35f};
    const pp_model_ads_config_t shotgun = {PP_SHOTGUN_ADS_FORWARD, PP_SHOTGUN_ADS_RIGHT,
        PP_SHOTGUN_ADS_UP, PP_SHOTGUN_MUZZLE_FORWARD, PP_SHOTGUN_MUZZLE_RIGHT,
        PP_SHOTGUN_MUZZLE_UP, PP_MODEL_ANIM_PUMP, .60f};
    const pp_model_ads_config_t double_barrel = {PP_SSHOTGUN_ADS_FORWARD, PP_SSHOTGUN_ADS_RIGHT,
        PP_SSHOTGUN_ADS_UP, PP_SSHOTGUN_MUZZLE_FORWARD, PP_SSHOTGUN_MUZZLE_RIGHT,
        PP_SSHOTGUN_MUZZLE_UP, 0, .70f};
    const pp_model_ads_config_t m60 = {PP_M60_ADS_FORWARD, PP_M60_ADS_RIGHT,
        PP_M60_ADS_UP, PP_M60_MUZZLE_FORWARD, PP_M60_MUZZLE_RIGHT, PP_M60_MUZZLE_UP, 0, .25f};
    const pp_model_ads_config_t launcher = {PP_GLAUNCHER_ADS_FORWARD, PP_GLAUNCHER_ADS_RIGHT,
        PP_GLAUNCHER_ADS_UP, PP_GLAUNCHER_MUZZLE_FORWARD, PP_GLAUNCHER_MUZZLE_RIGHT,
        PP_GLAUNCHER_MUZZLE_UP, PP_MODEL_ANIM_DRUM, .55f};
    const pp_model_ads_config_t rocket = {PP_RLAUNCHER_ADS_FORWARD, PP_RLAUNCHER_ADS_RIGHT,
        PP_RLAUNCHER_ADS_UP, PP_RLAUNCHER_MUZZLE_FORWARD, PP_RLAUNCHER_MUZZLE_RIGHT,
        PP_RLAUNCHER_MUZZLE_UP, 0, .50f};
    const pp_model_ads_config_t sniper = {PP_SNIPER_ADS_FORWARD, PP_SNIPER_ADS_RIGHT,
        PP_SNIPER_ADS_UP, PP_SNIPER_MUZZLE_FORWARD, PP_SNIPER_MUZZLE_RIGHT,
        PP_SNIPER_MUZZLE_UP, 0, .30f};
    const pp_model_ads_config_t flamethrower = {PP_FLAMETHROWER_ADS_FORWARD, PP_FLAMETHROWER_ADS_RIGHT,
        PP_FLAMETHROWER_ADS_UP, PP_FLAMETHROWER_MUZZLE_FORWARD, PP_FLAMETHROWER_MUZZLE_RIGHT,
        PP_FLAMETHROWER_MUZZLE_UP, 0, .08f};
    const pp_model_ads_config_t mortar = {PP_MORTAR_ADS_FORWARD, PP_MORTAR_ADS_RIGHT,
        PP_MORTAR_ADS_UP, PP_MORTAR_MUZZLE_FORWARD, PP_MORTAR_MUZZLE_RIGHT,
        PP_MORTAR_MUZZLE_UP, 0, .65f};
    const pp_model_ads_config_t smg = {PP_SMG_ADS_FORWARD, PP_SMG_ADS_RIGHT,
        PP_SMG_ADS_UP, PP_SMG_MUZZLE_FORWARD, PP_SMG_MUZZLE_RIGHT,
        PP_SMG_MUZZLE_UP, PP_SMG_VIEW_FRAMES, .40f};
    const pp_model_ads_config_t thunderhead = {PP_THUNDERHEAD_ADS_FORWARD, PP_THUNDERHEAD_ADS_RIGHT,
        PP_THUNDERHEAD_ADS_UP, PP_THUNDERHEAD_MUZZLE_FORWARD, PP_THUNDERHEAD_MUZZLE_RIGHT,
        PP_THUNDERHEAD_MUZZLE_UP, PP_THUNDERHEAD_VIEW_FRAMES, .60f};
    if (weapon == PP_MODEL_ADS_SHOTGUN) return shotgun;
    if (weapon == PP_MODEL_ADS_SSHOTGUN) return double_barrel;
    if (weapon == PP_MODEL_ADS_M60) return m60;
    if (weapon == PP_MODEL_ADS_GLAUNCHER) return launcher;
    if (weapon == PP_MODEL_ADS_RLAUNCHER) return rocket;
    if (weapon == PP_MODEL_ADS_SNIPER) return sniper;
    if (weapon == PP_MODEL_ADS_FLAMETHROWER) return flamethrower;
    if (weapon == PP_MODEL_ADS_MORTAR) return mortar;
    if (weapon == PP_MODEL_ADS_SMG) return smg;
    if (weapon == PP_MODEL_ADS_THUNDERHEAD) return thunderhead;
    return weapon == PP_MODEL_ADS_PISTOL ? sidearm : rifle;
}

/* Apply after procedural smoothing so an old hip-fire kick cannot linger in
 * the aimed pose. Full ADS stays on the sight axis with a small rearward
 * translation; partial ADS blends continuously into the original motion.
 * Camera recoil, server weapon behavior and articulated pump frames are
 * independent. Zero blend and the M16 return without touching any values. */
static inline void
PP_ModelADSConstrainMotion(pp_model_ads_config_t config, float blend, float hip_back,
    const float forward[3], const float right[3], const float up[3],
    const float base_origin[3], const float base_angles[3], float origin[3], float angles[3])
{
    float delta[3], local_forward=0, local_right=0, local_up=0;
    float scale, limit;
    int i;
    if (config.recoil_back <= 0 || blend <= 0 || hip_back <= 0) return;
    if (blend > 1) blend=1;
    for (i=0;i<3;i++) {
        delta[i]=origin[i]-base_origin[i];
        local_forward+=delta[i]*forward[i];
        local_right+=delta[i]*right[i];
        local_up+=delta[i]*up[i];
    }
    scale=1-blend+blend*config.recoil_back/hip_back;
    /* A raising weapon can start farther back than a recoil impulse. Fade
     * that existing tail continuously instead of snapping at ADS entry. */
    limit=-local_forward > hip_back ? -local_forward : hip_back;
    limit=(1-blend)*limit+blend*config.recoil_back;
    local_forward*=scale;
    if (local_forward < -limit) local_forward=-limit;
    local_right*=1-blend;
    local_up*=1-blend;
    for (i=0;i<3;i++) {
        float angle=angles[i]-base_angles[i];
        while (angle > 180) angle-=360;
        while (angle < -180) angle+=360;
        origin[i]=base_origin[i]+local_forward*forward[i]+local_right*right[i]+local_up*up[i];
        angles[i]=base_angles[i]+angle*(1-blend);
    }
}

/* Map the server schedule to each model's authored frames. */
static inline int PP_ModelADSFrame(pp_model_ads_config_t config, int gunframe)
{
    if (config.animated == PP_MODEL_ANIM_DRUM)
    {
        if (gunframe >= PP_GLAUNCHER_DRUM_FIRST_FRAME &&
            gunframe < PP_GLAUNCHER_DRUM_FIRST_FRAME + PP_GLAUNCHER_DRUM_STEPS)
            return gunframe - PP_GLAUNCHER_DRUM_FIRST_FRAME + 1;
        return 0;
    }
    return gunframe >= 0 && gunframe < config.animated ? gunframe : 0;
}

static inline int PP_ModelADSPreviousFrame(pp_model_ads_config_t config, int oldgunframe, int frame)
{
    /* Both ends of one drum step look identical. Blending their vertex
     * indices would make the drum rotate backward on its way to idle. */
    if (config.animated == PP_MODEL_ANIM_DRUM && frame == 0)
        return 0;
    return PP_ModelADSFrame(config, oldgunframe);
}
#endif
