#!/usr/bin/env python3
"""Malformed archive and hidden dependency checks for the standalone auditor."""
from pathlib import Path
import json
import struct
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/assets'))
from audit_standalone import audit, bsp_dependencies, dependency_report, inventory, pak_members, provenance_report


def bsp(textures, entity='{"classname" "worldspawn" "sky" "own_"}'):
    header_size = 8 + 19 * 8
    entities = entity.encode() + b'\0'
    texinfo = b''.join(struct.pack('<8fii32si', *(0.0,) * 8, flags, 0,
                                  name.encode(), -1) for name, flags in textures)
    lumps = [(0, 0)] * 19
    lumps[0] = (header_size, len(entities))
    lumps[5] = (header_size + len(entities), len(texinfo))
    return (struct.pack('<4si', b'IBSP', 38)
            + b''.join(struct.pack('<ii', *lump) for lump in lumps) + entities + texinfo)


def sp2(image):
    return struct.pack('<7i64s', 844317769, 2, 1, 16, 16, 0, 0, image.encode())


class StandaloneAuditTests(unittest.TestCase):
    def test_pak_rejects_out_of_bounds_and_unsafe_members(self):
        header = struct.pack('<4sii', b'PACK', 12, 64)
        with self.assertRaisesRegex(ValueError, 'bounds'):
            pak_members(header + struct.pack('<56sii', b'pics/test.pcx', 76, 1))
        with self.assertRaisesRegex(ValueError, 'unsafe'):
            pak_members(header + struct.pack('<56sii', b'../secret', 12, 0))
        self.assertEqual(pak_members(header + struct.pack('<56sii', b'pics/test.pcx', 12, 0)),
                         [('pics/test.pcx', b'')])

    def test_bsp_checks_all_texinfo_materials_and_all_sky_faces(self):
        references = bsp_dependencies('maps/test.bsp', bsp([('own/wall', 0), ('skip', 128), ('sky', 4)]))
        self.assertEqual(sum(kind == 'map_sky' for kind, _, _ in references), 6)
        textures = [ref for kind, ref, _ in references if kind == 'map_texture']
        self.assertEqual(textures, ['textures/own/wall.wal', 'textures/skip.wal', 'textures/sky.wal'])
        corrupt = bytearray(bsp([]))
        struct.pack_into('<ii', corrupt, 8, len(corrupt) + 1, 10)
        with self.assertRaisesRegex(ValueError, 'lump'):
            bsp_dependencies('bad.bsp', corrupt)

    def test_replacement_image_resolves_and_no_stock_exception_is_ignored(self):
        assets = {'sprites/test.sp2': [{'provider': 'test', 'data': sp2('pics/test.pcx')}],
                  'pics/test.png': [{'provider': 'test', 'data': b'pixels'}]}
        self.assertEqual(dependency_report(assets)['missing'], [])
        del assets['pics/test.png']
        missing = dependency_report(assets)['missing']
        self.assertEqual(missing[0]['reference'], 'pics/test.pcx')

    def test_all_providers_audited_and_conflicts_cannot_look_clean(self):
        with tempfile.TemporaryDirectory(prefix='pp-standalone-audit-') as directory:
            root = Path(directory)
            data = root / 'baseq2'
            data.mkdir()
            with zipfile.ZipFile(data / 'first.pk3', 'w') as archive:
                archive.writestr('sprites/test.sp2', sp2('pics/first.png'))
                archive.writestr('pics/first.png', b'pixels')
            with zipfile.ZipFile(data / 'second.pk3', 'w') as archive:
                archive.writestr('sprites/test.sp2', sp2('pics/missing.png'))
            assets, archives, errors = inventory(data)
            self.assertEqual(len(assets['sprites/test.sp2']), 2)
            self.assertEqual(errors, [])
            result = audit(data, root, ())
            self.assertFalse(result['runtime_dependency_checks_pass'])
            self.assertEqual(result['dependencies']['missing'][0]['reference'], 'pics/missing.png')
            self.assertEqual(result['inventory']['conflicting_providers'][0]['asset'], 'sprites/test.sp2')
            self.assertEqual(result['public_release_readiness'], 'not_certified')
            self.assertEqual(len(archives), 2)

    def test_bad_archive_is_reported_without_hiding_loose_assets(self):
        with tempfile.TemporaryDirectory(prefix='pp-standalone-audit-') as directory:
            root = Path(directory)
            (root / 'broken.pk3').write_bytes(b'not a zip')
            (root / 'default.cfg').write_text('bind w +forward\n')
            assets, _, errors = inventory(root)
            self.assertIn('default.cfg', assets)
            self.assertEqual(errors[0]['provider'], 'broken.pk3')

    def test_owner_declaration_is_recorded_without_certifying_history(self):
        with tempfile.TemporaryDirectory(prefix='pp-owner-declaration-') as directory:
            root = Path(directory)
            self.assertEqual(provenance_report(root)['status'], 'unreviewed')
            path = root / 'tools/assets/asset-provenance.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'status': 'owner_declared_original',
                                        'owner_statement': 'I made these assets.',
                                        'scope': ['Original game art'],
                                        'excluded': ['Historical stock content'],
                                        'license': 'GPL-2.0-or-later'}))
            recorded = provenance_report(root)
            self.assertEqual(recorded['status'], 'owner_declared_original')
            self.assertEqual(recorded['excluded'], ['Historical stock content'])
            self.assertEqual(recorded['source_history_review'], 'required')
            result = audit(root, root, ())
            self.assertEqual(result['public_release_readiness'], 'not_certified')
            path.write_text('{invalid')
            self.assertEqual(provenance_report(root)['status'], 'unreviewed')


if __name__ == '__main__':
    unittest.main()
