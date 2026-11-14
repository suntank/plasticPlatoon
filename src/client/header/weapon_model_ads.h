/* Shared model ADS transitions and weapon-specific alignment. */
#ifndef PP_WEAPON_MODEL_ADS_H
#define PP_WEAPON_MODEL_ADS_H
#include "m16_model_ads.h"
#include "pistol_model_ads.h"

typedef pp_m16_ads_state_t pp_model_ads_state_t;
#define PP_ModelADSAmount PP_M16ADSAmount
#define PP_ModelADSUpdate PP_M16ADSUpdate
#define PP_ModelADSSlotForEffectScope PP_M16ADSSlotForEffectScope

typedef struct {
    float forward, right, up;
    float muzzle_forward, muzzle_right, muzzle_up;
} pp_model_ads_config_t;

static inline pp_model_ads_config_t PP_ModelADSConfig(int pistol)
{
    const pp_model_ads_config_t rifle = {PP_M16_ADS_FORWARD, PP_M16_ADS_RIGHT,
        PP_M16_ADS_UP, PP_M16_MUZZLE_FORWARD, PP_M16_MUZZLE_RIGHT, PP_M16_MUZZLE_UP};
    const pp_model_ads_config_t sidearm = {PP_PISTOL_ADS_FORWARD, PP_PISTOL_ADS_RIGHT,
        PP_PISTOL_ADS_UP, PP_PISTOL_MUZZLE_FORWARD, PP_PISTOL_MUZZLE_RIGHT, PP_PISTOL_MUZZLE_UP};
    return pistol ? sidearm : rifle;
}
#endif
