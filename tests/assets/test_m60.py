#!/usr/bin/env python3
"""Validate authored M60 assets, shared mittens, sights and heavy-soldier poses."""
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
import build_m60 as builder
from asset_sources import source_bytes
from build_m16 import rigid_transforms
from m16_geometry import build_m16
from md2_assets import MD2, normal_table
from m60_geometry import build_m60


class M60Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets, cls.manifest, cls.header = builder.build_assets()
        cls.meshes = {kind: build_m60(kind) for kind in ('world', 'view')}

    @staticmethod
    def part_vertices(mesh, name):
        part = next(p for p in mesh['parts'] if p['name'] == name)
        start = part['first_triangle']
        indices = np.asarray(mesh['faces'])[start:start + part['triangle_count']]
        return np.asarray(mesh['vertices'])[indices].reshape(-1, 3)

    def test_exact_shipped_assets_manifest_and_alignment_header(self):
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

    def test_budgets_frames_skin_resolution_and_nondegenerate_animation(self):
        expected = {'view': 1, 'pickup': 1, 'player': 198, 'enemy': 475, 'enemy_tall': 475}
        for entry in self.manifest['models']:
            model = MD2.read(self.assets[entry['path']])
            with self.subTest(role=entry['role']):
                self.assertLess(len(model.faces), 950 if entry['role'] == 'view' else 450)
                self.assertEqual(model.header[10], expected[entry['role']])
                self.assertEqual(model.command_triangles, len(model.faces))
                self.assertEqual(model.header[4], 40 + 4 * model.header[6])
                for skin in model.skins:
                    self.assertIn(skin, self.assets)
                triangles = model.positions[:, model.faces]
                area = np.linalg.norm(np.cross(triangles[:, :, 1] - triangles[:, :, 0],
                                               triangles[:, :, 2] - triangles[:, :, 0]), axis=2)
                self.assertGreater(area.min(), 1e-9)

    def test_box_feed_gas_tube_and_paired_folded_bipod(self):
        for kind, mesh in self.meshes.items():
            with self.subTest(kind=kind):
                receiver = self.part_vertices(mesh, 'receiver')
                box = self.part_vertices(mesh, 'ammo_box')
                self.assertGreater(box[:, 1].max(), receiver[:, 1].max() + 5.)
                self.assertLess(box[:, 2].min(), receiver[:, 2].min())
                barrel = self.part_vertices(mesh, 'barrel')
                gas = self.part_vertices(mesh, 'gas_tube')
                self.assertLess(gas[:, 2].max(), barrel[:, 2].min())
                for side in ('left', 'right'):
                    leg = self.part_vertices(mesh, 'folded_bipod_' + side)
                    self.assertGreater(np.ptp(leg[:, 0]), 15.)
                    self.assertLess(np.ptp(leg[:, 2]), 6., 'bipod should remain folded alongside the barrel')
                    self.assertTrue(np.all(leg[:, 1] > 0) if side == 'left' else np.all(leg[:, 1] < 0))

    def test_existing_mitten_hand_style_and_arm_scale(self):
        mesh, rifle = self.meshes['view'], build_m16('view')
        for name in ('hand_left_palm', 'hand_right_palm', 'arm_left', 'arm_right'):
            actual, reference = self.part_vertices(mesh, name), self.part_vertices(rifle, name)
            ratio = np.ptp(actual, axis=0) / np.ptp(reference, axis=0)
            with self.subTest(part=name):
                self.assertTrue(np.all((ratio > .65) & (ratio < 1.35)))
        names = {p['name'] for p in self.meshes['world']['parts']}
        self.assertFalse(any(n.startswith(('hand_', 'arm_', 'cuff_')) for n in names))

    def test_all_gun_hand_and_arm_parts_are_closed(self):
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

    def test_actual_model_sights_have_an_unobstructed_center_channel(self):
        mesh = self.meshes['view']
        rear, front = (np.asarray(mesh['anchors'][key]) for key in ('rear_sight', 'front_sight'))
        np.testing.assert_array_equal(rear[1:], front[1:])
        self.assertEqual(rear[1], 0.)
        self.assertGreater(front[0] - rear[0], 30.)
        self.assertGreater(mesh['anchors']['muzzle'][0], front[0])
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

    def test_player_and_enemy_follow_pinned_archived_motion_in_all_poses(self):
        originals = json.loads((ROOT / 'tools/assets/platoon-originals.json').read_text())
        mesh = self.meshes['world']
        for path, role in builder.MODELS.items():
            if role not in ('player', 'enemy'):
                continue
            with self.subTest(role=role):
                source_path = 'models/monsters/soldier/weapon_machinegun.md2' if role == 'enemy' else path
                source = MD2.read(source_bytes(originals, 'baseq2/' + source_path), source_compat=True)
                model = MD2.read(self.assets[path])
                self.assertEqual(model.names, source.names)
                rotations, translations, errors = rigid_transforms(source)
                self.assertLess(errors.max(), .15)
                matrix, offset, _ = builder.placement(role)
                reference = np.asarray(mesh['vertices']) @ matrix + offset
                expected = np.asarray([reference @ r + t for r, t in zip(rotations, translations)])
                error = np.linalg.norm(model.positions - expected, axis=2)
                limit = np.linalg.norm(model.scales, axis=1) / 2 + 1e-5
                self.assertTrue(np.all(error <= limit[:, None]))

    def test_heavy_enemy_tall_variant_keeps_foot_anchored_transform(self):
        normal = MD2.read(self.assets['models/monsters/soldier/weapon_heavy.md2'])
        tall = MD2.read(self.assets['models/monsters/soldier/tall/weapon_heavy.md2'])
        self.assertEqual(normal.names, tall.names)
        np.testing.assert_array_equal(normal.faces, tall.faces)
        np.testing.assert_array_equal(normal.normals, tall.normals)
        expected = normal.positions * 1.2
        expected[:, :, 2] += 4.8
        np.testing.assert_allclose(tall.positions, expected, atol=8e-6)

    def test_outward_normals_winding_and_shared_plastic_atlas(self):
        for path in builder.TEXTURES:
            with Image.open(io.BytesIO(self.assets[path])) as image:
                self.assertEqual(image.size, (256, 256))
                self.assertEqual(image.mode, 'RGB')
        model = MD2.read(self.assets['models/weapons/g_chain/tris.md2'])
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
                pigment = (hsv[:, :, 0] >= 45) & (hsv[:, :, 0] <= 125) & (hsv[:, :, 1] >= 45)
                medians.append(float(np.median(hsv[:, :, 2][pigment])))
        self.assertLessEqual(abs(medians[0] - medians[1]), 3.)

    def test_legacy_pipeline_cannot_restore_the_previous_m60(self):
        import build_platoon
        config = json.loads(build_platoon.CONFIG.read_text())
        self.assertTrue(set(builder.MODELS) <= build_platoon.procedural_paths(config))
        manifest = json.loads(build_platoon.MANIFEST.read_text())
        self.assertFalse(set(builder.MODELS) & {entry['path'] for entry in manifest['models']})


if __name__ == '__main__':
    unittest.main(verbosity=2)
