#!/usr/bin/env python3
"""Build distinct insect shell/flesh fragments and legs for organic gib bursts."""
import argparse
import io
from pathlib import Path
from PIL import Image, ImageDraw
from build_heavy_tank import Mesh
from build_ant import ellipsoid
import build_helicopter as encoder
from md2_assets import ROOT


def skin(spider):
    image = Image.new('RGB', (256, 256))
    draw = ImageDraw.Draw(image)
    colors = ([(69,43,33),(103,68,48),(44,27,25),(181,38,30),(215,63,40),(237,108,65)] if spider
              else [(111,40,22),(151,61,30),(64,24,19),(194,40,27),(228,78,45),(247,121,77)])
    for i in range(16):
        x, y = (i % 4)*64, (i // 4)*64
        draw.rectangle((x,y,x+63,y+63), fill=colors[i % len(colors)])
    out = io.BytesIO(); image.save(out, format='PNG', compress_level=9); return out.getvalue()


def chunk(spider):
    m = Mesh()
    # Broken carapace with an exposed red wound, on opposite ends.
    ellipsoid(m, (0,0,0), (9 if spider else 7, 7 if spider else 5, 5), 0, 4, 8)
    m.cylinder((5 if spider else 4,0,0),(9 if spider else 7,0,0), 4 if spider else 3.4, 3, 4, 8)
    m.cylinder((9 if spider else 7,0,0),(10 if spider else 8,0,0), 2, 4, 5, 8)
    return m


def leg(spider):
    m = Mesh()
    # Spider legs are longer, darker and slimmer than the ant's.
    m.cylinder((-8,0,0),(0,0,1), 1.8 if spider else 2.1, 0, 3, 6)
    ellipsoid(m, (0,0,1), (2.2,2.2,2.2), 1, 3, 6)
    m.cylinder((0,0,1),(8 if spider else 6,3,-4), 1.1 if spider else 1.5, 0, 2, 6)
    m.cylinder((8 if spider else 6,3,-4),(11 if spider else 8,4,-5), .7, 2, 2, 6)
    return m


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--verify',action='store_true'); args = parser.parse_args()
    for name in ('ant','spider'):
        directory = f'models/objects/gibs/{name}'
        encoder.SKIN = directory+'/skin.png'
        outputs = {'skin.png':skin(name == 'spider'), 'chunk.md2':encoder.encode(chunk(name == 'spider'),'chunk'), 'leg.md2':encoder.encode(leg(name == 'spider'),'leg')}
        for filename, data in outputs.items():
            path = ROOT/'baseq2'/directory/filename
            if args.verify:
                if path.read_bytes() != data: raise ValueError(f'Asset differs: {path}')
            else:
                path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(data)
            print(('Verified ' if args.verify else 'Built ')+str(path.relative_to(ROOT)))

if __name__ == '__main__': main()
