#!/usr/bin/env python3
"""Export unmarked kitchen props and walkable arrangements as Quake II MAPs."""

import argparse
from math import cos, pi, sin, tau
from pathlib import Path
from random import Random

from PIL import ImageDraw

from generate_bathroom import BASE, disc, material
from generate_bath_prefabs import HEADER, bevel, block, bottle_shape, loft, oval, straight_oval
from generate_build_prefabs import prism
from generate_garage_prefabs import finish, ring_band, ring_sections, slab
from generate_sandkeep_materials import write_wal
from platoon_palette import load_palette

CREAM = 'enamel'
STEEL = 'kitchen_steel'
DARK = 'toy_ink'
BLUE = 'toy_blue'
TEAL = 'toy_aqua'
MINT = 'toy_mint'
CORAL = 'toy_coral'
CRUST = 'kitchen_crust'
CRUMB = 'kitchen_crumb'
GREEN = 'kitchen_green'
APPLE = 'kitchen_apple'
BANANA = 'kitchen_banana'
CHEESE = 'kitchen_cheese'
COOKIE = 'kitchen_cookie'
WOOD = 'kit_beech'

# The paper, glaze and food finishes contain no lettering or product marks.
def write_materials():
    surfaces = {
        STEEL: finish((163, 176, 176), lambda x,y: 6*cos(tau*y/7)+13*sin(tau*y/128)),
        CRUST: finish((163, 100, 52), lambda x,y: 7*cos(tau*(x-y)/32)),
        CRUMB: finish((231, 198, 144), lambda x,y: 5*cos(tau*(x+y)/16)),
        GREEN: finish((108, 150, 68), lambda x,y: 9*cos(tau*(x-y)/16)),
        APPLE: finish((182, 58, 51), lambda x,y: 15*cos(tau*x/128)+7*sin(tau*(x+y)/64)),
        BANANA: finish((225, 184, 62), lambda x,y: 7*cos(tau*x/32)+4*cos(tau*(x-y)/64)),
        CHEESE: finish((239, 180, 77), lambda x,y: 9*cos(tau*x/64)*sin(tau*y/128)),
        COOKIE: finish((175, 117, 69), lambda x,y: 7*cos(tau*(x-y)/21)),
    }
    random = Random(229)
    for name,color in ((CRUMB,(204,163,107)),(CRUST,(139,78,42)),(COOKIE,(140,84,49))):
        paint = ImageDraw.Draw(surfaces[name])
        for _ in range(210):
            x,y = random.randrange(128),random.randrange(128)
            radius = random.choices((1,2,3),(6,3,1))[0]
            paint.ellipse((x-radius,y-radius,x+radius,y+radius),fill=color)
    folder = BASE/'textures/bathroom'
    palette = load_palette()
    for name,image in surfaces.items():
        image.save(folder/(name+'.png'))
        write_wal(folder/(name+'.wal'),material(name),image,palette)


BREAD = [(-84,-82),(84,-82),(96,-65),(102,55),(91,81),(57,100),
         (-57,100),(-91,81),(-102,55),(-96,-65)]


def bread_slice(z, height, x=0, y=0):
    edge = loft([[(x+u*s,y+v*s,h) for u,v in BREAD]
                 for h,s in ((z,.95),(z+4,1),(z+height-4,1),(z+height,.96))],CRUST)
    crumb = slab([(x+u*.90,y+v*.90) for u,v in BREAD],z+height-1,z+height+1,CRUMB)
    return edge+crumb


def toast():
    return bread_slice(0,22)


def sandwich():
    slice1 = bread_slice(0,19)
    leaves = slab([(-99,-68),(-49,-87),(65,-84),(94,-62),(106,24),
                   (79,88),(-81,86),(-104,30)],19,32,GREEN)
    cheese = slab([(-89,-65),(74,-81),(100,-21),(97,77),(-79,88),(-97,15)],29,36,CHEESE)
    filling = slab([(x*.92,y*.91) for x,y in BREAD],35,48,APPLE)
    return slice1+leaves+cheese+filling+bread_slice(47,23,5,5)


def apple():
    contour = oval([(0,0,0,32),(17,0,0,56),(50,1,0,69),(79,2,1,66),
                    (108,3,0,50),(118,5,0,31)],APPLE,aspect=.91)
    stem = straight_oval(5,0,6,6,114,143,WOOD)
    leaf = slab([(5,0),(16,-16),(38,-16),(55,-6),(35,7),(16,8)],133,139,GREEN)
    return contour+stem+leaf


def bananas():
    pieces = []
    for offset,size in ((-23,1),(17,.95),(52,.83)):
        layers = [(x*size,s*size,y*size+offset,24*s*size)
                  for x,s,y in ((-120,.48,35),(-81,.88,0),(-29,1,-29),
                                 (36,.99,-31),(86,.7,-2),(117,.4,30))]
        pieces.append(bottle_shape(20,24,8,layers,BANANA,axis='x'))
        pieces.append(straight_oval(offset+30*size,10*size,8*size,9*size,
                                    115*size,124*size,WOOD,axis='x'))
    bridge = bevel((-122,-5,5,-107,75,30),3,GREEN)
    return ''.join(pieces)+bridge


def pizza():
    crust = slab([(-153,0),(85,-103),(116,-79),(132,0),(116,79),(85,103)],0,17,CRUST)
    sauce = slab([(-147,0),(84,-94),(115,-66),(120,0),(112,67),(82,94)],15,23,APPLE)
    cheese = slab([(-144,1),(86,-87),(106,-53),(112,0),(102,53),(87,88)],21,28,CHEESE)
    edge = slab([(77,-95),(86,-104),(118,-80),(134,0),(118,80),(86,104),(77,95)],10,34,CRUST)
    toppings = ''.join(straight_oval(x,y,r,r,27,31,APPLE)
                       for x,y,r in ((-66,0,13),(-18,9,18),(29,-37,16),
                                      (40,37,18),(79,8,16)))
    return crust+sauce+cheese+edge+toppings


def fried_egg():
    outline = [(-105,-26),(-71,-53),(-8,-60),(65,-55),(105,-31),(114,10),
               (90,52),(21,66),(-48,54),(-96,29)]
    white = loft([[(x*s,y*s,z) for x,y in outline]
                  for z,s in ((0,.91),(4,1),(10,1),(14,.92))],CREAM)
    yolk = oval([(11,22,6,29),(19,22,6,41),(32,22,6,35),(38,22,6,21)],CHEESE)
    return white+yolk


def cookie():
    dough = oval([(0,0,0,71),(4,0,0,82),(15,0,0,82),(21,0,0,75)],COOKIE,aspect=.92)
    chips = ''.join(slab([(x-8,y-2),(x+1,y-6),(x+7,y),(x+5,y+7),(x-6,y+5)],19,z,'bedroom/attic_leather')
                    for x,y,z in ((-46,-22,23),(-32,23,25),(-9,-42,24),
                                  (18,18,25),(43,-31,23),(53,9,24),(10,53,24)))
    return dough+chips


def cereal_box():
    shape = block((-103,-51,0,103,51,202),TEAL)
    slots = (block((-102,-51,201,102,-7,208),BLUE)+block((-102,7,201,102,51,208),MINT))
    flap = prism([(35,199),(48,199),(88,249),(81,254)],-103,103,TEAL)
    fold = block((-103,-53,44,103,-50,56),CREAM)
    return shape+slots+flap+fold


def bowl_shell(cx,cy,bottom,height,base_radius,radius,tint,trim=CREAM):
    floor = straight_oval(cx,cy,base_radius,base_radius,bottom,bottom+9,tint)
    body = ring_band(cx,cy,(bottom+8,base_radius-8,base_radius),
                     (height-5,radius-8,radius),tint)
    lip = ring_band(cx,cy,(height-6,radius-9,radius+2),(height,radius-9,radius+2),trim)
    return floor+body+lip


def plate():
    foot = straight_oval(0,0,101,101,0,9,CREAM)
    rim = ring_band(0,0,(8,96,103),(25,133,145),CREAM)
    edge = ring_band(0,0,(23,136,145),(27,136,145),TEAL)
    return foot+rim+edge


def bowl():
    return bowl_shell(0,0,0,83,82,130,CREAM,TEAL)


def mug():
    body = bowl_shell(0,0,0,131,57,63,MINT,CREAM)
    handle = ring_band(72,77,(-9,29,43),(9,29,43),MINT,axis='y',sides=12)
    return body+handle


def tumbler():
    cup = bowl_shell(0,0,0,149,50,69,BLUE,TEAL)
    foot = ring_band(0,0,(0,42,52),(13,42,52),TEAL)
    return cup+foot


def saucepan():
    body = bowl_shell(0,0,0,116,96,107,STEEL,STEEL)
    neck = bevel((92,-18,80,161,18,101),3,STEEL)
    grip = bevel((148,-20,80,285,20,112),5,DARK)
    return body+neck+grip


def skillet():
    pan = bowl_shell(0,0,0,43,107,129,DARK,STEEL)
    neck = bevel((113,-19,19,155,19,34),3,STEEL)
    grip = bevel((143,-21,11,290,21,37),5,DARK)
    return pan+neck+grip


def fork():
    grip = bevel((-192,-18,0,47,18,16),3,STEEL)
    root = slab([(27,-14),(61,-39),(106,-39),(106,39),(61,39),(27,14)],2,16,STEEL)
    tines = ''.join(slab([(98,y),(170,y),(181,y+4),(171,y+11),(98,y+11)],1,12,STEEL)
                    for y in (-35,-15,5,25))
    return grip+root+tines


def spoon():
    grip = bevel((-192,-16,0,48,16,16),3,STEEL)
    floor = oval([(0,106,0,59),(8,106,0,65)],STEEL,aspect=.69)
    sections = []
    for z,r,R in ((7,57,65),(24,77,85)):
        inner = disc(106,0,r,r*.69,z)
        outer = disc(106,0,R,R*.69,z)
        sections.append((inner,outer))
    return grip+floor+ring_sections(sections,STEEL)


def spatula():
    grip = bevel((-188,-25,0,-15,25,29),5,DARK)
    neck = bevel((-34,-11,3,51,11,18),2,STEEL)
    head = bevel((33,-56,0,64,56,17),3,STEEL)
    tip = bevel((149,-59,0,170,59,17),3,STEEL)
    slats = ''.join(bevel((57,y,0,158,y+12,16),2,STEEL) for y in (-56,-31,-6,19,44))
    return grip+neck+head+tip+slats


def rolling_pin():
    center = 37*cos(pi/12)
    barrel = oval([(-108,0,center,29),(-94,0,center,37),(89,0,center,37),
                   (105,0,center,28)],WOOD,axis='x')
    grips = ''.join(straight_oval(0,center,15,15,a,b,'bedroom/attic_tan',axis='x')
                    for a,b in ((-166,-103),(100,163)))
    collars = ''.join(straight_oval(0,center,18,18,a,b,STEEL,axis='x')
                      for a,b in ((-118,-101),(97,115)))
    return barrel+grips+collars


def cutting_board():
    base = bevel((-158,-89,0,112,89,21),4,WOOD)
    ends = ''.join(bevel((104,y,0,160,Y,21),3,WOOD) for y,Y in ((-44,-26),(26,44)))
    top = bevel((151,-38,0,173,38,21),4,WOOD)
    return base+ends+top


def toaster():
    footing = bevel((-123,-69,0,123,69,23),5,DARK)
    body = bevel((-130,-76,15,130,76,121),9,CREAM)
    slots = ''.join(block(bounds,STEEL) for bounds in (
        (-131,-77,112,131,-54,127),(-131,54,112,131,77,127),
        (-131,-54,112,-105,54,127),(105,-54,112,131,54,127),
        (-105,-8,117,105,9,127)))
    recesses = ''.join(block((-105,y,118,105,Y,121),DARK) for y,Y in ((-55,-8),(9,55)))
    lever = (block((129,-27,56,135,27,107),STEEL)
             +bevel((130,-20,83,158,20,98),3,DARK))
    controls = ''.join(straight_oval(x,40,12,12,-84,-74,TEAL,axis='y') for x in (-48,50))
    return footing+body+slots+recesses+lever+controls


def kettle():
    stand = straight_oval(0,0,78,78,0,12,DARK)
    body = oval([(10,0,0,66),(20,0,0,76),(85,0,0,84),
                 (131,0,0,65),(144,0,0,49)],CREAM)
    lid = straight_oval(0,0,53,53,139,150,STEEL)+straight_oval(0,0,19,19,148,170,DARK)
    handle = (bevel((-123,-20,42,-69,20,64),4,DARK)
              +bevel((-130,-20,52,-108,20,138),4,DARK)
              +bevel((-124,-20,122,-53,20,146),4,DARK))
    spout = oval([(65,0,61,25),(113,0,80,22),(162,0,120,14),(176,0,139,16)],
                 CREAM,axis='x')
    tip = ring_band(0,139,(174,8,17),(183,8,17),STEEL,axis='x',sides=12)
    return stand+body+lid+handle+spout+tip


def blender():
    base = bevel((-80,-75,0,80,75,86),9,CREAM)
    trim = bevel((-86,-79,6,86,79,21),4,DARK)
    dial = straight_oval(0,48,20,20,-85,-71,TEAL,axis='y')
    jar = bottle_shape(64,49,18,[(81,.72,0,0),(104,.75,0,0),(196,1,0,0)],
                       'window')
    lid = bevel((-69,-54,192,69,54,208),4,DARK)
    handle = (bevel((53,-20,106,101,20,128),3,TEAL)
              +bevel((85,-20,116,105,20,189),3,TEAL)
              +bevel((55,-20,174,102,20,191),3,TEAL))
    return base+trim+dial+jar+lid+handle


def mixer():
    stand = bevel((-122,-63,0,122,63,23),5,CORAL)
    foot = bevel((63,-43,19,120,43,146),8,CORAL)
    head = bevel((-90,-46,131,122,46,182),9,CORAL)
    bowl = bowl_shell(-33,0,20,96,50,75,STEEL,STEEL)
    spindle = straight_oval(-41,0,7,7,68,136,STEEL)
    wires = ''.join(block((x,-15,63,x+4,15,104),STEEL) for x in (-51,-34))
    knob = straight_oval(87,150,12,12,-50,-42,DARK,axis='y')
    return stand+foot+head+bowl+spindle+wires+knob


def tray_steps():
    result = []
    for i,tint in enumerate((TEAL,CREAM,MINT,CREAM)):
        left,z = -185+i*64,i*16
        right = 169-i*3
        result.append(bevel((left,-104,z,right,104,z+16),2,tint))
        for y,Y in ((-106,-99),(99,106)):
            result.append(block((left+9,y,z+10,right-9,Y,z+14),BLUE))
        for y,Y in ((-100,-88),(88,100)):
            result.append(bevel((left+10,y,z+14,right-10,Y,z+18),1,tint))
    return ''.join(result)


def board_steps():
    result = []
    for i,tint in enumerate((WOOD,'bedroom/attic_tan',WOOD,'bedroom/attic_tan',WOOD)):
        x,z = -224+i*68,i*16
        X,y,Y = 189-i*2,-89+i*2,89-i*2
        result.append(bevel((x,y,z,X,Y,z+16),2,tint))
        for y0,y1 in ((y-1,y+1),(Y-1,Y+1)):
            result.append(block((x+7,y0,z+4,X-7,y1,z+9),'kit_beech_end'))
    return ''.join(result)


def toaster_oven():
    floor = block((-173,-132,0,173,132,24),STEEL)
    sidewalls = ''.join(block(bb,CREAM) for bb in (
        (-182,-131,21,-126,132,149),(126,-131,21,182,132,149),
        (-126,105,21,126,132,138),(-182,-133,136,182,132,167)))
    lip = block((-182,-137,132,182,-129,147),DARK)
    path = prism([(-275,0),(-132,0),(-132,24)],-115,115,STEEL)
    door = prism([(-264,1.6),(-144,20.5),(-144,24),(-264,4.6)],-91,91,'window')
    grille = ''.join(block((-115,y,23,115,y+3,26),STEEL) for y in range(-87,101,19))
    knobs = ''.join(straight_oval(154,z,16,16,-146,-127,DARK,axis='y') for z in (54,102))
    trim = bevel((-178,-137,153,177,-129,162),2,TEAL)
    return floor+sidewalls+lip+path+door+grille+knobs+trim


PREFABS = {
    'toast': toast, 'sandwich': sandwich, 'apple': apple, 'banana_bunch': bananas,
    'pizza_slice': pizza, 'fried_egg': fried_egg, 'cookie': cookie, 'cereal_box': cereal_box,
    'plate': plate, 'bowl': bowl, 'mug': mug, 'tumbler': tumbler, 'saucepan': saucepan, 'skillet': skillet,
    'fork': fork, 'spoon': spoon, 'slotted_spatula': spatula, 'rolling_pin': rolling_pin,
    'cutting_board': cutting_board, 'toaster': toaster, 'kettle': kettle, 'blender': blender, 'stand_mixer': mixer,
    'tray_steps': tray_steps, 'board_steps': board_steps, 'toaster_oven_open': toaster_oven,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    write_materials()
    for name,make in PREFABS.items():
        map_text = HEADER+'{\n"classname" "worldspawn"\n'+make()+'}\n'
        (args.output/f'kitchen_{name}.map').write_text(map_text,encoding='ascii')


if __name__ == '__main__':
    main()
