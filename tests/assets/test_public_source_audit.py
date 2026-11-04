#!/usr/bin/env python3
"""Public-source guards exercise renamed/nested bytes and unreachable Git data."""
from pathlib import Path
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/assets'))
from audit_public_source import audit, history_audit, path_policy


def archive(entries):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as output:
        for name, content in entries.items():
            output.writestr(name, content)
    return stream.getvalue()


class PublicSourceAuditTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='pp-public-source-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name in ('LICENSE', 'ASSET-LICENSE.md', 'tools/assets/asset-provenance.json'):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{}' if name.endswith('.json') else 'License fixture\n')
        self.forbidden = b'Known removed artwork fixture; no copyrighted pixels.'
        self.banned = {hashlib.sha256(self.forbidden).hexdigest(): 'test stock identity'}

    def git(self, *args, input=None):
        return subprocess.run(['git', '-C', str(self.root), *args], input=input,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout

    def initialize(self):
        self.git('init', '-q')
        self.git('config', 'user.name', 'Audit Test')
        self.git('config', 'user.email', 'audit@example.invalid')

    def commit(self):
        self.git('add', '.')
        self.git('commit', '-qm', 'clean fixture')

    def test_multiple_clean_commits_and_custom_male_audio_are_allowed(self):
        self.initialize()
        recording = self.root / 'baseq2/sound/player/male/death1.wav'
        recording.parent.mkdir(parents=True)
        recording.write_bytes(b'Original custom recording fixture')
        self.commit()
        (self.root / 'README.md').write_text('Second clean commit\n')
        self.commit()
        report = audit(self.root, history=True, banned=self.banned)
        self.assertTrue(report['public_source_checks_pass'], report['violations'])
        self.assertGreaterEqual(report['history']['objects_checked'], 2)
        self.assertIsNone(path_policy('sound/player/male/death1.wav'))

    def test_renaming_and_nested_archives_cannot_hide_known_bytes(self):
        (self.root / 'renamed.bin').write_bytes(self.forbidden)
        nested = archive({'art/renamed.dat': self.forbidden})
        (self.root / 'inputs.pk3').write_bytes(archive({'sources/second.zip': nested}))
        report = audit(self.root, filesystem=True, banned=self.banned)
        matches = [item for item in report['violations'] if item['code'] == 'known_removed_bytes']
        self.assertEqual(len(matches), 2)
        self.assertTrue(any('inputs.pk3:sources/second.zip:art/renamed.dat' == item['location'] for item in matches))
        self.assertEqual(report['source']['archives_checked'], 2)

    def test_unreachable_blob_is_audited_even_without_a_ref_or_path(self):
        self.initialize()
        self.commit()
        oid = self.git('hash-object', '-w', '--stdin', input=self.forbidden).decode().strip()
        report = audit(self.root, history=True, banned=self.banned)
        self.assertFalse(report['public_source_checks_pass'])
        matches = [item for item in report['violations'] if item['code'] == 'known_removed_bytes']
        self.assertEqual([item['location'] for item in matches], ['git:' + oid])

    def test_history_detects_forbidden_commit_and_external_object_store(self):
        self.initialize()
        self.commit()
        head = self.git('rev-parse', 'HEAD').decode().strip()
        violations = []
        history_audit(self.root, {}, violations, forbidden_commits={head})
        self.assertEqual(violations[0]['code'], 'old_commit_object')
        # An empty alternates file is enough to require deliberate review.
        (self.root / '.git/objects/info/alternates').write_text('')
        report = audit(self.root, history=True, banned={})
        self.assertIn('object_alternates', {item['code'] for item in report['violations']})

    def test_member_paths_invalid_archives_and_source_backups_are_rejected(self):
        (self.root / 'bad.pk3').write_bytes(archive({'baseq2/players/male/tris.md2': b'unknown model',
                                                 '../escape.png': b'unknown pixels'}))
        (self.root / 'broken.zip').write_bytes(b'not a ZIP archive')
        (self.root / 'rig.blend1').write_bytes(b'editor backup')
        (self.root / 'backup.tar.gz').write_bytes(b'opaque archive fixture')
        (self.root / 'pak0.pak').write_bytes(b'PAK data fixture')
        report = audit(self.root, filesystem=True, banned={})
        codes = {item['code'] for item in report['violations']}
        self.assertTrue({'legacy_player_path', 'unsafe_path', 'invalid_archive',
                         'generated_or_backup', 'pak_data', 'uninspected_archive'}.issubset(codes))

    def test_filesystem_does_not_follow_or_hide_directory_symlinks(self):
        with tempfile.TemporaryDirectory(prefix='pp-external-fixture-') as other:
            (self.root / 'external').symlink_to(other, target_is_directory=True)
            report = audit(self.root, filesystem=True, banned={})
            self.assertIn('escaping_symlink', {item['code'] for item in report['violations']})

    def test_file_limit_and_missing_notices_cannot_report_clean(self):
        (self.root / 'oversized.dat').write_bytes(bytes(129))
        (self.root / 'LICENSE').unlink()
        report = audit(self.root, filesystem=True, banned={}, max_file_bytes=128)
        codes = {item['code'] for item in report['violations']}
        self.assertIn('oversized_source_file', codes)
        self.assertIn('missing_notice', codes)

    def test_tracked_mode_checks_ignored_files_if_they_were_committed(self):
        self.initialize()
        (self.root / '.gitignore').write_text('/private-backup/\n')
        directory = self.root / 'private-backup'
        directory.mkdir()
        (directory / 'archive.txt').write_text('private backup fixture')
        self.git('add', '-f', 'private-backup/archive.txt')
        self.git('add', '.')
        self.git('commit', '-qm', 'bad fixture')
        report = audit(self.root, banned={})
        self.assertIn('private_backup', {item['code'] for item in report['violations']})


if __name__ == '__main__':
    unittest.main()
