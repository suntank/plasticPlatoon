#!/usr/bin/env python3
"""Validate the ant model's animation and renderer contract."""
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/assets'))
from md2_assets import MD2, normal_table


class AntAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = MD2.read((ROOT / 'baseq2/models/monsters/ant/tris.md2').read_bytes())

    def test_frames_skin_and_engine_limits(self):
        m = self.model
        self.assertEqual(len(m.positions), 50)
        self.assertEqual([n.decode().rstrip('\0') for n in m.names],
                         [f'{name}{i:02}' for name, count in
                          [('idle',8),('walk',12),('run',12),('attack',8),('pain',4),('death',6)]
                          for i in range(count)])
        self.assertLessEqual(m.header[6], 2048)
        self.assertLessEqual(m.header[8], 4096)
        self.assertEqual(m.command_triangles, m.header[8])
        self.assertEqual(m.skins, ['models/monsters/ant/skin.png'])
        self.assertTrue((ROOT/'baseq2'/m.skins[0]).is_file())

    def test_all_poses_have_valid_geometry_and_stay_above_floor(self):
        m = self.model
        for index, positions in enumerate(m.positions):
            with self.subTest(frame=index):
                t = positions[m.faces]
                cross = np.cross(t[:,1]-t[:,0], t[:,2]-t[:,0])
                light = normal_table()[m.normals[index]][m.faces].mean(axis=1)
                self.assertTrue(np.all(np.einsum('ij,ij->i',cross,light) < 0))
                self.assertGreaterEqual(positions[:,2].min(), -24.1)
        self.assertLess(m.positions[0,:,2].max() - m.positions[0,:,2].min(), 56)
        self.assertGreater(np.ptp(m.positions[0,:,0]), 56)

    def test_run_uses_higher_steps_and_longer_strides_than_walk(self):
        p = self.model.positions
        feet = p[:, p[0, :, 2] < -22.7]
        walk = np.ptp(feet[8:20], axis=0).max(axis=0)
        run = np.ptp(feet[20:32], axis=0).max(axis=0)
        self.assertGreater(walk[0], 20)
        self.assertGreater(run[0], walk[0] + 4)
        self.assertGreater(run[2], walk[2] + 3)
        self.assertTrue(np.all(feet[8:32, :, 2].min(axis=1) < -23))

    def test_windup_opens_jaws_and_hit_frame_reaches_farthest(self):
        m = self.model
        tile = (m.uvs * 4).astype(int)
        mandibles = np.all(tile == [1, 1], axis=(1, 2))
        jaws = m.positions[32:40, np.unique(m.faces[mandibles])]
        widths = np.ptp(jaws[:, :, 1], axis=1)
        reach = jaws[:, :, 0].max(axis=1)
        self.assertGreater(widths[3], widths[4] + 6)
        self.assertGreater(reach[4], reach[3] + 10)
        self.assertEqual(reach.argmax(), 4)

    def test_gaster_normals_follow_the_rounded_shell(self):
        # Adjacent vertices on each of the seven 12-sided shell rings should
        # shade smoothly. Caps have their own flat normals.
        for frame in (0, 14, 25, 36, 42, 49):
            with self.subTest(frame=frame):
                normals = normal_table()[self.model.normals[frame, :84]].reshape(7, 12, 3)
                nearby = np.sum(normals * np.roll(normals, 1, axis=1), axis=2)
                self.assertGreater(nearby.min(), .55)
                self.assertGreater(len(np.unique(normals.reshape(-1, 3), axis=0)), 12)


if __name__ == '__main__':
    unittest.main()
