#!/usr/bin/env python3
"""Verify the six supplied sounds, their provenance, and packaging contracts."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import wave
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/assets'))
from build_overlay import build_overlay, verify_overlay
from build_support_sounds import SOUNDS
from import_enemy_sounds import EFFECTS, MANIFEST, SOURCE, import_effects
from import_soldier_sounds import mono_wav


class EnemySoundTests(unittest.TestCase):
    def test_all_six_sources_are_exactly_reproduced_and_spatial_mono(self):
        report = import_effects(verify=True)
        self.assertEqual(len(report['files']), 6)
        for item in report['files']:
            with self.subTest(sound=item['path']):
                source = (ROOT / item['source_path']).read_bytes()
                data = (ROOT / 'baseq2' / item['path']).read_bytes()
                self.assertEqual(hashlib.sha256(source).hexdigest(), item['source_sha256'])
                self.assertEqual(data, mono_wav(source)[0])
                with wave.open(io.BytesIO(data)) as sound:
                    self.assertEqual((sound.getnchannels(), sound.getsampwidth()), (1, 2))
                    self.assertEqual(sound.getframerate(), 48000)
                    self.assertEqual(sound.getnframes(), item['frames'])
                    self.assertGreater(sound.getnframes(), 20000)
                self.assertNotIn(item['path'][6:], SOUNDS,
                                 'Procedural builds must never overwrite supplied audio')

    def test_runtime_roles_and_loop_are_explicit(self):
        self.assertEqual(EFFECTS['all_quiet.wav'][0], 'soldier/solidle1.wav')
        self.assertEqual(EFFECTS['enemy_spotted.wav'][0], 'soldier/solsght1.wav')
        self.assertEqual(EFFECTS['contact.wav'][0], 'soldier/solsrch1.wav')
        self.assertEqual(EFFECTS['shotgun_cock.wav'][0], 'infantry/infatck3.wav')
        self.assertEqual(EFFECTS['rocket_reload.wav'][0], 'soldier/rocket_reload.wav')
        loops = [name for name, (_, _, loop) in EFFECTS.items() if loop]
        self.assertEqual(loops, ['rocket_fly.wav'])

    def test_conversion_and_archive_verification_detect_changed_audio(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, manifest = root / 'baseq2', root / 'manifest.json'
            report = import_effects(SOURCE, source / 'sound', manifest)
            archive = root / 'effects.pk3'
            build_overlay(source, archive)
            verify_overlay(source, archive)
            with zipfile.ZipFile(archive) as packaged:
                self.assertEqual(set(packaged.namelist()), {f['path'] for f in report['files']})
                for item in report['files']:
                    self.assertEqual(hashlib.sha256(packaged.read(item['path'])).hexdigest(), item['sha256'])
            changed = source / report['files'][0]['path']
            changed.write_bytes(changed.read_bytes()[:-2])
            with self.assertRaises(ValueError):
                import_effects(SOURCE, source / 'sound', manifest, verify=True)
            with self.assertRaises(ValueError):
                verify_overlay(source, archive)


if __name__ == '__main__':
    unittest.main()
