/* Read-only projectile probe and camera-only observer mode for visual QA. */
#include "../../src/game/header/local.h"
#include <stdio.h>
#include <string.h>

int PP_ColorGameObserver(void *raw_entity)
{
    edict_t *entity=raw_entity;
    if(!entity||!entity->client)return 0;
    entity->movetype=MOVETYPE_NOCLIP;
    entity->client->ps.pmove.pm_type=PM_SPECTATOR;
    return 1;
}

static void json_label(const char *text)
{
    fputc('"',stderr);
    for(const unsigned char *p=(const unsigned char *)text;*p;++p) {
        if(*p=='"'||*p=='\\') { fputc('\\',stderr);fputc(*p,stderr); }
        else if(*p<32) fprintf(stderr,"\\u%04x",*p);
        else fputc(*p,stderr);
    }
    fputc('"',stderr);
}
static void json_vector(const float *v) { fprintf(stderr,"[%.6f,%.6f,%.6f]",v[0],v[1],v[2]); }

int PP_ColorGameProjectileState(void *raw_edicts,int stride,int count,const char *label)
{
    int found=0;
    if(!raw_edicts||stride<(int)sizeof(edict_t)||count<0||!label)return -1;
    fputs("PP_PROJECTILE_STATE {\"label\":",stderr);json_label(label);fputs(",\"projectiles\":[",stderr);
    for(int i=0;i<count;++i) {
        edict_t *e=(edict_t *)((byte *)raw_edicts+(size_t)stride*i);
        if(!e->inuse||!e->classname||
            (strcmp(e->classname,"rocket")&&strcmp(e->classname,"grenade")&&
             strcmp(e->classname,"hgrenade")&&strcmp(e->classname,"mortar")))continue;
        if(found++)fputc(',',stderr);
        fprintf(stderr,"{\"number\":%d,\"classname\":",i);json_label(e->classname);
        fputs(",\"origin\":",stderr);json_vector(e->s.origin);
        fputs(",\"angles\":",stderr);json_vector(e->s.angles);
        fputs(",\"velocity\":",stderr);json_vector(e->velocity);
        fputs(",\"avelocity\":",stderr);json_vector(e->avelocity);
        fprintf(stderr,",\"movetype\":%d,\"effects\":%u,\"nextthink\":%.6f,\"modelindex\":%d}",
            e->movetype,e->s.effects,e->nextthink,e->s.modelindex);
    }
    fputs("]}\n",stderr);fflush(stderr);return found;
}
