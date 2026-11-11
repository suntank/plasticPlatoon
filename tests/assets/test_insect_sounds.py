#!/usr/bin/env python3
"""Verify the approved insect effect inventory, source parity and packaging."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/assets'))
from build_overlay import build_overlay, verify_overlay
from build_support_sounds import SOUNDS as GENERATED_SOUNDS
from import_insect_sounds import EVENTS, SOUNDS, SOURCE, import_sounds, pcm


class InsectSoundTests(unittest.TestCase):
    def test_18_approved_unique_takes_and_formats(self):
        report = import_sounds(verify=True)
        self.assertEqual(len(report['files']), 18)
        self.assertEqual(len({f['source_sha256'] for f in report['files']}), 18)
        self.assertEqual(len({f['sha256'] for f in report['files']}), 18)
        for item in report['files']:
            with self.subTest(sound=item['path']):
                raw = (ROOT / item['source_path']).read_bytes()
                mono = (ROOT / 'baseq2' / item['path']).read_bytes()
                self.assertEqual(mono, (ROOT / item['canonical_path']).read_bytes())
                self.assertEqual(hashlib.sha256(raw).hexdigest(), item['source_sha256'])
                self.assertEqual(hashlib.sha256(mono).hexdigest(), item['sha256'])
                frames, _ = pcm(mono, 1)
                self.assertEqual(frames, item['frames'])
                self.assertEqual(frames, pcm(raw, 2)[0])
                self.assertGreater(frames, 20000)
                self.assertLessEqual(frames, 57600)
                self.assertFalse(item['loop'])
                self.assertNotIn(item['path'][6:], GENERATED_SOUNDS)

    def test_two_takes_per_event_and_no_spider_alert(self):
        self.assertEqual(EVENTS['ant'], ('sight', 'pain', 'attack', 'idle', 'scuttle'))
        self.assertEqual(EVENTS['spider'], ('pain', 'attack', 'idle', 'scuttle'))
        report = import_sounds(verify=True)
        for creature, events in EVENTS.items():
            for event in events:
                self.assertEqual([f['take'] for f in report['files']
                                  if f['creature'] == creature and f['event'] == event], [1, 2])
        self.assertFalse(any('spider/sight' in name for name in SOUNDS))
        for filename in ('Makefile', 'CMakeLists.txt'):
            self.assertIn('import_insect_sounds.py', (ROOT / filename).read_text())

    def test_archive_packages_exact_samples_and_detects_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, manifest = root / 'baseq2', root / 'manifest.json'
            report = import_sounds(SOURCE, source / 'sound', manifest)
            archive = root / 'insects.pk3'
            build_overlay(source, archive)
            verify_overlay(source, archive)
            with zipfile.ZipFile(archive) as packaged:
                self.assertEqual(set(packaged.namelist()), {f['path'] for f in report['files']})
                for item in report['files']:
                    self.assertEqual(hashlib.sha256(packaged.read(item['path'])).hexdigest(), item['sha256'])
            changed = source / report['files'][0]['path']
            changed.write_bytes(changed.read_bytes()[:-2])
            with self.assertRaisesRegex(ValueError, 'differs from approved'):
                import_sounds(SOURCE, source / 'sound', manifest, verify=True)
            with self.assertRaises(ValueError):
                verify_overlay(source, archive)

    def test_original_canonical_and_manifest_tampering_are_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inputs = root / 'inputs'
            shutil.copytree(SOURCE, inputs)
            output, manifest = root / 'sound', root / 'manifest.json'
            report = import_sounds(inputs, output, manifest)
            for prefix in ('raw', 'game_ready'):
                changed = inputs / prefix / SOUNDS[0]
                data = changed.read_bytes()
                changed.write_bytes(data + b'changed')
                with self.assertRaisesRegex(ValueError, 'source hash mismatch'):
                    import_sounds(inputs, output, manifest, verify=True)
                changed.write_bytes(data)
            report['files'][0]['event'] = 'wrong event'
            manifest.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, 'manifest differs'):
                import_sounds(inputs, output, manifest, verify=True)
            generation = inputs / 'generation-manifest.json'
            data = json.loads(generation.read_text())
            data['files'].pop()
            generation.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'exactly the 18'):
                import_sounds(inputs, output, manifest, verify=True)


if __name__ == '__main__':
    unittest.main()
