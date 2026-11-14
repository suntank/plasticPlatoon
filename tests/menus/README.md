# Runtime menu visual checks

Build the current unstripped SDL2 client, game and renderer, then run:

```sh
python3 tests/menus/smoke_menus.py --size 240x240 --output /tmp/pp-menus-handheld
python3 tests/menus/smoke_menus.py --size 1280x720 --output /tmp/pp-menus-desktop
```

The script discovers all registered `menu_*` commands, opens each in the actual
client, navigates long menus to their last selectable row, and captures binding,
reserved-save-slot and quit prompts. It retains labeled PNGs, an input script,
console output, selected-row snapshots and `report.json`. Assertions cover menu
opening, valid focus, scrolling, binding prompts, screenshot count/dimensions and
clean exit. Inspect the screenshots to assess readability and visual hierarchy.

Use `--renderer gles1` for the alternate renderer and `--client /path/to/quake2`
for another current unstripped build. Matching renderer and `baseq2/game.so`
modules must be beside that executable. Development headers for SDL2 and a C
compiler are needed to build the temporary preload driver. Software rendering
is used on the host; this does not establish Pi performance or physical panel
legibility. All settings, saves and captures stay in the output runtime.
