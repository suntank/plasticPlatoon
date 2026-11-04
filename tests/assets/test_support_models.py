#!/usr/bin/env python3
"""Check support-model winding, frame ranges and effect dependency closure."""
import importlib.util
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/assets'))
from build_overlay import check_image_dependencies

SPEC = importlib.util.spec_from_file_location('support_models', ROOT / 'tools/assets/build_support_models.py')
support = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(support)


class SupportModelsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets, cls.manifest = support.build_assets()

    def test_all_model_and_sprite_images_resolve_in_generated_assets(self):
        references = check_image_dependencies(self.assets)
        self.assertEqual(references['external_images'], [])
        self.assertGreaterEqual(references['image_references'], 21)

    def test_md2_tables_and_commands_preserve_clockwise_exterior_winding(self):
        directions = {value: key for key, value in support.NORMALS.items()}
        for name, data in self.assets.items():
            if not name.endswith('.md2'):
                continue
            with self.subTest(model=name):
                h = struct.unpack_from('<17i', data)
                self.assertEqual(h[:2], (844121161, 8))
                self.assertEqual(h[16], len(data))
                self.assertLessEqual(h[6], 2048)
                scale = struct.unpack_from('<3f', data, h[14])
                translation = struct.unpack_from('<3f', data, h[14] + 12)
                vertices = [struct.unpack_from('<4B', data, h[14] + 40 + i * 4) for i in range(h[6])]
                points = [tuple(v[a] * scale[a] + translation[a] for a in range(3)) for v in vertices]
                command = h[15]
                for i in range(h[8]):
                    face = struct.unpack_from('<6H', data, h[13] + i * 12)
                    self.assertTrue(all(index < h[6] for index in face[:3]))
                    self.assertEqual(struct.unpack_from('<i', data, command)[0], 3)
                    command += 4
                    command_face = []
                    for _ in range(3):
                        u, v, index = struct.unpack_from('<ffi', data, command)
                        command += 12
                        self.assertTrue(0 <= u <= 1 and 0 <= v <= 1)
                        command_face.append(index)
                    self.assertEqual(tuple(command_face), face[:3])
                    a, b, c = (points[index] for index in face[:3])
                    first, second = [b[j] - a[j] for j in range(3)], [c[j] - a[j] for j in range(3)]
                    cross = (first[1] * second[2] - first[2] * second[1],
                             first[2] * second[0] - first[0] * second[2],
                             first[0] * second[1] - first[1] * second[0])
                    normal = directions[vertices[face[0]][3]]
                    self.assertLess(sum(a * b for a, b in zip(cross, normal)), -1e-6)
                self.assertEqual(struct.unpack_from('<i', data, command)[0], 0)
                self.assertEqual(command + 4, len(data))

    def test_grenade_and_bfg_effects_cover_game_requested_frames(self):
        grenade = struct.unpack_from('<17i', self.assets['models/weapons/v_handgr/tris.md2'])
        self.assertGreaterEqual(grenade[10], 49)
        # Weapon_Grenade advances through48; bfg_explode reaches frame5 before
        # freeing next tick; the client BFG explosion asks for4 frames.
        for path, minimum in (('sprites/s_bfg2.sp2', 4), ('sprites/s_bfg3.sp2', 6)):
            data = self.assets[path]
            ident, version, count = struct.unpack_from('<3i', data)
            self.assertEqual((ident, version), (844317769, 2))
            self.assertGreaterEqual(count, minimum)
            self.assertEqual(len(data), 12 + count * 80)

    def test_truecolor_textures_have_complete_rgba_payloads(self):
        for name, data in self.assets.items():
            if not name.endswith('.tga'):
                continue
            with self.subTest(image=name):
                self.assertEqual(data[:3], bytes((0, 0, 2)))
                width, height, depth, descriptor = struct.unpack_from('<HHBB', data, 12)
                self.assertEqual((depth, descriptor), (32, 40))
                self.assertEqual(len(data), 18 + width * height * 4)
                alpha = data[21::4]
                self.assertTrue(any(a > 0 for a in alpha))
                if name.startswith('sprites/') or name == 'pics/k_powercube.tga':
                    self.assertIn(0, alpha)


if __name__ == '__main__':
    unittest.main()
