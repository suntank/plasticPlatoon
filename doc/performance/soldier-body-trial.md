# Official lower-poly soldier bodies

The lower-poly soldier bodies were accepted after an in-game review and are now
enabled by default. They are a conservative retopology of the original bodies,
guided by all their existing animation poses, retaining the original sculpt's
proportions and features.
Face/helmet, distal hands,
and boot vertices identified in the standing reference are protected. Surviving
vertex positions, normals, quantization and frame names are copied exactly in
every animation frame. The cloth topology and its texture interpolation change.

The option is client-side and cosmetic. Collision dimensions, animation frame
numbers, weapon attachments, player skins and enemy colors retain their normal
sources. Optional custom player models are unaffected. A missing replacement file
falls back to its standard body. The separate Pi actor profile is unchanged;
the counts below compare against standard canonical bodies, not that profile.

## Compare in game

The built-in default is `1`, selecting the official lower-poly bodies. Use
`set cl_soldier_body_test 0` to restore the originals immediately, and
`set cl_soldier_body_test 1` to return to the lower-poly bodies. No restart is
required. The setting is saved if changed; an existing saved `0` remains a
deliberate rollback choice. No personal configuration is rewritten by this change.
The historical toggle and asset paths are retained for compatibility.

| Body | Original triangles | Official triangles |
| --- | ---: | ---: |
| Enemy | 1,784 | 1,150 |
| Tall enemy | 1,784 | 1,150 |
| Player | 1,766 | 1,164 |
| Pistol player | 1,768 | 1,176 |

The reduction stops above its target when further collapses violate the anatomy,
surface area, displacement or pose-orientation constraints. It does not force
a target by accepting broken joints. Actual Raspberry Pi frame rates have not
been measured for this change.

## Backup and regeneration

`tools/assets/sources/soldier-body-baseline.pk3` contains exact copies of the
four original model files. The archive and each original are hash-pinned in
`tools/assets/soldier-body-test-source.json`. Snapshot creation refuses to
replace an existing backup. Replacement outputs live only under
`models/experimental/soldier/`; the originals are never overwritten.

```sh
python3 tools/assets/build_soldier_body_test.py
python3 -S tools/assets/verify_soldier_body_test.py
python3 tests/assets/test_soldier_body_test.py
make -j4 all
```

Normal Make/CMake builds use the standard-library verifier. Regeneration needs
NumPy. Full source builds regenerate the official bodies after the original and
height-adjusted bodies, retaining the same backup/source checks.

## Grenades

Hand grenades are ammunition and no longer appear in normal weapon cycling or
the explosive weapon-cycle menu preset. `quickgrenade` retains the equipped
firearm; the keyboard/controller defaults already use it. Existing `use Grenades`
bindings now call the same quick throw. Legacy equipped/queued grenade states
resume the last firearm (or the default pistol). An already cooking legacy
grenade finishes its existing throw before that transition. Existing held-view
assets/functions remain compatibility resources; they are not a normal selection.

## Verification scope

The asset tests compare all 1,346 stored poses across the four models, exact
protected source vertices/normals, texture coordinates, bounds and non-inverting
faces. GL strip reordering and cyclic corner rotations are accounted for.

Native A/B photography uses isolated portable runtimes and existing animation
frame indices. A private controller freezes photographic poses and provides
uniform entity lighting for inspecting faces, clothing and grips; these are
diagnostic views, not ordinary gameplay lighting or a full combat playthrough.
The shipped renderer is unchanged. Standing, running, crouching, firing and both
player grip variants are reviewed, including toggling back to the original.
Native commands check quick-throw ammunition consumption, firearm retention,
direct-use compatibility, weapon cycling and legacy equipped-grenade recovery.

The pre-promotion native reports are `build/soldier-body-qa-gl3-release/report.json` (15
views), `build/soldier-body-qa-gl1-release/report.json` and
`build/soldier-body-qa-soft-release/report.json` (7 views each). All pass and exit
zero, including selecting the actual trial models, restoring the normal body,
both player weapon grips, quick throws consuming one grenade while retaining
the gun, and recovery from the legacy equipped-grenade state. A live legacy throw also
finishes before the automatic transition, avoiding a forced detonation. The software
palette's dark texture details also occur on the original body.

The source and release core packs match SHA256
`d14bb8479ea9d28cf1f59a5d3ef30a5502d1b93113cffde6ff5b2185f9d86874`.
These diagnostics establish model selection, pose fidelity and basic input
behavior; they do not constitute a complete gameplay or device-performance
assessment.

After promotion, `build/soldier-body-qa-official-gl3/report.json` passes with a
fresh configuration and no soldier-body override: the first rendered enemy uses
the lower-poly body by default. Its seven diagnostic views also verify the
original/lower-poly switch, restoration, and both player grips. The grenade
compatibility checks pass. The native process exits zero; source and release
packs retain the matching hash above because the accepted model bytes are unchanged.
