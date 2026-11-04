#!/usr/bin/env python3
"""Executable MD2 conversion regressions, using the pinned real pickup sources."""
import copy
import importlib.util
import json
from pathlib import Path
import struct
import sys
import unittest
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/assets"))
import md2_assets as md2
import build_platoon

CONFIG = json.loads((ROOT / "tools/assets/pickups.json").read_text())
ORIGINALS = json.loads((ROOT / "tools/assets/platoon-originals.json").read_text())


class AssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = md2.MD2.read(md2.source_bytes(ORIGINALS, "baseq2/models/items/armor/shard/tris.md2"), source_compat=True)

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

    def test_duplicate_exporter_primitive_repairs_without_extra_geometry(self):
        data = md2.source_bytes(ORIGINALS, "baseq2/models/weapons/g_rocket/tris.md2")
        header = list(md2.HEADER.unpack_from(data))
        count = struct.unpack_from('<i', data, header[15])[0]
        primitive_bytes = 4 + abs(count) * 12
        first = data[header[15]:header[15] + primitive_bytes]
        broken = bytearray(data[:header[16] - 4] + first + data[header[16] - 4:])
        header[9] += primitive_bytes // 4
        header[16] += primitive_bytes
        md2.HEADER.pack_into(broken, 0, *header)
        with self.assertRaises(ValueError):
            md2.MD2.read(bytes(broken))
        src = md2.MD2.read(bytes(broken), source_compat=True)
        self.assertEqual(src.command_triangles - len(src.faces), abs(count) - 2)
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

    def test_manifest_outputs_and_original_sources_recoverable(self):
        manifest_path = ROOT / "tools/assets/pickup-manifest.json"
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
        # The expanded Platoon pipeline now reduces animated actors with one
        # shared topology. Their original sources remain pinned and recoverable;
        # test_md2_animation.py checks every shipped pose and surviving vertex.
        for path in ["baseq2/players/soldier/tris.md2", "baseq2/players/soldier/weapon.md2"]:
            original = md2.MD2.read(md2.source_bytes(ORIGINALS, path), source_compat=True)
            self.assertEqual(original.header[10], 198)
        for path in ["baseq2/players/soldier/skin.png", "baseq2/models/weapons/g_machn/skin.png"]:
            self.assertEqual(md2.texture_stats(md2.source_bytes(ORIGINALS, path))["dimensions"], [2048, 2048])

    def test_pickups_use_audited_local_sources_and_exact_resized_textures(self):
        manifest = json.loads((ROOT / "tools/assets/pickup-manifest.json").read_text())
        sources = json.loads((ROOT / "tools/assets/platoon-sources.json").read_text())
        hashes = {entry["path"]: entry["source_sha256"] for entry in sources["files"]}
        self.assertIn("source_archive", manifest)
        for entry in manifest["assets"]:
            with self.subTest(model=entry["model"]):
                for path in (entry["model"], entry["texture_before"]["path"]):
                    raw = md2.pickup_source_bytes(manifest, "baseq2/" + path)
                    self.assertEqual(md2.sha(raw), hashes[path])
                expected = md2.resize_texture(raw, 256)
                self.assertEqual((ROOT / "baseq2" / entry["texture_after"]["path"]).read_bytes(), expected)
                for path in (ROOT / "baseq2").glob("operation-*.pk3"):
                    with zipfile.ZipFile(path) as archive:
                        name = entry["texture_after"]["path"]
                        if name in archive.namelist():
                            self.assertEqual(archive.read(name), expected, str(path))

    def test_snapshot_hash_and_full_release_overrides_prevent_old_pickup_restore(self):
        manifest = json.loads((ROOT / "tools/assets/pickup-manifest.json").read_text())
        bad = copy.deepcopy(manifest)
        bad["source_archive"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "archive hash changed"):
            md2.pickup_source_bytes(bad, "baseq2/" + manifest["assets"][0]["model"])
        originals, outputs = build_platoon.pickup_overrides(manifest)
        self.assertEqual(len(outputs), 16)
        for entry in manifest["assets"]:
            self.assertEqual(md2.sha(outputs[entry["model"]]), entry["after"]["sha256"])
            self.assertEqual(md2.sha(originals[entry["model"]]), entry["before"]["sha256"])
        self.assertEqual(originals["models/weapons/g_machn/skin_pickup.png"],
                         originals["models/weapons/g_machn/skin.png"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
