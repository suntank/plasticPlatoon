# Authored soldier and insect fragments

All 15 body-part models now use original low-poly shapes: molded soldier arms,
boots/legs, broken limb joints, helmeted heads, a vest torso, small plastic
pieces, machine fragments and distinct ant/spider shell chunks and bent legs.
Soldier surfaces use smooth molded shading. Ant and spider legs retain their
different proportions, and their shell/wound colors keep the established atlas
layout used by the enemy color system.

The models retain their existing paths, exact local bounds/origins and static
frame identities. Head aliases remain compatible with the normal death paths,
the three map-spawned limb classes and older saves. Dedicated green player
atlases and regenerated enemy variants follow the new UVs. No death, collision,
toss/bounce, fragment-count or cleanup code was changed.

| Fragment | Previous triangles | New triangles |
| --- | ---: | ---: |
| Arm | 200 | 104 |
| Limb / bone | 262 | 52 |
| Joint / bone2 | 104 | 32 |
| Torso | 684 | 128 |
| Fastener / gear | 104 | 48 |
| Head, head2, skull (each) | 188 | 124 |
| Leg | 416 | 76 |
| Small plastic piece | 104 | 32 |
| Small machine piece | 262 | 28 |
| Ant chunk | 116 | 52 |
| Ant leg | 92 | 44 |
| Spider chunk | 116 | 64 |
| Spider leg | 92 | 44 |

Total: 1,076 triangles instead of 3,116, a 65.5% reduction. This describes asset
budgets; target-device frame rates have not been measured.

`tools/assets/sources/body-parts-baseline.pk3` preserves all 39 previous model,
skin and player-override files. Its hash and inventory are recorded in
`body-parts-source.json`. New geometry is fitted to those archived bounds;
every fragment's frame identity is copied from its baseline. The original
soldier source archive remains intact as well.

The dedicated `body_parts` owner prevents the legacy converter from restoring
old meshes or UV layouts. The historical insect generator now delegates to
this owner. Only the three existing insect-fragment members in each of the
ant/spider test archives are synchronized; every other archive member is
protected by a content fingerprint. Normal Make/CMake builds verify all media,
sync these mission copies and regenerate color variants before packaging.

```sh
python3 tools/assets/build_body_parts.py
python3 tools/assets/build_body_parts.py --verify
python3 -S tools/assets/verify_body_parts_runtime.py
python3 tools/assets/build_body_parts_overlays.py
python3 tools/assets/build_body_parts_overlays.py --verify
python3 tests/assets/test_body_parts.py
python3 tests/assets/test_insect_gibs.py
python3 tests/assets/test_color_variants.py
python3 tools/assets/build_platoon.py verify
make -j4 all
python3 tools/performance/capture_body_parts.py --output build/body-parts-qa-gl3 --renderer gl3
```

Asset tests verify reproducible output, ownership, baseline bounds/frame names,
export budgets, GL command counts, nondegenerate quantized faces, closed directed
edges, outward normals, green player atlases and insect wound-mask exclusions.
The native gallery uses a separate portable runtime. Its static props expose
every fragment for close inspection. A private controller
then invokes native soldier, ant and spider death callbacks; the game selects
and throws the fragments normally, allowing model/count checks on actual bursts.
The player check invokes the existing player death callback and verifies the
green override on all five pieces. `--diagnostic-lighting` optionally uses the
existing private photography hook to make entity surfaces uniformly visible;
this does not modify the shipped renderer or ordinary gameplay lighting.

The normal-light native report `build/body-parts-qa-gl3-final/report.json`
passes with 19 views and all four death paths: five soldier pieces, eight ant
pieces, eleven spider pieces and five player pieces with their green overrides.
The normal build, three body-part asset tests, insect winding test and twelve
color-system tests pass. Both core packs verify 977 assets and 126 image
references and match SHA256
`7920b194098b60e2ee0345382c7eb0617b6bb9e70a1d0c2bcf862c93f05c26f1`.
Source/release insect mission archives also match, with all unmanaged members
retaining their pinned fingerprints.

The controlled-light inspection report `build/body-parts-qa-gl3-lit/report.json`
also passes all 19 views and four native death paths. Its private fullbright
entity hook exposes silhouettes, cuffs, helmet/nose/eye features, torso pouches,
machine openings, insect shell ends and bent legs for visual review. These
diagnostic views do not assess ordinary gameplay lighting or device performance.
