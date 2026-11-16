#include "../../src/client/header/weapon_model_ads.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>

int main(void)
{
    pp_model_ads_config_t double_barrel = PP_ModelADSConfig(PP_MODEL_ADS_SSHOTGUN);
    pp_model_ads_config_t pump = PP_ModelADSConfig(PP_MODEL_ADS_SHOTGUN);
    assert(!double_barrel.animated && pump.animated);
    for (int frame = 0; frame < 64; ++frame)
    {
        /* The rigid double barrel uses procedural recoil/raise and keeps
         * one cached model pose, including when aimed after a pump shotgun. */
        assert(PP_ModelADSFrame(double_barrel, frame) == 0);
        assert(PP_ModelADSFrame(pump, frame) == (frame < 40 ? frame : 0));
    }
    /* The center between the barrels stays below the sight ray, centered
     * horizontally at full aim and ahead of the 9.5-unit rear sight. */
    assert(fabsf(double_barrel.muzzle_right + double_barrel.right) < .001f);
    assert(double_barrel.muzzle_forward + double_barrel.forward > 9.5f);
    assert(double_barrel.muzzle_up + double_barrel.up < 0.f);

    pp_model_ads_state_t slots[4] = {{0}};
    for (int frame = 0; frame < 30; ++frame)
        for (int slot = 0; slot < 4; ++slot)
            PP_ModelADSUpdate(&slots[slot], 1, slot != 1, 30 + slot, 1, frame * .01f, .01f);
    for (int slot = 0; slot < 4; ++slot)
        assert(PP_ModelADSAmount(&slots[slot]) == (slot == 1 ? 0.f : 1.f));
    for (int frame = 0; frame < 30; ++frame)
        PP_ModelADSUpdate(&slots[0], 1, 0, 30, 1, .3f + frame * .01f, .01f);
    assert(PP_ModelADSAmount(&slots[0]) == 0.f);
    assert(PP_ModelADSAmount(&slots[2]) == 1.f);
    assert(PP_ModelADSUpdate(&slots[2], 1, 1, 99, 1, .7f, 0.f) == 0.f);
    assert(PP_ModelADSUpdate(&slots[3], 1, 1, 33, 2, .8f, 0.f) == 0.f);
    puts("Double-barrel model ADS/muzzle alignment, rigid pose and independent aiming passed");
    return 0;
}
