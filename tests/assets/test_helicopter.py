#!/usr/bin/env python3
"""Inspect shipped gunship MD2s under Quake II's actual model constraints."""
from pathlib import Path
import sys
import unittest

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/assets"))
from md2_assets import MD2, normal_table

DIRECTORY = ROOT / "baseq2/models/monsters/plastic_helicopter"


class HelicopterAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models = {name: MD2.read((DIRECTORY / f"{name}.md2").read_bytes())
                      for name in ("body", "main_rotor", "tail_rotor")}

    def test_complete_models_fit_engine_limits_and_resolve_their_skin(self):
        for name, model in self.models.items():
            with self.subTest(name=name):
                self.assertGreater(model.header[6], 50)
                self.assertLessEqual(model.header[6], 2048)
                self.assertLessEqual(model.header[8], 4096)
                self.assertEqual(model.command_triangles, model.header[8])
                self.assertEqual(model.header[2:4], (256, 256))
                self.assertEqual(model.skins, ["models/monsters/plastic_helicopter/tan.png"])
                self.assertTrue((ROOT / "baseq2" / model.skins[0]).is_file())

    def test_quantized_surfaces_have_outward_lighting_and_engine_winding(self):
        # Quake II GL1/GL3 cull GL_FRONT: exterior triangle cross products must
        # oppose outward lighting normals. This also detects collapsed faces.
        for name, model in self.models.items():
            with self.subTest(name=name):
                t = model.positions[0][model.faces]
                cross = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
                light = normal_table()[model.normals[0]][model.faces].mean(axis=1)
                size = np.linalg.norm(cross, axis=1) * np.linalg.norm(light, axis=1)
                self.assertTrue(np.all(size > 0))
                self.assertTrue(np.all(np.einsum("ij,ij->i", cross, light) / size < -.5))

    def test_body_animation_slots_and_rotors_are_separate(self):
        body = self.models["body"]
        self.assertEqual(len(body.positions), 32)
        for frame in range(1, 32):
            np.testing.assert_array_equal(body.positions[frame], body.positions[0])
            np.testing.assert_array_equal(body.normals[frame], body.normals[0])
        for name in ("main_rotor", "tail_rotor"):
            self.assertEqual(len(self.models[name].positions), 1)
            self.assertNotEqual(self.models[name].data, body.data)
        # Separate models use their own spin-axis origin; their dimensions are
        # those of the rotating blades, not a baked offset from the fuselage.
        main = self.models["main_rotor"].positions[0]
        tail = self.models["tail_rotor"].positions[0]
        np.testing.assert_allclose(main[:, :2].min(axis=0), [-92, -92], atol=.001)
        np.testing.assert_allclose(main[:, :2].max(axis=0), [92, 92], atol=.001)
        self.assertLess(np.ptp(main[:, 2]), 6)
        np.testing.assert_allclose(tail[:, [0, 2]].min(axis=0), [-17, -17], atol=.001)
        np.testing.assert_allclose(tail[:, [0, 2]].max(axis=0), [17, 17], atol=.001)
        self.assertLess(np.ptp(tail[:, 1]), 5)

    def test_gun_and_seven_tube_launcher_caps_match_gameplay_muzzles(self):
        model = self.models["body"]
        t = model.positions[0][model.faces]
        normals = normal_table()[model.normals[0]][model.faces].mean(axis=1)
        tiles = np.floor(model.uvs.mean(axis=1) * 4).astype(int)
        port = (tiles[:, 1] * 4 + tiles[:, 0] == 11) & (normals[:, 0] > .9)
        # Each actual tube mouth is a six-corner polygon (four triangles).
        # Test the exported caps so a changed mesh cannot silently leave the
        # projectile emerging from a missing tube or the helicopter's center.
        for side in (-1, 1):
            launcher = np.flatnonzero(port & (abs(t[:, :, 0].mean(axis=1) - 30) < .4)
                                     & (t[:, :, 1].mean(axis=1) * side > 35))
            self.assertEqual(len(launcher), 7 * 4)
            mouth_groups = []
            for face in model.faces[launcher]:
                face = set(int(v) for v in face)
                for group in mouth_groups:
                    if group.intersection(face):
                        group.update(face)
                        break
                else:
                    mouth_groups.append(face)
            self.assertEqual(len(mouth_groups), 7)
            centers = np.array([model.positions[0][sorted(group)].mean(axis=0)
                                for group in mouth_groups])
            np.testing.assert_allclose(centers.mean(axis=0), [30, side * 46, -2], atol=.4)
            guns = np.flatnonzero(port & (abs(t[:, :, 0].mean(axis=1) - 64) < .4)
                                 & (abs(t[:, :, 1].mean(axis=1) - side * 24) < 4))
            self.assertEqual(len(guns), 6)  # Eight-corner barrel mouth.
            center = model.positions[0][np.unique(model.faces[guns])].mean(axis=0)
            np.testing.assert_allclose(center, [64, side * 24, -10], atol=.4)

    def test_tan_materials_match_the_tank(self):
        helicopter = np.array(Image.open(DIRECTORY / "tan.png").convert("RGB"))
        tank = np.array(Image.open(ROOT / "baseq2/models/monsters/plastic_tank/tan.png").convert("RGB"))
        # The single glazing tile is the only material changed from the tank.
        changed = np.any(helicopter != tank, axis=2)
        permitted = np.zeros((256, 256), dtype=bool)
        permitted[:64, 192:] = True
        self.assertTrue(changed.any())
        self.assertFalse(np.any(changed & ~permitted))
        self.assertLess(helicopter[32, 224].mean(), helicopter[32, 32].mean())


if __name__ == "__main__":
    unittest.main(verbosity=2)
