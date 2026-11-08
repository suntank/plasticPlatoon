#!/usr/bin/env python3
"""Generate original Plastic Platoon application branding without image inputs.

The geometric toy-soldier helmet and PP lettering are source artwork. Outputs
and this generator use GPL-2.0-or-later. No Quake trademark artwork is read.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import struct
import zlib

from build_bootstrap import GLYPHS

ROOT = Path(__file__).resolve().parents[2]
SIZE = 64


def icon_pixels():
    pixels = bytearray()
    for y in range(SIZE):
        for x in range(SIZE):
            corner_x = max(0, 9 - x, x - 54)
            corner_y = max(0, 9 - y, y - 54)
            inside = corner_x * corner_x + corner_y * corner_y <= 81
            color = (21, 37, 27, 255) if inside else (0, 0, 0, 0)
            # Molded shoulders, head, and helmet dome.
            if (11 <= x <= 52 and 49 <= y <= 57
                    and abs(x - 31.5) <= 12 + (y - 49) * 1.1):
                color = (51, 106, 49, 255)
            if 22 <= x <= 41 and 32 <= y <= 49:
                color = (72, 143, 63, 255)
            if ((x - 31.5) / 21) ** 2 + ((y - 29) / 18) ** 2 <= 1 and y <= 30:
                color = (75, 151, 64, 255) if x < 32 else (52, 117, 50, 255)
            if 10 <= x <= 53 and 28 <= y <= 33:
                color = (95, 170, 74, 255) if y < 31 else (35, 79, 37, 255)
            if x == 31 and 12 <= y <= 27:
                color = (117, 186, 85, 255)
            # Original PP badge, using the project's own block letterforms.
            for left in (25, 33):
                px, py = x - left, y - 37
                if 0 <= px < 5 and 0 <= py < 7 and GLYPHS['P'].split('/')[py][px] == '1':
                    color = (227, 230, 181, 255)
            pixels.extend(color)
    return bytes(pixels)


def png(pixels):
    def chunk(kind, payload):
        return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind + payload))
    rows = b''.join(b'\0' + pixels[y * SIZE * 4:(y + 1) * SIZE * 4] for y in range(SIZE))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>2I5B', SIZE, SIZE, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows, 9)) + chunk(b'IEND', b''))


def ico(pixels):
    # Standard RGBA DIB icon with bottom-up BGRA pixels and a one-bit AND mask.
    bitmap = bytearray(struct.pack('<IiiHHIIiiII', 40, SIZE, SIZE * 2, 1, 32, 0,
                                   SIZE * SIZE * 4, 0, 0, 0, 0))
    for y in range(SIZE - 1, -1, -1):
        for x in range(SIZE):
            r, g, b, a = pixels[(y * SIZE + x) * 4:(y * SIZE + x + 1) * 4]
            bitmap.extend((b, g, r, a))
    for y in range(SIZE - 1, -1, -1):
        for left in range(0, SIZE, 8):
            byte = 0
            for dx in range(8):
                if pixels[(y * SIZE + left + dx) * 4 + 3] == 0:
                    byte |= 1 << (7 - dx)
            bitmap.append(byte)
    return struct.pack('<3H4B2H2I', 0, 1, 1, SIZE, SIZE, 0, 0, 1, 32, len(bitmap), 22) + bitmap


def header(pixels):
    rows = [', '.join(f'0x{value:02x}' for value in pixels[start:start + 16])
            for start in range(0, len(pixels), 16)]
    return ('''/* Original procedural Plastic Platoon icon; build_branding.py.
 * SPDX-License-Identifier: GPL-2.0-or-later */
static const struct {
    unsigned int width;
    unsigned int height;
    unsigned int bytes_per_pixel;
    unsigned char pixel_data[64 * 64 * 4];
} platoon_icon64 = {64, 64, 4, {
''' + ',\n'.join('    ' + row for row in rows) + '\n}};\n').encode()


def svg(pixels):
    # Run-length rectangles preserve the existing original pixel artwork at any
    # scale; no fonts, external images, or legacy logo paths are embedded.
    rows = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"',
            ' width="256" height="256" shape-rendering="crispEdges">',
            '<title>Plastic Platoon toy soldier</title>',
            '<!-- Original procedural artwork. SPDX-License-Identifier: GPL-2.0-or-later -->']
    for y in range(SIZE):
        x = 0
        while x < SIZE:
            color = pixels[(y * SIZE + x) * 4:(y * SIZE + x + 1) * 4]
            end = x + 1
            while end < SIZE and pixels[(y * SIZE + end) * 4:(y * SIZE + end + 1) * 4] == color:
                end += 1
            if color[3]:
                rows.append(f'<rect x="{x}" y="{y}" width="{end-x}" height="1" '
                            f'fill="#{color[:3].hex()}"/>')
            x = end
    return ('\n'.join(rows) + '\n</svg>\n').encode()


def build_assets():
    pixels = icon_pixels()
    return {'src/client/vid/icon/platoon_icon64.h': header(pixels),
            'packaging/branding/plastic-platoon.png': png(pixels),
            'packaging/branding/plastic-platoon.ico': ico(pixels),
            'packaging/branding/plastic-platoon.svg': svg(pixels)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    failures = []
    for name, data in build_assets().items():
        path = ROOT / name
        if args.verify:
            if not path.is_file() or path.read_bytes() != data:
                failures.append(name)
        elif not path.is_file() or path.read_bytes() != data:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    if failures:
        parser.error('Missing or changed original branding: ' + ', '.join(failures))
    print(('Verified' if args.verify else 'Built') + ' original SDL, PNG, SVG and Windows application icons')


if __name__ == '__main__':
    main()
