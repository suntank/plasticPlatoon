#!/usr/bin/env python3
"""Create compiler WALs from the existing sandbox artwork, using the project palette."""
from pathlib import Path
import struct
from PIL import Image
from platoon_palette import load_palette, quantize_opaque

textures = Path(__file__).resolve().parents[2] / 'baseq2/textures/sandbox'
palette = load_palette()
for name in ('sand1', 'wood1', 'water1', *(f'abc_block_{c}' for c in 'abcdef')):
    stem = textures / name
    src = next((stem.with_suffix(s) for s in ('.tga', '.png') if stem.with_suffix(s).is_file()), None)
    if src is None:
        raise FileNotFoundError(f'No source image for {stem}')
    with Image.open(src) as image:
        image = image.convert('RGB')
        width, height = image.size
        if min(width, height) < 8 or width & (width - 1) or height & (height - 1):
            raise ValueError(f'{src}: WAL dimensions must be powers of two and at least 8')
        levels = [quantize_opaque(image.resize((width >> i, height >> i), Image.Resampling.BOX), palette).tobytes() for i in range(4)]
    offsets, pos = [], 100
    for level in levels:
        offsets.append(pos)
        pos += len(level)
    header = struct.pack('<32sII4I32siii', ('sandbox/' + name).encode(), width, height, *offsets, b'', 0, 0, 0)
    stem.with_suffix('.wal').write_bytes(header + b''.join(levels))
print('Built nine sandbox WAL files.')
