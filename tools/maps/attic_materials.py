"""Build the repeated wallpaper, carpet and drop ceiling of The Rooms Remember."""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from generate_sandkeep_materials import write_wal
from platoon_palette import load_palette

BASE = Path(__file__).resolve().parents[2] / 'baseq2'
WALL = 'bedroom/memory_wall'
FLOOR = 'bedroom/memory_floor'
PANEL = 'bedroom/memory_panel'
DIFFUSER = 'bedroom/memory_diffuser'
SIZE = 128


def tile_noise(rng, size, cells):
    """Interpolate a repeated field so wear can continue across UV seams."""
    field = Image.fromarray(rng.normal(size=(cells, cells)).astype(np.float32))
    padded = Image.new('F', (cells * 3, cells * 3))
    for y in range(3):
        for x in range(3):
            padded.paste(field, (x * cells, y * cells))
    stretched = padded.resize((size * 3, size * 3), Image.Resampling.BICUBIC)
    return np.asarray(stretched.crop((size, size, size * 2, size * 2)))


def pigment(rgb, tone):
    color = np.asarray(rgb, dtype=np.float32) + tone[:, :, None]
    return Image.fromarray(np.clip(np.rint(color), 0, 255).astype(np.uint8))


def wallpaper(rng):
    print_layer = Image.new('L', (SIZE, SIZE), 128)
    draw = ImageDraw.Draw(print_layer)
    # The alternating little arches read as old botanical vinyl at player height.
    for x in range(16, SIZE, 32):
        stagger = 16 * ((x // 32) % 2)
        draw.line((x - 12, 0, x - 12, SIZE - 1), fill=120)
        draw.line((x - 11, 0, x - 11, SIZE - 1), fill=135)
        for y in range(stagger - 32, SIZE + 32, 32):
            draw.arc((x - 8, y-10, x+8, y+11), 180, 360, fill=105, width=2)
            draw.arc((x - 6, y-7, x+6, y+9), 180, 360, fill=139)
            draw.line((x, y-3, x, y+9), fill=106)
            draw.line((x-5, y-1, x, y+4, x+5, y-1), fill=110)
            draw.line((x-4, y+4, x, y+9, x+4, y+4), fill=113)
            draw.polygon(((x, y+11), (x+2, y+14), (x, y+16), (x-2, y+14)), fill=110)
    tone = np.asarray(print_layer, dtype=np.float32) - 128
    wear = tile_noise(rng, SIZE, 8)
    tone *= np.clip(.85 + .13 * wear, .60, 1.12)
    tone += 3.5 * tile_noise(rng, SIZE, 4) + 1.5 * wear
    tone += rng.normal(0, 1.6, (SIZE, SIZE))
    return pigment((206, 196, 128), tone)


def carpet(rng):
    fiber = rng.normal(0, 9, (SIZE, SIZE))
    tone = fiber * .8 + np.roll(fiber, 1, axis=1) * .28
    tone += tile_noise(rng, SIZE, 20) * 4.5
    tone += tile_noise(rng, SIZE, 4) * 4
    return pigment((156, 141, 93), tone)


def ceiling(rng):
    y, x = np.indices((SIZE, SIZE))
    seam = (x % 32 == 0) | (y % 32 == 0)
    inset = (x % 32 == 31) | (y % 32 == 31)
    highlight = (x % 32 == 1) | (y % 32 == 1)
    # The 32-texel grid aligns to 64-unit light slots with a UV scale of 2.
    tone = rng.normal(0, 3.4, (SIZE, SIZE))
    tone += np.repeat(np.repeat(rng.normal(0, 4.3, (4, 4)), 32, axis=0), 32, axis=1)
    tone -= np.where(seam, 41, np.where(inset, 13, 0))
    tone += np.where(highlight, 6, 0)
    return pigment((177, 171, 132), tone)


def diffuser(rng):
    size = 64
    y, x = np.indices((size, size))
    prism = ((x+x//4) % 4 == 0) & (y % 3 == 0)
    tone = rng.normal(0, .7, (size, size)) - np.where(prism, 3, 0)
    return pigment((252, 251, 240), tone)


def write_materials():
    palette = load_palette()
    rng = np.random.default_rng(28065)
    for name, generate in (
        (WALL, wallpaper), (FLOOR, carpet), (PANEL, ceiling), (DIFFUSER, diffuser),
    ):
        image = generate(rng)
        path = BASE / 'textures' / name
        image.save(path.with_suffix('.png'))
        write_wal(path.with_suffix('.wal'), name, image, palette)


if __name__ == '__main__':
    write_materials()
