#!/usr/bin/env python3
"""Verify all fragment shapes, source placement, export closure and color contracts."""
from collections import Counter
import io,json,subprocess,sys,unittest
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/assets'))
import build_body_parts as b
from md2_assets import MD2,normal_table
from build_color_variants import material_mask


class BodyParts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.assets,cls.manifest=b.build_assets()

    def test_outputs_source_backup_and_ownership(self):
        self.assertEqual(json.loads(b.MANIFEST.read_text()),self.manifest)
        self.assertEqual(len(self.assets),39)
        for path,raw in self.assets.items():self.assertEqual((ROOT/'baseq2'/path).read_bytes(),raw,path)
        subprocess.run([sys.executable,'-S',str(ROOT/'tools/assets/verify_body_parts_runtime.py')],check=True,capture_output=True)
        legacy=json.loads((ROOT/'tools/assets/platoon-manifest.json').read_text())
        self.assertFalse(set(self.assets)&{f['path'] for key in ('models','textures') for f in legacy[key]})

    def test_every_mesh_preserves_extent_frame_and_has_closed_outward_surfaces(self):
        for entry in self.manifest['models']:
            with self.subTest(kind=entry['kind']):
                m=MD2.read(self.assets[entry['path']]);points=m.positions[0];triangles=points[m.faces]
                self.assertLess(len(m.faces),entry['before']['triangles'])
                self.assertLessEqual(len(m.faces),160)
                self.assertEqual(m.command_triangles,len(m.faces))
                self.assertEqual(m.stats()['frame_names'],entry['before']['frame_names'])
                np.testing.assert_allclose(m.stats()['bounds'],entry['before']['bounds'],atol=1e-5)
                crossed=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
                self.assertGreater(np.linalg.norm(crossed,axis=1).min(),1e-6)
                normals=normal_table()[m.normals[0,m.faces]].mean(axis=1)
                self.assertTrue(np.all(np.sum(crossed*normals,axis=1)<0))
                for part in entry['parts']:
                    first=part['first_triangle'];last=first+part['triangle_count'];edges=Counter()
                    for tri in triangles[first:last]:
                        p=[tuple(v) for v in tri]
                        for a,z in zip(p,p[1:]+p[:1]):edges[(a,z)]+=1
                    self.assertTrue(all(count==1 and edges[(z,a)]==1 for (a,z),count in edges.items()),part['name'])

    def test_color_layouts_keep_player_green_and_insect_wounds(self):
        for species in ('ant','spider'):
            path=f'models/objects/gibs/{species}/skin.png'
            image=Image.open(io.BytesIO(self.assets[path]));mask,_=material_mask(image,path,'enemy')
            self.assertEqual(mask.getpixel((20,20)),255)
            self.assertEqual(mask.getpixel((210,20)),0)
        for kind in b.KINDS:
            path=f'models/objects/gibs/{kind}/player.png'
            image=Image.open(io.BytesIO(self.assets[path]));r,g,blue=image.getpixel((20,20))
            self.assertGreater(g,r);self.assertGreater(g,blue)


if __name__=='__main__':unittest.main()
