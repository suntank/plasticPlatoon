#!/usr/bin/env python3
"""Small executable benchmark/packaging regressions, without a game or GPU.

The launcher tests run a real fake-engine child process. The summary and archive
tests exercise production functions against independently constructed fixtures.
No compiler, source asset conversion, X server, or timing workload is required.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/performance"))
sys.path.insert(0, str(ROOT / "tools/assets"))
from summarize import percentile, summarize
from build_overlay import build_overlay

RUNNER = ROOT / "tools/performance/run_benchmark.py"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def write_csv(path, fields, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


FAKE_ENGINE = r'''#!/usr/bin/env python3
import csv, json, os, re, sys
from pathlib import Path
args = sys.argv[1:]
data = Path(args[args.index('-datadir') + 1])
cfg = data / 'baseq2' / args[args.index('+exec') + 1]
commands = cfg.read_text().splitlines()
label = next(c.split()[1] for c in commands if c.startswith('cl_perf_start '))
perf = data / 'baseq2/perf'
(perf / (label + '-invocation.json')).write_text(json.dumps({'args': args, 'cwd': str(Path.cwd())}))
print('FAKE_ENGINE_STARTED', flush=True)
if os.environ.get('PP_TEST_ENGINE') == 'failed':
    sys.exit(17)
settings = dict(re.findall(r'^set (\w+) "([^"]*)"$', cfg.read_text(), re.M))
count = int(settings['cl_perf_frames'])
with (perf / (label + '-frames.csv')).open('w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['frame', 'frame_ms', 'width', 'height', 'rss_kib', 'server_edicts'])
    for frame in range(count):
        writer.writerow([frame, 10 if frame else 0, settings['r_customwidth'], settings['r_customheight'], 1024, 8])
with (perf / (label + '-views.csv')).open('w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['frame', 'slot', 'renderer_serial', 'renderer_counters', 'gpu_supported', 'gpu_origin_serial', 'gpu_ms'])
    for frame in range(count):
        writer.writerow([frame, 0, frame + 1, 1, 0, 0, -1])
(perf / (label + '-settings.txt')).write_text('fixture, not a GPU benchmark\n')
'''


class LauncherTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pp benchmark tools ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.data = self.root / "runtime data"
        self.base = self.data / "baseq2"
        self.base.mkdir(parents=True)
        self.binary = self.root / "engine tools" / "fake quake2"
        self.binary.parent.mkdir()
        self.binary.write_text(FAKE_ENGINE)
        self.binary.chmod(0o755)
        self.perf = self.base / "perf"
        self.perf.mkdir()
        for path, payload in {
            self.binary.parent / "ref_gl1.so": b"renderer fixture",
            self.base / "game.so": b"game fixture",
            self.base / "pak0.pak": b"stock data fixture, not project content",
            self.base / "plastic-platoon.pk3": b"project overlay fixture",
            self.base / "maps/fixture.bsp": b"compiled map fixture",
        }.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)

    def launch(self, *extra, source=("--map", "fixture"), mode="", label="capture"):
        return subprocess.run(
            [sys.executable, str(RUNNER), "--binary", str(self.binary),
             "--data", str(self.data), "--label", label, "--frames", "6",
             "--warmup", "1", "--timeout", "5", *source, *extra],
            text=True, capture_output=True, timeout=15,
            env={**os.environ, "PP_TEST_ENGINE": mode})

    def test_map_command_pose_normalization_arguments_and_input_hashes(self):
        result = self.launch("--players", "2", "--size", "320x240", "--screenshot",
                             "--pose", "1.0", "1e1", "-2.5", "32", "0", "90",
                             "--set", "r_modulate", "1.25")
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = (self.perf / "capture.cfg").read_text().splitlines()
        self.assertIn("cl_bench_local 2 fixture", commands)
        self.assertIn("cl_bench_pose 1 10 -2.5 32 0 90", commands)
        self.assertIn('set cheats "1"', commands)
        self.assertIn('set cl_perf_screenshot "1"', commands)
        self.assertIn('set gl_finish "0"', commands)
        invocation = json.loads((self.perf / "capture-invocation.json").read_text())
        self.assertEqual(invocation["cwd"], str(self.data))
        self.assertEqual(invocation["args"][:3], ["-portable", "-datadir", str(self.data)])
        self.assertEqual(invocation["args"][-2:], ["+exec", "perf/capture.cfg"])
        self.assertIn("320", invocation["args"])
        meta = json.loads((self.perf / "capture-run.json").read_text())
        for field, path in {
            "binary_sha256": self.binary,
            "renderer_sha256": self.binary.parent / "ref_gl1.so",
            "game_sha256": self.base / "game.so",
            "map_sha256": self.base / "maps/fixture.bsp",
            "pak0_sha256": self.base / "pak0.pak",
            "project_overlay_sha256": self.base / "plastic-platoon.pk3",
        }.items():
            with self.subTest(field=field):
                self.assertEqual(meta[field], sha256(path.read_bytes()))
        self.assertEqual(meta["summary"]["frames"], 5)
        self.assertEqual(meta["summary"]["metrics"]["frame_ms"]["median"], 10)
        self.assertFalse(meta["software_display_requested"])
        self.assertEqual(meta["settings"]["r_modulate"], "1.25")

    def test_demo_mode_is_explicit_and_does_not_start_a_local_server(self):
        result = self.launch(source=("--demo", "demos/demo1.dm2"))
        self.assertEqual(result.returncode, 0, result.stderr)
        cfg = (self.perf / "capture.cfg").read_text()
        self.assertIn("set timedemo 1\ndemomap demos/demo1.dm2\n", cfg)
        self.assertNotIn("cl_bench_local", cfg)
        self.assertNotIn("cl_bench_pose", cfg)
        self.assertNotIn("set cheats", cfg)

    def test_unsafe_or_inconsistent_arguments_fail_before_launch_and_cfg_write(self):
        invalid = [
            ("--label", "bad;quit"), ("--label", "a" * 56),
            ("--map", "../escape"), ("--map", "fixture\nquit"),
            ("--size", "0x480"), ("--size", "640x-1"),
            ("--size", "640x480;quit"), ("--warmup", "-1"),
            ("--frames", "1"), ("--timeout", "0"),
            ("--timeout", "-1"), ("--timeout", "nan"), ("--timeout", "inf"),
            ("--set", "r_mode;quit", "1"), ("--set", "r_modulate", '1";quit'),
            ("--set", "r_modulate", "1\nquit"), ("--set", "game", "other"),
            ("--set", "cl_perf_frames", "0"), ("--set", "timedemo", "1"),
            ("--pose", "0.5", "0", "0", "0", "0", "0"),
            ("--pose", "1", "0", "0", "0", "0", "0"),
            ("--pose", "0", "nan", "0", "0", "0", "0"),
            ("--pose", "0", "0", "0", "0", "inf", "0"),
            ("--pose", "0", "32768", "0", "0", "0", "0"),
            ("--pose", "0", "0;quit", "0", "0", "0", "0"),
        ]
        for arguments in invalid:
            with self.subTest(arguments=arguments):
                result = self.launch(*arguments)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(list(self.perf.iterdir()), [])
        for arguments in [("--players", "2"),
                          ("--pose", "0", "0", "0", "0", "0", "0")]:
            with self.subTest(demo_arguments=arguments):
                result = self.launch(*arguments, source=("--demo", "demo1.dm2"))
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(list(self.perf.iterdir()), [])

    def test_each_existing_capture_artifact_prevents_any_overwrite(self):
        for suffix in (".cfg", "-frames.csv", "-views.csv", "-settings.txt",
                       "-console.log", "-run.json"):
            with self.subTest(suffix=suffix):
                protected = self.perf / ("capture" + suffix)
                protected.write_bytes(b"previous measurement must survive\n")
                result = self.launch()
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("capture already exists", result.stderr)
                self.assertEqual(protected.read_bytes(), b"previous measurement must survive\n")
                self.assertEqual(list(self.perf.iterdir()), [protected])
                protected.unlink()

    def test_successful_capture_cannot_be_reused_or_modified(self):
        first = self.launch()
        self.assertEqual(first.returncode, 0, first.stderr)
        before = {p.name: p.read_bytes() for p in self.perf.iterdir()}
        second = self.launch("--size", "240x240")
        self.assertEqual(second.returncode, 2, second.stderr)
        self.assertEqual({p.name: p.read_bytes() for p in self.perf.iterdir()}, before)

    def test_failed_engine_records_failure_without_claiming_a_summary(self):
        result = self.launch(mode="failed")
        self.assertEqual(result.returncode, 1, result.stderr)
        meta = json.loads((self.perf / "capture-run.json").read_text())
        self.assertEqual(meta["returncode"], 17)
        self.assertIn("engine exited 17", meta["error"])
        self.assertNotIn("summary", meta)
        self.assertGreaterEqual(meta["seconds"], 0)
        self.assertIn("FAKE_ENGINE_STARTED", (self.perf / "capture-console.log").read_text())


class SummaryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pp summary tests ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.frames = self.root / "capture-frames.csv"
        self.views = self.root / "capture-views.csv"

    def frame_fixture(self, rows):
        write_csv(self.frames, ["frame", "frame_ms", "rss_kib", "server_edicts",
                               "active_particles", "unsupported"],
                  [dict(frame=i, frame_ms=ms, rss_kib=1024+i, server_edicts=10+i,
                        active_particles=i, unsupported=-1) for i, ms in rows])

    def test_percentile_linear_interpolation_and_empty_singleton_edges(self):
        self.assertIsNone(percentile([], .95))
        self.assertEqual(percentile([7], .99), 7)
        self.assertEqual(percentile([40, 10, 30, 20], 0), 10)
        self.assertEqual(percentile([40, 10, 30, 20], 1), 40)
        self.assertEqual(percentile([40, 10, 30, 20], .5), 25)
        self.assertAlmostEqual(percentile([40, 10, 30, 20], .95), 38.5)
        self.assertAlmostEqual(percentile([40, 10, 30, 20], .99), 39.7)

    def test_warmup_counts_display_rows_and_drops_untimed_rows(self):
        self.frame_fixture([(0, 0), (1, 999), (2, 10), (3, 20), (4, 30), (5, 40), (6, 0), (7, -1)])
        result = summarize(self.frames, warmup=2)
        self.assertEqual(result["frames"], 4)
        self.assertEqual(result["warmup_frames"], 2)
        self.assertEqual(result["metrics"]["frame_ms"]["median"], 25)
        self.assertAlmostEqual(result["metrics"]["frame_ms"]["p95"], 38.5)
        self.assertAlmostEqual(result["metrics"]["frame_ms"]["p99"], 39.7)
        self.assertEqual(result["metrics"]["frame_ms"]["maximum"], 40)
        self.assertAlmostEqual(result["elapsed_seconds"], .1)
        self.assertEqual(result["over_33_333_ms_percent"], 25)
        self.assertEqual(result["rss_kib_first_last"], [1026, 1029])
        self.assertEqual(result["active_particles_first_last"], [2, 5])
        self.assertNotIn("unsupported", result["metrics"])
        self.assertNotIn("gpu_view_ms", result)
        with self.assertRaisesRegex(ValueError, "no timed frames"):
            summarize(self.frames, warmup=8)

    def test_gpu_queries_use_origins_deduplicate_and_exclude_warmup_or_untimed_frames(self):
        self.frame_fixture([(0, 0), (1, 10), (2, 0), (3, 30), (4, 40)])
        fields = ["frame", "slot", "renderer_serial", "renderer_counters",
                  "gpu_supported", "gpu_origin_serial", "gpu_ms"]
        values = [
            (0, 0, 100, 1, 1, 0, -1),
            (1, 0, 101, 1, 1, 100, 999),  # Origin discarded during warmup.
            (1, 1, 102, 1, 1, 100, 999),  # Repeated publication is not another query.
            (2, 0, 103, 1, 1, 101, 2),   # Query origin survives although delivery frame is untimed.
            (3, 0, 104, 1, 1, 101, 2),
            (3, 1, 105, 1, 1, 102, 4),
            (4, 0, 106, 1, 1, 103, 500), # Untimed originating frame must be excluded.
            (4, 1, 107, 1, 1, 104, 6),
            (4, 2, 108, 1, 1, 999, 500), # Unknown originating query must be excluded.
            (4, 3, 100, 0, 0, 0, -1),   # Unsupported stale serial cannot move origin out of warmup.
            (5, 0, 109, 1, 1, 109, 500), # No complete-frame record for this origin.
        ]
        write_csv(self.views, fields, [dict(zip(fields, row)) for row in values])
        result = summarize(self.frames, warmup=1)
        self.assertEqual(result["frames"], 3)
        self.assertEqual(result["gpu_view_samples"], 3)
        self.assertEqual(result["gpu_view_ms"]["median"], 4)
        self.assertAlmostEqual(result["gpu_view_ms"]["p95"], 5.8)
        self.assertEqual(result["metrics"]["frame_ms"]["median"], 30)

    def test_summary_cli_rejects_negative_warmup_and_writes_requested_json(self):
        self.frame_fixture([(0, 0), (1, 20), (2, 40)])
        script = ROOT / "tools/performance/summarize.py"
        output = self.root / "report/summary.json"
        result = subprocess.run([sys.executable, str(script), str(self.frames),
                                 "--warmup", "1", "--json", str(output)],
                                text=True, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Median complete frame ms", result.stdout)
        self.assertEqual(json.loads(output.read_text())[0]["frames"], 2)
        result = subprocess.run([sys.executable, str(script), str(self.frames), "--warmup", "-1"],
                                text=True, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_gpu_serials_above_double_integer_precision_remain_distinct(self):
        self.frame_fixture([(0, 0), (1, 10), (2, 20), (3, 30)])
        base = 2**53 + 4
        self.assertEqual(float(base), float(base + 1))  # This is the precision boundary being tested.
        fields = ["frame", "slot", "renderer_serial", "renderer_counters",
                  "gpu_supported", "gpu_origin_serial", "gpu_ms"]
        values = [
            (0, 0, base - 1, 1, 1, 0, -1),
            (1, 0, base, 1, 1, base - 1, 999),       # Warmup origin remains excluded.
            (1, 1, base + 1, 1, 1, base - 1, 999),
            (2, 0, base + 2, 1, 1, base, 2),
            (3, 0, base + 3, 1, 1, base + 1, 6),    # Adjacent 64-bit origin is distinct.
            (3, 1, base + 4, 1, 1, base, 2),        # Republishing still deduplicates.
        ]
        write_csv(self.views, fields, [dict(zip(fields, row)) for row in values])
        result = summarize(self.frames, warmup=1)
        self.assertEqual(result["gpu_view_samples"], 2)
        self.assertEqual(result["gpu_view_ms"]["median"], 4)
        self.assertAlmostEqual(result["gpu_view_ms"]["p95"], 5.8)


class OverlayTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pp overlay tests ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "project/baseq2"
        self.output = self.root / "release/baseq2/plastic-platoon.pk3"
        self.expected = {
            "models/items/armor/shard/tris.md2": b"project optimized model",
            "models/items/armor/shard/skin.png": b"project pickup skin",
            "players/male/tris.md2": b"project player model",
            "players/male/skin.PCX": b"project player skin",
            "sprites/muzzle.sp2": b"project sprite definition",
            "sprites/muzzle.tga": b"project sprite image",
            "performance/pi-zero2.cfg": b"set gl1_picmip 1\n",
        }
        excluded = {
            "pak0.pak": b"licensed stock archive",
            "other.pk3": b"unrelated archive",
            "game.so": b"platform-specific binary",
            "config.cfg": b"local user settings",
            "models/items/recovery.blend1": b"recoverable source, not runtime data",
            "models/items/private.txt": b"unrelated text",
            "models/items/skin.png.bak": b"backup image",
            "performance/capture-run.json": b"local timing report",
        }
        for relative, data in {**self.expected, **excluded}.items():
            path = self.source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    def test_archive_contains_only_project_runtime_assets_and_exact_provenance(self):
        manifest = build_overlay(self.source, self.output)
        self.assertEqual(manifest["schema"], 1)
        with zipfile.ZipFile(self.output) as archive:
            self.assertEqual(archive.namelist(), sorted(self.expected))
            for entry in manifest["files"]:
                with self.subTest(path=entry["path"]):
                    data = archive.read(entry["path"])
                    self.assertEqual(data, self.expected[entry["path"]])
                    self.assertEqual(entry["bytes"], len(data))
                    self.assertEqual(entry["sha256"], sha256(data))
                    self.assertNotIn("..", Path(entry["path"]).parts)
                    self.assertFalse(Path(entry["path"]).is_absolute())
                    info = archive.getinfo(entry["path"])
                    self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))
                    self.assertEqual(info.external_attr >> 16, 0o100644)
        self.assertEqual(manifest["archive_sha256"], sha256(self.output.read_bytes()))
        self.assertEqual(manifest["archive_bytes"], self.output.stat().st_size)
        self.assertEqual(json.loads(self.output.with_suffix(".manifest.json").read_text()), manifest)

    def test_output_is_deterministic_across_mtimes_permissions_and_output_names(self):
        first = build_overlay(self.source, self.output)
        archive_bytes = self.output.read_bytes()
        for relative in self.expected:
            path = self.source / relative
            path.chmod(0o600)
            os.utime(path, (1735689600, 1735689600))
        other = self.output.with_name("second-name.pk3")
        second = build_overlay(self.source, other)
        self.assertEqual(other.read_bytes(), archive_bytes)
        self.assertEqual(second, first)

    def test_manifest_describes_the_single_read_archived_even_if_source_changes(self):
        changed = self.source / "models/items/armor/shard/tris.md2"
        original_read = Path.read_bytes
        reads = []

        def changing_read(path):
            data = original_read(path)
            if path == changed:
                reads.append(path)
                path.write_bytes(b"later concurrently produced revision")
            return data

        with mock.patch.object(Path, "read_bytes", changing_read):
            manifest = build_overlay(self.source, self.output)
        self.assertEqual(reads, [changed])
        with zipfile.ZipFile(self.output) as archive:
            for entry in manifest["files"]:
                self.assertEqual(entry["sha256"], sha256(archive.read(entry["path"])))

    def test_failure_keeps_previous_archive_manifest_and_removes_staging_file(self):
        build_overlay(self.source, self.output)
        previous = self.output.read_bytes()
        manifest = self.output.with_suffix(".manifest.json")
        previous_manifest = manifest.read_bytes()
        with mock.patch.object(zipfile.ZipFile, "writestr", side_effect=OSError("fixture disk failure")):
            with self.assertRaisesRegex(OSError, "fixture disk failure"):
                build_overlay(self.source, self.output)
        self.assertEqual(self.output.read_bytes(), previous)
        self.assertEqual(manifest.read_bytes(), previous_manifest)
        self.assertEqual(set(self.output.parent.iterdir()), {self.output, manifest})

    def test_empty_sources_or_escaping_asset_symlinks_cannot_replace_release(self):
        build_overlay(self.source, self.output)
        previous = self.output.read_bytes()
        empty = self.root / "empty"
        empty.mkdir()
        with self.assertRaisesRegex(ValueError, "no project assets"):
            build_overlay(empty, self.output)
        outside = self.root / "unrelated.png"
        outside.write_bytes(b"must never be packaged")
        (self.source / "models/escape.png").symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "escapes project source"):
            build_overlay(self.source, self.output)
        self.assertEqual(self.output.read_bytes(), previous)


if __name__ == "__main__":
    unittest.main()
