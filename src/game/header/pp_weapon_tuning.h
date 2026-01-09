/*
 * Plastic Platoon - Weapon Tuning System
 *
 * Runtime tunable weapon parameters with JSON profile support.
 * Server-authoritative with hot reload capability.
 */

#ifndef PP_WEAPON_TUNING_H
#define PP_WEAPON_TUNING_H

#include "../../common/header/shared.h"

/* Forward declarations to avoid circular dependency with local.h */
struct edict_s;
typedef struct edict_s edict_t;

/* ============================================================================
 * AMMO TYPES
 * ============================================================================ */

typedef enum {
	AMMO_NONE = -1,
	AMMO_LIGHT_ROUNDS = 0,      /* SMG, Pistol */
	AMMO_HEAVY_ROUNDS,          /* M16, M60 */
	AMMO_SNIPER_ROUNDS,         /* Sniper Rifle */
	AMMO_PP_SHELLS,             /* Shotgun, Double-Barrel */
	AMMO_GL_ROUNDS_40MM,        /* Grenade Launcher */
	AMMO_PP_ROCKETS,            /* Bazooka */
	AMMO_THROWABLE_GRENADE,     /* Hand grenades */
	AMMO_THROWABLE_MINE,        /* Mines */
	AMMO_THROWABLE_SATCHEL,     /* Satchel charges */
	AMMO_FLAME_FUEL,            /* Flamethrower (no pickups) */
	AMMO_AIRSTRIKE_CHARGE,      /* Airstrike marker (single use) */
	AMMO_PP_MAX
} pp_ammo_id_t;

/* Default ammo caps */
#define AMMO_CAP_LIGHT_ROUNDS       999
#define AMMO_CAP_HEAVY_ROUNDS       999
#define AMMO_CAP_SNIPER_ROUNDS      999
#define AMMO_CAP_PP_SHELLS          999
#define AMMO_CAP_GL_ROUNDS_40MM     100
#define AMMO_CAP_PP_ROCKETS         100
#define AMMO_CAP_THROWABLE_GRENADE  6
#define AMMO_CAP_THROWABLE_MINE     6
#define AMMO_CAP_THROWABLE_SATCHEL  3
#define AMMO_CAP_FLAME_FUEL         100
#define AMMO_CAP_AIRSTRIKE_CHARGE   1

/* ============================================================================
 * WEAPON IDS
 * ============================================================================ */

typedef enum {
	WEAP_PP_NONE = -1,
	WEAP_PP_PISTOL = 0,          /* Replaces Blaster */
	WEAP_PP_SHOTGUN,             /* Replaces Shotgun */
	WEAP_PP_DOUBLE_BARREL,       /* Replaces Super Shotgun */
	WEAP_PP_SMG,                 /* Replaces Machinegun */
	WEAP_PP_M16,                 /* Replaces Chaingun */
	WEAP_PP_M60,                 /* Replaces Hyperblaster */
	WEAP_PP_GRENADE_LAUNCHER,    /* Replaces Grenade Launcher */
	WEAP_PP_BAZOOKA,             /* Replaces Rocket Launcher */
	WEAP_PP_SNIPER_RIFLE,        /* Replaces Railgun */
	WEAP_PP_FLAMETHROWER,        /* Replaces BFG */
	WEAP_PP_AIRSTRIKE_MARKER,    /* New ultimate */
	WEAP_PP_MAX
} pp_weapon_id_t;

/* ============================================================================
 * FIRE MODE TYPES
 * ============================================================================ */

typedef enum {
	FIRE_MODE_HITSCAN = 0,
	FIRE_MODE_PROJECTILE,
	FIRE_MODE_CONE_STREAM,       /* Flamethrower */
	FIRE_MODE_SHOTGUN            /* Multiple pellets */
} pp_fire_mode_type_t;

/* ============================================================================
 * ADS (AIM DOWN SIGHTS) PARAMETERS
 * ============================================================================ */

typedef struct {
	qboolean enabled;
	float accuracy_multiplier;   /* Spread multiplier when ADS (0.0-1.0, lower = tighter) */
	float move_speed_scale;      /* Movement speed multiplier when ADS (0.0-1.0) */
	qboolean zoom_enabled;       /* For sniper scope */
	float zoom_fov;              /* FOV when zoomed (e.g., 25 for sniper) */
	qboolean scope_overlay;      /* Show scope overlay texture */
} pp_ads_params_t;

/* Default ADS values */
#define ADS_ACCURACY_MULT_DEFAULT   0.75f
#define ADS_MOVE_SPEED_DEFAULT      0.5f

/* ============================================================================
 * HITSCAN FIRE MODE PARAMETERS
 * ============================================================================ */

typedef struct {
	float rate_rps;              /* Rounds per second */
	int damage;                  /* Damage per hit */
	float spread_base;           /* Base spread multiplier (1.0 = default) */
	float bloom_per_shot;        /* Spread increase per shot */
	float bloom_recover_rate;    /* Bloom recovery rate per second */
	int pellet_count;            /* For shotguns: number of pellets */
	int hspread;                 /* Horizontal spread (for shotgun) */
	int vspread;                 /* Vertical spread (for shotgun) */
} pp_hitscan_params_t;

/* ============================================================================
 * PROJECTILE FIRE MODE PARAMETERS
 * ============================================================================ */

typedef struct {
	qboolean bounce;             /* Bounces off surfaces */
	qboolean contact_detonation; /* Explodes on contact */
	float speed;                 /* Projectile speed (units/sec) */
	float fuse_time_sec;         /* Time until detonation */
	float gravity_scale;         /* Gravity multiplier (1.0 = normal) */
	int damage;                  /* Direct hit damage */
	int radius;                  /* Explosion radius */
	int radius_damage;           /* Splash damage */
} pp_projectile_params_t;

/* ============================================================================
 * M60 BRACING PARAMETERS (SPECIAL CASE)
 * ============================================================================ */

typedef struct {
	qboolean enabled;
	float spread_standing_hip;   /* Spread when standing, not ADS */
	float spread_crouched_hip;   /* Spread when crouched, not ADS */
	float spread_ads;            /* Spread when ADS (any stance) */
} pp_bracing_params_t;

/* ============================================================================
 * FLAMETHROWER PARAMETERS
 * ============================================================================ */

typedef struct {
	float fuel_per_tick;         /* Fuel consumed per tick */
	float tick_rate_hz;          /* Ticks per second */
	float range_units;           /* Max range */
	int damage_per_tick;         /* Damage per tick to targets */
	float ignite_chance;         /* Chance to ignite (0.0-1.0) */
} pp_flamethrower_params_t;

typedef struct {
	qboolean enabled;
	float spawn_rate_hz;         /* Burn pile spawn rate */
	float lifetime_sec;          /* How long burn piles last */
	int damage_per_tick;         /* Damage to entities in burn pile */
	float tick_rate_hz;          /* Burn pile damage tick rate */
	int max_active;              /* Max simultaneous burn piles */
} pp_burn_pile_params_t;

/* ============================================================================
 * AIRSTRIKE PARAMETERS
 * ============================================================================ */

typedef struct {
	float telegraph_delay_sec;   /* Delay before bombs drop */
	int bombs_count;             /* Number of bombs (6-8) */
	float bomb_spacing_units;    /* Spacing between bombs */
	int damage;                  /* Per-bomb damage */
	int radius;                  /* Per-bomb radius */
} pp_airstrike_params_t;

/* ============================================================================
 * THROWABLE PARAMETERS
 * ============================================================================ */

typedef struct {
	float speed;                 /* Throw velocity */
	float fuse_time_sec;         /* Fuse time (grenades, satchels) */
	float arm_delay_sec;         /* Arming delay (mines) */
	int damage;
	int radius;
	qboolean bounce;
} pp_throwable_params_t;

/* ============================================================================
 * COMPLETE WEAPON PARAMETERS
 * ============================================================================ */

typedef struct {
	pp_weapon_id_t id;
	const char *classname;       /* For item spawning */
	const char *ui_name;         /* Display name */
	pp_ammo_id_t ammo_type;
	int ammo_per_shot;           /* Ammo consumed per shot */
	pp_fire_mode_type_t fire_mode_type;

	/* Fire mode params (use appropriate one based on fire_mode_type) */
	pp_hitscan_params_t hitscan;
	pp_projectile_params_t projectile;
	pp_flamethrower_params_t flamethrower;
	pp_burn_pile_params_t burn_piles;
	pp_airstrike_params_t airstrike;

	/* ADS */
	pp_ads_params_t ads;

	/* M60 special bracing */
	pp_bracing_params_t bracing;

	/* Weapon pickup grants ammo */
	int pickup_ammo_amount;

	/* Frame timing (animation) */
	int frame_activate_last;
	int frame_fire_last;
	int frame_idle_last;
	int frame_deactivate_last;
} pp_weapon_params_t;

/* ============================================================================
 * AMMO PICKUP DEFINITION
 * ============================================================================ */

typedef struct {
	const char *classname;
	pp_ammo_id_t ammo_type;
	int amount;
} pp_ammo_pickup_t;

/* ============================================================================
 * RESUPPLY CRATE DEFINITION
 * ============================================================================ */

#define MAX_RESUPPLY_GRANTS 8

typedef struct {
	pp_ammo_id_t ammo_type;
	int amount;
} pp_resupply_grant_t;

typedef struct {
	const char *classname;
	const char *ui_name;
	qboolean raises_caps;
	pp_resupply_grant_t grants[MAX_RESUPPLY_GRANTS];
	int grant_count;
} pp_resupply_item_t;

/* ============================================================================
 * WEAPON PROFILE (COMPLETE TUNING STATE)
 * ============================================================================ */

typedef struct {
	char name[64];
	int version;
	char author[64];
	char description[256];

	/* Ammo caps */
	int ammo_caps[AMMO_PP_MAX];

	/* Weapon parameters */
	pp_weapon_params_t weapons[WEAP_PP_MAX];

	/* Throwables */
	pp_throwable_params_t throwable_grenade;
	pp_throwable_params_t throwable_mine;
	pp_throwable_params_t throwable_satchel;

	/* Global settings */
	float ads_move_speed_default;
	float ads_accuracy_mult_default;
	float throw_cooldown_sec;

	/* Checksum for network sync */
	unsigned int checksum;
} pp_weapon_profile_t;

/* ============================================================================
 * RUNTIME STATE (PER-CLIENT)
 * ============================================================================ */

typedef struct {
	/* ADS state */
	qboolean ads_active;
	float ads_transition;        /* 0.0 = hip, 1.0 = full ADS (for smooth transition) */

	/* Bloom tracking */
	float current_bloom;         /* Current accumulated bloom */
	float last_fire_time;        /* For bloom recovery calculation */

	/* Throwable selection */
	pp_ammo_id_t selected_throwable;
	float throw_cooldown_end;    /* Time when throw cooldown ends */

	/* M60 bracing state */
	qboolean is_braced;          /* Crouched or ADS */
} pp_client_weapon_state_t;

/* ============================================================================
 * GLOBAL FUNCTIONS
 * ============================================================================ */

/* Profile management */
void PP_Weapon_Init(void);
void PP_Weapon_Shutdown(void);
qboolean PP_Weapon_LoadProfile(const char *profile_name);
void PP_Weapon_ReloadProfile(void);
const pp_weapon_profile_t *PP_Weapon_GetProfile(void);

/* Get parameters */
const pp_weapon_params_t *PP_Weapon_GetParams(pp_weapon_id_t weapon_id);
int PP_Weapon_GetAmmoCap(pp_ammo_id_t ammo_id);

/* Apply ADS effects */
float PP_Weapon_GetSpreadMultiplier(edict_t *ent, pp_weapon_id_t weapon_id);
float PP_Weapon_GetMoveSpeedScale(edict_t *ent, pp_weapon_id_t weapon_id);

/* Bloom management */
void PP_Weapon_AddBloom(edict_t *ent, pp_weapon_id_t weapon_id);
void PP_Weapon_UpdateBloom(edict_t *ent, pp_weapon_id_t weapon_id, float frametime);

/* Throwable management */
void PP_Throwable_Select(edict_t *ent, pp_ammo_id_t throwable_type);
void PP_Throwable_Throw(edict_t *ent);
qboolean PP_Throwable_CanThrow(edict_t *ent);

/* Utility */
pp_weapon_id_t PP_Weapon_FromQ2Weapon(int q2_weapmodel);
const char *PP_Weapon_GetName(pp_weapon_id_t weapon_id);
const char *PP_Ammo_GetName(pp_ammo_id_t ammo_id);

/* Network sync (multiplayer) */
void PP_Weapon_BroadcastProfile(void);
void PP_Weapon_ReceiveProfile(const void *data, int len);

/* Console commands */
void PP_Cmd_WeaponReload(void);
void PP_Cmd_WeaponDump(void);
void PP_Cmd_WeaponProfile(void);

/* ============================================================================
 * CVAR DECLARATIONS
 * ============================================================================ */

extern cvar_t *sv_weapon_profile;
extern cvar_t *sv_weapon_profile_dir;
extern cvar_t *sv_pure_weapons;

/* ============================================================================
 * GLOBAL RUNTIME STATE
 * ============================================================================ */

extern pp_weapon_profile_t g_weapon_profile;

#endif /* PP_WEAPON_TUNING_H */
