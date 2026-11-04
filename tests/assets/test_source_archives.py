#!/usr/bin/env python3
"""Original project inputs remain recoverable after removing private Git history."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/assets'))
import asset_sources


class SourceArchiveTests(unittest.TestCase):
    def test_original_snapshot_matches_inventory_and_excludes_legacy_art(self):
        metadata = json.loads((ROOT / 'tools/assets/platoon-originals.json').read_text())
        files = asset_sources.source_files(metadata)
        inventory = {entry['path']: entry for entry in metadata['files']}
        self.assertEqual(set(files), set(inventory))
        self.assertEqual(len(files), 146)
        for name, raw in files.items():
            with self.subTest(path=name):
                self.assertFalse(name.startswith('baseq2/players/male/'))
                self.assertFalse(name.endswith('_i.pcx'))
                self.assertEqual(len(raw), inventory[name]['bytes'])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), inventory[name]['sha256'])
        for config in ('platoon.json', 'platoon-manifest.json', 'pickups.json', 'pickup-manifest.json'):
            record = json.loads((ROOT / 'tools/assets' / config).read_text())
            self.assertNotIn('source_commit', record)
            self.assertTrue(asset_sources.source_files(record))

    def test_missing_archive_cannot_fall_back_to_git(self):
        with self.assertRaisesRegex(ValueError, 'pinned source_archive is required'):
            asset_sources.source_bytes({'source_commit': 'old-private-history'}, 'baseq2/model.md2')

    def test_archive_digest_rejects_changed_originals(self):
        metadata = json.loads((ROOT / 'tools/assets/platoon-originals.json').read_text())
        metadata['source_archive']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'source archive hash changed'):
            asset_sources.source_files(metadata)

    def test_archive_rejects_unsafe_or_duplicate_members(self):
        with tempfile.TemporaryDirectory(prefix='platoon-source-fixture-') as temporary:
            root = Path(temporary)
            for number, names in enumerate((['baseq2/../outside.md2'], ['/baseq2/model.md2'],
                                            ['baseq2/model.md2', 'baseq2/model.md2'])):
                archive = root / f'{number}.pk3'
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore', UserWarning)
                    with zipfile.ZipFile(archive, 'w') as output:
                        for name in names:
                            output.writestr(name, b'fixture')
                metadata = {'source_archive': {'path': archive.name,
                            'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}}
                with patch.object(asset_sources, 'ROOT', root):
                    with self.assertRaisesRegex(ValueError, 'unsafe path|duplicate path'):
                        asset_sources.source_files(metadata)


if __name__ == '__main__':
    unittest.main(verbosity=2)
