#!/usr/bin/env python3
"""Generate a two-room diagnostic scene with the 92 audited pickup placements.

This is a synthetic workload, NOT a replacement or optimization of the sandbox.
It uses an original Quake II texture from the user's installed game data.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def box(lo, hi, texture):
    x, y, z = lo
    X, Y, Z = hi
    faces = [((x,y,z),(x,y,Z),(x,Y,Z)), ((X,y,z),(X,Y,z),(X,Y,Z)),
             ((x,y,z),(X,y,z),(X,y,Z)), ((x,Y,z),(x,Y,Z),(X,Y,Z)),
             ((x,y,z),(x,Y,z),(X,Y,z)), ((x,y,Z),(X,y,Z),(X,Y,Z))]
    # Quake MAP planes use (p0-p1) cross (p2-p1).
    return '{\n' + ''.join(' '.join('( %d %d %d )' % p for p in (a,c,b)) +
        f' {texture} 0 0 0 1 1\n' for a,b,c in faces) + '}\n'

def entity(properties):
    return '{\n' + ''.join(f'"{k}" "{v}"\n' for k,v in properties.items()) + '}\n'

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=ROOT / 'maps/fixtures/pp_perf_fixture.map')
    p.add_argument('--texture', default='e1u1/metal2_1')
    p.add_argument('--effects', action='store_true', help='add repeatable native projectile/explosion emitters; diagnostic stress only')
    a = p.parse_args()
    text = '{\n"classname" "worldspawn"\n"message" "Plastic Platoon diagnostic pickup fixture"\n'
    boxes = [((-640,-512,-32),(640,512,0)), ((-640,-512,256),(640,512,288)),
             ((-672,-544,-32),(-640,544,288)), ((640,-544,-32),(672,544,288)),
             ((-640,-544,-32),(640,-512,288)), ((-640,512,-32),(640,544,288)),
             ((-16,-512,0),(16,-64,256)), ((-16,64,0),(16,512,256)),
             ((-16,-64,128),(16,64,256))]
    text += ''.join(box(lo, hi, a.texture) for lo, hi in boxes) + '}\n'
    text += entity({'classname':'info_player_start','origin':'-560 0 24','angle':'0'})
    for y in (64, 128, 192):
        text += entity({'classname':'info_player_coop','origin':f'-560 {y} 24','angle':'0'})
    for x in (-400,-160,160,400):
        for y in (-300,0,300):
            text += entity({'classname':'light','origin':f'{x} {y} 192','light':'400'})
    assets = json.loads((ROOT / 'tools/assets/pickups.json').read_text())['assets']
    items = [asset['classname'] for asset in assets for _ in range(asset['instances'])]
    # Interleave asset types so each room exercises a mix of meshes.
    items = items[::2] + items[1::2]
    for i, classname in enumerate(items):
        room, cell = divmod(i, 46)
        x = (-400 if room == 0 else 128) + (cell % 5) * 64
        y = -400 + (cell // 5) * 80
        text += entity({'classname':classname,'origin':f'{x} {y} 32'})
    if a.effects:
        # Real game-module entities exercise multicast, both local parsers,
        # projectile trails, explosion sprites/smoke and dynamic lighting.
        # Emitters are kept away from the stationary camera/player starts.
        for i, y in enumerate((-220, 220)):
            text += entity({'classname':'target_blaster','targetname':f'perf_bolt_{i}',
                            'origin':f'-400 {y} 80','angle':'0','dmg':'1','speed':'320'})
            text += entity({'classname':'func_timer','target':f'perf_bolt_{i}',
                            'wait':'0.2','spawnflags':'1'})
            text += entity({'classname':'target_explosion','targetname':f'perf_boom_{i}',
                            'origin':f'-128 {y} 64','dmg':'0'})
            text += entity({'classname':'func_timer','target':f'perf_boom_{i}',
                            'wait':'0.5','spawnflags':'1'})
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(text)
    print(f'{a.output}: {len(items)} pickups; effects={a.effects}; diagnostic source only')

if __name__ == '__main__':
    main()
