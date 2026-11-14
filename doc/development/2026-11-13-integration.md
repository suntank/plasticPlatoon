# Project integration audit — 2026-11-13

This integration preserves the working-tree project work and the newer main
branch audio recordings.

Included work:

- Authored M16 and long beveled pistol replacements, molded hands, actual-model
  ADS, actor/pickup variants, asset generators and geometry/contact checks.
- Temple and Switchyard levels, sources, compiled packages, launch configs,
  menu entries, documentation, builders and collision/route verification.
- Endline and Sandstorm source/preview revisions and route/camera tooling.
- Compact/scrolling menus, GL1 world/inline batching, alias color caches,
  lightmap optimizations, pickup LODs and per-view draw profiling.
- Renderer regression suites, handheld menu smoke tests, Pi/PC benchmark tools,
  capture/analysis scripts and Game Bird documentation.

Validation passed: full engine build; asset unit suite; renderer regression
scripts; benchmark-tool tests; 240x240 runtime menu smoke test; Temple,
Switchyard and Endline verification. Authored weapon aiming/firing was also
checked in single-view and mixed four-player captures during implementation.
The merged asset package is regenerated to include main's newer support audio.

## Sandstorm follow-up

The current edited source and available BSP snapshots do **not** pass all
Sandstorm mission/route checks. Failures include counted roof-wave defenders,
response triggers and blocked routes/sightlines. Both the installed BSP and
older candidate BSP were checked. The manual work is preserved, but source,
compiled geometry and mission expectations need reconciliation and a fresh
verified build before claiming Sandstorm validation passes. No generator was
run over the manual level edits during this integration.

Local attachment images, editor autosaves and compiled preload drivers are
excluded from Git; source files and driver build instructions are included.
