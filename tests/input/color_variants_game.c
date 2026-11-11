/* Private game-layout half of the opt-in LD_PRELOAD visual QA controller.
 * Keep it separate: the engine deliberately sees abbreviated game structs. */
#include "../../src/game/header/local.h"
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

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

int PP_ColorGameGib(void *raw_edicts, int stride, int count, void *raw_attacker, const char *classname)
{
	edict_t *attacker = raw_attacker;
	edict_t *nearest = NULL;
	vec3_t point = {0, 0, 0};
	float nearest_distance = 1e30f;
	int nearest_index = -1;
	int i;
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
