#!/usr/bin/env python3
"""Validate real armor openings, closed walls, scale and independent ownership."""
from collections import Counter
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/assets'))
import build_armor as builder
from armor_geometry import build_armor, KINDS, REGIONS
from asset_sources import source_bytes
from md2_assets import MD2, normal_table


def ray_distances(triangles, origin, direction, maximum=np.inf):
    direction = np.asarray(direction)
    e1, e2 = triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]
    h = np.cross(direction, e2)
    determinant = np.einsum('ij,ij->i', e1, h)
    valid = np.abs(determinant) > 1e-9
    inverse = np.zeros(len(valid)); inverse[valid] = 1 / determinant[valid]
    relative = np.asarray(origin) - triangles[:, 0]
    u = inverse * np.einsum('ij,ij->i', relative, h)
    q = np.cross(relative, e1)
    v = inverse * (q @ direction)
    distance = inverse * np.einsum('ij,ij->i', e2, q)
    hits = distance[valid & (u >= -1e-8) & (v >= -1e-8) & (u + v <= 1 + 1e-8) &
                    (distance > 1e-6) & (distance < maximum)]
    return np.unique(np.round(hits, 6))


class ArmorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets, cls.manifest = builder.build_assets()
        cls.meshes = {kind: build_armor(kind) for kind in KINDS}
        cls.models = {kind: MD2.read(cls.assets[path]) for path, kind in builder.MODELS.items()}
        cls.pickups = json.loads((ROOT / 'tools/assets/pickups.json').read_text())

    @staticmethod
    def part(mesh, name):
        return next(part for part in mesh['parts'] if part['name'] == name)

    def triangles(self, kind, name=None):
        model = self.models[kind]
        triangles = model.positions[0, model.faces]
        if name:
            part = self.part(self.meshes[kind], name)
            a = part['first_triangle']; triangles = triangles[a:a + part['triangle_count']]
        return triangles

    def test_exact_nine_assets_manifest_dependency_hashes_and_standard_library_gate(self):
        self.assertEqual(len(self.assets), 9)
        self.assertEqual(json.loads(builder.MANIFEST.read_text()), self.manifest)
        inventory = {entry['path']: entry for entry in self.manifest['files']}
        self.assertEqual(set(inventory), set(self.assets))
        for path, raw in self.assets.items():
            with self.subTest(path=path):
                self.assertEqual((ROOT / 'baseq2' / path).read_bytes(), raw)
                self.assertEqual(inventory[path]['bytes'], len(raw))
                self.assertEqual(inventory[path]['sha256'], builder.sha(raw))
        for name, digest in self.manifest['dependencies_sha256'].items():
            self.assertEqual(builder.sha((ROOT / 'tools/assets' / name).read_bytes()), digest)
        subprocess.run([sys.executable, '-S', str(ROOT / 'tools/assets/verify_armor_runtime.py')],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def test_static_budgets_original_frame_names_and_placement_are_preserved(self):
        counts = {'shard': 76, 'jacket': 248, 'combat': 168, 'body': 212}
        self.assertEqual(set(builder.MODELS.values()), set(KINDS))
        for path, kind in builder.MODELS.items():
            model = self.models[kind]
            original = MD2.read(source_bytes(self.pickups, 'baseq2/' + path), source_compat=True)
            with self.subTest(kind=kind):
                self.assertEqual(len(model.faces), counts[kind])
                self.assertLessEqual(len(model.faces), 280)
                self.assertLess(len(model.faces), builder.BASELINES[kind]['triangles'])
                self.assertLess(len(model.data), builder.BASELINES[kind]['file_bytes'])
                self.assertEqual(model.names, original.names)
                self.assertEqual(model.header[10], 1)
                self.assertEqual(model.header[4], 40 + 4 * model.header[6])
                self.assertEqual(model.command_triangles, len(model.faces))
                self.assertEqual(model.skins, [builder.TEXTURES[kind]])
                self.assertTrue(np.all(model.uvs > 0) and np.all(model.uvs < 1))
                before, after = original.positions[0], model.positions[0]
                extent = np.ptp(before, axis=0)
                self.assertTrue(np.all(after.min(axis=0) >= before.min(axis=0) - extent * .12))
                self.assertTrue(np.all(after.max(axis=0) <= before.max(axis=0) + extent * .12))
                self.assertAlmostEqual(after[:, 2].min(), before[:, 2].min(), delta=.7)
                self.assertAlmostEqual(after[:, 2].max(), before[:, 2].max(), delta=.8)

    def test_every_quantized_component_is_closed_with_consistent_winding_and_outward_normals(self):
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

    def test_wrist_guard_has_a_real_through_channel_and_thick_annular_wall(self):
        triangles = self.triangles('shard')
        for x, y in ((0., 0.), (1., .5), (-1., -.5)):
            self.assertEqual(len(ray_distances(triangles, (x, y, -6.), (0., 0., 1.), 12.)), 0)
        for direction in ((1., 0., 0.), (-1., 0., 0.)):
            hits = ray_distances(triangles, (0., 0., 0.), direction)
            self.assertEqual(len(hits), 2)
            self.assertAlmostEqual(hits[0], 3.8, delta=.08)
            self.assertAlmostEqual(hits[1], 4.6, delta=.08)

    def test_boots_have_two_open_cuffs_and_deep_closed_foot_interiors(self):
        triangles = self.triangles('jacket')
        for center in (-7.1, 7.1):
            for x, y in ((center, 3.55), (center + .8, 3.8), (center - .8, 3.2)):
                hits = ray_distances(triangles, (x, y, 11.2), (0., 0., -1.))
                self.assertGreater(len(hits), 0)
                self.assertGreater(hits.min(), 16.)
                self.assertLess(hits.min(), 18.)
            # A neighboring ray hits the actual rim, showing that the clear
            # deep probe passed through an opening rather than absent walls.
            hits = ray_distances(triangles, (center + 3.1, 3.55, 11.2), (0., 0., -1.))
            self.assertGreater(len(hits), 0)
            self.assertAlmostEqual(hits.min(), .6, delta=.1)
        self.assertEqual(len(ray_distances(triangles, (0., 0., 12.), (0., 0., -1.), 25.)), 0)

    def test_helmet_has_an_open_interior_closed_crown_and_real_chinstrap_window(self):
        triangles = self.triangles('combat')
        for x, y in ((0., 3.), (2., 2.), (-2., 2.)):
            hits = ray_distances(triangles, (x, y, -3.), (0., 0., 1.))
            self.assertGreaterEqual(len(hits), 2)
            self.assertGreater(hits.min(), 8.)
            self.assertLess(hits.min(), 10.6)
        lip = ray_distances(triangles, (0., 8.8, -3.), (0., 0., 1.))
        self.assertGreater(len(lip), 0)
        self.assertAlmostEqual(lip.min(), .75, delta=.1)
        self.assertEqual(len(ray_distances(triangles, (0., -2., -5.), (0., 1., 0.), 4.)), 0)
        strap = ray_distances(triangles, (4.5, -2., -5.), (0., 1., 0.), 4.)
        self.assertEqual(len(strap), 2)

    def test_vest_keeps_torso_neck_and_arm_voids_with_separate_front_back_plates(self):
        triangles = self.triangles('body')
        self.assertEqual(len(ray_distances(triangles, (0., 0., 13.), (0., 0., -1.), 26.)), 0)
        for x, z in ((0., 9.), (-8.2, 6.), (8.2, 6.)):
            self.assertEqual(len(ray_distances(triangles, (x, -10., z), (0., 1., 0.), 20.)), 0)
        torso = ray_distances(triangles, (0., -10., 3.), (0., 1., 0.), 20.)
        np.testing.assert_allclose(torso, (3.2, 5.3, 14.7, 16.8), atol=.12)
        # Lower side protection is present below the anatomical armholes.
        for direction in ((1., 0., 0.), (-1., 0., 0.)):
            lower_side = ray_distances(triangles, (0., 0., 0.), direction)
            np.testing.assert_allclose(lower_side, (7., 9.2), atol=.12)
        shoulder = ray_distances(triangles, (5., 0., 13.), (0., 0., -1.), 26.)
        self.assertEqual(len(shoulder), 2)
        np.testing.assert_allclose(shoulder, (1.2, 3.25), atol=.12)

    def test_atlases_and_tier_markings_use_actual_armor_faces(self):
        for kind, model in self.models.items():
            image = np.asarray(Image.open(io.BytesIO(self.assets[builder.TEXTURES[kind]])))
            self.assertEqual(image.shape, (256, 256, 3))
            self.assertIn('tier', self.meshes[kind]['materials'])
            for material in set(self.meshes[kind]['materials']):
                x, y, X, Y = REGIONS[material]
                mask = np.asarray(self.meshes[kind]['materials']) == material
                uv = model.uvs[mask] * 256
                self.assertGreaterEqual(uv[:, :, 0].min(), x)
                self.assertLessEqual(uv[:, :, 0].max(), X)
                self.assertGreaterEqual(uv[:, :, 1].min(), y)
                self.assertLessEqual(uv[:, :, 1].max(), Y)
            x, y, X, Y = REGIONS['tier']
            self.assertGreater(np.all(image[y:Y, x:X] == builder.INK, axis=2).sum(), 500)
        body = self.models['body']
        tier = np.asarray(self.meshes['body']['materials']) == 'tier'
        self.assertEqual(tier.sum(), 2)
        points = body.positions[0, body.faces[tier]]
        self.assertLess(points[:, :, 1].max(), -8.8)
        self.assertLess(np.abs(points[:, :, 0]).max(), 2.2)

    def test_ownership_exact_shard_lod_and_other_asset_isolation(self):
        import build_platoon
        config = json.loads(build_platoon.CONFIG.read_text())
        owner = config['procedural_replacements']['armor']
        self.assertEqual(set(owner['models'] + owner['textures']), set(self.assets))
        self.assertEqual(set(owner['textures']), set(builder.TEXTURES.values()))
        self.assertTrue(set(owner['models']) <= build_platoon.procedural_paths(config))
        legacy = json.loads(build_platoon.MANIFEST.read_text())
        self.assertFalse(set(owner['models']) & {entry['path'] for entry in legacy['models']})
        path = 'models/items/armor/shard/tris.md2'
        self.assertEqual(self.assets[path], self.assets[path.replace('/tris.md2', '/lod1.md2')])
        for manifest in ('ammo-manifest.json', 'projectiles-manifest.json', 'health-manifest.json'):
            for entry in json.loads((ROOT / 'tools/assets' / manifest).read_text())['files']:
                self.assertNotIn(entry['path'], self.assets)
                self.assertEqual(builder.sha((ROOT / 'baseq2' / entry['path']).read_bytes()), entry['sha256'])

    def test_existing_armor_spawn_models_rotation_tags_and_reports_remain(self):
        source = (ROOT / 'src/game/g_items.c').read_text()
        for kind in KINDS:
            start = source.index('/* QUAKED item_armor_' + kind)
            end = source.index('/* QUAKED ', start + 3)
            entry = source[start:end]
            self.assertIn('Pickup_Armor', entry)
            self.assertIn(f'"models/items/armor/{kind}/tris.md2", EF_ROTATE', entry)
            self.assertIn('IT_ARMOR', entry)
            self.assertIn('ARMOR_' + kind.upper(), entry)
            self.assertIn('"misc/ar' + ('2' if kind == 'shard' else '1') + '_pkup.wav"', entry)


if __name__ == '__main__':
    unittest.main()
