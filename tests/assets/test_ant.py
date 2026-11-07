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
        self.assertEqual(len(m.positions), 54)
        self.assertEqual([n.decode().rstrip('\0') for n in m.names],
                         [f'{name}{i:02}' for name, count in
                          [('idle',8),('walk',12),('run',12),('attack',8),('pain',4),('death',10)]
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

    def test_motion_and_bite_are_distinct(self):
        p = self.model.positions
        for first, second in ((8,11), (20,23), (32,36), (40,42), (44,53)):
            self.assertGreater(np.max(np.linalg.norm(p[first]-p[second], axis=1)), 1)
        self.assertGreater(p[36,:,0].max(), p[32,:,0].max() + 1)

    def test_gaster_normals_are_smooth_across_face_seams(self):
        # The first 180 vertices form the gaster, including duplicated face
        # corners. They should shade consistently throughout the animation.
        for frame in (0, 14, 25, 36, 42, 53):
            with self.subTest(frame=frame):
                positions = self.model.positions[frame, :180]
                normals = self.model.normals[frame, :180]
                seam_normals = {}
                for position, normal in zip(positions, normals):
                    seam_normals.setdefault(tuple(position), set()).add(int(normal))
                self.assertTrue(all(len(indices) == 1 for indices in seam_normals.values()))
                self.assertGreater(len(set(int(n) for n in normals)), 12)


if __name__ == '__main__':
    unittest.main()
