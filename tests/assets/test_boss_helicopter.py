#!/usr/bin/env python3
"""Validate armored boss export, bores, clearance, colors and retained legacy files."""
from collections import Counter
import io,json,sys,unittest,subprocess
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools/assets'))
import build_boss_helicopter as b
from md2_assets import MD2,normal_table
from build_color_variants import material_mask,variant_path


class BossHelicopter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.assets,cls.manifest=b.build_assets()

    def test_assets_are_reproducible_and_all_skin_paths_fit(self):
        self.assertEqual(json.loads(b.MANIFEST.read_text()),self.manifest)
        for name,raw in self.assets.items():self.assertEqual((ROOT/'baseq2'/name).read_bytes(),raw)
        for name,kind in b.MODELS.items():
            m=MD2.read(self.assets[name]);self.assertEqual(m.skins,b.SKINS if kind=='body' else b.SKINS[:1])
            for i in range(len(m.skins)):self.assertLess(len(variant_path(name,'red',i)),64)
        subprocess.run([sys.executable,'-S',str(ROOT/'tools/assets/verify_boss_helicopter_runtime.py')],check=True,capture_output=True)

    def test_closed_quantized_surfaces_normals_and_clearance(self):
        total=0
        for entry in self.manifest['models']:
            m=MD2.read(self.assets[entry['path']]);total+=len(m.faces)
            self.assertEqual(m.command_triangles,len(m.faces));self.assertEqual(len(m.positions),1)
            t=m.positions[0,m.faces];cross=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0])
            n=normal_table()[m.normals[0,m.faces]].mean(axis=1)
            self.assertTrue(np.all(np.sum(cross*n,axis=1)<0))
            self.assertGreater(np.linalg.norm(cross,axis=1).min(),1e-6)
            for part in entry['parts']:
                a=part['first_triangle'];z=a+part['triangle_count'];edges=Counter()
                for tri in t[a:z]:
                    p=[tuple(v) for v in tri]
                    for x,y in zip(p,p[1:]+p[:1]):edges[(x,y)]+=1
                self.assertTrue(all(count==1 and edges[(y,x)]==1 for (x,y),count in edges.items()),part['name'])
            low,high=m.stats()['bounds']
            if entry['kind']=='body':
                self.assertTrue(np.all(np.array(low)>=[-114,-50,36]))
                self.assertTrue(np.all(np.array(high)<=[68,50,96]))
                anchors=entry['anchors'];self.assertEqual(anchors['guns'],[[60,-15,50],[60,15,50]])
                self.assertEqual(anchors['rockets'],[[0,45,45],[0,40,45],[0,-40,45],[0,-45,45]])
                mouths=[p for p in entry['parts'] if p['name'].startswith(('heavy_cannon','rocket_tube'))]
                self.assertEqual(len(mouths),6)
        self.assertEqual(total,992);self.assertLess(total,self.manifest['baseline_triangles']*.34)

    def test_red_paint_glass_mechanics_and_boss_markings(self):
        for name in b.SKINS:
            image=Image.open(io.BytesIO(self.assets[name]));mask,_=material_mask(image,name,'enemy')
            red,green,blue=image.getpixel((50,20));self.assertGreater(red,green*2)
            self.assertEqual(mask.getpixel((50,20)),255)
            self.assertEqual(mask.getpixel((220,20)),0) # Dark cockpit.
            self.assertEqual(mask.getpixel((140,145)),0) # Pale boss chevron.
            self.assertEqual(mask.getpixel((150,87)),0) # Black vent detail.
        self.assertNotEqual(self.assets[b.SKINS[0]],self.assets[b.SKINS[1]])
        subprocess.run([sys.executable,'-S',str(ROOT/'tools/assets/verify_dropship_runtime.py')],check=True,capture_output=True)


if __name__=='__main__':unittest.main()
