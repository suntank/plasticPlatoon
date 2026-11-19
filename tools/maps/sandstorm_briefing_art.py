"""Original diagrams and surface artwork for the Sandstorm briefing room."""
from pathlib import Path
import math
import random

from PIL import Image, ImageDraw, ImageFont

from generate_sandkeep_materials import write_wal
from platoon_palette import load_palette, quantize_opaque

INK = '#e8e8cf'
DIM = '#9caea1'
TEAL = '#74dfd4'
AMBER = '#ffcd78'
SAND = '#d7ae6f'
DEPLOY_PIC = 'pics/briefing_deploy'


def font(root, size, name='DejaVuSansCondensed-Bold'):
    return ImageFont.truetype(str(root / (name + '.ttf')), size)


def dashed(draw, points, fill, width=3, dash=14):
    for (x, y), (X, Y) in zip(points, points[1:]):
        length = math.hypot(X-x, Y-y)
        for i in range(0, math.ceil(length), dash*2):
            lo, hi = i/length, min(1, (i+dash)/length)
            draw.line((x+(X-x)*lo, y+(Y-y)*lo, x+(X-x)*hi, y+(Y-y)*hi), fill, width)


def waypoint(draw, x, y, size, color, glyph=None, glyph_font=None):
    draw.ellipse((x-size, y-size, x+size, y+size), '#172323', color, max(2, size//8))
    inner = size * .72
    draw.ellipse((x-inner, y-inner, x+inner, y+inner), outline=color, width=1)
    if glyph:
        draw.text((x, y-1), glyph, font=glyph_font, fill=color, anchor='mm')
    else:
        dot = size / 5
        draw.ellipse((x-dot, y-dot, x+dot, y+dot), color)


def star(draw, x, y, r, color):
    draw.polygon([(x + math.cos(a) * radius, y + math.sin(a) * radius)
                  for i in range(10) for a in [i * math.tau / 10 - math.pi / 2]
                  for radius in [r if i % 2 == 0 else r * .42]], color)


def board(fonts):
    image = Image.new('RGB', (1024, 512), '#172424')
    draw = ImageDraw.Draw(image)
    headline = font(fonts, 54)
    ui = font(fonts, 21, 'DejaVuSansMono-Bold')
    small = font(fonts, 18, 'DejaVuSansMono')
    draw.rectangle((7, 7, 1016, 504), outline='#687c70', width=2)
    draw.rectangle((24, 24, 999, 110), '#203230')
    draw.rectangle((24, 24, 31, 110), TEAL)
    draw.text((52, 66), 'Operation: Sandstorm', font=headline, fill=INK, anchor='lm')
    draw.text((970, 66), 'MISSION BRIEFING', font=ui, fill=TEAL, anchor='rm')
    draw.rectangle((34, 128, 705, 468), '#1e3330', '#597368', 2)
    for x in range(57, 700, 24):
        draw.line((x, 129, x, 467), '#2b4540')
    for y in range(131, 466, 24):
        draw.line((35, y, 704, y), '#2b4540')
    draw.text((55, 147), 'GARDEN', font=ui, fill='#a3c1a0')
    draw.text((680, 148), 'N', font=small, fill=DIM, anchor='mm')
    draw.polygon([(680, 163), (672, 182), (680, 178), (688, 182)], DIM)

    for x in (55, 98, 141, 184):
        for y in (193, 374):
            draw.rounded_rectangle((x, y, x+34, y+62), 6, '#303f2c', '#73946c', 2)
            for dy in (10, 23, 36, 49):
                draw.line((x+6, y+dy, x+28, y+dy), '#73946c', 2)
    draw.rectangle((256, 177, 537, 396), '#887454', '#ded3a5', 3)
    draw.rectangle((269, 190, 524, 383), '#5f5943', '#b6a47b', 2)
    draw.text((395, 205), 'SANDBOX', font=small, fill=INK, anchor='mt')
    randomizer = random.Random(29)
    for _ in range(400):
        x, y = randomizer.randrange(273, 521), randomizer.randrange(222, 380)
        draw.point((x, y), fill='#867651')

    # The castle is an outlined footprint with four towers and a broken entry wall.
    draw.rectangle((312, 247, 477, 354), fill='#b2925b', outline=AMBER, width=3)
    draw.rectangle((327, 261, 462, 340), fill='#434438', outline='#ddbb82', width=2)
    for x in (312, 477):
        for y in (247, 354):
            draw.rectangle((x-14, y-14, x+14, y+14), '#c8a268', AMBER, 2)
            draw.rectangle((x-7, y-7, x+7, y+7), '#70614b', AMBER, 1)
    draw.rectangle((312, 282, 327, 321), '#5f5943')
    draw.rectangle((366, 281, 426, 321), fill='#896a45', outline=SAND, width=2)
    draw.line((386, 295, 407, 307), '#ffde9c', 3)
    draw.line((407, 295, 386, 307), '#ffde9c', 3)
    dashed(draw, [(145, 302), (312, 302), (351, 302)], TEAL, 4)
    draw.polygon(((351, 302), (340, 295), (340, 309)), TEAL)
    dashed(draw, [(435, 301), (524, 301), (598, 294)], AMBER, 4)
    draw.polygon(((598, 294), (587, 287), (587, 301)), AMBER)
    waypoint(draw, 130, 300, 22, TEAL)
    waypoint(draw, 624, 290, 26, AMBER, 'E', ui)
    draw.text((397, 432), 'SANDCASTLE ONE', font=ui, fill=AMBER, anchor='mm')
    draw.line((396, 400, 396, 414), AMBER, 2)

    for i, (number, heading, description, accent) in enumerate((
        ('01', 'DROP POINT', 'Garden beds', TEAL),
        ('02', 'INFILTRATE', 'Sandcastle One', SAND),
        ('03', 'EXTRACTION', 'Far side of castle', AMBER),
    )):
        y = 135 + i*113
        draw.rectangle((728, y, 981, y+100), '#203230')
        draw.rectangle((728, y, 731, y+100), accent)
        draw.text((747, y+18), number, font=small, fill=accent)
        draw.text((785, y+18), heading, font=ui, fill=INK)
        draw.text((747, y+55), description, font=small, fill=DIM)
    return image


def terrain(fonts):
    image = Image.new('RGB', (1024, 512), '#3b4939')
    draw = ImageDraw.Draw(image)
    rand = random.Random(41)
    for _ in range(29000):
        x, y = rand.randrange(1024), rand.randrange(512)
        draw.point((x, y), rand.choice(('#46604a', '#49553c', '#334333', '#56583e')))
    draw.rounded_rectangle((42, 48, 285, 354), 21, '#54654a', '#789371', 4)
    draw.rectangle((320, 72, 706, 372), '#8f7956', '#cebd91', 5)
    draw.line((134, 236, 253, 231, 349, 220, 550, 220, 680, 222, 851, 227), '#6c7160', 28, joint='curve')
    dashed(draw, [(155, 236), (250, 231), (351, 220)], TEAL, 5)
    dashed(draw, [(646, 222), (750, 225), (843, 227)], AMBER, 5)
    sign_font = font(fonts, 23, 'DejaVuSansMono-Bold')
    for x, label, color in ((148, '01  GARDEN DROP', TEAL), (512, '02  SANDCASTLE ONE', SAND),
                            (869, '03  EXTRACTION', AMBER)):
        draw.rounded_rectangle((x-129, 424, x+129, 475), 6, '#202d28', color, 2)
        draw.text((x, 449), label, font=sign_font, fill=color, anchor='mm')
    waypoint(draw, 145, 235, 49, TEAL, '+', font(fonts, 60))
    waypoint(draw, 870, 227, 54, AMBER, 'E', font(fonts, 57))
    draw.rectangle((10, 11, 1013, 500), outline='#98a388', width=2)
    return image


def pane(name, color, dim, dark):
    image = Image.new('RGB', (128,128), color)
    draw = ImageDraw.Draw(image)
    rand = random.Random(name)
    for _ in range(3100):
        x, y = rand.randrange(128), rand.randrange(128)
        shade = rand.randrange(-7, 8)
        draw.point((x,y), tuple(c+shade for c in color))
    if name in ('wall', 'floor'):
        draw.line((0, 127, 127, 127, 127, 0), dark, 2)
        draw.line((1, 124, 124, 124, 124, 1), dim)
    if name == 'wall':
        for x in (8, 117):
            for y in (8, 117):
                draw.ellipse((x-2, y-2, x+2, y+2), dark)
                draw.point((x-1, y-1), dim)
    return image


def plate(fonts, title, subtitle, accent, title_size=42):
    image = Image.new('RGB', (512,128), '#192827')
    draw = ImageDraw.Draw(image)
    draw.rectangle((5,5,506,122), outline=accent, width=2)
    draw.rectangle((15,15,21,113), accent)
    draw.text((44,48), title, font=font(fonts, title_size), fill=INK, anchor='lm')
    draw.text((45,91), subtitle, font=font(fonts, 23, 'DejaVuSansMono-Bold'), fill=accent, anchor='lm')
    return image


def door_panel(fonts):
    image = Image.new('RGB', (256,256), '#333c35')
    draw = ImageDraw.Draw(image)
    draw.rectangle((9,9,246,246), outline='#667667', width=3)
    for y in (21, 211):
        draw.rectangle((21,y,234,y+23), '#282d28')
        for x in range(23, 216, 32):
            draw.polygon(((x,y+21),(x+12,y+21),(x+29,y+2),(x+17,y+2)), '#887445')
    draw.rectangle((29,80,226,175), '#192827', '#887445', 2)
    draw.text((128,113), 'STAND BY', font=font(fonts, 35), fill=INK, anchor='mm')
    draw.text((128,145), 'BRIEFING IN PROGRESS', font=font(fonts, 14, 'DejaVuSansMono-Bold'),
              fill=AMBER, anchor='mm')
    return image


def write_art(base: Path, fonts: Path):
    materials = {
        'wall': pane('wall', (76, 89, 75), '#596d5a', '#252f2d'),
        'floor': pane('floor', (59, 66, 63), '#4c5550', '#22292a'),
        'steel': pane('steel', (52, 67, 62), '#496259', '#263732'),
        'edge': pane('edge', (101, 119, 101), '#8d9a81', '#3b4e43'),
        'black': pane('black', (34, 43, 41), '#3b4e43', '#212a28'),
        'paint': pane('paint', (162, 130, 63), '#b28c44', '#493b23'),
        'lamp': Image.new('RGB', (32,32), '#eddfaa'),
        'armed': Image.new('RGB', (32,32), '#75dbac'),
        'locked': Image.new('RGB', (32,32), '#dc6d45'),
        'board': board(fonts),
        'terrain': terrain(fonts),
        'general': plate(fonts, 'THE GENERAL', 'FIELD COMMAND', TEAL),
        'deploy': plate(fonts, 'DEPLOY', 'GARDEN INFILTRATION', AMBER),
        'door': door_panel(fonts),
    }
    palette = load_palette()
    directory = base / 'textures/briefing'
    directory.mkdir(parents=True, exist_ok=True)
    for name, image in materials.items():
        image.convert('RGBA').save(directory / (name+'.png'))
        write_wal(directory / (name+'.wal'), 'briefing/'+name, image, palette)

    objective = plate(fonts, 'DEPLOY TO THE GARDEN', 'WALK THROUGH THE DEPLOY DOOR', TEAL,
                      title_size=35)
    (base / 'pics').mkdir(parents=True, exist_ok=True)
    objective.save(base / (DEPLOY_PIC+'.png'))
    quantize_opaque(objective, palette).save(base / (DEPLOY_PIC+'.pcx'))
