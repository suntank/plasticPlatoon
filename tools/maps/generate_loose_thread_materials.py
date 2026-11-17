#!/usr/bin/env python3
"""Paint the sewing-box materials using the game's original WAL palette."""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from generate_sandkeep_materials import text, write_wal
from platoon_palette import load_palette


def materials():
    y, x = np.indices((128, 128))
    images = {}

    def surface(name, base, relief):
        pixels = np.array(base) + relief[:, :, None]
        images[name] = Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8))

    # Low contrast at a distance, with twill ribs visible at soldier height.
    weave = 2 * ((x // 3 + y // 3) % 2) + 4 * np.cos((x + y) * np.pi / 8)
    for name, color in [('teal', (63, 102, 95)), ('linen', (161, 136, 103)),
                        ('denim', (80, 101, 120)), ('rose', (139, 78, 77))]:
        surface(name, color, weave)

    for name, base in [('coral', (187, 77, 64)), ('jade', (53, 131, 121)),
                       ('gold', (201, 153, 67))]:
        # Two thread directions suggest successive layers wound on the bobbin.
        direction = np.where((y // 32) % 2, x, -x)
        winding = 13 * np.cos((y + direction / 16) * np.pi / 4)
        surface(name, base, winding + 3 * np.cos((x - y) * np.pi / 4))

    # Staggered stamped dimples read on the tapered metal thimble.
    height = 8 * np.cos(y * np.pi / 64)
    surface('thimble', (153, 162, 151), height)
    d = ImageDraw.Draw(images['thimble'])
    for j in range(0, 144, 16):
        for i in range(-16, 144, 16):
            cx = i + (j // 16 % 2) * 8
            d.ellipse((cx-4, j-4, cx+4, j+4), fill=(104, 116, 111))
            d.arc((cx-5, j-5, cx+5, j+5), 15, 154, fill=(208, 212, 192), width=2)

    ink = (48, 59, 55)
    paper = (233, 211, 164)
    for name, base in [('button', (62, 128, 129)), ('ivory', paper)]:
        im = Image.new('RGB', (128, 128), base)
        d = ImageDraw.Draw(im)
        for inset, color, width in [(7, ink, 3), (12, (177, 169, 131), 2)]:
            d.ellipse((inset, inset, 127-inset, 127-inset), outline=color, width=width)
        for a in (48, 80):
            for b in (48, 80):
                d.ellipse((a-7, b-7, a+7, b+7), fill=ink)
                d.arc((a-8, b-8, a+8, b+8), 10, 160, fill=(204, 188, 150), width=2)
        images[name] = im

    cap = Image.new('RGB', (128, 128), (191, 154, 104))
    d = ImageDraw.Draw(cap)
    d.ellipse((8, 8, 120, 120), fill=paper, outline=ink, width=2)
    text(d, 64, 32, 'COTTON', 2, ink)
    d.ellipse((55, 55, 73, 73), fill=ink)
    text(d, 64, 85, '60 YD', 1, ink)
    images['bobbin'] = cap

    tape = Image.new('RGB', (256, 32), (225, 179, 83))
    d = ImageDraw.Draw(tape)
    for i in range(32):
        h = 15 if i % 8 == 0 else 10 if i % 4 == 0 else 5
        d.rectangle((i*8, 0, i*8+1, h), fill=ink)
    for i in range(4):
        text(d, i*64+10, 17, str(i+1), 1, ink)
    images['tape'] = tape

    for name, heading, subtitle in [
        ('buttons', 'BUTTON TIN', '01 / MENDING KIT'),
        ('cotton', 'COTTON REELS', '02 / MENDING KIT'),
        ('needles', 'NEEDLE BOOK', '03 / MENDING KIT'),
        ('pins', 'PIN CUSHION', '04 / MENDING KIT'),
        ('latch', 'CASE LATCH', 'RALLY AT THE CLASP'),
    ]:
        im = Image.new('RGB', (256, 128), paper)
        d = ImageDraw.Draw(im)
        d.rectangle((4, 4, 251, 123), outline=ink, width=2)
        for i in range(12, 240, 12):
            d.line((i, 13, i+6, 13), fill=ink, width=2)
            d.line((i, 114, i+6, 114), fill=ink, width=2)
        text(d, 128, 36, heading, 3, ink)
        text(d, 128, 82, subtitle, 2, (118, 65, 48))
        images[name] = im
    return images


if __name__ == '__main__':
    directory = Path(__file__).resolve().parents[2] / 'baseq2/textures/notions'
    directory.mkdir(parents=True, exist_ok=True)
    for name, image in materials().items():
        image.save(directory / (name + '.png'))
        write_wal(directory / (name + '.wal'), 'notions/' + name, image, load_palette())
