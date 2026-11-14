#!/usr/bin/env python3
"""No open boundaries or reversed faces in either weapon's exported hands."""
from collections import Counter
from pathlib import Path
import struct
import sys
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/assets'))
from md2_assets import MD2
from m16_geometry import build_m16
from pistol_geometry import build_pistol


class HandSurfaceTests(unittest.TestCase):
    def test_pistol_wrist_gap_does_not_show_the_background(self):
        from build_pistol import placement
        model = MD2.read((ROOT/'baseq2/models/weapons/v_blast/tris.md2').read_bytes())
        geometry = build_pistol('view')
        # Restrict hits to the wrist/hand assembly: a gun surface behind an
        # actual wrist opening must not accidentally make the check pass.
        faces = np.array([struct.unpack_from('<3H',model.data,model.header[13]+12*i)
                          for i in range(model.header[8])])
        ids = [i for part in geometry['parts']
               if part['name'].startswith(('arm_','hand_','cuff_'))
               for i in range(part['first_triangle'],part['first_triangle']+part['triangle_count'])]
        triangles = model.positions[0,faces[ids]]
        e1 = triangles[:,1]-triangles[:,0]
        e2 = triangles[:,2]-triangles[:,0]
        matrix,offset,_ = placement('view')
        # The wrist now meets the rounded heel behind the grip, rather than
        # entering the handle's center. Straddle that rear cuff/heel junction.
        for point in ((25.3,-1.0,-8.9),(25.6,-.8,-8.5),(26,-.5,-8.0)):
            with self.subTest(wrist_point=point):
                ray = np.asarray(point)@matrix+offset
                p = np.cross(ray,e2); determinant = np.sum(e1*p,axis=1)
                valid = np.abs(determinant)>1e-10
                inverse = np.zeros_like(determinant)
                inverse[valid] = 1/determinant[valid]
                t = -triangles[:,0]
                u = np.sum(t*p,axis=1)*inverse
                q = np.cross(t,e1)
                v = np.sum(ray*q,axis=1)*inverse
                distance = np.sum(e2*q,axis=1)*inverse
                self.assertTrue(np.any(valid & (u>=0) & (v>=0) &
                                       (u+v<=1) & (distance>0)),
                                'background visible through wrist connection')

    def test_every_hand_component_is_closed_in_the_exported_viewmodel(self):
        for name, geometry, path in (
            ('M16',build_m16('view'),'models/weapons/v_machn/tris.md2'),
            ('Pistol',build_pistol('view'),'models/weapons/v_blast/tris.md2')):
            model = MD2.read((ROOT/'baseq2'/path).read_bytes())
            # The MD2 triangle table retains source-part ordering. Its GL
            # command stream may reorder triangles for rendering strips.
            faces = np.array([struct.unpack_from('<3H',model.data,model.header[13]+12*i)
                              for i in range(model.header[8])])
            for part in geometry['parts']:
                if not part['name'].startswith(('arm_','hand_','cuff_')):
                    continue
                with self.subTest(weapon=name, part=part['name']):
                    start = part['first_triangle']; stop = start+part['triangle_count']
                    directed = Counter()
                    for face in faces[start:stop]:
                        points = [tuple(model.positions[0,i]) for i in face]
                        for a,b in zip(points,points[1:]+points[:1]):
                            directed[(a,b)] += 1
                    self.assertTrue(directed)
                    # Geometrically weld UV/normal seams and require each
                    # edge once in each direction, including both limb caps.
                    for (a,b),count in directed.items():
                        self.assertEqual(count,1,'nonmanifold or doubled edge')
                        self.assertEqual(directed[(b,a)],1,'open or reversed face')


if __name__=='__main__':
    unittest.main(verbosity=2)
