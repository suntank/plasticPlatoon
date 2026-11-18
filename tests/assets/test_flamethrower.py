#!/usr/bin/env python3
"""Validate the shipped flame wand, independently moving pack and attached hose."""
from collections import Counter
import copy
import io
import json
from pathlib import Path
import re
import sys
import unittest

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/assets'))
import build_flamethrower as builder
from build_color_variants import material_mask
from build_m16 import MATERIALS
from build_m16 import rigid_transforms, texture_bytes as rifle_texture_bytes
from flamethrower_geometry import (build_flamethrower, combine_meshes, hose_mesh,
                                  HOSE_CONTROLS, INLET)
from m16_geometry import build_m16
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
    return distance[valid & (u >= -1e-8) & (v >= -1e-8) & (u + v <= 1 + 1e-8) &
                    (distance > 1e-6) & (distance < maximum)]


class FlamethrowerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets, cls.manifest, cls.header = builder.build_assets()
        cls.assembled, cls.gun, cls.pack, cls.hose = builder.build_assembled()
        cls.view = combine_meshes((build_flamethrower('view'),
            hose_mesh(((1., -11., -30.), (9., -10., -18.), (22., -7., -12.), INLET),
                      radius=1.4, detail='view')), 'view')
        originals = json.loads((ROOT / 'tools/assets/platoon-originals.json').read_text())
        cls.source, cls.repair, cls.motion = builder.source_motion(originals)
        # Refit each archived component independently for the test reference.
        # A single fit to the complete source is specifically invalid here.
        cls.reference_motion = {}
        for name, (a, b) in builder.SOURCE_GROUPS.items():
            selected = copy.copy(cls.source)
            selected.positions = cls.source.positions[:, a:b]
            cls.reference_motion[name] = rigid_transforms(selected)
        cls.player = MD2.read(cls.assets['players/soldier/w_hyperblaster.md2'])

    @staticmethod
    def part(mesh, name):
        return next(part for part in mesh['parts'] if part['name'] == name)

    @classmethod
    def part_vertices(cls, mesh, name):
        part = cls.part(mesh, name)
        a = part['first_triangle']; b = a + part['triangle_count']
        return np.asarray(mesh['vertices'])[np.asarray(mesh['faces'])[a:b]].reshape(-1, 3)

    def test_exact_shipped_assets_hashes_dependencies_manifest_and_header(self):
        inventory = {entry['path']: entry for entry in self.manifest['files']}
        self.assertEqual(set(inventory), set(self.assets))
        for path, raw in self.assets.items():
            with self.subTest(path=path):
                self.assertEqual((ROOT / 'baseq2' / path).read_bytes(), raw)
                self.assertEqual(inventory[path]['bytes'], len(raw))
                self.assertEqual(inventory[path]['sha256'], builder.sha(raw))
        self.assertEqual(json.loads(builder.MANIFEST.read_text()), self.manifest)
        self.assertEqual(builder.ADS_HEADER.read_bytes(), self.header)
        for name, digest in self.manifest['dependencies_sha256'].items():
            self.assertEqual(builder.sha((ROOT / 'tools/assets' / name).read_bytes()), digest)

    def test_budgets_static_view_and_runtime_skin_references(self):
        self.assertEqual(builder.MODELS, {'models/weapons/g_hyperb/tris.md2': 'pickup',
            'models/weapons/v_hyperb/tris.md2': 'view', 'players/soldier/w_hyperblaster.md2': 'player'})
        counts = {'view': 888, 'pickup': 736, 'player': 736}
        frames = {'view': 1, 'pickup': 1, 'player': 198}
        for entry in self.manifest['models']:
            model = MD2.read(self.assets[entry['path']])
            with self.subTest(role=entry['role']):
                self.assertEqual(len(model.faces), counts[entry['role']])
                self.assertLess(len(model.faces), 900 if entry['role'] == 'view' else 750)
                self.assertLess(len(model.faces), entry['baseline']['triangles'])
                self.assertEqual(model.header[10], frames[entry['role']])
                self.assertEqual(model.header[4], 40 + 4 * model.header[6])
                self.assertEqual(model.command_triangles, len(model.faces))
                self.assertTrue(all(skin in self.assets for skin in model.skins))
                self.assertTrue(np.all(model.uvs > 0))
                self.assertTrue(np.all(model.uvs < 1))

    def test_hash_pinned_source_repair_and_two_component_motion(self):
        self.assertEqual(builder.SOURCE_GROUPS, {'gun': (0, 284), 'backpack': (284, 1366)})
        self.assertEqual(self.source.header[6], 1366)
        self.assertEqual(self.repair['source_sha256'], builder.SOURCE_HASH)
        self.assertEqual(self.repair['preserved_frames'], 198)
        self.assertGreater(self.repair['invalid_xyz_triangles'], 0)
        self.assertEqual(self.manifest['source_repair'], self.repair)
        self.assertFalse(np.any((self.source.faces.min(axis=1) < 284) &
                                (self.source.faces.max(axis=1) >= 284)))
        self.assertEqual(self.player.names, self.source.names)
        for name in ('gun', 'backpack'):
            for actual, reference in zip(self.motion[name], self.reference_motion[name]):
                np.testing.assert_allclose(actual, reference, atol=1e-10)
            self.assertLess(self.motion[name][2].max(), .12)
        with self.assertRaisesRegex(ValueError, 'not rigid'):
            rigid_transforms(self.source)

    def test_all_198_gun_and_pack_poses_follow_their_own_archived_components(self):
        cursor = 0
        limit = np.linalg.norm(self.player.scales, axis=1) / 2 + 1e-5
        for name, mesh in (('gun', self.gun), ('backpack', self.pack)):
            reference = np.asarray(mesh['vertices'])
            rotations, translations, _ = self.reference_motion[name]
            expected = np.asarray([reference @ rotation + translation
                                   for rotation, translation in zip(rotations, translations)])
            actual = self.player.positions[:, cursor:cursor + len(reference)]
            error = np.linalg.norm(actual - expected, axis=2)
            with self.subTest(component=name):
                self.assertTrue(np.all(error <= limit[:, None]))
                # In torso/gun local space the part retains its fitted size
                # through standing, crouched, firing, running and death poses.
                restored = np.asarray([(points - translation) @ rotation.T
                    for points, rotation, translation in zip(actual, rotations, translations)])
                self.assertTrue(np.all(np.abs(restored.min(axis=1) - reference.min(axis=0)) <= limit[:, None]))
                self.assertTrue(np.all(np.abs(restored.max(axis=1) - reference.max(axis=0)) <= limit[:, None]))
            cursor += len(reference)

    def test_hose_rings_and_endpoints_follow_pack_and_gun_in_all_198_poses(self):
        controls = np.asarray(HOSE_CONTROLS)
        np.testing.assert_allclose(controls[0], self.pack['anchors']['outlet'])
        np.testing.assert_allclose(controls[3], self.gun['anchors']['inlet'])
        reference = np.asarray(self.hose['vertices'])
        self.assertEqual(reference.shape, (8 * 6, 3))
        times = np.linspace(0., 1., 8)
        reference_centers = np.asarray([(1-t)**3 * controls[0] + 3*(1-t)**2*t*controls[1] +
            3*(1-t)*t*t*controls[2] + t**3*controls[3] for t in times])
        rings = [np.flatnonzero(np.abs(np.linalg.norm(reference - center, axis=1) - .65) < 1e-7)
                 for center in reference_centers]
        self.assertTrue(all(len(ring) == 6 for ring in rings))
        self.assertEqual(len(np.unique(np.concatenate(rings))), 48)
        cursor = len(self.gun['vertices']) + len(self.pack['vertices'])
        gun_rot, gun_offset, _ = self.reference_motion['gun']
        pack_rot, pack_offset, _ = self.reference_motion['backpack']
        for frame in range(198):
            posed_controls = np.concatenate((controls[:2] @ pack_rot[frame] + pack_offset[frame],
                controls[2:] @ gun_rot[frame] + gun_offset[frame]))
            centers = np.asarray([(1-t)**3 * posed_controls[0] + 3*(1-t)**2*t*posed_controls[1] +
                3*(1-t)*t*t*posed_controls[2] + t**3*posed_controls[3] for t in times])
            actual = self.player.positions[frame, cursor:]
            limit = np.linalg.norm(self.player.scales[frame]) / 2 + 1e-5
            with self.subTest(frame=frame):
                for ring, center in zip(rings, centers):
                    self.assertLessEqual(np.linalg.norm(actual[ring].mean(axis=0) - center), limit)
                    self.assertTrue(np.all(np.abs(np.linalg.norm(actual[ring] - center, axis=1) - .65) <= limit))
                np.testing.assert_allclose(actual[rings[0]].mean(axis=0), posed_controls[0], atol=limit)
                np.testing.assert_allclose(actual[rings[-1]].mean(axis=0), posed_controls[3], atol=limit)

    def test_pack_body_fit_and_representation_coverage(self):
        names = {part['name'] for part in self.assembled['parts']}
        required = {'nozzle', 'pack_tank_left', 'pack_tank_right', 'pack_backplate',
                    'pack_pressure_bottle', 'pack_manifold', 'pack_outlet', 'fuel_hose'}
        self.assertTrue(required <= names)
        for role in ('pickup', 'player'):
            entry = next(entry for entry in self.manifest['models'] if entry['role'] == role)
            self.assertTrue(required <= {part['name'] for part in entry['parts']})
        self.assertFalse(any(part['name'].startswith('pack_') for part in self.view['parts']))
        self.assertIn('fuel_hose', {part['name'] for part in self.view['parts']})
        pack = np.asarray(self.pack['vertices'])
        self.assertGreaterEqual(pack[:, 0].min(), -14.)
        self.assertLess(pack[:, 0].max(), -3.)
        self.assertLessEqual(np.abs(pack[:, 1]).max(), 8.)
        self.assertGreaterEqual(pack[:, 2].min(), 7.)
        body = MD2.read((ROOT / 'baseq2/players/soldier/tris.md2').read_bytes()).positions[0]
        self.assertLess(pack[:, 2].max(), body[:, 2].max() - 4.)
        torso = body[(body[:, 2] > 7.) & (body[:, 2] < 23.) & (np.abs(body[:, 1]) < 6.5)]
        backplate = self.part_vertices(self.pack, 'pack_backplate')
        self.assertLess(abs(backplate[:, 0].max() - torso[:, 0].min()), 1.5)

    def test_existing_hands_and_arm_geometry_and_materials_are_exact(self):
        rifle = build_m16('view')
        prefixes = ('hand_', 'arm_', 'cuff_')
        names = {part['name'] for part in self.view['parts'] if part['name'].startswith(prefixes)}
        self.assertEqual(names, {part['name'] for part in rifle['parts'] if part['name'].startswith(prefixes)})
        for name in names:
            with self.subTest(part=name):
                np.testing.assert_array_equal(self.part_vertices(self.view, name), self.part_vertices(rifle, name))
        self.assertFalse(any(part['name'].startswith(prefixes) for part in self.assembled['parts']))
        with Image.open(io.BytesIO(rifle_texture_bytes())) as rifle_atlas:
            for path in builder.TEXTURES:
                with Image.open(io.BytesIO(self.assets[path])) as image:
                    self.assertEqual(image.size, (256, 256))
                    self.assertEqual(image.mode, 'RGB')
                    for material in ('hand','cuff','fingers'):
                        row,column = divmod(MATERIALS.index(material),4)
                        box = (column*64,row*64,(column+1)*64,(row+1)*64)
                        self.assertEqual(image.crop(box).tobytes(),rifle_atlas.crop(box).tobytes())

    def test_all_visible_materials_take_player_color(self):
        path = builder.TEXTURES[1]
        with Image.open(io.BytesIO(self.assets[path])) as image:
            mask, _ = material_mask(image, path, 'player')
        for material in sorted(set(self.assembled['materials']) | set(self.view['materials'])):
            row,column = divmod(MATERIALS.index(material),4)
            box = (column*64,row*64,(column+1)*64,(row+1)*64)
            with self.subTest(material=material):
                self.assertEqual(mask.crop(box).getextrema(),(255,255))

    def test_every_wand_tank_hose_hand_and_arm_part_is_closed(self):
        for mesh in (self.assembled, self.view):
            vertices = np.round(np.asarray(mesh['vertices']), 7)
            for part in mesh['parts']:
                a = part['first_triangle']; b = a + part['triangle_count']
                edges = Counter()
                for face in mesh['faces'][a:b]:
                    points = [tuple(vertices[index]) for index in face]
                    for start, end in zip(points, points[1:] + points[:1]):
                        edges[tuple(sorted((start, end)))] += 1
                with self.subTest(detail=mesh['detail'], part=part['name']):
                    self.assertTrue(edges)
                    self.assertTrue(all(count == 2 for count in edges.values()))

    def test_quantized_faces_never_collapse_or_reverse_in_any_held_pose(self):
        controls = np.asarray(HOSE_CONTROLS)
        gun_rot, gun_offset, _ = self.reference_motion['gun']
        pack_rot, pack_offset, _ = self.reference_motion['backpack']
        for frame in range(198):
            posed_controls = np.concatenate((controls[:2] @ pack_rot[frame] + pack_offset[frame],
                controls[2:] @ gun_rot[frame] + gun_offset[frame]))
            hose = hose_mesh(posed_controls, seed=np.array([1., 0., 0.]) @ pack_rot[frame])
            expected = np.concatenate((np.asarray(self.gun['vertices']) @ gun_rot[frame] + gun_offset[frame],
                np.asarray(self.pack['vertices']) @ pack_rot[frame] + pack_offset[frame], hose['vertices']))
            reference = expected[self.player.faces]
            actual = self.player.positions[frame, self.player.faces]
            target = np.cross(reference[:, 1] - reference[:, 0], reference[:, 2] - reference[:, 0])
            normal = np.cross(actual[:, 1] - actual[:, 0], actual[:, 2] - actual[:, 0])
            with self.subTest(frame=frame):
                self.assertGreater(np.linalg.norm(normal, axis=1).min(), 1e-9)
                self.assertTrue(np.all(np.einsum('ij,ij->i', target, normal) > 0))
                self.assertTrue(np.all(np.linalg.norm(self.player.positions[frame] - expected, axis=1) <=
                                       np.linalg.norm(self.player.scales[frame]) / 2 + 1e-5))
        points = self.player.positions[:, self.player.faces]
        normal = np.cross(points[:, :, 1] - points[:, :, 0], points[:, :, 2] - points[:, :, 0])
        normal /= np.linalg.norm(normal, axis=2)[:, :, None]
        stored = normal_table()[self.player.normals[:, self.player.faces]].mean(axis=2)
        self.assertLess(np.quantile(np.sum(normal * stored, axis=2), .99), 0.)

    def test_decoded_view_sight_channel_and_recessed_nozzle(self):
        model = MD2.read(self.assets['models/weapons/v_hyperb/tris.md2'])
        matrix, offset, _ = builder.placement('view')
        vertices = (model.positions[0] - offset) @ np.linalg.inv(matrix)
        triangles = vertices[model.faces]
        a = self.part(self.view, 'front_sight')['first_triangle']
        b = a + self.part(self.view, 'front_sight')['triangle_count']
        channel = np.concatenate((triangles[:a], triangles[b:]))
        rear = np.asarray(self.view['anchors']['rear_sight'])
        sight_length = self.view['anchors']['front_sight'][0]-rear[0]
        self.assertEqual(len(ray_distances(channel, rear, (1., 0., 0.), sight_length)), 0)
        part = self.part(self.view, 'nozzle')
        a = part['first_triangle']; b = a + part['triangle_count']
        hits = ray_distances(triangles[a:b], (94., 0., 0.), (-1., 0., 0.))
        self.assertGreater(len(hits), 0)
        self.assertGreater(hits.min() - 2., 3.)
        self.assertLess(hits.min() - 2., 6.)
        values = {name: float(value) for name, value in re.findall(
            r'#define PP_FLAMETHROWER_(\w+) \(([-\d.]+)f\)', self.header.decode())}
        rear = rear @ matrix + offset
        self.assertAlmostEqual(rear[0] + values['ADS_FORWARD'], 9.5, places=6)
        self.assertAlmostEqual(-rear[1] + values['ADS_RIGHT'], 0., places=6)
        self.assertAlmostEqual(rear[2] + values['ADS_UP'], 0., places=6)

    def test_registered_ownership_excludes_legacy_overwrites(self):
        import build_platoon
        config = json.loads(build_platoon.CONFIG.read_text())
        registered = config['procedural_replacements']['flamethrower']
        self.assertEqual(set(registered['models']), set(builder.MODELS))
        self.assertEqual(set(registered['textures']), set(builder.TEXTURES))
        self.assertTrue(set(builder.MODELS) <= build_platoon.procedural_paths(config))
        legacy = json.loads(build_platoon.MANIFEST.read_text())
        self.assertFalse(set(builder.MODELS) & {entry['path'] for entry in legacy['models']})


if __name__ == '__main__':
    unittest.main(verbosity=2)
