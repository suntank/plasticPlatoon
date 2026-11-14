# Long beveled pistol

The pistol uses a long, eight-corner beveled slide with a narrowed rear,
shallow frame with a tapered rear, sloped grip and compact sights. Its upper body carries the
silhouette; the frame no longer forms a second tall block under the slide.
All solids are closed, authored profiles and lofts. The established green
army-man palette and single 256 by 256 atlas remain. Four fine rear serrations
leave the long slide planes clean. Soft finger creases stay on the fused
finger bank, leaving the rounded palm and thumb unstriped.

| Version | Previous triangles | Current triangles | Reduction |
| --- | ---: | ---: | ---: |
| First person, now with right hand and arm | 1,400 | 598 | 57.3% |
| Player-held | 1,580 | 200 | 87.3% |
| Enemy-held, including taller variant | 1,616 | 200 | 87.6% |
| New world/pickup mesh | No prior mesh | 200 | — |

`pistol_geometry.add_pistol_hand` fits a high mitten grip specifically to this
pistol while retaining the M16's molded hand style and uniform model scale.
A concave palm/finger wrap follows the exterior backstrap and front strap,
leaving a grip-shaped cavity inside the hand. Rounded knuckles and a sloping
heel flow into one continuous forearm/wrist sweep, with the cuff painted as a
material band. The thumb root is buried in the rear palm and its tip follows
the visible side. The hand remains in the gun's
MD2 and atlas, so it adds no separate draw call. World models omit it.

The real rear notch and front blade move onto the eye's center ray over the
shared 0.18-second aim transition. Each local player owns its own state; each
weapon supplies its own sight and muzzle offsets. Switching weapons resets
the transition. Releasing aim returns to the hip pose, with normal procedural
recoil and raising. Unsupported weapons retain their image overlays.

The first-person mesh remains one frame for the static renderer cache. All
198 player and 475 enemy attachment poses retain their original frame names
and follow rigid motion fitted to the archived pistol. The held grip center
stays at the previous attachment point while the longer muzzle follows the
new silhouette. Tall attachments retain
the existing foot-anchored 1.2 scale. The muzzle table follows the new barrel
rim through every player pose. All gun, hand and forearm components have closed
surfaces, including the concave wrap's ear-clipped ends. Dense exported-face
sampling checks that the hand does not pass through the grip. The wrist's
narrow end is buried in the heel, so no separate capped adapter is exposed.

The pistol remains the always-owned starting weapon. Its new world-model
reference enables review/editor placement without changing pickup/drop rules.
The legacy converter and optional Pi overlay omit the replaced models, so
neither can restore the old pistol over the new main package.

## Rebuild and verify

```sh
.venv/bin/python tools/assets/build_pistol.py
python3 tools/assets/build_soldier_height.py
python3 tools/assets/build_player_muzzle_points.py
python3 tools/assets/build_color_variants.py
make -j4 all
python3 tools/assets/build_overlay.py --output baseq2/plastic-platoon.pk3

.venv/bin/python tests/assets/test_pistol.py
.venv/bin/python tests/assets/test_authored_hands.py
.venv/bin/python tools/assets/render_pistol_hand.py --output build/pistol-hand-qa
sh tests/input/run_pistol_model_ads_tests.sh
.venv/bin/python tests/assets/test_player_muzzle_points.py
.venv/bin/python tests/assets/test_color_variants.py
python3 tools/assets/verify_pistol_runtime.py
.venv/bin/python tools/assets/build_platoon.py verify
python3 tools/assets/build_overlay.py --verify --output baseq2/plastic-platoon.pk3
```

`pistol-manifest.json` records exact assets, source archive, generator
dependencies, triangle counts, all-pose validation and sight anchors. The
generated `pistol_model_ads.h` binds the runtime alignment to those anchors.
Normal builds verify the checked outputs using only the Python standard
library. Reauthoring needs NumPy and Pillow.

`capture_m16.py --weapon Pistol --ads` captures actual first-person, sight,
firing, release, held and world views in an isolated game. Add `--four` and
`--mixed-weapons` to check pistol/M16 aiming independently across four players.
The geometry reduction is measured; a Raspberry Pi frame-rate improvement
requires a separate target-device comparison.

`render_pistol_hand.py` generates six paired diagnostics from the actual
exported MD2: the player's eye, both rear three-quarter angles, both sides,
and a lower rear view of the wrist. Temporary contrasting gun/hand colors
expose contact and occlusion; hand-only silhouettes show the mitten without
the gun masking its shape. These are geometry checks, not game screenshots.
