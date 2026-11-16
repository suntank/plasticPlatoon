# Sandkeep armored boss helicopter

`monster_boss2` now uses dedicated `models/monsters/plastic_boss/` media: a
narrow armored red cockpit/fuselage, large twin engines, heavy cannon fairings,
four recessed rocket tubes, short armored wings and a six-blade linked rotor.
Pale double chevrons distinguish the boss. The green transport and smaller
attack helicopter retain their own models and behaviors. The original shared
boss2 files remain untouched as compatibility resources.

The body uses 892 triangles and the rotor 100, versus 2,580 and 411 previously
(992 versus 2,991 combined, 66.8% fewer). Both use one static geometry frame;
the client explicitly renders pose zero while native AI frame indices continue
to drive attacks and pain. This avoids invalid-frame warnings in software.
The rotor retains the original axle/socket transform and client spin. Cannon
bores end at `[60, ±15, 50]`; the four rocket mouths are at `[0, ±40/45, 45]`,
matching the shared muzzle-offset table. New body bounds stay within
`[-114,-50,36]` to `[68,50,96]`; the original gameplay collision box is retained.

Both body skins are red, with a darker scratched damaged version below half
health. The regular enemy-color generator produces both body overrides and a
rotor override; cockpit glazing, black bores/vents, neutral machinery and pale
markings retain their material contrast. All image names fit the engine's
64-byte path limit. Dedicated green dropship files and legacy enemy files are
still verified unchanged by the dropship gate.

## Combat

Fresh bosses default to 4,000 health (regular attack helicopter: 500), twice the
previous boss health. Explicit map health values are respected. Twin cannons
deal 8 damage per bullet instead of 6; rockets deal 65 damage at speed 650
instead of 50 at speed 500. The old attack wind-up is retained. At half health
the rocket animation adds another four-rocket salvo six ticks after the first,
followed by a 1.2-second recovery. Machinegun attacks have at most three short
bursts before their recovery, and phase two chooses rockets more frequently.

Hits below 25 damage still hurt and update damaged paint but do not interrupt
the attack. Larger hits retain the existing pain response/cooldown. Shots
recheck a live visible target and trace from their actual muzzle to the target;
blocked bores, a lost target or targets within 280 horizontal units suppress
rocket fire. Damage, cadence, wind-up and cover behavior are verified in the
production game harness. Final difficulty balance still requires playtesting.

The existing death-target sequence opens the objective route. The crashing
boss loses its flying flag and falls with normal toss physics before its
explosion burst and cleanup. Crash callbacks are registered for saving. Loading
an existing boss refreshes only model indices, preserving health, AI/animation,
fight progress and a rotor already detached during the terminal crash burst.

## Build and verification

```sh
python3 tools/assets/build_boss_helicopter.py
python3 tests/assets/test_boss_helicopter.py
python3 -S tools/assets/verify_boss_helicopter_runtime.py
tests/helicopter/run_tests.sh
tests/sandstorm/run_tests.sh
tests/performance/run_effects_tests.sh
make -j4 all
python3 tools/performance/capture_boss_helicopter.py --output build/boss-helicopter-qa-gl3 --renderer gl3
```

The authored-owner entry excludes these assets from legacy conversion. Both
Make and CMake verify them. Asset tests cover deterministic outputs, skins,
path limits, closed components, normals/winding, quantization, budgets, bounds,
muzzle anchors and pigment exclusions. Game tests cover both phases, timed
follow-up, bounded gun bursts, cover/target/range safety, pain responses, old
save media migration, saves during attack/crash, death objectives and cleanup.
The regular helicopter suite passes too. Render regressions compare all three
legacy/dropship/boss body/rotor pairs in four views on GL1, GL3 and software.

`build/boss-helicopter-qa-gl3-final/report.json` passes eight native views, exact
registered red body/rotor/damaged skins, spinning rotor, wind-up, eight observed
phase-two rockets and crash cleanup. It also loads the unchanged packaged
Sandkeep BSP, wakes its actual boss and verifies 4,000 health, the new rendered
models and its `boss_down` death-target wiring. The mission scene bypasses
earlier objective gates for inspection; it is not a complete level playthrough.
The gallery uses native entity lighting; the synthetic room is very brightly
lit. `build/boss-helicopter-mesh-review.png` is an offline actual-MD2 review,
not an in-game lighting capture.

`build/boss-helicopter-qa-gl1-final/report.json` and
`build/boss-helicopter-qa-soft-final/report.json` pass four-view smoke checks,
including both skin indices, rotor spin, eight rockets and crash cleanup. All
three final captures exit zero and explicitly verify pose-zero presentation;
their console logs contain no invalid-frame warnings.

Source/release core packages match SHA256
`c075b911799026bcdc114f6decc8dc1b8bc65a84dc26ef426efc2cd61f1c0a58`;
both verify 984 assets and 129 image references. No Sandkeep map or mission
archive was regenerated or edited.
