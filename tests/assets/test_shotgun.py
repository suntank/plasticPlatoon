#!/usr/bin/env python3
"""Validate authored shotgun assets, clear sights, and the exported pump cycle."""
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
import build_shotgun as builder
from asset_sources import source_bytes
from build_m16 import rigid_transforms
from md2_assets import MD2, normal_table
from shotgun_geometry import build_shotgun


class ShotgunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets, cls.manifest, cls.header = builder.build_assets()
        cls.meshes = {kind: build_shotgun(kind) for kind in ('world', 'view')}

    @staticmethod
    def part_indices(mesh, name):
        part = next(p for p in mesh['parts'] if p['name'] == name)
        start = part['first_triangle']
        return np.unique(np.asarray(mesh['faces'])[start:start + part['triangle_count']])

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

    def test_geometry_budget_frame_schedule_and_resolved_skins(self):
        frames = {'view': 40, 'pickup': 1, 'player': 198, 'enemy': 475, 'enemy_tall': 475}
        for entry in self.manifest['models']:
            model = MD2.read(self.assets[entry['path']])
            with self.subTest(role=entry['role']):
                self.assertLess(len(model.faces), 900 if entry['role'] == 'view' else 400)
                self.assertEqual(model.header[10], frames[entry['role']])
                self.assertEqual(model.command_triangles, len(model.faces))
                self.assertEqual(model.header[4], 40 + 4 * model.header[6])
                for skin in model.skins:
                    self.assertIn(skin, self.assets)
                points = model.positions[:, model.faces]
                area = np.linalg.norm(np.cross(points[:, :, 1] - points[:, :, 0],
                                               points[:, :, 2] - points[:, :, 0]), axis=2)
                self.assertGreater(area.min(), 1e-9)

    def test_pump_and_left_hand_retract_together_while_sights_and_grip_stay_fixed(self):
        rest = self.meshes['view']
        back = build_shotgun('view', pump=1.)
        np.testing.assert_array_equal(rest['faces'], back['faces'])
        a, b = np.asarray(rest['vertices']), np.asarray(back['vertices'])
        names = [p['name'] for p in rest['parts']]
        pump_name = next(name for name in names if name == 'pump' or name.startswith('pump_'))
        for name in (pump_name, 'hand_left_palm', 'hand_left_thumb'):
            ids = self.part_indices(rest, name)
            np.testing.assert_allclose(b[ids] - a[ids], np.tile([-7., 0., 0.], (len(ids), 1)), atol=1e-7)
        for name in ('receiver', 'hand_right_palm', 'hand_right_thumb'):
            ids = self.part_indices(rest, name)
            np.testing.assert_array_equal(a[ids], b[ids])
        for anchor in ('rear_sight', 'front_sight', 'muzzle'):
            np.testing.assert_array_equal(rest['anchors'][anchor], back['anchors'][anchor])
        arm = self.part_indices(rest, 'arm_left')
        travel = np.linalg.norm(b[arm] - a[arm], axis=1)
        self.assertLess(travel.min(), .01, 'the elbow must stay planted while the wrist follows the pump')
        self.assertGreater(travel.max(), 6., 'the support arm must follow the moving hand')

    def test_exported_view_cycle_has_one_full_rearward_and_forward_stroke(self):
        model = MD2.read(self.assets['models/weapons/v_shotg/tris.md2'])
        rest = self.meshes['view']
        matrix, offset, _ = builder.placement('view')
        expected_fractions = np.zeros(40)
        expected_fractions[[10, 11, 12, 13, 14, 15]] = [.35, .75, 1., 1., .65, .25]
        np.testing.assert_array_equal(self.manifest['view_animation']['pump_fractions'], expected_fractions)
        # Validate the decoded MD2, including its hand/arm animation, rather than
        # only trusting the animation metadata or procedural source meshes.
        for frame, fraction in enumerate(expected_fractions):
            expected = np.asarray(build_shotgun('view', pump=float(fraction))['vertices']) @ matrix + offset
            error = np.linalg.norm(model.positions[frame] - expected, axis=1)
            self.assertLessEqual(error.max(), np.linalg.norm(model.scales[frame]) / 2 + 1e-5)
        # Consecutive fully-back frames reach a stable endpoint for interpolation.
        np.testing.assert_array_equal(model.positions[12], model.positions[13])
        np.testing.assert_array_equal(model.positions[0], model.positions[16])

    def test_every_solid_part_is_closed_at_both_pump_endpoints(self):
        for kind in ('world', 'view'):
            for fraction in (0., 1.):
                mesh = build_shotgun(kind, pump=fraction)
                vertices = np.round(np.asarray(mesh['vertices']), 7)
                for part in mesh['parts']:
                    start = part['first_triangle']
                    edges = Counter()
                    for face in mesh['faces'][start:start + part['triangle_count']]:
                        points = [tuple(vertices[i]) for i in face]
                        for a, b in zip(points, points[1:] + points[:1]):
                            edges[tuple(sorted((a, b)))] += 1
                    with self.subTest(kind=kind, pump=fraction, part=part['name']):
                        self.assertTrue(edges)
                        self.assertTrue(all(n == 2 for n in edges.values()), 'open surface exposes the background')

    def test_actual_sights_share_a_clear_center_ray(self):
        mesh = self.meshes['view']
        rear, front = (np.asarray(mesh['anchors'][name]) for name in ('rear_sight', 'front_sight'))
        np.testing.assert_array_equal(rear[1:], front[1:])
        self.assertGreater(front[0] - rear[0], 30.)
        entry = next(m for m in self.manifest['models'] if m['role'] == 'view')
        anchors = entry['anchors_frame0']
        self.assertGreater(anchors['muzzle'][0], anchors['front_sight'][0])
        # Ray/triangle intersections reveal blocked rear notches and barrels
        # even when their vertices individually sit outside the sight line.
        triangles = np.asarray(mesh['vertices'])[np.asarray(mesh['faces'])]
        direction = np.array([1., 0., 0.])
        edge1, edge2 = triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]
        h = np.cross(direction, edge2)
        determinant = np.einsum('ij,ij->i', edge1, h)
        valid = np.abs(determinant) > 1e-9
        inverse = np.zeros(len(valid)); inverse[valid] = 1 / determinant[valid]
        s = rear - triangles[:, 0]
        u = inverse * np.einsum('ij,ij->i', s, h)
        q = np.cross(s, edge1)
        v = inverse * (q @ direction)
        distance = inverse * np.einsum('ij,ij->i', edge2, q)
        blocked = valid & (u >= 0) & (v >= 0) & (u + v <= 1) & (distance > .15) & (distance < front[0] - rear[0] - .15)
        # The front blade itself intentionally ends the ray at its top edge.
        front_part = next(p for p in mesh['parts'] if p['name'] == 'front_sight')
        a = front_part['first_triangle']; b = a + front_part['triangle_count']
        blocked[a:b] = False
        self.assertFalse(np.any(blocked), 'geometry blocks the centered rear/front sight ray')

    def test_held_animation_names_and_static_receiver_follow_archived_motion(self):
        originals = json.loads((ROOT / 'tools/assets/platoon-originals.json').read_text())
        mesh = self.meshes['world']
        receiver = self.part_indices(mesh, 'receiver')
        for path, role in builder.MODELS.items():
            if role not in ('player', 'enemy'):
                continue
            with self.subTest(role=role):
                original = MD2.read(source_bytes(originals, 'baseq2/' + path), source_compat=True)
                output = MD2.read(self.assets[path])
                self.assertEqual(output.names, original.names)
                rotations, translations, errors = rigid_transforms(original)
                self.assertLess(errors.max(), .12)
                matrix, offset, _ = builder.placement(role)
                posed = np.asarray(mesh['vertices'])[receiver] @ matrix + offset
                expected = np.asarray([posed @ r + t for r, t in zip(rotations, translations)])
                error = np.linalg.norm(output.positions[:, receiver] - expected, axis=2)
                limit = np.linalg.norm(output.scales, axis=1) / 2 + 1e-5
                self.assertTrue(np.all(error <= limit[:, None]))
                # The newly authored world pump must also move during attack.
                pump_name = next(p['name'] for p in mesh['parts'] if p['name'] == 'pump' or p['name'].startswith('pump_'))
                pump = self.part_indices(mesh, pump_name)
                canonical = np.asarray([(positions[pump] - t) @ np.linalg.inv(r)
                                        for positions, r, t in zip(output.positions, rotations, translations)])
                center = canonical.mean(axis=1)
                self.assertGreater(np.ptp(center[:, 0]), 1., 'held shotgun pump never cycles')

    def test_tall_enemy_preserves_foot_anchored_scale_and_pose_layout(self):
        normal = MD2.read(self.assets['models/monsters/soldier/weapon_shotgun.md2'])
        tall = MD2.read(self.assets['models/monsters/soldier/tall/weapon_shotgun.md2'])
        self.assertEqual(normal.names, tall.names)
        np.testing.assert_array_equal(normal.faces, tall.faces)
        expected = normal.positions * 1.2
        expected[:, :, 2] += 4.8
        np.testing.assert_allclose(tall.positions, expected, atol=8e-6)

    def test_atlas_and_winding_match_existing_army_man_materials(self):
        for path in builder.TEXTURES:
            with Image.open(io.BytesIO(self.assets[path])) as image:
                self.assertEqual(image.size, (256, 256))
                self.assertEqual(image.mode, 'RGB')
        model = MD2.read(self.assets['models/weapons/g_shotg/tris.md2'])
        points = model.positions[0, model.faces]
        normals = np.cross(points[:, 1] - points[:, 0], points[:, 2] - points[:, 0])
        normals /= np.linalg.norm(normals, axis=1)[:, None]
        stored = normal_table()[model.normals[0, model.faces]].mean(axis=1)
        self.assertLess(np.median(np.sum(normals * stored, axis=1)), -.65)
        self.assertTrue(np.all(model.uvs > 0))
        self.assertTrue(np.all(model.uvs < 1))
        for kind, mesh in self.meshes.items():
            hands = {p['name'] for p in mesh['parts'] if p['name'].startswith(('arm_', 'hand_'))}
            if kind == 'view':
                self.assertTrue({'arm_left', 'arm_right', 'hand_left_palm', 'hand_right_palm'} <= hands)
            else:
                self.assertFalse(hands)

    def test_legacy_rebuild_cannot_restore_the_replaced_shotgun(self):
        import build_platoon
        config = json.loads(build_platoon.CONFIG.read_text())
        self.assertTrue(set(builder.MODELS) <= build_platoon.procedural_paths(config))
        manifest = json.loads(build_platoon.MANIFEST.read_text())
        self.assertFalse(set(builder.MODELS) & {m['path'] for m in manifest['models']})


if __name__ == '__main__':
    unittest.main(verbosity=2)
