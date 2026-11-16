#!/usr/bin/env python3
"""Audit exact authored pickup identity and safe historical LOD handling."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/assets'))
import build_pickup_lods as lods


class PickupLODTests(unittest.TestCase):
    def test_shipped_manifest_and_standard_library_verifier(self):
        subprocess.run([sys.executable, '-S', str(ROOT / 'tools/assets/build_pickup_lods.py'), '--verify'],
                       cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def test_authored_ammo_keeps_exact_mesh_at_both_distances(self):
        config = json.loads(lods.CONFIG.read_text())
        ammo = [spec for spec in config['assets'] if spec['recipe'] == 'authored_ammo']
        self.assertEqual({spec['classname'] for spec in ammo}, {'ammo_shells', 'ammo_bullets', 'ammo_grenades'})
        for spec in ammo:
            with self.subTest(classname=spec['classname']):
                canonical = (ROOT / 'baseq2' / spec['canonical']).read_bytes()
                distant = (ROOT / 'baseq2' / spec['lod']).read_bytes()
                self.assertEqual(canonical, distant)
                before, after = lods.validate_pair(spec, canonical, distant)
                self.assertEqual(before, after)
                self.assertLessEqual(after['triangles'], spec['target_triangles'])

    def test_small_authored_mesh_is_not_padded_to_legacy_floor(self):
        decoded = dict(skins=['same'], skin_dimensions=[32, 32], scale=[1, 1, 1],
                       translation=[0, 0, 0], frame_name_hex='00', frames=1,
                       triangles=48, bounds=[[0, 0, 0], [1, 1, 1]])
        with patch.object(lods, 'decode', return_value=decoded):
            for recipe in lods.AUTHORED_RECIPES:
                spec = dict(recipe=recipe, target_triangles=80)
                self.assertEqual(lods.validate_pair(spec, b'same', b'same'), (decoded, decoded))
                with self.assertRaisesRegex(ValueError, 'exact close mesh'):
                    lods.validate_pair(spec, b'authored', b'old shape')
                with self.assertRaisesRegex(ValueError, 'triangle budget'):
                    lods.validate_pair(dict(spec, target_triangles=40), b'same', b'same')
            with self.assertRaisesRegex(ValueError, '100-200'):
                lods.validate_pair(dict(spec, recipe='qem'), b'same', b'same')

    def test_authored_refresh_refuses_changed_legacy_geometry(self):
        config = json.loads(lods.CONFIG.read_text())
        previous = json.loads(lods.MANIFEST.read_text())
        # No active pickup needs reduction now. Retain an explicit historical
        # recipe fixture so refresh cannot silently bless a changed old LOD.
        legacy = copy.deepcopy(config['assets'][0])
        legacy.update(recipe='qem', source_sha256='pinned-historical-source')
        config['assets'][0] = legacy
        canonical = (ROOT / 'baseq2' / legacy['canonical']).read_bytes()
        distant = (ROOT / 'baseq2' / legacy['lod']).read_bytes()
        altered = copy.deepcopy(previous)
        entry = lods.record(legacy, canonical, distant)
        altered['assets'][0] = entry
        entry['after']['sha256'] = 'not-the-preserved-output'
        inventories = lods.authored_inventories(config)
        with patch.object(Path, 'read_text', return_value=json.dumps(altered)), \
             patch.object(lods, 'authored_inventories', return_value=inventories), \
             patch.object(lods, 'inputs', return_value=iter([(legacy, canonical, canonical, b'')])), \
             patch.object(lods, 'manifest_header', return_value={'assets': []}), \
             patch.object(Path, 'write_text') as write:
            with self.assertRaisesRegex(ValueError, 'cannot change legacy LOD'):
                lods.refresh_authored(config)
            write.assert_not_called()

    def test_authored_refresh_adopts_only_owner_verified_hashes(self):
        config = json.loads(lods.CONFIG.read_text())
        previous = json.loads(lods.MANIFEST.read_text())
        for spec in config['assets']:
            if spec['recipe'] in lods.AUTHORED_RECIPES:
                spec['canonical_sha256'] = spec['skin_sha256'] = 'stale-owner-output'
        with tempfile.TemporaryDirectory() as directory:
            config_path, manifest_path = Path(directory) / 'config.json', Path(directory) / 'manifest.json'
            config_path.write_text(json.dumps(config))
            manifest_path.write_text(json.dumps(previous))
            with patch.object(lods, 'CONFIG', config_path), patch.object(lods, 'MANIFEST', manifest_path):
                lods.refresh_authored(config)
            adopted = json.loads(config_path.read_text())
            refreshed = json.loads(manifest_path.read_text())
        for before, after in zip(config['assets'], adopted['assets']):
            if before['recipe'] in lods.AUTHORED_RECIPES:
                self.assertEqual(after['canonical_sha256'], lods.sha((ROOT / 'baseq2' / after['canonical']).read_bytes()))
                self.assertEqual(after['skin_sha256'], lods.sha((ROOT / 'baseq2' / after['skin']).read_bytes()))
                self.assertEqual({k: v for k, v in before.items() if k not in ('canonical_sha256', 'skin_sha256')},
                                 {k: v for k, v in after.items() if k not in ('canonical_sha256', 'skin_sha256')})
            else:
                self.assertEqual(before, after)
                legacy = next(entry for entry in previous['assets'] if entry['lod'] == before['lod'])
                self.assertEqual(legacy, next(entry for entry in refreshed['assets'] if entry['lod'] == before['lod']))

    def test_authored_health_keeps_exact_stimpack_at_both_distances(self):
        config = json.loads(lods.CONFIG.read_text())
        health = [spec for spec in config['assets'] if spec['recipe'] == 'authored_health']
        self.assertEqual([spec['classname'] for spec in health], ['item_health_small'])
        spec = health[0]
        canonical = (ROOT / 'baseq2' / spec['canonical']).read_bytes()
        distant = (ROOT / 'baseq2' / spec['lod']).read_bytes()
        self.assertEqual(canonical, distant)
        before, after = lods.validate_pair(spec, canonical, distant)
        self.assertEqual(before, after)
        self.assertLessEqual(after['triangles'], spec['target_triangles'])

    def test_refresh_cli_verifies_the_newly_adopted_hash_pins(self):
        stale, adopted = {'canonical_sha256': 'previous'}, {'canonical_sha256': 'owner-verified'}
        with patch.object(sys, 'argv', ['build_pickup_lods.py', '--refresh-authored']), \
             patch.object(Path, 'read_text', side_effect=[json.dumps(stale), json.dumps(adopted)]), \
             patch.object(lods, 'refresh_authored') as refresh, patch.object(lods, 'verify') as verify:
            lods.main()
            refresh.assert_called_once_with(stale)
            verify.assert_called_once_with(adopted)

    def test_authored_armor_keeps_exact_shard_at_both_distances(self):
        config = json.loads(lods.CONFIG.read_text())
        armor = [spec for spec in config['assets'] if spec['recipe'] == 'authored_armor']
        self.assertEqual([spec['classname'] for spec in armor], ['item_armor_shard'])
        spec = armor[0]
        canonical = (ROOT / 'baseq2' / spec['canonical']).read_bytes()
        distant = (ROOT / 'baseq2' / spec['lod']).read_bytes()
        self.assertEqual(canonical, distant)
        before, after = lods.validate_pair(spec, canonical, distant)
        self.assertEqual(before, after)
        self.assertLessEqual(after['triangles'], spec['target_triangles'])
        self.assertTrue(all(spec['recipe'] in lods.AUTHORED_RECIPES for spec in config['assets']))
        self.assertNotIn('pymeshlab', json.loads(lods.MANIFEST.read_text())['tools'])

    def test_authored_build_does_not_require_reduction_tools(self):
        config = json.loads(lods.CONFIG.read_text())
        spec = next(spec for spec in config['assets'] if spec['recipe'] == 'authored_ammo')
        config['assets'] = [spec]
        raw = (ROOT / 'baseq2' / spec['canonical']).read_bytes()
        authored = {spec['canonical']: raw, spec['lod']: raw}

        def tool_version(name):
            self.assertIn(name, ('numpy', 'Pillow'))
            return 'test-version'

        with patch.object(lods, 'inputs', return_value=iter([(spec, raw, raw, b'')])), \
             patch('importlib.metadata.version', side_effect=tool_version), \
             patch('importlib.import_module', return_value=SimpleNamespace(build_assets=lambda: (authored, {}))), \
             patch.object(Path, 'write_bytes') as write_model, patch.object(Path, 'write_text') as write_manifest:
            lods.build(config, False)
            write_model.assert_called_once_with(raw)
            manifest = json.loads(write_manifest.call_args.args[0])
            self.assertEqual(set(manifest['tools']), {'numpy', 'Pillow'})

    def test_source_archive_pins_still_reject_drift_with_all_authored_recipes(self):
        config = json.loads(lods.CONFIG.read_text())
        pinned = ROOT / next(iter(config['source_archives'].values()))['path']
        read_bytes = Path.read_bytes

        def changed_archive(path):
            return b'changed pinned source archive' if path == pinned else read_bytes(path)

        with patch.object(Path, 'read_bytes', changed_archive):
            with self.assertRaisesRegex(ValueError, 'pinned source archive changed'):
                list(lods.inputs(config))


if __name__ == '__main__':
    unittest.main()
