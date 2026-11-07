#!/usr/bin/env python3
"""Generate the animated eight-legged spider and its skin as original MD2 assets."""
import argparse
import io
import math
import numpy as np
from PIL import Image, ImageDraw
import build_ant as base
from build_heavy_tank import Mesh
from md2_assets import ROOT, MD2

DIRECTORY = 'models/monsters/spider'
base.DIRECTORY = DIRECTORY
base.SKIN = DIRECTORY + '/skin.png'


def skin():
    image = Image.new('RGB', (256, 256)); draw = ImageDraw.Draw(image)
    colors = [(55,47,38), (81,67,49), (35,29,26), (155,38,27),
              (116,91,61), (196,151,87), (44,35,29), (94,71,48),
              (58,45,37), (83,62,43), (48,36,29), (112,83,52),
              (67,50,39), (94,70,47), (75,54,39), (37,29,26)]
    for i, color in enumerate(colors):
        x, y = i % 4 * 64, i // 4 * 64
        draw.rectangle((x,y,x+63,y+63),fill=color)
        for py in range(4,60,8):
            for px in range(4,60,8):
                v = ((px*13+py*7+i)%5)-2
                draw.point((x+px,y+py), fill=tuple(max(0,min(255,c+v)) for c in color))
    out=io.BytesIO(); image.save(out,format='PNG',compress_level=9); return out.getvalue()


def make_frame(kind,index,count):
    m=Mesh(); phase=math.tau*index/count
    gait = (1 if kind=='walk' else 1.45) if kind in ('walk','run') else 0
    bob = 1.7*math.sin(phase*2) if gait else (0.9*math.sin(phase) if kind=='idle' else 0)
    bite = math.sin(math.pi*index/(count-1)) if kind=='attack' else 0
    recoil = math.sin(math.pi*index/(count-1)) if kind=='pain' else 0
    head_shift = 8*bite-5*recoil
    head_drop = -3*bite+2*recoil
    # Two broad body segments and a narrow pedicel identify a spider silhouette.
    base.ellipsoid(m,(-20,0,0+bob),(21,17,16),0,5,10)
    base.ellipsoid(m,(-3,0,-2+bob),(6,6,6),2,4,8)
    base.ellipsoid(m,(10+head_shift,0,-1+bob+head_drop),(17,14,11),1,5,10)
    # Eight bright, separately modeled eyes, arranged across the front of the head.
    for side in (-1,1):
        for j in range(4):
            y=side*(2.3+j*2.7); x=25-0.08*y*y+head_shift
            base.ellipsoid(m,(x,y,3.7+bob+head_drop+(j%2)*2),(3.2,3.1,3.1),3,3,6)
        # Paired downward curved fangs and palps.
        m.cylinder((23+head_shift,side*5,-6+bob+head_drop),(30+head_shift,side*(6+3*bite),-9+bob+head_drop),2.2,2,2,6)
        m.cylinder((30+head_shift,side*(6+3*bite),-9+bob+head_drop),(32+head_shift,side*(4+3*bite),-16+bob+head_drop),1.35,2,2,6)
        for leg,x in enumerate((17,9,0,-9)):
            a=phase+(leg%2)*math.pi+(side==1)*math.pi
            swing=math.sin(a)*gait; lift=max(0,math.cos(a))*gait
            spread=(1.5-leg)*9
            hip=np.array([x,side*10,-3+bob])
            knee=np.array([x+spread+swing*6,side*(30+1.5*lift),9+bob+lift*3])
            ankle=np.array([x+spread*1.55+swing*9,side*43,-10+lift*5])
            foot=np.array([x+spread*1.8+swing*11,side*49,-23+lift*7])
            m.cylinder(hip,knee,2.6,1,2,6)
            m.cylinder(knee,ankle,2.0,0,2,6)
            m.cylinder(ankle,foot,1.2,2,2,6)
    if kind=='death':
        # Complete the full inversion in half a second, then hold the pose.
        t=min(index/5,1.0); angle=math.pi*(1-(1-t)**2)
        cs,sn=math.cos(angle),math.sin(angle)
        rot=np.array([[1,0,0],[0,cs,-sn],[0,sn,cs]])
        p=np.asarray(m.vertices); pivot=np.array([0.,0.,-15.]); p=(p-pivot)@rot.T+pivot
        p[:,2]+=-24-p[:,2].min(); m.vertices=p.tolist()
        m.normals=(np.asarray(m.normals)@rot.T).tolist()
    return m


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify',action='store_true'); parser.add_argument('--review',action='store_true')
    args=parser.parse_args(); base.make_frame=make_frame
    model,png=base.build(),skin()
    for path,data in ((ROOT/'baseq2'/DIRECTORY/'tris.md2',model),(ROOT/'baseq2'/base.SKIN,png)):
        if args.verify:
            if path.read_bytes()!=data: raise ValueError(f'Asset differs: {path}')
        else:
            path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(data)
    if args.review: base.review(model,png,'spider.png',65)
    print('Spider:',MD2.read(model).stats())

if __name__=='__main__': main()
