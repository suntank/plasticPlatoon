# ADS viewmodel recoil audit

Nine authored weapons now use a short straight-back visual kick while aiming.
The M16 is explicitly excluded, and all hip-fire motion is preserved. Damage,
spread, firing cadence, gameplay camera kick, zoom/FOV, ADS alignment and weapon
models remain unchanged. The shotgun's forty pump/hand frames remain active.

The previous single-view path applied full hip-fire pushback, upward lift and
pitch to the aimed model. Heavy weapons could retreat seven to twelve model
units while tipping the breech/receiver into the eye. The split-screen path
had separate legacy recoil amplitudes but the same presentation problem.

| Weapon | Previous primary full-strength pushback | New full-ADS travel cap |
| --- | ---: | ---: |
| Pistol | 4.25 | 0.35 |
| Shotgun | 7.00 | 0.60 |
| Double barrel | 9.00 | 0.70 |
| M60 | 1.95 | 0.25 |
| Grenade launcher | 8.00 | 0.55 |
| Rocket launcher | 5.40 | 0.50 |
| Sniper rifle | 7.00 | 0.30 |
| Flamethrower | 0.24 | 0.08 |
| Mortar | 12.00 | 0.65 |

These are model-space configuration limits, before per-frame decay and
smoothing; observed kicks can be smaller. At full ADS, added procedural pitch,
yaw, roll, lateral movement and lift are zero. The base sight alignment and
any movement of the camera itself are retained.

`PP_ModelADSConstrainMotion` runs after the existing procedural smoothing in
both `CL_AddViewWeapon` and `SS_AddSlotViewWeapon`. Applying it there prevents
a prior hip-fire kick from lingering in the fully aimed pose. A partial aim
blend smoothly reduces the old motion. Even a raising weapon or unusually
large smoothing tail blends continuously at ADS entry. Zero aim blend and
the M16 return immediately without changing input values. A zero M16 limit
is an exclusion marker rather than a request to eliminate its recoil.

## Verification

`tests/input/run_ads_recoil_tests.sh` verifies all nine caps and straight-back
movement across multiple camera bases, zero added aimed angles/lift, large
smoothing tails, continuous entry, and bit-identical hip-fire/M16 exclusions.
All ten existing model-ADS suites pass, including sight/muzzle alignment,
independent slots, transitions and pump frames. Production shared-effect
regressions pass with the extended ADS configuration.

The private observer in `color_variants_runtime.c`, enabled only for this
capture tool, records actual weapon entities submitted to each viewport's
renderer. `capture_ads_recoil.py` drives normal attacks in an isolated portable
runtime, observes real muzzle events/ammunition use, and compares aimed firing
against aimed idle in camera space. The renderer's fixed world-space 1/16-unit
BSP-plane camera bias is removed from this analysis. The unlimited pistol and
the mortar's separate ammo pool are checked through actual muzzle events.

The native audit covers all nine weapons and an unchanged M16 control in one
view and all four split-screen views. Pump frames 9–18 are observed while firing
in ADS. Screenshots cover aimed idle and firing. Fast-recovering weapons can
have zero residual kick at the offscreen host's frame rate; the independent
peak/tail tests verify their configured limits as well. These captures are
functional/visual checks rather than device-performance measurements.

Final release-binary captures passed with clean exits in
`build/ads-recoil-qa-single-release/report.json` (ten weapons, one view) and
`build/ads-recoil-qa-four-final-release/report.json` (ten weapons, four views).
Both include the M16 control. The source/release core asset pack remains
`b1407f1d4d34d4251e2286fe40da457e3925dc9bae97ea68fcb20c4bbc3dc42f`;
this change adjusts presentation code rather than weapon assets.

```sh
tests/input/run_ads_recoil_tests.sh
tests/performance/run_effects_tests.sh
make -j4 all
python3 tools/performance/capture_ads_recoil.py --output build/ads-recoil-single
python3 tools/performance/capture_ads_recoil.py --output build/ads-recoil-four --four
```
