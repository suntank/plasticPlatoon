#!/usr/bin/env python3
"""Export unmarked toy-scale laundry room brushes and their Quake II materials."""

import argparse
from math import cos, sin, tau
from pathlib import Path

from generate_bathroom import BASE, material
from generate_bath_prefabs import HEADER, bevel, block, bottle_shape, cloth_surface, oval, straight_oval
from generate_build_prefabs import prism
from generate_garage_prefabs import finish, flat_ring, ring_band, ring_sections, slab
from generate_kitchen_prefabs import bowl_shell
from generate_sandbox_prefabs import arch_ring
from generate_sandkeep_materials import write_wal
from platoon_palette import load_palette

CREAM='enamel'
STEEL='garage_steel'
DARK='toy_ink'
NAVY='toy_navy'
TEAL='laundry_teal'
GLASS='laundry_smoke'
CLAY='toy_coral'
LILAC='toy_lilac'
MINT='toy_mint'
TERRY='laundry_terry'
PINK='laundry_terry_rose'
GREEN='laundry_terry_sage'
WEAVE='laundry_wicker'
CORD='laundry_cord'
WOOD='kit_beech'
KRAFT='garage_kraft'


def write_materials():
    def loops(x,y):
        return 6*cos(tau*(x+y)/6)+6*cos(tau*y/4)+3*sin(tau*x/16)

    images={
        TEAL:finish((73,140,136),lambda x,y:4*cos(tau*(x+y)/128)),
        GLASS:finish((52,69,75),lambda x,y:13*cos(tau*(x-y)/128)+3*sin(tau*y/32)),
        TERRY:finish((163,190,194),loops),
        PINK:finish((177,116,125),loops),
        GREEN:finish((124,155,131),loops),
        WEAVE:finish((158,121,84),lambda x,y:17*cos(tau*x/16)*cos(tau*y/8)),
        CORD:finish((185,177,150),lambda x,y:9*cos(tau*x/5)+5*cos(tau*y/8)),
    }
    directory=BASE/'textures/bathroom'
    palette=load_palette()
    for name,image in images.items():
        image.save(directory/(name+'.png'))
        write_wal(directory/(name+'.wal'),material(name),image,palette)


# The drum and square outside casing share exact radial seam planes.
DRUM_POINTS=[(107,0),(96,48),(75,75),(48,96),(0,107),(-48,96),(-75,75),(-96,48),
             (-107,0),(-96,-48),(-75,-75),(-48,-96),(0,-107),(48,-96),(75,-75),(96,-48)]
CASE_POINTS=[(112,0),(112,56),(112,112),(56,112),(0,112),(-56,112),(-112,112),(-112,56),
             (-112,0),(-112,-56),(-112,-112),(-56,-112),(0,-112),(56,-112),(112,-112),(112,-56)]
DRUM_Z=157


def drum_profile(plane,scale=1,*,axis='y'):
    if axis=='x':
        return [(-250+x*scale,DRUM_Z+z*scale,plane) for x,z in DRUM_POINTS]
    return [(x*scale,DRUM_Z+z*scale,plane) for x,z in DRUM_POINTS]


def drum_rim(first,last,inner,outer,texture,*,axis='y'):
    rings=[(drum_profile(y,inner,axis=axis),drum_profile(y,outer,axis=axis))
           for y in (first,last)]
    return ring_sections(rings,texture,axis=axis)


def controls(accent,*,dryer=False):
    base=block((-185,-137,275,185,-127,331),CREAM)
    fascia=block((-173,-141,282,174,-135,316),accent)
    knobx=119 if dryer else 106
    dial=straight_oval(knobx,299,16,16,-152,-139,STEEL,axis='y')
    keypad=''.join(block((x,-144,292,x+13,-138,303),DARK) for x in (-19,6,31))
    panel=bevel((-156,-145,287,-78,-138,308),2,NAVY)
    light=block((-148,-147,298,-109,-144,302),MINT)
    return base+fascia+dial+keypad+panel+light


def washer():
    body=bevel((-185,-135,0,185,141,331),9,CREAM)
    seal=drum_rim(-156,-132,.88,1.19,NAVY)
    window=straight_oval(0,DRUM_Z,98,100,-147,-135,GLASS,axis='y')
    latch=bevel((100,-158,143,126,-151,177),2,STEEL)
    return body+seal+window+latch+controls(TEAL)


def washer_open():
    shell=''.join(block(b,CREAM) for b in (
        (-185,-135,0,185,141,45),(-185,-135,269,185,141,331),
        (-185,-135,44,-112,141,274),(112,-135,44,185,141,274),
        (-112,118,44,112,141,273)))
    ring=ring_sections([(drum_profile(y,1.025),[(x,DRUM_Z+z,y) for x,z in CASE_POINTS])
                        for y in (-135,121)],axis='y',tint=CREAM)
    liner=drum_rim(-135,117,1,1.028,STEEL)
    seal=drum_rim(-147,-133,1,1.14,NAVY)
    platform=block((-62,-146,47,62,118,64),STEEL)
    approach=prism([(-324,0),(-141,0),(-141,64)],-60,60,TEAL)
    door=drum_rim(-151,-138,.88,1.09,NAVY,axis='x')
    window=straight_oval(-250,DRUM_Z,98,100,-145,-137,GLASS,axis='x')
    hinge=block((-151,-161,123,-112,-132,190),STEEL)
    return shell+ring+liner+seal+platform+approach+door+window+hinge+controls(TEAL)


def dryer():
    body=bevel((-185,-136,0,185,140,331),9,CREAM)
    door=bevel((-131,-153,54,125,-130,264),9,NAVY)
    inner=bevel((-111,-157,68,101,-150,247),2,GLASS)
    handle=bevel((95,-162,131,126,-150,185),3,STEEL)
    vents=''.join(block((x,-139,22,x+24,-133,32),DARK) for x in range(-132,136,36))
    return body+door+inner+handle+vents+controls(LILAC,dryer=True)


def rectangular_tub(rx,ry,z,height,tint,*,side_slots=False):
    body=bevel((-rx,-ry,z,rx,ry,z+16),3,tint)
    body+=''.join(block(b,tint) for b in (
        (-rx,-ry,z+14,rx,-ry+9,height) if not side_slots else (-rx,-ry,z+14,rx,-ry+9,z+40),
        (-rx,ry-9,z+14,rx,ry,height) if not side_slots else (-rx,ry-9,z+14,rx,ry,z+40),
        (-rx,-ry+9,z+13,-rx+10,ry-9,height),
        (rx-10,-ry+9,z+13,rx,ry-9,height)))
    if side_slots:
        for y,Y in ((-ry,-ry+9),(ry-9,ry)):
            body+=block((-rx,y,height-22,rx,Y,height),tint)
            body+=''.join(block((x,y,z+39,x+12,Y,height-21),tint)
                          for x in range(-rx,rx-11,33))
            body+=block((rx-12,y,z+39,rx,Y,height-21),tint)
    lip=''.join(block(b,tint) for b in (
        (-rx-3,-ry-3,height-9,rx+3,-ry+12,height+2),
        (-rx-3,ry-12,height-9,rx+3,ry+3,height+2),
        (-rx-3,-ry+12,height-9,-rx+13,ry-12,height+2),
        (rx-13,-ry+12,height-9,rx+3,ry-12,height+2)))
    return body+lip


def sink():
    basin=rectangular_tub(171,98,139,212,CREAM)
    legs=''.join(bevel((x,y,0,x+21,y+21,147),3,NAVY)
                 for x in (-152,130) for y in (-79,57))
    rail=block((-150,66,34,151,82,49),NAVY)
    tap=straight_oval(0,76,12,12,209,260,STEEL)
    tap+=bevel((-11,22,246,11,81,265),3,STEEL)+block((-10,20,231,10,36,253),STEEL)
    knobs=''.join(straight_oval(x,72,11,11,209,229,STEEL) for x in (-49,49))
    return legs+rail+basin+tap+knobs


def cart():
    shelves=''.join(block((-155,-86,z,155,86,z+12),CREAM) for z in (4,106,208))
    posts=''.join(bevel((x,y,0,x+15,y+16,222),3,TEAL)
                  for x in (-153,138) for y in (-82,65))
    ends=''.join(block(b,TEAL) for b in (
        (-155,-89,215,-135,89,254),(135,-89,215,155,89,254),
        (-153,-89,247,-135,89,263),(135,-89,247,153,89,263)))
    casters=''.join(straight_oval(x,18,18,18,y,Y,DARK,axis='y')
                    for x in (-143,143) for y,Y in ((-88,-60),(60,88)))
    return shelves+posts+ends+casters


def ironing_board():
    board=bottle_shape(222,75,52,[(145,.96,0,0),(153,1,0,0),(168,.97,0,0)],TERRY)
    rails=''.join(prism(p,y,Y,STEEL,axis='y') for y,Y in ((-56,-44),(44,56)) for p in (
        [(-161,0),(-142,0),(151,149),(128,149)],
        [(142,0),(162,0),(-120,150),(-142,150)]))
    feet=''.join(bevel((x,-63,0,x+35,63,15),3,NAVY) for x in (-168,132))
    return board+rails+feet


def iron():
    outline=[(-123,0),(-47,-47),(66,-51),(94,-37),(94,37),(66,51),(-47,47)]
    sole=slab(outline,0,12,STEEL)
    upper=slab([(x*.90,y*.86) for x,y in outline],11,55,TEAL)
    rim=slab([(x*.83,y*.80) for x,y in outline],53,66,CREAM)
    handle=''.join(bevel(b,3,NAVY) for b in (
        (-67,-17,61,-43,17,100),(56,-18,60,78,18,103),(-67,-19,92,78,19,110)))
    dial=straight_oval(-11,-2,14,14,64,73,LILAC)
    return sole+upper+rim+handle+dial


def basket():
    return rectangular_tub(139,91,0,111,TEAL,side_slots=True)


def basket_full():
    tub=rectangular_tub(153,101,0,125,CREAM,side_slots=True)
    folds=''.join(bevel(b,e,tint) for b,e,tint in (
        ((-116,-67,13,129,78,44),6,GREEN),((-90,-57,39,127,70,84),8,PINK),
        ((-64,-73,76,126,75,122),7,TERRY),((-82,-41,109,61,75,151),6,LILAC),
        ((-126,-67,61,-67,60,92),5,MINT)))
    return tub+folds


def hamper():
    base=straight_oval(0,0,106,106,0,12,WEAVE)
    body=ring_band(0,0,(11,96,106),(198,112,122),WEAVE)
    rim=ring_band(0,0,(193,112,126),(211,112,126),WOOD)
    lid=oval([(199,0,0,119),(212,0,0,124),(222,0,0,114)],WEAVE)
    loop=(block((-27,-11,218,-15,11,239),WOOD)+block((15,-11,218,27,11,239),WOOD)
          +bevel((-27,-13,235,27,13,248),3,WOOD))
    return base+body+rim+lid+loop


def tipped_basket():
    floor=block((-122,-132,0,122,113,12),TEAL)
    walls=''.join(block(b,TEAL) for b in (
        (-122,-132,10,-110,113,44),(110,-132,10,122,113,44),
        (-122,-132,94,-110,113,127),(110,-132,94,122,113,127),
        (-122,-132,123,122,113,136),(-122,104,10,122,120,130)))
    ribs=''.join(block((x,y,42,X,y+11,96),TEAL) for y in range(-127,101,33) for x,X in (
        (-122,-110),(110,122)))
    edge=''.join(block(b,NAVY) for b in (
        (-127,-137,0,-107,-128,136),(107,-137,0,127,-128,136),
        (-127,-137,124,127,-128,138)))
    return floor+walls+ribs+edge


def detergent():
    body=bottle_shape(97,55,24,[(0,.92,0,0),(14,1,0,0),(150,1,0,0),
                                   (201,.75,-5,0)],TEAL)
    cap=straight_oval(-42,0,28,28,198,229,CREAM)
    grip=''.join(bevel(b,4,NAVY) for b in (
        (62,-19,105,130,19,131),(108,-19,117,132,19,199),(40,-18,181,128,18,207)))
    band=block((-57,-56,27,55,-52,35),MINT)
    return body+cap+grip+band


def softener():
    bottle=oval([(0,0,0,56),(11,0,0,64),(77,0,0,61),(122,3,0,56),
               (182,3,0,37),(200,3,0,27)],LILAC,aspect=.82)
    ring=straight_oval(3,0,28,28,194,205,NAVY)
    cap=oval([(202,3,0,29),(213,3,0,34),(236,3,0,34)],CREAM)
    return bottle+ring+cap


def sprayer():
    drape=bottle_shape(62,40,19,[(0,.87,0,0),(12,1,0,0),(103,.91,0,0),
                                   (139,.64,5,0),(159,.4,16,0)],'toy_orange')
    neck=straight_oval(16,0,26,26,150,178,NAVY)
    head=bevel((-37,-25,172,68,25,199),5,CREAM)
    jet=bevel((-50,-19,179,-31,19,195),3,NAVY)
    trigger=prism([(-34,169),(-18,172),(-9,141),(-23,135)],-11,11,CLAY,axis='y')
    return drape+neck+head+jet+trigger


def powder_box():
    side=block((-91,-58,0,91,58,193),CLAY)
    cap=block((-91,-58,190,91,58,200),CREAM)
    flap=prism([(43,194),(58,194),(92,244),(84,249)],-91,91,CLAY)
    base=block((-91,-61,19,91,-57,31),CREAM)
    return side+cap+flap+base


def bucket():
    shell=bowl_shell(0,0,0,131,75,106,CLAY,CREAM)
    handle=arch_ring(0,117,101,109,-5,5,STEEL)
    pins=''.join(straight_oval(0,117,13,13,a,b,NAVY,axis='x')
                 for a,b in ((-112,-96),(96,112)))
    return shell+handle+pins


def mop():
    shaft=straight_oval(0,15,12,12,-224,39,WOOD,axis='x')
    handle=bevel((-253,-16,0,-196,16,30),4,TEAL)
    plate=bevel((16,-57,6,61,57,29),4,NAVY)
    strands=''
    for y in range(-57,58,13):
        x=142+(19-abs(y)//4)
        strands+=slab([(47,y-6),(109,y-9),(x,y-5),(x-5,y+4),(57,y+7)],0,13,CORD)
    return shaft+handle+plate+strands


def broom():
    shaft=straight_oval(0,18,12,12,-241,19,WOOD,axis='x')
    grip=bevel((-264,-16,0,-217,16,32),4,NAVY)
    mount=bevel((5,-69,9,54,69,34),5,CLAY)
    bristles=''.join(slab([(46,y),(115,y-2),(136,y+7),(118,y+16),(46,y+12)],0,18,'garage_bristle')
                     for y in range(-70,65,13))
    return shaft+grip+mount+bristles


def dustpan():
    pan=slab([(-43,-85),(142,-94),(142,94),(-43,85),(-72,60),(-72,-60)],0,9,TEAL)
    rails=''.join(bevel(b,2,NAVY) for b in (
        (-55,-89,7,131,-78,40),(-55,78,7,131,89,40),(-68,-80,7,-48,80,48)))
    stem=bevel((-156,-16,4,-65,16,29),5,NAVY)
    hoop=flat_ring(-174,0,21,34,3,29,NAVY,sides=8)
    return pan+rails+stem+hoop


def sponge():
    dark=bevel((-75,-57,0,75,57,14),3,TEAL)
    blocky=bevel((-76,-58,11,76,58,38),6,'yellow')
    grooves=''.join(bevel((x,-54,32,x+12,54,40),2,'toy_lemon') for x in (-53,3,47))
    return dark+blocky+grooves


def clothespins():
    wins=[]
    for cx,cy,tint in ((-81,-54,WOOD),(40,15,TEAL),(-34,66,LILAC)):
        jaw=[(-59,3),(-38,0),(45,0),(60,6),(53,12),(-42,13)]
        pins=prism([(x+cx,z) for x,z in jaw],cy-11,cy+11,tint,axis='y')
        upper=[(-58,18),(-38,15),(53,14),(59,22),(40,29),(-46,28)]
        pins+=prism([(x+cx,z) for x,z in upper],cy-11,cy+11,tint,axis='y')
        wins.append(pins+straight_oval(cx,14,8,8,cy-14,cy+14,STEEL,axis='y'))
    return ''.join(wins)


def loose_clothes():
    zones=[
        ((-25,-22,31),[(-129,-74,7),(-73,-86,17),(14,-72,8),(61,-38,16),
                      (36,34,20),(-86,46,8),(-132,12,13)],(PINK,CLAY,PINK)),
        ((45,34,42),[(-36,-4,14),(51,-17,17),(124,8,8),(125,64,7),
                     (68,89,9),(-27,74,15),(-50,38,21)],(GREEN,TEAL,GREEN)),
    ]
    return ''.join(cloth_surface(center,outline,cols) for center,outline,cols in zones)


def folded_towels():
    return (bevel((-112,-82,0,111,81,27),5,TERRY)
            +bevel((-102,-76,25,110,66,49),4,PINK)
            +bevel((-98,-60,46,94,67,69),4,GREEN)
            +block((-94,-35,66,91,-28,70),TEAL))


def towel_steps():
    pieces=[]
    for i,tint in enumerate((NAVY,TERRY,GREEN,PINK,TERRY,GREEN)):
        x,z=-217+i*66,16*i
        X=211-i*2
        width=99-i*2
        pieces.append(bottle_shape((X-x)/2,width,17,
                                  [(z,1,(x+X)/2,0),(z+16,1,(x+X)/2,0)],tint))
        for y,Y in ((-width-1,-width+1),(width-1,width+1)):
            pieces.append(block((x+19,y,z+5,X-18,Y,z+9),TEAL))
    return ''.join(pieces)


def crate_steps():
    pieces=[]
    for i,tint in enumerate((NAVY,TEAL,LILAC,TEAL)):
        y,top=-153+i*76,16*(i+1)
        pieces.append(bottle_shape(95,38,15,[(0,1,0,y+38),(top,1,0,y+38)],tint))
        for x,X in ((-97,-92),(92,97)):
            pieces.append(block((x,y+14,top-10,X,y+60,top-4),CREAM))
    return ''.join(pieces)


def board_ramp():
    incline=prism([(-245,0),(-199,0),(174,97),(174,112)],-61,61,WOOD,axis='y')
    platform=block((174,-67,97,249,67,112),WOOD)
    supports=bevel((149,-55,0,221,55,100),7,TEAL)
    return incline+platform+supports


PREFABS={
    'washer_front':washer,'washer_open':washer_open,'dryer':dryer,
    'utility_sink':sink,'rolling_cart':cart,'ironing_board':ironing_board,'iron':iron,
    'basket_open':basket,'basket_full':basket_full,'hamper_tall':hamper,'basket_tipped':tipped_basket,
    'detergent_jug':detergent,'softener_bottle':softener,'spray_bottle':sprayer,'powder_box':powder_box,
    'bucket':bucket,'mop':mop,'broom':broom,'dustpan':dustpan,'sponge':sponge,
    'clothespins':clothespins,'loose_clothes':loose_clothes,'folded_towels':folded_towels,
    'towel_steps':towel_steps,'crate_steps':crate_steps,'board_ramp':board_ramp,
}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    write_materials()
    for name,make in PREFABS.items():
        data=HEADER+'{\n"classname" "worldspawn"\n'+make()+'}\n'
        (args.output/f'laundry_{name}.map').write_text(data,encoding='ascii')


if __name__=='__main__':
    main()
