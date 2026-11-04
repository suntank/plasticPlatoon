#!/usr/bin/env python3
"""Check original bootstrap binary formats against the renderer contracts."""
import importlib.util
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('bootstrap', ROOT / 'tools/assets/build_bootstrap.py')
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)


def decode_pcx(data):
    """Independent minimal decoder checks the generated one-plane PCX stream."""
    if data[:4] != bytes((10, 5, 1, 8)) or data[65] != 1 or data[-769] != 12:
        raise AssertionError('invalid 8-bit PCX header/palette')
    width, height = (v + 1 for v in struct.unpack_from('<2H', data, 8))
    stride = struct.unpack_from('<H', data, 66)[0]
    pos, pixels = 128, bytearray()
    for _ in range(height):
        row = bytearray()
        while len(row) < stride:
            code = data[pos]
            pos += 1
            if code & 192 == 192:
                count, color = code & 63, data[pos]
                pos += 1
            else:
                count, color = 1, code
            row.extend([color] * count)
        if len(row) != stride:
            raise AssertionError('PCX run crosses scanline')
        pixels.extend(row[:width])
    if pos != len(data) - 769:
        raise AssertionError('extra bytes before PCX palette')
    palette = [tuple(data[i:i + 3]) for i in range(len(data) - 768, len(data), 3)]
    return width, height, pixels, palette


class BootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets = bootstrap.build_assets()

    def test_colormap_has_complete_shading_and_alpha_tables(self):
        width, height, pixels, palette = decode_pcx(self.assets['pics/colormap.pcx'])
        self.assertEqual((width, height, len(pixels)), (256, 320, 81920))
        for i in range(255):
            self.assertEqual(palette[pixels[i]], palette[i])
            self.assertEqual(palette[pixels[63 * 256 + i]], (0, 0, 0))
        self.assertTrue(all(pixels[level * 256 + 255] == 255 for level in range(64)))
        # Renderer indexes [foreground*256+background] for 66% foreground.
        red, blue = 5 * 36, 5
        result = palette[pixels[64 * 256 + red * 256 + blue]]
        self.assertGreater(result[0], result[2])
        self.assertNotIn(255, pixels[64 * 256:])

    def test_conversion_table_uses_renderer_bit_order_and_opaque_indices(self):
        table = self.assets['pics/16to8.dat']
        self.assertEqual(len(table), 65536)
        palette = bootstrap.PALETTE
        self.assertEqual(palette[table[31]], (255, 0, 0))
        self.assertEqual(palette[table[63 << 5]], (0, 255, 0))
        self.assertEqual(palette[table[31 << 11]], (0, 0, 255))
        self.assertEqual(palette[table[65535]], (255, 255, 255))
        self.assertNotIn(255, table)

    def test_font_has_renderer_grid_and_legible_ascii(self):
        width, height, pixels, _ = decode_pcx(self.assets['pics/conchars.pcx'])
        self.assertEqual((width, height), (128, 128))
        for code in range(32, 127):
            x, y = (code & 15) * 8, (code >> 4) * 8
            cell = [pixels[(y + dy) * width + x + dx] for dy in range(8) for dx in range(8)]
            if code == 32:
                self.assertEqual(set(cell), {255})
            else:
                self.assertTrue(any(v != 255 for v in cell), repr(chr(code)))

    def test_all_images_decode_and_soldier_portraits_have_transparency(self):
        images = {name: decode_pcx(data) for name, data in self.assets.items() if name.endswith('.pcx')}
        self.assertGreater(len(images), 70)
        for name, (width, height, pixels, _) in images.items():
            self.assertEqual(len(pixels), width * height, name)
            if name.startswith('players/'):
                self.assertEqual((width, height), (32, 32), name)
                self.assertIn(255, pixels, name)
                self.assertTrue(any(v != 255 for v in pixels), name)

    def test_sky_and_compatibility_textures_have_complete_payloads(self):
        skies = [data for name, data in self.assets.items() if name.endswith('.tga')]
        self.assertEqual(len(skies), 6)
        for data in skies:
            self.assertEqual(data[:3], bytes((0, 0, 2)))
            width, height, depth, descriptor = struct.unpack_from('<HHBB', data, 12)
            self.assertEqual((width, height, depth, descriptor), (128, 128, 24, 32))
            self.assertEqual(len(data), 18 + width * height * 3)
        for name, data in self.assets.items():
            if not name.endswith('.wal'):
                continue
            width, height, *offsets = struct.unpack_from('<6I', data, 32)
            end = 100
            for mip, offset in enumerate(offsets):
                self.assertEqual(offset, end)
                end += (width >> mip) * (height >> mip)
            self.assertEqual(len(data), end)
            self.assertNotIn(255, data[100:])

    def test_overlay_images_fit_engine_text_layouts(self):
        self.assertEqual(decode_pcx(self.assets['pics/num_0.pcx'])[:2], (16, 24))
        self.assertEqual(decode_pcx(self.assets['pics/field_3.pcx'])[:2], (50, 24))
        self.assertEqual(decode_pcx(self.assets['pics/help.pcx'])[:2], (256, 192))
        self.assertEqual(decode_pcx(self.assets['pics/inventory.pcx'])[:2], (256, 224))


if __name__ == '__main__':
    unittest.main()
