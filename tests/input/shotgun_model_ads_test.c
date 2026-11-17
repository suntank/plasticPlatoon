#include "../../src/client/header/weapon_model_ads.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>

int main(void)
{
    pp_model_ads_config_t shotgun = PP_ModelADSConfig(PP_MODEL_ADS_SHOTGUN);
    pp_model_ads_config_t pistol = PP_ModelADSConfig(PP_MODEL_ADS_PISTOL);
    pp_model_ads_config_t rifle = PP_ModelADSConfig(PP_MODEL_ADS_RIFLE);
    assert(shotgun.animated);
    assert(!pistol.animated && !rifle.animated);
    for (int frame = 0; frame < 40; ++frame)
    {
        /* Aiming must preserve every cocking frame, including idle/raise. */
        assert(PP_ModelADSFrame(shotgun, frame) == frame);
        assert(PP_ModelADSFrame(pistol, frame) == 0);
        assert(PP_ModelADSFrame(rifle, frame) == 0);
    }
    assert(PP_ModelADSFrame(shotgun, -1) == 0);
    assert(PP_ModelADSFrame(shotgun, 40) == 0);
    /* Muzzle remains on the centered sight plane at full aim, ahead of
     * the rear sight at 9.5 units. The barrel sits below the sight line. */
    assert(fabsf(shotgun.muzzle_right + shotgun.right) < .001f);
    assert(shotgun.muzzle_forward + shotgun.forward > 9.5f);
    assert(shotgun.muzzle_up + shotgun.up < 0.f);
    assert(fabsf(shotgun.up - pistol.up) > .1f);

    pp_model_ads_state_t slots[4] = {{0}};
    for (int frame = 0; frame < 30; ++frame)
        for (int slot = 0; slot < 4; ++slot)
            PP_ModelADSUpdate(&slots[slot], 1, slot % 2, 20 + slot, 1, frame * .01f, .01f);
    for (int slot = 0; slot < 4; ++slot)
        assert(PP_ModelADSAmount(&slots[slot]) == (slot % 2 ? 1.f : 0.f));
    for (int frame = 0; frame < 30; ++frame)
        PP_ModelADSUpdate(&slots[1], 1, 0, 21, 1, .3f + frame * .01f, .01f);
    assert(PP_ModelADSAmount(&slots[1]) == 0.f);
    assert(PP_ModelADSAmount(&slots[3]) == 1.f);
    /* A weapon switch and reconnect each begin a fresh transition. */
    assert(PP_ModelADSUpdate(&slots[3], 1, 1, 99, 1, .7f, 0.f) == 0.f);
    assert(PP_ModelADSUpdate(&slots[3], 1, 1, 99, 2, .8f, 0.f) == 0.f);
    puts("Shotgun pump frames, model ADS/muzzle alignment and independent aiming passed");
    return 0;
}
