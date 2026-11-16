#!/usr/bin/env python3
"""Mission projectile sync preserves unrelated files and rejects source drift."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/assets'))
import build_projectile_overlays as overlays

ROCKET = 'models/objects/rocket/tris.md2'
SKIN = 'models/objects/rocket/skin.png'
OLD_SKIN = 'models/items/ammo/rockets/medium/skin.png'


def write_zip(path, entries, comment=b'mission comment'):
    with zipfile.ZipFile(path, 'w') as archive:
        archive.comment = comment
        for name, data in entries.items():
            info = zipfile.ZipInfo(name, (2001, 2, 3, 4, 5, 6))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.comment = b'preserved member comment'
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED)


class ProjectileOverlayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='pp-projectile-overlay-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        manifest_path = 'tools/assets/projectiles-manifest.json'
        manifest = json.loads((ROOT / manifest_path).read_text())
        files = [manifest_path, 'tools/assets/platoon.json']
        files += ['tools/assets/' + name for name in manifest['dependencies_sha256']]
        files += ['baseq2/' + entry['path'] for entry in manifest['files']]
        for name in files:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / name).read_bytes())
        managed = [ROCKET, SKIN]
        self.original = {}
        specs = []
        for index, name in enumerate(('tank', 'helicopter')):
            path = 'baseq2/operation-' + name + '-test.pk3'
            entries = {ROCKET: b'previous rocket model', OLD_SKIN: b'old shared atlas',
                       'maps/range.bsp': bytes([index, 2, 3, 4]),
                       'sound/unrelated.wav': b'unrelated existing sound'}
            write_zip(self.root / path, entries)
            raw = (self.root / path).read_bytes()
            self.original[path] = raw
            members, _ = overlays.archive_members(raw)
            count, fingerprint = overlays.untouched_fingerprint(members, managed)
            specs.append(dict(path=path, untouched_members=count, untouched_sha256=fingerprint))
        config = dict(schema=1, projectile_manifest=manifest_path, managed_members=managed,
                      required_existing_members=[ROCKET], archives=specs)
        (self.root / overlays.CONFIG).write_text(json.dumps(config, indent=2) + '\n')

    def test_sync_changes_only_owned_members_and_is_idempotent(self):
        result = overlays.sync(self.root)
        self.assertEqual(len(result['archives']), 2)
        after = {}
        for path, before in self.original.items():
            raw = (self.root / path).read_bytes()
            after[path] = raw
            old, comment = overlays.archive_members(before)
            new, new_comment = overlays.archive_members(raw)
            self.assertEqual(comment, new_comment)
            current = {info.filename: (info, data) for info, data in new}
            self.assertEqual(set(current), {info.filename for info, _ in old} | {SKIN})
            for info, data in old:
                new_info, new_data = current[info.filename]
                if info.filename != ROCKET:
                    self.assertEqual(data, new_data)
                for key in ('date_time', 'external_attr', 'comment', 'extra', 'compress_type'):
                    self.assertEqual(getattr(info, key), getattr(new_info, key))
            for name in (ROCKET, SKIN):
                self.assertEqual(current[name][1], (self.root / 'baseq2' / name).read_bytes())
        overlays.sync(self.root)
        self.assertEqual(after, {path: (self.root / path).read_bytes() for path in after})
        self.assertEqual(result, overlays.verify(self.root))

    def test_preflight_rejects_unrelated_change_without_writing_either_archive(self):
        path = list(self.original)[1]
        members, _ = overlays.archive_members(self.original[path])
        entries = {info.filename: data for info, data in members}
        entries['maps/range.bsp'] = b'user edited map'
        write_zip(self.root / path, entries)
        before = {name: (self.root / name).read_bytes() for name in self.original}
        with self.assertRaisesRegex(ValueError, 'unmanaged mission contents changed'):
            overlays.sync(self.root)
        self.assertEqual(before, {name: (self.root / name).read_bytes() for name in self.original})
        self.assertFalse((self.root / overlays.MANIFEST).exists())

    def test_stale_canonical_source_cannot_be_installed(self):
        (self.root / 'baseq2' / ROCKET).write_bytes(b'unverified model edit')
        with self.assertRaisesRegex(ValueError, 'stale canonical projectile asset'):
            overlays.sync(self.root)
        self.assertEqual(self.original, {name: (self.root / name).read_bytes() for name in self.original})

    def test_verify_detects_old_managed_model_and_sync_repairs_it(self):
        overlays.sync(self.root)
        path = next(iter(self.original))
        members, comment = overlays.archive_members((self.root / path).read_bytes())
        entries = {info.filename: data for info, data in members}
        entries[ROCKET] = b'old overlay restored'
        write_zip(self.root / path, entries, comment)
        with self.assertRaisesRegex(ValueError, 'differs from canonical source'):
            overlays.verify(self.root)
        overlays.sync(self.root)
        overlays.verify(self.root)

    def test_added_unmanaged_member_is_rejected(self):
        path = next(iter(self.original))
        members, _ = overlays.archive_members(self.original[path])
        entries = {info.filename: data for info, data in members}
        entries['extra-user-file.txt'] = b'keep this unrelated edit'
        write_zip(self.root / path, entries)
        changed = (self.root / path).read_bytes()
        with self.assertRaisesRegex(ValueError, 'unmanaged mission contents changed'):
            overlays.sync(self.root)
        self.assertEqual((self.root / path).read_bytes(), changed)


if __name__ == '__main__':
    unittest.main(verbosity=2)
