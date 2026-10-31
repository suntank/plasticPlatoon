# Pickup asset optimization and visual review

Sixteen static pickup and weapon models have been rebuilt with texture-aware quadric simplification. The same 92 initial sandbox placements now reference **74,769 triangles instead of 211,975**, a **64.7% content workload reduction before visibility culling**. This is a verified geometry inventory, not a claim about triangles visible in one frame or a measured FPS improvement.

All changed models remain single-frame MD2s in the original coordinate system. Gameplay collision, pickup rules, weapon behavior, player animation and first-person view models are untouched. Each image below compares the exact original asset from commit `f2d9366ec7d2bbd256b5d103f1a57c6a5e1b011b` against its shipped replacement.

## Geometry inventory

Position vertices are the MD2 animation vertices. Render vertices count unique position-index/float-UV pairs after UV seam expansion. The latter is the relevant size for the new persistent renderer topology. Every listed model has one frame before and after.

| Asset | Sandbox instances | Triangles before → after | Position vertices before → after | Render vertices before → after |
|---|---:|---:|---:|---:|
| Armor shard | 18 | 2,000 → 800 | 982 → 382 | 2,107 → 1,075 |
| Small health | 15 | 3,000 → 800 | 1,502 → 402 | 2,669 → 932 |
| Medium health | 11 | 2,994 → 800 | 1,491 → 394 | 2,954 → 970 |
| Large health | 12 | 1,998 → 998 | 999 → 500 | 2,307 → 1,235 |
| Combat armor | 1 | 4,096 → 1,000 | 2,048 → 500 | 3,584 → 1,204 |
| Body armor | 2 | 2,000 → 1,000 | 1,002 → 502 | 2,147 → 1,267 |
| Jacket armor | 2 | 1,999 → 799 | 1,004 → 404 | 2,383 → 1,121 |
| Grenade ammo | 16 | 2,000 → 800 | 998 → 398 | 2,275 → 1,190 |
| Rocket ammo | 6 | 2,000 → 500 | 1,002 → 252 | 1,854 → 640 |
| Mega health | 0 | 1,994 → 800 | 999 → 402 | 2,165 → 1,095 |
| Chaingun pickup | 1 | 1,999 → 799 | 992 → 392 | 2,068 → 1,064 |
| Grenade launcher pickup | 1 | 1,996 → 800 | 989 → 391 | 2,311 → 1,156 |
| Machinegun pickup | 2 | 1,990 → 800 | 991 → 396 | 1,880 → 974 |
| Rocket launcher pickup | 1 | 1,999 → 799 | 991 → 391 | 1,882 → 979 |
| Shotgun pickup | 3 | 1,999 → 799 | 1,000 → 400 | 1,632 → 832 |
| Super shotgun pickup | 1 | 2,000 → 800 | 997 → 397 | 1,855 → 931 |

| Inventory measure | Before | After |
|---|---:|---:|
| Triangles across the 16 unique meshes | 36,064 | 13,094 |
| Triangles weighted by 92 initial sandbox instances | 211,975 | 74,769 |
| Position vertices weighted by instances | 105,586 | 36,995 |
| Render vertices weighted by instances | 215,079 | 96,254 |
| Total MD2 bytes for 16 unique meshes | 1,650,089 | 574,500 |

The supplied map hash and all class-to-model instance counts are recorded in [the conversion configuration](../../tools/assets/pickups.json). A conversion with `--map` verifies both its SHA-256 and all 16 class counts. Mega health has no initial placement in this sandbox, but its asset is used elsewhere and is included in the unique-asset totals.

## Texture and file inventory

The original 2048×2048 skins had far more resolution than these world pickups normally occupy. Shipped pickup skins are 256×256. The small-health, medium-health and combat-armor skins were already that size and remain byte-for-byte unchanged. The machinegun pickup uses a new `skin_pickup.png`; the original `g_machn/skin.png` is also used by the animated soldier weapon and is deliberately retained.

All byte counts below are exact. Decoded RGBA estimates use four bytes per texel and exclude driver overhead and mipmaps. They are **not a VRAM measurement**. PNG compression reduces file size, not the decoded estimate.

| Asset | Texture dimensions before → after | MD2 bytes before → after | PNG bytes before → after | RGBA MiB before → after |
|---|---|---:|---:|---:|
| Armor shard | 2048×2048 → 256×256 | 91,226 → 35,696 | 3,812,578 → 130,971 | 16 → 0.25 |
| Small health | 256×256 → 256×256 | 138,118 → 34,480 | 106,017 → 106,017 | 0.25 → 0.25 |
| Medium health | 256×256 → 256×256 | 134,717 → 34,492 | 114,841 → 114,841 | 0.25 → 0.25 |
| Large health | 2048×2048 → 256×256 | 94,209 → 43,104 | 3,960,818 → 102,629 | 16 → 0.25 |
| Combat armor | 256×256 → 256×256 | 177,580 → 42,984 | 78,673 → 78,673 | 0.25 → 0.25 |
| Body armor | 2048×2048 → 256×256 | 90,602 → 43,608 | 4,466,557 → 111,565 | 16 → 0.25 |
| Jacket armor | 2048×2048 → 256×256 | 96,240 → 36,180 | 5,221,399 → 136,626 | 16 → 0.25 |
| Grenade ammo | 2048×2048 → 256×256 | 90,274 → 37,256 | 4,762,304 → 109,460 | 16 → 0.25 |
| Rocket ammo | 2048×2048 → 256×256 | 90,410 → 22,188 | 3,901,287 → 95,426 | 16 → 0.25 |
| Mega health | 2048×2048 → 256×256 | 88,549 → 35,704 | 4,178,404 → 107,469 | 16 → 0.25 |
| Chaingun pickup | 2048×2048 → 256×256 | 94,012 → 35,768 | 4,394,845 → 104,357 | 16 → 0.25 |
| Grenade launcher pickup | 2048×2048 → 256×256 | 96,763 → 36,652 | 4,720,309 → 110,486 | 16 → 0.25 |
| Machinegun pickup | 2048×2048 → 256×256 | 93,569 → 34,752 | 2,878,856 → 71,820 | 16 → 0.25 |
| Rocket launcher pickup | 2048×2048 → 256×256 | 92,937 → 34,664 | 2,207,110 → 47,610 | 16 → 0.25 |
| Shotgun pickup | 2048×2048 → 256×256 | 90,156 → 33,004 | 1,252,866 → 45,253 | 16 → 0.25 |
| Super shotgun pickup | 2048×2048 → 256×256 | 90,727 → 33,968 | 3,084,337 → 64,753 | 16 → 0.25 |

The set of unique textures referenced by these pickups falls from **208.75 MiB to 4 MiB** under the RGBA base-level estimate; full mip chains are approximately **278.33 MiB to 5.33 MiB**. With the animated soldier weapon also loaded, its retained 2048² machinegun skin adds 16 MiB after optimization. For that combined set, the comparable base-level estimate is **208.75 MiB to 20 MiB**, a 188.75 MiB reduction. Other actor/world/UI textures, renderer allocations and process memory are excluded.

## Visual acceptance and deliberate budget choices

The pipeline rasterizes actual source/replacement MD2 geometry, source/replacement PNG pixels and the MD2 normal table. Four fixed rotations (25°, 115°, 205°, 295°), equal framing and equal directional lighting are used. Each sheet includes 48-pixel coverage views and 224-pixel inspection views; inspection views are supersampled at 448 pixels. These are offline asset comparisons, not screenshots from the game or evidence of hardware speed.

All 16 sheets were visually inspected. The first 350–400 triangle trials were rejected for the shard, health pickups and grenade because they deformed straps, rounded bandages, the medkit cross or the grenade pin. The shipped 500–1,000 triangle budgets deliberately exceed some provisional Pi budgets to retain recognizable shapes. There is no silently enabled aggressive asset profile.

- Shard: the outer straps and hollow center survive at 800 triangles; the 350-triangle trial lost too much shape.
- Health pickups: the red crosses, bandage rolls and stimpack label stay readable. The medkit uses 998 triangles to retain its cross and handle. Small and medium health use 800 triangles; their close-up cylinders are more polygonal than the originals.
- Armor: the helmet, vest openings/pouches, boots and knee/foot shapes retain their identity. The helmet becomes somewhat smoother and the boots lose some fine edge detail at inspection scale.
- Grenade/rocket ammo: the pin ring, safety lever, rocket tip and fins remain present. The grenade needs 800 triangles; the thin rocket uses 500.
- Weapon pickups: stocks, barrels, magazines, grips and distinctive silhouettes remain intact at approximately 800 triangles. Their small projected width makes a one-pixel boundary change disproportionately large in a silhouette score.
- Mega health: the lid, badge/cross and green translucent-looking texture survive at 800 triangles. The normal opaque MD2 texture path is preserved.

The minimum silhouette intersection-over-union over the four 48-pixel views is 0.954–0.986 for the non-weapon pickups, except the rocket at 0.954 after rounding. Weapon minima range from 0.916 to 0.968. The exact per-view numbers are in the manifest. These scores are a screening aid, not a substitute for the inspected images. Close inspection still reveals reduced surface detail and mild UV stretching in some models; gameplay readability and the green-plastic visual identity were the acceptance criteria. Real game lighting and very close camera placement still warrant an owner review.

### Comparison sheets

- [Armor shard](asset-comparisons/models_items_armor_shard.png)
- [Small health](asset-comparisons/models_items_healing_stimpack.png)
- [Medium health](asset-comparisons/models_items_healing_medium.png)
- [Large health](asset-comparisons/models_items_healing_large.png)
- [Combat armor](asset-comparisons/models_items_armor_combat.png)
- [Body armor](asset-comparisons/models_items_armor_body.png)
- [Jacket armor](asset-comparisons/models_items_armor_jacket.png)
- [Grenade ammo](asset-comparisons/models_items_ammo_grenades_medium.png)
- [Rocket ammo](asset-comparisons/models_items_ammo_rockets_medium.png)
- [Mega health](asset-comparisons/models_items_mega_h.png)
- [Chaingun pickup](asset-comparisons/models_weapons_g_chain.png)
- [Grenade launcher pickup](asset-comparisons/models_weapons_g_launch.png)
- [Machinegun pickup](asset-comparisons/models_weapons_g_machn.png)
- [Rocket launcher pickup](asset-comparisons/models_weapons_g_rocket.png)
- [Shotgun pickup](asset-comparisons/models_weapons_g_shotg.png)
- [Super shotgun pickup](asset-comparisons/models_weapons_g_shotg2.png)

## Format correctness and repairs

The converter reads both the triangle table and GL strip/fan commands. It uses float UVs from the GL stream to avoid discarding seam precision. The output includes new deterministic strips with exact seam matching, a matching triangle/ST table, valid normal indices, correct offsets/counts, and a terminal zero command. The frame name, original compression scale/translation, coordinate axes and original quantization lattice are preserved. Quantized extrema may change slightly when vertices are removed; before/after bounds are reported explicitly in the manifest.

Normals are transferred barycentrically from the closest original triangle surface and re-encoded using the engine’s 162-normal table. This preserves smooth plastic shading and the original winding/normal convention. Regenerating normals directly from a coarser face mesh was rejected because it introduced unnecessary faceting; assuming mathematical counterclockwise normals would also invert Quake’s usual front-face convention.

The original static exporters reserve `40 + 7 × position_vertices` frame bytes, while the runtime reads `40 + 4 × position_vertices` meaningful bytes. Rebuilt files use the standard compact stride. Exact duplicate GL command triangles are repaired in large health, chaingun, machinegun, rocket launcher and super shotgun. The compatibility reader only accepts duplicate oriented position/UV triangles already represented in the triangle table. Unknown extra or missing faces remain errors. Stimpack and grenade launcher had unusable extra skin slots; the slot count is retained and those slots now refer to the valid skin.

Independent per-frame animated simplification is explicitly rejected. The 198-frame soldier mesh (2,000 triangles, 2048² skin), 198-frame soldier weapon (1,990 triangles, shared 2048² machinegun skin), stock male player and first-person view models are not modified. Their larger screen coverage and consistent animation topology require a separate visual/animation pass.

## Reproduction and recovery

The original sources remain in the pinned baseline commit and are never overwritten before being read. The tool uses `git show` with that exact commit for every MD2 and PNG, so rerunning conversion cannot simplify an already simplified mesh. [The manifest](assets-manifest.json) records source/output SHA-256 hashes, tool versions, algorithm parameters, per-asset counts, bounds, texture estimates and comparison-image hashes.

Use isolated worktrees for side-by-side inspection and regeneration:

```sh
git worktree add --detach ../plasticPlatoon-asset-source f2d9366ec7d2bbd256b5d103f1a57c6a5e1b011b
git worktree add --detach ../plasticPlatoon-asset-rebuild HEAD
cd ../plasticPlatoon-asset-rebuild
python3 -m venv /tmp/plastic-platoon-asset-venv
. /tmp/plastic-platoon-asset-venv/bin/activate
python -m pip install -r tools/assets/requirements.txt
python tools/assets/md2_assets.py build --write --review --map /absolute/path/to/pp_sandbox_coop1.map
python tools/assets/md2_assets.py verify
python tests/assets/test_md2_assets.py
python tests/run_renderer_tests.py --sanitize
```

The `--map` argument is optional if the supplied map file is unavailable; omit it to reproduce assets while retaining the pinned source-map hash/count inventory. An experiment should pass `--only <path-substring> --manifest /tmp/trial-manifest.json`; omitting `--write` keeps the installed MD2/PNG files unchanged. Comparison sheets are still regenerated when `--review` is requested. Pinned Python package versions match the recorded conversion environment; cross-platform numerical or image-library changes must be reviewed against the manifest hashes.

To restore one original asset for a controlled comparison, recover it in a separate worktree or use `git show <source_commit>:baseq2/<asset_path>` to write a comparison copy. Avoid mixing original models with replacement skin references when comparing. The manifest preserves each original and replacement skin path.

## Validation evidence and remaining checks

- Eight executable Python regressions pass: coordinate/frame/UV round trip; source normal direction; animated-input rejection; corrupt offset/stride/index/normal/command rejection; exact duplicate repair; deterministic conversion; output-manifest validation; and unchanged actor/shared-texture assertions.
- All 16 shipped models and skins pass manifest verification, including original source hashes, valid skin paths, frame identity, counts and texture dimensions.
- The renderer fixture loads all 16 real output files through production `Mod_LoadMD2` and `Mod_BuildAliasCache` under AddressSanitizer, UndefinedBehaviorSanitizer and LeakSanitizer. It checks source-index bounds, UVs, topology, cache allocation/lifetime and decoded static coordinates.
- All 16 four-angle sheets were inspected at gameplay coverage and inspection scale.

No Pi FPS or GPU-memory claim follows from this asset inventory. Benchmark equivalent engine settings with original versus optimized content in separate runs, keeping framebuffer, player positions, gameplay state, map and quality settings fixed. Asset gains belong in the content-optimization category, separately from renderer efficiency at equivalent content. The next asset opportunity is a deliberate animated soldier/weapon pass, followed by art-directed low-poly retopology of the hollow straps and rounded health props if measured Pi performance still requires lower counts.
