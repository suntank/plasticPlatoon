#!/usr/bin/env python3
"""Validate seven original ammo shapes, legible case labels and LOD identity."""
from collections import Counter
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
import zipfile

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/assets'))
import build_ammo as builder
from ammo_geometry import build_ammo, KINDS, LABELS, REGIONS
from asset_sources import source_bytes
from md2_assets import MD2, normal_table


class AmmoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets, cls.manifest = builder.build_assets()
        cls.meshes = {kind: build_ammo(kind) for kind in KINDS}
        cls.originals = json.loads((ROOT / 'tools/assets/platoon-originals.json').read_text())
        cls.models = {kind: MD2.read(cls.assets[path]) for path, kind in builder.MODELS.items()}

    @staticmethod
    def part(mesh, name):
        return next(part for part in mesh['parts'] if part['name'] == name)

    @classmethod
    def part_points(cls, mesh, name):
        part = cls.part(mesh, name)
        a = part['first_triangle']; b = a + part['triangle_count']
        return np.asarray(mesh['vertices'])[np.asarray(mesh['faces'])[a:b]].reshape(-1, 3)

    def test_exact_assets_manifest_dependency_hashes_and_standard_library_gate(self):
        self.assertEqual(len(self.assets), 17)
        inventory = {entry['path']: entry for entry in self.manifest['files']}
        self.assertEqual(set(inventory), set(self.assets))
        self.assertEqual(json.loads(builder.MANIFEST.read_text()), self.manifest)
        for path, raw in self.assets.items():
            with self.subTest(path=path):
                self.assertEqual((ROOT / 'baseq2' / path).read_bytes(), raw)
                self.assertEqual(inventory[path]['bytes'], len(raw))
                self.assertEqual(inventory[path]['sha256'], builder.sha(raw))
        for name, digest in self.manifest['dependencies_sha256'].items():
            self.assertEqual(builder.sha((ROOT / 'tools/assets' / name).read_bytes()), digest)
        subprocess.run([sys.executable, '-S', str(ROOT / 'tools/assets/verify_ammo_runtime.py')],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def test_seven_static_models_reduce_original_budgets_and_preserve_frame_names(self):
        counts = {'shells': 116, 'bullets': 116, 'grenades': 148, 'gl_ammo': 76,
                  'rockets': 128, 'cells': 180, 'slugs': 200}
        self.assertEqual(set(builder.MODELS.values()), set(KINDS))
        for path, kind in builder.MODELS.items():
            model = self.models[kind]
            source = MD2.read(source_bytes(self.originals, 'baseq2/' + path), source_compat=True)
            with self.subTest(kind=kind):
                self.assertEqual(len(model.faces), counts[kind])
                self.assertLessEqual(len(model.faces), 200)
                self.assertLess(len(model.faces), builder.BASELINES[kind]['triangles'])
                self.assertEqual(model.names, source.names)
                self.assertEqual(model.header[10], 1)
                self.assertEqual(model.header[4], 40 + 4 * model.header[6])
                self.assertEqual(model.command_triangles, len(model.faces))
                self.assertEqual(model.skins, [builder.TEXTURES[kind]])
                self.assertTrue(np.all(model.uvs > 0))
                self.assertTrue(np.all(model.uvs < 1))
                # Keep the original pickup's scale and floor placement while
                # allowing the new handle, lever and fins to define its shape.
                original = source.positions[0]
                span = np.ptp(original, axis=0)
                self.assertTrue(np.all(model.positions[0].min(axis=0) >= original.min(axis=0) - span * .12))
                self.assertTrue(np.all(model.positions[0].max(axis=0) <= original.max(axis=0) + span * .12))
                self.assertAlmostEqual(model.positions[0, :, 2].min(), original[:, 2].min(), delta=.65)

    def test_all_parts_are_closed_after_quantization_with_correct_winding(self):
        for kind, model in self.models.items():
            mesh = self.meshes[kind]
            points = model.positions[0]
            ideal = np.asarray(mesh['vertices'])
            limit = np.linalg.norm(model.scales[0]) / 2 + 1e-5
            self.assertLessEqual(np.linalg.norm(points - ideal, axis=1).max(), limit)
            triangles = points[model.faces]
            crossed = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
            target = ideal[model.faces]
            target_crossed = np.cross(target[:, 1] - target[:, 0], target[:, 2] - target[:, 0])
            self.assertGreater(np.linalg.norm(crossed, axis=1).min(), 1e-8)
            self.assertTrue(np.all(np.sum(crossed * target_crossed, axis=1) > 0))
            stored = normal_table()[model.normals[0, model.faces]].mean(axis=1)
            unit = crossed / np.linalg.norm(crossed, axis=1)[:, None]
            self.assertLess(np.median(np.sum(unit * stored, axis=1)), -.65)
            for part in mesh['parts']:
                a = part['first_triangle']; b = a + part['triangle_count']
                edges = Counter()
                for face in model.faces[a:b]:
                    corners = [tuple(points[index]) for index in face]
                    for start, end in zip(corners, corners[1:] + corners[:1]):
                        edges[tuple(sorted((start, end)))] += 1
                with self.subTest(kind=kind, part=part['name']):
                    self.assertTrue(edges)
                    self.assertTrue(all(count == 2 for count in edges.values()))

    def test_shell_and_bullet_cases_have_open_handles_closed_lids_latches_and_rails(self):
        for kind in ('shells', 'bullets'):
            mesh = self.meshes[kind]
            self.assertEqual({part['name'] for part in mesh['parts']},
                             {'case_body', 'lid_seam', 'case_lid', 'latch_left', 'latch_right',
                              'carry_handle', 'base_rail_front', 'base_rail_rear'})
            handle = self.part_points(mesh, 'carry_handle')
            lid = self.part_points(mesh, 'case_lid')
            body = self.part_points(mesh, 'case_body')
            self.assertGreater(handle[:, 2].max(), lid[:, 2].max() + 3.)
            self.assertGreater(lid[:, 2].min(), body[:, 2].max())
            # A ring must leave a real hole rather than being a painted block.
            part = self.part(mesh, 'carry_handle')
            self.assertEqual(part['triangle_count'], 32)
            self.assertGreater(np.unique(handle[:, 0]).size, 2)
            self.assertGreater(np.unique(handle[:, 2]).size, 2)

    def test_shell_and_bullet_lettering_faces_both_sides_and_lid_without_mirroring(self):
        for kind in ('shells', 'bullets'):
            mesh, model = self.meshes[kind], self.models[kind]
            triangles = model.positions[0, model.faces]
            for sign in (-1, 1):
                material = np.asarray(mesh['materials']) == 'label'
                mask = material & (np.sign(triangles.mean(axis=1)[:, 1]) == sign)
                self.assertEqual(mask.sum(), 2)
                points, uvs = triangles[mask].reshape(-1, 3), model.uvs[mask].reshape(-1, 2)
                design = np.column_stack((points[:, 0], points[:, 2], np.ones(len(points))))
                coefficients = np.linalg.lstsq(design, uvs, rcond=None)[0]
                self.assertGreater(coefficients[0, 0] * -sign, 0.)
                self.assertLess(coefficients[1, 1], 0.)
                self.assertLess(np.abs(design @ coefficients - uvs).max(), .001)
            mask = np.asarray(mesh['materials']) == 'lid_label'
            self.assertEqual(mask.sum(), 2)
            points, uvs = triangles[mask].reshape(-1, 3), model.uvs[mask].reshape(-1, 2)
            coefficients = np.linalg.lstsq(np.column_stack((points[:, :2], np.ones(len(points)))), uvs, rcond=None)[0]
            self.assertGreater(coefficients[0, 0], 0.)
            self.assertLess(coefficients[1, 1], 0.)

    def test_label_atlases_contain_exact_high_contrast_readable_stencil_letters(self):
        for kind in KINDS:
            image = np.asarray(Image.open(io.BytesIO(self.assets[builder.TEXTURES[kind]])))
            self.assertEqual(image.shape, (256, 256, 3))
            for material in ('label', 'lid_label'):
                x, y, X, Y = REGIONS[material]
                text = LABELS[kind]
                columns = len(text) * 6 - 1
                scale = min((X - x - 18) // columns, (Y - y - 16) // 7)
                left = (X - x - columns * scale) // 2
                top = (Y - y - 7 * scale) // 2
                expected = np.zeros((Y - y, X - x), dtype=bool)
                for index, letter in enumerate(text):
                    for row, bits in enumerate(builder.GLYPHS[letter]):
                        for col, on in enumerate(bits):
                            if on == '1':
                                a, b = left + (index * 6 + col) * scale, top + row * scale
                                expected[b:b + scale, a:a + scale] = True
                actual = np.all(image[y:Y, x:X] == builder.LETTER_COLOR, axis=2)
                with self.subTest(kind=kind, material=material):
                    self.assertGreater(scale, 1)
                    np.testing.assert_array_equal(actual, expected)
                    self.assertGreater(image[y:Y, x:X][expected].mean() - image[y:Y, x:X][~expected].mean(), 100.)

    def test_five_other_ammo_shapes_have_distinct_functional_details(self):
        names = {kind: {part['name'] for part in mesh['parts']} for kind, mesh in self.meshes.items()}
        self.assertTrue({'grenade_body', 'fuse', 'safety_lever', 'pull_ring'} <= names['grenades'])
        self.assertEqual(names['gl_ammo'], {'launcher_round'})
        self.assertTrue({'rocket_body', 'rocket_nozzle'} | {'rocket_fin_' + str(i) for i in range(4)} <= names['rockets'])
        self.assertTrue({'fuel_tank_left', 'fuel_tank_right', 'tank_manifold', 'tank_label_strap'} <= names['cells'])
        self.assertTrue({'rounds_clip', 'clip_back'} | {'sniper_round_' + str(i) for i in range(4)} <= names['slugs'])
        for i in range(4):
            points = self.part_points(self.meshes['rockets'], 'rocket_fin_' + str(i))
            self.assertGreater(np.linalg.norm(points[:, :2], axis=1).max(), 2.6)
            self.assertGreater(np.ptp(points[:, 2]), 4.)
        self.assertGreater(self.part_points(self.meshes['cells'], 'fuel_tank_left')[:, 1].mean(), 2.)
        self.assertLess(self.part_points(self.meshes['cells'], 'fuel_tank_right')[:, 1].mean(), -2.)

    def test_near_and_far_ammo_identity_and_registered_ownership(self):
        import build_platoon
        config = json.loads(build_platoon.CONFIG.read_text())
        registration = config['procedural_replacements']['ammo']
        self.assertEqual(set(registration['models'] + registration['textures']), set(self.assets))
        self.assertEqual(set(registration['textures']), set(builder.TEXTURES.values()))
        self.assertTrue(set(registration['models']) <= build_platoon.procedural_paths(config))
        legacy = json.loads(build_platoon.MANIFEST.read_text())
        self.assertFalse(set(registration['models']) & {entry['path'] for entry in legacy['models']})
        for kind in builder.LOD_KINDS:
            path = f'models/items/ammo/{kind}/medium/tris.md2'
            self.assertEqual(self.assets[path], self.assets[path.replace('/tris.md2', '/lod1.md2')])

    def test_projectiles_hand_grenade_and_shared_rocket_skin_are_isolated(self):
        self.assertEqual(builder.TEXTURES['rockets'], 'models/items/ammo/rockets/medium/skin_ammo.png')
        # Flying projectiles have their own authored owner and regression
        # suite. The ammo builder must never overwrite them or the hand view.
        for name in ('models/objects/rocket/tris.md2', 'models/objects/grenade/tris.md2',
                     'models/objects/grenade2/tris.md2', 'models/weapons/v_handgr/tris.md2'):
            self.assertNotIn(name, self.assets)
        hand = (ROOT / 'baseq2/models/weapons/v_handgr/tris.md2').read_bytes()
        self.assertEqual(builder.sha(hand), '9b74b53a1729ec04921ea4c9e142f3494ab15683e557c47269e1da2d6fdbb32f')
        pickups = json.loads((ROOT / 'tools/assets/pickups.json').read_text())
        with zipfile.ZipFile(ROOT / pickups['source_archive']['path']) as archive:
            path = 'models/items/ammo/rockets/medium/skin.png'
            self.assertNotIn(path, self.assets)
            raw = (ROOT / 'baseq2' / path).read_bytes()
            self.assertEqual(builder.sha(raw), '9cc6122b646e70b0bfde420163bfaa8fed18b6671143da6721189593b9448b72')
            original = Image.open(io.BytesIO(archive.read('baseq2/' + path)))
            original.thumbnail((256, 256), Image.Resampling.LANCZOS)
            np.testing.assert_array_equal(np.asarray(Image.open(io.BytesIO(raw))), np.asarray(original))


if __name__ == '__main__':
    unittest.main()
