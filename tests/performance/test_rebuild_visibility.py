#!/usr/bin/env python3
"""VIS-only updates must preserve rendered/collision geometry and lighting."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_map_tools import fixture_bsp, lump_range
from rebuild_visibility import LUMPS, lump_bytes, replace_visibility


class RebuildVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.original = self.root / 'original.bsp'
        self.compiled = self.root / 'compiled.bsp'
        self.output = self.root / 'candidate.bsp'
        self.original.write_bytes(fixture_bsp())
        self.compiled.write_bytes(fixture_bsp(light=False))

    def test_replace_only_visibility_and_keep_baked_face_metadata(self):
        data = bytearray(self.compiled.read_bytes())
        offset, _ = lump_range(data, 'visibility')
        data[offset + 22] = 2  # narrow second cluster PVS; PHS remains valid
        self.compiled.write_bytes(data)
        before = self.original.read_bytes()
        report = replace_visibility(self.original, self.compiled, self.output)
        after = self.output.read_bytes()
        self.assertLess(report['pvs_visible_clusters_mean_after'], report['pvs_visible_clusters_mean_before'])
        self.assertEqual(before, self.original.read_bytes())
        self.assertEqual(data, self.compiled.read_bytes())
        for name in LUMPS:
            self.assertEqual(lump_bytes(after, name), lump_bytes(data if name == 'visibility' else before, name), name)

    def test_reject_changed_geometry_or_entities_and_keep_existing_output(self):
        valid = fixture_bsp(light=False)
        for name in ('entities', 'planes', 'vertexes', 'nodes', 'texinfo', 'faces',
                     'leafs', 'leaffaces', 'edges', 'surfedges', 'models', 'areas'):
            with self.subTest(name=name):
                bad = bytearray(valid)
                offset, _ = lump_range(bad, name)
                bad[offset] ^= 1
                self.compiled.write_bytes(bad)
                self.output.write_bytes(b'existing candidate')
                with self.assertRaises(ValueError):
                    replace_visibility(self.original, self.compiled, self.output)
                self.assertEqual(self.output.read_bytes(), b'existing candidate')

    def test_reject_missing_or_invalid_visibility_rows(self):
        for fixture in (fixture_bsp(vis=False, light=False),
                        fixture_bsp(absent_rows=True, light=False),
                        fixture_bsp(bad_row=True, light=False)):
            self.compiled.write_bytes(fixture)
            with self.assertRaises(ValueError):
                replace_visibility(self.original, self.compiled, self.output)
            self.assertFalse(self.output.exists())

    def test_build_directory_cannot_overwrite_original(self):
        tool = Path(__file__).resolve().parents[2] / 'tools/performance/rebuild_visibility.py'
        source = self.root / 'map.map'
        source.write_text('not needed: collision must be caught before compilation')
        for original in (self.root / 'compiled/map.bsp', self.root / 'compile/map/map.bsp'):
            original.parent.mkdir(parents=True, exist_ok=True)
            original.write_bytes(fixture_bsp())
            result = subprocess.run([sys.executable, str(tool), '--source', str(source),
                                     '--bsp', str(original), '--output', str(self.output),
                                     '--build-dir', str(self.root), '--tool', '/missing/compiler'],
                                    text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('would overwrite the original BSP', result.stderr)
            self.assertEqual(original.read_bytes(), fixture_bsp())

    def test_reject_overwriting_input(self):
        for destination in (self.original, self.compiled):
            with self.assertRaises(ValueError):
                replace_visibility(self.original, self.compiled, destination)


if __name__ == '__main__':
    unittest.main()
