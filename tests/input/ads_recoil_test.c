/* ADS recoil must stay on the bore axis; hip fire and the M16 are exclusions. */
#include "../../src/client/header/weapon_model_ads.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static float dot(const float *a,const float *b)
{ return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]; }

int main(void)
{
    const float axes[][3][3]={{{1,0,0},{0,-1,0},{0,0,1}},
        {{0,1,0},{1,0,0},{0,0,1}},{{0,0,1},{0,-1,0},{-1,0,0}},
        {{.6f,.8f,0},{.8f,-.6f,0},{0,0,1}}};
    const float base[3]={140,-250,72},angles[3]={350,5,-179};
    const float hip[]={3.2f,5,7,9,3,8,6,7,1.2f,12,2.6f,5.8f};
    for(int weapon=PP_MODEL_ADS_RIFLE;weapon<=PP_MODEL_ADS_THUNDERHEAD;weapon++) {
        pp_model_ads_config_t cfg=PP_ModelADSConfig(weapon);
        assert(weapon==PP_MODEL_ADS_RIFLE ? cfg.recoil_back==0 : cfg.recoil_back>0 && cfg.recoil_back<=.7f);
        for(int view=0;view<4;view++)for(int recoil=0;recoil<3;recoil++) {
            const float *f=axes[view][0],*r=axes[view][1],*u=axes[view][2];
            float origin[3],rotation[3],original[3],old_rotation[3];
            for(int i=0;i<3;i++) {
                origin[i]=base[i]-hip[weapon]*recoil*f[i]+.3f*r[i]+recoil*u[i];
                rotation[i]=angles[i]+(i==0?-12.f:2.f)*recoil;
            }
            memcpy(original,origin,sizeof(origin));memcpy(old_rotation,rotation,sizeof(rotation));
            PP_ModelADSConstrainMotion(cfg,0,hip[weapon],f,r,u,base,angles,origin,rotation);
            assert(!memcmp(origin,original,sizeof(origin))&&!memcmp(rotation,old_rotation,sizeof(rotation)));
            PP_ModelADSConstrainMotion(cfg,1,hip[weapon],f,r,u,base,angles,origin,rotation);
            if(weapon==PP_MODEL_ADS_RIFLE) {
                assert(!memcmp(origin,original,sizeof(origin))&&!memcmp(rotation,old_rotation,sizeof(rotation)));
                continue;
            }
            float delta[3];for(int i=0;i<3;i++)delta[i]=origin[i]-base[i];
            assert(dot(delta,f)>=-cfg.recoil_back-.0001f && dot(delta,f)<=.0001f);
            assert(fabsf(dot(delta,r))<.0001f && fabsf(dot(delta,u))<.0001f);
            for(int i=0;i<3;i++)assert(rotation[i]==angles[i]);
            /* Entering/exiting ADS must stay finite through arbitrary smoothing tails. */
            for(int step=1;step<=100;step++) {
                memcpy(origin,original,sizeof(origin));memcpy(rotation,old_rotation,sizeof(rotation));
                PP_ModelADSConstrainMotion(cfg,step/100.f,hip[weapon],f,r,u,base,angles,origin,rotation);
                for(int i=0;i<3;i++)assert(isfinite(origin[i])&&isfinite(rotation[i]));
            }
            memcpy(origin,original,sizeof(origin));memcpy(rotation,old_rotation,sizeof(rotation));
            PP_ModelADSConstrainMotion(cfg,.000001f,hip[weapon],f,r,u,base,angles,origin,rotation);
            for(int i=0;i<3;i++)assert(fabsf(origin[i]-original[i])<.001f);
        }
    }
    puts("ADS recoil: eleven bounded straight-back weapons, camera bases, smoothing tails, hip fire and M16 exclusions passed");
    return 0;
}
