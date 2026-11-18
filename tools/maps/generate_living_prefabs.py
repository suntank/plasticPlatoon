#!/usr/bin/env python3
"""Export unmarked living-room brushes and matching Quake II materials."""

import argparse
from math import cos, sin, tau
from pathlib import Path

from PIL import Image, ImageDraw

from generate_bathroom import BASE, material
from generate_bath_prefabs import HEADER, bevel, block, bottle_shape, cloth_surface, oval, straight_oval
from generate_bedroom_prefabs import book, cover_art
from generate_build_prefabs import prism
from generate_garage_prefabs import finish, flat_ring, ring_band, slab
from generate_kitchen_prefabs import bowl_shell
from generate_sandkeep_materials import write_wal
from platoon_palette import load_palette

OAT = 'bedroom/living_oat'
SAGE = 'bedroom/living_sage'
RUST = 'bedroom/living_rust'
BLUE = 'bedroom/living_blue'
SCREEN = 'bedroom/living_screen'
RUG = 'bedroom/living_rug'
COVER = 'bedroom/living_cover'
WOOD = 'kit_beech'
DARKWOOD = 'bedroom/attic_wood'
INK = 'toy_ink'
STEEL = 'garage_steel'
CREAM = 'enamel'
TEAL = 'toy_aqua'
NAVY = 'toy_navy'
MINT = 'toy_mint'
CORAL = 'toy_coral'
GREEN = 'kitchen_green'


def write_materials():
    def weave(x,y):
        return 5*cos(tau*(x+y)/8)+4*cos(tau*x/4)+2*sin(tau*y/32)

    surfaces={
        key:finish(rgb,weave) for key,rgb in (
            (OAT,(176,165,142)),(SAGE,(114,138,117)),
            (RUST,(155,99,77)),(BLUE,(77,105,142)))
    }
    surfaces[SCREEN]=finish((44,60,69),lambda x,y: 7*cos(tau*(x+y)/128)+3*cos(tau*y/4))
    rug=finish((164,132,93),weave)
    d=ImageDraw.Draw(rug)
    for border,color,width in ((4,(73,102,98),7),(12,(216,187,143),2),(17,(91,119,109),3)):
        d.rectangle((border,border,127-border,127-border),outline=color,width=width)
    for x in (38,64,90):
        for y in (40,64,88):
            d.polygon([(x,y-8),(x+12,y),(x,y+8),(x-12,y)],
                      fill=(134,105,80) if (x+y)%4 else (94,123,113))
    surfaces[RUG]=rug

    cover=Image.new('RGB',(128,128),(53,104,115))
    d=ImageDraw.Draw(cover)
    d.rectangle((8,8,119,119),outline=(221,195,148),width=2)
    d.ellipse((32,24,102,95),fill=(231,176,86))
    d.polygon([(14,109),(60,49),(112,109)],fill=(143,98,79))
    d.line((17,103,110,103),fill=(222,203,174),width=2)
    surfaces[COVER]=cover

    directory=BASE/'textures/bedroom'
    palette=load_palette()
    for name,image in surfaces.items():
        leaf=name.split('/')[-1]
        image.save(directory/(leaf+'.png'))
        write_wal(directory/(leaf+'.wal'),name,image,palette)


def upholstered(seats,tint,lining,*,chaise=False):
    pitch=190
    half=seats*pitch/2
    outer=half+52
    feet=''.join(bevel((x,y,0,x+34,y+32,27),4,DARKWOOD)
                 for x in (-outer+19,outer-53) for y in (-127,111))
    base=bevel((-outer,-143,21,outer,150,89),8,tint)
    hem=bevel((-outer+8,-145,41,outer-8,-136,54),2,lining)
    arms=''.join(bevel((x,-143,60,X,151,164),9,tint)
                 for x,X in ((-outer,-half-1),(half+1,outer)))
    back=prism([(67,72),(151,72),(158,224),(121,246),(87,235)],-outer,outer,tint)
    pieces=[feet,base,hem,arms,back]
    for i in range(seats):
        x=-half+i*pitch+3
        X=x+pitch-6
        front=-281 if chaise and i==0 else -141
        if chaise and i==0:
            pieces.append(bevel((x,front+8,18,X,-128,88),7,tint))
            pieces.append(block((x+13,front+18,0,X-13,front+45,24),DARKWOOD))
        pieces.append(bevel((x,front,79,X,91,112),5,lining))
        pieces.append(prism([(77,105),(109,104),(136,221),(105,228),(83,188)],
                            x+4,X-4,lining))
    return ''.join(pieces)


def square_cushion():
    body=bevel((-91,-83,0,91,83,39),7,BLUE)
    welt=bevel((-93,-84,16,93,84,21),1,NAVY)
    return body+welt


def leaning_cushion():
    return prism([(-61,0),(-30,0),(64,103),(39,134),(12,128),(-47,37)],
                 -85,85,RUST)


def cushion_steps():
    pieces=[]
    for i,tint in enumerate((NAVY,BLUE,SAGE,OAT,RUST,SAGE,OAT)):
        y,z=-260+i*64,16*i
        end=253-i*1.5
        width=112-i*2
        center=(y+end)/2
        pieces.append(bottle_shape(width,(end-y)/2,21,
                                  [(z,1,0,center),(z+16,1,0,center)],tint))
        for x,X in ((-width-1,-width+1),(width-1,width+1)):
            pieces.append(block((x,y+24,z+6,X,end-24,z+10),NAVY))
    return ''.join(pieces)


def ottoman():
    feet=''.join(bevel((x,y,0,x+31,y+28,25),3,DARKWOOD)
                 for x in (-112,81) for y in (-74,46))
    body=bevel((-133,-95,20,133,95,68),7,SAGE)
    cushion=bevel((-137,-99,59,137,99,80),5,OAT)
    return feet+body+cushion


def footstool_steps():
    pieces=[]
    for i,tint in enumerate((BLUE,SAGE,RUST,OAT)):
        x,top=-176+78*i,16*(i+1)
        pieces.append(block((x,-79,0,x+78,79,top-9),DARKWOOD))
        pieces.append(bevel((x,-83,top-10,x+78,83,top),2,tint))
        if i:
            pieces.append(block((x+10,-81,2,x+68,-78,8),tint))
    return ''.join(pieces)


def television_crt():
    feet=bevel((-200,-108,0,196,130,22),4,INK)
    housing=bottle_shape(225,145,38,[(-106,1,0,153),(63,.92,0,153),
                                       (168,.73,0,156)],INK,axis='y')
    fascia=bevel((-216,-123,20,216,-102,281),6,NAVY)
    glass=bottle_shape(162,111,28,[(-136,.94,-22,151),(-120,1,-22,151)],
                       SCREEN,axis='y')
    speaker=''.join(block((154,-126,z,192,-121,z+3),INK) for z in range(57,190,13))
    dials=''.join(straight_oval(173,z,12,12,-135,-121,STEEL,axis='y') for z in (220,248))
    return feet+housing+fascia+glass+speaker+dials


def television_flat():
    panel=bevel((-242,-22,86,242,18,363),6,INK)
    display=bevel((-231,-26,97,231,-18,352),2,SCREEN)
    indicator=block((216,-25,89,223,-21,94),TEAL)
    supports=[]
    for x in (-176,155):
        supports.append(prism([(-69,0),(63,0),(63,10),(19,19),(-54,12)],x,x+21,INK))
        supports.append(prism([(-14,11),(14,11),(6,93),(-13,93)],x,x+21,INK))
    return panel+display+indicator+''.join(supports)


def long_remote():
    body=bevel((-115,-36,0,117,36,31),6,INK)
    power=straight_oval(-82,-9,9,9,29,35,CORAL)
    arrows=flat_ring(-38,0,8,21,29,34,STEEL,sides=12)
    ok=straight_oval(-38,0,8,8,29,35,INK)
    keys=''.join(bevel((x,y,29,x+15,y+10,35),1,CREAM if j==0 else NAVY)
                 for j,y in enumerate((-22,-5,12)) for x in (2,25,48,71,94))
    return body+power+arrows+ok+keys


def small_remote():
    body=bevel((-77,-32,0,79,32,24),5,NAVY)
    face=bevel((-59,-24,22,58,24,28),2,INK)
    button=straight_oval(-44,0,11,11,26,32,CORAL)
    pad=flat_ring(-9,0,9,19,26,33,STEEL)
    keys=''.join(bevel((x,-15,26,x+12,15,32),2,CREAM) for x in (18,39))
    return body+face+button+pad+keys


def media_console():
    plinth=block((-226,-103,0,226,103,16),DARKWOOD)
    sides=''.join(bevel((x,-107,8,X,107,190),4,WOOD)
                  for x,X in ((-230,-199),(199,230)))
    shelf=block((-213,-100,102,213,100,120),WOOD)
    top=bevel((-237,-115,174,237,115,194),3,WOOD)
    doors=''.join(bevel((x,-106,119,X,-94,174),2,DARKWOOD)
                  for x,X in ((-201,-85),(85,201)))
    grips=''.join(block((x,-110,142,x+28,-104,150),STEEL) for x in (-132,104))
    return plinth+sides+shelf+top+doors+grips


def coffee_table():
    top=bevel((-226,-114,110,226,114,135),6,WOOD)
    legs=''.join(bevel((x,y,0,x+25,y+25,117),4,DARKWOOD)
                 for x in (-201,176) for y in (-91,66))
    apron=''.join(block((-209,y,92,209,Y,117),DARKWOOD)
                  for y,Y in ((-93,-77),(77,93)))
    return top+legs+apron


def side_table():
    top=bevel((-106,-92,139,106,92,162),5,DARKWOOD)
    shelf=bevel((-91,-76,24,91,76,40),4,WOOD)
    legs=''.join(bevel((x,y,0,x+22,y+22,145),3,DARKWOOD)
                 for x in (-92,70) for y in (-79,57))
    drawer=bevel((-88,-80,103,88,79,145),5,WOOD)
    latch=block((-17,-86,116,17,-79,123),STEEL)
    return top+shelf+legs+drawer+latch


def area_rug():
    body=bevel((-232,-139,0,232,139,8),2,OAT)
    face=cover_art((-226,-134,7,226,134,8.25),OAT,RUG)
    tassels=''.join(block((x,y,0,X,y+5,4),OAT)
                     for x,X in ((-244,-230),(230,244)) for y in range(-119,120,14))
    return body+face+tassels


def blanket():
    outline=[(-132,-88,7),(-57,-109,18),(30,-103,12),(129,-86,6),
             (138,-23,10),(124,73,12),(38,98,13),(-66,86,4),(-133,57,9),(-128,-5,16)]
    return cloth_surface((4,3,37),outline,(RUST,RUST,OAT,RUST))


def magazine_steps():
    return ''.join(book((-195+64*i,-103,16*i,176-2*i,103,16*(i+1)),tint,art)
                   for i,(tint,art) in enumerate(((NAVY,'kid_moon'),(SAGE,'kid_hills'),
                                                  (RUST,COVER),(BLUE,'kid_moon'),(TEAL,COVER))))


def lamp(height,shade_radius):
    base=straight_oval(0,0,shade_radius*.71,shade_radius*.71,0,15,INK)
    pole=straight_oval(0,0,8,8,10,height-19,STEEL)
    crown=straight_oval(0,0,34,34,height-31,height-12,CREAM)
    shade=ring_band(0,0,(height-97,shade_radius-6,shade_radius),
                    (height,shade_radius*.63,shade_radius*.63+6),OAT)
    trim=ring_band(0,0,(height-98,shade_radius-7,shade_radius+2),
                   (height-93,shade_radius-7,shade_radius+2),RUST)
    return base+pole+crown+shade+trim


def snack_bowl():
    dish=bowl_shell(0,0,0,67,79,116,SAGE,CREAM)
    kernels=[]
    for x,y,r,z in ((-44,-33,24,11),(-14,-39,19,24),(22,-39,22,19),(56,-20,19,10),
                     (-47,13,25,15),(-14,2,24,30),(21,8,19,39),(49,26,19,21),
                     (-25,44,20,14),(12,42,21,27),(106,-77,16,0),(132,-55,10,0)):
        kernels.append(oval([(z,x,y,r*.6),(z+r*.43,x,y,r),(z+r*.91,x,y,r*.61)],
                            'kitchen_crumb' if x%2 else CREAM,sides=8))
    return dish+''.join(kernels)


def controller():
    shell=bevel((-82,-49,7,82,41,33),6,NAVY)
    grips=slab([(-83,-40),(-49,-27),(-39,-8),(-59,65),(-85,79),(-107,63),(-106,32)],0,29,NAVY)
    grips+=slab([(83,-40),(106,32),(107,63),(85,79),(59,65),(39,-8),(49,-27)],0,29,NAVY)
    direction=(block((-62,-23,31,-52,18,38),INK)+block((-76,-8,31,-38,3,38),INK))
    sticks=''.join(straight_oval(x,21,14,14,30,43,INK) for x in (-28,28))
    buttons=''.join(straight_oval(x,y,7,7,31,37,t) for x,y,t in (
        (54,-16,CORAL),(67,-5,CREAM),(53,7,MINT),(42,-5,TEAL)))
    return shell+grips+direction+sticks+buttons


def disc_cases():
    return ''.join(book((-105+i*9,-86+i*5,z,105+i*9,86+i*5,z+12),tint,art)
                   for i,(z,tint,art) in enumerate(((0,NAVY,'kid_moon'),(12,RUST,COVER),
                                                    (24,TEAL,'kid_hills'))))


def tissues():
    base=bevel((-104,-78,0,104,78,81),5,TEAL)
    panel=bevel((-100,-74,75,100,74,86),2,MINT)
    slit=block((-68,-13,85,68,13,87),INK)
    left=prism([(-6,84),(4,84),(18,116),(4,134),(-3,128)],-49,15,CREAM)
    right=prism([(-1,85),(7,85),(14,117),(0,125),(-7,119)],13,49,CREAM)
    return base+panel+slit+left+right


def plant():
    vessel=bowl_shell(0,0,0,109,63,86,RUST,RUST)
    soil=straight_oval(0,0,71,71,83,93,'bedroom/attic_tan')
    stalk=straight_oval(0,0,6,6,88,235,GREEN)
    leaves=''
    for profile,low,high,axis in (
        ([(1,155),(45,175),(102,165),(82,155),(38,145)],-11,11,'y'),
        ([(-97,199),(-59,205),(-2,178),(-7,165),(-62,184)],-13,13,'y'),
        ([(2,200),(34,220),(82,238),(67,211),(29,192)],-8,10,'x'),
        ([(-87,210),(-55,209),(0,188),(2,178),(-56,189)],-9,11,'x'),
        ([(-11,214),(26,237),(62,244),(38,216),(7,207)],-7,8,'y')):
        leaves+=prism(profile,low,high,GREEN,axis=axis)
    return vessel+soil+stalk+leaves


PREFABS={
    'sofa':lambda:upholstered(3,BLUE,OAT),
    'loveseat':lambda:upholstered(2,SAGE,MINT),
    'sectional':lambda:upholstered(3,RUST,OAT,chaise=True),
    'armchair':lambda:upholstered(1,OAT,SAGE),
    'cushion_square':square_cushion, 'cushion_leaning':leaning_cushion, 'cushion_steps':cushion_steps,
    'ottoman':ottoman, 'footstool_steps':footstool_steps, 'television_crt':television_crt,
    'television_flat':television_flat, 'remote_long':long_remote, 'remote_compact':small_remote,
    'media_console':media_console, 'coffee_table':coffee_table, 'side_table':side_table,
    'area_rug':area_rug, 'throw_blanket':blanket, 'magazine_steps':magazine_steps,
    'floor_lamp':lambda:lamp(414,109), 'table_lamp':lambda:lamp(204,78),
    'snack_bowl':snack_bowl, 'controller':controller, 'disc_case_stack':disc_cases,
    'tissue_box':tissues, 'plant_pot':plant,
}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    write_materials()
    for name,make in PREFABS.items():
        data=HEADER+'{\n"classname" "worldspawn"\n'+make()+'}\n'
        (args.output/f'living_{name}.map').write_text(data,encoding='ascii')


if __name__=='__main__':
    main()
