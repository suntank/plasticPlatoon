#!/usr/bin/env python3
"""Verify source provenance, playable formats, and packaging for added alerts."""
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest
import wave
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/assets'))
from build_overlay import build_overlay, verify_overlay
from build_support_sounds import SOUNDS
from import_soldier_callouts import CALLOUTS, SOURCE, import_callouts
from import_soldier_sounds import mono_wav


class SoldierCalloutTests(unittest.TestCase):
    def test_eight_unique_takes_reproduce_exactly_as_mono_pcm(self):
        report = import_callouts(verify=True)
        self.assertEqual(len(report['files']), 8)
        self.assertEqual(len({f['original_sha256'] for f in report['files']}), 8)
        self.assertEqual(len({f['sha256'] for f in report['files']}), 8)
        for item in report['files']:
            with self.subTest(sound=item['path']):
                original = (ROOT / item['original_path']).read_bytes()
                decoded = (ROOT / item['source_path']).read_bytes()
                data = (ROOT / 'baseq2' / item['path']).read_bytes()
                self.assertEqual(hashlib.sha256(original).hexdigest(), item['original_sha256'])
                self.assertEqual(hashlib.sha256(decoded).hexdigest(), item['source_sha256'])
                self.assertEqual(data, mono_wav(decoded)[0])
                with wave.open(io.BytesIO(data)) as sound:
                    self.assertEqual((sound.getnchannels(), sound.getsampwidth()), (1, 2))
                    self.assertEqual(sound.getframerate(), 44100)
                    self.assertEqual(sound.getnframes(), item['frames'])
                    self.assertGreater(sound.getnframes(), 10000)
                self.assertNotIn(item['path'][6:], SOUNDS)
                self.assertFalse(item['loop'])

    def test_each_phrase_has_two_takes_and_all_paths_are_used_by_game(self):
        self.assertEqual({phrase for _, phrase, _ in CALLOUTS.values()},
                         {'Contact!', 'Enemy spotted!', 'Over here!', 'Contact, get him!'})
        for phrase in {phrase for _, phrase, _ in CALLOUTS.values()}:
            self.assertEqual([take for _, text, take in CALLOUTS.values() if text == phrase],
                             ['A', 'B'])
        source = (ROOT / 'src/game/monster/soldier/soldier.c').read_text()
        paths = set(re.findall(r'"(soldier/callouts/[^"\n]+)"', source))
        self.assertEqual(paths, {'soldier/callouts/' + path for path, _, _ in CALLOUTS.values()})
        for build_file in ('Makefile', 'CMakeLists.txt'):
            self.assertIn('import_soldier_callouts.py', (ROOT / build_file).read_text())

    def test_archive_contains_all_takes_and_detects_modified_audio(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, manifest = root / 'baseq2', root / 'manifest.json'
            report = import_callouts(SOURCE, source / 'sound', manifest)
            archive = root / 'callouts.pk3'
            build_overlay(source, archive)
            verify_overlay(source, archive)
            with zipfile.ZipFile(archive) as packaged:
                self.assertEqual(set(packaged.namelist()), {f['path'] for f in report['files']})
                for item in report['files']:
                    self.assertEqual(hashlib.sha256(packaged.read(item['path'])).hexdigest(),
                                     item['sha256'])
            changed = source / report['files'][0]['path']
            changed.write_bytes(changed.read_bytes()[:-2])
            with self.assertRaises(ValueError):
                import_callouts(SOURCE, source / 'sound', manifest, verify=True)
            with self.assertRaises(ValueError):
                verify_overlay(source, archive)

    def test_original_mp3_and_manifest_changes_are_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inputs = root / 'inputs'
            shutil.copytree(SOURCE, inputs)
            output, manifest = root / 'sound', root / 'manifest.json'
            report = import_callouts(inputs, output, manifest)
            original = inputs / Path(report['files'][0]['original_path']).name
            original.write_bytes(original.read_bytes() + b'changed')
            with self.assertRaisesRegex(ValueError, 'manifest differs'):
                import_callouts(inputs, output, manifest, verify=True)
            shutil.copytree(SOURCE, inputs, dirs_exist_ok=True)
            report['files'][0]['phrase'] = 'wrong phrase'
            manifest.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, 'manifest differs'):
                import_callouts(inputs, output, manifest, verify=True)


if __name__ == '__main__':
    unittest.main()
