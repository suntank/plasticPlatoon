#!/usr/bin/env python3
"""Compare the compiled rocket-soldier muzzle with the exported tube rim."""
import os
from pathlib import Path
import shlex
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
# Reviewed outer and inner front lip of the authored launch_tube (canonical X100).
RIM = (56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 76, 82, 88, 94, 100, 106)


def rim_center(raw, frame):
    header = struct.unpack_from('<17i', raw)
    start = header[14] + frame * header[4]
    transform = struct.unpack_from('<6f', raw, start)
    points = [tuple(raw[start + 40 + vertex * 4 + axis] * transform[axis]
                    + transform[axis + 3] for axis in range(3)) for vertex in RIM]
    return tuple(sum(point[axis] for point in points) / len(points) for axis in range(3))


class EnemyRocketLauncherMuzzleTests(unittest.TestCase):
    def test_rocket_flash_matches_tall_model_at_planted_firing_pose(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / 'muzzle.c'
            source.write_text('#include <stdio.h>\n'
                '#include "src/common/header/shared.h"\n'
                'int main(void) { printf("%.9f %.9f %.9f\\n", '
                'monster_flash_offset[MZ2_SOLDIER_ROCKET][0], '
                'monster_flash_offset[MZ2_SOLDIER_ROCKET][1], '
                'monster_flash_offset[MZ2_SOLDIER_ROCKET][2]); return 0; }\n')
            executable = directory / 'muzzle'
            subprocess.run([*shlex.split(os.environ.get('CC', 'cc')), '-std=c11',
                '-I', str(ROOT), str(source), str(ROOT/'src/common/shared/flash.c'),
                '-o', str(executable)], check=True, capture_output=True)
            actual = tuple(map(float, subprocess.check_output([str(executable)], text=True).split()))
        frames = (ROOT/'src/game/monster/soldier/soldier.h').read_text()
        self.assertIn('#define FRAME_attak303 32\n', frames)
        raw = (ROOT/'baseq2/models/monsters/soldier/tall/weapon_rocket.md2').read_bytes()
        center = rim_center(raw, 32)
        expected = (center[0], -center[1], center[2])
        # Game and client use right rather than model +Y (left). The shared
        # soldier macros apply the foot-anchored height transform once.
        for measured, target in zip(actual, expected):
            self.assertAlmostEqual(measured, target, delta=.0001)


if __name__ == '__main__':
    unittest.main()
