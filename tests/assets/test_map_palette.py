#!/usr/bin/env python3
"""Map exports retain source art and metadata without a stock game palette."""
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/maps'))
from platoon_palette import PROJECT_PALETTE, load_palette, quantize_opaque
from reindex_materials import converted, reindex_wal


def wal():
    return struct.pack('<32sII4I32siii', b'test/original', 8, 8, 100, 164, 180, 184,
                       b'test/next_frame', 4, 32, 120) + bytes([255]) * 85


def source_png():
    image = Image.new('RGB', (8, 8), (255, 0, 255))
    image.putpixel((0, 0), (90, 130, 50))
    output = io.BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()


class MapPaletteTests(unittest.TestCase):
    def test_default_palette_is_defined_by_project_source_and_reserves_transparency(self):
        self.assertEqual(load_palette(), PROJECT_PALETTE)
        indexed = quantize_opaque(Image.open(io.BytesIO(source_png())))
        self.assertEqual(len(indexed.tobytes()), 64)
        self.assertNotIn(255, indexed.tobytes())

    def test_wal_reindex_keeps_metadata_and_all_four_mipmap_lengths(self):
        original = wal()
        output = reindex_wal('textures/test/original.wal', original, source_png())
        self.assertEqual(output[:100], original[:100])
        self.assertEqual(len(output), 185)
        self.assertNotIn(255, output[100:])
        self.assertNotEqual(output[100:], original[100:])
        self.assertEqual(reindex_wal('textures/test/original.wal', output, source_png()), output)

    def test_archive_conversion_changes_only_indexed_material_data(self):
        inputs = {'textures/test/original.wal': wal(),
                  'textures/test/original.png': source_png(),
                  'maps/mission.bsp': b'unchanged map geometry',
                  'models/actor.md2': b'unchanged actor animation',
                  'textures/test/materials.json': json.dumps({'materials': {
                      'test/original': {'wal_sha256': 'old', 'palette_indices': [4, 5],
                                        'animation_next': 'test/next_frame'}}}).encode()}
        outputs, records = converted(inputs)
        for name in ('textures/test/original.png', 'maps/mission.bsp', 'models/actor.md2'):
            self.assertEqual(outputs[name], inputs[name])
        self.assertEqual(records[0]['source_sha256'], hashlib.sha256(source_png()).hexdigest())
        material = json.loads(outputs['textures/test/materials.json'])['materials']['test/original']
        self.assertEqual(material['wal_sha256'], hashlib.sha256(outputs['textures/test/original.wal']).hexdigest())
        self.assertEqual(material['animation_next'], 'test/next_frame')
        self.assertNotIn('palette_indices', material)

    def test_explicit_unrelated_palette_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'unrelated.pcx'
            image = Image.new('P', (16, 16))
            image.putpalette(bytes(768))
            image.save(path)
            with self.assertRaisesRegex(ValueError, 'project palette'):
                load_palette(path)


if __name__ == '__main__':
    unittest.main()
