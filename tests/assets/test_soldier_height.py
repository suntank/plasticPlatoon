#!/usr/bin/env python3
"""Check taller enemy meshes preserve authored animation and attachment data."""
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('soldier_height_builder', ROOT/'tools/assets/build_soldier_height.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
sys.path.insert(0, str(ROOT/'tools/maps'))
from verify_sandkeep import BSP, MONSTER_MASK


def vertices(data, frame):
    h = struct.unpack_from('<17i', data)
    offset = h[14] + frame*h[4]
    values = struct.unpack_from('<6f', data, offset)
    return [tuple(data[offset+40+4*i+a]*values[a]+values[a+3] for a in range(3)) for i in range(h[6])]


class SoldierHeightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(builder.CONFIG.read_text())
        cls.models = {}
        for name in builder.MODELS:
            cls.models[name] = ((ROOT/'baseq2'/builder.MODEL_DIR/name).read_bytes(),
                                (ROOT/'baseq2'/builder.MODEL_DIR/'tall'/name).read_bytes())

    def test_generated_outputs_are_current(self):
        subprocess.run([sys.executable, str(ROOT/'tools/assets/build_soldier_height.py'), '--verify'], check=True)

    def test_only_frame_transform_bytes_change(self):
        for name, (source, taller) in self.models.items():
            with self.subTest(model=name):
                h = struct.unpack_from('<17i', source)
                self.assertEqual(source[:h[14]], taller[:h[14]], 'Header/skin references/UV/triangles changed')
                self.assertEqual(source[h[15]:], taller[h[15]:], 'Draw commands changed')
                self.assertEqual(len(source), len(taller))
                self.assertEqual(h[10], 475)
                for frame in range(h[10]):
                    offset = h[14]+frame*h[4]
                    self.assertEqual(source[offset+24:offset+h[4]], taller[offset+24:offset+h[4]],
                                     'Frame names, packed vertices or lighting normals changed')

    def test_every_action_uses_same_uniform_foot_anchor_transform(self):
        for name, (source, taller) in self.models.items():
            for frame in (0, 32, 45, 146, 270, 474):
                with self.subTest(model=name, frame=frame):
                    for old, new in zip(vertices(source, frame), vertices(taller, frame)):
                        scale, foot = self.config['scale'], self.config['foot_z']
                        expected = (old[0]*scale, old[1]*scale, foot+(old[2]-foot)*scale)
                        for a in range(3):
                            self.assertAlmostEqual(new[a], expected[a], delta=0.00003)

    def test_standing_eye_intersects_chest_and_feet_stay_grounded(self):
        source, taller = self.models['tris.md2']
        old = vertices(source, 146)
        new = vertices(taller, 146)
        low, high = min(v[2] for v in new), max(v[2] for v in new)
        original_low, original_high = min(v[2] for v in old), max(v[2] for v in old)
        old_fraction = (22-original_low)/(original_high-original_low)
        new_fraction = (22-low)/(high-low)
        self.assertGreater(old_fraction, .85)
        self.assertGreater(new_fraction, .6)
        self.assertLess(new_fraction, .76)
        self.assertLess(abs(low+24), .5)
        manifest = json.loads(builder.MANIFEST.read_text())
        self.assertLess(high, manifest['standing_hull_max_z'], 'Standing hull no longer encloses the visible head')
        self.assertLessEqual(manifest['standing_hull_max_z']+24, 64,
                             'Taller soldier no longer fits existing 64-unit passages')

    def test_heavy_and_rocket_muzzles_match_scaled_barrel_centres(self):
        # These are the reviewed barrel-rim markers used by both game and client.
        for name, old_marker in (('weapon_heavy.md2', (25.37,-4.46,4.50)),
                                  ('weapon_rocket.md2', (22.19,-4.72,4.19))):
            _, taller = self.models[name]
            points = vertices(taller, 32)  # FRAME_attak303, planted fire pose.
            front = max(p[0] for p in points)
            rim = [p for p in points if front-p[0] < .26]
            centre = tuple(sum(p[a] for p in rim)/len(rim) for a in range(3))
            scale, foot = self.config['scale'], self.config['foot_z']
            marker = (old_marker[0]*scale, old_marker[1]*scale, foot+(old_marker[2]-foot)*scale)
            for a in range(3):
                self.assertAlmostEqual(centre[a], marker[a], delta=.025)

    def test_taller_hull_does_not_block_authored_soldier_spawns(self):
        manifest = json.loads(builder.MANIFEST.read_text())
        rows = []
        for path in sorted((ROOT/'baseq2/maps').glob('*.bsp')):
            bsp = BSP(path)
            row = dict(map=path.stem, soldiers=0, existing_blocked=0, newly_blocked=[])
            for entity in bsp.entities:
                keys = entity['keys']
                if not keys.get('classname', '').startswith('monster_soldier'):
                    continue
                row['soldiers'] += 1
                origin = tuple(map(float, keys.get('origin', '0 0 0').split()))
                old = bsp.collision(origin, (-16,-16,-24), (16,16,32), MONSTER_MASK)
                new = bsp.collision(origin, (-16,-16,-24),
                                    (16,16,manifest['standing_hull_max_z']), MONSTER_MASK)
                if old:
                    row['existing_blocked'] += 1
                elif new:
                    row['newly_blocked'].append(dict(classname=keys['classname'], origin=origin, collision=new))
            if row['soldiers']:
                rows.append(row)
        report = ROOT/'build/soldier-height/spawn-clearance.json'
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(rows, indent=2)+'\n')
        self.assertGreater(sum(row['soldiers'] for row in rows), 0, 'No compiled soldier maps checked')
        for row in rows:
            self.assertEqual(row['newly_blocked'], [], f"Taller hull blocks spawns in {row['map']}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
