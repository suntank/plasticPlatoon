#!/usr/bin/env python3
"""Validate authored medical pickups, medical markings and unchanged contracts."""
from collections import Counter
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest
import zipfile

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/assets'))
import build_health as builder
from asset_sources import source_bytes
from health_geometry import build_health, KINDS, LABELS, REGIONS
from md2_assets import MD2, normal_table


def function_text(source, name):
    start = re.search(r'\n' + re.escape(name) + r'\([^;]+?\)\s*\{', source).end()
    depth = 1
    for end in range(start, len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if depth == 0:
            return source[start:end]
    raise ValueError('Unterminated production function: ' + name)


class HealthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets, cls.manifest = builder.build_assets()
        cls.meshes = {kind: build_health(kind) for kind in KINDS}
        cls.models = {kind: MD2.read(cls.assets[path]) for path, kind in builder.MODELS.items()}
        cls.pickups = json.loads((ROOT / 'tools/assets/pickups.json').read_text())

    @staticmethod
    def part(mesh, name):
        return next(part for part in mesh['parts'] if part['name'] == name)

    @classmethod
    def part_points(cls, mesh, name):
        part = cls.part(mesh, name)
        a = part['first_triangle']; b = a + part['triangle_count']
        return np.asarray(mesh['vertices'])[np.asarray(mesh['faces'])[a:b]].reshape(-1, 3)

    def test_exact_eleven_assets_manifest_dependency_hashes_and_standard_library_gate(self):
        self.assertEqual(len(self.assets), 11)
        self.assertEqual(json.loads(builder.MANIFEST.read_text()), self.manifest)
        inventory = {entry['path']: entry for entry in self.manifest['files']}
        self.assertEqual(set(inventory), set(self.assets))
        for name, raw in self.assets.items():
            with self.subTest(path=name):
                self.assertEqual((ROOT / 'baseq2' / name).read_bytes(), raw)
                self.assertEqual(inventory[name]['bytes'], len(raw))
                self.assertEqual(inventory[name]['sha256'], builder.sha(raw))
        for name, digest in self.manifest['dependencies_sha256'].items():
            self.assertEqual(builder.sha((ROOT / 'tools/assets' / name).read_bytes()), digest)
        subprocess.run([sys.executable, '-S', str(ROOT / 'tools/assets/verify_health_runtime.py')],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def test_five_static_models_reduce_original_budgets_and_preserve_frame_names_and_scale(self):
        counts = {'stimpack': 128, 'medium': 80, 'large': 124, 'mega': 128, 'adrenaline': 124}
        self.assertEqual(set(builder.MODELS.values()), set(KINDS))
        for entry in self.manifest['models']:
            kind = entry['kind']; model = self.models[kind]
            source = MD2.read(source_bytes(self.pickups, 'baseq2/' + entry['source_frame_from']), source_compat=True)
            with self.subTest(kind=kind):
                self.assertEqual(len(model.faces), counts[kind])
                self.assertLessEqual(len(model.faces), 180)
                self.assertLess(len(model.faces), entry['baseline']['triangles'])
                self.assertLess(len(model.data), entry['baseline']['file_bytes'])
                self.assertEqual(model.names, source.names)
                self.assertEqual(model.header[10], 1)
                self.assertEqual(model.header[4], 40 + 4 * model.header[6])
                self.assertEqual(model.command_triangles, len(model.faces))
                self.assertEqual(model.skins, [builder.TEXTURES[kind]])
                self.assertTrue(np.all(model.uvs > 0) and np.all(model.uvs < 1))
                old = source.positions[0]; points = model.positions[0]; span = np.ptp(old, axis=0)
                self.assertTrue(np.all(points.min(axis=0) >= old.min(axis=0) - span * .12))
                self.assertTrue(np.all(points.max(axis=0) <= old.max(axis=0) + span * .12))
                self.assertAlmostEqual(points[:, 2].min(), old[:, 2].min(), delta=.7)
                self.assertAlmostEqual(points[:, 2].max(), old[:, 2].max(), delta=.8)

    def test_every_quantized_part_is_closed_nondegenerate_and_has_outward_normals(self):
        for kind, model in self.models.items():
            mesh = self.meshes[kind]
            points, ideal = model.positions[0], np.asarray(mesh['vertices'])
            self.assertLessEqual(np.linalg.norm(points - ideal, axis=1).max(), np.linalg.norm(model.scales[0]) / 2 + 1e-5)
            actual, expected = points[model.faces], ideal[model.faces]
            crossed = np.cross(actual[:, 1] - actual[:, 0], actual[:, 2] - actual[:, 0])
            reference = np.cross(expected[:, 1] - expected[:, 0], expected[:, 2] - expected[:, 0])
            self.assertGreater(np.linalg.norm(crossed, axis=1).min(), 1e-8)
            self.assertTrue(np.all(np.sum(crossed * reference, axis=1) > 0))
            stored = normal_table()[model.normals[0, model.faces]].mean(axis=1)
            crossed /= np.linalg.norm(crossed, axis=1)[:, None]
            self.assertLess(np.median(np.sum(crossed * stored, axis=1)), -.65)
            for part in mesh['parts']:
                a = part['first_triangle']; b = a + part['triangle_count']; edges = Counter()
                for face in model.faces[a:b]:
                    corners = [tuple(points[index]) for index in face]
                    for start, end in zip(corners, corners[1:] + corners[:1]):
                        edges[tuple(sorted((start, end)))] += 1
                with self.subTest(kind=kind, part=part['name']):
                    self.assertTrue(edges)
                    self.assertTrue(all(count == 2 for count in edges.values()))

    def test_distinct_injector_bandages_medkit_and_mega_shapes_keep_real_details(self):
        names = {kind: {part['name'] for part in mesh['parts']} for kind, mesh in self.meshes.items()}
        self.assertEqual(names['stimpack'], {'needle', 'nozzle', 'injector_barrel', 'finger_flange', 'plunger_stem', 'thumb_pad'})
        self.assertEqual(names['medium'], {'bandage_roll_front', 'bandage_roll_rear', 'bundle_strap', 'medical_patch'})
        self.assertTrue({'case_body', 'case_lid', 'lid_seam', 'carry_handle', 'latch_left', 'latch_right'} <= names['large'])
        self.assertTrue({'medical_canister', 'base_rim', 'sealed_lid', 'lid_marking', 'carry_handle'} <= names['mega'])
        for kind in ('large', 'adrenaline', 'mega'):
            self.assertEqual(self.part(self.meshes[kind], 'carry_handle')['triangle_count'], 32)
            handle = self.part_points(self.meshes[kind], 'carry_handle')
            self.assertGreater(np.unique(handle[:, 0]).size, 2)
            self.assertGreater(np.unique(handle[:, 2]).size, 2)
        needle = self.part_points(self.meshes['stimpack'], 'needle')
        self.assertGreater(np.linalg.norm(needle[:, :2], axis=1).min(), .2)
        self.assertLess(np.linalg.norm(needle[:, :2], axis=1).max(), .3)
        self.assertAlmostEqual(needle[:, 2].min(), 0.)
        for name, sign in (('bandage_roll_front', -1), ('bandage_roll_rear', 1)):
            roll = self.part_points(self.meshes['medium'], name)
            self.assertAlmostEqual(np.ptp(roll[:, 0]), 15.)
            self.assertGreater(roll[:, 1].mean() * sign, 2.)
        for name in names['large']:
            np.testing.assert_array_equal(self.part_points(self.meshes['large'], name), self.part_points(self.meshes['adrenaline'], name))
        self.assertNotEqual(self.assets[builder.TEXTURES['large']], self.assets[builder.TEXTURES['adrenaline']])

    def test_side_and_top_medical_print_is_correctly_oriented_on_actual_solid_faces(self):
        for kind in ('stimpack', 'large', 'mega', 'adrenaline'):
            model, mesh = self.models[kind], self.meshes[kind]
            triangles = model.positions[0, model.faces]
            material = np.asarray(mesh['materials']) == ('injector' if kind == 'stimpack' else 'label')
            for sign in (-1, 1):
                mask = material & (np.sign(triangles.mean(axis=1)[:, 1]) == sign)
                self.assertEqual(mask.sum(), 2)
                points, uvs = triangles[mask].reshape(-1, 3), model.uvs[mask].reshape(-1, 2)
                design = np.column_stack((points[:, 0], points[:, 2], np.ones(len(points))))
                coefficients = np.linalg.lstsq(design, uvs, rcond=None)[0]
                self.assertGreater(coefficients[0, 0] * -sign, 0.)
                self.assertLess(coefficients[1, 1], 0.)
                self.assertLess(np.abs(design @ coefficients - uvs).max(), .001)
        for kind in ('medium', 'large', 'mega', 'adrenaline'):
            model, mesh = self.models[kind], self.meshes[kind]
            triangles = model.positions[0, model.faces]
            material = np.asarray(mesh['materials']) == ('label' if kind == 'medium' else 'cross')
            points, uvs = triangles[material].reshape(-1, 3), model.uvs[material].reshape(-1, 2)
            # Different heights can share an atlas region; XY remains the
            # correct orientation separately on each horizontal solid cap.
            for height in np.unique(points[:, 2]):
                mask = points[:, 2] == height
                if mask.sum() < 3: continue
                coefficients = np.linalg.lstsq(np.column_stack((points[mask, :2], np.ones(mask.sum()))), uvs[mask], rcond=None)[0]
                self.assertGreater(coefficients[0, 0], 0.)
                self.assertLess(coefficients[1, 1], 0.)

    def test_atlases_have_exact_legible_plus_amounts_boost_and_medical_crosses(self):
        panels = {'stimpack': ((28, 67), (14, 18, 9), (2, 40, 26, 63)),
                  'medium': ((82, 70), (41, 23, 16), (9, 47, 73, 66)),
                  'large': ((178, 111), (89, 34, 24), (14, 69, 164, 103)),
                  'mega': ((96, 154), (48, 48, 28), (8, 104, 88, 140)),
                  'adrenaline': ((178, 111), (89, 34, 24), (14, 69, 164, 103))}

        def cross_mask(width, height, cx, cy, radius):
            result = np.zeros((height, width), dtype=np.uint8)
            arm = radius // 3
            result[cy - radius:cy + radius + 1, cx - arm:cx + arm + 1] = 255
            result[cy - arm:cy + arm + 1, cx - radius:cx + radius + 1] = 255
            return result

        def resize(mask, rectangle):
            x, y, X, Y = rectangle
            return np.asarray(Image.fromarray(mask).resize((X - x, Y - y), Image.Resampling.NEAREST)) > 0

        for kind in KINDS:
            image = np.asarray(Image.open(io.BytesIO(self.assets[builder.TEXTURES[kind]])))
            self.assertEqual(image.shape, (256, 256, 3))
            for material, panel_kind in (('label', kind), ('injector', 'stimpack')):
                (width, height), (cx, cy, radius), (x, y, X, Y) = panels[panel_kind]
                expected = cross_mask(width, height, cx, cy, radius)
                text = LABELS[panel_kind]; columns = len(text) * 4 - 1
                scale = min((X - x) // columns, (Y - y) // 5)
                left, top = x + (X - x - columns * scale) // 2, y + (Y - y - 5 * scale) // 2
                for index, letter in enumerate(text):
                    for row, bits in enumerate(builder.GLYPHS[letter]):
                        for col, on in enumerate(bits):
                            if on == '1':
                                a, b = left + (index * 4 + col) * scale, top + row * scale
                                expected[b:b + scale, a:a + scale] = 255
                x, y, X, Y = REGIONS[material]
                expected = resize(expected, REGIONS[material])
                actual = np.all(image[y:Y, x:X] == builder.INK, axis=2)
                with self.subTest(kind=kind, material=material):
                    self.assertGreater(scale, 1)
                    np.testing.assert_array_equal(actual, expected)
                    self.assertGreater(image[y:Y, x:X][expected].mean() - image[y:Y, x:X][~expected].mean(), 100.)
            width, height = (200, 91) if kind in ('large', 'adrenaline') else (80, 80)
            radius = round(min(width, height) * .34)
            expected = resize(cross_mask(width, height, width // 2, height // 2, radius), REGIONS['cross'])
            x, y, X, Y = REGIONS['cross']
            actual = np.all(image[y:Y, x:X] == builder.INK, axis=2)
            with self.subTest(kind=kind, material='cross'):
                np.testing.assert_array_equal(actual, expected)

    def test_crosses_stay_square_in_decoded_surface_space(self):
        # Measure the shipped ink after mapping its atlas pixels back through
        # each actual face's dimensions. A square atlas cross on a tall/wide
        # face fails this, even when its bitmap alone looks correct.
        for kind in KINDS:
            image = np.asarray(Image.open(io.BytesIO(self.assets[builder.TEXTURES[kind]])))
            material = 'injector' if kind == 'stimpack' else 'label'
            x, y, X, Y = REGIONS[material]
            ink = np.all(image[y:Y, x:X] == builder.INK, axis=2)
            ink[int(len(ink) * .6):] = False  # lettering is below the cross
            rows, columns = np.where(ink)
            mesh, model = self.meshes[kind], self.models[kind]
            mask = np.asarray(mesh['materials']) == material
            triangles = model.positions[0, model.faces]
            if kind == 'medium':
                axes = (0, 1)
            else:
                mask &= triangles.mean(axis=1)[:, 1] < 0
                axes = (0, 2)
            points = triangles[mask].reshape(-1, 3)
            physical = np.ptp(points[:, axes], axis=0)
            width = (np.ptp(columns) + 1) / (X - x - 1) * physical[0]
            height = (np.ptp(rows) + 1) / (Y - y - 1) * physical[1]
            with self.subTest(kind=kind):
                self.assertGreater(width / height, .85)
                self.assertLess(width / height, 1.15)
            caps = np.asarray(mesh['materials']) == 'cross'
            if caps.any():
                x, y, X, Y = REGIONS['cross']
                rows, columns = np.where(np.all(image[y:Y, x:X] == builder.INK, axis=2))
                points = triangles[caps].reshape(-1, 3)
                physical = np.ptp(points[:, :2], axis=0)
                width = (np.ptp(columns) + 1) / (X - x - 1) * physical[0]
                height = (np.ptp(rows) + 1) / (Y - y - 1) * physical[1]
                with self.subTest(kind=kind, face='horizontal cap'):
                    self.assertGreater(width / height, .85)
                    self.assertLess(width / height, 1.15)

    def test_exact_stimpack_lod_ownership_and_other_asset_isolation(self):
        import build_platoon
        config = json.loads(build_platoon.CONFIG.read_text())
        registration = config['procedural_replacements']['health']
        self.assertEqual(set(registration['models'] + registration['textures']), set(self.assets))
        self.assertEqual(set(registration['textures']), set(builder.TEXTURES.values()))
        self.assertTrue(set(registration['models']) <= build_platoon.procedural_paths(config))
        legacy = json.loads(build_platoon.MANIFEST.read_text())
        self.assertFalse(set(registration['models']) & {entry['path'] for entry in legacy['models']})
        stim = 'models/items/healing/stimpack/tris.md2'
        self.assertEqual(self.assets[stim], self.assets[stim.replace('/tris.md2', '/lod1.md2')])
        self.assertEqual(builder.TEXTURES['large'], 'models/items/healing/large/skin_health.png')
        self.assertEqual(builder.TEXTURES['adrenaline'], 'models/items/adrenal/skin.png')
        self.assertNotIn('models/items/healing/large/skin.png', self.assets)
        legacy_skin = (ROOT / 'baseq2/models/items/healing/large/skin.png').read_bytes()
        self.assertEqual(builder.sha(legacy_skin), '1d3f5e3dc59ddad422f4b930adb1ff3cd8b3c7148b193f9092860142de389944')
        for manifest in ('ammo-manifest.json', 'projectiles-manifest.json'):
            for entry in json.loads((ROOT / 'tools/assets' / manifest).read_text())['files']:
                self.assertNotIn(entry['path'], self.assets)
                self.assertEqual(builder.sha((ROOT / 'baseq2' / entry['path']).read_bytes()), entry['sha256'])

    def test_original_spawn_paths_health_amounts_flags_and_sounds_remain(self):
        source = (ROOT / 'src/game/g_items.c').read_text()
        cases = {'SP_item_health_small': ('models/items/healing/stimpack/tris.md2', 2, 'HEALTH_IGNORE_MAX', 's'),
                 'SP_item_health': ('models/items/healing/medium/tris.md2', 10, None, 'n'),
                 'SP_item_health_large': ('models/items/healing/large/tris.md2', 25, None, 'l'),
                 'SP_item_health_mega': ('models/items/mega_h/tris.md2', 100, 'HEALTH_IGNORE_MAX | HEALTH_TIMED', 'm')}
        for name, (path, amount, style, sound) in cases.items():
            body = function_text(source, name)
            self.assertIn(f'self->model = "{path}";', body)
            self.assertIn(f'self->count = {amount};', body)
            self.assertIn('SpawnItem(self, FindItem("Health"));', body)
            self.assertIn(f'gi.soundindex("items/{sound}_health.wav");', body)
            self.assertIn('DF_NO_HEALTH', body)
            if style: self.assertIn(f'self->style = {style};', body)
            else: self.assertNotIn('self->style', body)
        adrenaline = source[source.index('/* QUAKED item_adrenaline'):source.index('/* QUAKED item_bandolier')]
        self.assertIn('Pickup_Adrenaline', adrenaline)
        self.assertIn('"models/items/adrenal/tris.md2", EF_ROTATE', adrenaline)
        self.assertIn('"Adrenaline",\n\t\t2,\n\t\t60,', adrenaline)

    def test_sandstorm_booster_overlay_matches_authored_assets_and_preserves_edited_map(self):
        import build_health_overlays
        # The receipt authenticates all55 unmanaged members, including the
        # edited map/BSP and compatibility medkit atlas, before any sync.
        build_health_overlays.verify(ROOT)
        with zipfile.ZipFile(ROOT / 'baseq2/operation-sandstorm-preview.pk3') as archive:
            for path in ('models/items/adrenal/tris.md2', 'models/items/adrenal/skin.png'):
                self.assertEqual(archive.read(path), self.assets[path])
            path = 'models/items/healing/large/skin.png'
            self.assertEqual(archive.read(path), (ROOT / 'baseq2' / path).read_bytes())


if __name__ == '__main__':
    unittest.main()
