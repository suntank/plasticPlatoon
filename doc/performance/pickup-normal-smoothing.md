# Health and armor normal audit

All five health and four armor pickups were reviewed for unwanted faceted
lighting. The revision changes shading while preserving every triangle corner
position, UV, texture, frame identity, bound and silhouette. There are still
584 health triangles and 704 armor triangles. Vertices shared between curved
walls and flat caps are split where separate normals are required; no triangles
are added. No gameplay or renderer code changes are involved.

| Pickup | Smoothing applied | Crisp surfaces retained |
| --- | --- | --- |
| Stimpack injector | Needle, tapered nozzle, stem and thumb-pad sides; barrel's beveled corners | Flat caps, flange and printed barrel faces |
| Bandage bundle | Cylindrical cloth-roll sides | Flat printed roll ends, strap and medical patch |
| Large medkit | Vertical molded corner bevels on body and lid | Flat case faces, labels, seams, latches and open handle |
| Adrenaline kit | Same molded corner bevels | Flat faces, markings and hardware |
| Mega health | Canister corner bevels and round lid/base walls | Printed panels, cap faces and handle |
| Armor shard | Outer and inner wrist-guard walls | Rim faces and guard plate |
| Jacket armor | Boot shafts inside/out, rounded foot uppers and sole walls | Cuff rims, sole cap planes and shin plates |
| Combat armor | Continuous outer dome and inner helmet shell, including crown | Open lip, badge and chin strap |
| Body armor | None needed; model bytes unchanged | Flat vest plates, pouches and straps |

`pickup_normals.py` supplies local shading islands for only these two owners.
Coincident corners within each curved island use angle-weighted face normals,
so UV seams and triangle fans do not introduce lighting seams. Interior/exterior
walls and rims stay separate. Medical case chamfers interpolate between the
neighboring flat-panel normals: the chamfer looks rounded without making the
printed face appear bowed. The shared weapon/vehicle geometry library is unchanged.

The build metadata includes the new shading helper. Both generators reproduce
their new exports. The injector and wrist-guard LODs are identical to their
close models, and their owner metadata was refreshed. The narrow health-overlay
sync updates the existing Sandstorm booster model; all other archive members
retain their pinned content fingerprints.

## Verification

`build/pickup-normal-audit.json` compares decoded pre/post exports for all nine
models: triangle positions and UVs are exact, textures/frame names/skin paths
are unchanged, flat medical print normals are unchanged, the vest bytes are
identical, and helmet normals agree across duplicated UV corners. Eight models
receive shading changes; the flat vest needs none.

The existing health and armor asset suites pass ten tests each. The ten pickup
LOD tests and five mission-overlay tests pass, covering closure, winding,
nondegeneracy, shape/scale, real openings, label orientation, source ownership
and deterministic outputs. The standard-library gates and full legacy/owner
verification also pass.

Native GL3 gallery reports `build/health-smooth-qa-gl3/report.json` and
`build/armor-smooth-qa-gl3/report.json` pass, each with twenty views, ordinary
pickup gains and a clean engine exit. Helmet dome/interior, cuffs, boot uppers,
rolls, injector and canister details were visually inspected. Equal-camera,
equal-light offline MD2 comparisons are saved as
`build/pickup-smoothing-{helmet,boots,bandages}-{before,after}.png`; these show
shading differences without changing the geometry or presentation.

Source/release core packages verify 984 assets and 129 image references and
match SHA256 `b1407f1d4d34d4251e2286fe40da457e3925dc9bae97ea68fcb20c4bbc3dc42f`.

```sh
python3 tools/assets/build_health.py
python3 tools/assets/build_armor.py
python3 -S tools/assets/build_pickup_lods.py --refresh-authored
python3 tools/assets/build_health_overlays.py
python3 tests/assets/test_health.py
python3 tests/assets/test_armor.py
python3 tests/assets/test_pickup_lods.py
python3 tests/assets/test_health_overlays.py
python3 tools/assets/build_platoon.py verify
python3 tools/assets/build_overlay.py
```
