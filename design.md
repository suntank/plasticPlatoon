Let's work on refactoring weapons, adding ADS and also a new script based weapons tuning feature! Here are some docs:

# Plastic Platoon - Weapon + Ammo Implementation Spec
# Target: Quake 2 total conversion (game DLL / weapons system)
# Scope: Weapons, ammo, caps/pickups, ADS, throwables, resupply crates, ultimates
# Excludes: wave-mode logic and progression systems.

meta:
  name: "Plastic Platoon"
  version: "spec-v1"
  philosophy:
    - "Match Quake 2 slot coverage while minimizing redundancy."
    - "High ammo caps for common ammo to reduce wasted pickups."
    - "Low caps for encounter-warping ammo (explosives/throwables/ultimates)."
    - "ADS for most weapons: improved accuracy + reduced movement."
    - "Distinct handling identities for SMG/M16/M60 to avoid 'three bullet hoses'."

globals:
  input:
    throw_key: "g"            # throws selected throwable regardless of active weapon
    ads_key: "mouse2"         # suggested; bindable
    throwable_select:
      mode: "hold_to_select"  # options: hold_to_select | cycle_on_tap | radial
      tap_behavior: "throw_selected"
      hold_behavior: "open_selector_and_release_to_confirm"
      cycle_key_optional: "mousewheel"  # if selector uses cycling
  movement:
    ads_move_speed_scale_default: 0.5   # walking speed factor relative to normal
    m60_ads_move_speed_scale: 0.5       # may be lower if desired (open tuning knob)
  accuracy:
    # Accuracy model is implementation-dependent; represent as multipliers on spread/bloom.
    ads_accuracy_multiplier_default: 0.75  # ADS tightens spread by this factor
  cleanup:
    # Optional global cleanup for performance/readability (not wave logic).
    burn_pile_max_active: 32
    burn_pile_default_lifetime_sec: 6.0

# -----------------------------
# AMMO TYPES AND RULES
# -----------------------------
ammo_types:
  LIGHT_ROUNDS:
    ui_name: "Light Rounds"
    cap_policy: "very_high"
    default_cap: 999  # tuning knob; can lower to hundreds if UI or balance requires
  HEAVY_ROUNDS:
    ui_name: "Heavy Rounds"
    cap_policy: "very_high"
    default_cap: 999
  SNIPER_ROUNDS:
    ui_name: "Sniper Rounds"
    cap_policy: "moderate_low"
    default_cap: 50   # tuning knob; keep scarce to preserve railgun fantasy
  SHELLS:
    ui_name: "Shells"
    cap_policy: "moderate"
    default_cap: 100  # tuning knob
  GL_ROUNDS_40MM:
    ui_name: "40mm Rounds"
    cap_policy: "low"
    default_cap: 50   # tuning knob
  ROCKETS:
    ui_name: "Rockets"
    cap_policy: "low"
    default_cap: 30   # tuning knob
  THROWABLE_GRENADE:
    ui_name: "Grenades"
    cap_policy: "strict"
    default_cap: 6    # tuning knob
  THROWABLE_MINE:
    ui_name: "Mines"
    cap_policy: "strict"
    default_cap: 6    # tuning knob
  THROWABLE_SATCHEL:
    ui_name: "Satchels"
    cap_policy: "strict"
    default_cap: 3    # tuning knob
  FLAME_FUEL:
    ui_name: "Fuel"
    cap_policy: "fixed"
    default_cap: 100  # represents 100% tank; no ammo pickups
  AIRSTRIKE_CHARGE:
    ui_name: "Airstrike"
    cap_policy: "single_use"
    default_cap: 1    # no ammo pickups

ammo_pickups:
  # Use fewer, chunkier pickups than vanilla Q2 to reduce wasted pickups.
  # Values are initial targets; tune after playtests.
  light_rounds_small:   { ammo: LIGHT_ROUNDS, amount: 60 }
  light_rounds_large:   { ammo: LIGHT_ROUNDS, amount: 150 }
  heavy_rounds_small:   { ammo: HEAVY_ROUNDS, amount: 40 }
  heavy_rounds_large:   { ammo: HEAVY_ROUNDS, amount: 120 }
  sniper_rounds_small:  { ammo: SNIPER_ROUNDS, amount: 5 }
  shells_small:         { ammo: SHELLS, amount: 10 }
  shells_large:         { ammo: SHELLS, amount: 25 }
  gl_rounds_small:      { ammo: GL_ROUNDS_40MM, amount: 5 }
  gl_rounds_large:      { ammo: GL_ROUNDS_40MM, amount: 12 }
  rockets_small:        { ammo: ROCKETS, amount: 2 }
  rockets_large:        { ammo: ROCKETS, amount: 5 }
  grenade_pickup:       { ammo: THROWABLE_GRENADE, amount: 3 }
  mine_pickup:          { ammo: THROWABLE_MINE, amount: 3 }
  satchel_pickup:       { ammo: THROWABLE_SATCHEL, amount: 3 }

# -----------------------------
# RESUPPLY ITEMS (REPLACING BANDOLIER/BACKPACK)
# -----------------------------
resupply_items:
  BALLISTICS_AMMO_CRATE:
    ui_name: "Ballistics Ammo Crate"
    raises_caps: false
    grants:
      - { ammo: LIGHT_ROUNDS, amount: 200 }
      - { ammo: HEAVY_ROUNDS, amount: 150 }
      - { ammo: SHELLS, amount: 30 }
      - { ammo: SNIPER_ROUNDS, amount: 5 }   # optional; remove if sniper should be rarer
  EXPLOSIVES_AMMO_CRATE:
    ui_name: "Explosives Ammo Crate"
    raises_caps: false
    grants:
      - { ammo: GL_ROUNDS_40MM, amount: 10 }
      - { ammo: ROCKETS, amount: 4 }
      # Optional: include small throwable top-offs, but keep strict caps meaningful.
      - { ammo: THROWABLE_GRENADE, amount: 1 }
      - { ammo: THROWABLE_MINE, amount: 1 }
      - { ammo: THROWABLE_SATCHEL, amount: 1 }

# -----------------------------
# WEAPON DEFINITIONS (MAPPING TO Q2 SLOTS)
# -----------------------------
weapons:
  # --- Slot: Blaster ---
  PISTOL:
    q2_slot_replaces: "Blaster"
    ui_name: "Pistol"
    ammo_type: LIGHT_ROUNDS
    fire_mode:
      type: "hitscan"
      rate_rps: 4.0          # tuning knob
      damage: 12             # tuning knob
      spread_base: 1.0       # relative
      bloom_per_shot: 0.1
      bloom_recover_rate: 1.2
    ads:
      enabled: true
      accuracy_multiplier: 0.85
      move_speed_scale: 0.6

  # --- Slot: Shotgun ---
  SHOTGUN:
    q2_slot_replaces: "Shotgun"
    ui_name: "Shotgun"
    ammo_type: SHELLS
    implementation_note: "Model swap only; keep Q2 shotgun code/mechanics."
    ads:
      enabled: true
      accuracy_multiplier: 0.9
      move_speed_scale: 0.6

  # --- Slot: Super Shotgun ---
  DOUBLE_BARREL_SHOTGUN:
    q2_slot_replaces: "Super Shotgun"
    ui_name: "Double-Barrel Shotgun"
    ammo_type: SHELLS
    implementation_note: "Model swap only; keep Q2 super shotgun code/mechanics."
    ads:
      enabled: true
      accuracy_multiplier: 0.9
      move_speed_scale: 0.6

  # --- Slot: Machinegun ---
  SMG:
    q2_slot_replaces: "Machinegun"
    ui_name: "SMG"
    ammo_type: LIGHT_ROUNDS
    identity: "Mobile close-range spray; degrades quickly at distance."
    fire_mode:
      type: "hitscan"
      rate_rps: 12.0          # faster than Q2 machinegun
      damage: 6               # lower per-shot damage
      spread_base: 1.25       # ~25% less accurate baseline
      bloom_per_shot: 0.18    # rapid bloom
      bloom_recover_rate: 1.0
    ads:
      enabled: true
      accuracy_multiplier: 0.85  # helps slightly, not enough to turn into M16
      move_speed_scale: 0.55

  # --- Slot: Chaingun (but uses machinegun feel) ---
  M16:
    q2_slot_replaces: "Chaingun"
    ui_name: "M16"
    ammo_type: HEAVY_ROUNDS
    identity: "Controllable mid-range workhorse; better precision than SMG/M60."
    mechanics_base: "Q2_machinegun_style_no_horrendous_recoil"
    fire_mode:
      type: "hitscan"
      rate_rps: 9.0
      damage: 8
      spread_base: 0.9
      bloom_per_shot: 0.08
      bloom_recover_rate: 1.4
    ads:
      enabled: true
      accuracy_multiplier: 0.75
      move_speed_scale: 0.5
    optional_alt_fire:
      enabled: false
      note: "If needed for differentiation: 3-round burst or semi precision."

  # --- Slot: Hyperblaster (but uses chaingun mechanics without spinup) ---
  M60:
    q2_slot_replaces: "Hyperblaster"
    ui_name: "M60"
    ammo_type: HEAVY_ROUNDS
    identity: "High sustained DPS suppression when braced; unreliable standing hipfire."
    mechanics_base: "Q2_chaingun_style_no_spinup"
    fire_mode:
      type: "hitscan"
      rate_rps: 10.0
      damage: 9
      # Bracing rules implemented as spread/bloom state machine.
      spread_standing_hip: 2.0
      spread_crouched_hip: 1.0
      spread_ads: 0.85
      bloom_per_shot: 0.2
      bloom_recover_rate: 0.9
    bracing:
      crouch_bonus_enabled: true
      # Rule: weapon is "good" when crouched or ADS.
      standing_penalty_enabled: true
    ads:
      enabled: true
      accuracy_multiplier: 0.7
      move_speed_scale: 0.5     # walking speed
    notes:
      - "Implement: if standing and not ADS, apply large spread and/or fast bloom."
      - "If crouched OR ADS, apply improved spread. ADS also slows movement."
      - "Goal: M60 should not replace M16 as universal solution."

  # --- Slot: Grenade Launcher ---
  GRENADE_LAUNCHER:
    q2_slot_replaces: "Grenade Launcher"
    ui_name: "Grenade Launcher"
    ammo_type: GL_ROUNDS_40MM
    identity: "Bank-shot skill weapon; more decisive than vanilla via shorter fuse."
    projectile:
      type: "grenade"
      bounce: true
      contact_detonation: false
      speed_multiplier_vs_q2: 1.1   # increased range via velocity
      fuse_time_sec: 1.8            # shorter than Q2 (tuning knob)
      gravity_scale: 1.0            # adjust if you want flatter arc
      damage: 120                   # tuning knob
      radius: 160                   # tuning knob
    ads:
      enabled: true
      accuracy_multiplier: 0.9
      move_speed_scale: 0.55

  # --- Slot: Rocket Launcher ---
  BAZOOKA:
    q2_slot_replaces: "Rocket Launcher"
    ui_name: "Bazooka"
    ammo_type: ROCKETS
    identity: "Iconic direct rocket role; mostly Q2 behavior."
    projectile:
      type: "rocket"
      speed_multiplier_vs_q2: 1.1   # optional
      damage: 100
      radius: 120
    ads:
      enabled: true
      accuracy_multiplier: 0.9
      move_speed_scale: 0.55

  # --- Slot: Railgun ---
  SNIPER_RIFLE:
    q2_slot_replaces: "Railgun"
    ui_name: "Sniper Rifle"
    ammo_type: SNIPER_ROUNDS  # preferred
    identity: "Precision burst; gated by scarce ammo; ADS scope with overlay."
    fire_mode:
      type: "hitscan"
      rate_rps: 1.0
      damage: 150
      spread_base: 0.1
    ads:
      enabled: true
      accuracy_multiplier: 0.3
      move_speed_scale: 0.4
      zoom:
        enabled: true
        fov: 25              # tuning knob
        scope_overlay: true

  # --- Slot: BFG ---
  M1_FLAMETHROWER:
    q2_slot_replaces: "BFG"
    ui_name: "M1 Flamethrower"
    ammo_type: FLAME_FUEL
    ammo_pickups_allowed: false
    identity: "Short-range area denial; leaves temporary burn piles; BFG-tier feel."
    fire_mode:
      type: "cone_or_stream"       # implementation choice
      fuel_per_tick: 1            # fuel burn rate tuning knob
      tick_rate_hz: 15
      range_units: 220
      damage_per_tick: 6
      ignite_chance: 1.0
    burn_piles:
      enabled: true
      spawn_rate_hz: 6
      lifetime_sec: 6.0
      damage_per_tick: 8
      tick_rate_hz: 5
      max_active: 32
    ads:
      enabled: false              # optional; usually not needed for flamethrower
    notes:
      - "Hard range gate. Strong up close, not a mid-range weapon."
      - "No fuel pickups. Weapon pickup grants fixed fuel (default 100)."

  # --- Additional Ultimate ---
  AIRSTRIKE_MARKER:
    q2_slot_replaces: null
    ui_name: "Airstrike Marker"
    ammo_type: AIRSTRIKE_CHARGE
    ammo_pickups_allowed: false
    identity: "Single-use ultimate; call plane that drops BFG-tier bombs over marked area."
    usage:
      consumes: 1
      telegraph_delay_sec: 1.0
      plane_pass:
        bombs_count: 6            # tuning knob 6-8
        bomb_spacing_units: 120
        pattern: "line_or_spread" # implementation choice
        damage: 250               # 2-3x normal explosives
        radius: 280               # very wide radius (BFG-tier)
        falloff: "strong"         # ensure edge damage still meaningful
    notes:
      - "Make audio/visual telegraph obvious before impacts."
      - "No ammo pickups. Item grants single use."

# -----------------------------
# THROWABLES (OFF-HAND SYSTEM)
# -----------------------------
throwables:
  selected_type_default: THROWABLE_GRENADE
  types:
    GRENADE:
      ammo_type: THROWABLE_GRENADE
      ui_name: "Grenade"
      throw:
        speed: 650
        fuse_time_sec: 2.5
        damage: 120
        radius: 160
        bounce: true
    MINE:
      ammo_type: THROWABLE_MINE
      ui_name: "Mine"
      throw:
        speed: 550
        arm_delay_sec: 0.6
        damage: 160
        radius: 200
      behavior:
        trigger: "proximity_or_contact"  # implementation choice
        readable_model: true
        audible_arm_cue: true
    SATCHEL:
      ammo_type: THROWABLE_SATCHEL
      ui_name: "Satchel"
      throw:
        speed: 550
        # Detonation choice:
        detonation: "timed"  # options: timed | remote
        fuse_time_sec: 1.5
        damage: 240          # BFG-tier in explosives category
        radius: 260          # very wide radius
      notes:
        - "Satchel and airstrike bombs are intended as BFG-tier explosives."

throw_logic:
  # Pseudocode contract for agent:
  # - Press G: if selected_type ammo > 0, spawn throwable entity, decrement ammo, apply cooldown.
  # - Hold G (if configured): open selector UI, allow cycling; on release set selected_type.
  cooldown_sec: 0.4
  allow_throw_while_reloading: true
  allow_throw_while_ads: true
  selection_ui:
    show_counts: true
    show_selected_indicator: true

# -----------------------------
# PICKUPS (WEAPON ITEMS)
# -----------------------------
weapon_pickups:
  # Q2 pattern: picking up weapon also grants some ammo.
  # For ultimates, pickup grants fixed charges/fuel and does NOT use ammo pickups.
  PISTOL:
    grants_ammo: [{ ammo: LIGHT_ROUNDS, amount: 40 }]
  SHOTGUN:
    grants_ammo: [{ ammo: SHELLS, amount: 10 }]
  DOUBLE_BARREL_SHOTGUN:
    grants_ammo: [{ ammo: SHELLS, amount: 10 }]
  SMG:
    grants_ammo: [{ ammo: LIGHT_ROUNDS, amount: 80 }]
  M16:
    grants_ammo: [{ ammo: HEAVY_ROUNDS, amount: 60 }]
  M60:
    grants_ammo: [{ ammo: HEAVY_ROUNDS, amount: 80 }]
  GRENADE_LAUNCHER:
    grants_ammo: [{ ammo: GL_ROUNDS_40MM, amount: 8 }]
  BAZOOKA:
    grants_ammo: [{ ammo: ROCKETS, amount: 3 }]
  SNIPER_RIFLE:
    grants_ammo: [{ ammo: SNIPER_ROUNDS, amount: 6 }]
  M1_FLAMETHROWER:
    grants_ammo: [{ ammo: FLAME_FUEL, amount: 100 }]
    note: "Fuel is set/add up to cap. No fuel pickups."
  AIRSTRIKE_MARKER:
    grants_ammo: [{ ammo: AIRSTRIKE_CHARGE, amount: 1 }]
    note: "Single use only. No ammo pickups."

# -----------------------------
# IMPLEMENTATION CONTRACTS (STATE MACHINES)
# -----------------------------
contracts:
  ads:
    - "When ADS active: apply weapon.ads.accuracy_multiplier and weapon.ads.move_speed_scale."
    - "ADS should be cancelable by firing (optional) or toggle/hold based on settings."
    - "Sniper ADS: apply zoom FOV and scope overlay while ADS active."
  m60_bracing:
    - "If weapon == M60 and player is standing and not ADS: apply spread_standing_hip."
    - "If crouched and not ADS: apply spread_crouched_hip."
    - "If ADS (standing or crouched): apply spread_ads and ADS movement limit."
  grenade_launcher:
    - "Projectile bounces; detonates on fuse expiry."
    - "Increase range via speed multiplier; reduce fuse time to configured value."
  throwables:
    - "Off-hand throw ignores active weapon selection."
    - "Throw consumes ammo from selected throwable type."
    - "Selection system must be fast; hold-to-select or cycle is acceptable."
  ultimates:
    - "Flamethrower uses FLAME_FUEL only; no pickups except weapon pickup."
    - "Airstrike consumes AIRSTRIKE_CHARGE; no pickups except item pickup."

# -----------------------------
# OPEN TUNING KNOBS (FOR PLAYTEST ITERATION)
# -----------------------------
tuning_knobs:
  - "Ammo caps for bullets: keep very high; ensure UI supports 3 digits or more."
  - "Sniper ammo cap/pickup sizes to maintain scarcity without frustration."
  - "M60 standing penalty strength vs crouch/ADS effectiveness."
  - "GL fuse time and velocity to preserve bank-shots while reducing annoyance."
  - "Satchel radius/damage to be powerful but not dominant in all situations."
  - "Airstrike telegraph delay and bomb pattern to remain readable and fair."

Next document: Script import for weapon stats

1. System Overview
Goals

Runtime tuning of weapon knobs (damage, ROF, spread, fuse time, caps, pickup amounts).

Hot reload in single player and server-hosted co-op.

Multiplayer safe: server is authoritative, clients use the server’s final applied tuning.

Deterministic: all clients simulate the same weapon behavior.

Secure: no code execution from file content.

Core Components

Compiled defaults: Your current weapon constants remain compiled as the baseline.

Weapon tuning profiles: External files override subsets of knobs.

Loader + validator: Parses files, clamps ranges, rejects unknown fields.

Apply step: Overrides your runtime weapon tables and ammo tables.

Network sync (multiplayer): Server sends final effective tuning to clients, clients enforce it.

Hot reload command: sv_weapon_reload reloads profile and rebroadcasts to clients.

2. File Format and Layout
Recommended format

JSON is simplest in C and easiest to validate.

YAML is fine too, but requires a YAML parser. JSON is lower friction.

Directory layout
baseq2/
  plastic_platoon/
    tuning/
      default.json
      arcade.json
      realism.json
      test_local.json

Server cvars / settings

sv_weapon_profile "default"

sv_weapon_profile_dir "plastic_platoon/tuning" (optional)

sv_pure_weapons 1 (enforce server profile and checksum)

3. Dovetail with Your Existing Spec

Take the YAML spec you already have and treat it as the “schema of knobs.” Your runtime weapon system should already have a set of structured values like:

weapons[M16].rate_rps

weapons[M60].spread_standing_hip

ammoCaps[HEAVY_ROUNDS]

pickupAmounts[rockets_large]

The external file overrides exactly those same knobs.

4. JSON Profile Schema (Data-Only)
Example: default.json
{
  "meta": {
    "name": "default",
    "version": 1,
    "author": "Austin",
    "description": "Baseline Plastic Platoon tuning"
  },

  "ammo_caps": {
    "LIGHT_ROUNDS": 999,
    "HEAVY_ROUNDS": 999,
    "SNIPER_ROUNDS": 50,
    "SHELLS": 100,
    "GL_ROUNDS_40MM": 50,
    "ROCKETS": 30,
    "THROWABLE_GRENADE": 6,
    "THROWABLE_MINE": 6,
    "THROWABLE_SATCHEL": 3,
    "FLAME_FUEL": 100,
    "AIRSTRIKE_CHARGE": 1
  },

  "weapon_overrides": {
    "SMG": {
      "fire_mode": {
        "rate_rps": 12.0,
        "damage": 6,
        "spread_base": 1.25,
        "bloom_per_shot": 0.18,
        "bloom_recover_rate": 1.0
      },
      "ads": {
        "enabled": true,
        "accuracy_multiplier": 0.85,
        "move_speed_scale": 0.55
      }
    },

    "M60": {
      "fire_mode": {
        "rate_rps": 10.0,
        "damage": 9,
        "spread_standing_hip": 2.0,
        "spread_crouched_hip": 1.0,
        "spread_ads": 0.85,
        "bloom_per_shot": 0.2,
        "bloom_recover_rate": 0.9
      },
      "ads": {
        "enabled": true,
        "accuracy_multiplier": 0.70,
        "move_speed_scale": 0.50
      }
    },

    "GRENADE_LAUNCHER": {
      "projectile": {
        "bounce": true,
        "contact_detonation": false,
        "speed_multiplier_vs_q2": 1.10,
        "fuse_time_sec": 1.80,
        "damage": 120,
        "radius": 160
      }
    }
  },

  "resupply_items": {
    "BALLISTICS_AMMO_CRATE": {
      "grants": {
        "LIGHT_ROUNDS": 200,
        "HEAVY_ROUNDS": 150,
        "SHELLS": 30,
        "SNIPER_ROUNDS": 5
      }
    },
    "EXPLOSIVES_AMMO_CRATE": {
      "grants": {
        "GL_ROUNDS_40MM": 10,
        "ROCKETS": 4,
        "THROWABLE_GRENADE": 1,
        "THROWABLE_MINE": 1,
        "THROWABLE_SATCHEL": 1
      }
    }
  }
}

Schema rules

Unknown top-level keys: reject or warn (recommended: reject on server, warn in SP).

Unknown weapon names: reject/warn.

Unknown knob fields: reject/warn.

Values must be clamped to safe ranges (see §6).

This is “scriptable” in the sense that you can iterate by editing files, but it is data-only.

5. Runtime Application Flow
5.1 Startup (server or single player)

Load compiled defaults into runtime tables.

Determine profile: sv_weapon_profile (server) or cl_weapon_profile (SP only).

Load JSON file and validate.

Apply overrides to runtime tables.

Compute checksum (SHA-256 or CRC32) of the effective applied config.

Store checksum in serverinfo: sv_weapon_checksum.

5.2 Multiplayer join

Client connects.

Server sends sv_weapon_checksum and a compressed blob of the effective config (or a compact list of overrides).

Client applies the received config, ignoring local files.

Client compares checksum. If mismatch, client forces server version.

If sv_pure_weapons 1, disallow play if client refuses to apply or checksum fails.

5.3 Hot reload (server command)

sv_weapon_reload

Reload file.

Validate, apply.

Recompute checksum.

Broadcast new config and checksum to all clients.

Optionally print a diff summary to server console.

5.4 Single player hot reload

weapon_reload (no sv_ prefix)

Reload local profile and apply immediately.

6. Validation and Safety

This is the part that keeps you safe and prevents “host sets rate_rps to 5000 and crashes clients” problems.

Strongly recommended clamps (examples)

damage: 0 to 1000

rate_rps: 0.1 to 30

spread_*: 0.01 to 10

move_speed_scale: 0.1 to 1.0

radius: 0 to 1024

fuse_time_sec: 0.1 to 10

bombs_count: 1 to 12

Reject unknown keys

Do not accept arbitrary new knobs unless you explicitly add them. This avoids typos silently producing confusing behavior.

Server authority

In multiplayer:

Only server reads from disk.

Clients never load local profiles unless you explicitly add a “client-side cosmetics only” system.

7. Network Sync Implementation Options (Quake 2 Friendly)

Quake 2’s protocol has limited room in configstrings, so use one of these:

Option A: “Compact override list” (recommended)

Send only the overrides, not the whole defaults.

Represent overrides as tuples:

(weaponId, fieldId, value) for floats/ints/bools

(ammoTypeId, capValue)

(pickupId, amount)

This can be sent:

reliably at connect time

reliably after reload

Pros: small, easy to parse, avoids giant blobs.

Option B: Compressed JSON blob

Send a gzip’d JSON string with length prefix via a reliable channel.

Pros: easiest to debug.
Cons: more work, risk of size issues, more allocation.

Option C: “Ship profiles as pak assets”

If you package profiles inside the mod’s pak, then both sides can load the same file. You still need checksum enforcement, but you can send only the profile name.

Pros: tiny net traffic.
Cons: less flexible for quick iteration unless you allow external override in dev builds.

For your stated goal (rapid tuning), Option A is the best.

8. Proposed Internal Data Structures
8.1 Enumerations

weapon_id_t with stable IDs: WEAP_PISTOL, WEAP_SMG, WEAP_M16, etc.

ammo_id_t with stable IDs: AMMO_LIGHT, AMMO_HEAVY, etc.

knob_id_t for each tunable field (generated by hand or script).

8.2 Runtime tables

weapon_params_t g_weaponParams[WEAP_MAX];

int g_ammoCaps[AMMO_MAX];

pickup_params_t g_pickups[PICKUP_MAX];

resupply_params_t g_resupply[RESUPPLY_MAX];

8.3 Config application

Start with compiled defaults: g_weaponParams = default_weaponParams;

Apply overrides after load.

9. Minimal C-Level Pseudocode
Load and apply (server)
void SV_LoadWeaponProfile(void) {
    WeaponProfile profile = WeaponProfile_Default();          // compiled defaults
    WeaponProfileOverrides ov = ParseJsonProfileFile(path);   // data-only
    if (!ValidateOverrides(&ov)) {
        Com_Printf("Weapon profile invalid, using defaults\n");
        return;
    }

    ApplyOverrides(&profile, &ov);                            // clamp inside apply
    g_runtimeProfile = profile;

    g_weapon_checksum = ComputeChecksum(&profile);
    SV_SetServerinfo("sv_weapon_checksum", g_weapon_checksum_str);

    if (svs.clients) {
        SV_BroadcastWeaponProfile(&profile, g_weapon_checksum);
    }
}

Client receive and apply
void CL_ReceiveWeaponProfile(const WeaponProfileNetMsg* msg) {
    WeaponProfile profile = WeaponProfile_Default();
    ApplyNetOverrides(&profile, msg);            // server authoritative
    g_runtimeProfile = profile;
    g_weapon_checksum = msg->checksum;
}

10. Developer Experience Features (Optional but Valuable)
10.1 Live diff output

When reloading, print:

changed knobs only, old -> new

10.2 “Dev overlay”

HUD debug toggle:

show current weapon key knobs (damage, rate, spread, ADS mult)

10.3 Profile chaining

Allow:

default.json + local_override.json layering in SP

Server can layer default then server_override for quick tweaks

Rule:

Apply in order, later wins.

11. Recommended Implementation Steps

Define runtime tables for weapon params and ammo caps (if not already).

Implement JSON parser for a restricted schema (or embed a small JSON lib).

Implement validation + clamps.

Implement apply step (defaults + overrides).

Implement checksum computation.

Implement server-to-client replication (Option A compact override list).

Add console commands:

sv_weapon_profile <name>

sv_weapon_reload

weapon_dump_profile (prints effective values)

Confirm determinism: client and server weapon behavior matches exactly after sync.

12. Security Notes (Practical)

Do not execute Lua, Python, or arbitrary expression languages in multiplayer.

Keep it data-only and server-authoritative.

Reject unknown keys to prevent silent bugs.

Clamp all numeric values.
