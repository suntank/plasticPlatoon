#!/usr/bin/env python3
"""Build original, dependency-free Plastic Platoon startup and interface assets.

No Quake II data, font files, or other external artwork is read. The 6x6x6
RGB cube plus gray ramp is deliberately a new palette: inherited indexed PCX
and WAL artwork must be replaced or converted using its own authorized palette.
The simple 5x7 letterforms and geometric interface below are source artwork.
Generated assets are distributed under the repository's GPL-2.0-or-later terms.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[2]
PALETTE = tuple((r * 51, g * 51, b * 51)
                for r in range(6) for g in range(6) for b in range(6)) + tuple(
                    (round(i * 255 / 38),) * 3 for i in range(39)) + ((255, 0, 255),)
TRANSPARENT = 255

# Seven rows per glyph, five bits per row, drawn here rather than imported.
GLYPHS = {
    ' ': '00000/00000/00000/00000/00000/00000/00000',
    'A': '01110/10001/10001/11111/10001/10001/10001',
    'B': '11110/10001/10001/11110/10001/10001/11110',
    'C': '01111/10000/10000/10000/10000/10000/01111',
    'D': '11110/10001/10001/10001/10001/10001/11110',
    'E': '11111/10000/10000/11110/10000/10000/11111',
    'F': '11111/10000/10000/11110/10000/10000/10000',
    'G': '01111/10000/10000/10111/10001/10001/01111',
    'H': '10001/10001/10001/11111/10001/10001/10001',
    'I': '11111/00100/00100/00100/00100/00100/11111',
    'J': '00111/00010/00010/00010/10010/10010/01100',
    'K': '10001/10010/10100/11000/10100/10010/10001',
    'L': '10000/10000/10000/10000/10000/10000/11111',
    'M': '10001/11011/10101/10101/10001/10001/10001',
    'N': '10001/11001/11001/10101/10011/10011/10001',
    'O': '01110/10001/10001/10001/10001/10001/01110',
    'P': '11110/10001/10001/11110/10000/10000/10000',
    'Q': '01110/10001/10001/10001/10101/10010/01101',
    'R': '11110/10001/10001/11110/10100/10010/10001',
    'S': '01111/10000/10000/01110/00001/00001/11110',
    'T': '11111/00100/00100/00100/00100/00100/00100',
    'U': '10001/10001/10001/10001/10001/10001/01110',
    'V': '10001/10001/10001/10001/10001/01010/00100',
    'W': '10001/10001/10001/10101/10101/11011/10001',
    'X': '10001/10001/01010/00100/01010/10001/10001',
    'Y': '10001/10001/01010/00100/00100/00100/00100',
    'Z': '11111/00001/00010/00100/01000/10000/11111',
    '0': '01110/10001/10011/10101/11001/10001/01110',
    '1': '00100/01100/00100/00100/00100/00100/01110',
    '2': '01110/10001/00001/00010/00100/01000/11111',
    '3': '11110/00001/00001/01110/00001/00001/11110',
    '4': '00010/00110/01010/10010/11111/00010/00010',
    '5': '11111/10000/10000/11110/00001/00001/11110',
    '6': '01110/10000/10000/11110/10001/10001/01110',
    '7': '11111/00001/00010/00100/01000/01000/01000',
    '8': '01110/10001/10001/01110/10001/10001/01110',
    '9': '01110/10001/10001/01111/00001/00001/01110',
    '!': '00100/00100/00100/00100/00100/00000/00100',
    '?': '01110/10001/00001/00010/00100/00000/00100',
    '.': '00000/00000/00000/00000/00000/00110/00110',
    ',': '00000/00000/00000/00000/00110/00100/01000',
    ':': '00000/00110/00110/00000/00110/00110/00000',
    ';': '00000/00110/00110/00000/00110/00100/01000',
    '-': '00000/00000/00000/11111/00000/00000/00000',
    '_': '00000/00000/00000/00000/00000/00000/11111',
    '+': '00000/00100/00100/11111/00100/00100/00000',
    '=': '00000/00000/11111/00000/11111/00000/00000',
    '/': '00001/00010/00010/00100/01000/01000/10000',
    '\\': '10000/01000/01000/00100/00010/00010/00001',
    '(': '00010/00100/01000/01000/01000/00100/00010',
    ')': '01000/00100/00010/00010/00010/00100/01000',
    '[': '01110/01000/01000/01000/01000/01000/01110',
    ']': '01110/00010/00010/00010/00010/00010/01110',
    '{': '00010/00100/00100/01000/00100/00100/00010',
    '}': '01000/00100/00100/00010/00100/00100/01000',
    '<': '00001/00010/00100/01000/00100/00010/00001',
    '>': '10000/01000/00100/00010/00100/01000/10000',
    '"': '01010/01010/01010/00000/00000/00000/00000',
    "'": '00100/00100/01000/00000/00000/00000/00000',
    '`': '01000/00100/00010/00000/00000/00000/00000',
    '*': '00000/10101/01110/11111/01110/10101/00000',
    '#': '01010/01010/11111/01010/11111/01010/01010',
    '%': '11001/11010/00010/00100/01000/01011/10011',
    '&': '01100/10010/10100/01000/10101/10010/01101',
    '@': '01110/10001/10111/10101/10111/10000/01110',
    '$': '00100/01111/10100/01110/00101/11110/00100',
    '^': '00100/01010/10001/00000/00000/00000/00000',
    '|': '00100/00100/00100/00100/00100/00100/00100',
    '~': '00000/00000/01000/10101/00010/00000/00000',
}


def nearest(r, g, b):
    """Nearest opaque color in the RGB cube or gray ramp (no transparency)."""
    channels = [min(5, max(0, int(v / 51 + .5))) for v in (r, g, b)]
    cube = channels[0] * 36 + channels[1] * 6 + channels[2]
    gray = 216 + min(38, max(0, int((r + g + b) * 38 / (3 * 255) + .5)))
    dist = lambda i: sum((a - v) ** 2 for a, v in zip(PALETTE[i], (r, g, b)))
    return gray if dist(gray) < dist(cube) else cube


def pcx(width, height, pixels):
    """Write one-plane 8-bit PCX with row padding and an explicit palette."""
    if len(pixels) != width * height:
        raise ValueError('PCX pixel count differs from dimensions')
    stride = (width + 1) & ~1
    header = bytearray(128)
    struct.pack_into('<4B6H', header, 0, 10, 5, 1, 8, 0, 0,
                     width - 1, height - 1, width, height)
    header[65] = 1
    struct.pack_into('<2H', header, 66, stride, 1)
    encoded = bytearray()
    for y in range(height):
        row = bytes(pixels[y * width:(y + 1) * width]) + b'\0' * (stride - width)
        start = 0
        while start < stride:
            end = start + 1
            while end < stride and row[end] == row[start] and end - start < 63:
                end += 1
            count, color = end - start, row[start]
            if count > 1 or color >= 192:
                encoded.extend((192 | count, color))
            else:
                encoded.append(color)
            start = end
    return bytes(header + encoded + b'\x0c' + bytes(c for rgb in PALETTE for c in rgb))


def text(pixels, width, height, words, x, y, color, scale=1):
    for position, char in enumerate(words.upper()):
        glyph = GLYPHS.get(char, GLYPHS['?']).split('/')
        for row, bits in enumerate(glyph):
            for column, bit in enumerate(bits):
                if bit != '1':
                    continue
                for dy in range(scale):
                    for dx in range(scale):
                        px = x + (position * 6 + column) * scale + dx
                        py = y + row * scale + dy
                        if 0 <= px < width and 0 <= py < height:
                            pixels[py * width + px] = color


def panel(width, height, words='', background=TRANSPARENT, color=None, scale=1):
    pixels = bytearray([background]) * (width * height)
    if words:
        text(pixels, width, height, words, max(0, (width - (len(words) * 6 - 1) * scale) // 2),
             max(0, (height - 7 * scale) // 2),
             nearest(255, 255, 255) if color is None else color, scale)
    return pcx(width, height, pixels)


def framed_panel(width, height, title=''):
    """Opaque background sized for the engine's fixed overlay text coordinates."""
    dark, green = nearest(20, 40, 25), nearest(153, 255, 102)
    pixels = bytearray([dark]) * (width * height)
    for y in range(height):
        for x in range(width):
            if x in (0, width - 1) or y in (0, height - 1):
                pixels[y * width + x] = green
    if title:
        text(pixels, width, height, title, 8, 5, green)
    return pcx(width, height, pixels)


def wal(name, width, height, pixel_at):
    """Original indexed mip texture with all four mip levels."""
    levels, offsets, position = [], [], 100
    for mip in range(4):
        mw, mh = width >> mip, height >> mip
        pixels = bytes(pixel_at(x << mip, y << mip) for y in range(mh) for x in range(mw))
        offsets.append(position)
        levels.append(pixels)
        position += len(pixels)
    return struct.pack('<32s6I32s3I', name.encode(), width, height, *offsets,
                       b'', 0, 0, 0) + b''.join(levels)


def sky_tga(face):
    """A simple original blue gradient, stored as uncompressed top-down BGR."""
    size = 128
    data = bytearray(struct.pack('<BBBHHBHHHHBB', 0, 0, 2, 0, 0, 0, 0, 0,
                                 size, size, 24, 32))
    for y in range(size):
        level = 0 if face == 'up' else 1 if face == 'dn' else y / (size - 1)
        rgb = tuple(round(top * (1 - level) + bottom * level)
                    for top, bottom in zip((53, 115, 183), (166, 198, 217)))
        data.extend(bytes(reversed(rgb)) * size)
    return bytes(data)


def build_assets():
    """Return every generated path and its deterministic contents."""
    assets = {}
    # Software renderer: 64 rows of lighting then a 256x256 blend lookup.
    shades = bytearray(nearest(*(v * (63 - level) / 63 for v in rgb))
                       if i != TRANSPARENT else TRANSPARENT
                       for level in range(64) for i, rgb in enumerate(PALETTE))
    blends = bytearray(nearest(*((2 * a + b) / 3 for a, b in zip(row, column)))
                       for row in PALETTE for column in PALETTE)
    assets['pics/colormap.pcx'] = pcx(256, 320, shades + blends)
    # Engine format is R5 in bits 0..4, G6 in 5..10, B5 in 11..15.
    assets['pics/16to8.dat'] = bytes(nearest((v & 31) * 255 / 31,
                                          ((v >> 5) & 63) * 255 / 63,
                                          ((v >> 11) & 31) * 255 / 31)
                                   for v in range(65536))
    # Compatibility paths referenced by existing sandbox BSPs. These are new
    # procedural textures, with no copied Quake II pixels or source data.
    for face in ('rt', 'bk', 'lf', 'ft', 'up', 'dn'):
        assets[f'env/unit1_{face}.tga'] = sky_tga(face)
    assets['textures/common/caulk.wal'] = wal('common/caulk', 64, 64,
                                           lambda x, y: nearest(70, 90, 65))
    assets['textures/e1u1/rpip2_2.wal'] = wal('e1u1/rpip2_2', 64, 64,
                                           lambda x, y: nearest(85, 100, 95)
                                           if x % 16 < 3 else nearest(140, 155, 145))
    pixels = bytearray([TRANSPARENT]) * (128 * 128)
    for code in range(256):
        char = chr(code & 127)
        if ord(char) < 32 or ord(char) == 127:
            char = {10: '[', 11: '-', 12: ']', 13: '=', 16: '>', 17: '<',
                    18: '-', 19: '-', 20: '-', 24: '^', 25: 'V', 30: '^',
                    31: 'V'}.get(ord(char), '*')
        color = nearest(153, 255, 102) if code & 128 else nearest(255, 255, 255)
        text(pixels, 128, 128, char, (code & 15) * 8 + 1, (code >> 4) * 8, color)
    assets['pics/conchars.pcx'] = pcx(128, 128, pixels)
    white, green, dark = nearest(255, 255, 255), nearest(153, 255, 102), nearest(20, 40, 25)
    for prefix, color in (('num_', white), ('anum_', nearest(255, 102, 51))):
        for char in '0123456789-':
            name = 'minus' if char == '-' else char
            assets[f'pics/{prefix}{name}.pcx'] = panel(16, 24, char, color=color, scale=3)
    assets['pics/conback.pcx'] = panel(320, 200, 'PLASTIC PLATOON', dark, green, 2)
    assets['pics/backtile.pcx'] = panel(64, 64, background=dark)
    for name, label in {'loading': 'DEPLOYING', 'pause': 'PAUSED', 'net': 'NET',
                        'i_help': '?',
                        'field_3': '', 'field_4': '', 'field_5': ''}.items():
        width, height = ((24, 24) if name in ('net', 'i_help') else
                         (int(name[-1]) * 16 + 2, 24) if name.startswith('field_') else (160, 32))
        assets[f'pics/{name}.pcx'] = panel(width, height, label,
                                        dark if name.startswith('field_') else TRANSPARENT,
                                        green)
    # HelpComputerMessage draws its final stats at local y=164, and inventory
    # draws 17 rows at eight-pixel intervals. A small centered label would sit
    # underneath their text and leave most rows without an opaque backdrop.
    assets['pics/help.pcx'] = framed_panel(256, 192)
    assets['pics/inventory.pcx'] = framed_panel(256, 224, 'INVENTORY')
    for name in ('ch1', 'ch2', 'ch3'):
        assets[f'pics/{name}.pcx'] = panel(16, 16, '+', color=green)
    for name, label in {'game': 'DEPLOY', 'multiplayer': 'MULTIPLAYER',
                        'options': 'OPTIONS', 'video': 'VIDEO', 'quit': 'QUIT'}.items():
        for suffix, color in (('', white), ('_sel', green)):
            assets[f'pics/m_main_{name}{suffix}.pcx'] = panel(144, 24, label, color=color)
    for name, label in {'game': 'DEPLOY', 'multiplayer': 'MULTIPLAYER',
                        'options': 'OPTIONS', 'video': 'VIDEO', 'load_game': 'LOAD GAME',
                        'save_game': 'SAVE GAME', 'join_server': 'JOIN SERVER',
                        'addressbook': 'ADDRESS BOOK', 'start_server': 'HOST GAME',
                        'player_setup': 'PLAYER SETUP', 'download': 'DOWNLOADS'}.items():
        assets[f'pics/m_banner_{name}.pcx'] = panel(256, 32, label, color=green, scale=2)
    assets['pics/m_main_plaque.pcx'] = panel(48, 80, 'PP', dark, green, 2)
    assets['pics/m_main_logo.pcx'] = panel(48, 24, 'TC', color=green, scale=2)
    for i in range(15):
        assets[f'pics/m_cursor{i}.pcx'] = panel(16, 16, '>', color=green)
    # Avoid 320x240: the engine recognizes that size as the stock quit artwork
    # and applies a hard-coded correction for its credits.
    assets['pics/quit.pcx'] = panel(256, 96, 'QUIT? Y / N', dark, green, 2)
    # Imported *_i.pcx files were recolored stock player portraits. Replace
    # them with an original, flat molded-toy helmet/shoulders silhouette.
    player_colors = {'tan': (204, 170, 102), 'orange': (255, 153, 51),
                     'green': (51, 153, 51), 'red': (204, 51, 51),
                     'purple': (153, 51, 204), 'pink': (255, 102, 204),
                     'blue': (51, 102, 204), 'skin': (51, 153, 51),
                     'white': (230, 230, 230), 'gray': (130, 130, 130)}
    for name, rgb in player_colors.items():
        pixels = bytearray([TRANSPARENT]) * (32 * 32)
        body = nearest(*rgb)
        light = nearest(*(min(255, v + 51) for v in rgb))
        shadow = nearest(*(v / 2 for v in rgb))
        for y in range(32):
            for x in range(32):
                helmet = ((x - 15.5) / 10) ** 2 + ((y - 12) / 10) ** 2 <= 1 and y <= 12
                brim = 4 <= x <= 27 and 10 <= y <= 13
                head = 10 <= x <= 21 and 13 <= y <= 22
                neck = 12 <= x <= 19 and 21 <= y <= 25
                shoulders = 24 <= y <= 30 and 4 + (30 - y) // 2 <= x <= 27 - (30 - y) // 2
                if helmet or brim or head or neck or shoulders:
                    pixels[y * 32 + x] = light if x < 12 else shadow if x > 23 or y == 13 else body
        assets[f'players/soldier/{name}_i.pcx'] = pcx(32, 32, pixels)
    assets['default.cfg'] = b'''// Original Plastic Platoon defaults generated by build_bootstrap.py.
unbindall
bind w +forward
bind s +back
bind a +moveleft
bind d +moveright
bind SPACE +moveup
bind CTRL +movedown
bind SHIFT +speed
bind MOUSE1 +attack
bind MOUSE2 +ads
bind TRIG_LEFT +ads
bind TRIG_RIGHT +attack
bind BTN_SOUTH +moveup
bind BTN_EAST +movedown
bind BTN_WEST +use
bind BTN_NORTH quickgrenade
bind SHOULDR_LEFT weapprev
bind SHOULDR_RIGHT quickgrenade
bind STICK_LEFT +speed
bind DP_UP invuse
bind DP_DOWN inven
bind DP_LEFT weapprev
bind DP_RIGHT weapnext
bind BTN_BACK score
bind MWHEELUP weapprev
bind MWHEELDOWN weapnext
bind TAB inven
bind ENTER invuse
bind [ invprev
bind ] invnext
bind ` toggleconsole
bind ~ toggleconsole
bind ESCAPE menu_main
bind F1 help
bind F2 menu_savegame
bind F3 menu_loadgame
bind F10 menu_quit
bind 1 "use Pistol"
bind 2 "use Shotgun"
bind 3 "use Double Barrel Shotgun"
bind 4 "use Rifle"
bind 5 "use Heavy Machinegun"
bind 6 "use Grenade Launcher"
bind 7 "use Rocket Launcher"
bind 8 "use M1 Flamethrower"
bind 9 "use Sniper Rifle"
bind 0 "use Mortar Cannon"
set skin soldier/green
set name Platoon
set hostname "Plastic Platoon"
set vid_fullscreen 0
set r_mode 4
set crosshair 1
set cl_run 1
set freelook 1
set lookstrafe 0
set sensitivity 3
set in_grab 2
alias d1 "menu_main"
alias newgame "map pp_sandbox_coop1"
alias dedicated_start "map pp_sandbox_coop1"
'''
    return assets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'baseq2', help='asset base directory')
    parser.add_argument('--verify', action='store_true', help='compare existing files without writing')
    args = parser.parse_args()
    assets = build_assets()
    mismatches = []
    for name, data in sorted(assets.items()):
        path = args.output / name
        if args.verify:
            if not path.is_file() or path.read_bytes() != data:
                mismatches.append(name)
        elif not path.is_file() or path.read_bytes() != data:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    if mismatches:
        parser.error('Missing or changed generated assets: ' + ', '.join(mismatches))
    digest = hashlib.sha256(b''.join(name.encode() + data for name, data in sorted(assets.items()))).hexdigest()
    print(f'{"Verified" if args.verify else "Built"} {len(assets)} original bootstrap files; SHA256 {digest}')


if __name__ == '__main__':
    main()
