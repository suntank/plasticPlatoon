/* Opt-in QA access to friendly dropship state and its existing use callback. */
#include "../../src/game/header/local.h"
#include <stdio.h>
#include <string.h>

static void json_string(const char *text)
{
    fputc('"',stderr);
    for(const unsigned char *p=(const unsigned char *)(text?text:"");*p;++p) {
        if(*p=='"'||*p=='\\'){fputc('\\',stderr);fputc(*p,stderr);}
        else if(*p<32)fprintf(stderr,"\\u%04x",*p);
        else fputc(*p,stderr);
    }
    fputc('"',stderr);
}
static void json_vector(const float *v) { fprintf(stderr,"[%.6f,%.6f,%.6f]",v[0],v[1],v[2]); }
static int friendly_ship(edict_t *e)
{ return e->inuse&&e->classname&&!strcmp(e->classname,"misc_platoon_dropship"); }

int PP_ColorGameDropshipState(void *raw_edicts,int stride,int count,const char *label)
{
    int found=0;
    if(!raw_edicts||stride<(int)sizeof(edict_t)||count<0||!label)return -1;
    fputs("PP_DROPSHIP_STATE {\"label\":",stderr);json_string(label);fputs(",\"dropships\":[",stderr);
    for(int i=0;i<count;++i) {
        edict_t *e=(edict_t *)((byte *)raw_edicts+(size_t)stride*i);
        if(!friendly_ship(e))continue;
        if(found++)fputc(',',stderr);
        fprintf(stderr,"{\"number\":%d,\"targetname\":",i);json_string(e->targetname);
        fputs(",\"origin\":",stderr);json_vector(e->s.origin);
        fputs(",\"angles\":",stderr);json_vector(e->s.angles);
        fprintf(stderr,",\"count\":%d,\"speed\":%.6f,\"svflags\":%d,\"renderfx\":%d,\"solid\":%d,\"modelindex\":%d,\"modelindex2\":%d,\"nextthink\":%.6f,\"timestamp\":%.6f,\"target\":",
            e->count,e->speed,e->svflags,e->s.renderfx,e->solid,e->s.modelindex,e->s.modelindex2,e->nextthink,e->timestamp);
        json_string(e->target);fputs(",\"deathtarget\":",stderr);json_string(e->deathtarget);
        fputs(",\"movetarget\":",stderr);json_string(e->movetarget&&e->movetarget->inuse?e->movetarget->targetname:NULL);
        fputc('}',stderr);
    }
    fputs("]}\n",stderr);fflush(stderr);return found;
}

int PP_ColorGameDropshipUse(void *raw_edicts,int stride,int count,void *raw_activator,const char *targetname)
{
    int invoked=0;
    if(!raw_edicts||stride<(int)sizeof(edict_t)||count<0||!targetname||!*targetname)return -1;
    for(int i=0;i<count;++i) {
        edict_t *e=(edict_t *)((byte *)raw_edicts+(size_t)stride*i);
        if(friendly_ship(e)&&e->targetname&&!strcmp(e->targetname,targetname)&&e->use) {
            e->use(e,NULL,raw_activator);++invoked;
        }
    }
    return invoked;
}
