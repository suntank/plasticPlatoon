#!/usr/bin/env python3
"""Protect the edited Sandstorm mission while replacing only booster media."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/assets'))
import build_health_overlays as overlays

MODEL = 'models/items/adrenal/tris.md2'
SKIN = 'models/items/adrenal/skin.png'
OLD_SKIN = 'models/items/healing/large/skin.png'
ARCHIVE = 'baseq2/operation-sandstorm-preview.pk3'


def write_zip(path, entries):
    with zipfile.ZipFile(path, 'w') as archive:
        archive.comment = b'edited mission comment'
        for name, data in entries.items():
            info = zipfile.ZipInfo(name, (2002, 3, 4, 5, 6, 8))
            info.comment = b'preserve member metadata'
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED)


class HealthOverlayTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='pp-health-overlay-test-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        manifest_name = 'tools/assets/health-manifest.json'
        manifest = json.loads((ROOT / manifest_name).read_text())
        files = [manifest_name, 'tools/assets/platoon.json']
        files += ['tools/assets/' + name for name in manifest['dependencies_sha256']]
        files += ['baseq2/' + entry['path'] for entry in manifest['files']]
        for name in files:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / name).read_bytes())
        self.entries = {MODEL: b'old fallback medkit', OLD_SKIN: b'old shared skin',
                        'maps/pp_sandstorm.map': b'user edited geometry source',
                        'maps/pp_sandstorm.bsp': b'user edited compiled level',
                        'sound/world/explod1.wav': b'unrelated effect'}
        write_zip(self.root / ARCHIVE, self.entries)
        self.before = (self.root / ARCHIVE).read_bytes()
        members, _ = overlays.archive_members(self.before)
        count, digest = overlays.untouched_fingerprint(members, (MODEL, SKIN))
        config = dict(schema=1, asset_manifest=manifest_name,
                      managed_members=[MODEL, SKIN], required_existing_members=[MODEL],
                      archives=[dict(path=ARCHIVE, untouched_members=count, untouched_sha256=digest)])
        (self.root / overlays.CONFIG).write_text(json.dumps(config, indent=2) + '\n')

    def test_only_booster_changes_and_repeated_sync_is_exact(self):
        result = overlays.sync(self.root)
        after = (self.root / ARCHIVE).read_bytes()
        old, old_comment = overlays.archive_members(self.before)
        new, new_comment = overlays.archive_members(after)
        self.assertEqual(old_comment, new_comment)
        current = {info.filename: (info, data) for info, data in new}
        self.assertEqual(set(current), set(self.entries) | {SKIN})
        for info, data in old:
            new_info, new_data = current[info.filename]
            if info.filename != MODEL:
                self.assertEqual(data, new_data)
            for key in ('date_time', 'external_attr', 'comment', 'extra', 'compress_type'):
                self.assertEqual(getattr(info, key), getattr(new_info, key))
        for name in (MODEL, SKIN):
            self.assertEqual(current[name][1], (self.root / 'baseq2' / name).read_bytes())
        overlays.sync(self.root)
        self.assertEqual((self.root / ARCHIVE).read_bytes(), after)
        self.assertEqual(overlays.verify(self.root), result)

    def test_user_map_edit_is_not_overwritten(self):
        self.entries['maps/pp_sandstorm.bsp'] = b'newer user level edit'
        write_zip(self.root / ARCHIVE, self.entries)
        changed = (self.root / ARCHIVE).read_bytes()
        with self.assertRaisesRegex(ValueError, 'unmanaged mission contents changed'):
            overlays.sync(self.root)
        self.assertEqual((self.root / ARCHIVE).read_bytes(), changed)
        self.assertFalse((self.root / overlays.MANIFEST).exists())

    def test_unverified_health_source_is_not_installed(self):
        (self.root / 'baseq2' / MODEL).write_bytes(b'unverified booster edit')
        with self.assertRaisesRegex(ValueError, 'stale canonical health asset'):
            overlays.sync(self.root)
        self.assertEqual((self.root / ARCHIVE).read_bytes(), self.before)

    def test_old_managed_model_is_detected_and_repaired(self):
        overlays.sync(self.root)
        members, _ = overlays.archive_members((self.root / ARCHIVE).read_bytes())
        entries = {info.filename: data for info, data in members}
        entries[MODEL] = b'old fallback restored'
        write_zip(self.root / ARCHIVE, entries)
        with self.assertRaisesRegex(ValueError, 'differs from canonical source'):
            overlays.verify(self.root)
        overlays.sync(self.root)
        overlays.verify(self.root)

    def test_future_packager_reads_booster_atlas(self):
        sys.path.insert(0, str(ROOT / 'tools/maps'))
        import package_sandstorm
        self.assertEqual(list(package_sandstorm.model_skins(ROOT / 'baseq2' / MODEL)), [SKIN])


if __name__ == '__main__':
    unittest.main(verbosity=2)
