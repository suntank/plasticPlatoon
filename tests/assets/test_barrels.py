#!/usr/bin/env python3
"""Check barrel export closure, winding, scale, ownership and reproducibility."""
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/assets'))
import build_barrels as builder
from md2_assets import MD2, normal_table


class BarrelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets,cls.manifest = builder.build_assets()
        cls.model = MD2.read(cls.assets[builder.MODEL])
        cls.mesh = builder.geometry()

    def test_reproducible_outputs_and_independent_ownership(self):
        self.assertEqual(json.loads(builder.MANIFEST.read_text()),self.manifest)
        for path,raw in self.assets.items():
            self.assertEqual((ROOT/'baseq2'/path).read_bytes(),raw)
        subprocess.run([sys.executable,'-S',str(ROOT/'tools/assets/verify_barrels_runtime.py')],check=True,capture_output=True)
        legacy = json.loads((ROOT/'tools/assets/platoon-manifest.json').read_text())
        self.assertFalse(set(self.assets)&{f['path'] for kind in ('models','textures') for f in legacy[kind]})

    def test_scale_origin_frame_and_render_budget(self):
        m = self.model
        self.assertEqual(len(m.faces),260)
        self.assertLess(len(m.faces),self.manifest['previous_runtime']['triangles']*.3)
        self.assertLess(len(m.data),self.manifest['previous_runtime']['file_bytes']*.4)
        self.assertEqual(m.command_triangles,len(m.faces))
        self.assertEqual(m.skins,[builder.TEXTURE])
        self.assertEqual(m.stats()['frame_names'],self.manifest['original']['frame_names'])
        np.testing.assert_allclose(m.positions[0].min(axis=0),[-16,-16,0],atol=.01)
        np.testing.assert_allclose(m.positions[0].max(axis=0),[16,16,39.8],atol=.01)
        self.assertTrue(np.all(m.uvs>0) and np.all(m.uvs<1))

    def test_quantized_surfaces_are_closed_and_correctly_lit(self):
        m = self.model
        points = m.positions[0]
        triangles = points[m.faces]
        cross = np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
        self.assertGreater(np.linalg.norm(cross,axis=1).min(),.1)
        stored = normal_table()[m.normals[0,m.faces]].mean(axis=1)
        # MD2 reverses authored CCW to Quake winding; stored normals stay outward.
        self.assertTrue(np.all(np.sum(cross*stored,axis=1)<0))
        for part in self.mesh['parts']:
            a = part['first_triangle']; b = a+part['triangle_count']
            edges = Counter()
            for triangle in triangles[a:b]:
                vertices = [tuple(p) for p in triangle]
                for start,end in zip(vertices,vertices[1:]+vertices[:1]):
                    edges[(start,end)] += 1
            with self.subTest(part=part['name']):
                self.assertTrue(all(count==1 and edges[(end,start)]==1
                                    for (start,end),count in edges.items()))
                self.assertLess(np.einsum('ij,ij->i',triangles[a:b,0],
                    np.cross(triangles[a:b,1],triangles[a:b,2])).sum(),0)


if __name__ == '__main__': unittest.main()
