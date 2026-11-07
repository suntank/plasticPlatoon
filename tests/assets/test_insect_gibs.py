"""Ensure each insect's organic fragments ship as valid distinct MD2 assets."""
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/assets'))
from md2_assets import MD2, normal_table


class InsectGibAssets(unittest.TestCase):
    def test_models_have_valid_winding_and_distinct_species_skins(self):
        for species in ('ant', 'spider'):
            for part in ('chunk', 'leg'):
                with self.subTest(species=species, part=part):
                    directory = f'models/objects/gibs/{species}'
                    model = MD2.read((ROOT/'baseq2'/directory/f'{part}.md2').read_bytes())
                    self.assertEqual(model.skins, [f'{directory}/skin.png'])
                    self.assertTrue((ROOT/'baseq2'/model.skins[0]).is_file())
                    self.assertEqual(len(model.positions), 1)
                    triangles = model.positions[0][model.faces]
                    cross = np.cross(triangles[:,1]-triangles[:,0], triangles[:,2]-triangles[:,0])
                    normals = normal_table()[model.normals[0]][model.faces].mean(axis=1)
                    self.assertTrue(np.all(np.einsum('ij,ij->i', cross, normals) < 0))
        ant = (ROOT/'baseq2/models/objects/gibs/ant/skin.png').read_bytes()
        spider = (ROOT/'baseq2/models/objects/gibs/spider/skin.png').read_bytes()
        self.assertNotEqual(ant, spider)


if __name__ == '__main__': unittest.main()
