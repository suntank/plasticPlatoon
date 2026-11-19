#!/usr/bin/env python3
"""Narrow friendly-transport sync preserves edited mission content and peers."""
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/assets'))
import build_dropship_overlays as dropship
import build_health_overlays as health

OWNED = list(dropship.MANAGED_MEMBERS)
HEALTH = list(dropship.PEER_MEMBERS['health'])
ENDLINE = 'baseq2/operation-endline.pk3'
SANDSTORM = 'baseq2/operation-sandstorm-preview.pk3'


def write_zip(path, entries):
    with zipfile.ZipFile(path, 'w') as archive:
        archive.comment = b'edited mission archive'
        for name, raw in entries.items():
            info = zipfile.ZipInfo(name, (2003, 4, 5, 6, 7, 8))
            info.comment = b'original member metadata'
            info.external_attr = 0o100640 << 16
            archive.writestr(info, raw, compress_type=zipfile.ZIP_DEFLATED)


class DropshipOverlayTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='pp-dropship-overlay-test-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / 'baseq2').mkdir()
        (self.root / 'tools/assets').mkdir(parents=True)
        self.manifests = {}
        owners = {}
        for owner, names in [('dropship', OWNED), ('health', HEALTH)]:
            generator = 'tools/assets/build_' + owner + '.py'
            self.write(generator, b'fixture generator\n')
            records = []
            for name in names:
                if name.endswith('.md2'):
                    skin = OWNED[-1] if owner == 'dropship' else HEALTH[-1]
                    header = [844121161, 8, 256, 256, 40, 1, 0, 0, 0, 0, 1, 68, 132, 132, 132, 132, 132]
                    raw = struct.pack('<17i', *header) + skin.encode().ljust(64, b'\0')
                else:
                    raw = (owner + ' atlas').encode()
                self.write('baseq2/' + name, raw)
                records.append(dict(path=name, bytes=len(raw), sha256=dropship.sha(raw)))
            manifest = dict(generator=generator,
                            dependencies_sha256={'build_' + owner + '.py': dropship.sha(b'fixture generator\n')},
                            files=records)
            self.manifests[owner] = manifest
            self.write_json('tools/assets/' + owner + '-manifest.json', manifest)
            owners[owner] = dict(generator=generator, manifest='tools/assets/' + owner + '-manifest.json',
                                 models=[n for n in names if n.endswith('.md2')],
                                 textures=[n for n in names if n.endswith('.png')])
        self.write_json('tools/assets/platoon.json', dict(procedural_replacements=owners))
        self.entries = {
            ENDLINE: {'maps/pp_endline.map': b'user edited window geometry',
                      'maps/pp_endline.bsp': b'user edited compiled level',
                      'models/monsters/boss2/tris.md2': b'unchanged legacy enemy'},
            SANDSTORM: {'maps/pp_sandstorm.map': b'newer user level source',
                        'maps/pp_sandstorm.bsp': b'newer compiled mission',
                        'models/items/healing/large/skin.png': b'compatibility atlas',
                        **{name: (self.root / 'baseq2' / name).read_bytes() for name in HEALTH}}}
        specs = []
        for path, entries in self.entries.items():
            write_zip(self.root / path, entries)
            members, _ = dropship.archive_members((self.root / path).read_bytes())
            excluded = OWNED + (HEALTH if path == SANDSTORM else [])
            count, digest = dropship.untouched_fingerprint(members, excluded)
            spec = dict(path=path, untouched_members=count, untouched_sha256=digest)
            if path == SANDSTORM:
                spec['peer_owners'] = {'health': HEALTH}
            specs.append(spec)
        self.config = dict(schema=1, asset_manifest='tools/assets/dropship-manifest.json',
                           managed_members=OWNED, required_existing_members=[], archives=specs)
        self.write_json(dropship.CONFIG, self.config)
        health_spec = dict(specs[1], peer_owners={'dropship': OWNED})
        self.write_json(health.CONFIG, dict(schema=1, asset_manifest='tools/assets/health-manifest.json',
                                          managed_members=HEALTH, required_existing_members=[HEALTH[0]],
                                          archives=[health_spec]))
        self.before = {name: (self.root / name).read_bytes() for name in self.entries}

    def write(self, name, raw):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)

    def write_json(self, name, value):
        self.write(name, (json.dumps(value, indent=2) + '\n').encode())

    def update_source(self, owner, name, raw):
        self.write('baseq2/' + name, raw)
        manifest = self.manifests[owner]
        record = next(entry for entry in manifest['files'] if entry['path'] == name)
        record.update(bytes=len(raw), sha256=dropship.sha(raw))
        self.write_json('tools/assets/' + owner + '-manifest.json', manifest)

    def test_append_only_three_files_preserving_every_existing_member(self):
        result = dropship.sync(self.root)
        for path, before in self.before.items():
            old, comment = dropship.archive_members(before)
            after = (self.root / path).read_bytes()
            new, new_comment = dropship.archive_members(after)
            current = {info.filename: (info, raw) for info, raw in new}
            self.assertEqual(comment, new_comment)
            self.assertEqual(set(current), set(self.entries[path]) | set(OWNED))
            for info, raw in old:
                new_info, new_raw = current[info.filename]
                self.assertEqual(raw, new_raw)
                for key in ('date_time', 'comment', 'extra', 'external_attr', 'compress_type'):
                    self.assertEqual(getattr(info, key), getattr(new_info, key))
            dropship.sync(self.root)
            self.assertEqual(after, (self.root / path).read_bytes())
        self.assertEqual(dropship.verify(self.root), result)

    def test_second_archive_edit_refuses_before_first_write(self):
        self.entries[SANDSTORM]['maps/pp_sandstorm.bsp'] = b'even newer user edit'
        write_zip(self.root / SANDSTORM, self.entries[SANDSTORM])
        before = {name: (self.root / name).read_bytes() for name in self.entries}
        with self.assertRaisesRegex(ValueError, 'unmanaged mission contents changed'):
            dropship.sync(self.root)
        self.assertEqual(before, {name: (self.root / name).read_bytes() for name in self.entries})
        self.assertFalse((self.root / dropship.MANIFEST).exists())

    def test_stale_source_or_generator_refuses_without_archive_writes(self):
        self.write('baseq2/' + OWNED[0], b'unverified body edit')
        with self.assertRaisesRegex(ValueError, 'stale canonical dropship asset'):
            dropship.sync(self.root)
        self.assertEqual(self.before, {name: (self.root / name).read_bytes() for name in self.entries})
        self.update_source('dropship', OWNED[0], b'new verified body')
        self.write('tools/assets/build_dropship.py', b'changed generator')
        with self.assertRaisesRegex(ValueError, 'generator changed'):
            dropship.sync(self.root)
        self.assertEqual(self.before, {name: (self.root / name).read_bytes() for name in self.entries})

    def test_changed_managed_file_is_detected_and_repaired(self):
        dropship.sync(self.root)
        with zipfile.ZipFile(self.root / ENDLINE) as archive:
            entries = {name: archive.read(name) for name in archive.namelist()}
        entries[OWNED[0]] = b'old friendly model restored'
        write_zip(self.root / ENDLINE, entries)
        with self.assertRaisesRegex(ValueError, 'differs from canonical source'):
            dropship.verify(self.root)
        dropship.sync(self.root)
        dropship.verify(self.root)

    def test_separate_owners_can_update_in_either_order_without_receipt_deadlock(self):
        health.sync(self.root)
        dropship.sync(self.root)
        health.verify(self.root)
        self.update_source('health', HEALTH[0], b'new verified booster')
        health.sync(self.root)
        dropship.verify(self.root)
        self.update_source('dropship', OWNED[0], b'new verified dropship')
        dropship.sync(self.root)
        health.verify(self.root)
        dropship.verify(self.root)
        with zipfile.ZipFile(self.root / SANDSTORM) as archive:
            for name in OWNED + HEALTH:
                self.assertEqual(archive.read(name), (self.root / 'baseq2' / name).read_bytes())

    def test_peer_exemptions_are_fixed_registered_and_archive_specific(self):
        original = json.loads(json.dumps(self.config))
        cases = [
            lambda c: c['archives'][1]['peer_owners'].update(health=HEALTH + ['maps/pp_sandstorm.bsp']),
            lambda c: c['archives'][0].update(peer_owners={'health': HEALTH})]
        for mutate in cases:
            config = json.loads(json.dumps(original))
            mutate(config)
            self.write_json(dropship.CONFIG, config)
            with self.assertRaisesRegex(ValueError, 'unexpected separately owned mission payload'):
                dropship.sync(self.root)
        self.write_json(dropship.CONFIG, original)
        ownership = json.loads((self.root / 'tools/assets/platoon.json').read_text())
        ownership['procedural_replacements']['health']['models'] = []
        self.write_json('tools/assets/platoon.json', ownership)
        with self.assertRaisesRegex(ValueError, 'differs from procedural ownership'):
            dropship.sync(self.root)
        self.assertEqual(self.before, {name: (self.root / name).read_bytes() for name in self.entries})

    def test_future_packagers_resolve_only_dedicated_friendly_dependencies(self):
        sys.path.insert(0, str(ROOT / 'tools/maps'))
        from dropship_dependencies import dropship_files
        import package_endline
        import package_garden_infiltration
        import package_sandstorm
        self.assertIs(package_endline.dropship_files, dropship_files)
        self.assertIs(package_garden_infiltration.dropship_files, dropship_files)
        self.assertIs(package_sandstorm.dropship_files, dropship_files)
        self.assertEqual(set(dropship_files(self.root / 'baseq2')), set(OWNED))


if __name__ == '__main__':
    unittest.main(verbosity=2)
