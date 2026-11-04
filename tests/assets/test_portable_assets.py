#!/usr/bin/env python3
"""Release completeness checks that do not depend on any user-home assets."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/assets'))
from import_portable_assets import repair_boss_skin_paths, verify
from build_overlay import model_images


class PortableAssetTests(unittest.TestCase):
    def test_imported_assets_and_original_sound_source_are_self_contained(self):
        report = verify()
        with zipfile.ZipFile(ROOT / 'baseq2/plastic-platoon.pk3') as package:
            for entry in report['files']:
                self.assertEqual(hashlib.sha256(package.read(entry['path'])).hexdigest(), entry['sha256'])
        with zipfile.ZipFile(ROOT / report['original_sound_archive']['path']) as originals:
            sounds = json.loads((ROOT / 'tools/assets/soldier-sounds-manifest.json').read_text())
            for entry in sounds['files']:
                self.assertEqual(hashlib.sha256(originals.read(entry['source_path'])).hexdigest(),
                                 entry['source_sha256'])

    def test_player_models_effects_and_all_33_ui_images_are_in_main_pack(self):
        with zipfile.ZipFile(ROOT / 'baseq2/plastic-platoon.pk3') as package:
            names = package.namelist()
            self.assertGreaterEqual(len([n for n in names if n.startswith('pics/')]), 33)
            for name in ('default.cfg', 'pics/colormap.pcx', 'pics/conchars.pcx', 'pics/16to8.dat'):
                self.assertIn(name, names)
            self.assertFalse(any(n.startswith('players/male/') for n in names))
            self.assertEqual(len([n for n in names if n.startswith('pics/ads_')]), 11)
            for name in ('players/soldier/tris.md2', 'players/soldier/green.png',
                         'players/soldier/w_chaingun.md2', 'sprites/explosion.sp2',
                         'sprites/flame.sp2', 'sprites/smoke.sp2',
                         'models/monsters/boss2/propeller.md2', 'maps/pp_sandbox_coop1.bsp'):
                self.assertIn(name, names)
            self.assertFalse(any('ChatGPT' in n or n.endswith(('.bak', '.py', '.zip')) for n in names))
            for name in ('models/monsters/boss2/tris.md2', 'models/monsters/boss2/propeller.md2'):
                self.assertEqual(set(model_images(name, package.read(name))),
                                 {'models/monsters/boss2/skin.png'})

    def test_boss_skin_repair_changes_only_the_skin_table(self):
        header = [844121161, 8] + [0] * 15
        header[5], header[11] = 2, 68
        geometry = b'geometry and animation bytes remain identical'
        raw = struct.pack('<17i', *header) + b'first'.ljust(64, b'\0') + b'/old/workstation'.ljust(64, b'\0') + geometry
        result = repair_boss_skin_paths(raw)
        self.assertEqual(result[:68], raw[:68])
        self.assertEqual(result[196:], geometry)
        for invalid in (b'', struct.pack('<17i', *([0] * 17))):
            with self.assertRaises(ValueError):
                repair_boss_skin_paths(invalid)


if __name__ == '__main__':
    unittest.main(verbosity=2)
