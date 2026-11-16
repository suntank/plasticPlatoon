#!/usr/bin/env python3
"""Validate the carried mortar, deployed pickup, real bore and existing hands."""
from collections import Counter
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
import build_mortar as builder
from asset_sources import source_bytes
from build_m16 import rigid_transforms, texture_bytes as rifle_texture_bytes
from m16_geometry import build_m16
from md2_assets import MD2, normal_table
from mortar_geometry import build_mortar, deployed_point, PICKUP_ROTATION


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


class MortarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets, cls.manifest, cls.header = builder.build_assets()
        cls.meshes = {kind: build_mortar(kind) for kind in ('world', 'view', 'pickup')}
        originals = json.loads((ROOT / 'tools/assets/platoon-originals.json').read_text())
        cls.source = MD2.read(source_bytes(originals, 'baseq2/players/soldier/w_bfg.md2'), source_compat=True)
        cls.motion = rigid_transforms(cls.source)
        cls.player = MD2.read(cls.assets['players/soldier/w_bfg.md2'])

    @staticmethod
    def part(mesh, name):
        return next(part for part in mesh['parts'] if part['name'] == name)

    @classmethod
    def part_vertices(cls, mesh, name):
        part = cls.part(mesh, name)
        a = part['first_triangle']; b = a + part['triangle_count']
        return np.asarray(mesh['vertices'])[np.asarray(mesh['faces'])[a:b]].reshape(-1, 3)

    def decoded(self, role, undo_deployment=False):
        entry = next(entry for entry in self.manifest['models'] if entry['role'] == role)
        model = MD2.read(self.assets[entry['path']])
        matrix, offset, _ = builder.placement(role)
        vertices = (model.positions[0] - offset) @ np.linalg.inv(matrix)
        if undo_deployment:
            vertices = (vertices - [0., 0., 4.]) @ PICKUP_ROTATION.T + [18., 0., 2.8]
        return model, vertices, vertices[model.faces]

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

    def test_budget_and_single_cached_view_pickup_with_all_198_held_frames(self):
        self.assertEqual(builder.MODELS, {'models/weapons/g_bfg/tris.md2': 'pickup',
                         'models/weapons/v_bfg/tris.md2': 'view', 'players/soldier/w_bfg.md2': 'player'})
        counts = {'view': 740, 'pickup': 328, 'player': 312}
        frames = {'view': 1, 'pickup': 1, 'player': 198}
        for entry in self.manifest['models']:
            model = MD2.read(self.assets[entry['path']])
            with self.subTest(role=entry['role']):
                self.assertEqual(len(model.faces), counts[entry['role']])
                self.assertLess(len(model.faces), 800 if entry['role'] == 'view' else 400)
                self.assertLess(len(model.faces), entry['baseline']['triangles'])
                self.assertEqual(model.header[10], frames[entry['role']])
                self.assertEqual(model.header[4], 40 + 4 * model.header[6])
                self.assertEqual(model.command_triangles, len(model.faces))
                self.assertTrue(all(skin in self.assets for skin in model.skins))
                self.assertTrue(np.all(model.uvs > 0))
                self.assertTrue(np.all(model.uvs < 1))

    def test_deployed_pickup_keeps_the_same_core_at_55_degree_elevation(self):
        carried, pickup = self.meshes['world'], self.meshes['pickup']
        core = carried['parts'][:next(i for i, part in enumerate(carried['parts']) if part['name'] == 'baseplate')]
        for part in core:
            name = part['name']
            with self.subTest(part=name):
                np.testing.assert_allclose(self.part_vertices(pickup, name),
                    deployed_point(self.part_vertices(carried, name)), atol=1e-12)
        for name, anchor in carried['anchors'].items():
            np.testing.assert_allclose(pickup['anchors'][name], deployed_point(anchor), atol=1e-12)
        model, vertices, _ = self.decoded('pickup')
        part = self.part(pickup, 'mortar_tube')
        a = part['first_triangle']; b = a + part['triangle_count']
        indices = np.unique(model.faces[a:b])
        local = (vertices[indices] - [0., 0., 4.]) @ PICKUP_ROTATION.T + [18., 0., 2.8]
        rear = vertices[indices[local[:, 0] < 18.3]].mean(axis=0)
        front = vertices[indices[local[:, 0] > 85.7]].mean(axis=0)
        axis = front - rear
        self.assertAlmostEqual(np.degrees(np.arctan2(axis[2], axis[0])), 55., delta=.5)

    def test_flat_deployed_plate_ground_feet_and_distinct_carried_supports(self):
        required = {'mortar_tube', 'baseplate', 'bipod_mount', 'bipod_left', 'bipod_right',
                    'bipod_foot_left', 'bipod_foot_right', 'bipod_crossbrace'}
        for kind, mesh in self.meshes.items():
            self.assertTrue(required <= {part['name'] for part in mesh['parts']})
        world, pickup = self.meshes['world'], self.meshes['pickup']
        carried_plate = self.part_vertices(world, 'baseplate')
        deployed_plate = self.part_vertices(pickup, 'baseplate')
        self.assertLess(np.ptp(carried_plate[:, 0]), 3.1)
        self.assertGreaterEqual(carried_plate[:, 0].min(), 17.9)
        self.assertLessEqual(carried_plate[:, 0].max(), 21.1)
        self.assertGreater(np.ptp(carried_plate[:, 2]), 25.)
        self.assertLess(np.ptp(deployed_plate[:, 2]), 3.1)
        self.assertGreater(np.ptp(deployed_plate[:, 0]), 35.)
        self.assertGreater(np.ptp(deployed_plate[:, 1]), 35.)
        self.assertAlmostEqual(deployed_plate[:, 2].min(), 0.)
        for side in ('left', 'right'):
            carried = self.part_vertices(world, 'bipod_foot_' + side)
            deployed = self.part_vertices(pickup, 'bipod_foot_' + side)
            self.assertLess(carried[:, 2].max(), -20.)
            self.assertGreaterEqual(deployed[:, 2].min(), 0.)
            self.assertLess(deployed[:, 2].min(), 1.)
            self.assertLess(deployed[:, 2].max(), 3.)
            self.assertGreater(np.abs(deployed[:, 1]).mean(), 15.)
        self.assertIn('baseplate_hinge', {part['name'] for part in world['parts']})
        self.assertIn('baseplate_socket', {part['name'] for part in pickup['parts']})

    def test_existing_hands_and_forearms_and_shared_atlas_are_exact(self):
        view, rifle = self.meshes['view'], build_m16('view')
        prefixes = ('hand_', 'arm_', 'cuff_')
        names = {part['name'] for part in view['parts'] if part['name'].startswith(prefixes)}
        self.assertEqual(names, {part['name'] for part in rifle['parts'] if part['name'].startswith(prefixes)})
        for name in names:
            with self.subTest(part=name):
                np.testing.assert_array_equal(self.part_vertices(view, name), self.part_vertices(rifle, name))
        for kind in ('world', 'pickup'):
            self.assertFalse(any(part['name'].startswith(prefixes) for part in self.meshes[kind]['parts']))
        for path in builder.TEXTURES:
            self.assertEqual(self.assets[path], rifle_texture_bytes())
            with Image.open(io.BytesIO(self.assets[path])) as image:
                self.assertEqual(image.size, (256, 256))
                self.assertEqual(image.mode, 'RGB')

    def test_all_tube_plate_bipod_hand_and_arm_parts_are_closed(self):
        for kind, mesh in self.meshes.items():
            vertices = np.round(np.asarray(mesh['vertices']), 7)
            for part in mesh['parts']:
                a = part['first_triangle']; b = a + part['triangle_count']
                edges = Counter()
                for face in mesh['faces'][a:b]:
                    points = [tuple(vertices[index]) for index in face]
                    for start, end in zip(points, points[1:] + points[:1]):
                        edges[tuple(sorted((start, end)))] += 1
                with self.subTest(detail=kind, part=part['name']):
                    self.assertTrue(edges)
                    self.assertTrue(all(count == 2 for count in edges.values()))

    def test_decoded_carried_and_deployed_tube_has_a_real_deep_bore(self):
        for role, kind in (('view', 'view'), ('pickup', 'pickup')):
            _, _, triangles = self.decoded(role, undo_deployment=role == 'pickup')
            part = self.part(self.meshes[kind], 'mortar_tube')
            a = part['first_triangle']; b = a + part['triangle_count']
            points = triangles[a:b].reshape(-1, 3)
            rim = points[np.abs(points[:, 0] - 86.) < .3]
            radii = np.linalg.norm(rim[:, 1:] - [0., 2.8], axis=1)
            self.assertAlmostEqual(radii.min(), 3.5, delta=.25)
            self.assertAlmostEqual(radii.max(), 5.3, delta=.25)
            for y, z in ((0., 2.8), (2.5, 2.8), (-2.5, 3.3)):
                with self.subTest(role=role, y=y, z=z):
                    hits = ray_distances(triangles[a:b], (88., y, z), (-1., 0., 0.))
                    self.assertGreater(len(hits), 0)
                    depth = hits.min() - 2.
                    self.assertGreater(depth, 60., 'mortar bore is capped too close to the muzzle')
                    self.assertLess(depth, 65.)
            if role == 'view':
                hits = ray_distances(triangles, (88., 0., 2.8), (-1., 0., 0.))
                self.assertGreater(hits.min() - 2., 60., 'a hand or receiver blocks the true deep bore')

    def test_decoded_real_sight_channel_and_generated_ads_alignment(self):
        mesh = self.meshes['view']
        self.assertEqual(mesh['anchors']['rear_sight'], [32., 0., 10.2])
        self.assertEqual(mesh['anchors']['front_sight'], [80., 0., 10.2])
        _, _, triangles = self.decoded('view')
        part = self.part(mesh, 'front_sight')
        a = part['first_triangle']; b = a + part['triangle_count']
        channel = np.concatenate((triangles[:a], triangles[b:]))
        for y in (0., -.25, .25):
            self.assertEqual(len(ray_distances(channel, (32., y, 10.2), (1., 0., 0.), 48.)), 0)
        values = {name: float(value) for name, value in re.findall(
            r'#define PP_MORTAR_(\w+) \(([-\d.]+)f\)', self.header.decode())}
        matrix, offset, _ = builder.placement('view')
        rear = np.asarray(mesh['anchors']['rear_sight']) @ matrix + offset
        self.assertAlmostEqual(rear[0] + values['ADS_FORWARD'], builder.ADS_EYE_RELIEF, places=6)
        self.assertAlmostEqual(-rear[1] + values['ADS_RIGHT'], 0., places=6)
        self.assertAlmostEqual(rear[2] + values['ADS_UP'], 0., places=6)

    def test_camera_stays_outside_the_tube_through_aim_and_full_recoil(self):
        # Read the actual client recoil settings rather than assuming the
        # current 12-unit push/12-degree kick will never be retuned.
        source = (ROOT / 'src/client/cl_entities.c').read_text()
        fields = re.search(r'/\*\s*PP_WEAPON_MORTAR\s*\*/\s*\{([^}]+)\}', source)[1]
        strength, _, _, pitch_kick, push_back = [float(value.strip().rstrip('f'))
                                                for value in fields.split(',')]
        values = {name: float(value) for name, value in re.findall(
            r'#define PP_MORTAR_(\w+) \(([-\d.]+)f\)', self.header.decode())}
        matrix, offset, _ = builder.placement('view')
        inverse = np.linalg.inv(matrix)
        scale = np.linalg.norm(matrix[0])
        mesh = self.meshes['view']
        part = self.part(mesh, 'mortar_tube')
        a = part['first_triangle']; b = a + part['triangle_count']
        _, _, triangles = self.decoded('view')
        plastic = np.asarray(mesh['materials'][a:b]) == 'plastic'
        outer = np.unique(triangles[a:b][plastic].reshape(-1, 3), axis=0)
        axial = np.unique(outer[:, 0])
        center_y, center_z = mesh['anchors']['muzzle'][1:]
        radii = np.asarray([np.linalg.norm(outer[outer[:, 0] == x, 1:] -
                            [center_y, center_z], axis=1).max() for x in axial])

        def clearances(forward):
            distances = []
            for blend in np.linspace(0., 1., 41):
                for recoil in np.linspace(0., strength, 41):
                    # This is the production alias matrix convention used by
                    # GL1/GL3: pitch is applied after the mesh's pitch flip.
                    pitch = np.radians(-recoil * pitch_kick)
                    cosine, sine = np.cos(pitch), np.sin(pitch)
                    rotation = np.array([[cosine, 0., -sine], [0., 1., 0.],
                                         [sine, 0., cosine]])
                    origin = blend * np.array([forward, -values['ADS_RIGHT'], values['ADS_UP']])
                    origin += [-recoil * push_back, 0., recoil]
                    # Invert the resolved weapon pose to locate the eye in
                    # the canonical exported mortar's coordinates.
                    eye = ((-origin) @ rotation.T - offset) @ inverse
                    radial = np.linalg.norm(eye[1:] - [center_y, center_z])
                    radius = np.interp(eye[0], axial, radii)
                    axial_gap = max(axial[0] - eye[0], eye[0] - axial[-1], 0.)
                    radial_gap = max(radial - radius, 0.)
                    # A finite circular envelope conservatively includes the
                    # octagonal casing AND bore: being inside the empty bore
                    # also gives the unwanted full-screen green tube view.
                    distances.append(np.hypot(axial_gap, radial_gap) * scale)
            return np.asarray(distances)

        self.assertGreater(clearances(values['ADS_FORWARD']).min(), .1,
                           'eye/weapon near plane enters the tube during aim or recoil')
        rear = np.asarray(mesh['anchors']['rear_sight']) @ matrix + offset
        self.assertLess(clearances(9.5 - rear[0]).min(), .001,
                        'clearance check must detect the previous short eye-relief failure')

    def test_all_198_held_poses_and_faces_follow_pinned_rigid_motion(self):
        self.assertEqual(self.player.names, self.source.names)
        rotations, translations, errors = self.motion
        self.assertLess(errors.max(), .12)
        matrix, offset, _ = builder.placement('player')
        reference = np.asarray(self.meshes['world']['vertices']) @ matrix + offset
        expected = np.asarray([reference @ rotation + translation
                               for rotation, translation in zip(rotations, translations)])
        limit = np.linalg.norm(self.player.scales, axis=1) / 2 + 1e-5
        self.assertTrue(np.all(np.linalg.norm(self.player.positions - expected, axis=2) <= limit[:, None]))
        targets = expected[:, self.player.faces]
        points = self.player.positions[:, self.player.faces]
        target_normals = np.cross(targets[:, :, 1] - targets[:, :, 0], targets[:, :, 2] - targets[:, :, 0])
        normals = np.cross(points[:, :, 1] - points[:, :, 0], points[:, :, 2] - points[:, :, 0])
        self.assertGreater(np.linalg.norm(normals, axis=2).min(), 1e-9)
        self.assertTrue(np.all(np.einsum('ijk,ijk->ij', target_normals, normals) > 0))
        normals /= np.linalg.norm(normals, axis=2)[:, :, None]
        stored = normal_table()[self.player.normals[:, self.player.faces]].mean(axis=2)
        self.assertLess(np.median(np.sum(normals * stored, axis=2)), -.65)

    def test_registered_ownership_excludes_legacy_overwrites(self):
        import build_platoon
        config = json.loads(build_platoon.CONFIG.read_text())
        registration = config['procedural_replacements']['mortar']
        self.assertEqual(set(registration['models']), set(builder.MODELS))
        self.assertEqual(set(registration['textures']), set(builder.TEXTURES))
        self.assertTrue(set(builder.MODELS) <= build_platoon.procedural_paths(config))
        legacy = json.loads(build_platoon.MANIFEST.read_text())
        self.assertFalse(set(builder.MODELS) & {entry['path'] for entry in legacy['models']})


if __name__ == '__main__':
    unittest.main(verbosity=2)
