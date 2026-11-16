/* Private native boss observation and controlled scene setup; never shipped. */
#include "../../src/game/header/local.h"
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void *symbol(uintptr_t base,const char *name)
{
    char key[128];snprintf(key,sizeof(key),"PP_COLOR_GAME_%s",name);
    const char *value=getenv(key);return value?(void *)(base+strtoull(value,NULL,16)):NULL;
}

int PP_BossQA(void *raw,int stride,int count,void *player,uintptr_t base,const char *action,const char *label)
{
    edict_t *attacker=player;level_locals_t *clock=symbol(base,"level");int found=0;
    if(!strcmp(action,"state"))fprintf(stderr,"PP_BOSS_STATE {\"label\":\"%s\",\"bosses\":[",label);
    for(int i=1;i<count;i++) {
        edict_t *e=(edict_t *)((byte *)raw+stride*i);
        if(!e->inuse||!e->classname||strcmp(e->classname,"monster_boss2"))continue;
        if(!strcmp(action,"state")) {
            if(found)fputc(',',stderr);
            fprintf(stderr,"{\"number\":%d,\"health\":%d,\"max_health\":%d,\"skin\":%d,\"svflags\":%d,\"flags\":%d,\"solid\":%d,\"dead\":%d,\"rotor\":%d,\"frame\":%d,\"origin\":[%.3f,%.3f,%.3f],\"deathtarget\":\"%s\"}",
                i,e->health,e->max_health,e->s.skinnum,e->svflags,e->s.renderfx,e->solid,e->deadflag,e->s.modelindex2,e->s.frame,
                e->s.origin[0],e->s.origin[1],e->s.origin[2],e->deathtarget?e->deathtarget:"");
        } else if(!strcmp(action,"freeze")) {
            e->nextthink=0;VectorClear(e->velocity);
        } else if(!strcmp(action,"wake")&&e->use) {
            e->use(e,attacker,attacker);
        } else if(!strcmp(action,"phase")) {
            e->health=e->max_health/2-1;e->pain(e,attacker,0,8);e->nextthink=0;
        } else if(!strcmp(action,"fire")&&clock) {
            mmove_t *move=symbol(base,"boss2_move_attack_rocket");
            if(move){e->enemy=attacker;e->monsterinfo.currentmove=move;e->s.frame=move->firstframe-1;e->nextthink=clock->time+FRAMETIME;}
        } else if(!strcmp(action,"kill")) {
            void (*damage)(edict_t *,edict_t *,edict_t *,vec3_t,vec3_t,vec3_t,int,int,int,int)=symbol(base,"T_Damage");
            vec3_t zero={0,0,0};
            if(damage)damage(e,attacker,attacker,zero,e->s.origin,zero,e->health+1000,0,DAMAGE_NO_ARMOR,MOD_ROCKET);
        }
        found++;
    }
    if(!strcmp(action,"state"))fprintf(stderr,"],\"killed_monsters\":%d}\n",clock?clock->killed_monsters:-1);
    fflush(stderr);return found;
}
