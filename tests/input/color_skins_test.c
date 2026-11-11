/* Exercise the actual client-info loader and per-entity material resolver. */
#include "../../src/client/cl_color_skins.c"
#include "../../src/client/cl_parse.c"
#include "../../src/client/cl_splitscreen.c"
#include <assert.h>

client_state_t cl;
static cvar_t no_skins, visible_weapons = {.value = 1};
cvar_t *cl_noskins = &no_skins, *cl_vwep = &visible_weapons;
char cl_weaponmodels[MAX_CLIENTWEAPONMODELS][MAX_QPATH] = {"weapon.md2", "w_machinegun.md2"};
int num_cl_weaponmodels = 2;

typedef struct { char path[MAX_QPATH]; int generation; } test_image_t;
static test_image_t images[4096];
static int image_count, generation, registrations;
static qboolean new_variant_exists, alternate_skin_exists;
static qboolean missing_pink_body_variant;
static int message_index;
static char *message_value;
int MSG_ReadShort(sizebuf_t *buf) { return message_index; }
char *MSG_ReadString(sizebuf_t *buf) { return message_value; }

int FS_LoadFile(const char *name, void **buffer)
{
	assert(!buffer);
	if (missing_pink_body_variant && !strcmp(name, "players/soldier/colors/body_pink.png")) return -1;
	if (strstr(name, "_teal.png") && !new_variant_exists) return -1;
	if (strstr(name, "_red_1.png") && !alternate_skin_exists) return -1;
	if (strstr(name, "_red_4.png")) return -1;
	return 10;
}

static struct image_s *image(const char *path)
{
	test_image_t *entry;
	assert(strlen(path) < MAX_QPATH && image_count < (int)ARRLEN(images));
	entry = &images[image_count++];
	Q_strlcpy(entry->path, path, sizeof(entry->path));
	entry->generation = generation;
	return (struct image_s *)entry;
}

struct image_s *R_RegisterSkin(const char *path)
{
	++registrations;
	if (strstr(path, "missingbody")) return NULL;
	if (strstr(path, "_teal.png") && !new_variant_exists) return NULL;
	if (strstr(path, "_red_1.png") && !alternate_skin_exists) return NULL;
	if (strstr(path, "_red_4.png")) return NULL;
	return image(path);
}

struct image_s *Draw_FindPic(const char *path)
{
	++registrations;
	if (strstr(path, "_teal.png") && !new_variant_exists) return NULL;
	return image(path);
}

struct model_s *R_RegisterModel(const char *path)
{
	if (strstr(path, "players/foreignfallback/") &&
		(strstr(path, "/weapon.md2") || strstr(path, "/w_machinegun.md2"))) return NULL;
	return (struct model_s *)(uintptr_t)(strstr(path, "missingmodel") ? 0 : 1);
}

void Com_Printf(const char *format, ...) {}

static const char *path(struct image_s *img)
{
	assert(img);
	return ((test_image_t *)img)->path;
}

static void player(const char *name, const char *color, clientinfo_t *ci)
{
	char info[128];
	Com_sprintf(info, sizeof(info), "%s\\soldier/%s", name, color);
	CL_LoadClientinfo(ci, info);
	assert(ci->skin && ci->model && ci->weaponmodel[0]);
}

int main(void)
{
	clientinfo_t a = {0}, b = {0};
	struct image_s *red, *blue, *old;
	const char *red_pic, *blue_pic;
	int before;
	player("A", "red", &a);
	player("B", "blue", &b);
	assert(!strcmp(path(a.skin), "players/soldier/colors/body_red.png"));
	assert(!strcmp(path(b.skin), "players/soldier/colors/body_blue.png") && a.skin != b.skin);
	red = CL_PlayerWeaponSkin(&a, "models/weapons/v_machn/tris.md2");
	blue = CL_PlayerWeaponSkin(&b, "models/weapons/v_machn/tris.md2");
	assert(!strcmp(path(red), "models/weapons/v_machn/colors/tris_red.png"));
	assert(!strcmp(path(blue), "models/weapons/v_machn/colors/tris_blue.png") && red != blue);
	assert(!strcmp(path(CL_PlayerWeaponSkin(&a, "players/soldier/w_machinegun.md2")),
		"players/soldier/colors/w_machinegun_red.png"));
	red_pic = CL_PlayerADSPic(&a, "ads_machinegun.png");
	blue_pic = CL_PlayerADSPic(&b, "ads_machinegun.png");
	assert(!strcmp(red_pic, "colors/ads_machinegun_red.png"));
	assert(!strcmp(blue_pic, "colors/ads_machinegun_blue.png"));
	assert(strcmp(red_pic, blue_pic));
	assert(a.weapon_soldier_mask == 3 && b.weapon_soldier_mask == 3);
	assert(!strcmp(path(CL_PlayerLinkedWeaponSkin(&a, &a, 1)),
		"players/soldier/colors/w_machinegun_red.png"));
	/* Optional custom weapon models keep their own texture/UV layout. A
	 * missing custom weapon uses project geometry with the owning color. */
	{
		clientinfo_t custom = {0}, fallback = {0};
		CL_LoadClientinfo(&custom, "Custom\\foreign/red");
		assert(!strcmp(path(custom.skin), "players/foreign/red.pcx"));
		assert(custom.weaponmodel[0] && custom.weaponmodel[1] && !custom.weapon_soldier_mask);
		assert(!CL_PlayerLinkedWeaponSkin(&custom, &custom, 0));
		assert(!CL_PlayerLinkedWeaponSkin(&custom, &custom, 1));
		assert(strstr(path(CL_PlayerWeaponSkin(&custom, "models/weapons/v_machn/tris.md2")), "_red.png"));
		CL_LoadClientinfo(&fallback, "Fallback\\foreignfallback/blue");
		assert(!strcmp(path(fallback.skin), "players/foreignfallback/blue.pcx"));
		assert(fallback.weapon_soldier_mask == 3);
		assert(!strcmp(path(CL_PlayerLinkedWeaponSkin(&fallback, &fallback, 1)),
			"players/soldier/colors/w_machinegun_blue.png"));
		assert(!strcmp(path(CL_PlayerLinkedWeaponSkin(&custom, &b, 0)),
			"players/soldier/colors/weapon_red.png")); /* geometry fallback retains owner color */
		player("Custom", "pink", &custom);
		assert(custom.weapon_soldier_mask == 3 && CL_PlayerLinkedWeaponSkin(&custom, &custom, 1));
		CL_LoadClientinfo(&custom, "Custom\\foreign/red");
		assert(!custom.weapon_soldier_mask && !CL_PlayerLinkedWeaponSkin(&custom, &custom, 1));
	}
	for (int i = 0; i < color_image_count; i++)
		if (color_images[i].pic) assert(!color_images[i].image); /* evictable picture pointers never escape */

	/* Reloading one skin changes both of its weapon views, not another client. */
	player("A", "pink", &a);
	assert(!strcmp(path(a.skin), "players/soldier/colors/body_pink.png"));
	assert(strstr(path(CL_PlayerWeaponSkin(&a, "models/weapons/v_machn/tris.md2")), "_pink.png"));
	assert(strstr(path(CL_PlayerWeaponSkin(&a, "players/soldier/w_machinegun.md2")), "_pink.png"));
	assert(CL_PlayerWeaponSkin(&b, "models/weapons/v_machn/tris.md2") == blue);
	assert(!strcmp(CL_PlayerADSPic(&b, "ads_machinegun.png"), blue_pic));
	player("A", "missingbody", &a);
	assert(!strcmp(a.weaponcolor, "green"));
	assert(!strcmp(path(a.skin), "players/soldier/colors/body_green.png"));
	player("A", "teal", &a);
	assert(!strcmp(path(a.skin), "players/soldier/teal.pcx")); /* missing generated color keeps canonical body */
	assert(strstr(path(CL_PlayerWeaponSkin(&a, "models/weapons/v_machn/tris.md2")), "_green.png"));
	assert(!strcmp(CL_PlayerADSPic(&a, "ads_machinegun.png"), "colors/ads_machinegun_green.png"));
	CL_SetClientWeaponColor(&a, "../red");
	assert(!strcmp(a.weaponcolor, "green"));
	CL_SetClientWeaponColor(&a, "white");
	assert(strstr(path(CL_PlayerWeaponSkin(&a, "models/weapons/v_machn/tris.md2")), "_white.png"));
	CL_SetClientWeaponColor(&a, "skin");
	assert(strstr(path(CL_PlayerWeaponSkin(&a, "models/weapons/v_machn/tris.md2")), "_skin.png"));
	CL_SetClientWeaponColor(&a, "this_skin_name_is_too_long_for_a_weapon_variant_path");
	assert(strstr(path(CL_PlayerWeaponSkin(&a, "models/weapons/v_machn/tris.md2")), "_green.png"));
	assert(!strcmp(CL_PlayerADSPic(&a, "ads_machinegun.png"), "colors/ads_machinegun_green.png"));

	assert(!strcmp(path(CL_EnemyModelSkin("models/monsters/soldier/weapon_machinegun.md2", 0, 0)),
		"models/monsters/soldier/colors/weapon_machinegun_red.png"));
	assert(!strcmp(path(CL_EnemyModelSkin("models/monsters/soldier/tall/tris.md2", 4, RF_PP_ENEMY_COLOR)),
		"models/monsters/soldier/colors/tris_red.png"));
	alternate_skin_exists = true;
	assert(strstr(path(CL_EnemyModelSkin("models/monsters/boss2/tris.md2", 1, 0)), "tris_red_1.png"));
	before = registrations;
	assert(!CL_EnemyModelSkin("models/monsters/boss2/tris.md2", 0, RF_PP_FRIENDLY_COLOR));
	assert(!CL_EnemyModelSkin("models/weapons/g_machn/tris.md2", 0, RF_PP_ENEMY_COLOR));
	assert(!CL_PlayerWeaponSkin(&a, "models/weapons/g_machn/tris.md2"));
	assert(!CL_EnemyModelSkin("models/objects/gibs/head2/tris.md2", PP_GIB_PLAYER_SKIN_OVERRIDE, RF_PP_ENEMY_COLOR));
	assert(!CL_EnemyModelSkin("models/objects/debris1/tris.md2", 0, 0));
	assert(registrations == before);
	assert(CL_EnemyModelSkin("models/objects/gibs/ant/chunk.md2", 0, RF_PP_ENEMY_COLOR));
	assert(CL_EnemyModelSkin("models/objects/debris1/tris.md2", 0, RF_PP_ENEMY_COLOR));

	/* A secondary receives a reliable skin broadcast before the primary.
	 * It updates the shared configstring, which would otherwise suppress the
	 * primary parser's changed-string check. Load the actual owning clientinfo
	 * immediately; duplicate packets must not reload it or affect player 2. */
	cl.refresh_prepped = true;
	player("P1", "red", &cl.clientinfo[0]);
	player("P2", "blue", &cl.clientinfo[1]);
	message_index = CS_PLAYERSKINS;
	message_value = "P1\\soldier/pink";
	SS_ParseConfigString(NULL);
	assert(!strcmp(cl.configstrings[CS_PLAYERSKINS], message_value));
	assert(!strcmp(cl.clientinfo[0].weaponcolor, "pink"));
	assert(!strcmp(cl.clientinfo[1].weaponcolor, "blue"));
	assert(!strcmp(path(cl.clientinfo[0].skin), "players/soldier/colors/body_pink.png"));
	assert(!strcmp(path(cl.clientinfo[1].skin), "players/soldier/colors/body_blue.png"));
	before = registrations;
	SS_ParseConfigString(NULL);
	assert(registrations == before);
	message_index = CS_PLAYERSKINS + 1;
	message_value = "P2\\soldier/white";
	SS_ParseConfigString(NULL);
	assert(!strcmp(cl.clientinfo[0].weaponcolor, "pink"));
	assert(!strcmp(cl.clientinfo[1].weaponcolor, "white"));
	assert(!strcmp(path(cl.clientinfo[1].skin), "players/soldier/colors/body_white.png"));
	/* A primary-first load is also untouched by duplicate secondary packets. */
	Q_strlcpy(cl.configstrings[CS_PLAYERSKINS], "P1\\soldier/orange", MAX_QPATH);
	CL_ParseClientinfo(0);
	message_index = CS_PLAYERSKINS;
	message_value = "P1\\soldier/orange";
	before = registrations;
	SS_ParseConfigString(NULL);
	assert(registrations == before);
	assert(!strcmp(path(cl.clientinfo[0].skin), "players/soldier/colors/body_orange.png"));

	CL_ClearColorSkins();
	missing_pink_body_variant = true;
	player("A", "pink", &a);
	assert(!strcmp(a.weaponcolor, "pink") && !strcmp(path(a.skin), "players/soldier/pink.pcx"));
	assert(strstr(path(CL_PlayerWeaponSkin(&a, "models/weapons/v_machn/tris.md2")), "_pink.png"));
	missing_pink_body_variant = false;
	no_skins.value = 1;
	CL_LoadClientinfo(&a, "A\\foreign/red");
	assert(!strcmp(a.weaponcolor, "green") && !strcmp(path(a.skin), "players/soldier/colors/body_green.png"));
	no_skins.value = 0;

	/* A registration generation never retains renderer pointers or failed
	 * variant lookups from before a renderer/map refresh. */
	old = CL_PlayerWeaponSkin(&b, "models/weapons/v_machn/tris.md2");
	CL_ClearColorSkins();
	++generation;
	new_variant_exists = true;
	assert(CL_PlayerWeaponSkin(&b, "models/weapons/v_machn/tris.md2") != old);
	player("A", "teal", &a);
	assert(!strcmp(path(a.skin), "players/soldier/colors/body_teal.png"));
	assert(strstr(path(CL_PlayerWeaponSkin(&a, "models/weapons/v_machn/tris.md2")), "_teal.png"));
	{
		const char *colors[] = {"blue", "gray", "green", "orange", "pink", "purple", "red", "skin", "tan", "white"};
		char expected[MAX_QPATH];
		for (size_t i = 0; i < ARRLEN(colors); ++i)
		{
			player("A", colors[i], &a);
			Com_sprintf(expected, sizeof(expected), "players/soldier/colors/body_%s.png", colors[i]);
			assert(!strcmp(path(a.skin), expected));
			assert(a.model && a.model_pistol && !strcmp(a.weaponcolor, colors[i]));
		}
	}
	puts("Per-player FP/TP/ADS colors, enemy ownership, pickups, fallback, refresh and isolation passed");
	return 0;
}
