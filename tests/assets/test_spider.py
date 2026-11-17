#!/usr/bin/env python3
"""Validate spider animation and creature-specific debris MD2 assets."""
from pathlib import Path
import sys
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/assets'))
from md2_assets import MD2, normal_table

class SpiderAssets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spider = MD2.read((ROOT/'baseq2/models/monsters/spider/tris.md2').read_bytes())

    def test_spider_animation_and_shape(self):
        m = self.spider
        ant=MD2.read((ROOT/'baseq2/models/monsters/ant/tris.md2').read_bytes())
        self.assertEqual(len(m.positions),54)
        self.assertEqual(m.skins,['models/monsters/spider/skin.png'])
        self.assertLessEqual(m.header[6],2048)
        self.assertEqual(m.command_triangles, m.header[8])
        self.assertGreater(np.ptp(m.positions[0,:,1]),np.ptp(ant.positions[0,:,1]))
        self.assertGreater(np.ptp(m.positions[0,:,0]),np.ptp(ant.positions[0,:,0]))
        for a,b in ((8,11),(20,23),(32,36),(40,42),(44,53)):
            self.assertGreater(np.max(np.linalg.norm(m.positions[a]-m.positions[b],axis=1)),1)
        for p,n in zip(m.positions,m.normals):
            t=p[m.faces]; cross=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0])
            self.assertTrue(np.all(np.einsum('ij,ij->i',cross,normal_table()[n][m.faces].mean(axis=1))<0))
            self.assertGreaterEqual(p[:,2].min(),-24.1)

    def test_front_legs_raise_then_plant_on_the_bite_frame(self):
        m = self.spider
        rest = m.positions[0]
        toes = (rest[:, 0] > 50) & (rest[:, 2] < -22.5)
        self.assertGreater(np.count_nonzero(toes), 0)
        front_feet = m.positions[:, toes, 2]
        self.assertGreater(np.min(front_feet[35] - front_feet[32]), 15)
        self.assertLess(np.max(np.abs(front_feet[36] - front_feet[32])), .5)

        fang_faces = np.all((m.uvs * 4).astype(int) == [2, 0], axis=(1, 2))
        fangs = m.positions[32:40, np.unique(m.faces[fang_faces])]
        reach = fangs[:, :, 0].max(axis=1)
        self.assertEqual(reach.argmax(), 4)
        self.assertGreater(reach[4] - reach[3], 10)

    def test_run_lengthens_the_stride_and_lifts_feet_higher(self):
        p = self.spider.positions
        feet = p[:, p[0, :, 2] < -22.5]
        walk = np.ptp(feet[8:20], axis=0).max(axis=0)
        run = np.ptp(feet[20:32], axis=0).max(axis=0)
        self.assertGreater(run[0] - walk[0], 8)
        self.assertGreater(run[2] - walk[2], 2.5)
        self.assertTrue(np.all(feet[8:32, :, 2].min(axis=1) < -23))

    def test_gib_models_are_distinct_and_have_skins(self):
        for piece in ('chunk','leg'):
            models=[]
            for creature in ('ant','spider'):
                m=MD2.read((ROOT/f'baseq2/models/objects/gibs/{creature}/{piece}.md2').read_bytes())
                self.assertEqual(m.skins,[f'models/objects/gibs/{creature}/skin.png'])
                self.assertTrue((ROOT/'baseq2'/m.skins[0]).is_file())
                models.append(m.data)
            self.assertNotEqual(*models)

if __name__=='__main__': unittest.main()
