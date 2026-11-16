# Authored green barrels

The shared explosive barrel now uses an original eight-sided green drum in the
same molded plastic style as the updated equipment. Its silhouette has two
raised rolling hoops, a protective top rim, a recessed lid and two hexagonal
bung caps. A small cream fuel stencil and flame mark appear on opposite faces.
The label and surface colors use a single 256 by 256 RGB atlas, without external
artwork or installed fonts.

The drum sides use smooth normals around the circumference, continuous across
UV seams. Hoop shoulders, the rim and the recessed lid retain hard shading
boundaries. This changes only stored vertex normals; geometry, UVs, frame
identity and the triangle budget remain identical to the first authored barrel.

The existing `models/objects/barrels/tris.md2` and `skin.png` paths are retained,
covering map placements and existing saves. No mission archive supplies another
copy of the model. Its feet remain at local height zero, with an approximately
32 by 32 by 40 unit extent matching the existing collision box. All gameplay
code is retained: pushing, health, configurable damage, explosion delay, chain
reactions and debris use their existing functions and values.

The drum uses 260 triangles instead of the previous 899 (71.1% fewer). The MD2
is 11,832 bytes instead of 38,728. These are asset budgets, not measured device
frame rates. The manifest records original archived source statistics, the
previous runtime budget, current output hashes and export validation.

The dedicated `barrels` owner prevents the legacy converter from restoring the
old mesh or atlas. The old conversion records are retained in the legacy
manifest's superseded inventories, and the checked source archive remains intact.
Normal Make/CMake builds run the standard-library barrel verifier; full source
regeneration invokes the new generator.

```sh
python3 tools/assets/build_barrels.py
python3 tools/assets/build_barrels.py --verify
python3 tests/assets/test_barrels.py
python3 -S tools/assets/verify_barrels_runtime.py
python3 tools/assets/build_platoon.py verify
make -j4 all
python3 tools/assets/build_overlay.py --output baseq2/plastic-platoon.pk3
python3 tools/performance/capture_barrels.py --output build/barrels-qa-gl3 --renderer gl3
```

Asset tests verify reproducible bytes, independent ownership, original frame
identity, scale/origin, GL command counts, nondegenerate quantized triangles,
closed component edges, consistent winding and outward stored normals. Native
captures use a separate portable runtime and normal entity lighting. The test
room photographs front, back, side, lid and distant views, then fires the normal
pistol to check that the barrel disappears and native debris appears.

Initial flat-normal native reports in `build/barrels-qa-gl3/report.json`,
`build/barrels-qa-gl1/report.json` and `build/barrels-qa-soft/report.json` all
pass, each with six screenshots and a clean engine exit. Front and lid views
were inspected for the shape, stencil orientation, caps and culling. That
version's matching source/release package SHA256 was
`1039630524210e5220c0e568e9056417448f18cdef921907751e26f3190be486`.

The smooth-normal revision passes `build/barrels-smooth-qa-gl3/report.json`
with six views and a clean engine exit. Front and lid views confirm the rounded
side lighting and retained rim/lid creases. Comparing exported MD2 bytes shows
that only 376 stored normal indices changed; all other model bytes are identical.
Source and release packages verify 977 assets and 126 image references and match
SHA256 `47f0cbea32c4b610b37539e529f7dfe7f852b50ca5fcc144054da0fb7bb10a6f`.
