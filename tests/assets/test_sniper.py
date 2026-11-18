#!/usr/bin/env python3
"""Validate shipped sniper geometry, preserved hands, animation and open optics."""
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
import build_sniper as builder
from asset_sources import source_bytes
from build_color_variants import material_mask
from build_m16 import MATERIALS, rigid_transforms, texture_bytes as rifle_texture_bytes
from m16_geometry import build_m16
from md2_assets import MD2, normal_table
from sniper_geometry import build_sniper


def ray_hits(triangles, origin, direction=(1., 0., 0.), maximum=np.inf):
    """Return triangle indices and distances for actual exported face interiors."""
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
    hits = valid & (u >= -1e-8) & (v >= -1e-8) & (u + v <= 1 + 1e-8) & (distance > 1e-6) & (distance < maximum)
    return np.flatnonzero(hits), distance[hits]


class SniperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets, cls.manifest, cls.header = builder.build_assets()
        cls.meshes = {kind: build_sniper(kind) for kind in ('world', 'view')}

    @staticmethod
    def part(mesh, name):
        return next(part for part in mesh['parts'] if part['name'] == name)

    @classmethod
    def part_vertices(cls, mesh, name):
        part = cls.part(mesh, name)
        a = part['first_triangle']; b = a + part['triangle_count']
        return np.asarray(mesh['vertices'])[np.asarray(mesh['faces'])[a:b]].reshape(-1, 3)

    def decoded(self, role):
        entry = next(entry for entry in self.manifest['models'] if entry['role'] == role)
        model = MD2.read(self.assets[entry['path']])
        matrix, offset, _ = builder.placement(role)
        # Pickup includes a 180-degree rotation; invert the complete placement.
        vertices = (model.positions[0] - offset) @ np.linalg.inv(matrix)
        return vertices, vertices[model.faces]

    def test_exact_shipped_assets_hashes_manifest_and_sight_header(self):
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
        for name, digest in self.manifest['dependencies_sha256'].items():
            self.assertEqual(builder.sha((ROOT / 'tools/assets' / name).read_bytes()), digest)

    def test_budget_static_cache_and_all_exported_pose_faces(self):
        self.assertEqual(builder.MODELS, {'models/weapons/g_rail/tris.md2': 'pickup',
                         'models/weapons/v_rail/tris.md2': 'view', 'players/soldier/w_railgun.md2': 'player'})
        frames = {'view': 1, 'pickup': 1, 'player': 198}
        baselines = {'view': 2000, 'pickup': 1200, 'player': 2664}
        for entry in self.manifest['models']:
            model = MD2.read(self.assets[entry['path']])
            with self.subTest(role=entry['role']):
                self.assertEqual(entry['baseline']['triangles'], baselines[entry['role']])
                self.assertLess(len(model.faces), 1000 if entry['role'] == 'view' else 550)
                self.assertEqual(len(model.faces), 996 if entry['role'] == 'view' else 520)
                self.assertEqual(model.header[10], frames[entry['role']])
                self.assertEqual(model.command_triangles, len(model.faces))
                self.assertEqual(model.header[4], 40 + 4 * model.header[6])
                for skin in model.skins:
                    self.assertIn(skin, self.assets)
                points = model.positions[:, model.faces]
                area = np.linalg.norm(np.cross(points[:, :, 1] - points[:, :, 0],
                                               points[:, :, 2] - points[:, :, 0]), axis=2)
                self.assertGreater(area.min(), 1e-9)

    def test_all_existing_mitten_hands_and_forearms_are_preserved_exactly(self):
        mesh, rifle = self.meshes['view'], build_m16('view')
        prefixes = ('hand_', 'arm_', 'cuff_')
        actual = {part['name'] for part in mesh['parts'] if part['name'].startswith(prefixes)}
        expected = {part['name'] for part in rifle['parts'] if part['name'].startswith(prefixes)}
        self.assertEqual(actual, expected)
        self.assertGreater(len(actual), 4)
        for name in actual:
            with self.subTest(part=name):
                np.testing.assert_array_equal(self.part_vertices(mesh, name), self.part_vertices(rifle, name))
        self.assertFalse(any(part['name'].startswith(prefixes) for part in self.meshes['world']['parts']))
        with Image.open(io.BytesIO(builder.texture_bytes())) as sniper, \
                Image.open(io.BytesIO(rifle_texture_bytes())) as rifle:
            self.assertEqual(sniper.crop((0, 128, 256, 192)).tobytes(),
                             rifle.crop((0, 128, 256, 192)).tobytes())

    def test_every_gun_scope_reticle_hand_and_arm_part_is_closed(self):
        for kind, mesh in self.meshes.items():
            vertices = np.round(np.asarray(mesh['vertices']), 7)
            for part in mesh['parts']:
                a = part['first_triangle']; b = a + part['triangle_count']
                edges = Counter()
                for face in mesh['faces'][a:b]:
                    points = [tuple(vertices[index]) for index in face]
                    for start, end in zip(points, points[1:] + points[:1]):
                        edges[tuple(sorted((start, end)))] += 1
                with self.subTest(kind=kind, part=part['name']):
                    self.assertTrue(edges)
                    self.assertTrue(all(count == 2 for count in edges.values()))

    def test_scope_anchors_and_decoded_end_lips_align_with_generated_ads(self):
        mesh = self.meshes['view']
        self.assertEqual(mesh['anchors']['rear_sight'], [28., 0., 12.])
        self.assertEqual(mesh['anchors']['front_sight'], [48., 0., 12.])
        model = MD2.read(self.assets['models/weapons/v_rail/tris.md2'])
        part = self.part(mesh, 'scope')
        a = part['first_triangle']; b = a + part['triangle_count']
        points = np.unique(model.positions[0, model.faces[a:b]].reshape(-1, 3), axis=0)
        rear = points[points[:, 0] < points[:, 0].min() + .05].mean(axis=0)
        front = points[points[:, 0] > points[:, 0].max() - .05].mean(axis=0)
        values = {name: float(value) for name, value in re.findall(
            r'#define PP_SNIPER_(\w+) \(([-\d.]+)f\)', self.header.decode())}
        for point, forward in ((rear, 9.5), (front, None)):
            self.assertAlmostEqual(-point[1] + values['ADS_RIGHT'], 0., delta=.1)
            self.assertAlmostEqual(point[2] + values['ADS_UP'], 0., delta=.1)
            if forward is not None:
                self.assertAlmostEqual(point[0] + values['ADS_FORWARD'], forward, delta=.1)
        self.assertGreater(front[0], rear[0] + 10.)

    def test_decoded_optic_center_and_off_axis_lower_channel_remain_open(self):
        for role, kind in (('view', 'view'), ('pickup', 'world')):
            vertices, triangles = self.decoded(role)
            mesh = self.meshes[kind]
            # Lower probes pass inside the tight octagonal bore, beside the
            # lower reticle post. They catch the formerly raised scope mounts
            # even though those mounts do not block the exact center ray.
            probes = ((0., 12.), (.2, 12.2), (-.2, 11.8), (.8, 8.35), (-.8, 8.35))
            for y, z in probes:
                with self.subTest(role=role, y=y, z=z):
                    hits, _ = ray_hits(triangles, (27., y, z), maximum=22.)
                    self.assertEqual(len(hits), 0, 'exported casing, mount or reticle blocks the optical channel')
            for name, ceiling in (('scope_mount_rear', 7.70), ('scope_mount_front', 7.38)):
                part = self.part(mesh, name)
                a = part['first_triangle']; b = a + part['triangle_count']
                self.assertLess(triangles[a:b, :, 2].max(), ceiling)
            turret = self.part(mesh, 'scope_turret')
            a = turret['first_triangle']; b = a + turret['triangle_count']
            self.assertGreater(triangles[a:b, :, 2].min(), 16.48)
            scope = self.part(mesh, 'scope')
            a = scope['first_triangle']; b = a + scope['triangle_count']
            for y, z in ((0., 12.), (.8, 8.35), (-.8, 8.35)):
                self.assertEqual(len(ray_hits(triangles[a:b], (27., y, z), maximum=22.)[0]), 0)

    def test_four_decoded_reticle_posts_are_visible_solids_with_a_clear_center_gap(self):
        probes = {'right': (-1.2, 12.), 'left': (1.2, 12.),
                  'lower': (0., 10.8), 'upper': (0., 13.2)}
        for role, kind in (('view', 'view'), ('pickup', 'world')):
            _, triangles = self.decoded(role)
            mesh = self.meshes[kind]
            names = {part['name'] for part in mesh['parts'] if part['name'].startswith('reticle_')}
            self.assertEqual(names, {'reticle_' + name for name in probes})
            for name, (y, z) in probes.items():
                part = self.part(mesh, 'reticle_' + name)
                a = part['first_triangle']; b = a + part['triangle_count']
                with self.subTest(role=role, post=name):
                    self.assertGreater(len(ray_hits(triangles[a:b], (27., y, z), maximum=22.)[0]), 0)
                    self.assertEqual(len(ray_hits(triangles[a:b], (27., 0., 12.), maximum=22.)[0]), 0)

    def test_decoded_muzzle_brake_has_a_recessed_back_wall(self):
        _, triangles = self.decoded('view')
        part = self.part(self.meshes['view'], 'muzzle_brake')
        a = part['first_triangle']; b = a + part['triangle_count']
        hits, distance = ray_hits(triangles[a:b], (114., 0., 1.8), (-1., 0., 0.))
        self.assertGreater(len(hits), 0)
        depth = distance.min() - 2.
        self.assertGreater(depth, 2.)
        self.assertLess(depth, 4.)

    def test_all_198_held_poses_follow_pinned_archived_motion(self):
        originals = json.loads((ROOT / 'tools/assets/platoon-originals.json').read_text())
        path = 'players/soldier/w_railgun.md2'
        original = MD2.read(source_bytes(originals, 'baseq2/' + path), source_compat=True)
        model = MD2.read(self.assets[path])
        self.assertEqual(model.names, original.names)
        rotations, translations, errors = rigid_transforms(original)
        self.assertLess(errors.max(), .15)
        matrix, offset, _ = builder.placement('player')
        reference = np.asarray(self.meshes['world']['vertices']) @ matrix + offset
        expected = np.asarray([reference @ rotation + translation
                               for rotation, translation in zip(rotations, translations)])
        error = np.linalg.norm(model.positions - expected, axis=2)
        limit = np.linalg.norm(model.scales, axis=1) / 2 + 1e-5
        self.assertTrue(np.all(error <= limit[:, None]))

    def test_exported_winding_normals_and_colorable_plastic_atlas(self):
        gun_materials = set(self.meshes['world']['materials'])
        for path in builder.TEXTURES:
            with Image.open(io.BytesIO(self.assets[path])) as image:
                self.assertEqual(image.size, (256, 256))
                self.assertEqual(image.mode, 'RGB')
                mask, _ = material_mask(image, path, 'player')
                for material in gun_materials:
                    index = MATERIALS.index(material)
                    x, y = (index % 4) * 64, (index // 4) * 64
                    with self.subTest(material=material):
                        self.assertEqual(mask.crop((x, y, x + 64, y + 64)).getextrema(), (255, 255))
        model = MD2.read(self.assets['models/weapons/g_rail/tris.md2'])
        points = model.positions[0, model.faces]
        normals = np.cross(points[:, 1] - points[:, 0], points[:, 2] - points[:, 0])
        normals /= np.linalg.norm(normals, axis=1)[:, None]
        stored = normal_table()[model.normals[0, model.faces]].mean(axis=1)
        self.assertLess(np.median(np.sum(normals * stored, axis=1)), -.65)
        self.assertTrue(np.all(model.uvs > 0))
        self.assertTrue(np.all(model.uvs < 1))

    def test_registered_ownership_excludes_legacy_overwrites(self):
        import build_platoon
        config = json.loads(build_platoon.CONFIG.read_text())
        registration = config['procedural_replacements']['sniper']
        self.assertEqual(set(registration['models']), set(builder.MODELS))
        self.assertEqual(set(registration['textures']), set(builder.TEXTURES))
        self.assertTrue(set(builder.MODELS) <= build_platoon.procedural_paths(config))
        legacy = json.loads(build_platoon.MANIFEST.read_text())
        self.assertFalse(set(builder.MODELS) & {entry['path'] for entry in legacy['models']})


if __name__ == '__main__':
    unittest.main(verbosity=2)
