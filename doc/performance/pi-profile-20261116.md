# Garden combat profiling and publication

The Pi engine now caches canonical cvar lookups, reuses exact model normal
colours, and exits alias-model frustum tests early. The changes preserve
rendered geometry, lighting, assets, and enemy counts. The original paths
remain available with `cvar_lookup_cache 0`, `r_gl1_normal_colors 0`, and
`r_gl1_fast_alias_cull 0`.

Four independent players fought in separated regions on the native 240x240
display, with normal quality, live AI, dynamic lighting and sound mixing.
Players received extra health and shotgun ammunition. Each fresh combat
window lasted 90 seconds. A test-only SDL swap observer recorded complete
display intervals with both `r_perf` and `r_drawprofile` disabled, avoiding
the measurable overhead of ordinary renderer counters.

| Difficulty | Optimized average FPS | P95 frame time | P99 frame time |
| --- | ---: | ---: | ---: |
| Normal | 33.78 | 33.14 ms | 36.39 ms |
| Hard | 32.50 | 35.92 ms | 39.76 ms |

Both optimized captures passed resource checks. The hard legacy capture was
32.15 FPS with 37.29 ms P95. The normal legacy capture had a major page fault
and is excluded from a clean speedup claim. Live AI, recoil and knockback
vary between runs, so these are workload observations rather than identical
scene comparisons. Average FPS exceeds 30 in both optimized captures; hard
does not meet a stricter 33.333 ms P95 criterion. The user accepted the
32.50 average FPS result and requested publication without further tests.

The performance measurements apply to authored source
`d4f39d62732841ece6e6180861055bc0790670b3bd5dfd9c1b37f1c37bdf65fa`,
compiled BSP
`083c3cd2789f3fea68972b5f97c31e1d68cbabff16741ff40ed454404017c866`.
The subsequently saved map is compiled and published separately; its current
identities are recorded in [the map publication receipt](../../maps/garden-infiltration-status.json).
No performance result is attributed to the untested publication revision.

Host and native ARM correctness checks passed before publication: canonical
cvar lookup behaviour, 1,024 byte-exact normal palettes, 3,072 expanded-colour
cases, and 100,000 equivalent alias-frustum classifications. GL1 and GLES1
compiled successfully. The installed GL1 build passed an ordinary four-client
functional check. Those checks were not rerun for the later map publication.

Native captures, exact sources, binaries, backups and deployment receipts are
retained under
`/data/build-sources/plastic-platoon-garden-combat-20261116/`.
The map-only publication and its previous installed files are retained under
`/data/build-sources/plastic-platoon-garden-publish-20261116/`.
The test-only swap observer is never installed in the game package.

The [native correctness receipt](../../tools/performance/pi_bench/pi-native-validation-20261116.json)
retains the measured map identity, installed binary hashes and original
P95 verdict. The benchmark source manifest records the installed source and
helper identities. Real player saves and settings are preserved.
