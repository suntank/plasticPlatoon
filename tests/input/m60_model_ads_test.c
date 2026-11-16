#include "../../src/client/header/weapon_model_ads.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>

int main(void)
{
    pp_model_ads_config_t m60 = PP_ModelADSConfig(PP_MODEL_ADS_M60);
    pp_model_ads_config_t pump = PP_ModelADSConfig(PP_MODEL_ADS_SHOTGUN);
    assert(!m60.animated && pump.animated);
    for (int frame = 0; frame < 64; ++frame)
    {
        /* M60 fire/spin frames keep the one cached mesh pose. */
        assert(PP_ModelADSFrame(m60, frame) == 0);
        assert(PP_ModelADSFrame(pump, frame) == (frame < 40 ? frame : 0));
    }
    assert(fabsf(m60.muzzle_right + m60.right) < .001f);
    assert(m60.muzzle_forward + m60.forward > 9.5f);
    assert(m60.muzzle_up + m60.up < 0.f);

    pp_model_ads_state_t slots[4] = {{0}};
    for (int frame = 0; frame < 30; ++frame)
        for (int slot = 0; slot < 4; ++slot)
            PP_ModelADSUpdate(&slots[slot], 1, slot % 2, 40 + slot, 1, frame * .01f, .01f);
    for (int slot = 0; slot < 4; ++slot)
        assert(PP_ModelADSAmount(&slots[slot]) == (slot % 2 ? 1.f : 0.f));
    for (int frame = 0; frame < 30; ++frame)
        PP_ModelADSUpdate(&slots[1], 1, 0, 41, 1, .3f + frame * .01f, .01f);
    assert(PP_ModelADSAmount(&slots[1]) == 0.f);
    assert(PP_ModelADSAmount(&slots[3]) == 1.f);
    assert(PP_ModelADSUpdate(&slots[3], 1, 1, 99, 1, .7f, 0.f) == 0.f);
    assert(PP_ModelADSUpdate(&slots[3], 1, 1, 99, 2, .8f, 0.f) == 0.f);
    puts("M60 model ADS/muzzle alignment, rigid fire frames and independent aiming passed");
    return 0;
}
