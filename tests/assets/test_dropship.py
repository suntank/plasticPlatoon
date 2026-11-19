#!/usr/bin/env python3
"""Validate dedicated friendly helicopter art, attachment and mission clearance."""
from collections import Counter
import io
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import unittest

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/assets'))
import build_dropship as builder
from dropship_geometry import build_dropship, BODY_SOCKET, ROTOR_AXLE, REGIONS
from md2_assets import MD2, normal_table


def first_frame(raw):
    """Read positions without trusting the legacy enemy's stale face table."""
    h = struct.unpack_from('<17i', raw); offset = h[14]
    scale = np.asarray(struct.unpack_from('<3f', raw, offset))
    translation = np.asarray(struct.unpack_from('<3f', raw, offset + 12))
    packed = np.frombuffer(raw, dtype=np.uint8, count=h[6] * 4, offset=offset + 40).reshape(-1, 4)
    return packed[:, :3] * scale + translation


def mission_clearance():
    """Sample current BSP routes with rotating mesh envelopes, without edits.

    Sandstorm deliberately flies its final outro beyond the outer sky shell.
    Garden's departure also has existing terrain and world-boundary contacts.
    Those contacts must match the original craft. New contacts always fail.
    """
    sys.path.insert(0, str(ROOT / 'tools/maps'))
    from verify_sandkeep import BSP, SOLID, vec

    def cloud(body, rotor):
        points = [body]
        for phase in range(360):
            angle = math.radians(phase); c, s = math.cos(angle), math.sin(angle)
            rotation = np.array([[c, s, 0.], [-s, c, 0.], [0., 0., 1.]])
            points.append((rotor - ROTOR_AXLE) @ rotation + BODY_SOCKET)
        return np.concatenate(points)

    legacy = cloud(*(first_frame((ROOT / 'baseq2' / builder.BASELINES[kind]['path']).read_bytes())
                     for kind in ('body', 'main_rotor')))
    authored = cloud(*(MD2.read((ROOT / 'baseq2' / path).read_bytes()).positions[0] for path in builder.MODELS))
    records = []
    for mapname in ('pp_sandstorm', 'pp_endline', 'pp_garden_infiltration'):
        bsp_path = ROOT / 'baseq2/maps' / (mapname + '.bsp')
        bsp = BSP(bsp_path); keys = [entry['keys'] for entry in bsp.entities]
        names = {entry['targetname']: entry for entry in keys if entry.get('targetname')}
        for ship in [entry for entry in keys if entry.get('classname') == 'misc_platoon_dropship']:
            start = np.asarray(vec(ship['origin'])); yaw = float(ship.get('angle', 0))
            for key in ('target', 'deathtarget'):
                name = ship.get(key); route = [start]; seen = set()
                while name and name not in seen:
                    seen.add(name); corner = names[name]
                    if corner['classname'] != 'path_corner': raise ValueError('Invalid dropship route')
                    route.append(np.asarray(vec(corner['origin']))); name = corner.get('target')
                if len(route) == 1: continue
                record = dict(map=mapname, ship=ship.get('targetname'), route=key, samples=0,
                              bsp_sha256=builder.sha(bsp_path.read_bytes()), legacy_contacts=0,
                              authored_contacts=0, new_or_interior_blockers=[])
                beyond_outro_sky = False
                for first, last in zip(route, route[1:]):
                    direction = last - first; distance = float(np.linalg.norm(direction))
                    if not distance: continue
                    direction /= distance
                    if direction[0] or direction[1]: yaw = int(math.degrees(math.atan2(direction[1], direction[0])))
                    pitch = math.radians(-direction[2] * 12); angle = math.radians(yaw)
                    cp, sp, cy, sy = math.cos(pitch), math.sin(pitch), math.cos(angle), math.sin(angle)
                    rotation = np.array([[cp * cy, cp * sy, -sp], [-sy, cy, 0.], [sp * cy, sp * sy, cp]])
                    envelopes = []
                    for points in (legacy, authored):
                        posed = points @ rotation
                        low, high = posed.min(axis=0) - [0., 0., 2.], posed.max(axis=0) + [0., 0., 2.]
                        center = (low + high) / 2
                        envelopes.append((center, low - center, high - center))
                    for t in np.linspace(0., 1., max(1, math.ceil(distance / 16)) + 1):
                        origin = first + (last - first) * t
                        old_hit, new_hit = [bsp.collision(tuple(origin + center), tuple(low), tuple(high), SOLID)
                                            for center, low, high in envelopes]
                        record['samples'] += 1
                        record['legacy_contacts'] += bool(old_hit); record['authored_contacts'] += bool(new_hit)
                        if not new_hit: continue
                        sky = False
                        if new_hit.startswith('world brush '):
                            brush = int(new_hit.rsplit(' ', 1)[1]); a, count, _ = bsp.brushes[brush]
                            textures = [bsp.texinfo[texture][10].split(b'\0')[0].decode()
                                        for _, texture in bsp.sides[a:a + count] if texture >= 0]
                            sky = bool(textures) and all(texture.endswith('/sky') for texture in textures)
                        outside_sky = sky or new_hit == 'world solid/void at origin'
                        intentional_outro = mapname == 'pp_sandstorm' and key == 'deathtarget'
                        if old_hit and outside_sky and intentional_outro:
                            beyond_outro_sky = True
                        # BSP collision may report other world brushes after
                        # the craft has crossed the opaque outer sky shell.
                        # Accept only the exact legacy contact there.
                        retained_outside_contact = beyond_outro_sky and old_hit == new_hit
                        retained_garden_contact = (mapname == 'pp_garden_infiltration'
                                                   and ship.get('targetname') == 'garden_insertion_ship'
                                                   and key == 'target' and old_hit == new_hit)
                        if not (retained_garden_contact or
                                (old_hit and intentional_outro and (outside_sky or retained_outside_contact))):
                            record['new_or_interior_blockers'].append(dict(origin=origin.tolist(), old=old_hit, new=new_hit))
                records.append(record); start = route[-1]
    return records


class DropshipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets, cls.manifest = builder.build_assets()
        cls.meshes = {kind: build_dropship(kind) for kind in ('body', 'main_rotor')}
        cls.models = {kind: MD2.read(cls.assets[path]) for path, kind in builder.MODELS.items()}

    @staticmethod
    def part(mesh, name):
        return next(part for part in mesh['parts'] if part['name'] == name)

    def part_points(self, kind, name):
        model, mesh = self.models[kind], self.meshes[kind]
        part = self.part(mesh, name)
        a = part['first_triangle']; b = a + part['triangle_count']
        return model.positions[0, np.unique(model.faces[a:b])]

    def test_exact_three_assets_dependency_hashes_manifest_and_standard_library_gate(self):
        self.assertEqual(len(self.assets), 3)
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
        subprocess.run([sys.executable, '-S', str(ROOT / 'tools/assets/verify_dropship_runtime.py')],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def test_compact_static_body_and_rotor_preserve_original_frame_identity(self):
        self.assertEqual(builder.MODELS, {'models/vehicles/platoon_dropship/body.md2': 'body',
                         'models/vehicles/platoon_dropship/main_rotor.md2': 'main_rotor'})
        for kind, model in self.models.items():
            with self.subTest(kind=kind):
                self.assertLess(len(model.faces), 700 if kind == 'body' else 100)
                self.assertLess(len(model.faces), builder.BASELINES[kind]['triangles'])
                self.assertLess(len(model.data), builder.BASELINES[kind]['file_bytes'])
                self.assertEqual(model.names, [b'stand02'.ljust(16, b'\0')])
                self.assertEqual(model.header[10], 1)
                self.assertEqual(model.header[4], 40 + 4 * model.header[6])
                self.assertEqual(model.command_triangles, len(model.faces))
                self.assertEqual(model.skins, [builder.SKIN])
                self.assertTrue(np.all(model.uvs > 0) and np.all(model.uvs < 1))

    def test_every_exported_hull_blade_skid_and_fitting_is_closed_and_nondegenerate(self):
        for kind, model in self.models.items():
            mesh = self.meshes[kind]
            actual, ideal = model.positions[0], np.asarray(mesh['vertices'])
            self.assertLessEqual(np.linalg.norm(actual - ideal, axis=1).max(), np.linalg.norm(model.scales[0]) / 2 + 1e-5)
            triangles, targets = actual[model.faces], ideal[model.faces]
            crossed = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
            expected = np.cross(targets[:, 1] - targets[:, 0], targets[:, 2] - targets[:, 0])
            self.assertGreater(np.linalg.norm(crossed, axis=1).min(), 1e-8)
            self.assertTrue(np.all(np.sum(crossed * expected, axis=1) > 0))
            stored = normal_table()[model.normals[0, model.faces]].mean(axis=1)
            crossed /= np.linalg.norm(crossed, axis=1)[:, None]
            self.assertLess(np.median(np.sum(crossed * stored, axis=1)), -.65)
            for part in mesh['parts']:
                a = part['first_triangle']; b = a + part['triangle_count']; edges = Counter()
                for face in model.faces[a:b]:
                    corners = [tuple(actual[index]) for index in face]
                    for start, end in zip(corners, corners[1:] + corners[:1]):
                        edges[tuple(sorted((start, end)))] += 1
                with self.subTest(kind=kind, part=part['name']):
                    self.assertTrue(edges)
                    self.assertTrue(all(count == 2 for count in edges.values()))

    def test_decoded_mast_and_hub_share_the_unchanged_client_socket(self):
        self.assertEqual(BODY_SOCKET, (-3.9, .5, 81.3))
        self.assertEqual(ROTOR_AXLE, (0., .25, 81.3))
        self.assertEqual(self.meshes['body']['anchors']['socket'], list(BODY_SOCKET))
        self.assertEqual(self.meshes['main_rotor']['anchors']['axle'], list(ROTOR_AXLE))
        mast = self.part_points('body', 'mast_socket')
        mast_top = mast[mast[:, 2] > 81.15].mean(axis=0)
        np.testing.assert_allclose(mast_top, BODY_SOCKET, atol=.16)
        hub = self.part_points('main_rotor', 'rotor_hub')
        hub_bottom = hub[hub[:, 2] < 81.4].mean(axis=0)
        np.testing.assert_allclose(hub_bottom, ROTOR_AXLE, atol=.3)
        source = (ROOT / 'src/client/header/helicopter_rotor.h').read_text()
        self.assertIn('VectorMA(origin, -3.9f, forward, origin);', source)
        self.assertIn('VectorMA(origin, -0.5f, right, origin);', source)
        self.assertIn('VectorMA(origin, 0.25f, rotor_right, origin);', source)

    def test_all_rotor_phases_stay_in_existing_visible_mission_bounds(self):
        body, rotor = self.models['body'].positions[0], self.models['main_rotor'].positions[0]
        low, high = np.asarray([-114., -68., 36.]), np.asarray([68., 68., 96.])
        self.assertTrue(np.all(body.min(axis=0) >= low))
        self.assertTrue(np.all(body.max(axis=0) <= high))
        for phase in range(360):
            angle = np.radians(phase); c, s = np.cos(angle), np.sin(angle)
            rotation = np.array([[c, s, 0.], [-s, c, 0.], [0., 0., 1.]])
            joined = (rotor - ROTOR_AXLE) @ rotation + BODY_SOCKET
            self.assertTrue(np.all(joined.min(axis=0) >= low))
            self.assertTrue(np.all(joined.max(axis=0) <= high))

    def test_transport_cabin_engines_wings_skids_and_four_solid_blades_have_correct_placement(self):
        names = {part['name'] for part in self.meshes['body']['parts']}
        self.assertTrue({'transport_fuselage', 'rising_tail_boom', 'vertical_tail_fin',
                         'horizontal_tailplane', 'tail_fan', 'nose_searchlight'} <= names)
        tail = self.part_points('body', 'vertical_tail_fin')
        fan = self.part_points('body', 'tail_fan')
        self.assertTrue(np.all(fan.min(axis=0) > tail.min(axis=0)))
        self.assertTrue(np.all(fan.max(axis=0) < tail.max(axis=0)))
        cabin = self.part_points('body', 'transport_fuselage')
        self.assertGreater(np.ptp(cabin[:, 1]), 55.)
        self.assertGreater(cabin[:, 0].max(), 63.)
        for side, sign in (('port', -1), ('starboard', 1)):
            self.assertGreater(self.part_points('body', 'engine_' + side)[:, 1].mean() * sign, 12.)
            self.assertGreater(self.part_points('body', 'stub_wing_' + side)[:, 1].mean() * sign, 30.)
            skid = self.part_points('body', 'skid_rail_' + side)
            self.assertGreater(np.ptp(skid[:, 0]), 79.)
            self.assertGreater(skid[:, 1].mean() * sign, 29.)
            self.assertLess(skid[(skid[:, 0] > -35) & (skid[:, 0] < 45), 2].max(), 40.)
            self.assertGreater(skid[skid[:, 0] > 50, 2].min(), 42.)
        rotor = self.meshes['main_rotor']
        self.assertEqual({part['name'] for part in rotor['parts']}, {'rotor_hub'} | {'rotor_blade_' + str(i) for i in range(4)})
        for i in range(4):
            blade = self.part_points('main_rotor', 'rotor_blade_' + str(i))
            self.assertEqual(self.part(rotor, 'rotor_blade_' + str(i))['triangle_count'], 12)
            self.assertGreater(np.linalg.norm(blade[:, :2] - [0., .25], axis=1).max(), 65.)
            self.assertGreater(np.ptp(blade[:, 2]), 1.)

    def test_glass_cargo_and_green_plastic_use_real_exterior_faces_and_one_dedicated_atlas(self):
        image = np.asarray(Image.open(io.BytesIO(self.assets[builder.SKIN])))
        self.assertEqual(image.shape, (256, 256, 3))
        x, y, X, Y = REGIONS['plastic']
        plastic = image[y:Y, x:X]
        self.assertTrue(np.all(plastic[:, :, 1] > plastic[:, :, 0]))
        body = self.meshes['body']; model = self.models['body']
        materials = np.asarray(body['materials'])
        self.assertEqual((materials == 'cargo').sum(), 4)
        self.assertGreaterEqual((materials == 'glass').sum(), 16)
        self.assertEqual((materials == 'windshield').sum(), 2)
        for material in set(materials):
            x, y, X, Y = REGIONS[material]
            uv = model.uvs[materials == material] * 256
            self.assertGreaterEqual(uv[:, :, 0].min(), x)
            self.assertLessEqual(uv[:, :, 0].max(), X)
            self.assertGreaterEqual(uv[:, :, 1].min(), y)
            self.assertLessEqual(uv[:, :, 1].max(), Y)
        cargo = model.positions[0, model.faces[materials == 'cargo']]
        self.assertGreater(cargo[:, :, 1].max(), 27.)
        self.assertLess(cargo[:, :, 1].min(), -27.)
        x, y, X, Y = REGIONS['cargo']
        self.assertGreater(np.all(image[y:Y, x:X] == builder.INK, axis=2).sum(), 100)

    def test_dedicated_owner_leaves_legacy_enemy_models_and_existing_assets_untouched(self):
        import build_platoon
        config = json.loads(build_platoon.CONFIG.read_text())
        owner = config['procedural_replacements']['dropship']
        self.assertEqual(set(owner['models'] + owner['textures']), set(self.assets))
        self.assertTrue(set(builder.MODELS) <= build_platoon.procedural_paths(config))
        for previous in builder.BASELINES.values():
            self.assertNotIn(previous['path'], self.assets)
            self.assertEqual(builder.sha((ROOT / 'baseq2' / previous['path']).read_bytes()), previous['sha256'])
        enemy = (ROOT / 'src/game/monster/boss2/boss2.c').read_text()
        self.assertIn('gi.modelindex("models/monsters/plastic_boss/body.md2")', enemy)
        self.assertIn('gi.modelindex("models/monsters/plastic_boss/main_rotor.md2")', enemy)
        friendly = (ROOT / 'src/game/g_misc.c').read_text()
        self.assertIn('gi.modelindex("models/vehicles/platoon_dropship/body.md2")', friendly)
        self.assertIn('gi.modelindex("models/vehicles/platoon_dropship/main_rotor.md2")', friendly)
        for manifest in ('ammo-manifest.json', 'projectiles-manifest.json', 'health-manifest.json', 'armor-manifest.json'):
            for entry in json.loads((ROOT / 'tools/assets' / manifest).read_text())['files']:
                self.assertNotIn(entry['path'], self.assets)
                self.assertEqual(builder.sha((ROOT / 'baseq2' / entry['path']).read_bytes()), entry['sha256'])

    def test_current_compiled_insertion_extraction_routes_have_no_new_blockers(self):
        records = mission_clearance()
        self.assertEqual(len(records), 5)
        self.assertEqual({entry['map'] for entry in records},
                         {'pp_sandstorm', 'pp_endline', 'pp_garden_infiltration'})
        self.assertGreaterEqual(sum(entry['samples'] for entry in records), 400)
        for entry in records:
            with self.subTest(map=entry['map'], ship=entry['ship'], route=entry['route']):
                self.assertEqual(entry['new_or_interior_blockers'], [])


if __name__ == '__main__':
    unittest.main()
