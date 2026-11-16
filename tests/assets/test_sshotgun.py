#!/usr/bin/env python3
"""Validate the authored double-barrel shotgun, shared hands and real sights."""
from collections import Counter
import io
import json
from pathlib import Path
import sys
import unittest

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/assets'))
import build_sshotgun as builder
from asset_sources import source_bytes
from build_m16 import rigid_transforms
from m16_geometry import build_m16
from md2_assets import MD2, normal_table
from sshotgun_geometry import build_sshotgun


class DoubleBarrelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets, cls.manifest, cls.header = builder.build_assets()
        cls.meshes = {kind: build_sshotgun(kind) for kind in ('world', 'view')}

    @staticmethod
    def part_vertices(mesh, name):
        part = next(p for p in mesh['parts'] if p['name'] == name)
        start = part['first_triangle']
        indices = np.asarray(mesh['faces'])[start:start + part['triangle_count']]
        return np.asarray(mesh['vertices'])[indices].reshape(-1, 3)

    def test_exact_shipped_assets_manifest_and_sight_header(self):
        for path, raw in self.assets.items():
            with self.subTest(path=path):
                self.assertEqual((ROOT / 'baseq2' / path).read_bytes(), raw)
        self.assertEqual(json.loads(builder.MANIFEST.read_text()), self.manifest)
        self.assertEqual(builder.ADS_HEADER.read_bytes(), self.header)
        inventory = {entry['path']: entry for entry in self.manifest['files']}
        self.assertEqual(set(inventory), set(self.assets))
        for path, raw in self.assets.items():
            self.assertEqual(inventory[path]['sha256'], builder.sha(raw))
            self.assertEqual(inventory[path]['bytes'], len(raw))

    def test_reduced_budget_and_single_view_frame_preserve_static_cache(self):
        frames = {'view': 1, 'pickup': 1, 'player': 198}
        self.assertEqual(set(builder.MODELS.values()), set(frames))
        for entry in self.manifest['models']:
            model = MD2.read(self.assets[entry['path']])
            with self.subTest(role=entry['role']):
                self.assertLess(len(model.faces), 900 if entry['role'] == 'view' else 400)
                self.assertEqual(model.header[10], frames[entry['role']])
                self.assertEqual(model.command_triangles, len(model.faces))
                self.assertEqual(model.header[4], 40 + 4 * model.header[6])
                for skin in model.skins:
                    self.assertIn(skin, self.assets)
                triangles = model.positions[:, model.faces]
                area = np.linalg.norm(np.cross(triangles[:, :, 1] - triangles[:, :, 0],
                                               triangles[:, :, 2] - triangles[:, :, 0]), axis=2)
                self.assertGreater(area.min(), 1e-9)

    def test_separate_parallel_barrels_and_two_muzzle_centers(self):
        for kind, mesh in self.meshes.items():
            with self.subTest(kind=kind):
                left = self.part_vertices(mesh, 'barrel_left')
                right = self.part_vertices(mesh, 'barrel_right')
                self.assertGreater(left[:, 1].min(), 0.)
                self.assertLess(right[:, 1].max(), 0.)
                np.testing.assert_allclose(left[:, [0, 2]].min(axis=0), right[:, [0, 2]].min(axis=0))
                np.testing.assert_allclose(left[:, [0, 2]].max(axis=0), right[:, [0, 2]].max(axis=0))
                self.assertGreater(np.ptp(left[:, 0]), 40.)
                anchors = mesh['anchors']
                a, b = np.asarray(anchors['muzzle_left']), np.asarray(anchors['muzzle_right'])
                np.testing.assert_array_equal(a[[0, 2]], b[[0, 2]])
                self.assertGreater(a[1], 0.)
                self.assertLess(b[1], 0.)
                np.testing.assert_allclose((a + b) / 2, anchors['muzzle'])
                self.assertAlmostEqual(a[0], left[:, 0].max())
                self.assertAlmostEqual(b[0], right[:, 0].max())

    def test_existing_two_hand_style_and_scale_are_retained(self):
        mesh = self.meshes['view']
        rifle = build_m16('view')
        for name in ('hand_left_palm', 'hand_right_palm', 'arm_left', 'arm_right'):
            a, b = self.part_vertices(mesh, name), self.part_vertices(rifle, name)
            ratio = np.ptp(a, axis=0) / np.ptp(b, axis=0)
            with self.subTest(part=name):
                self.assertTrue(np.all((ratio > .65) & (ratio < 1.35)))
        names = {p['name'] for p in self.meshes['world']['parts']}
        self.assertFalse(any(n.startswith(('hand_', 'arm_', 'cuff_')) for n in names))

    def test_every_gun_hand_and_arm_part_is_closed(self):
        for kind, mesh in self.meshes.items():
            vertices = np.round(np.asarray(mesh['vertices']), 7)
            for part in mesh['parts']:
                start = part['first_triangle']
                edges = Counter()
                for face in mesh['faces'][start:start + part['triangle_count']]:
                    points = [tuple(vertices[i]) for i in face]
                    for a, b in zip(points, points[1:] + points[:1]):
                        edges[tuple(sorted((a, b)))] += 1
                with self.subTest(kind=kind, part=part['name']):
                    self.assertTrue(edges)
                    self.assertTrue(all(n == 2 for n in edges.values()), 'open surface exposes the background')

    def test_center_sight_channel_is_clear_between_the_barrels(self):
        mesh = self.meshes['view']
        rear, front = (np.asarray(mesh['anchors'][key]) for key in ('rear_sight', 'front_sight'))
        np.testing.assert_array_equal(rear[1:], front[1:])
        self.assertEqual(rear[1], 0.)
        self.assertGreater(front[0] - rear[0], 30.)
        self.assertGreater(mesh['anchors']['muzzle'][0], front[0])
        # Detect triangle interiors across the line of aim, including a
        # accidentally solid rear notch or a raised receiver face.
        triangles = np.asarray(mesh['vertices'])[np.asarray(mesh['faces'])]
        ray = np.array([1., 0., 0.])
        e1, e2 = triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]
        h = np.cross(ray, e2)
        determinant = np.einsum('ij,ij->i', e1, h)
        valid = np.abs(determinant) > 1e-9
        inverse = np.zeros(len(valid)); inverse[valid] = 1 / determinant[valid]
        s = rear - triangles[:, 0]
        u = inverse * np.einsum('ij,ij->i', s, h)
        q = np.cross(s, e1)
        v = inverse * (q @ ray)
        distance = inverse * np.einsum('ij,ij->i', e2, q)
        blocked = valid & (u >= 0) & (v >= 0) & (u + v <= 1) & (distance > .15) & (distance < front[0] - rear[0] - .15)
        for part in mesh['parts']:
            if part['name'].startswith('front_sight'):
                a = part['first_triangle']; b = a + part['triangle_count']
                blocked[a:b] = False
        self.assertFalse(np.any(blocked), 'geometry blocks the centered real sight ray')

    def test_all_198_held_poses_follow_archived_rigid_motion(self):
        originals = json.loads((ROOT / 'tools/assets/platoon-originals.json').read_text())
        path = 'players/soldier/w_sshotgun.md2'
        original = MD2.read(source_bytes(originals, 'baseq2/' + path), source_compat=True)
        model = MD2.read(self.assets[path])
        self.assertEqual(model.names, original.names)
        rotations, translations, errors = rigid_transforms(original)
        self.assertLess(errors.max(), .15)
        matrix, offset, _ = builder.placement('player')
        reference = np.asarray(self.meshes['world']['vertices']) @ matrix + offset
        expected = np.asarray([reference @ r + t for r, t in zip(rotations, translations)])
        error = np.linalg.norm(model.positions - expected, axis=2)
        limit = np.linalg.norm(model.scales, axis=1) / 2 + 1e-5
        self.assertTrue(np.all(error <= limit[:, None]))

    def test_exported_winding_normals_and_molded_plastic_atlas(self):
        for path in builder.TEXTURES:
            with Image.open(io.BytesIO(self.assets[path])) as image:
                self.assertEqual(image.size, (256, 256))
                self.assertEqual(image.mode, 'RGB')
        model = MD2.read(self.assets['models/weapons/g_shotg2/tris.md2'])
        points = model.positions[0, model.faces]
        normals = np.cross(points[:, 1] - points[:, 0], points[:, 2] - points[:, 0])
        normals /= np.linalg.norm(normals, axis=1)[:, None]
        stored = normal_table()[model.normals[0, model.faces]].mean(axis=1)
        self.assertLess(np.median(np.sum(normals * stored, axis=1)), -.65)
        self.assertTrue(np.all(model.uvs > 0))
        self.assertTrue(np.all(model.uvs < 1))
        medians = []
        for raw in (self.assets[builder.TEXTURES[0]], (ROOT / 'baseq2/models/weapons/g_machn/skin.png').read_bytes()):
            with Image.open(io.BytesIO(raw)) as image:
                hsv = np.asarray(image.convert('HSV'))
                plastic = (hsv[:, :, 0] >= 45) & (hsv[:, :, 0] <= 125) & (hsv[:, :, 1] >= 45)
                medians.append(float(np.median(hsv[:, :, 2][plastic])))
        self.assertLessEqual(abs(medians[0] - medians[1]), 3.)

    def test_legacy_pipeline_cannot_restore_the_previous_double_barrel(self):
        import build_platoon
        config = json.loads(build_platoon.CONFIG.read_text())
        self.assertTrue(set(builder.MODELS) <= build_platoon.procedural_paths(config))
        manifest = json.loads(build_platoon.MANIFEST.read_text())
        self.assertFalse(set(builder.MODELS) & {entry['path'] for entry in manifest['models']})


if __name__ == '__main__':
    unittest.main(verbosity=2)
