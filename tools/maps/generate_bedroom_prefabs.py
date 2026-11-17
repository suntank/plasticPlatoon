#!/usr/bin/env python3
"""Make unmarked bedroom props and walkable toy-scale arrangements."""

import argparse
from math import cos, pi, sin, tau
from pathlib import Path

from PIL import Image, ImageDraw

from generate_bathroom import BASE, disc, material
from generate_bath_prefabs import (HEADER, bevel, block, bottle_shape,
                                   cloth_surface, loft, oval, straight_oval)
from generate_build_prefabs import prism
from generate_garage_prefabs import finish, flat_ring, ring_band, slab
from generate_sandkeep_materials import write_wal
from generate_switchyard import box
from platoon_palette import load_palette

CREAM = 'enamel'
INK = 'toy_ink'
PAGES = 'kid_pages'
DENIM = 'kid_denim'
BLUE = 'kid_cotton_blue'
ROSE = 'kid_cotton_rose'
MINT = 'kid_cotton_mint'


def picture(page):
    paper = (231, 216, 186)
    im = Image.new('RGB', (128, 128), paper)
    draw = ImageDraw.Draw(im)
    if page == 'moon':
        draw.rounded_rectangle((6, 6, 121, 121), radius=11, fill=(59, 89, 139))
        draw.ellipse((36, 27, 83, 74), fill=(241, 202, 100))
        draw.ellipse((50, 21, 86, 62), fill=(59, 89, 139))
        for x,y in ((23,24),(100,43),(92,99),(19,78),(43,103)):
            draw.polygon([(x,y-6),(x+2,y-2),(x+6,y),(x+2,y+2),
                          (x,y+6),(x-2,y+2),(x-6,y),(x-2,y-2)], fill=paper)
        draw.arc((-16, 83, 142, 151), 190, 350, fill=(111, 158, 178), width=3)
    else:
        draw.rounded_rectangle((6, 6, 121, 121), radius=11, fill=(166, 193, 175))
        draw.ellipse((79, 18, 104, 43), fill=(245, 195, 83))
        draw.polygon([(13,97),(47,42),(64,67),(79,49),(116,99)], fill=(63, 121, 121))
        draw.polygon([(34,64),(47,42),(60,62),(51,58),(44,62)], fill=paper)
        draw.arc((-15, 90, 148, 138), 190, 350, fill=paper, width=4)
    return im


def write_materials():
    weave = lambda x, y: 6 * cos(tau * (x + y) / 8) + 3 * cos(tau * y / 4)
    finishes = {
        BLUE: finish((81, 128, 159), weave),
        ROSE: finish((169, 103, 116), weave),
        MINT: finish((120, 154, 128), weave),
        DENIM: finish((55, 84, 120), weave),
        PAGES: finish((219, 204, 174), lambda x,y: 7 * cos(tau * y / 4)),
        'kid_fleece': finish((151, 105, 72), lambda x,y: weave(x,y) * .8),
        'kid_wicker': finish((158, 119, 72), lambda x,y: 13 * cos(tau*x/16) * cos(tau*y/8)),
        'kid_moon': picture('moon'),
        'kid_hills': picture('hills'),
    }
    ruler = Image.new('RGB', (128, 64), (179, 137, 82))
    draw = ImageDraw.Draw(ruler)
    for x in range(0, 128, 8):
        h = 17 if x % 32 == 0 else 10 if x % 16 == 0 else 6
        draw.rectangle((x, 0, x+1, h), fill=(65, 51, 42))
        draw.rectangle((x, 63-h, x+1, 63), fill=(65, 51, 42))
    finishes['kid_ruler'] = ruler
    folder = BASE/'textures/bathroom'
    folder.mkdir(parents=True, exist_ok=True)
    palette = load_palette()
    for name,image in finishes.items():
        image.save(folder/(name+'.png'))
        write_wal(folder/(name+'.wal'),material(name),image,palette)


def cover_art(bounds, tint, picture_name):
    x,y,z,X,Y,Z = bounds
    sx, sy = (X-x)/128, (Y-y)/128
    return box(bounds, material(tint), detail=True, overrides={
        5: {'texture':material(picture_name), 'scale':(sx,sy), 'shift':(-x/sx,Y/sy)}})


def book(bounds, tint, art=None):
    x,y,z,X,Y,Z = bounds
    return (block((x,y,z,X,Y,z+3),tint)
            + block((x+4,y+4,z+3,X-4,Y-4,Z-3),PAGES)
            + block((x,y,z+2,X,y+8,Z-2),tint)
            + (cover_art((x,y,Z-3,X,Y,Z),tint,art) if art
               else block((x,y,Z-3,X,Y,Z),tint)))


def open_book():
    cover = bevel((-158,-108,0,158,108,10),2,'toy_navy')
    leaves = ''.join(prism(profile,-101,101,PAGES,axis='y') for profile in (
        [(-152,9),(-6,9),(-6,23),(-152,45)],
        [(6,9),(152,9),(152,43),(6,23)],
    ))
    crease = block((-10,-102,9,10,103,25),'toy_navy')
    # Each illustration is a separate printed inset with no raised trim.
    def panel(x,y,X,Y,start,end,art):
        patch = prism([(x,start-2),(X,end-2),(X,end),(x,start)],y,Y,PAGES,axis='y')
        sy, sx = (Y-y)/128, (X-x)/128
        lines = patch.splitlines(keepends=True)
        # Faces 1 and 2 are the end caps. The fourth profile edge is the top.
        target = 6
        prefix = lines[target].split(material(PAGES),1)[0]
        lines[target] = (prefix+f'{material(art)} {-x/sx:g} {Y/sy:g} 0 '
                          f'{sx:g} {sy:g} 134217728 0 0\n')
        return ''.join(lines)
    return (cover+leaves+crease
            +panel(-144,-86,-32,86,45,28,'kid_moon')
            +panel(32,-87,144,87,28,43,'kid_hills'))


def book_steps():
    colors = ('toy_navy','toy_coral',MINT,'toy_lilac','toy_blue')
    return ''.join(book((-192+64*i,-104+2*(i%2),16*i,176,104,16*(i+1)),tint)
                   for i,tint in enumerate(colors))


def pillow(bounds, tint):
    return bevel(bounds, 4, tint)


def cushion_steps():
    return ''.join(pillow((-171+64*i,-94,16*i,151,94,16*(i+1)),tint)
                   for i,tint in enumerate((BLUE,ROSE,MINT,'toy_lilac')))


def shoebox_steps():
    parts = []
    for i,tint in enumerate(('toy_navy',ROSE,BLUE,MINT,'toy_coral','toy_lilac')):
        x, top = -192+64*i, 16*(i+1)
        parts.append(block((x,-83,0,x+64,83,top-8),tint))
        parts.append(block((x-2,-87,top-8,x+66,87,top),tint))
        if top>=32:
            parts.append(block((x+17,-84,top-22,x+47,-82,top-16),INK))
    return ''.join(parts)


def ruler_bridge():
    bridge = prism([(-226,0),(226,0),(226,12),(-226,12)],-48,48,'kit_beech',axis='y')
    patch = box((-222,-47,11,222,47,12.25), material('kit_beech'), detail=True,
                overrides={5: {'texture':material('kid_ruler'),'scale':(1,94/64),'shift':(0,32)}})
    return bridge + patch


def sneaker():
    sole = bevel((-160,-70,0,176,70,18),4,CREAM)
    welt = bevel((-157,-68,16,173,68,25),3,DENIM)
    profile = [(-55,0),(55,0),(58,11),(42,35),(-42,35),(-58,11)]
    upper = loft([[(y*s,z*s+21,x) for y,z in profile]
                  for x,s in ((-59,1.14),(36,1.12),(104,1.03),(152,.84),(170,.45))],
                 BLUE,axis='x')
    collar = (bevel((-153,-61,22,-124,61,79),4,BLUE)
              + bevel((-139,-65,21,-52,-46,80),4,BLUE)
              + bevel((-139,46,21,-52,65,80),4,BLUE))
    tongue = prism([(-64,57),(36,55),(36,58),(-64,87)],-34,34,DENIM,axis='y')
    toe = bottle_shape(51,17,6,[(112,1,0,39),(153,.88,0,37),(171,.55,0,32)],
                       CREAM,axis='x')
    laces = ''.join(bevel((x,-42,z-2,x+7,42,z+3),1,CREAM)
                    for x,z in ((-54,85),(-33,79),(-12,73),(9,67),(29,61)))
    return sole+welt+upper+collar+tongue+toe+laces


def slipper():
    sole = bevel((-143,-66,0,150,66,17),4,'toy_navy')
    sides = (bevel((-138,-64,13,-117,64,41),3,'toy_lilac')
             + bevel((-130,-64,13,48,-49,45),3,'toy_lilac')
             + bevel((-130,49,13,48,64,45),3,'toy_lilac'))
    toe = oval([(15,70,0,72),(44,69,0,81),(63,73,0,65),(73,74,0,41)],
               'toy_lilac',aspect=.8)
    tips = ''.join(oval([(60,82,y,18),(82,75,y,14),(99,64,y,10)],ROSE,aspect=.58)
                   for y in (-25,25))
    eyes = ''.join(straight_oval(y,54,6,7,141,149,INK,axis='x') for y in (-20,20))
    return sole+sides+toe+tips+eyes


def shirt_outline():
    return [(-69,-100,9),(69,-100,11),(65,32,15),(116,20,8),(128,60,11),
            (70,93,19),(34,89,17),(0,61,18),(-32,90,16),(-73,94,18),
            (-130,59,9),(-114,19,10),(-65,31,14)]


def tshirt():
    return cloth_surface((0,55,26),shirt_outline(),(MINT,MINT,BLUE,MINT))


def hoodie():
    body = cloth_surface((0,55,36),[(x,y,z+4) for x,y,z in shirt_outline()],(ROSE,))
    hood = ring_band(0,78,(15,27,56),(49,29,51),ROSE,sides=12)
    hood_base = straight_oval(0,78,43,38,0,16,ROSE)
    pocket = slab([(-32,-46),(35,-45),(43,-22),(-45,-22)],18,29,'toy_coral')
    return body+hood_base+hood+pocket


def jeans():
    waist = cloth_surface((6,42,32),[(-78,14,18),(80,8,15),(99,85,13),
                                    (21,100,21),(-85,92,19)],(DENIM,))
    result = [waist]
    for side in (-1,1):
        outline = [(x*side,y,z) for x,y,z in ((4,27,19),(82,26,18),(94,-58,16),
                                             (126,-143,9),(67,-148,9),(36,-79,14))]
        result.append(cloth_surface((61*side,-35,29),outline,(DENIM,DENIM,BLUE,DENIM)))
    return ''.join(result)


def socks():
    outline = [(-60,-15,8),(-10,-20,15),(39,-57,11),(74,-49,8),(76,-26,9),
               (42,9,16),(12,35,14),(-62,32,12)]
    return ''.join(cloth_surface((x+10,y,26),[(x+u,y+v,z) for u,v,z in outline],
                                 (tint,CREAM,CREAM,tint,tint,CREAM,CREAM,CREAM))
                   for x,y,tint in ((-51,-23,BLUE),(56,44,ROSE)))


def teddy():
    fur = 'kid_fleece'
    belly = oval([(0,0,9,53),(24,0,8,64),(85,0,8,65),(128,0,8,47)],
                 fur,aspect=.8)
    head = oval([(110,0,2,40),(138,0,0,57),(180,0,0,62),(216,0,3,43),
                 (226,0,4,25)],fur,aspect=.8)
    ears = ''.join(oval([(-10,x,209,20),(3,x,214,26),(16,x,214,22)],fur,aspect=1.15,axis='y')
                   +straight_oval(x,215,12,13,-13,-8,ROSE,axis='y') for x in (-54,54))
    muzzle = oval([(-64,0,150,24),(-52,0,151,41),(-33,0,151,46)],
                  CREAM,aspect=.60,axis='y')
    nose = straight_oval(0,159,13,9,-68,-62,INK,axis='y')
    eyes = ''.join(straight_oval(x,178,7,8,-51,-40,INK,axis='y') for x in (-24,24))
    limbs = ''.join(oval([(0,x,-40,35),(23,x,-41,39),(51,x,-36,29)],fur,aspect=1.12)
                    +oval([(35,1.48*x,0,29),(73,1.47*x,1,34),(114,1.19*x,7,25)],
                          fur,aspect=.86) for x in (-42,42))
    return belly+head+ears+muzzle+nose+eyes+limbs


def toy_car():
    shell = bevel((-149,-62,19,152,62,53),7,'toy_coral')
    cabin = prism([(-80,48),(106,48),(66,90),(-41,90)],-47,47,'toy_navy',axis='y')
    roof = bevel((-48,-47,87,70,47,99),3,'toy_coral')
    bumpers = block((-151,-57,22,-143,57,36),'garage_steel')+block((146,-57,22,155,57,37),'garage_steel')
    axle = 32*cos(pi/12)
    wheels = ''.join(straight_oval(x,axle,32,32,y,Y,INK,axis='y')
                     +straight_oval(x,axle,17,17,a,b,'garage_steel',axis='y')
                     for x in (-91,92) for y,Y,a,b in ((-76,-52,-78,-72),(52,76,72,78)))
    return shell+cabin+roof+wheels+bumpers


def rocket():
    body = oval([(0,0,0,38),(22,0,0,44),(69,0,0,55),(172,0,0,55),
                 (200,0,0,44)],CREAM)
    cap = oval([(194,0,0,46),(222,0,0,40),(251,0,0,23),(276,0,0,5)],'toy_coral')
    porthole = (straight_oval(0,140,25,25,-61,-49,'toy_navy',axis='y')
                +straight_oval(0,140,18,18,-64,-59,'window',axis='y'))
    shape = [(30,13),(84,0),(74,38),(36,84)]
    fins = ''.join(prism([(direction*x,z) for x,z in shape],-6,6,'toy_coral',axis=axis)
                   for direction in (-1,1) for axis in ('x','y'))
    return body+cap+porthole+fins


def stacking_rings():
    base = straight_oval(0,0,91,91,0,12,'toy_navy')
    peg = straight_oval(0,0,15,15,10,140,CREAM)
    rings = ''.join(flat_ring(0,0,15,outer,z,z+22,color) for z,outer,color in (
        (12,79,'toy_coral'),(34,69,'toy_orange'),(56,59,'toy_lemon'),
        (78,49,'toy_mint'),(100,38,'toy_blue')))
    return base+peg+rings+straight_oval(0,0,21,21,129,146,'toy_lilac')


def play_ball():
    # Integer radial directions keep the painted panels joined on all tiers.
    rim = [(6,2),(4,5),(0,6),(-4,5),(-6,2),(-6,-2),(-4,-5),(0,-6),(4,-5),(6,-2)]
    panels = []
    colors = ('toy_coral','toy_blue',CREAM,'toy_lemon',CREAM)
    for i,(x,y) in enumerate(rim):
        u,v = rim[i-1]
        rings = [[(0,0,z),(u*scale,v*scale,z),(x*scale,y*scale,z)]
                 for z,scale in ((0,3),(16,8),(43,11),(83,11),(112,8),(128,3))]
        panels.append(loft(rings,colors[i%len(colors)]))
    return ''.join(panels)


def drum():
    skin = straight_oval(0,0,89,89,112,119,CREAM)
    shell = (straight_oval(0,0,85,85,0,11,'toy_navy')
             +straight_oval(0,0,82,82,11,110,'toy_coral')
             +straight_oval(0,0,91,91,107,115,'toy_navy'))
    clamps = ''.join(straight_oval(round(82*cos(a),3),round(82*sin(a),3),
                                   5,5,18,105,'garage_steel') for a in (i*tau/8 for i in range(8)))
    sticks = ''.join(bevel((-59,y,117,64,y+8,125),2,'kit_beech')
                     +straight_oval(y+4,121,7,6,57,70,'kit_beech',axis='x') for y in (-24,17))
    return shell+skin+clamps+sticks


def backpack():
    case = bottle_shape(82,48,20,[(0,.86,0,0),(14,1,0,0),(139,1,0,0),
                                   (179,.78,0,0)],BLUE)
    pouch = (bevel((-65,-65,25,65,-36,91),6,DENIM)
             +block((-57,-66,78,57,-64,82),CREAM))
    straps = ''.join(bevel((x,35,18,x+24,63,151),5,'toy_navy') for x in (-58,34))
    grip = (block((-38,-8,166,-28,11,196),'toy_navy')
            +block((28,-8,166,38,11,196),'toy_navy')
            +bevel((-38,-11,190,38,14,206),3,'toy_navy'))
    return case+pouch+straps+grip


def pencil():
    paint = straight_oval(0,17,17,17,-134,104,'toy_lemon',axis='x')
    tip = oval([(102,0,17,17),(144,0,17,6)],'kit_beech',axis='x')
    lead = oval([(142,0,17,6),(156,0,17,1.5)],INK,axis='x')
    grip = straight_oval(0,17,18,18,-150,-128,'garage_steel',axis='x')
    eraser = straight_oval(0,17,16,16,-173,-148,ROSE,axis='x')
    return paint+tip+lead+grip+eraser


def crayons():
    return ''.join(straight_oval(y,17,17,17,-87+shift,67+shift,tint,axis='x')
                   +oval([(65+shift,y,17,17),(92+shift,y,17,6)],tint,axis='x')
                   +straight_oval(y,17,18,18,-69+shift,55+shift,paper,axis='x')
                   for y,shift,tint,paper in ((-47,-13,'toy_coral',ROSE),
                                              (0,18,'toy_blue',BLUE),(49,-24,'toy_mint',MINT)))


def hamper():
    pan = straight_oval(0,0,91,91,0,12,'kid_wicker')
    lower = ring_band(0,0,(12,77,91),(133,98,112),'kid_wicker')
    rim = ring_band(0,0,(128,97,115),(143,97,115),'kit_beech')
    clothes = (bevel((-64,-52,12,61,59,41),5,ROSE)
               +bevel((-61,-54,38,62,64,64),5,BLUE))
    handgrips = ''.join(bevel((x,-32,113,X,32,142),4,MINT) for x,X in ((-121,-106),(106,121)))
    return pan+lower+rim+clothes+handgrips


PREFABS = {
    'book_thin': lambda: book((-104,-79,0,104,79,16),'toy_navy','kid_moon'),
    'book_thick': lambda: book((-133,-92,0,133,92,48),'toy_coral','kid_hills'),
    'book_open': open_book,
    'book_steps': book_steps,
    'cushion_steps': cushion_steps,
    'shoebox_steps': shoebox_steps,
    'ruler_bridge': ruler_bridge,
    'sneaker': sneaker,
    'slipper': slipper,
    'tshirt': tshirt,
    'hoodie': hoodie,
    'jeans': jeans,
    'sock_pair': socks,
    'teddy': teddy,
    'toy_car': toy_car,
    'toy_rocket': rocket,
    'stacking_rings': stacking_rings,
    'play_ball': play_ball,
    'toy_drum': drum,
    'pillow': lambda: pillow((-105,-77,0,105,77,39),BLUE),
    'backpack': backpack,
    'pencil': pencil,
    'crayons': crayons,
    'laundry_basket': hamper,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    write_materials()
    for name,make in PREFABS.items():
        map_text = HEADER+'{\n"classname" "worldspawn"\n'+make()+'}\n'
        (args.output/f'kid_{name}.map').write_text(map_text,encoding='ascii')


if __name__ == '__main__':
    main()
