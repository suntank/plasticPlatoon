#!/usr/bin/env python3
"""Bake the view back across the sandbox from the extraction oak's fence line."""

import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bake_room_skybox import bake, match_edge_texels, material, new_scene, parse_args
from render_backyard_skybox import fencing, grass, house, summer_sky
from render_window_yard_skybox import garden, sandbox, window_yard_materials


# The playable oak stands at (.95, 3.43). Look out from its fence-side roots,
# at the same toy-soldier eye height as the garden infiltration sky.
EYE = (.95, 3.96, .088)
SKY = "pp_extraction"


def build_scene(samples):
    scene = new_scene(samples, bounces=3, exposure=-.14)
    scene.view_settings.view_transform = "Standard"
    scene.cycles.adaptive_threshold = .045
    materials = window_yard_materials()
    # Pale packed sand keeps the gate readable against the shaded cedar fence.
    materials["castle"] = material("Pale packed sand", "d8b477", "e7c78a", 15, glow=.12)
    materials["castle_lit"] = material("Sun-dried crenels", "efd399", glow=.12)
    summer_sky(scene)
    fencing(materials)
    house(materials)
    garden(materials)
    sandbox(materials, center=(.1, -.55), gate_yaw=math.radians(65),
            castle_scale=(1.24, 1.24, 1.42))
    grass(materials, eye=EYE)
    return scene


if __name__ == "__main__":
    args = parse_args(__doc__, samples=24)
    bake(build_scene(args.samples), SKY, EYE, args.output)
    match_edge_texels(args.output, SKY)
