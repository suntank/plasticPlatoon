#!/usr/bin/env python3
"""Check actual compiled enemy muzzle offsets against the exported shotgun rim."""
import os
from pathlib import Path
import shlex
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
# The visible front/inside barrel rim uses the same identities in every pose.
RIM = (144, 145, 146, 147, 148, 149, 156, 157, 158, 159, 160, 161)
# soldier_fire1/2/3/4/6/7/8 callbacks, indexed from soldier.h animation frames.
# Flash 5 has no callback in this game and retains its legacy table value.
FIRE_POSES = ((1, 'attak103', 2), (2, 'attak205', 16),
              (3, 'attak303', 32), (4, 'attak403', 41),
              (6, 'death122', 293), (7, 'death125', 296),
              (8, 'runs04', 112))


def rim_center(raw, frame):
    header = struct.unpack_from('<17i', raw)
    frame_start = header[14] + frame * header[4]
    transform = struct.unpack_from('<6f', raw, frame_start)
    points = [tuple(raw[frame_start + 40 + vertex * 4 + axis] * transform[axis]
                    + transform[axis + 3] for axis in range(3)) for vertex in RIM]
    return tuple(sum(point[axis] for point in points) / len(points) for axis in range(3))


class EnemyShotgunMuzzleTests(unittest.TestCase):
    def test_runtime_offsets_match_tall_shotgun_at_each_firing_pose(self):
        # Compile the same shared table used by the game and client, so the
        # actual macros, signs and foot-anchored height transform are tested.
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / 'muzzle.c'
            source.write_text('#include <stdio.h>\n'
                '#include "src/common/header/shared.h"\n'
                'int main(void) {\n' + ''.join(
                    f'printf("{flash} %.9f %.9f %.9f\\n", '
                    f'monster_flash_offset[MZ2_SOLDIER_SHOTGUN_{flash}][0], '
                    f'monster_flash_offset[MZ2_SOLDIER_SHOTGUN_{flash}][1], '
                    f'monster_flash_offset[MZ2_SOLDIER_SHOTGUN_{flash}][2]);\n'
                    for flash, _, _ in FIRE_POSES) + 'return 0; }\n')
            executable = directory / 'muzzle'
            subprocess.run([*shlex.split(os.environ.get('CC', 'cc')), '-std=c11',
                '-I', str(ROOT), str(source), str(ROOT/'src/common/shared/flash.c'),
                '-o', str(executable)], check=True, capture_output=True)
            actual = {int(row[0]): tuple(map(float, row[1:])) for row in
                      (line.split() for line in subprocess.check_output(
                          [str(executable)], text=True).splitlines())}
        raw = (ROOT/'baseq2/models/monsters/soldier/tall/weapon_shotgun.md2').read_bytes()
        frames = (ROOT/'src/game/monster/soldier/soldier.h').read_text()
        for flash, name, frame in FIRE_POSES:
            with self.subTest(flash=flash, pose=name):
                self.assertIn(f'#define FRAME_{name} {frame}\n', frames)
                center = rim_center(raw, frame)
                # Model +Y is left. The shared projection table stores right.
                expected = (center[0], -center[1], center[2])
                for measured, target in zip(actual[flash], expected):
                    self.assertAlmostEqual(measured, target, delta=.0001)


if __name__ == '__main__':
    unittest.main()
