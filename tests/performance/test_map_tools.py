#!/usr/bin/env python3
"""Black-box release-map publication regressions and independent IBSP fixtures.

The fake compiler is a real child process. It records argument boundaries, emits
valid or malformed BSP files and simulates the failure modes which must never
replace an existing published map. No map compiler or extra packages are needed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/performance"))
from map_inventory import bsp_inventory, decompress_vis, map_inventory

LUMP_NAMES = ("entities planes vertexes visibility nodes texinfo faces lighting "
              "leafs leaffaces leafbrushes edges surfedges models brushes "
              "brushsides pop areas areaportals").split()
MAP_TEXT = '''{
"classname" "worldspawn"
{
( 0 0 0 ) ( 0 64 0 ) ( 64 64 0 ) sandbox/sand1 0 0 0 1 1 134217728 0 0
( 0 0 64 ) ( 64 0 64 ) ( 64 64 64 ) sandbox/sand1 0 0 0 1 1 0 0 0
( 0 0 0 ) ( 64 0 0 ) ( 64 0 64 ) sandbox/sand1 0 0 0 1 1 0 0 0
( 0 64 0 ) ( 0 64 64 ) ( 64 64 64 ) sandbox/sand1 0 0 0 1 1 0 0 0
( 0 0 0 ) ( 0 0 64 ) ( 0 64 64 ) sandbox/sand1 0 0 0 1 1 0 0 0
( 64 0 0 ) ( 64 64 0 ) ( 64 64 64 ) sandbox/sand1 0 0 0 1 1 0 0 0
}
}
{
"classname" "info_player_start"
"origin" "32 32 32"
}
'''


def fixture_bsp(*, vis=True, light=True, absent_rows=False, bad_row=False):
    """IBSP38 fixture with one face, two PVS clusters and three valid leaves."""
    lumps = dict.fromkeys(LUMP_NAMES, b"")
    lumps["entities"] = b'{\n"classname" "worldspawn"\n}\n\0'
    lumps["planes"] = struct.pack("<4fi", 0, 0, 1, 0, 2)
    lumps["vertexes"] = struct.pack("<9f", 0, 0, 0, 64, 0, 0, 0, 64, 0)
    if vis:
        offsets = (-1,) * 4 if absent_rows else (20, 21, 22, 23)
        lumps["visibility"] = struct.pack("<5i", 2, *offsets) + (b"\0\0\3\3" if bad_row else b"\1\3\3\3")
    lumps["nodes"] = struct.pack("<iii6hHH", 0, -2, -3, 0, 0, 0, 64, 64, 64, 0, 1)
    lumps["texinfo"] = struct.pack("<8fii32si", 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, b"sandbox/sand1", -1)
    lumps["faces"] = struct.pack("<Hhihh4Bi", 0, 0, 0, 3, 0, 0, 255, 255, 255, 0 if light else -1)
    lumps["lighting"] = b"\x80\x90\xa0" if light else b""
    leaves = []
    for cluster in (-1, 0, 1):
        leaves.append(struct.pack("<ihh6h4H", 1 if cluster == -1 else 0, cluster, 0,
                                  0, 0, 0, 64, 64, 64, 0, 0 if cluster == -1 else 1, 0, 0))
    lumps["leafs"] = b"".join(leaves)
    lumps["leaffaces"] = struct.pack("<H", 0)
    lumps["edges"] = struct.pack("<6H", 0, 1, 1, 2, 2, 0)
    lumps["surfedges"] = struct.pack("<3i", 0, 1, 2)
    lumps["models"] = struct.pack("<9f3i", 0, 0, 0, 64, 64, 64, 0, 0, 0, 0, 0, 1)
    lumps["areas"] = struct.pack("<2i", 0, 0)
    data = bytearray(160)
    struct.pack_into("<4si", data, 0, b"IBSP", 38)
    for i, name in enumerate(LUMP_NAMES):
        payload = lumps[name]
        if not payload:
            continue
        data.extend(bytes((-len(data)) % 4))
        struct.pack_into("<ii", data, 8 + 8 * i, len(data), len(payload))
        data.extend(payload)
    return bytes(data)


def lump_range(data, name):
    return struct.unpack_from("<ii", data, 8 + LUMP_NAMES.index(name) * 8)


FAKE_COMPILER = r'''#!/usr/bin/env python3
import json, os
from pathlib import Path
import sys
args = sys.argv[1:]
stage = args[0].removeprefix('-')
with open(os.environ['FAKE_ACTION_LOG'], 'a') as f:
    f.write(json.dumps(args) + '\n')
target = Path(args[-1])
mode = os.environ.get('FAKE_MODE', '')
if mode == 'failed' and stage == os.environ.get('FAKE_FAIL_STAGE', 'bsp'):
    print('intentional compiler failure')
    sys.exit(17)
if mode == 'missing_texture' and stage == 'bsp':
    print("WARNING: couldn't locate texture sandbox/missing")
if mode == 'missing_colormap' and stage == 'rad':
    print("Couldn't load pics/colormap.pcx")
if mode == 'leak_log' and stage == 'bsp':
    print('**** leaked ****')
if mode == 'leak_file' and stage == 'bsp':
    target.with_suffix('.lin').write_text('0 0 0\n')
if mode != 'no_output':
    fixture = {'bsp': 'preview', 'vis': 'vis', 'rad': 'full'}[stage]
    if stage == 'rad' and mode in ('bad_vis', 'missing_vis', 'missing_light'):
        fixture = mode
    target.with_suffix('.bsp').write_bytes((Path(os.environ['FAKE_FIXTURES']) / (fixture + '.bsp')).read_bytes())
'''


class VisibilityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="pp-vis-tests-")
        self.root = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)

    def audit(self, data, release=False):
        path = self.root / "fixture.bsp"
        path.write_bytes(data)
        return bsp_inventory(path, require_release=release)

    def test_rle_literals_zero_runs_and_absent_row_semantics(self):
        self.assertEqual(decompress_vis(b"\xff\x12\0\3\x80", 1, 5), b"\x12\0\0\0\x80")
        self.assertEqual(decompress_vis(b"", -1, 3), b"\xff" * 3)
        for data, offset, size in [(b"\0", 0, 1), (b"\0\0", 0, 1),
                                   (b"\0\4", 0, 3), (b"\1", 0, 2),
                                   (b"\1", 1, 1), (b"\1", -2, 1)]:
            with self.subTest(data=data, offset=offset, size=size), self.assertRaises(ValueError):
                decompress_vis(data, offset, size)

    def test_valid_pvs_cluster_statistics_and_preview(self):
        report = self.audit(fixture_bsp(), release=True)
        self.assertEqual(report["clusters"], 2)
        self.assertEqual(report["pvs_visible_clusters_mean"], 1.5)
        self.assertEqual(report["pvs_visible_clusters_max"], 2)
        self.assertEqual(report["pvs_visible_fraction_mean"], .75)
        self.assertEqual(report["lumps"]["leafs"]["count"], 3)
        self.assertTrue(report["release_lumps_present"])
        self.assertFalse(self.audit(fixture_bsp(vis=False, light=False))["release_lumps_present"])

    def test_reject_bad_bsp_headers_lump_bounds_sizes_and_leaf_clusters(self):
        valid = fixture_bsp()
        invalid = [b"", valid[:159], b"NOT!" + valid[4:]]
        bad = bytearray(valid); struct.pack_into("<i", bad, 4, 39); invalid.append(bad)
        bad = bytearray(valid); struct.pack_into("<ii", bad, 8, len(valid) + 1, 4); invalid.append(bad)
        bad = bytearray(valid); struct.pack_into("<ii", bad, 8, 159, 2); invalid.append(bad)
        bad = bytearray(valid)
        planes = 8 + LUMP_NAMES.index("planes") * 8
        struct.pack_into("<i", bad, planes + 4, 19); invalid.append(bad)
        bad = bytearray(valid)
        leaves, _ = lump_range(bad, "leafs")
        struct.pack_into("<h", bad, leaves + 28 + 4, 2); invalid.append(bad)
        for data in invalid:
            with self.subTest(length=len(data)), self.assertRaises(ValueError):
                self.audit(data)

    def test_reject_invalid_pvs_or_phs_and_offsets_inside_table(self):
        valid = fixture_bsp()
        vis_start, _ = lump_range(valid, "visibility")
        bad = bytearray(valid); struct.pack_into("<i", bad, vis_start + 4, 4)
        with self.assertRaises(ValueError):
            self.audit(bad)
        bad = bytearray(valid); struct.pack_into("<i", bad, vis_start + 8, 24)
        with self.assertRaises(ValueError):
            self.audit(bad)
        with self.assertRaises(ValueError):
            self.audit(fixture_bsp(bad_row=True))

    def test_reject_overlapping_nonempty_lumps(self):
        bad = bytearray(fixture_bsp())
        # The first 20 bytes of texinfo also satisfy the plane-size modulus.
        texinfo, _ = lump_range(bad, "texinfo")
        struct.pack_into("<ii", bad, 8 + LUMP_NAMES.index("planes") * 8, texinfo, 20)
        with self.assertRaisesRegex(ValueError, "overlap"):
            self.audit(bad, release=True)

    def test_release_requires_actual_vis_rows_and_baked_lighting(self):
        for data in [fixture_bsp(vis=False), fixture_bsp(light=False), fixture_bsp(absent_rows=True)]:
            with self.subTest(size=len(data)), self.assertRaises(ValueError):
                self.audit(data, release=True)


class SourceInventoryTests(unittest.TestCase):
    def test_exact_supplied_sandbox_source_inventory(self):
        path = ROOT / "maps/source/pp_sandbox_coop1.map"
        report = map_inventory(path)
        expected = {"sha256": "09dd444a8523b669d31c26940dd630f2ce42e7799ee6745a0622ccf5284bd550",
                    "entities": 470, "brushes": 1738, "world_brushes": 1664,
                    "detail_brushes": 499, "source_faces": 11317, "pickups": 155,
                    "initial_monsters": 37, "spawners": 26, "timers": 13,
                    "placed_lights": 118, "sand_brushes": 1201,
                    "sand_detail": 57, "sand_structural": 1144}
        for key, value in expected.items():
            with self.subTest(key=key):
                self.assertEqual(report[key], value)
        self.assertEqual(len(report["player_starts"]), 5)

    def test_classic_and_valve220_detail_flags_agree(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.map"
            for text in [MAP_TEXT, MAP_TEXT.replace("0 0 0 1 1 134217728", "[ 1 0 0 0 ] [ 0 1 0 0 ] 0 1 1 134217728")]:
                path.write_text(text)
                report = map_inventory(path)
                self.assertEqual(report["detail_brushes"], 1)
                self.assertEqual(report["source_faces"], 6)
                self.assertEqual(report["sand_detail"], 1)
            path.write_text(MAP_TEXT[:-2])
            with self.assertRaises(ValueError):
                map_inventory(path)


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="pp compile test ")
        self.root = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)
        self.source = self.root / "source input" / "room with spaces.map"
        self.source.parent.mkdir()
        self.source.write_text(MAP_TEXT)
        self.basedir = self.root / "game data"; self.basedir.mkdir()
        self.builddir = self.root / "build area"
        self.outputdir = self.root / "published maps"; self.outputdir.mkdir()
        self.final = self.outputdir / self.source.with_suffix(".bsp").name
        self.old = b"previous published map must survive"
        self.final.write_bytes(self.old)
        self.stage = self.builddir / self.source.stem
        self.fixtures = self.root / "fixtures"; self.fixtures.mkdir()
        for name, data in {
            "preview": fixture_bsp(vis=False, light=False), "vis": fixture_bsp(light=False),
            "full": fixture_bsp(), "bad_vis": fixture_bsp(bad_row=True),
            "missing_vis": fixture_bsp(vis=False), "missing_light": fixture_bsp(light=False)
        }.items():
            (self.fixtures / (name + ".bsp")).write_bytes(data)
        self.tool = self.root / "compiler directory" / "fake q2tool"
        self.tool.parent.mkdir()
        self.tool.write_text(FAKE_COMPILER); self.tool.chmod(0o755)
        self.action_log = self.root / "actions.jsonl"

    def run_compile(self, *extra, mode="", fail_stage="bsp"):
        env = os.environ.copy()
        env.update(FAKE_ACTION_LOG=str(self.action_log), FAKE_FIXTURES=str(self.fixtures),
                   FAKE_MODE=mode, FAKE_FAIL_STAGE=fail_stage)
        cmd = [sys.executable, str(ROOT / "tools/performance/compile_map.py"),
               "--source", str(self.source), "--tool", str(self.tool),
               "--basedir", str(self.basedir), "--build-dir", str(self.builddir),
               "--output-dir", str(self.outputdir), "--threads", "2", *extra]
        return subprocess.run(cmd, env=env, text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=20)

    def actions(self):
        return [json.loads(line) for line in self.action_log.read_text().splitlines()] if self.action_log.exists() else []

    def manifest(self):
        return json.loads((self.stage / "manifest.json").read_text())

    def assert_preserved(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.final.exists(), "failed build deleted the old published BSP")
        self.assertEqual(self.final.read_bytes(), self.old)

    def test_release_runs_full_bsp_vis_rad_with_safe_argument_boundaries(self):
        result = self.run_compile()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        calls = self.actions()
        self.assertEqual([c[0] for c in calls], ["-bsp", "-vis", "-rad"])
        for i, call in enumerate(calls):
            self.assertEqual(call[1:5], ["-threads", "2", "-basedir", str(self.basedir)])
            self.assertEqual(call[-1], str(self.stage / self.source.name) if i == 0 else str(self.stage / self.source.with_suffix(".bsp").name))
            self.assertNotIn("-fast", call)
        self.assertEqual(self.final.read_bytes(), fixture_bsp())
        manifest = self.manifest()
        self.assertTrue(manifest["published"])
        self.assertEqual(manifest["profile"], "release")
        self.assertEqual([s["returncode"] for s in manifest["stages"]], [0, 0, 0])
        self.assertTrue(manifest["bsp_inventory"]["release_lumps_present"])
        self.assertEqual(self.source.read_text(), MAP_TEXT)

    def test_preview_omits_vis_rad_unless_explicit(self):
        result = self.run_compile("--profile", "preview")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([c[0] for c in self.actions()], ["-bsp"])
        self.assertFalse(self.manifest()["bsp_inventory"]["release_lumps_present"])
        self.action_log.unlink()
        result = self.run_compile("--profile", "preview", "--rad")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([c[0] for c in self.actions()], ["-bsp", "-vis", "-rad"])

    def test_each_compiler_stage_failure_preserves_old_publication(self):
        for stage in ["bsp", "vis", "rad"]:
            with self.subTest(stage=stage):
                result = self.run_compile(mode="failed", fail_stage=stage)
                self.assert_preserved(result)
                manifest = self.manifest()
                self.assertFalse(manifest["published"])
                self.assertEqual(manifest["stages"][-1]["returncode"], 17)
                self.assertIn("error", manifest)

    def test_leak_log_or_pointfile_blocks_publication(self):
        for mode in ["leak_log", "leak_file"]:
            with self.subTest(mode=mode):
                self.assert_preserved(self.run_compile(mode=mode))
                self.assertFalse(self.manifest()["published"])

    def test_missing_textures_or_colormap_block_publication(self):
        for mode in ["missing_texture", "missing_colormap"]:
            with self.subTest(mode=mode):
                self.assert_preserved(self.run_compile(mode=mode))
                self.assertIn("missing compile assets", self.manifest()["error"])

    def test_missing_asset_diagnostic_never_publishes(self):
        result = self.run_compile("--allow-missing-textures", mode="missing_texture")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.final.read_bytes(), self.old)
        self.assertFalse(self.manifest()["published"])
        self.assertTrue(self.manifest()["diagnostic"])
        self.assertTrue((self.stage / self.final.name).is_file())

    def test_missing_or_invalid_compiler_outputs_do_not_publish(self):
        for mode in ["no_output", "bad_vis", "missing_vis", "missing_light"]:
            with self.subTest(mode=mode):
                self.assert_preserved(self.run_compile(mode=mode))
                self.assertFalse(self.manifest()["published"])
                self.assertIn("error", self.manifest())

    def test_overlapping_stage_and_publication_is_rejected_without_deletion(self):
        self.outputdir = self.stage
        self.outputdir.mkdir(parents=True)
        self.final = self.outputdir / self.source.with_suffix(".bsp").name
        self.final.write_bytes(self.old)
        self.assert_preserved(self.run_compile(mode="failed"))
        self.assertEqual(self.actions(), [], "unsafe stage/output overlap should be rejected before compiler invocation")

    def test_symlinked_stage_cannot_alias_published_directory(self):
        self.builddir.mkdir()
        try:
            self.stage.symlink_to(self.outputdir, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("directory symlinks unavailable on this platform")
        self.assert_preserved(self.run_compile(mode="failed"))
        self.assertEqual(self.actions(), [])

    def test_malformed_source_records_failure_without_traceback_or_publication(self):
        self.source.write_text(MAP_TEXT[:-2])
        result = self.run_compile()
        self.assert_preserved(result)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.actions(), [])
        self.assertFalse(self.manifest()["published"])
        self.assertIn("error", self.manifest())


if __name__ == "__main__":
    unittest.main(verbosity=2)
