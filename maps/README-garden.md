# Garden

`pp_garden` is the original user-authored garden shell, with one solo start and
three co-op starts. Load it with `map pp_garden` after local squad setup.
The separate playable mission is `pp_garden_infiltration` (Operation Garden
Ghost).

The original editable source and compiled map are `baseq2/maps/pp_garden.map`
and `baseq2/maps/pp_garden.bsp`. Rebuild the standalone archive with
`python3 tools/maps/package_garden.py`. It contains the original MAP/BSP,
all referenced textures and animation followers, and the complete sky.
It ships as `baseq2/operation-garden.pk3`.

Packaging checks release visibility and lighting, gameplay entity agreement,
and brush counts. The original compile receipt is unavailable, so these checks
do not establish exact source-to-BSP geometry correspondence.
