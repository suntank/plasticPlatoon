#include "../../src/client/header/weapon_model_ads.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
int main(void)
{
    pp_model_ads_config_t pistol=PP_ModelADSConfig(1), rifle=PP_ModelADSConfig(0);
    /* Both sight pairs lie on the forward center ray after the translation. */
    const float rear[]={24.98339371f,-8.8f,-1.39667874f};
    const float front[]={43.01227845f,-8.8f,-1.39667874f};
    assert(fabsf(rear[0]+pistol.forward-9.5f)<.001f);
    assert(front[0]>rear[0]);
    assert(fabsf(-rear[1]+pistol.right)<.001f);
    assert(fabsf(rear[2]+pistol.up)<.001f);
    assert(fabsf(front[2]+pistol.up)<.001f);
    assert(fabsf(pistol.muzzle_right+pistol.right)<.001f);
    assert(fabsf(pistol.up-rifle.up)>1);
    pp_model_ads_state_t slots[4]={{0}};
    for(int frame=0;frame<30;++frame)
        for(int slot=0;slot<4;++slot)
            PP_ModelADSUpdate(&slots[slot],1,slot%2,10+slot,1,frame*.01f,.01f);
    for(int slot=0;slot<4;++slot)assert(PP_ModelADSAmount(&slots[slot])==(slot%2?1.f:0.f));
    /* Switching from pistol to rifle while aiming starts a fresh transition. */
    assert(PP_ModelADSUpdate(&slots[1],1,1,99,1,.31f,0)==0);
    puts("Pistol/M16 sight offsets, shared transitions, switching and slot isolation passed");
    return 0;
}
