#!/usr/bin/env python3
"""Executable MD2 conversion regressions, using the pinned real pickup sources."""
import copy
import importlib.util
import json
from pathlib import Path
import struct
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/assets"))
import md2_assets as md2

CONFIG = json.loads((ROOT / "tools/assets/pickups.json").read_text())
REF = CONFIG["source_commit"]


class AssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = md2.MD2.read(md2.source_bytes(REF, "baseq2/models/items/armor/shard/tris.md2"), source_compat=True)

    def test_roundtrip_exact_coordinate_system_frame_and_uvs(self):
        src = self.original
        data = md2.encode_static(src, src.positions[0], src.faces, src.uvs, src.skins)
        out = md2.MD2.read(data)
        self.assertEqual(src.names, out.names)
        np.testing.assert_array_equal(src.positions, out.positions)
        np.testing.assert_array_equal(src.scales, out.scales)
        np.testing.assert_array_equal(src.translations, out.translations)
        self.assertEqual(out.header[4], 40 + out.header[6] * 4)
        # Canonical corner tuples preserve winding and seam-specific float UVs.
        def triangles(m):
            result = set()
            for face, coords in zip(m.faces, m.uvs):
                t = tuple((int(v), struct.pack("<2f", *uv)) for v, uv in zip(face, coords))
                result.add(min(t, t[1:] + t[:1], t[2:] + t[:2]))
            return result
        self.assertEqual(triangles(src), triangles(out))

    def test_source_normal_direction_is_preserved(self):
        src = self.original
        out = md2.MD2.read(md2.encode_static(src, src.positions[0], src.faces, src.uvs, src.skins))
        dots = np.sum(md2.normal_table()[src.normals[0]] * md2.normal_table()[out.normals[0]], axis=1)
        self.assertGreater(np.median(dots), .99)
        self.assertGreater(np.percentile(dots, 5), .90)

    def test_animation_cannot_be_simplified(self):
        src = copy.copy(self.original)
        src.positions = np.concatenate([src.positions, src.positions])
        with self.assertRaisesRegex(ValueError, "animated"):
            md2.encode_static(src, src.positions[0], src.faces, src.uvs, src.skins)
        with self.assertRaisesRegex(ValueError, "single-frame"):
            md2.simplify(src, 300, CONFIG["parameters"])

    def test_reject_truncation_invalid_offsets_and_normal_indices(self):
        src = self.original
        with self.assertRaises(ValueError):
            md2.MD2.read(src.data[:-1])
        bad = bytearray(src.data)
        struct.pack_into("<i", bad, 14 * 4, 4)  # frame section overlaps header
        with self.assertRaises(ValueError):
            md2.MD2.read(bytes(bad))
        bad = bytearray(src.data)
        bad[src.header[14] + 43] = 162
        with self.assertRaisesRegex(ValueError, "normal"):
            md2.MD2.read(bytes(bad))

    def test_reject_invalid_commands_and_winding(self):
        src = self.original
        bad = bytearray(src.data)
        struct.pack_into("<i", bad, src.header[15] + 12, src.header[6])
        with self.assertRaises(ValueError):
            md2.MD2.read(bytes(bad))
        bad = bytearray(src.data)
        a, b = struct.unpack_from("<2H", bad, src.header[13])
        struct.pack_into("<2H", bad, src.header[13], b, a)
        with self.assertRaisesRegex(ValueError, "winding"):
            md2.MD2.read(bytes(bad))
        bad = bytearray(src.data)
        struct.pack_into("<i", bad, src.header[15] + (src.header[9] - 1) * 4, 3)
        with self.assertRaises(ValueError):
            md2.MD2.read(bytes(bad))

    def test_known_source_exporter_duplicates_repair_exactly(self):
        data = md2.source_bytes(REF, "baseq2/models/weapons/g_rocket/tris.md2")
        with self.assertRaises(ValueError):
            md2.MD2.read(data)
        src = md2.MD2.read(data, source_compat=True)
        self.assertEqual(src.command_triangles - len(src.faces), 2)
        out = md2.MD2.read(md2.encode_static(src, src.positions[0], src.faces, src.uvs, src.skins))
        self.assertEqual(out.command_triangles, out.header[8])

    @unittest.skipUnless(importlib.util.find_spec("pymeshlab"), "conversion dependency not installed")
    def test_conversion_is_deterministic(self):
        src = self.original
        outputs = []
        for _ in range(2):
            p, f, uv = md2.simplify(src, 800, CONFIG["parameters"])
            outputs.append(md2.encode_static(src, p, f, uv, src.skins))
        self.assertEqual(outputs[0], outputs[1])
        self.assertLessEqual(len(md2.MD2.read(outputs[0]).faces), 800)

    def test_manifest_outputs_and_animated_sources_unchanged(self):
        manifest_path = ROOT / "doc/performance/assets-manifest.json"
        if not manifest_path.exists():
            self.skipTest("production outputs not installed yet")
        manifest = json.loads(manifest_path.read_text())
        for asset in manifest["assets"]:
            with self.subTest(model=asset["model"]):
                out = md2.MD2.read((ROOT / "baseq2" / asset["model"]).read_bytes())
                self.assertEqual(out.stats(), asset["after"])
                self.assertEqual(out.command_triangles, out.header[8])
                self.assertLess(out.header[6], 2048)
                self.assertEqual(out.header[10], 1)
                for skin in out.skins:
                    self.assertTrue((ROOT / "baseq2" / skin).is_file())
        for path in ["baseq2/players/soldier/tris.md2", "baseq2/players/soldier/weapon.md2",
                     "baseq2/players/soldier/skin.png", "baseq2/models/weapons/g_machn/skin.png"]:
            self.assertEqual((ROOT / path).read_bytes(), md2.source_bytes(REF, path))


if __name__ == "__main__":
    unittest.main(verbosity=2)
