#!/usr/bin/env python3
"""Audit generated muzzle attachments against shipped animated held meshes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('player_muzzle_builder', ROOT/'tools/assets/build_player_muzzle_points.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class PlayerMuzzlePointsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(builder.REPORT.read_text())
        cls.header = builder.HEADER.read_text()

    def test_generation_is_current(self):
        subprocess.run([sys.executable, str(ROOT/'tools/assets/build_player_muzzle_points.py'), '--check'], check=True)

    def test_complete_inventory_and_package_provenance(self):
        expected = {p.name for p in (ROOT/'baseq2/players/soldier').glob('w_*.md2')} | {'weapon.md2'}
        self.assertEqual(expected, {m['filename'] for m in self.report['models']})
        self.assertEqual(len(expected), 11)
        with zipfile.ZipFile(ROOT/'baseq2/plastic-platoon.pk3') as package:
            for entry in self.report['models']:
                with self.subTest(model=entry['filename']):
                    data = package.read('players/soldier/'+entry['filename'])
                    self.assertEqual(hashlib.sha256(data).hexdigest(),entry['source_sha256'])

    def test_every_frame_tracks_reviewed_barrel_vertices(self):
        for entry in self.report['models']:
            name = entry['filename']
            symbol = 'pp_muzzle_' + ('w_machinegun' if name == 'weapon.md2' else name.removesuffix('.md2'))
            table = re.search(r'static const float '+symbol+r'\[198\]\[3\] = \{(.*?)\n\};', self.header, re.S)
            self.assertIsNotNone(table, name)
            generated = [tuple(map(float, point)) for point in re.findall(r'\{(-?[\d.]+)f, (-?[\d.]+)f, (-?[\d.]+)f\}', table.group(1))]
            self.assertEqual(len(generated),198,name)
            data = (ROOT/'baseq2/players/soldier'/name).read_bytes()
            h = struct.unpack_from('<17i',data)
            self.assertEqual(h[10],198)
            selected=entry['vertices']
            for frame,actual in enumerate(generated):
                offset = h[14] + h[4]*frame
                st = struct.unpack_from('<6f',data,offset)
                vertices = [tuple(data[offset+40+4*i+a]*st[a]+st[a+3] for a in range(3)) for i in selected]
                expected = tuple(sum(v[a] for v in vertices)/len(vertices) for a in range(3))
                for a in range(3):self.assertAlmostEqual(actual[a],expected[a],delta=.000001,msg=f'{name} frame {frame} axis {a}')
            # Current source anatomy: rifles' tips are ~16 units above model
            # origin standing and ~1 unit below crouching. Never add eye height.
            self.assertTrue(14.0 < generated[0][2] < 18.0,name)
            self.assertTrue(-2.0 < generated[160][2] < 0.0,name)
            self.assertGreater(generated[46][0]-generated[47][0],2.0,name)

    def test_changed_source_requires_visual_review(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'changed.md2';p.write_bytes(b'not the reviewed mesh')
            with self.assertRaisesRegex(ValueError,'source changed'):
                builder.load_model(p,'0'*64)


if __name__=='__main__':unittest.main()
