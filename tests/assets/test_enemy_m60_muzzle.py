#!/usr/bin/env python3
"""Compare the compiled heavy-gunner muzzle with the actual M60 front cap."""
import os
from pathlib import Path
import shlex
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
# Reviewed forward cap of the authored flash_hider, including cap/side UV seams.
RIM = (228, 229, 231, 233, 235, 237, 244, 245, 246, 247, 248, 249)


def rim_center(raw, frame):
    header = struct.unpack_from('<17i', raw)
    start = header[14] + frame * header[4]
    transform = struct.unpack_from('<6f', raw, start)
    points = [tuple(raw[start + 40 + vertex * 4 + axis] * transform[axis]
                    + transform[axis + 3] for axis in range(3)) for vertex in RIM]
    return tuple(sum(point[axis] for point in points) / len(points) for axis in range(3))


class EnemyM60MuzzleTests(unittest.TestCase):
    def test_heavy_flash_matches_tall_model_at_planted_firing_pose(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / 'muzzle.c'
            source.write_text('#include <stdio.h>\n'
                '#include "src/common/header/shared.h"\n'
                'int main(void) { printf("%.9f %.9f %.9f\\n", '
                'monster_flash_offset[MZ2_SOLDIER_HEAVY][0], '
                'monster_flash_offset[MZ2_SOLDIER_HEAVY][1], '
                'monster_flash_offset[MZ2_SOLDIER_HEAVY][2]); return 0; }\n')
            executable = directory / 'muzzle'
            subprocess.run([*shlex.split(os.environ.get('CC', 'cc')), '-std=c11',
                '-I', str(ROOT), str(source), str(ROOT/'src/common/shared/flash.c'),
                '-o', str(executable)], check=True, capture_output=True)
            actual = tuple(map(float, subprocess.check_output([str(executable)], text=True).split()))
        frames = (ROOT/'src/game/monster/soldier/soldier.h').read_text()
        self.assertIn('#define FRAME_attak303 32\n', frames)
        raw = (ROOT/'baseq2/models/monsters/soldier/tall/weapon_heavy.md2').read_bytes()
        center = rim_center(raw, 32)
        expected = (center[0], -center[1], center[2])
        # Model +Y is left; both the game and client project with right.
        # The shared soldier macros apply the foot-anchored height once.
        for measured, target in zip(actual, expected):
            self.assertAlmostEqual(measured, target, delta=.0001)


if __name__ == '__main__':
    unittest.main()
