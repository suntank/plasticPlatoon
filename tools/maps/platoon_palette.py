"""Original Plastic Platoon palette and opaque WAL conversion helpers.

The palette is defined in build_bootstrap.py. No installed game data or legacy
palette image is needed by a map/material authoring tool.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys

from PIL import Image

ASSETS = Path(__file__).resolve().parents[1] / 'assets'
if str(ASSETS) not in sys.path:
    sys.path.insert(0, str(ASSETS))
from build_bootstrap import PALETTE

PROJECT_PALETTE = bytes(channel for color in PALETTE for channel in color)
PROJECT_PALETTE_SHA256 = hashlib.sha256(PROJECT_PALETTE).hexdigest()


def load_palette(path=None):
    """Return the project palette, or validate an explicitly supplied copy."""
    if path is None:
        return PROJECT_PALETTE
    with Image.open(path) as image:
        values = image.getpalette()
    if values is None or bytes(values) != PROJECT_PALETTE:
        raise ValueError('Expected the original project palette from baseq2/pics/colormap.pcx')
    return PROJECT_PALETTE


def quantize_opaque(image, palette=PROJECT_PALETTE):
    """Map RGB artwork to opaque palette entries, never reserved index 255."""
    if len(palette) != 768:
        raise ValueError('A palette must contain 256 RGB colors')
    rgb = image.convert('RGB')
    palette_image = Image.new('P', (16, 16))
    palette_image.putpalette(palette)
    indexed = rgb.quantize(palette=palette_image, dither=Image.Dither.NONE)
    indices = bytearray(indexed.tobytes())
    if 255 in indices:
        pixels = list(rgb.getdata())
        colors = [tuple(palette[i:i + 3]) for i in range(0, 255 * 3, 3)]
        cache = {}
        for position, index in enumerate(indices):
            if index != 255:
                continue
            pixel = pixels[position]
            if pixel not in cache:
                cache[pixel] = min(range(255), key=lambda i:
                    sum((colors[i][channel] - pixel[channel]) ** 2 for channel in range(3)))
            indices[position] = cache[pixel]
    result = Image.frombytes('P', rgb.size, bytes(indices))
    result.putpalette(palette)
    return result
