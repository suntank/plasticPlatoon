# Plastic Platoon asset sources and releases

The source tree contains the project's runtime assets, editable artwork and
checked original conversion inputs. The project needs no Quake II PAKs, stock
palette, historical Git objects or home-directory assets. Original asset terms
and the owner's declaration are in [ASSET-LICENSE.md](../../ASSET-LICENSE.md).

## Build a playable release

```sh
make -j4 all
./release/play-portable.sh
```

The asset target uses standard-library Python and Pillow generators for original
branding, palette/font/UI, provisional support sounds, props and color variants,
then creates
`release/baseq2/plastic-platoon.pk3`. It stages every `operation-*.pk3` mission,
the launcher, notices and an identical loose `tuning/default.json` needed by the
game module. Personal configs and saves are never packaging inputs.

To update the canonical source pack after editing runtime files:

```sh
python3 tools/assets/build_overlay.py --output baseq2/plastic-platoon.pk3
python3 tools/assets/build_overlay.py --verify --output baseq2/plastic-platoon.pk3
python3 tools/assets/build_overlay.py --verify
```

Archive manifests record every entry's size/hash. MD2 skin and SP2 image
references must resolve within the pack. Legacy male/grunt media has no exception
and is excluded from both the source tree and its conversion inputs.

## Reproduce models and textures

The M16 is an original simple-shape replacement, with first-person mitten
hands and model-based ADS. Its current budgets are 800 first-person triangles
including arms/hands, and 256 triangles for pickup/player/enemy versions.
See [the M16 experiment](../../doc/performance/m16-simple-shapes.md) for
rebuilding, visual review, validation and performance limits. Its dedicated
generator and manifest own these paths; the old decimation records remain
under `superseded_*` only for historical comparison.

The long beveled pistol uses 598 first-person triangles with a fitted high
mitten grip and tapered wrist, and 200 for each world/held version. It shares
the M16's molded-plastic palette and hand style. It uses actual
model sights in single-player and split-screen. See [the pistol notes](../../doc/performance/pistol-simple-shapes.md).

The pump shotgun uses 752 first-person triangles including the M16-style
molded hands, and 300 triangles in each world/held version, with actual model
sights. Its support hand follows the sliding fore-end through a complete pump
cycle after each shot. First-person, pickup, player-held and
enemy-held versions share the new design. See [the shotgun notes](../../doc/performance/shotgun-simple-shapes.md).

The double-barrel shotgun uses 748 first-person triangles with M16-style
hands, and 296 triangles for its pickup and all player-held poses. Its original
twin-barrel design uses actual model sights in single-player and split-screen. See
[the double-barrel shotgun notes](../../doc/performance/sshotgun-simple-shapes.md).

The M60 uses 816 first-person triangles including M16-style molded mittens,
and 380 triangles for each world/held version, with actual model sights in
single-player and split-screen. Its first-person,
pickup, player-held and normal/tall enemy-held versions share the authored
design. See [the M60 notes](../../doc/performance/m60-simple-shapes.md).

The grenade launcher uses 712 first-person triangles including molded hands,
and 284 triangles for its pickup and player-held versions, with actual model
sights. See [the grenade-launcher notes](../../doc/performance/glauncher-simple-shapes.md).

The rocket launcher uses 684 first-person triangles with molded mittens,
and 256 triangles in each world/held version, with actual model sights.
First-person, world pickup, player-held and normal/tall enemy attachments
share the full tube and rear flare. GL1, GL3 and software alias rendering use
a close near clipping plane only for weapon models, keeping the complete tube
visible through aiming and recoil. See
[the rocket-launcher notes](../../doc/performance/rlauncher-simple-shapes.md).

The sniper rifle uses 920 first-person triangles including molded mitten
hands, and 492 triangles for pickup/player-held versions, with an open modeled
scope. First-person, pickup and all player-held versions share
the design, and aiming raises the actual scope into view. See
[the sniper notes](../../doc/performance/sniper-simple-shapes.md).

The M1 Flamethrower uses 804 first-person triangles with mitten hands and a
hose, and 648 triangles for the complete pickup/player-held assembly. Twin
tanks follow the soldier's back independently from the wand, and an authored
hose bends between them. Aiming raises the actual model. See
[the flamethrower notes](../../doc/performance/flamethrower-simple-shapes.md).

The Mortar Cannon uses 740 first-person triangles including mitten hands,
328 for the deployed pickup and 312 for the carried player version. Its wide
tube, round baseplate and two-leg bipod remain visible across these roles;
aiming raises the actual model. See
[the mortar notes](../../doc/performance/mortar-simple-shapes.md).

Seven ammunition pickups are authored as simple green labeled boxes, compact
grenades, launcher rounds, rockets, flame-fuel tanks and sniper rounds. Their
models, atlases and three existing ammo LOD siblings are owned by the dedicated
ammo generator. See [the ammo notes](../../doc/performance/ammo-simple-shapes.md).

The flying rocket, armed hand grenade and shared grenade-launcher/mortar round
also use the authored ammo style. Dedicated projectile atlases and narrowly
synchronized mission copies keep the same models visible in every operation.
See [the projectile notes](../../doc/performance/projectiles-simple-shapes.md).

Five health pickups use authored medical shapes: an injector, bandage bundle,
medkit, mega-health canister and adrenaline booster. Their quantity/BOOST marks
are painted on the modeled surfaces. See
[the health notes](../../doc/performance/health-simple-shapes.md).

The armor pickups are an open wrist guard, paired boots, hollow helmet and
plate-carrier vest, using 76, 248, 168 and 212 triangles respectively. The
existing shard/jacket/combat/body classes keep their gameplay rules. See
[the armor notes](../../doc/performance/armor-simple-shapes.md).

The friendly green dropship uses a dedicated 656-triangle transport body and
76-triangle main rotor, retaining the original large mission silhouette and
existing rotor attachment. The shared legacy enemy helicopter stays intact.
See [the dropship notes](../../doc/performance/dropship-simple-shapes.md).

Install the tested conversion dependencies separately from the game build:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r tools/assets/requirements.txt
```

`platoon.json` pins `sources/platoon-originals.pk3`, which contains 146 authorized
original model, texture and sprite inputs. `platoon-originals.json` records its
contents. Corrected pickup originals are retained in `sources/pickups-local.pk3`.
`pickup-manifest.json`, `pickups.json` and `platoon-manifest.json` identify input
and output hashes, geometry/animation checks and conversion settings. No source
reader falls back to Git history or an installed game.

```sh
.venv/bin/python tools/assets/md2_assets.py verify
.venv/bin/python tools/assets/build_platoon.py verify
.venv/bin/python tests/assets/test_md2_assets.py
.venv/bin/python tests/assets/test_md2_animation.py
python3 tests/assets/test_source_archives.py
```

All original decimated pickup pairs now have dedicated authored owners. The
retired pickup inventory has no active conversion outputs; its pinned archive
and historical records remain available for provenance and compatibility
atlases. Rebuild the remaining legacy assets and all authored families with:

```sh
.venv/bin/python tools/assets/build_platoon.py build --write --review
```

The legacy model manifest covers 15 custom MD2s and 42 PNGs; authored weapons
have separate `m16-manifest.json`, `pistol-manifest.json`,
`shotgun-manifest.json`, `sshotgun-manifest.json`, `m60-manifest.json`,
`glauncher-manifest.json`, `rlauncher-manifest.json`, `sniper-manifest.json`,
`flamethrower-manifest.json` and `mortar-manifest.json` inventories.
Authored ammo, health, armor and flying projectiles have separate
`ammo-manifest.json`, `health-manifest.json`, `armor-manifest.json` and
`projectiles-manifest.json` inventories. The original shared rocket atlas
remains a legacy compatibility output in mission archives; the rocket pickup
uses `skin_ammo.png`, and the flying rocket has its own object atlas.
Independent procedural vehicle builders reproduce the tan tank and attack
helicopter and the green friendly dropship (`dropship-manifest.json`); enemy
M60 and rocket attachments come from the respective authored weapon generators:

```sh
.venv/bin/python tools/assets/build_heavy_tank.py --verify
.venv/bin/python tools/assets/build_helicopter.py --verify
.venv/bin/python tools/assets/build_dropship.py --verify
python3 -S tools/assets/verify_dropship_runtime.py
python3 -S tools/assets/build_dropship_overlays.py --verify
.venv/bin/python tools/assets/build_heavy_gunner.py --verify
.venv/bin/python tools/assets/build_heavy_gunner.py --weapon rocket --verify
.venv/bin/python tools/assets/build_ant.py --verify
.venv/bin/python tools/assets/build_spider.py --verify
.venv/bin/python tools/assets/build_insect_gibs.py --verify
```

The ant and spider models, animation frames, skins and species-specific gib
models are original procedural assets generated by those scripts. Run the
scripts without `--verify` to regenerate them; the ant and spider builders also
accept `--review` for a decoded animation review sheet.

The dedicated friendly dropship media are also appended to the existing
Endline and Sandstorm preview archives by `build_dropship_overlays.py`.
It preserves all 91 existing Endline members and the same 55 immutable
Sandstorm map/material/compatibility members. The booster and dropship have
explicit, registered peer exclusions in Sandstorm: each archive gate checks
its own exact payload, and both gates together check every authored payload.
Neither sync invokes a map packager. Future mission packagers collect the
new transport's model/skin dependencies without changing their map selection
rules. Continue to avoid old Sandstorm packaging defaults when preserving the
newer edited loose map.

Original recordings are retained in `sources/player-sounds.zip`. Soldier sound
conversion has an independent hash manifest and verifier. The support-sound
manifest identifies synthesized placeholders separately from those recordings.
The six supplied ElevenLabs soldier clips and reproducible mono conversions are
recorded in `enemy-sounds-manifest.json`; `import_enemy_sounds.py --verify` checks
them during both Make and CMake asset builds. See `SOLDIER-SOUNDS.md`.
Eight additional alert takes, their MP3 exports and decoded WAV sources are
recorded in `soldier-callouts-manifest.json`; `import_soldier_callouts.py --verify`
checks them during both build systems without needing an MP3 decoder.

## Distant pickup models

Five common pickups have additive `lod1.md2` siblings. All five are now
byte-identical to their authored close-up models, retaining the same shapes
and markings at a distance. Current budgets are:

| Pickup | Close triangles | Distant triangles |
| --- | ---: | ---: |
| Bullet ammo | 116 | 116 |
| Shell ammo | 116 | 116 |
| Grenade ammo | 148 | 148 |
| Armor shard | 76 | 76 |
| Small health | 128 | 128 |

`r_pickup_lod 1` enables these models by default in GL1/GLES1, GL3/GLES3 and the
software renderer. Each camera selects independently: the pickup must be at
least 256 units away and its canonical bounding sphere must project to no more
than 12 pixels in diameter. Larger displays and zoom retain the close model
until it is sufficiently small. Animated frames, renderer-origin interpolation
and special rendering effects keep the original mesh. Missing LOD files also
fall back to the original.
`r_pickup_lod 0` disables substitution for comparisons.

The configuration and output hashes are in `pickup-lods.json` and
`pickup-lods-manifest.json`. The three ammo siblings, injector and wrist guard
come from `build_ammo.py`, `build_health.py` and `build_armor.py`, including
identical markings and quantization. After intentional pickup reauthoring,
`--refresh-authored` adopts only independently verified owner hash pins and
metadata. The full asset builder performs that refresh after generating all
three owners. The original source archives remain hash-pinned; no active QEM
LOD recipe remains, so full LOD generation no longer needs PyMeshLab.
Generation and checks:

```sh
python3 tools/assets/build_ammo.py
python3 tools/assets/build_health.py
python3 tools/assets/build_armor.py
python3 -S tools/assets/build_pickup_lods.py --refresh-authored
python3 -S tools/assets/build_pickup_lods.py --verify
# Optional combined regeneration/review uses NumPy and Pillow:
.venv/bin/python tools/assets/build_pickup_lods.py --review
sh tests/renderers/run_pickup_lod_tests.sh
python3 tools/performance/capture_pickup_lod.py
```

Normal Make/CMake asset builds verify the checked-in LODs before packaging;
they do not require conversion dependencies. The runtime capture checks mixed
near/far cameras, expected triangle counts, renderer restart, map reload,
toggle restoration and absent-LOD fallback. Host captures verify behavior and
appearance; Pi performance must be measured on the device.

## Player colors and enemy variants

`build_color_variants.py` generates separate PNG skins for red enemies, their
held weapons and debris, plus player bodies, every first-person weapon, linked
third-person weapon and ADS overlay in each selectable soldier color. It
discovers colors from `players/soldier/<color>.png` skins with matching selection icons; missing
or unsupported held-weapon variants fall back to green at runtime. Per-entity
skin overrides keep each player's weapon color independent and leave unheld
pickups and existing player debris unchanged.

Player body atlases use `players/soldier/colors/body_<color>.png`, shared by the
unchanged `tris.md2` and `tris_pistol.md2` models. They apply the weapon pigment
hue/saturation and brightness curve to the original green body atlas, retaining
its shading and texture detail. This also normalizes the brighter original
pink, skin and white bodies to their held weapons; gray and white remain
achromatic. The body mask includes deep plastic shadows and preserves neutral
details and alpha. Canonical skin images, menu icons and player debris remain
unchanged. Missing generated body art retains the selected canonical body;
normal missing-skin handling still chooses green.

Generated model skins use `<model-directory>/colors/<model-stem>_<color>.png`;
additional enemy skin indices use `_<color>_<index>.png`. ADS art uses
`pics/colors/ads_<weapon>_<color>.png`. Taller soldier models share the canonical
soldier color paths. `color-variants-manifest.json` records source/model hashes,
palette values, material-mask rules and hashes, output dimensions and hashes,
and coverage of enemy models in the bundled operation archives. Enemy plastic
uses the same saturated red pigment on bodies, parts and held weapons while
retaining the source brightness and shading. Material masks preserve alpha and
contrasting eyes, glass, optics, metal and dark mechanical details. Original
model and texture inputs remain unchanged.

`build_soldier_height.py` reads `soldier-height.json` (currently scale `1.2`, a
20% increase, anchored at foot Z `-24`) and writes six enemy body/held-weapon MD2s
under `models/monsters/soldier/tall/`. Only each frame's scale and translation
change; packed vertices, normals, skins, UVs, triangles and frame names remain
exact. `soldier-height-manifest.json` pins the inputs/outputs and generated
`src/common/header/soldier_dimensions.h` keeps gameplay dimensions aligned.
Make and CMake regenerate height models before color variants and packaging.

Rebuild and verify these derived assets with Python and Pillow:

```sh
python3 tools/assets/build_soldier_height.py
python3 tools/assets/build_color_variants.py
python3 tools/assets/build_soldier_height.py --verify
python3 tools/assets/build_color_variants.py --verify --review
python3 tests/assets/test_soldier_height.py
python3 tests/assets/test_color_variants.py
```

Color verification checks hashes, dimensions, alpha and exact preservation of
pixels outside each plastic mask. Review sheets are written to
`build/color-variants/red-material-review.png` and `player-body-review.png`.
The manifest also pins both body model layouts and their shared generated
atlases. Body recipes have a separate cache key, so body changes retain identical
weapon/enemy/ADS bytes. Unchanged source/palette/recipe inputs reuse identical
generated PNG bytes; run the overlay verifier above after packaging to check
that every variant ships.

## Maps, palette and branding

Editable `.map`, `.blend`, PSD and material source images remain in this source
release. The separate private pre-cleanup backup also preserves editor backups
and removed diagnostic files. Runtime downloads do not need editable sources.

All map material generators use `tools/maps/platoon_palette.py`, which imports
the original palette defined in `build_bootstrap.py`. Indexed WALs were migrated
from their truecolor companions while retaining headers, flags, animation links,
BSP geometry and truecolor image bytes. Verify or update indexed outputs with:

```sh
.venv/bin/python tools/maps/reindex_materials.py
# After changing the authored truecolor textures:
.venv/bin/python tools/maps/reindex_materials.py --write
```

`tools/maps/material-palette-manifest.json` records 195 loose/archive WAL
representations across the source textures and seven mission packages.
`build_branding.py --verify` checks the original SDL, PNG and Windows icons.
The macOS workflow packages source-built binaries rather than an old app bundle.

## Public-source and runtime verification

```sh
python3 tools/assets/audit_public_source.py --history --strict
python3 tools/assets/audit_standalone.py --strict --output /tmp/platoon-runtime-audit.json
python3 tools/assets/smoke_standalone.py --renderer gl3 --renderer gl1 --renderer soft
```

The public-source guard checks tracked files, archive members and all Git blobs,
including unreachable objects, for known removed media, prohibited paths and
private backups. It does not independently establish ownership. Retain the GPL
and component notices; the source release relies on the recorded owner declaration.

See [the cleanup record](STANDALONE.md) for backups, test results and remaining
presentation/platform limitations. Historical offline model comparisons are
retained because they show project artwork; stock-map/runtime screenshots were
removed from the public source.

## Ant and spider audio

See [insect sound sources and rebuild checks](INSECT-SOUNDS.md). The eighteen
approved effects are reproduced and checked by `import_insect_sounds.py`;
both build systems verify them before packaging. Spider sight remains silent.

## Optional Pi actor models

The Pi profile uses a separate model-only overlay for remaining legacy actor
and view models. Authored weapon replacements come from the main package.
Rebuild the accepted Pi topology with the pinned asset virtual environment:

```sh
.venv/bin/python tools/assets/build_pi_actor_models.py
.venv/bin/python tools/assets/build_pi_actor_models.py --verify
```

The output is `build/assets/pi-actor-models.pkz`; install it explicitly in the
Pi package's `baseq2/`. It is deliberately outside the normal asset build.
The current pack replaces only four body models. All twenty-six weapon entries
from the original recipe are omitted; the main package supplies the ten authored
guns, including hands and model ADS.
Rebuild the Pi pack after integrating replacements; an older installed PKZ can
override the main PK3.
Player bodies use 1,012/994 triangles instead of
1,766/1,768; normal and taller soldier bodies use 1,028 instead of 1,784.
The M16 uses 256 triangles when carried and 800 in first person, including
hands. The authored sniper rifle also comes from the main package, including
its held model, which the legacy Pi recipe did not cover.
Yamagi loads PKZ archives after PK3 archives, placing them earlier in the search
path. A `zz` prefix alone does not guarantee precedence among this engine's
unsorted PK3 files. Remove the PKZ to restore the original models.

`pi-actor-models.json` records the reviewed topology, original vertex indices,
UVs, and exact source/output hashes. Animated models retain every original
frame, name, skin reference, quantization lattice and surviving packed vertex
and normal byte. The builder replays the accepted topology on the original
frames and requires byte-exact reproduction. It does not rerun an unconstrained
decimator. The embedded manifest records triangle counts and quality evidence.

The original recipe's first-person cleanup retained vertex/frame/skin/ST
bytes and surviving triangle order. Its historical `pi-firstperson-proof.json`
certificate covers default zero `gun_x/y/z` with `r_cull 1`, normal recoil,
bob, lowering, mirrored hands and FOV changes within a 29-unit bound. Those
legacy gun entries are now omitted in favor of the authored main-package
models and their dedicated validation. The animated hand grenade remains
outside the overlay. No texture, renderer, game logic, level or map source is
in the pack.
