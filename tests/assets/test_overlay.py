#!/usr/bin/env python3
"""Release archive provenance and model/sprite dependency regressions."""
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import wave
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/assets'))
from build_overlay import build_overlay, check_image_dependencies, model_images, verify_overlay
from import_soldier_sounds import mono_wav


def md2(skin):
    """A standard one-triangle, one-frame MD2 with an explicit image path."""
    header = (844121161, 8, 16, 16, 52, 1, 3, 3, 1, 11, 1,
              68, 132, 144, 156, 208, 252)
    frame = struct.pack('<6f16s', 1, 1, 1, 0, 0, 0, b'frame0')
    frame += bytes((0, 0, 0, 0, 15, 0, 0, 0, 0, 15, 0, 0))
    commands = struct.pack('<i', 3)
    commands += b''.join(struct.pack('<ffi', *corner) for corner in ((0, 0, 0), (1, 0, 1), (0, 1, 2)))
    commands += struct.pack('<i', 0)
    return (struct.pack('<17i', *header) + skin.encode().ljust(64, b'\0')
            + struct.pack('<6h', 0, 0, 16, 0, 0, 16)
            + struct.pack('<6h', 0, 1, 2, 0, 1, 2) + frame + commands)


def sp2(image):
    return struct.pack('<7i64s', 844317769, 2, 1, 256, 256, 128, 128, image.encode())


def wav():
    """A short mono PCM sound with identifiable sample bytes."""
    data = io.BytesIO()
    with wave.open(data, 'wb') as output:
        output.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
        output.writeframes(struct.pack('<4h', 0, 1200, -1200, 0))
    return data.getvalue()


class SoldierSoundConversionTests(unittest.TestCase):
    def test_imported_npc_aliases_are_mono_and_do_not_collide_with_player_assets(self):
        manifest = json.loads((ROOT / 'tools/assets/soldier-sounds-manifest.json').read_text())
        self.assertEqual(len(manifest['files']), 28)
        aliases = [item for item in manifest['files']
                   if item['path'].startswith('sound/soldier/player/')]
        self.assertEqual(len(aliases), 27)
        self.assertEqual(len({item['path'] for item in aliases}), len(aliases))
        player_names = {item['source_path'] for item in manifest['files']}
        for item in manifest['files']:
            with self.subTest(sound=item['path']):
                data = (ROOT / 'baseq2' / item['path']).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), item['sha256'])
                with wave.open(io.BytesIO(data), 'rb') as sound:
                    self.assertEqual((sound.getnchannels(), sound.getsampwidth()), (1, 2))
                    self.assertEqual(sound.getframerate(), item['sample_rate'])
                    self.assertEqual(sound.getnframes(), item['frames'])
                if item in aliases:
                    self.assertNotIn(item['path'], player_names,
                                     'Player assets could override an NPC mono sound')

    def test_stereo_downmix_preserves_timing_and_handles_full_scale_samples(self):
        source = io.BytesIO()
        pairs = [(1000, 3000), (32767, 32767), (-32768, -32768), (10000, -10000)]
        with wave.open(source, 'wb') as output:
            output.setparams((2, 2, 48000, 0, 'NONE', 'not compressed'))
            output.writeframes(b''.join(struct.pack('<hh', *pair) for pair in pairs))
        converted, metadata = mono_wav(source.getvalue())
        with wave.open(io.BytesIO(converted), 'rb') as actual:
            self.assertEqual((actual.getnchannels(), actual.getsampwidth(),
                              actual.getframerate(), actual.getnframes()), (1, 2, 48000, 4))
            self.assertEqual(struct.unpack('<4h', actual.readframes(4)),
                             (2000, 32767, -32768, 0))
        self.assertEqual(metadata['source_channels'], 2)


class OverlayVerificationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='pp-overlay-verify-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'baseq2'
        self.output = self.source / 'plastic-platoon.pk3'
        self.assets = {
            'models/prop/tris.md2': md2('models/prop/skin.pcx'),
            'models/prop/skin.png': b'PNG fixture',
            'sprites/effect.sp2': sp2('sprites/effect.png'),
            'sprites/effect.png': b'sprite PNG fixture',
            'performance/pi_zero2.cfg': b'set r_mode -1\n',
            'sound/soldier/player/pistol1.wav': wav(),
        }
        for name, data in self.assets.items():
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    def test_verify_accepts_exact_pack_and_replacement_image_dependencies(self):
        manifest = build_overlay(self.source, self.output)
        actual, references = verify_overlay(self.source, self.output)
        self.assertEqual(manifest, actual)
        self.assertEqual(references, {'image_references': 2, 'external_images': []})

    def test_tuning_is_packed_and_staged_identically_for_game_module(self):
        profile = self.source / 'tuning/default.json'
        profile.parent.mkdir()
        data = b'{"weapon_overrides":{"M60":{"fire_mode":{"rate_rps":35,"spread_standing_hip":3}}}}'
        profile.write_bytes(data)
        release = self.root / 'release/baseq2/plastic-platoon.pk3'
        manifest = build_overlay(self.source, release)
        self.assertIn('tuning/default.json', [entry['path'] for entry in manifest['files']])
        with zipfile.ZipFile(release) as archive:
            self.assertEqual(archive.read('tuning/default.json'), data)
        staged = release.parent / 'tuning/default.json'
        self.assertEqual(staged.read_bytes(), data)
        verify_overlay(self.source, release)
        staged.write_bytes(b'{"old":true}')
        with self.assertRaisesRegex(ValueError, 'loose tuning differs'):
            verify_overlay(self.source, release)
        build_overlay(self.source, release)
        self.assertEqual(staged.read_bytes(), data)
        staged.unlink()
        with self.assertRaisesRegex(ValueError, 'loose tuning differs'):
            verify_overlay(self.source, release)

    def test_invalid_tuning_cannot_replace_release(self):
        build_overlay(self.source, self.output)
        before = self.output.read_bytes()
        profile = self.source / 'tuning/default.json'
        profile.parent.mkdir()
        for data in (b'{broken', b'[]'):
            profile.write_bytes(data)
            with self.assertRaises(ValueError):
                build_overlay(self.source, self.output)
            self.assertEqual(self.output.read_bytes(), before)

    def test_release_tuning_preserves_the_audited_laptop_profile(self):
        data = (ROOT / 'baseq2/tuning/default.json').read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(),
                         '219e0f1ec97fa6b944336f263726564a3eb0a176351f5fd19f805913d24a22ea')
        fire_mode = json.loads(data)['weapon_overrides']['M60']['fire_mode']
        self.assertEqual(fire_mode['rate_rps'], 35)
        self.assertEqual(fire_mode['spread_standing_hip'], 3)

    def test_verify_rejects_new_missing_or_changed_loose_assets(self):
        build_overlay(self.source, self.output)
        skin = self.source / 'models/prop/skin.png'
        skin.write_bytes(b'changed skin')
        with self.assertRaisesRegex(ValueError, 'differs from loose asset'):
            verify_overlay(self.source, self.output)
        skin.unlink()
        with self.assertRaisesRegex(ValueError, 'inventory'):
            verify_overlay(self.source, self.output)

    def test_sound_is_packaged_and_changed_audio_fails_verification(self):
        manifest = build_overlay(self.source, self.output)
        name = 'sound/soldier/player/pistol1.wav'
        with zipfile.ZipFile(self.output) as archive:
            self.assertEqual(archive.read(name), self.assets[name])
        entry = next(item for item in manifest['files'] if item['path'] == name)
        self.assertEqual(entry['sha256'], hashlib.sha256(self.assets[name]).hexdigest())
        (self.source / name).write_bytes(wav() + b'changed')
        with self.assertRaisesRegex(ValueError, 'differs from loose asset'):
            verify_overlay(self.source, self.output)

    def test_verify_rejects_tampered_archive_or_manifest(self):
        build_overlay(self.source, self.output)
        self.output.write_bytes(self.output.read_bytes() + b'changed')
        with self.assertRaisesRegex(ValueError, 'bytes/hash'):
            verify_overlay(self.source, self.output)
        build_overlay(self.source, self.output)
        manifest_path = self.output.with_suffix('.manifest.json')
        manifest = json.loads(manifest_path.read_text())
        manifest['files'][0]['sha256'] = 'incorrect'
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'manifest entries'):
            verify_overlay(self.source, self.output)

    def test_verify_rejects_duplicate_entries_even_with_matching_archive_hash(self):
        manifest = build_overlay(self.source, self.output)
        with zipfile.ZipFile(self.output, 'a') as archive:
            archive.writestr('sprites/effect.png', b'duplicate')
        data = self.output.read_bytes()
        manifest['archive_bytes'] = len(data)
        manifest['archive_sha256'] = hashlib.sha256(data).hexdigest()
        self.output.with_suffix('.manifest.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'inventory'):
            verify_overlay(self.source, self.output)

    def test_missing_skin_or_sprite_image_fails(self):
        for name in ('models/prop/skin.png', 'sprites/effect.png'):
            with self.subTest(name=name):
                assets = dict(self.assets)
                del assets[name]
                with self.assertRaisesRegex(ValueError, 'missing image dependency'):
                    check_image_dependencies(assets)

    def test_no_model_can_hide_a_missing_skin_as_an_external_dependency(self):
        for model, image in (('players/male/weapon.md2', 'players/male/weapon.pcx'),
                             ('players/soldier/weapon.md2', 'players/male/weapon.pcx'),
                             ('players/male/weapon.md2', 'players/male/other.pcx')):
            with self.subTest(model=model, image=image):
                with self.assertRaisesRegex(ValueError, 'missing image dependency'):
                    check_image_dependencies({model: md2(image)})

    def test_bootstrap_is_packaged_and_legacy_player_is_excluded(self):
        defaults = self.source / 'default.cfg'
        defaults.write_bytes(b'bind w +forward\n')
        table = self.source / 'pics/16to8.dat'
        table.parent.mkdir()
        table.write_bytes(bytes(65536))
        legacy = self.source / 'players/male/tris.md2'
        legacy.parent.mkdir(parents=True)
        legacy.write_bytes(b'legacy stock player fixture')
        build_overlay(self.source, self.output)
        with zipfile.ZipFile(self.output) as archive:
            self.assertEqual(archive.read('default.cfg'), defaults.read_bytes())
            self.assertEqual(archive.read('pics/16to8.dat'), table.read_bytes())
            self.assertFalse(any(n.startswith('players/male/') for n in archive.namelist()))
        verify_overlay(self.source, self.output)

    def test_dependency_parser_rejects_unsafe_paths_and_truncated_tables(self):
        for reference in ('/home/private.png', '../outside.png', '.', 'models//skin.png', 'models\\skin.png'):
            with self.subTest(reference=reference):
                with self.assertRaisesRegex(ValueError, 'unsafe image dependency'):
                    model_images('models/prop/tris.md2', md2(reference))
        with self.assertRaisesRegex(ValueError, 'MD2 skin table'):
            model_images('models/prop/tris.md2', md2('skin.png')[:100])
        with self.assertRaisesRegex(ValueError, 'SP2 frames'):
            model_images('sprites/effect.sp2', sp2('sprites/effect.png')[:-1])


if __name__ == '__main__':
    unittest.main(verbosity=2)
