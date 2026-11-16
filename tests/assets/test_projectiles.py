#!/usr/bin/env python3
"""Audit actual flying ammo, armed grenade details and preserved flight origins."""
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
import build_projectiles as builder
from ammo_geometry import build_ammo
from asset_sources import source_bytes
from md2_assets import MD2, normal_table
from projectile_geometry import build_projectile, placement, AMMO_KINDS, KINDS


class ProjectileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets, cls.manifest = builder.build_assets()
        cls.meshes = {kind: build_projectile(kind) for kind in KINDS}
        cls.models = {kind: MD2.read(cls.assets[path]) for path, kind in builder.MODELS.items()}
        cls.originals = json.loads((ROOT / 'tools/assets/platoon-originals.json').read_text())

    @staticmethod
    def part(mesh, name):
        return next(part for part in mesh['parts'] if part['name'] == name)

    @classmethod
    def part_triangles(cls, mesh, name):
        part = cls.part(mesh, name)
        a = part['first_triangle']; b = a + part['triangle_count']
        return np.asarray(mesh['vertices'])[np.asarray(mesh['faces'])[a:b]]

    def test_exact_six_assets_hashes_dependencies_manifest_and_standard_library_gate(self):
        self.assertEqual(len(self.assets), 6)
        self.assertEqual(json.loads(builder.MANIFEST.read_text()), self.manifest)
        inventory = {entry['path']: entry for entry in self.manifest['files']}
        self.assertEqual(set(inventory), set(self.assets))
        for path, raw in self.assets.items():
            with self.subTest(path=path):
                self.assertEqual((ROOT / 'baseq2' / path).read_bytes(), raw)
                self.assertEqual(inventory[path]['sha256'], builder.sha(raw))
                self.assertEqual(inventory[path]['bytes'], len(raw))
        for name, digest in self.manifest['dependencies_sha256'].items():
            self.assertEqual(builder.sha((ROOT / 'tools/assets' / name).read_bytes()), digest)
        subprocess.run([sys.executable, '-S', str(ROOT / 'tools/assets/verify_projectiles_runtime.py')],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def test_three_static_flight_paths_keep_original_frame_names_with_small_budgets(self):
        self.assertEqual(builder.MODELS, {'models/objects/rocket/tris.md2': 'rocket',
                         'models/objects/grenade/tris.md2': 'gl_round',
                         'models/objects/grenade2/tris.md2': 'hand_grenade'})
        counts = {'rocket': 128, 'gl_round': 76, 'hand_grenade': 88}
        for path, kind in builder.MODELS.items():
            model = self.models[kind]
            original = MD2.read(source_bytes(self.originals, 'baseq2/' + path), source_compat=True)
            with self.subTest(kind=kind):
                self.assertEqual(len(model.faces), counts[kind])
                self.assertLessEqual(len(model.faces), 128)
                self.assertLess(len(model.faces), builder.BASELINES[kind]['triangles'])
                self.assertLess(len(model.data), builder.BASELINES[kind]['file_bytes'])
                self.assertEqual(model.names, original.names)
                self.assertEqual(model.header[10], 1)
                self.assertEqual(model.header[4], 40 + 4 * model.header[6])
                self.assertEqual(model.command_triangles, len(model.faces))
                self.assertEqual(model.skins, [builder.TEXTURES[kind]])
                self.assertTrue(np.all(model.uvs > 0) and np.all(model.uvs < 1))

    def test_ammo_shapes_retain_exact_parts_uvs_and_palette_under_flight_transform(self):
        for kind, mesh in self.meshes.items():
            ammo = build_ammo(AMMO_KINDS[kind])
            matrix, offset = placement(kind)
            selected = {'grenade_body', 'fuse'} if kind == 'hand_grenade' else {part['name'] for part in ammo['parts']}
            self.assertEqual({part['name'] for part in mesh['parts']}, selected)
            for name in selected:
                with self.subTest(kind=kind, part=name):
                    np.testing.assert_allclose(self.part_triangles(mesh, name),
                        self.part_triangles(ammo, name) @ matrix + offset, atol=1e-12)
                    source = self.part(ammo, name); target = self.part(mesh, name)
                    a, b = source['first_triangle'], target['first_triangle']; n = source['triangle_count']
                    np.testing.assert_array_equal(mesh['uvs'][b:b + n], ammo['uvs'][a:a + n])
                    self.assertEqual(mesh['materials'][b:b + n], ammo['materials'][a:a + n])
            path = f'models/items/ammo/{AMMO_KINDS[kind]}/medium/'
            path += 'skin_ammo.png' if kind == 'rocket' else 'skin.png'
            self.assertEqual(self.assets[builder.TEXTURES[kind]], (ROOT / 'baseq2' / path).read_bytes())
            image = Image.open(io.BytesIO(self.assets[builder.TEXTURES[kind]]))
            self.assertEqual(image.mode, 'RGB'); self.assertEqual(image.size, (256, 256))

    def test_every_quantized_part_is_closed_nondegenerate_and_clockwise_with_outward_normals(self):
        for kind, model in self.models.items():
            mesh = self.meshes[kind]
            points, ideal = model.positions[0], np.asarray(mesh['vertices'])
            limit = np.linalg.norm(model.scales[0]) / 2 + 1e-5
            self.assertLessEqual(np.linalg.norm(points - ideal, axis=1).max(), limit)
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

    def test_rocket_exhaust_stays_at_trail_origin_and_nose_faces_plus_x(self):
        mesh, model = self.meshes['rocket'], self.models['rocket']
        self.assertEqual(mesh['anchors']['exhaust'], [0., 0., 0.])
        self.assertEqual(mesh['anchors']['nose'], [24.1, 0., 0.])
        points = model.positions[0]
        self.assertAlmostEqual(points[:, 0].min(), 0., delta=.06)
        self.assertAlmostEqual(points[:, 0].max(), 24.1, delta=.06)
        self.assertLess(np.abs(points[:, 1:]).max(), 2.8)
        body = self.part(mesh, 'rocket_body'); a = body['first_triangle']; b = a + body['triangle_count']
        nose = points[np.unique(model.faces[a:b])]
        nose = nose[nose[:, 0] > 23.95]
        self.assertGreater(len(nose), 0)
        self.assertLess(np.linalg.norm(nose[:, 1:], axis=1).max(), .3)
        for index in range(4):
            fin = self.part_triangles(mesh, 'rocket_fin_' + str(index)).reshape(-1, 3)
            self.assertLess(fin[:, 0].max(), 4.5)
            self.assertGreater(np.linalg.norm(fin[:, 1:], axis=1).max(), 2.6)
        nozzle = self.part_triangles(mesh, 'rocket_nozzle').reshape(-1, 3)
        self.assertAlmostEqual(nozzle[:, 0].min(), 0.)
        self.assertLess(nozzle[:, 0].max(), 2.7)

    def test_spinning_grenades_are_centered_at_existing_flight_origin_and_scale(self):
        for kind in ('gl_round', 'hand_grenade'):
            points = self.models[kind].positions[0]
            with self.subTest(kind=kind):
                self.assertAlmostEqual(points[:, 0].min(), -5., delta=.08)
                self.assertAlmostEqual(points[:, 0].max(), 5., delta=.08)
                self.assertAlmostEqual((points[:, 0].min() + points[:, 0].max()) / 2, 0., delta=.06)
                self.assertGreater(np.abs(points[:, 1:]).max(), 2.6)
                self.assertLess(np.abs(points[:, 1:]).max(), 2.9)
        mesh = self.meshes['hand_grenade']
        self.assertEqual({part['name'] for part in mesh['parts']}, {'grenade_body', 'fuse'})
        self.assertNotIn('pull_ring', {part['name'] for part in mesh['parts']})
        self.assertNotIn('safety_lever', {part['name'] for part in mesh['parts']})

    def test_nonuniform_round_scale_uses_inverse_transpose_normals(self):
        kind = 'gl_round'
        source = build_ammo(AMMO_KINDS[kind])
        matrix, _ = placement(kind)
        expected = np.asarray(source['normals']) @ np.linalg.inv(matrix).T
        expected /= np.linalg.norm(expected, axis=1)[:, None]
        np.testing.assert_allclose(self.meshes[kind]['normals'], expected, atol=1e-12)
        naive = np.asarray(source['normals']) @ matrix
        naive /= np.linalg.norm(naive, axis=1)[:, None]
        self.assertGreater(np.linalg.norm(expected - naive, axis=1).max(), .03)

    def test_separate_ownership_and_no_ammo_hand_view_or_shared_skin_changes(self):
        import build_platoon
        config = json.loads(build_platoon.CONFIG.read_text())
        registration = config['procedural_replacements']['projectiles']
        self.assertEqual(set(registration['models']), set(builder.MODELS))
        self.assertEqual(set(registration['textures']), set(builder.TEXTURES.values()))
        self.assertTrue(set(builder.MODELS) <= build_platoon.procedural_paths(config))
        legacy = json.loads(build_platoon.MANIFEST.read_text())
        self.assertFalse(set(builder.MODELS) & {entry['path'] for entry in legacy['models']})
        ammo = json.loads((ROOT / 'tools/assets/ammo-manifest.json').read_text())
        for entry in ammo['files']:
            self.assertNotIn(entry['path'], self.assets)
            self.assertEqual(builder.sha((ROOT / 'baseq2' / entry['path']).read_bytes()), entry['sha256'])
        for name, digest in {
            'models/weapons/v_handgr/tris.md2': '9b74b53a1729ec04921ea4c9e142f3494ab15683e557c47269e1da2d6fdbb32f',
            'models/items/ammo/rockets/medium/skin.png': '9cc6122b646e70b0bfde420163bfaa8fed18b6671143da6721189593b9448b72'}.items():
            self.assertNotIn(name, self.assets)
            self.assertEqual(builder.sha((ROOT / 'baseq2' / name).read_bytes()), digest)

    def test_both_mission_overlays_load_the_same_authored_rocket_and_exhaust_atlas(self):
        import build_projectile_overlays
        # The receipt also authenticates every unmanaged archive member, so
        # an operation cannot quietly shadow the model with older geometry.
        build_projectile_overlays.verify(ROOT)
        for name in ('operation-tank-test.pk3', 'operation-helicopter-test.pk3'):
            with self.subTest(archive=name), zipfile.ZipFile(ROOT / 'baseq2' / name) as archive:
                for path in ('models/objects/rocket/tris.md2', 'models/objects/rocket/skin.png'):
                    self.assertEqual(archive.read(path), self.assets[path])
                legacy = 'models/items/ammo/rockets/medium/skin.png'
                self.assertEqual(archive.read(legacy), (ROOT / 'baseq2' / legacy).read_bytes())


if __name__ == '__main__':
    unittest.main()
