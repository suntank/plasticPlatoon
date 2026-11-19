#!/usr/bin/env python3
"""Build the Sandstorm briefing MAP and its standalone mission pack."""
from __future__ import annotations

import argparse
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from PIL import Image

from generate_helicopter_test import box, entity
from sandstorm_briefing_art import DEPLOY_PIC, write_art
from verify_sandkeep import parse_entities
from build_briefing_general import build_general, MODEL, SKIN, VOICE

ROOT = Path(__file__).resolve().parents[2]
NAME = 'pp_sandstorm_briefing'
BASE = ROOT / 'baseq2'
DEFAULT_VOICE = ROOT / 'dialog_briefing1.wav'
SUBTITLES = ROOT / 'tools/assets/sources/sandstorm-briefing.sub'
DETAIL = 0x08000000
LIGHT = 1


def mapped_box(lo, hi, material, detail=DETAIL, panel=None):
    """Apply a single artwork to one face of an otherwise tiled brush."""
    brush = box(lo, hi, material, detail)
    if panel is None:
        return brush
    face, texture, size, glow = panel
    offset, bounds = {
        0: ((hi[1], -hi[2]), (lo[1]-hi[1], hi[2]-lo[2])),
        2: ((lo[0], -hi[2]), (hi[0]-lo[0], hi[2]-lo[2])),
        5: ((lo[0], -hi[1]), (hi[0]-lo[0], hi[1]-lo[1])),
    }[face]
    sx, sy = (span / extent for span, extent in zip(bounds, size))
    lines = brush.splitlines(keepends=True)
    points = lines[1+face].rsplit(' )', 1)[0] + ' )'
    lines[1+face] = (f'{points} briefing/{texture} {-offset[0]/sx:.8f} {-offset[1]/sy:.8f}'
                     f' 0 {sx:.8f} {sy:.8f} {detail} {LIGHT if glow else 0} {glow}\n')
    return ''.join(lines)


def round_brush(cx, cy, bottom, top, radius, material):
    """Eight-sided detail brush, kept small so the tabletop sightline stays open."""
    outline = [(cx+radius*math.cos(math.tau*(i+.5)/8), cy+radius*math.sin(math.tau*(i+.5)/8))
               for i in range(8)]
    a = [(x,y,bottom) for x,y in outline]
    b = [(x,y,top) for x,y in outline]
    planes = [(a[0], a[1], a[2]), (b[0], b[2], b[1])]
    planes.extend((a[i], b[(i+1)%8], a[(i+1)%8]) for i in range(8))
    return '{\n' + ''.join(' '.join('( '+' '.join(f'{v:.4f}' for v in p)+' )' for p in plane)
                            + f' {material} 0 0 0 1 1 {DETAIL} 0 0\n' for plane in planes) + '}\n'


def layout(last_frame):
    brushes, entities = [], []

    def prop(lo, hi, material='briefing/steel', detail=DETAIL, panel=None):
        brushes.append(mapped_box(lo, hi, material, detail, panel))

    def point(classname, origin=None, brush='', **keys):
        if origin is not None:
            keys['origin'] = ' '.join(map(str, origin))
        entities.append(entity(dict(classname=classname, **keys), brush))

    def light(origin, power, color):
        point('light', origin, light=power, _color=color)

    # The east wall opens into a short deployment bay. Both spaces share a sealed shell.
    prop((-304,-216,-16), (432,208,0), 'briefing/floor', 0)
    prop((-304,-216,184), (432,208,200), 'briefing/wall', 0)
    prop((-304,-216,0), (432,-192,184), 'briefing/wall', 0)
    prop((-304,184,0), (432,208,184), 'briefing/wall', 0)
    prop((-304,-192,0), (-280,184,184), 'briefing/wall', 0)
    prop((408,-192,0), (432,184,184), 'briefing/wall', 0)
    prop((280,-192,0), (408,-24,184), 'briefing/wall', 0)
    prop((280,56,0), (408,184,184), 'briefing/wall', 0)
    prop((280,-24,78), (408,56,184), 'briefing/wall', 0)

    # Recessed backing, field diagram, bench seats and ceiling battens.
    prop((-280,174,0), (280,184,30), 'briefing/black')
    prop((-187,172,32), (187,184,171), 'briefing/steel')
    prop((-178,169,39), (178,172,163), 'briefing/black', panel=(2,'board',(1024,512),40))
    for x in (-192, 184):
        prop((x,165,36), (x+8,176,167), 'briefing/edge')
    for x in (-252, 216):
        prop((x,128,0), (x+39,171,20), 'sandkeep/trim')
        prop((x-2,126,19), (x+41,173,23), 'briefing/edge')
        for dx in (5,30):
            prop((x+dx,126,3), (x+dx+3,129,19), 'briefing/edge')
    for x in (-265, 250):
        for y in (-138, 82):
            prop((x,y,5), (x+11,y+9,12), 'briefing/black')
            prop((x,y+59,5), (x+11,y+68,12), 'briefing/black')
            prop((x-4,y-3,11), (x+15,y+71,16), 'briefing/edge')
            prop((x-1,y-1,16), (x+12,y+69,20), 'sandkeep/garden_canvas')
    for y in (-130, -23, 105):
        prop((-280,y,173), (280,y+12,184), 'briefing/steel')
        for x in (-137, 55):
            prop((x-4,y-4,168), (x+86,y+16,173), 'briefing/black')
            prop((x,y,166), (x+82,y+12,168), 'briefing/lamp')
            light((x+41,y+6,148), 240, '1 .93 .78')
    for x in (-219, 211):
        prop((x,178,70), (x+8,183,147), 'briefing/black')
        prop((x+2,176,75), (x+6,178,142), 'briefing/lamp')
        light((x+4,159,110), 155, '1 .8 .6')
    light((0,119,113), 185, '.77 .94 1')
    light((2,-12,114), 255, '1 .97 .83')
    light((-30,35,86), 165, '1 .92 .75')
    light((34,49,73), 135, '.72 .91 1')
    light((0,-119,95), 125, '.82 .92 1')

    # Low steel war table with a printed terrain surface and physical miniatures.
    for x in (-101, 91):
        for y in (-43, 28):
            prop((x,y,0), (x+10,y+10,24), 'briefing/black')
        prop((x,-43,4), (x+10,38,8), 'briefing/steel')
    prop((-116,-63,22), (116,53,27), 'briefing/edge')
    prop((-114,-61,27), (114,51,29), 'briefing/black', panel=(5,'terrain',(1024,512),3))
    prop((-36,-64,14), (36,-63,27), 'briefing/black', panel=(2,'general',(512,128),10))
    prop((-40,-29,29), (41,33,30), 'sandkeep/sand')
    for lo, hi in (((-43,-32,29), (-40,36,33)), ((41,-32,29), (44,36,33)),
                   ((-40,-32,29), (41,-29,33)), ((-40,33,29), (41,36,33))):
        prop(lo, hi, 'sandkeep/garden_cedar')
    for x in (-20, 20):
        for y in (-12, 16):
            brushes.append(round_brush(x,y,30,43,5,'sandkeep/sand_wall'))
            brushes.append(round_brush(x,y,40,43,6.1,'sandkeep/sand'))
            for dx, dy in ((-2.8,-2.8),(-2.8,2.8),(2.8,-2.8),(2.8,2.8)):
                prop((x+dx-1.1,y+dy-1.1,43), (x+dx+1.1,y+dy+1.1,45.7), 'sandkeep/sand')
    for lo, hi in (((-20,14,30),(20,18,38)), ((-20,-14,30),(20,-10,38)),
                   ((-22,-12,30),(-18,-5,36)), ((-22,8,30),(-18,16,36)),
                   ((18,-12,30),(22,16,36))):
        prop(lo, hi, 'sandkeep/sand_wall')
    for x in range(-14, 16, 5):
        prop((x,14,38), (x+2,18,40), 'sandkeep/sand')
    prop((-8,-2,30), (8,11,39), 'sandkeep/sand_wall')
    prop((-9,-3,39), (9,12,41), 'sandkeep/sand')
    # A walk-through gateway passes into the castle from the garden side.
    for y in (-7,6):
        prop((-25,y,30), (-19,y+4,39), 'sandkeep/sand_wall')
    prop((-25,-7,37), (-18,10,40), 'sandkeep/sand')
    # Raised garden planters bracket the painted drop point on the left.
    for x in (-101, -82, -63):
        for y in (-23,22):
            prop((x-5,y-5,29), (x+6,y+6,31), 'sandkeep/garden_cedar')
            prop((x-4,y-4,31), (x+5,y+5,31.6), 'sandkeep/garden_loam')
            for dx,dy,h in ((-2,-1,2.8),(1,1,3.6),(3,-2,2)):
                brushes.append(round_brush(x+dx,y+dy,31.6,31.6+h,1.35,'sandkeep/garden_leaf'))
    # The General stands behind the table on a molded display base.
    prop((-24,63,0), (24,91,3), 'briefing/black')
    prop((-23,60,3), (23,90,5), 'briefing/edge')

    # Painted lane and mechanical door guide the player to the mission exit.
    for x in range(134, 280, 24):
        for y in (-17, 43):
            prop((x,y,0), (x+13,y+2,.5), 'briefing/paint')
    for y in (-28,56):
        prop((273,y,0), (282,y+4,81), 'briefing/edge')
    prop((271,-30,78), (280,62,101), 'briefing/black', panel=(0,'deploy',(512,128),12))
    for y in (-33,61):
        prop((270,y,30), (279,y+3,64), 'briefing/paint')
    prop((273,1,106), (279,30,111), 'briefing/black')
    sign = box((271,3,107),(273,28,110),'briefing/locked')
    point('func_wall', brush=sign, targetname='deployment_lamp', spawnflags=7)
    sign = box((269,3,107),(271,28,110),'briefing/armed')
    point('func_wall', brush=sign, targetname='deployment_lamp', spawnflags=3)
    light((236,17,103), 220, '1 .89 .67')
    light((324,18,64), 170, '.65 .95 .88')
    light((391,17,63), 112, '.7 .93 1')
    door = mapped_box((282,-24,0), (293,56,78), 'briefing/steel', 0,
                      (0,'door',(256,256),0))
    point('func_door', brush=door, targetname='deployment_door', angle=90, speed=94,
          wait=-1, lip=0, sounds=1)
    point('trigger_once', brush=box((351,-24,0),(401,56,78),'briefing/steel'),
          target='start_garden_infiltration')
    point('target_changelevel', targetname='start_garden_infiltration', map='pp_garden_infiltration')

    point('info_player_start', (0,-161,24), angle=90)
    for x,y in ((-53,-161),(53,-161),(-100,-161)):
        point('info_player_coop', (x,y,24), angle=90)
    point('info_player_intermission', (152,-123,66), angles='7 135 0')
    point('trigger_always', target='briefing_arrival', delay=1)
    point('target_help', targetname='briefing_arrival', spawnflags=1,
          message='Approach the war table to hear the General brief Operation Sandstorm.')
    point('trigger_once', brush=box((-154,-119,0),(154,-68,112),'briefing/steel'),
          target='briefing_start', killtarget='briefing_arrival')
    point('target_help', targetname='briefing_start', spawnflags=1,
          message='Start in the garden beds. Reach and breach the sandbox wall. Sandcastle One and far-side extraction are later objectives.')
    point('misc_platoon_briefing', (0,77,5), targetname='briefing_start', target='briefing_complete',
          angle=270, model=MODEL, noise=VOICE.removeprefix('sound/'), count=last_frame)
    point('target_help', targetname='briefing_complete', spawnflags=1,
          message='Deploy to Garden Infiltration through the door on the right.')
    point('target_screen_image', targetname='briefing_complete', pic='briefing_deploy', count=4,
          distance=360)
    point('trigger_relay', targetname='briefing_complete', target='deployment_door')
    point('trigger_relay', targetname='briefing_complete', target='deployment_lamp')
    world = entity({'classname':'worldspawn', 'message':'Operation Sandstorm Briefing Room',
                    'sounds':0}, ''.join(brushes))
    return '// Sandstorm briefing room. Editable Quake II map.\n' + world + ''.join(entities)


def stage_existing_textures(source, assets):
    textures = sorted({texture for item in parse_entities(source.read_text()) for texture in item['textures']})
    for texture in textures:
        for ext in ('.wal', '.png'):
            relative = 'textures/' + texture + ext
            dst = assets / relative
            if texture.startswith('briefing/'):
                if not dst.is_file():
                    raise FileNotFoundError(dst)
            else:
                src = BASE / relative
                dst.parent.mkdir(parents=True, exist_ok=True)
                if src.is_file():
                    if ext == '.png':
                        # The compiler's RGB PNG path misreads green and blue channels.
                        with Image.open(src) as image:
                            image.convert('RGBA').save(dst)
                    else:
                        shutil.copyfile(src, dst)
                elif ext == '.wal':
                    raise FileNotFoundError(src)
            if dst.is_file():
                yield relative


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tool', default=os.environ.get('Q2TOOL', 'q2tool'))
    parser.add_argument('--voice', type=Path, default=DEFAULT_VOICE,
                        help='Voice WAV to bake into the performance (default: dialog_briefing1.wav)')
    parser.add_argument('--fonts', type=Path, default=Path('/usr/share/fonts/truetype/dejavu'))
    args = parser.parse_args()
    build = ROOT / 'build/sandstorm-briefing'
    assets = build / 'assets'
    source = ROOT / 'maps/source' / (NAME+'.map')
    write_art(assets, args.fonts)
    last_frame = build_general(assets, args.voice)
    source.write_text(layout(last_frame))
    (assets/'pics').mkdir(exist_ok=True)
    shutil.copyfile(BASE/'pics/colormap.pcx', assets/'pics/colormap.pcx')
    textures = list(stage_existing_textures(source, assets))
    subprocess.run([sys.executable, str(ROOT/'tools/performance/compile_map.py'),
                    '--source', str(source), '--tool', args.tool, '--basedir', str(assets),
                    '--profile', 'release', '--rad-subdiv', '32', '--rad-ambient', '38',
                    '--output-dir', str(BASE/'maps')], check=True)

    entries = {f'maps/{source.name}': source, f'maps/{NAME}.bsp': BASE/'maps'/(NAME+'.bsp')}
    entries.update({relative: assets/relative for relative in
                    (MODEL, SKIN, VOICE, DEPLOY_PIC+'.png', DEPLOY_PIC+'.pcx')})
    if args.voice.resolve() == DEFAULT_VOICE.resolve():
        entries['sound/briefing/sandstorm.sub'] = SUBTITLES
    entries.update({relative: (assets if relative.startswith('textures/briefing/') else BASE)/relative
                    for relative in textures})
    for mode in ('solo', 'coop'):
        cfg = f'sandstorm_briefing_{mode}.cfg'
        entries[cfg] = BASE/cfg
    archive = BASE/'operation-sandstorm-briefing.pk3'
    with tempfile.NamedTemporaryFile(dir=archive.parent, prefix=archive.stem,
                                     suffix='.tmp', delete=False) as temporary:
        draft = Path(temporary.name)
    try:
        with ZipFile(draft, 'w', ZIP_DEFLATED, compresslevel=9) as pack:
            for name, path in sorted(entries.items()):
                member = ZipInfo(name)
                member.external_attr = 0o100644 << 16
                pack.writestr(member, path.read_bytes(), compress_type=ZIP_DEFLATED, compresslevel=9)
        draft.chmod(0o644)
        draft.replace(archive)
    finally:
        draft.unlink(missing_ok=True)
    print(archive)


if __name__ == '__main__':
    main()
