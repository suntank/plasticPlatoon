# Plastic Heavy Tank Test Range

Open the game console and run `exec tank_test.cfg`, or use `map pp_tank_test`
in an existing single-player session. The range requires the updated game
module/client with `monster_plastic_tank`, the main Plastic Platoon asset pack,
and original Quake II game data. Restart the game after installing the new PK3.

The protected southern supply bay contains a rocket launcher, M60
(`weapon_chaingun`), heavy armor, health, six boxes of rockets and six boxes of
bullets. Three tan plastic heavy tanks occupy the center, western rear lane and
northeastern lane. All three appear on every difficulty. Their turrets can turn
independently of their hulls and fire the existing green rockets at the player.
The tanks can pursue through the broad central approach and side lanes. Tall
toy barricades stop rockets; work around their ends to flank the vehicles.
Health, rockets and bullets are also available on both flanks. Defeating all
three displays “ARMOR RANGE CLEAR” and leaves the map running for inspection.
Use `map pp_tank_test` to reset. Three additional co-op starts are provided.

The ready-to-use `operation-tank-test.pk3` includes the compiled map, editable
source, launch config, used Sandkeep materials, new hull/turret models and their
skins, existing green rocket model/skin, and the existing M60 audio used by the
supplied weapon. It contains no original game PAK data.

The source can be regenerated with standard Python 3, without third-party
packages. Regeneration overwrites manual edits to the generated MAP.

```sh
python3 tools/maps/generate_tank_test.py
./compile_map.sh --source maps/source/pp_tank_test.map \
  --basedir baseq2 \
  --tool "$Q2TOOL" \
  --profile release --threads 4 --output-dir baseq2/maps
python3 tools/maps/generate_tank_test.py --verify
python3 tools/maps/package_tank_test.py
```

Set `Q2TOOL` to your installed q2tool executable. The compiler's asset directory must contain the existing Sandkeep WALs and an
authentic `pics/colormap.pcx`. The source uses those materials without changing
their artwork. Release compilation runs BSP, full VIS and RAD and rejects leaks
or missing compile textures. The compiled level is `baseq2/maps/pp_tank_test.bsp`;
compiler logs and the build manifest are in `build/maps/pp_tank_test`.

Verification reads the compiled BSP independently of the brush writer. It
checks source/BSP entity agreement, actual tank hulls, player starts and pickup
hulls, five supported player routes, three tank routes, and 648 muzzle checks
across the full turret sweep at -10, 0 and +10 degrees pitch. Muzzle positions
use the actual turret pivot, barrel length and pitch transform (56 units above
the ground at zero pitch). Initial rocket lanes and aimed firing lines into
every player start are checked along with all three skill settings, target
wiring, visibility and lightmaps. These static
geometry checks complement real-engine validation; they are not a claim of a
full human combat playthrough. Results and exact source/BSP hashes are saved to
`build/maps/pp_tank_test/verification.json`.

Packaging requires passing verification for the exact source/BSP and follows
the actual MD2 skin tables. It writes identical archives with fixed timestamps
to `baseq2` and `release/baseq2`; the file hashes are recorded in
`build/maps/pp_tank_test/package.json`. Add `--install-user` to install the same
archive into `~/.yq2/baseq2`.

For close-up renderer checks after building the client, renderer and game module:

```sh
python3 tools/maps/capture_sandkeep.py --source release --map-name pp_tank_test \
  --map baseq2/maps/pp_tank_test.bsp --materials baseq2 \
  --label tank-gl3 --views tools/maps/tank_test_views.json
```

Repeat with `--renderer gl1` and a fresh `--label` for GL1. This optional check
uses Xvfb and local loopback sockets; Pillow adds a contact sheet.
