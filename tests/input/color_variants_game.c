/* Private game-layout half of the opt-in LD_PRELOAD visual QA controller.
 * Keep it separate: the engine deliberately sees abbreviated game structs. */
#include "../../src/game/header/local.h"
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef PP_SOLDIER_QA
/* Photography only: freeze an observed native actor at an original pose. */
int PP_SoldierBodyPose(void *raw,int stride,int count,uintptr_t base,const char *kind,int frame);
#endif

static void *game_symbol(uintptr_t base, const char *name)
{
	char environment[128], *end;
	const char *value;
	unsigned long long offset;
	snprintf(environment, sizeof(environment), "PP_COLOR_GAME_%s", name);
	value = getenv(environment);
	if (!value || !*value) {
		fprintf(stderr, "PP_COLOR_ERROR missing %s\n", environment);
		return NULL;
	}
	offset = strtoull(value, &end, 16);
	return offset && !*end ? (void *)(base + offset) : NULL;
}

int PP_ColorGameEquip(void *raw_entity, uintptr_t game_base, const char *name)
{
	edict_t *entity = raw_entity;
	gitem_t *(*find_item)(const char *) = game_symbol(game_base, "FindItem");
	void (*change_weapon)(edict_t *) = game_symbol(game_base, "ChangeWeapon");
	gitem_t *item;
	if (!entity || !entity->client || !find_item || !change_weapon || !(item = find_item(name))) return 0;
	entity->client->newweapon = item;
	change_weapon(entity);
	return 1;
}

int PP_ColorGameAmmoState(void *raw_entity, uintptr_t game_base, int counts[7])
{
	static const char *const names[]={"Shells", "Bullets", "Grenades", "GL Ammo",
		"Rockets", "Napalm", "Sniper Rounds"};
	edict_t *entity=raw_entity;
	gitem_t *(*find_item)(const char *)=game_symbol(game_base,"FindItem");
	gitem_t *items=game_symbol(game_base,"itemlist");
	if (!entity || !entity->client || !find_item || !items || !counts) return 0;
	for (int i=0; i<7; ++i) {
		gitem_t *item=find_item(names[i]);
		ptrdiff_t index=item ? item-items : -1;
		if (index<0 || index>=MAX_ITEMS) return 0;
		counts[i]=entity->client->pers.inventory[index];
	}
	return 1;
}

int PP_ColorGameHealthState(void *raw_entity, int out[2])
{
	edict_t *entity=raw_entity;
	if (!entity || !entity->inuse || !entity->client || !out) return 0;
	out[0]=entity->health;
	out[1]=entity->max_health;
	return 1;
}

int PP_ColorGameArmorState(void *raw_entity, uintptr_t game_base, int counts[3])
{
	static const char *const names[]={"Jacket Armor", "Combat Armor", "Body Armor"};
	edict_t *entity=raw_entity;
	gitem_t *(*find_item)(const char *)=game_symbol(game_base,"FindItem");
	gitem_t *items=game_symbol(game_base,"itemlist");
	if (!entity || !entity->inuse || !entity->client || !find_item || !items || !counts) return 0;
	for (int i=0; i<3; ++i) {
		gitem_t *item=find_item(names[i]);
		ptrdiff_t index=item ? item-items : -1;
		if (index<0 || index>=MAX_ITEMS) return 0;
		counts[i]=entity->client->pers.inventory[index];
	}
	return 1;
}

int PP_ColorGameGib(void *raw_edicts, int stride, int count, void *raw_attacker, const char *classname)
{
	edict_t *attacker = raw_attacker;
	edict_t *nearest = NULL;
	vec3_t point = {0, 0, 0};
	float nearest_distance = 1e30f;
	int nearest_index = -1;
	int i;
#ifdef PP_BODY_PARTS_QA
	/* Private fragment inspection: exercise the unchanged player death path. */
	if (!strcmp(classname, "player") && attacker && attacker->client && attacker->die) {
		attacker->health = -10000;
		attacker->die(attacker, attacker, attacker, 10000, point);
		return attacker->s.number;
	}
#endif
	if (strncmp(classname, "monster_", 8)) return -1;
	for (i = 1; i < count; ++i) {
		edict_t *entity = (edict_t *)((byte *)raw_edicts + stride * i);
		if (!entity->inuse || !entity->classname || strcmp(entity->classname, classname) ||
			entity->health <= 0 || !entity->die || (entity->s.renderfx & RF_PP_FRIENDLY_COLOR)) continue;
		float distance = 0;
		for (int axis = 0; axis < 3; ++axis) {
			float delta = entity->s.origin[axis] - (attacker ? attacker->s.origin[axis] : 0);
			distance += delta * delta;
		}
		if (distance < nearest_distance) {
			nearest = entity;
			nearest_index = i;
			nearest_distance = distance;
		}
	}
	if (!nearest) return -1;
	nearest->health = -10000;
	for (int axis = 0; axis < 3; ++axis) point[axis] = nearest->s.origin[axis];
	nearest->die(nearest, attacker, attacker, 10000, point);
	return nearest_index;
}

#ifdef PP_SOLDIER_QA
int PP_SoldierLegacyCook(void *raw,uintptr_t base)
{
    edict_t *e=raw;level_locals_t *clock=game_symbol(base,"level");
    if(!clock || !e || !e->client || !PP_ColorGameEquip(e,base,"Grenades"))return 0;
    e->client->grenade_time=clock->time+2;
    e->client->weaponstate=WEAPON_FIRING;e->client->ps.gunframe=12;
    e->client->buttons &= ~BUTTON_ATTACK;
    return 1;
}

int PP_SoldierBodyPose(void *raw,int stride,int count,uintptr_t base,const char *kind,int frame)
{
    game_import_t *api=game_symbol(base,"gi");int changed=0;
    for(int i=1;i<count;i++) {
        edict_t *e=(edict_t *)((byte *)raw+stride*i);
        if(!e->inuse)continue;
        if(!strcmp(kind,"player")) {
            if(!e->client)continue;
            e->s.frame=frame;e->client->anim_end=frame;e->client->anim_priority=ANIM_DEATH;changed++;
        } else {
            if(!e->classname||strncmp(e->classname,"monster_soldier",15))continue;
            e->nextthink=0;e->s.frame=frame;VectorClear(e->velocity);
            e->s.modelindex=api->modelindex(!strcmp(kind,"enemy")?"models/monsters/soldier/tris.md2":"models/monsters/soldier/tall/tris.md2");
            e->s.modelindex2=0;changed++;
        }
    }
    return changed;
}
#endif
