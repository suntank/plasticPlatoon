/* Per-entity Plastic Platoon materials. Models and their shared default skins
 * remain immutable: pickups, players and enemies can share model resources. */
#include "header/client.h"

#define COLOR_IMAGE_CACHE 1024

typedef struct
{
	char path[MAX_QPATH];
	struct image_s *image;
	qboolean pic;
	qboolean available;
} color_image_t;

static color_image_t color_images[COLOR_IMAGE_CACHE];
static int color_image_count;

void
CL_ClearColorSkins(void)
{
	/* Renderer registration changes invalidate image pointers, including
	 * negative lookups from a previous asset generation. */
	memset(color_images, 0, sizeof(color_images));
	color_image_count = 0;
}

static color_image_t *
CL_ColorImage(const char *path, qboolean pic)
{
	color_image_t *entry;
	int i;
	for (i = 0; i < color_image_count; i++)
	{
		entry = &color_images[i];
		if (entry->pic == pic && !strcmp(entry->path, path)) return entry;
	}
	if (color_image_count == COLOR_IMAGE_CACHE) return NULL;
	entry = &color_images[color_image_count++];
	Q_strlcpy(entry->path, path, sizeof(entry->path));
	entry->pic = pic;
	/* Variant fallbacks are expected, not missing-model warnings. */
	{
		char file[MAX_QPATH];
		if (pic) Com_sprintf(file, sizeof(file), "pics/%s", path);
		else Q_strlcpy(file, path, sizeof(file));
		if (FS_LoadFile(file, NULL) <= 0) return entry;
	}
	if (pic)
	{
		/* Colored ADS pictures have a bounded renderer LRU. Keep only their
		 * path/presence here, never an image pointer the renderer may evict. */
		entry->available = Draw_FindPic(path) != NULL;
	}
	else
	{
		entry->image = R_RegisterSkin(path);
		entry->available = entry->image != NULL;
	}
	return entry;
}

void
CL_SetClientWeaponColor(clientinfo_t *ci, const char *skin_name)
{
	size_t i, length;
	if (!ci) return;
	Q_strlcpy(ci->weaponcolor, "green", sizeof(ci->weaponcolor));
	if (!skin_name || !(length = strlen(skin_name)) || length >= sizeof(ci->weaponcolor)) return;
	for (i = 0; i < length; i++)
	{
		unsigned char c = (unsigned char)skin_name[i];
		if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
			(c >= '0' && c <= '9') || c == '_' || c == '-')) return;
	}
	for (i = 0; i < length; i++)
	{
		char c = skin_name[i];
		ci->weaponcolor[i] = c >= 'A' && c <= 'Z' ? c + ('a' - 'A') : c;
	}
	ci->weaponcolor[length] = 0;
}

const clientinfo_t *
CL_ColorClientinfo(int playernum)
{
	return playernum >= 0 && playernum < MAX_CLIENTS ?
		&cl.clientinfo[playernum] : &cl.baseclientinfo;
}

static qboolean
CL_ColorModelPath(const char *model_path, const char *color, int skin,
	char *out, size_t size)
{
	char canonical[MAX_QPATH], stem[MAX_QPATH];
	const char *slash, *dot;
	size_t directory, length;
	if (!model_path || strlen(model_path) >= sizeof(canonical)) return false;
	/* Taller soldier models retain the original material and UV layout. */
	if (!strncmp(model_path, "models/monsters/soldier/tall/", 29))
	{
		Com_sprintf(canonical, sizeof(canonical), "models/monsters/soldier/%s", model_path + 29);
	}
	else Q_strlcpy(canonical, model_path, sizeof(canonical));
	slash = strrchr(canonical, '/');
	dot = strrchr(canonical, '.');
	if (!slash || !dot || dot <= slash || Q_stricmp(dot, ".md2")) return false;
	directory = (size_t)(slash - canonical);
	length = (size_t)(dot - slash - 1);
	if (length >= sizeof(stem)) return false;
	memcpy(stem, slash + 1, length);
	stem[length] = 0;
	if (skin > 0)
	{
		if (directory + strlen(stem) + strlen(color) + 20 >= size) return false;
		Com_sprintf(out, (int)size, "%.*s/colors/%s_%s_%d.png", (int)directory, canonical, stem, color, skin);
	}
	else
	{
		if (directory + strlen(stem) + strlen(color) + 14 >= size) return false;
		Com_sprintf(out, (int)size, "%.*s/colors/%s_%s.png", (int)directory, canonical, stem, color);
	}
	return true;
}

struct image_s *
CL_PlayerWeaponSkin(const clientinfo_t *ci, const char *model_path)
{
	char path[MAX_QPATH];
	color_image_t *entry;
	const char *color = ci && ci->weaponcolor[0] ? ci->weaponcolor : "green";
	if (!model_path ||
		(strncmp(model_path, "models/weapons/v_", 17) &&
		 strncmp(model_path, "players/soldier/", 16))) return NULL;
	if (strstr(model_path, "/tris_pistol.md2") ||
		!strcmp(model_path, "players/soldier/tris.md2")) return NULL;
	if (CL_ColorModelPath(model_path, color, 0, path, sizeof(path)))
	{
		entry = CL_ColorImage(path, false);
		if (entry && entry->image) return entry->image;
	}
	if (strcmp(color, "green") && CL_ColorModelPath(model_path, "green", 0, path, sizeof(path)))
	{
		entry = CL_ColorImage(path, false);
		if (entry) return entry->image;
	}
	return NULL;
}

struct image_s *
CL_PlayerBodySkin(const char *model_name, const clientinfo_t *ci)
{
	char path[MAX_QPATH];
	color_image_t *entry;
	const char *color = ci && ci->weaponcolor[0] ? ci->weaponcolor : "green";
	/* The standing and pistol bodies share the same atlas. Optional player
	 * geometry must retain its own texture layout. Missing generated variants
	 * keep the already-loaded canonical selected skin. */
	if (!model_name || Q_stricmp(model_name, "soldier") || strlen(color) + 33 > sizeof(path)) return NULL;
	Com_sprintf(path, sizeof(path), "players/soldier/colors/body_%s.png", color);
	entry = CL_ColorImage(path, false);
	return entry ? entry->image : NULL;
}

struct image_s *
CL_PlayerLinkedWeaponSkin(const clientinfo_t *owner, const clientinfo_t *source, int weapon)
{
	char path[MAX_QPATH];
	if (!source || weapon < 0 || weapon >= MAX_CLIENTWEAPONMODELS ||
		!(source->weapon_soldier_mask & (1U << weapon))) return NULL;
	Com_sprintf(path, sizeof(path), "players/soldier/%s",
		weapon < num_cl_weaponmodels ? cl_weaponmodels[weapon] : "weapon.md2");
	return CL_PlayerWeaponSkin(owner, path);
}

struct image_s *
CL_EnemyModelSkin(const char *model_path, int skinnum, int renderfx)
{
	char path[MAX_QPATH];
	color_image_t *entry;
	if (!model_path || (renderfx & RF_PP_FRIENDLY_COLOR) ||
		(skinnum & PP_GIB_PLAYER_SKIN_OVERRIDE)) return NULL;
	if (strncmp(model_path, "models/monsters/", 16) &&
		strncmp(model_path, "models/objects/gibs/", 20) &&
		(!(renderfx & RF_PP_ENEMY_COLOR) || strncmp(model_path, "models/objects/debris", 21))) return NULL;
	/* Most modelindex owners use skinnum as metadata (rotors), not a skin.
	 * Preserve actual alternates only where a matching variant exists. */
	if (skinnum > 0 && skinnum < 8 && CL_ColorModelPath(model_path, "red", skinnum, path, sizeof(path)))
	{
		entry = CL_ColorImage(path, false);
		if (entry && entry->image) return entry->image;
	}
	if (!CL_ColorModelPath(model_path, "red", 0, path, sizeof(path))) return NULL;
	entry = CL_ColorImage(path, false);
	return entry ? entry->image : NULL;
}

const char *
CL_PlayerADSPic(const clientinfo_t *ci, const char *base_pic)
{
	char path[MAX_QPATH];
	color_image_t *entry;
	const char *color = ci && ci->weaponcolor[0] ? ci->weaponcolor : "green";
	size_t length;
	if (!base_pic || strncmp(base_pic, "ads_", 4)) return base_pic;
	length = strlen(base_pic);
	if (length < 5 || strcmp(base_pic + length - 4, ".png")) return base_pic;
	if (length + strlen(color) + 14 >= sizeof(path)) color = "green";
	if (length + strlen(color) + 14 >= sizeof(path)) return base_pic;
	Com_sprintf(path, sizeof(path), "colors/%.*s_%s.png", (int)length - 4, base_pic, color);
	entry = CL_ColorImage(path, true);
	if (entry && entry->available) return entry->path;
	Com_sprintf(path, sizeof(path), "colors/%.*s_green.png", (int)length - 4, base_pic);
	entry = CL_ColorImage(path, true);
	return entry && entry->available ? entry->path : base_pic;
}
