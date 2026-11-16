# Authored health pickups

Curved surfaces and molded corner bevels now use the selective shading described
in [the health/armor normal audit](pickup-normal-smoothing.md).

Five custom health pickups share the army-man plastic palette and original
closed geometry: a +2 injector, +10 bandage bundle, +25 medkit, +100 sealed
mega-health canister and adrenaline booster marked BOOST. Medical crosses,
quantity marks and bandage ends are mapped onto real faces, with deterministic
256 by 256 RGB atlases. Each pickup uses one static model and one atlas.

Existing health gains, caps, overheal rules, booster behavior and mega-health
decay remain gameplay properties of the unchanged item functions. The models
retain their existing paths, spawn origins and item flags. Ancient Head has
no custom model or placement in the current maps; the five present custom
health assets are covered here.

## Asset budgets

| Pickup | Previous triangles | Current triangles | Reduction |
| --- | ---: | ---: | ---: |
| Injector (+2) | 800 | 128 | 84.0% |
| Bandages (+10) | 800 | 80 | 90.0% |
| Large medkit (+25) | 998 | 124 | 87.6% |
| Mega-health (+100) | 800 | 128 | 84.0% |
| Adrenaline (BOOST) | 998 | 124 | 87.6% |

Together they use 584 triangles instead of 4,396, an 86.7% reduction.
`health-manifest.json` records exact model, atlas and source hashes. The old
adrenaline fallback was byte-identical to the large-health model, so its source
frame derives explicitly from the same pinned original. Its new BOOST atlas
and model are owned independently by the health generator.

The injector's existing `lod1.md2` sibling is byte-identical to its close model.
The LOD pipeline audits authored ammo, health and armor owners separately,
adopting only verified owner hash pins during `--refresh-authored`. All five
existing LOD siblings now retain their owners' exact close-up geometry. Distance and
projection thresholds still operate independently for each camera.

## Atlas and mission isolation

Large health uses `models/items/healing/large/skin_health.png`. The old shared
`skin.png` remains byte-identical compatibility media because the Sandstorm
preview contains it. Full rebuilds preserve its corrected source from the
pinned pickup archive. Adrenaline uses its own
`models/items/adrenal/skin.png` atlas.

The preview mission also embeds the old adrenaline fallback and would shadow
the main package. `build_health_overlays.py` replaces only that MD2 and adds
its dedicated atlas. The 55 immutable map/material/compatibility members
retain their exact path, size and content hashes, including the user's edited
map/BSP and old atlas. The later friendly dropship replacement appends three
dedicated vehicle files under its own archive gate, bringing the preview to
60 members. Both gates must pass: the health gate audits its two payloads,
the dropship gate audits its three, and both preserve those same 55 immutable
members. Only fixed registered peer paths are excluded from each owner's
unchanged-member fingerprint; neither sync writes the other owner's files.

Both source validation and the complete unchanged-member fingerprint pass
before writing. Archive replacement uses the reviewed same-directory atomic
writer; repeated syncs preserve already-correct bytes and member metadata.
Unrelated mission edits cause a clear error and remain untouched. The future
Sandstorm packager reads the new model's skin dependencies and retains the
compatibility atlas. Its older map defaults are not used by the sync helper.

## Rebuild and verify

Reauthoring needs NumPy/Pillow. Normal Make/CMake verification, LOD metadata
refresh and mission sync work with only the Python standard library. A full
asset rebuild generates health before refreshing LOD metadata and syncing the
preview mission. Armor models and all other authored assets retain their
existing owners.

```sh
python3 tools/assets/build_health.py
python3 -S tools/assets/build_pickup_lods.py --refresh-authored
python3 tools/assets/build_health_overlays.py
python3 -S tools/assets/verify_health_runtime.py
python3 -S tools/assets/build_health_overlays.py --verify
python3 -S tools/assets/build_pickup_lods.py --verify
make -j4 all
python3 tools/assets/build_overlay.py --output baseq2/plastic-platoon.pk3

python3 tests/assets/test_health.py
python3 tests/assets/test_health_overlays.py
python3 tests/assets/test_pickup_lods.py
python3 tests/assets/test_md2_assets.py
sh tests/health/run_tests.sh
sh tests/renderers/run_pickup_lod_tests.sh
python3 tools/assets/build_platoon.py verify
python3 tools/assets/md2_assets.py verify
python3 tools/assets/build_overlay.py --verify --output baseq2/plastic-platoon.pk3
```

The focused overlay fixtures check edited map/BSP preservation, old atlas and
member metadata identity, idempotence, stale-source rejection, safe refusal of
unrelated edits, managed-media repair and future packager atlas resolution.
Host captures establish appearance and behavior; Raspberry Pi frame rates
require a controlled device comparison.

## Native visual and pickup review

The isolated gallery photographs each real pickup from the front, opposite
side, end and above at 1280 by 720. Camera readback verifies the requested
downward views; booster views account for its normal rotation. Read-only
health/max-health snapshots then check native touches, including boundary
cases. Starting health is set through the existing cheat command. Each
additional scenario uses a full map reset so coop's saved collected-item state
cannot remove its test pickup.

```sh
python3 tools/performance/capture_health.py --prepare-only \
  --q2tool /path/to/q2tool --output build/health-review-map
python3 tools/performance/capture_health.py --renderer gl3 \
  --map-dir build/health-review-map/maps --output build/health-qa-gl3-verified
```

Repeat with `--renderer gl1` and `--renderer soft`, using fresh output
directories. `--targets` selects individual classes; `--gallery-only` skips
the extra boundary scenarios for a preliminary shape review. Final captures
use the full default behavior checks.

| Renderer | Final directory | Images |
| --- | --- | ---: |
| GL1 | `build/health-qa-gl1-verified` | 20 |
| GL3 | `build/health-qa-gl3-verified` | 20 |
| Software | `build/health-qa-soft-verified` | 20 |

All three reports pass and complete with return code zero, using package
SHA256 `fbcf642eb7f26383b35734af0e4c420acad94ac4a8a1fee1f80a97c02674d8c7`.
Inspection confirms distinct injector, bandage rolls, handled medkit,
mega-health canister and BOOST case silhouettes. The crosses, quantities and
BOOST word are upright and readable. Software retains its darker palette and
faceting with the same recognizable markings.

| Pickup | Native result from 50 health | Additional verified behavior |
| --- | --- | --- |
| Injector | 52 | 100 becomes 102; normal maximum stays 100 |
| Bandages | 60 | 95 caps at 100; at 100 the item remains unconsumed |
| Medkit | 75 | 95 caps at 100; at 100 the item remains unconsumed |
| Mega-health | 150 | 100 becomes 200, then decays to 199 after its native delay |
| BOOST | 101 | Maximum increases from 100 to 101 and current health refills to it |

The booster also succeeds when starting at full health. Mega-health is
verified hidden and non-solid after pickup, retaining its native delayed
decay entity rather than being mistaken for a freed item. These scenarios use
the ordinary non-deathmatch item rules.

Stimpack LOD reports under `build/health-stimpack-lod-gl1-final` and
`build/health-stimpack-lod-gl3-final` pass all six numeric checks: near detail,
expected far delta, renderer restart, map reload, disabling LOD and missing
sibling fallback. Both meshes contain 128 triangles, giving the expected zero
delta while keeping the new injector in every view. The corresponding
`build/health-stimpack-lod-soft-final` report passes visual and camera smoke
checks; software exposes no model-triangle counters, so no numeric reduction
is claimed for that renderer.
