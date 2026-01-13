/*
 * Plastic Platoon - Weapon Tuning System Implementation
 *
 * Runtime tunable weapon parameters with JSON profile support.
 */

#include "../header/local.h"
#include "../header/pp_weapon_tuning.h"
#include "../pp_json.h"
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

/* Forward declaration for file reading */
static char *PP_ReadFile(const char *filename, int *len_out);

/* ============================================================================
 * CVARS
 * ============================================================================ */

cvar_t *sv_weapon_profile;
cvar_t *sv_weapon_profile_dir;
cvar_t *sv_pure_weapons;

/* ============================================================================
 * GLOBAL RUNTIME STATE
 * ============================================================================ */

pp_weapon_profile_t g_weapon_profile;

/* ============================================================================
 * AMMO NAME TABLE
 * ============================================================================ */

static const char *ammo_names[AMMO_PP_MAX] = {
	"Light Rounds",
	"Heavy Rounds",
	"Sniper Rounds",
	"Shells",
	"40mm Rounds",
	"Rockets",
	"Grenades",
	"Mines",
	"Satchels",
	"Fuel",
	"Airstrike",
	"Mortar Rounds"
};

/* ============================================================================
 * DEFAULT AMMO CAPS
 * ============================================================================ */

static const int default_ammo_caps[AMMO_PP_MAX] = {
	AMMO_CAP_LIGHT_ROUNDS,       /* AMMO_LIGHT_ROUNDS */
	AMMO_CAP_HEAVY_ROUNDS,       /* AMMO_HEAVY_ROUNDS */
	AMMO_CAP_SNIPER_ROUNDS,      /* AMMO_SNIPER_ROUNDS */
	AMMO_CAP_PP_SHELLS,          /* AMMO_PP_SHELLS */
	AMMO_CAP_GL_ROUNDS_40MM,     /* AMMO_GL_ROUNDS_40MM */
	AMMO_CAP_PP_ROCKETS,         /* AMMO_PP_ROCKETS */
	AMMO_CAP_THROWABLE_GRENADE,  /* AMMO_THROWABLE_GRENADE */
	AMMO_CAP_THROWABLE_MINE,     /* AMMO_THROWABLE_MINE */
	AMMO_CAP_THROWABLE_SATCHEL,  /* AMMO_THROWABLE_SATCHEL */
	AMMO_CAP_FLAME_FUEL,         /* AMMO_FLAME_FUEL */
	AMMO_CAP_AIRSTRIKE_CHARGE,   /* AMMO_AIRSTRIKE_CHARGE */
	AMMO_CAP_MORTAR_ROUNDS       /* AMMO_MORTAR_ROUNDS */
};

/* ============================================================================
 * DEFAULT WEAPON PARAMETERS (COMPILED DEFAULTS FROM SPEC)
 * ============================================================================ */

static const pp_weapon_params_t default_weapons[WEAP_PP_MAX] = {
	/* WEAP_PP_PISTOL - Replaces Blaster */
	{
		.id = WEAP_PP_PISTOL,
		.classname = "weapon_pistol",
		.ui_name = "Pistol",
		.ammo_type = AMMO_LIGHT_ROUNDS,
		.ammo_per_shot = 1,
		.fire_mode_type = FIRE_MODE_HITSCAN,
		.hitscan = {
			.rate_rps = 4.0f,
			.damage = 12,
			.spread_base = 1.0f,
			.bloom_per_shot = 0.1f,
			.bloom_recover_rate = 1.2f,
			.pellet_count = 1,
			.hspread = DEFAULT_BULLET_HSPREAD,
			.vspread = DEFAULT_BULLET_VSPREAD
		},
		.ads = {
			.enabled = true,
			.accuracy_multiplier = 0.5f,
			.move_speed_scale = 0.6f,
			.zoom_enabled = false,
			.zoom_fov = 90.0f,
			.scope_overlay = false
		},
		.bracing = { .enabled = false },
		.pickup_ammo_amount = 40,
		.frame_activate_last = 4,
		.frame_fire_last = 8,
		.frame_idle_last = 52,
		.frame_deactivate_last = 55
	},

	/* WEAP_PP_SHOTGUN - Replaces Shotgun */
	{
		.id = WEAP_PP_SHOTGUN,
		.classname = "weapon_shotgun",
		.ui_name = "Shotgun",
		.ammo_type = AMMO_PP_SHELLS,
		.ammo_per_shot = 1,
		.fire_mode_type = FIRE_MODE_SHOTGUN,
		.hitscan = {
			.rate_rps = 1.0f,
			.damage = 4,
			.spread_base = 1.0f,
			.bloom_per_shot = 0.0f,
			.bloom_recover_rate = 1.0f,
			.pellet_count = DEFAULT_SHOTGUN_COUNT,
			.hspread = 500,
			.vspread = 500
		},
		.ads = {
			.enabled = true,
			.accuracy_multiplier = 0.5f,
			.move_speed_scale = 0.6f,
			.zoom_enabled = false,
			.zoom_fov = 90.0f,
			.scope_overlay = false
		},
		.bracing = { .enabled = false },
		.pickup_ammo_amount = 10,
		.frame_activate_last = 7,
		.frame_fire_last = 18,
		.frame_idle_last = 36,
		.frame_deactivate_last = 39
	},

	/* WEAP_PP_DOUBLE_BARREL - Replaces Super Shotgun */
	{
		.id = WEAP_PP_DOUBLE_BARREL,
		.classname = "weapon_supershotgun",
		.ui_name = "Double-Barrel Shotgun",
		.ammo_type = AMMO_PP_SHELLS,
		.ammo_per_shot = 2,
		.fire_mode_type = FIRE_MODE_SHOTGUN,
		.hitscan = {
			.rate_rps = 0.9f,
			.damage = 6,
			.spread_base = 1.0f,
			.bloom_per_shot = 0.0f,
			.bloom_recover_rate = 1.0f,
			.pellet_count = DEFAULT_SSHOTGUN_COUNT,
			.hspread = DEFAULT_SHOTGUN_HSPREAD,
			.vspread = DEFAULT_SHOTGUN_VSPREAD
		},
		.ads = {
			.enabled = true,
			.accuracy_multiplier = 0.5f,
			.move_speed_scale = 0.6f,
			.zoom_enabled = false,
			.zoom_fov = 90.0f,
			.scope_overlay = false
		},
		.bracing = { .enabled = false },
		.pickup_ammo_amount = 10,
		.frame_activate_last = 6,
		.frame_fire_last = 17,
		.frame_idle_last = 57,
		.frame_deactivate_last = 61
	},

	/* WEAP_PP_SMG - Replaces Machinegun */
	{
		.id = WEAP_PP_SMG,
		.classname = "weapon_machinegun",
		.ui_name = "SMG",
		.ammo_type = AMMO_LIGHT_ROUNDS,
		.ammo_per_shot = 1,
		.fire_mode_type = FIRE_MODE_HITSCAN,
		.hitscan = {
			.rate_rps = 12.0f,
			.damage = 6,
			.spread_base = 1.25f,
			.bloom_per_shot = 0.18f,
			.bloom_recover_rate = 1.0f,
			.pellet_count = 1,
			.hspread = DEFAULT_BULLET_HSPREAD,
			.vspread = DEFAULT_BULLET_VSPREAD
		},
		.ads = {
			.enabled = true,
			.accuracy_multiplier = 0.5f,
			.move_speed_scale = 0.55f,
			.zoom_enabled = false,
			.zoom_fov = 90.0f,
			.scope_overlay = false
		},
		.bracing = { .enabled = false },
		.pickup_ammo_amount = 80,
		.frame_activate_last = 3,
		.frame_fire_last = 5,
		.frame_idle_last = 45,
		.frame_deactivate_last = 49
	},

	/* WEAP_PP_M16 - Replaces Chaingun */
	{
		.id = WEAP_PP_M16,
		.classname = "weapon_chaingun",
		.ui_name = "M16",
		.ammo_type = AMMO_HEAVY_ROUNDS,
		.ammo_per_shot = 1,
		.fire_mode_type = FIRE_MODE_HITSCAN,
		.hitscan = {
			.rate_rps = 9.0f,
			.damage = 8,
			.spread_base = 0.9f,
			.bloom_per_shot = 0.08f,
			.bloom_recover_rate = 1.4f,
			.pellet_count = 1,
			.hspread = DEFAULT_BULLET_HSPREAD,
			.vspread = DEFAULT_BULLET_VSPREAD
		},
		.ads = {
			.enabled = true,
			.accuracy_multiplier = 0.5f,
			.move_speed_scale = 0.5f,
			.zoom_enabled = false,
			.zoom_fov = 90.0f,
			.scope_overlay = false
		},
		.bracing = { .enabled = false },
		.pickup_ammo_amount = 60,
		.frame_activate_last = 4,
		.frame_fire_last = 31,
		.frame_idle_last = 61,
		.frame_deactivate_last = 64
	},

	/* WEAP_PP_FLAMETHROWER - Replaces Hyperblaster */
	{
		.id = WEAP_PP_FLAMETHROWER,
		.classname = "weapon_hyperblaster",
		.ui_name = "M1 Flamethrower",
		.ammo_type = AMMO_FLAME_FUEL,
		.ammo_per_shot = 1,
		.fire_mode_type = FIRE_MODE_CONE_STREAM,
		.flamethrower = {
			.fuel_per_tick = 1.0f,
			.tick_rate_hz = 15.0f,
			.range_units = 220.0f,
			.damage_per_tick = 6,
			.ignite_chance = 1.0f
		},
		.burn_piles = {
			.enabled = true,
			.spawn_rate_hz = 6.0f,
			.lifetime_sec = 6.0f,
			.damage_per_tick = 8,
			.tick_rate_hz = 5.0f,
			.max_active = 32
		},
		.ads = {
			.enabled = false,
			.accuracy_multiplier = 1.0f,
			.move_speed_scale = 1.0f,
			.zoom_enabled = false,
			.zoom_fov = 90.0f,
			.scope_overlay = false
		},
		.bracing = { .enabled = false },
		.pickup_ammo_amount = 100,
		.frame_activate_last = 5,
		.frame_fire_last = 20,
		.frame_idle_last = 49,
		.frame_deactivate_last = 53
	},

	/* WEAP_PP_GRENADE_LAUNCHER - Replaces Grenade Launcher */
	{
		.id = WEAP_PP_GRENADE_LAUNCHER,
		.classname = "weapon_grenadelauncher",
		.ui_name = "Grenade Launcher",
		.ammo_type = AMMO_GL_ROUNDS_40MM,
		.ammo_per_shot = 1,
		.fire_mode_type = FIRE_MODE_PROJECTILE,
		.projectile = {
			.bounce = true,
			.contact_detonation = false,
			.speed = 660.0f,  /* Q2 default 600 * 1.1 */
			.fuse_time_sec = 1.8f,
			.gravity_scale = 1.0f,
			.damage = 120,
			.radius = 160,
			.radius_damage = 120
		},
		.ads = {
			.enabled = true,
			.accuracy_multiplier = 0.5f,
			.move_speed_scale = 0.55f,
			.zoom_enabled = false,
			.zoom_fov = 90.0f,
			.scope_overlay = false
		},
		.bracing = { .enabled = false },
		.pickup_ammo_amount = 8,
		.frame_activate_last = 5,
		.frame_fire_last = 16,
		.frame_idle_last = 59,
		.frame_deactivate_last = 64
	},

	/* WEAP_PP_BAZOOKA - Replaces Rocket Launcher */
	{
		.id = WEAP_PP_BAZOOKA,
		.classname = "weapon_rocketlauncher",
		.ui_name = "Bazooka",
		.ammo_type = AMMO_ROCKETS,
		.ammo_per_shot = 1,
		.fire_mode_type = FIRE_MODE_PROJECTILE,
		.projectile = {
			.bounce = false,
			.contact_detonation = true,
			.speed = 715.0f,  /* Q2 default 650 * 1.1 */
			.fuse_time_sec = 10.0f,
			.gravity_scale = 0.0f,
			.damage = 100,
			.radius = 120,
			.radius_damage = 120
		},
		.ads = {
			.enabled = true,
			.accuracy_multiplier = 0.5f,
			.move_speed_scale = 0.55f,
			.zoom_enabled = false,
			.zoom_fov = 90.0f,
			.scope_overlay = false
		},
		.bracing = { .enabled = false },
		.pickup_ammo_amount = 3,
		.frame_activate_last = 4,
		.frame_fire_last = 12,
		.frame_idle_last = 50,
		.frame_deactivate_last = 54
	},

	/* WEAP_PP_SNIPER_RIFLE - Replaces Railgun */
	{
		.id = WEAP_PP_SNIPER_RIFLE,
		.classname = "weapon_railgun",
		.ui_name = "Sniper Rifle",
		.ammo_type = AMMO_SNIPER_ROUNDS,
		.ammo_per_shot = 1,
		.fire_mode_type = FIRE_MODE_HITSCAN,
		.hitscan = {
			.rate_rps = 1.0f,
			.damage = 150,
			.spread_base = 0.1f,
			.bloom_per_shot = 0.0f,
			.bloom_recover_rate = 1.0f,
			.pellet_count = 1,
			.hspread = 0,
			.vspread = 0
		},
		.ads = {
			.enabled = true,
			.accuracy_multiplier = 0.5f,
			.move_speed_scale = 0.4f,
			.zoom_enabled = true,
			.zoom_fov = 25.0f,
			.scope_overlay = true
		},
		.bracing = { .enabled = false },
		.pickup_ammo_amount = 6,
		.frame_activate_last = 3,
		.frame_fire_last = 18,
		.frame_idle_last = 56,
		.frame_deactivate_last = 61
	},

	/* WEAP_PP_MORTAR_CANNON - Replaces BFG */
	{
		.id = WEAP_PP_MORTAR_CANNON,
		.classname = "weapon_bfg",
		.ui_name = "Mortar Cannon",
		.ammo_type = AMMO_MORTAR_ROUNDS,
		.ammo_per_shot = 1,
		.fire_mode_type = FIRE_MODE_PROJECTILE,
		.projectile = {
			.bounce = false,
			.contact_detonation = true,
			.speed = 650.0f,
			.fuse_time_sec = 10.0f,
			.gravity_scale = 0.3f,
			.damage = 200,
			.radius = 480,
			.radius_damage = 200
		},
		.ads = {
			.enabled = true,
			.accuracy_multiplier = 0.5f,
			.move_speed_scale = 0.4f,
			.zoom_enabled = false,
			.zoom_fov = 90.0f,
			.scope_overlay = false
		},
		.bracing = { .enabled = false },
		.pickup_ammo_amount = 3,
		.frame_activate_last = 8,
		.frame_fire_last = 32,
		.frame_idle_last = 55,
		.frame_deactivate_last = 58
	},

	/* WEAP_PP_AIRSTRIKE_MARKER - New ultimate */
	{
		.id = WEAP_PP_AIRSTRIKE_MARKER,
		.classname = "weapon_airstrike",
		.ui_name = "Airstrike Marker",
		.ammo_type = AMMO_AIRSTRIKE_CHARGE,
		.ammo_per_shot = 1,
		.fire_mode_type = FIRE_MODE_PROJECTILE,
		.airstrike = {
			.telegraph_delay_sec = 1.0f,
			.bombs_count = 6,
			.bomb_spacing_units = 120.0f,
			.damage = 250,
			.radius = 280
		},
		.ads = {
			.enabled = false,
			.accuracy_multiplier = 1.0f,
			.move_speed_scale = 1.0f,
			.zoom_enabled = false,
			.zoom_fov = 90.0f,
			.scope_overlay = false
		},
		.bracing = { .enabled = false },
		.pickup_ammo_amount = 1,
		.frame_activate_last = 4,
		.frame_fire_last = 8,
		.frame_idle_last = 20,
		.frame_deactivate_last = 24
	}
};

/* ============================================================================
 * DEFAULT THROWABLES
 * ============================================================================ */

static const pp_throwable_params_t default_throwable_grenade = {
	.speed = 650.0f,
	.fuse_time_sec = 2.5f,
	.arm_delay_sec = 0.0f,
	.damage = 120,
	.radius = 160,
	.bounce = true
};

static const pp_throwable_params_t default_throwable_mine = {
	.speed = 550.0f,
	.fuse_time_sec = 0.0f,
	.arm_delay_sec = 0.6f,
	.damage = 160,
	.radius = 200,
	.bounce = false
};

static const pp_throwable_params_t default_throwable_satchel = {
	.speed = 550.0f,
	.fuse_time_sec = 1.5f,
	.arm_delay_sec = 0.0f,
	.damage = 240,
	.radius = 260,
	.bounce = false
};

/* ============================================================================
 * INITIALIZATION
 * ============================================================================ */

static void
PP_Weapon_LoadDefaults(void)
{
	int i;

	memset(&g_weapon_profile, 0, sizeof(g_weapon_profile));

	/* Meta */
	Q_strlcpy(g_weapon_profile.name, "default", sizeof(g_weapon_profile.name));
	g_weapon_profile.version = 1;
	Q_strlcpy(g_weapon_profile.author, "Plastic Platoon", sizeof(g_weapon_profile.author));
	Q_strlcpy(g_weapon_profile.description, "Compiled defaults", sizeof(g_weapon_profile.description));

	/* Ammo caps */
	for (i = 0; i < AMMO_PP_MAX; i++)
	{
		g_weapon_profile.ammo_caps[i] = default_ammo_caps[i];
	}

	/* Weapons */
	for (i = 0; i < WEAP_PP_MAX; i++)
	{
		memcpy(&g_weapon_profile.weapons[i], &default_weapons[i], sizeof(pp_weapon_params_t));
	}

	/* Throwables */
	memcpy(&g_weapon_profile.throwable_grenade, &default_throwable_grenade, sizeof(pp_throwable_params_t));
	memcpy(&g_weapon_profile.throwable_mine, &default_throwable_mine, sizeof(pp_throwable_params_t));
	memcpy(&g_weapon_profile.throwable_satchel, &default_throwable_satchel, sizeof(pp_throwable_params_t));

	/* Global settings */
	g_weapon_profile.ads_move_speed_default = ADS_MOVE_SPEED_DEFAULT;
	g_weapon_profile.ads_accuracy_mult_default = ADS_ACCURACY_MULT_DEFAULT;
	g_weapon_profile.throw_cooldown_sec = 0.4f;

	/* Checksum will be computed after any overrides are applied */
	g_weapon_profile.checksum = 0;
}

void
PP_Weapon_Init(void)
{
	/* Register cvars */
	sv_weapon_profile = gi.cvar("sv_weapon_profile", "default", CVAR_SERVERINFO);
	sv_weapon_profile_dir = gi.cvar("sv_weapon_profile_dir", "plastic_platoon/tuning", 0);
	sv_pure_weapons = gi.cvar("sv_pure_weapons", "1", CVAR_SERVERINFO);

	/* Load defaults */
	PP_Weapon_LoadDefaults();

	/* Try to load profile from cvar */
	if (sv_weapon_profile->string[0])
	{
		if (!PP_Weapon_LoadProfile(sv_weapon_profile->string))
		{
			gi.dprintf("Weapon profile '%s' not found, using defaults\n", sv_weapon_profile->string);
		}
	}
}

void
PP_Weapon_Shutdown(void)
{
	/* Nothing to clean up currently */
}

/* ============================================================================
 * PROFILE MANAGEMENT
 * ============================================================================ */

const pp_weapon_profile_t *
PP_Weapon_GetProfile(void)
{
	return &g_weapon_profile;
}

void
PP_Weapon_ReloadProfile(void)
{
	PP_Weapon_LoadDefaults();

	if (sv_weapon_profile->string[0])
	{
		PP_Weapon_LoadProfile(sv_weapon_profile->string);
	}

	gi.dprintf("Weapon profile reloaded: %s\n", g_weapon_profile.name);
}

/* ============================================================================
 * PARAMETER ACCESS
 * ============================================================================ */

const pp_weapon_params_t *
PP_Weapon_GetParams(pp_weapon_id_t weapon_id)
{
	if (weapon_id < 0 || weapon_id >= WEAP_PP_MAX)
	{
		return NULL;
	}

	return &g_weapon_profile.weapons[weapon_id];
}

int
PP_Weapon_GetAmmoCap(pp_ammo_id_t ammo_id)
{
	if (ammo_id < 0 || ammo_id >= AMMO_PP_MAX)
	{
		return 0;
	}

	return g_weapon_profile.ammo_caps[ammo_id];
}

/* ============================================================================
 * WEAPON ID MAPPING
 * ============================================================================ */

pp_weapon_id_t
PP_Weapon_FromQ2Weapon(int q2_weapmodel)
{
	switch (q2_weapmodel)
	{
		case WEAP_BLASTER:        return WEAP_PP_PISTOL;
		case WEAP_SHOTGUN:        return WEAP_PP_SHOTGUN;
		case WEAP_SUPERSHOTGUN:   return WEAP_PP_DOUBLE_BARREL;
		case WEAP_MACHINEGUN:     return WEAP_PP_SMG;
		case WEAP_CHAINGUN:       return WEAP_PP_M16;
		case WEAP_HYPERBLASTER:   return WEAP_PP_FLAMETHROWER;
		case WEAP_GRENADELAUNCHER: return WEAP_PP_GRENADE_LAUNCHER;
		case WEAP_ROCKETLAUNCHER: return WEAP_PP_BAZOOKA;
		case WEAP_RAILGUN:        return WEAP_PP_SNIPER_RIFLE;
		case WEAP_BFG:            return WEAP_PP_MORTAR_CANNON;
		default:                  return WEAP_PP_NONE;
	}
}

const char *
PP_Weapon_GetName(pp_weapon_id_t weapon_id)
{
	if (weapon_id < 0 || weapon_id >= WEAP_PP_MAX)
	{
		return "Unknown";
	}

	return g_weapon_profile.weapons[weapon_id].ui_name;
}

const char *
PP_Ammo_GetName(pp_ammo_id_t ammo_id)
{
	if (ammo_id < 0 || ammo_id >= AMMO_PP_MAX)
	{
		return "Unknown";
	}

	return ammo_names[ammo_id];
}

/* ============================================================================
 * ADS AND SPREAD CALCULATIONS
 * ============================================================================ */

float
PP_Weapon_GetSpreadMultiplier(edict_t *ent, pp_weapon_id_t weapon_id)
{
	const pp_weapon_params_t *params;
	pp_client_weapon_state_t *ws;
	float spread = 1.0f;
	qboolean is_crouched;
	qboolean is_ads;

	if (!ent || !ent->client)
	{
		return 1.0f;
	}

	params = PP_Weapon_GetParams(weapon_id);
	if (!params)
	{
		return 1.0f;
	}

	ws = &ent->client->weapon_state;
	is_crouched = (ent->client->ps.pmove.pm_flags & PMF_DUCKED) != 0;
	is_ads = ws->ads_active;

	/* Base spread from weapon */
	spread = params->hitscan.spread_base;

	/* M60 bracing special case */
	if (params->bracing.enabled)
	{
		if (is_ads)
		{
			spread *= params->bracing.spread_ads;
		}
		else if (is_crouched)
		{
			spread *= params->bracing.spread_crouched_hip;
		}
		else
		{
			spread *= params->bracing.spread_standing_hip;
		}
	}
	else if (is_ads && params->ads.enabled)
	{
		/* Standard ADS accuracy bonus */
		spread *= params->ads.accuracy_multiplier;
	}

	/* Apply bloom */
	spread *= (1.0f + ws->current_bloom);

	return spread;
}

float
PP_Weapon_GetMoveSpeedScale(edict_t *ent, pp_weapon_id_t weapon_id)
{
	const pp_weapon_params_t *params;
	pp_client_weapon_state_t *ws;

	if (!ent || !ent->client)
	{
		return 1.0f;
	}

	params = PP_Weapon_GetParams(weapon_id);
	if (!params)
	{
		return 1.0f;
	}

	ws = &ent->client->weapon_state;

	if (ws->ads_active && params->ads.enabled)
	{
		return params->ads.move_speed_scale;
	}

	return 1.0f;
}

/* ============================================================================
 * BLOOM MANAGEMENT
 * ============================================================================ */

void
PP_Weapon_AddBloom(edict_t *ent, pp_weapon_id_t weapon_id)
{
	const pp_weapon_params_t *params;
	pp_client_weapon_state_t *ws;
	float max_bloom = 2.0f;  /* Cap bloom at 200% increase */

	if (!ent || !ent->client)
	{
		return;
	}

	params = PP_Weapon_GetParams(weapon_id);
	if (!params)
	{
		return;
	}

	ws = &ent->client->weapon_state;
	ws->current_bloom += params->hitscan.bloom_per_shot;

	if (ws->current_bloom > max_bloom)
	{
		ws->current_bloom = max_bloom;
	}

	ws->last_fire_time = level.time;
}

void
PP_Weapon_UpdateBloom(edict_t *ent, pp_weapon_id_t weapon_id, float frametime)
{
	const pp_weapon_params_t *params;
	pp_client_weapon_state_t *ws;
	float decay;

	if (!ent || !ent->client)
	{
		return;
	}

	params = PP_Weapon_GetParams(weapon_id);
	if (!params)
	{
		return;
	}

	ws = &ent->client->weapon_state;

	/* Decay bloom over time */
	decay = params->hitscan.bloom_recover_rate * frametime;
	ws->current_bloom -= decay;

	if (ws->current_bloom < 0.0f)
	{
		ws->current_bloom = 0.0f;
	}
}

/* ============================================================================
 * THROWABLE MANAGEMENT
 * ============================================================================ */

void
PP_Throwable_Select(edict_t *ent, pp_ammo_id_t throwable_type)
{
	if (!ent || !ent->client)
	{
		return;
	}

	/* Validate throwable type */
	if (throwable_type != AMMO_THROWABLE_GRENADE &&
		throwable_type != AMMO_THROWABLE_MINE &&
		throwable_type != AMMO_THROWABLE_SATCHEL)
	{
		return;
	}

	ent->client->weapon_state.selected_throwable = throwable_type;
}

qboolean
PP_Throwable_CanThrow(edict_t *ent)
{
	pp_client_weapon_state_t *ws;

	if (!ent || !ent->client)
	{
		return false;
	}

	ws = &ent->client->weapon_state;

	/* Check cooldown */
	if (level.time < ws->throw_cooldown_end)
	{
		return false;
	}

	/* Check ammo - would need inventory access */
	/* This will be implemented when we integrate with the inventory system */

	return true;
}

void
PP_Throwable_Throw(edict_t *ent)
{
	pp_client_weapon_state_t *ws;
	const pp_throwable_params_t *params;

	if (!ent || !ent->client)
	{
		return;
	}

	if (!PP_Throwable_CanThrow(ent))
	{
		return;
	}

	ws = &ent->client->weapon_state;

	/* Get throwable params based on selected type */
	switch (ws->selected_throwable)
	{
		case AMMO_THROWABLE_GRENADE:
			params = &g_weapon_profile.throwable_grenade;
			break;
		case AMMO_THROWABLE_MINE:
			params = &g_weapon_profile.throwable_mine;
			break;
		case AMMO_THROWABLE_SATCHEL:
			params = &g_weapon_profile.throwable_satchel;
			break;
		default:
			return;
	}

	/* Set cooldown */
	ws->throw_cooldown_end = level.time + g_weapon_profile.throw_cooldown_sec;

	/* Actual throwing logic will be implemented in weapon.c */
	/* This function sets up the state, the actual projectile spawn is elsewhere */
}

/* ============================================================================
 * CONSOLE COMMANDS
 * ============================================================================ */

void
PP_Cmd_WeaponReload(void)
{
	PP_Weapon_ReloadProfile();
	gi.dprintf("Weapon profile reloaded\n");
}

void
PP_Cmd_WeaponDump(void)
{
	int i;
	const pp_weapon_params_t *w;

	gi.dprintf("=== Weapon Profile: %s ===\n", g_weapon_profile.name);
	gi.dprintf("Version: %d, Author: %s\n", g_weapon_profile.version, g_weapon_profile.author);
	gi.dprintf("\n--- Ammo Caps ---\n");

	for (i = 0; i < AMMO_PP_MAX; i++)
	{
		gi.dprintf("  %s: %d\n", ammo_names[i], g_weapon_profile.ammo_caps[i]);
	}

	gi.dprintf("\n--- Weapons ---\n");
	for (i = 0; i < WEAP_PP_MAX; i++)
	{
		w = &g_weapon_profile.weapons[i];
		gi.dprintf("  %s:\n", w->ui_name);
		gi.dprintf("    Ammo: %s, Per Shot: %d\n",
				ammo_names[w->ammo_type], w->ammo_per_shot);

		if (w->fire_mode_type == FIRE_MODE_HITSCAN ||
			w->fire_mode_type == FIRE_MODE_SHOTGUN)
		{
			gi.dprintf("    Damage: %d, RPS: %.1f, Spread: %.2f\n",
					w->hitscan.damage, w->hitscan.rate_rps, w->hitscan.spread_base);
		}

		if (w->ads.enabled)
		{
			gi.dprintf("    ADS: accuracy=%.2f, speed=%.2f\n",
					w->ads.accuracy_multiplier, w->ads.move_speed_scale);
		}
	}
}

void
PP_Cmd_WeaponProfile(void)
{
	const char *profile_name;

	if (gi.argc() < 2)
	{
		gi.dprintf("Current profile: %s\n", g_weapon_profile.name);
		gi.dprintf("Usage: sv_weapon_profile <name>\n");
		return;
	}

	profile_name = gi.argv(1);
	gi.cvar_set("sv_weapon_profile", profile_name);
	PP_Weapon_ReloadProfile();
}

/* ============================================================================
 * NETWORK SYNC (STUB - TO BE IMPLEMENTED)
 * ============================================================================ */

void
PP_Weapon_BroadcastProfile(void)
{
	/* TODO: Implement multiplayer profile broadcasting */
	/* This would send the effective profile to all connected clients */
}

void
PP_Weapon_ReceiveProfile(const void *data, int len)
{
	/* TODO: Implement client-side profile reception */
	/* This would receive and apply the server's profile */
	(void)data;
	(void)len;
}

/* ============================================================================
 * FILE READING
 * ============================================================================ */

static char *
PP_ReadFile(const char *filename, int *len_out)
{
	FILE *f;
	char *buffer;
	long size;

	f = fopen(filename, "rb");
	if (!f)
	{
		return NULL;
	}

	fseek(f, 0, SEEK_END);
	size = ftell(f);
	fseek(f, 0, SEEK_SET);

	if (size <= 0 || size > 1024 * 1024)  /* Max 1MB */
	{
		fclose(f);
		return NULL;
	}

	buffer = (char *)malloc(size + 1);
	if (!buffer)
	{
		fclose(f);
		return NULL;
	}

	if (fread(buffer, 1, size, f) != (size_t)size)
	{
		free(buffer);
		fclose(f);
		return NULL;
	}

	buffer[size] = '\0';
	fclose(f);

	if (len_out)
	{
		*len_out = (int)size;
	}

	return buffer;
}

/* ============================================================================
 * JSON PROFILE PARSING HELPERS
 * ============================================================================ */

/* Weapon name to ID mapping */
static pp_weapon_id_t
PP_WeaponNameToId(const char *name)
{
	if (!name) return WEAP_PP_NONE;

	if (strcmp(name, "PISTOL") == 0) return WEAP_PP_PISTOL;
	if (strcmp(name, "SHOTGUN") == 0) return WEAP_PP_SHOTGUN;
	if (strcmp(name, "DOUBLE_BARREL_SHOTGUN") == 0) return WEAP_PP_DOUBLE_BARREL;
	if (strcmp(name, "SMG") == 0) return WEAP_PP_SMG;
	if (strcmp(name, "M16") == 0) return WEAP_PP_M16;
	if (strcmp(name, "M1_FLAMETHROWER") == 0) return WEAP_PP_FLAMETHROWER;
	if (strcmp(name, "FLAMETHROWER") == 0) return WEAP_PP_FLAMETHROWER;
	if (strcmp(name, "GRENADE_LAUNCHER") == 0) return WEAP_PP_GRENADE_LAUNCHER;
	if (strcmp(name, "BAZOOKA") == 0) return WEAP_PP_BAZOOKA;
	if (strcmp(name, "SNIPER_RIFLE") == 0) return WEAP_PP_SNIPER_RIFLE;
	if (strcmp(name, "MORTAR_CANNON") == 0) return WEAP_PP_MORTAR_CANNON;
	if (strcmp(name, "AIRSTRIKE_MARKER") == 0) return WEAP_PP_AIRSTRIKE_MARKER;

	return WEAP_PP_NONE;
}

/* Ammo name to ID mapping */
static pp_ammo_id_t
PP_AmmoNameToId(const char *name)
{
	if (!name) return AMMO_NONE;

	if (strcmp(name, "LIGHT_ROUNDS") == 0) return AMMO_LIGHT_ROUNDS;
	if (strcmp(name, "HEAVY_ROUNDS") == 0) return AMMO_HEAVY_ROUNDS;
	if (strcmp(name, "SNIPER_ROUNDS") == 0) return AMMO_SNIPER_ROUNDS;
	if (strcmp(name, "PP_SHELLS") == 0) return AMMO_PP_SHELLS;
	if (strcmp(name, "GL_ROUNDS_40MM") == 0) return AMMO_GL_ROUNDS_40MM;
	if (strcmp(name, "PP_ROCKETS") == 0) return AMMO_PP_ROCKETS;
	if (strcmp(name, "THROWABLE_GRENADE") == 0) return AMMO_THROWABLE_GRENADE;
	if (strcmp(name, "THROWABLE_MINE") == 0) return AMMO_THROWABLE_MINE;
	if (strcmp(name, "THROWABLE_SATCHEL") == 0) return AMMO_THROWABLE_SATCHEL;
	if (strcmp(name, "FLAME_FUEL") == 0) return AMMO_FLAME_FUEL;
	if (strcmp(name, "AIRSTRIKE_CHARGE") == 0) return AMMO_AIRSTRIKE_CHARGE;
	if (strcmp(name, "MORTAR_ROUNDS") == 0) return AMMO_MORTAR_ROUNDS;

	return AMMO_NONE;
}

/* Clamp helpers for validation */
static int
PP_ClampInt(int val, int min, int max)
{
	if (val < min) return min;
	if (val > max) return max;
	return val;
}

static float
PP_ClampFloat(float val, float min, float max)
{
	if (val < min) return min;
	if (val > max) return max;
	return val;
}

/* Apply fire_mode overrides */
static void
PP_ApplyFireModeOverrides(pp_hitscan_params_t *hitscan, json_value_t *fire_mode)
{
	json_value_t *val;

	if (!hitscan || !fire_mode) return;

	val = JSON_GetMember(fire_mode, "rate_rps");
	if (val) hitscan->rate_rps = PP_ClampFloat(JSON_GetFloat(val, hitscan->rate_rps), 0.1f, 30.0f);

	val = JSON_GetMember(fire_mode, "damage");
	if (val) hitscan->damage = PP_ClampInt(JSON_GetInt(val, hitscan->damage), 0, 1000);

	val = JSON_GetMember(fire_mode, "spread_base");
	if (val) hitscan->spread_base = PP_ClampFloat(JSON_GetFloat(val, hitscan->spread_base), 0.01f, 10.0f);

	val = JSON_GetMember(fire_mode, "bloom_per_shot");
	if (val) hitscan->bloom_per_shot = PP_ClampFloat(JSON_GetFloat(val, hitscan->bloom_per_shot), 0.0f, 1.0f);

	val = JSON_GetMember(fire_mode, "bloom_recover_rate");
	if (val) hitscan->bloom_recover_rate = PP_ClampFloat(JSON_GetFloat(val, hitscan->bloom_recover_rate), 0.1f, 10.0f);

	/* M60 special spread values */
	val = JSON_GetMember(fire_mode, "spread_standing_hip");
	if (val) hitscan->spread_base = PP_ClampFloat(JSON_GetFloat(val, hitscan->spread_base), 0.01f, 10.0f);

	val = JSON_GetMember(fire_mode, "spread_crouched_hip");
	if (val) ; /* Handled in bracing */

	val = JSON_GetMember(fire_mode, "spread_ads");
	if (val) ; /* Handled in bracing */
}

/* Apply projectile overrides */
static void
PP_ApplyProjectileOverrides(pp_projectile_params_t *proj, json_value_t *projectile)
{
	json_value_t *val;

	if (!proj || !projectile) return;

	val = JSON_GetMember(projectile, "bounce");
	if (val) proj->bounce = JSON_GetBool(val, proj->bounce);

	val = JSON_GetMember(projectile, "contact_detonation");
	if (val) proj->contact_detonation = JSON_GetBool(val, proj->contact_detonation);

	val = JSON_GetMember(projectile, "speed_multiplier_vs_q2");
	if (val)
	{
		float mult = PP_ClampFloat(JSON_GetFloat(val, 1.0f), 0.5f, 3.0f);
		/* Base Q2 speeds: grenade=600, rocket=650 */
		if (proj->bounce)
			proj->speed = 600.0f * mult;
		else
			proj->speed = 650.0f * mult;
	}

	val = JSON_GetMember(projectile, "fuse_time_sec");
	if (val) proj->fuse_time_sec = PP_ClampFloat(JSON_GetFloat(val, proj->fuse_time_sec), 0.1f, 10.0f);

	val = JSON_GetMember(projectile, "damage");
	if (val) proj->damage = PP_ClampInt(JSON_GetInt(val, proj->damage), 0, 1000);

	val = JSON_GetMember(projectile, "radius");
	if (val) proj->radius = PP_ClampInt(JSON_GetInt(val, proj->radius), 0, 1024);
}

/* Apply ADS overrides */
static void
PP_ApplyAdsOverrides(pp_ads_params_t *ads, json_value_t *ads_json)
{
	json_value_t *val;

	if (!ads || !ads_json) return;

	val = JSON_GetMember(ads_json, "enabled");
	if (val) ads->enabled = JSON_GetBool(val, ads->enabled);

	val = JSON_GetMember(ads_json, "accuracy_multiplier");
	if (val) ads->accuracy_multiplier = PP_ClampFloat(JSON_GetFloat(val, ads->accuracy_multiplier), 0.1f, 2.0f);

	val = JSON_GetMember(ads_json, "move_speed_scale");
	if (val) ads->move_speed_scale = PP_ClampFloat(JSON_GetFloat(val, ads->move_speed_scale), 0.1f, 1.0f);
}

/* Apply bracing overrides (M60) */
static void
PP_ApplyBracingOverrides(pp_bracing_params_t *bracing, json_value_t *fire_mode)
{
	json_value_t *val;

	if (!bracing || !fire_mode) return;

	val = JSON_GetMember(fire_mode, "spread_standing_hip");
	if (val) bracing->spread_standing_hip = PP_ClampFloat(JSON_GetFloat(val, bracing->spread_standing_hip), 0.1f, 10.0f);

	val = JSON_GetMember(fire_mode, "spread_crouched_hip");
	if (val) bracing->spread_crouched_hip = PP_ClampFloat(JSON_GetFloat(val, bracing->spread_crouched_hip), 0.1f, 10.0f);

	val = JSON_GetMember(fire_mode, "spread_ads");
	if (val) bracing->spread_ads = PP_ClampFloat(JSON_GetFloat(val, bracing->spread_ads), 0.1f, 10.0f);
}

/* Apply weapon overrides from JSON */
static void
PP_ApplyWeaponOverrides(json_value_t *weapon_overrides)
{
	int i;
	json_value_t *weapon_obj;
	json_value_t *fire_mode;
	json_value_t *ads;
	json_value_t *projectile;
	pp_weapon_id_t weap_id;
	pp_weapon_params_t *params;

	if (!weapon_overrides || weapon_overrides->type != JSON_OBJECT)
	{
		return;
	}

	for (i = 0; i < weapon_overrides->child_count; i++)
	{
		weapon_obj = &weapon_overrides->children[i];
		weap_id = PP_WeaponNameToId(weapon_obj->key);

		if (weap_id == WEAP_PP_NONE)
		{
			gi.dprintf("Warning: Unknown weapon '%s' in profile\n", weapon_obj->key);
			continue;
		}

		params = &g_weapon_profile.weapons[weap_id];

		/* Apply fire_mode overrides */
		fire_mode = JSON_GetMember(weapon_obj, "fire_mode");
		if (fire_mode)
		{
			PP_ApplyFireModeOverrides(&params->hitscan, fire_mode);

			/* M60 bracing */
			if (params->bracing.enabled)
			{
				PP_ApplyBracingOverrides(&params->bracing, fire_mode);
			}
		}

		/* Apply projectile overrides */
		projectile = JSON_GetMember(weapon_obj, "projectile");
		if (projectile)
		{
			PP_ApplyProjectileOverrides(&params->projectile, projectile);
		}

		/* Apply ADS overrides */
		ads = JSON_GetMember(weapon_obj, "ads");
		if (ads)
		{
			PP_ApplyAdsOverrides(&params->ads, ads);
		}
	}
}

/* Apply ammo cap overrides from JSON */
static void
PP_ApplyAmmoCaps(json_value_t *ammo_caps)
{
	int i;
	json_value_t *cap_val;
	pp_ammo_id_t ammo_id;

	if (!ammo_caps || ammo_caps->type != JSON_OBJECT)
	{
		return;
	}

	for (i = 0; i < ammo_caps->child_count; i++)
	{
		cap_val = &ammo_caps->children[i];
		ammo_id = PP_AmmoNameToId(cap_val->key);

		if (ammo_id == AMMO_NONE)
		{
			gi.dprintf("Warning: Unknown ammo type '%s' in profile\n", cap_val->key);
			continue;
		}

		g_weapon_profile.ammo_caps[ammo_id] = PP_ClampInt(
			JSON_GetInt(cap_val, g_weapon_profile.ammo_caps[ammo_id]),
			1, 9999
		);
	}
}

/* ============================================================================
 * PROFILE LOADING
 * ============================================================================ */

qboolean
PP_Weapon_LoadProfile(const char *profile_name)
{
	char filepath[MAX_QPATH * 2];
	char *file_content;
	char json_error[256];
	json_value_t *root;
	json_value_t *meta;
	json_value_t *ammo_caps;
	json_value_t *weapon_overrides;
	json_value_t *val;
	int file_len;

	if (!profile_name || !profile_name[0])
	{
		return false;
	}

	/* Build file path */
	snprintf(filepath, sizeof(filepath), "%s/%s.json",
		sv_weapon_profile_dir->string, profile_name);

	/* Try to read file */
	file_content = PP_ReadFile(filepath, &file_len);
	if (!file_content)
	{
		/* Try game directory */
		snprintf(filepath, sizeof(filepath), "baseq2/%s/%s.json",
			sv_weapon_profile_dir->string, profile_name);
		file_content = PP_ReadFile(filepath, &file_len);

		if (!file_content)
		{
			return false;
		}
	}

	/* Parse JSON */
	root = JSON_Parse(file_content, json_error, sizeof(json_error));
	
	/* Always free file_content to prevent memory leaks */
	free(file_content);
	file_content = NULL;

	if (!root)
	{
		gi.dprintf("Failed to parse weapon profile '%s': %s\n", profile_name, json_error);
		return false;
	}

	/* Validate JSON structure */
	if (root->type != JSON_OBJECT)
	{
		gi.dprintf("Invalid weapon profile '%s': root must be an object\n", profile_name);
		JSON_Free(root);
		return false;
	}

	/* Parse meta section */
	meta = JSON_GetMember(root, "meta");
	if (meta)
	{
		val = JSON_GetMember(meta, "name");
		if (val)
		{
			Q_strlcpy(g_weapon_profile.name, JSON_GetString(val, profile_name),
				sizeof(g_weapon_profile.name));
		}

		val = JSON_GetMember(meta, "version");
		if (val)
		{
			g_weapon_profile.version = JSON_GetInt(val, 1);
		}

		val = JSON_GetMember(meta, "author");
		if (val)
		{
			Q_strlcpy(g_weapon_profile.author, JSON_GetString(val, "Unknown"),
				sizeof(g_weapon_profile.author));
		}

		val = JSON_GetMember(meta, "description");
		if (val)
		{
			Q_strlcpy(g_weapon_profile.description, JSON_GetString(val, ""),
				sizeof(g_weapon_profile.description));
		}
	}

	/* Apply ammo caps */
	ammo_caps = JSON_GetMember(root, "ammo_caps");
	if (ammo_caps && ammo_caps->type == JSON_OBJECT)
	{
		PP_ApplyAmmoCaps(ammo_caps);
	}
	else if (ammo_caps)
	{
		gi.dprintf("Warning: ammo_caps section is not a valid object in profile '%s'\n", profile_name);
	}

	/* Apply weapon overrides */
	weapon_overrides = JSON_GetMember(root, "weapon_overrides");
	if (weapon_overrides && weapon_overrides->type == JSON_OBJECT)
	{
		PP_ApplyWeaponOverrides(weapon_overrides);
	}
	else if (weapon_overrides)
	{
		gi.dprintf("Warning: weapon_overrides section is not a valid object in profile '%s'\n", profile_name);
	}

	/* Compute checksum (simple sum for now) */
	/* TODO: Implement proper checksum for network sync */
	g_weapon_profile.checksum = (unsigned int)file_len;

	gi.dprintf("Loaded weapon profile: %s (v%d by %s)\n",
		g_weapon_profile.name, g_weapon_profile.version, g_weapon_profile.author);

	JSON_Free(root);
	return true;
}
