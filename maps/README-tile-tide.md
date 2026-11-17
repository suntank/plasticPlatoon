# Tile Tide

Tile Tide is a Plastic Platoon free-for-all arena designed for 2–4 players.
Choose `pp_tile_tide` in **Multiplayer** after setting up the local players, or
run `exec tile_tide_dm.cfg` in the console. The preset starts deathmatch with
a 20-frag limit and a 10-minute timer.

```sh
./release/play-portable.sh +exec tile_tide_dm.cfg
```

## Routes

- The tub's front opening and east opening both slope gently into the dry
  basin. The grenade launcher and jacket armor give players a reason to
  cross the basin, and either opening works as an exit.
- The open floor runs past the toilet and hamper, around either side of
  the folded towels, and beneath the floating vanity. The floor routes
  connect to both tub openings. The vanity overhang and bath apron break
  sightlines between the ends of the room.
- The tub rim and countertop are future high ground. The arena's spawns and
  pickups are all on the connected floor and basin routes. There are 12
  deathmatch starts, two of them inside the bath. The layout works without
  teleporters, lifts, or toy stairs.

## Editing and building

Open [pp_tile_tide.map](source/pp_tile_tide.map) in TrenchBroom with the Quake II
game configuration and the repository as the game path. The room sits on
**Z 0**, the bath floor is at **Z 48**, the bath rim is at **Z 320**, and
the vanity counter is at **Z 520**.

| Space for future toys | Floor footprint in map units | Landing |
| --- | --- | --- |
| Along the middle of the tub apron | X −630 to −64, Y 121 to 250 | Tub rim at Z 320 |
| Along the face of the vanity | X 552 to 688, Y −360 to 176 | Counter at Z 520 |
| Outside the north end of the vanity | X 752 to 1090, Y 248 to 450 | Counter at Z 520 |

A continuous staircase can use risers up to 16 units. Keep the tub openings
at **X −920 to −736** on the south edge and **Y 488 to 648** on the east
edge clear if you want to preserve the deathmatch circuit. The wood door
on the south wall is a landmark and a potential mission entrance for a
single-player pass.

Rebuild the edited MAP with Python 3, Pillow and q2tools-220. The builder
stages compiler materials, runs full BSP, VIS and RAD, and creates
`baseq2/operation-tile-tide.pk3`. It also installs the pack into the
portable build if `release/baseq2` exists.

```sh
python3 tools/maps/build_bathroom.py
```

Pass `--tool /path/to/q2tool` if the compiler is installed elsewhere. The
original textures ship as PNGs and WALs. To regenerate just the textures
with the repo's asset dependencies installed, run
`python3 tools/maps/generate_bathroom.py --materials-only`. Running the
generator without this flag replaces the MAP. Use the build script when
compiling hand edits.

The first build was checked in four-player local deathmatch. The packaged
arena loaded and all four views rendered. Both tub ramps were walked in
both directions, and the vanity underpass was walked from south to north.

## N64 reference

The original *Army Men: Sarge's Heroes* campaign uses the bathtub as the
anchor for its Bathroom mission. The N64 manual also describes fighting
over the sink and reaching the commode in the final bathroom sequence.
Producer Michael Mendheim singled out the bathroom as a setting for
four-player battles. Tile Tide uses the oversized fixtures and floor-level
cover as the starting point for its own room layout and traversal.
[N64 manual](https://nintendo64.pl/wp-content/uploads/Army-Men-Sarges-Heroes-USA.pdf),
[N64 Bathroom gameplay](https://www.youtube.com/watch?v=Gh2gpSrn9Dk&t=3582s),
[Michael Mendheim interview](https://www.oocities.org/timessquare/bunker/2005/news_interviewmike.html)
