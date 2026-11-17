#!/usr/bin/env python3
"""Build unmarked sand toys, packed-sand structures and natural scatter."""

import argparse
from math import cos, hypot, pi, sin, tau
from pathlib import Path

from generate_bathroom import BASE, material, rounded_rectangle
from generate_bath_prefabs import HEADER, bevel, block, bottle_shape, loft, oval, straight_oval
from generate_build_prefabs import prism
from generate_garage_prefabs import finish, flat_ring, ring_band, ring_sections, slab
from generate_sandkeep_materials import write_wal
from generate_switchyard import convex
from platoon_palette import load_palette

SAND = 'sandbox/kit_damp'
TOP = 'sandbox/kit_sand'
ROCK = 'sandbox/kit_rock'
WARM_ROCK = 'sandbox/kit_rock_warm'
BARK = 'sandbox/kit_bark'
ENDGRAIN = 'sandkeep/wood_end'
BLUE = 'toy_blue'
NAVY = 'toy_navy'
ORANGE = 'toy_orange'
YELLOW = 'toy_lemon'
TEAL = 'toy_aqua'
RED = 'toy_coral'
RUBBER = 'garage_tread'
CREAM = 'enamel'

OCTAGON = [(24, 10), (10, 24), (-10, 24), (-24, 10),
           (-24, -10), (-10, -24), (10, -24), (24, -10)]


def write_materials():
    texture_dir = BASE / 'textures/sandbox'
    palette = load_palette()
    speckle = lambda x,y: ((x * 19 + y * 41) ^ (x * y * 3)) % 15 - 7
    grain = lambda x,y: 9*sin(tau*x/32 + sin(tau*y/128))+5*sin(tau*x/8)
    textures = {
        SAND: finish((184, 139, 87), lambda x,y: speckle(x,y)+3*cos(tau*y/32)),
        TOP: finish((205, 161, 106), lambda x,y: speckle(x,y)+4*cos(tau*(x+y)/64)),
        ROCK: finish((133, 135, 126), lambda x,y: speckle(x,y)+8*cos(tau*(x+y)/128)),
        WARM_ROCK: finish((146, 120, 97), lambda x,y: speckle(x,y)+7*cos(tau*(x+y)/64)),
        BARK: finish((106, 74, 50), grain),
    }
    for name, image in textures.items():
        leaf = name.split('/')[-1]
        image.save(texture_dir / (leaf + '.png'))
        write_wal(texture_dir / (leaf + '.wal'), name, image, palette)


def tiers(outline, layers, tint, *, top=None):
    """Loft one plan outline with uniform scales and optional horizontal shifts."""
    return loft([[(x*u+dx, y*u+dy, z) for x,y in outline] for z,u,dx,dy in layers],
                tint, top=top)


def packed(bounds, edge=8):
    x,y,z,X,Y,Z = bounds
    outline = rounded_rectangle(0,0,(X-x)/2,(Y-y)/2,edge,0)
    outline = [(a,b) for a,b,_ in outline]
    return tiers(outline, [(z,1,(x+X)/2,(y+Y)/2),
                           (Z,.93,(x+X)/2,(y+Y)/2)], SAND, top=TOP)


def arch_ring(cx, z, inner, outer, near, far, tint):
    def curve(r):
        return [(cx+round(r*cos(i*pi/8),3),z+round(r*sin(i*pi/8),3)) for i in range(9)]
    a,b = curve(inner),curve(outer)
    return ''.join(prism([a[i],a[i+1],b[i+1],b[i]],near,far,tint,axis='y')
                   for i in range(8))


def pail():
    body = straight_oval(0,0,88,88,0,12,ORANGE)
    wall = ring_band(0,0,(10,75,88),(143,103,116),ORANGE)
    rim = ring_band(0,0,(142,101,119),(155,101,119),YELLOW)
    handle = arch_ring(0,136,113,122,-5,5,BLUE)
    journals = ''.join(straight_oval(0,135,20,20,a,b,BLUE,axis='x')
                       for a,b in ((-126,-106),(106,126)))
    return body+wall+rim+handle+journals


def tipped_bucket():
    # Integer profile, with a genuinely empty half-round interior.
    outline = [(-144,0),(-132,56),(-102,102),(-55,132),(0,144),
               (55,132),(102,102),(132,56),(144,0)]
    def profile(scale,y):
        return [(x*scale,z*scale,y) for x,z in outline]
    bands = [(-185,.9,1.05),(-168,.86,1), (133,.735,.84)]
    sections = [(profile(inner,y),profile(outer,y)) for y,inner,outer in bands]
    shell = ''.join(loft([[a[i],a[i+1],b[i+1],b[i]] for a,b in (start,end)],
                          tint,axis='y')
                    for start,end,tint in zip(sections,sections[1:],(TEAL,BLUE))
                    for i in range(8))
    back = loft([profile(.84,133),profile(.84,146)],BLUE,axis='y')
    tags = ''.join(bevel((x,-145,22,X,-101,47),5,NAVY) for x,X in ((-145,-125),(125,145)))
    return shell+back+tags


def spade():
    tray = bottle_shape(87,60,22,[(0,.89,89,0),(10,1,89,0)],BLUE)
    lips = ''.join(bevel(bounds,3,TEAL) for bounds in (
        (25,-61,7,154,-45,30),(25,45,7,154,61,30),(12,-54,7,39,54,34)))
    shaft = straight_oval(0,21,15,15,-139,32,ORANGE,axis='x')
    grip = flat_ring(-170,0,25,43,0,28,ORANGE,sides=8)
    return tray+lips+shaft+grip


def rake():
    handle = straight_oval(0,25,15,15,-158,99,'sandkeep/wood',axis='x')
    palm = bevel((-183,-46,0,-147,46,44),5,ORANGE)
    head = bevel((74,-104,0,111,104,38),6,RED)
    fingers = ''.join(prism([(101,9),(161,6),(166,13),(110,32)],y,y+12,RED,axis='y')
                       for y in range(-91,92,29))
    return handle+palm+head+fingers


def sieve():
    rim = ring_band(0,0,(0,104,122),(31,104,122),YELLOW)
    bars = ''.join(block((x-3,-half,1,x+3,half,8),TEAL)
                   for x,half in ((-75,74),(-50,94),(-25,99),(0,105),(25,99),(50,94),(75,74)))
    bars += ''.join(block((-half,y-3,1,half,y+3,8),TEAL)
                    for y,half in ((-75,74),(-50,94),(-25,99),(0,105),(25,99),(50,94),(75,74)))
    tabs = ''.join(bevel((x,-38,0,X,38,19),3,NAVY) for x,X in ((-156,-109),(109,156)))
    return rim+bars+tabs


def turret_mold():
    body = ring_band(0,0,(0,90,108),(101,65,82),TEAL)
    cap = straight_oval(0,0,83,83,99,120,TEAL)
    foot = ring_band(0,0,(0,90,114),(12,90,114),NAVY)
    tips = ''.join(straight_oval(x,y,22,22,111,138,TEAL) for x,y in (
        (-49,-40),(-49,40),(49,-40),(49,40)))
    return body+cap+foot+tips


def dump_truck():
    undercarriage = bevel((-221,-83,22,230,83,52),7,NAVY)
    deck = block((-212,-83,51,80,83,64),YELLOW)
    bulkhead = bevel((61,-86,64,91,86,116),5,YELLOW)
    rails = ''.join(bevel((-212,y,62,78,Y,108),4,YELLOW)
                    for y,Y in ((-90,-75),(75,90)))
    face = bevel((91,-81,42,242,81,103),8,ORANGE)
    glass = prism([(94,97),(234,97),(207,154),(120,154)],-61,61,NAVY,axis='y')
    lid = bevel((116,-64,147,214,64,165),4,ORANGE)
    tailgate = prism([(-371,0),(-212,0),(-212,64)],-59,59,YELLOW,axis='y')
    center = 45*cos(pi/12)
    wheels = ''.join(straight_oval(x,center,45,45,a,b,RUBBER,axis='y')
                     +straight_oval(x,center,24,24,u,v,ORANGE,axis='y')
                     for x in (-164,-56,170) for a,b,u,v in (
                         (-106,-68,-112,-101),(68,106,101,112)))
    return undercarriage+deck+bulkhead+rails+face+glass+lid+tailgate+wheels


def watering_can():
    drum = bottle_shape(90,64,25,[(0,.9,0,0),(15,1,0,0),(102,1,0,0),
                                  (127,.83,-3,0)],BLUE)
    filler = flat_ring(-18,0,34,48,124,147,TEAL)
    bail = (bevel((-133,-19,43,-74,19,62),4,NAVY)
            +bevel((-139,-20,49,-116,20,135),4,NAVY)
            +bevel((-130,-18,123,-49,18,147),4,NAVY))
    pipe = oval([(67,0,62,26),(113,0,70,22),(161,0,106,16),(191,0,127,18)],
                BLUE,axis='x')
    rose = straight_oval(0,127,29,29,184,206,TEAL,axis='x')
    return drum+filler+bail+pipe+rose


def coping(cx,cy,z,scale,skips=()):
    result=[]
    def section(k,u,t):
        a,b=OCTAGON[k-1],OCTAGON[k]
        return (cx+u*(a[0]+(b[0]-a[0])*t),cy+u*(a[1]+(b[1]-a[1])*t))
    for k in range(len(OCTAGON)):
        if k in skips:
            continue
        def panel(t0,t1):
            return [section(k,scale,t0),section(k,scale,t1),
                    section(k,scale-1,t1),section(k,scale-1,t0)]
        result.append(slab(panel(0,1),z,z+16,SAND))
        result.append(slab(panel(.18,.82),z+16,z+52,SAND))
    return ''.join(result)


def tower(cx,cy,height,scale,skips=()):
    drum = tiers(OCTAGON,[(0,scale+1,cx,cy),(19,scale+1,cx,cy),
                           (height-12,scale-.35,cx,cy),(height,scale,cx,cy)],SAND,top=TOP)
    return drum+coping(cx,cy,height,scale,skips)


def sand_ramp():
    return prism([(-173,0),(173,0),(173,80)],-82,82,TOP,axis='y')


def castle_tower():
    # The +Y walk ends at the tower deck. Leave the south edge open.
    body = tower(0,0,112,5,(6,))
    path = prism([(-406,0),(-106,0),(-106,112)],-54,54,TOP)
    return body+path


def gate(cx=0,cy=0):
    support = ''.join(packed(bounds) for bounds in (
        (cx-172,cy-58,0,cx-71,cy+58,92),(cx+71,cy-58,0,cx+172,cy+58,92)))
    arch = arch_ring(cx,84,71,113,cy-55,cy+55,SAND)
    flags = ''.join(packed((cx+x,cy-38,z,cx+x+34,cy+14,z+35),4)
                    for x,z in ((-140,110),(-66,171),(-17,193),(37,181),(105,132)))
    caps = ''.join(tiers(OCTAGON,[(0,2.4,cx+x,cy),(79,2.1,cx+x,cy),
                                    (138,1.8,cx+x,cy)],SAND,top=TOP) for x in (-131,131))
    return support+arch+caps+flags


def castle_mound():
    base = tiers(OCTAGON,[(0,9,0,0),(20,8.4,0,0),(80,6.6,3,-3),
                           (97,5.5,5,-3)],TOP)
    center = tiers(OCTAGON,[(83,4.8,4,10),(110,4.5,4,10),(182,3.55,7,13),
                             (199,3.6,7,13)],SAND,top=TOP)
    cups = ''.join(tiers(OCTAGON,[(27,2.3,x,y),(81,2.15,x,y),(h,1.85,x,y)],
                         SAND,top=TOP)+coping(x,y,h,1.85,())
                   for x,y,h in ((-117,-103,113),(117,-103,121),
                                 (-106,94,134),(108,92,129)))
    return base+center+coping(7,13,199,3.6,())+cups


def sand_wall(bounds=(-176,-28,0,176,28,107)):
    x,y,z,X,Y,Z = bounds
    wall = packed(bounds)
    for u in range(x+16,X-30,76):
        wall += packed((u,y+7,Z-8,u+34,Y-7,Z+23),5)
    return wall


def castle_courtyard():
    front = gate(0,-269)
    banks = ''.join(packed(bounds) for bounds in (
        (-316,-269,0,-137,-222,122),(137,-269,0,316,-222,122),
        (-316,-234,0,-260,233,119),(260,-234,0,316,233,119),
        (-290,213,0,289,274,136),
    ))
    turrets = ''.join(tower(x,y,h,2.6) for x,y,h in (
        (-290,-245,157),(290,-245,157),(-292,223,164),(292,223,164)))
    terrace = packed((-198,115,0,198,214,96))
    ramp = prism([(-113,0),(132,0),(132,96)],-62,62,TOP)
    crowns = ''.join(packed(bounds,5) for bounds in (
        (-248,216,132,-204,266,168),(-149,216,132,-105,266,168),
        (-48,216,132,-4,266,168),(54,216,132,98,266,168),
        (154,216,132,198,266,168)))
    return front+banks+turrets+terrace+ramp+crowns


def bunker():
    floor = block((-154,-131,0,154,145,12),TOP)
    walls = ''.join(block(bounds,SAND) for bounds in (
        (-163,-134,12,-121,148,131),(121,-134,12,163,148,131),
        (-121,116,12,-64,148,131),(64,116,12,121,148,131),
        (-121,-134,12,121,-99,63),(-121,-134,104,121,-99,131),
        (-121,-134,63,-70,-99,104),(70,-134,63,121,-99,104)))
    roof = packed((-172,-143,130,172,154,172),14)
    skirts = ''.join(prism(points,-123,142,SAND,axis='y') for points in (
        [(-192,0),(-162,0),(-161,101),(-176,63)],
        [(162,0),(192,0),(176,63),(161,101)]))
    return floor+walls+roof+skirts


def outpost():
    deck = block((-145,-111,0,145,145,64),TOP)
    approach = prism([(-282,0),(-110,0),(-110,64)],-58,58,TOP)
    berms = ''.join(packed(bounds,8) for bounds in (
        (-146,-99,56,-110,147,113),(110,-99,56,146,147,113),
        (-130,113,56,130,148,114),(-113,-112,58,-64,-78,109),
        (64,-112,58,112,-78,109)))
    pole = straight_oval(116,104,5,5,64,219,'sandkeep/wood')
    flag = slab([(116,101),(188,104),(186,111),(116,108)],177,217,RED)
    return deck+approach+berms+pole+flag


def trench():
    route=[(0,-247),(0,-100),(98,29),(108,244)]
    chunks = []
    for (a,y),(b,Y),h in zip(route,route[1:],(76,97,81)):
        for low,high in ((-137,-63),(63,137)):
            outline=[(a+low,y),(a+high,y),(b+high,Y),(b+low,Y)]
            cx,cy=(a+b+low+high)/2,(y+Y)/2
            centered=[(x-cx,v-cy) for x,v in outline]
            chunks.append(tiers(centered,[(0,1,cx,cy),(h,.77,cx,cy)],SAND,top=TOP))
    return ''.join(chunks)


def barricade():
    return (packed((-190,-41,0,-28,20,74))
            +packed((-34,-25,0,39,66,65))
            +packed((33,30,0,190,95,81))
            +packed((132,79,0,188,150,71))
            +packed((-151,-56,0,-85,28,24)))


def crater():
    base = [(x,y) for x,y in OCTAGON]
    def outline(scale,z):
        return [(x*scale,y*scale,z) for x,y in base]
    return ring_sections([(outline(2.6,0),outline(7,0)),
                          (outline(4.25,29),outline(5.2,29))],TOP)


def stone(cx,cy,rx,ry,z,Z,tint,lean=(2,-4)):
    outline=[(-.94,-.23),(-.68,-.79),(.07,-1),(.82,-.66),
             (1,.09),(.61,.81),(-.28,1),(-.81,.57)]
    shape=[(round(rx*x),round(ry*y)) for x,y in outline]
    dx,dy=lean
    return tiers(shape,[(z,.82,cx,cy),(z+(Z-z)*.27,1,cx,cy),
                         (Z,.66,cx+dx,cy+dy)],tint)


def rock():
    return stone(0,0,125,90,0,93,ROCK,(-14,-7))


def rock_cluster():
    return (stone(33,18,92,80,0,85,ROCK,(-12,7))
            +stone(-58,-27,66,54,0,49,WARM_ROCK)
            +stone(88,-54,42,34,0,31,ROCK)
            +stone(-39,70,41,37,0,34,WARM_ROCK))


def rock_steps():
    # Shallow shelves overlap. Their exposed centers stay clear of bevel edges.
    return ''.join(stone(x,0,rx,ry,16*i,16*(i+1),tint,lean=(0,0))
                   for i,(x,rx,ry,tint) in enumerate((
                       (-64,248,150,ROCK),(-17,170,119,WARM_ROCK),
                       (21,110,96,ROCK),(56,57,76,WARM_ROCK))))


def pebbles():
    return ''.join(stone(x,y,rx,ry,0,h,tint) for x,y,rx,ry,h,tint in (
        (-86,-43,24,20,18,ROCK),(-45,28,30,23,21,WARM_ROCK),
        (-5,-27,20,16,12,WARM_ROCK),(31,38,27,25,23,ROCK),
        (51,-42,33,26,22,ROCK),(88,19,23,20,17,WARM_ROCK)))


def twig(a,b,r0,r1):
    dx,dy=b[0]-a[0],b[1]-a[1]
    length=hypot(dx,dy)
    u,v=-dy/length,dx/length
    def outline(position,r):
        return [(round(position[0]+u*r*cos(i*tau/8),3),
                 round(position[1]+v*r*cos(i*tau/8),3),
                 round(position[2]+r*sin(i*tau/8),3)) for i in range(8)]
    near,far=outline(a,r0),outline(b,r1)
    faces=[[near[i-1],near[i],far[i],far[i-1]] for i in range(8)]
    return convex([near,far,*faces],BARK,detail=True).replace(material(BARK),material(ENDGRAIN),2)


def stick():
    return (twig((-118,-14,13),(8,0,15),13,13)
            +twig((0,-1,15),(114,32,9),13,6)
            +twig((36,8,12),(63,54,12),7,4))


def fork():
    return (twig((-172,-53,26),(-34,-14,28),26,22)
            +twig((-43,-16,28),(141,38,17),22,12)
            +twig((-59,-19,26),(77,-112,13),17,7)
            +twig((43,9,24),(95,78,16),13,5)
            +twig((-118,-38,22),(-96,-96,18),12,5))


def stick_bridge():
    cross_section=[(-45,0),(45,0),(56,12),(44,27),(-45,27),(-55,10)]
    log = prism(cross_section,-177,177,BARK,end=ENDGRAIN)
    lips = (prism([(-234,0),(-177,0),(-177,27)],-43,43,ENDGRAIN,axis='y')
            +prism([(177,0),(234,0),(177,27)],-43,43,ENDGRAIN,axis='y'))
    return log+lips


PREFABS = {
    'pail': pail,
    'bucket_tipped': tipped_bucket,
    'spade': spade,
    'rake': rake,
    'sieve': sieve,
    'turret_mold': turret_mold,
    'dump_truck': dump_truck,
    'watering_can': watering_can,
    'castle_mound': castle_mound,
    'castle_gate': gate,
    'castle_tower': castle_tower,
    'castle_courtyard': castle_courtyard,
    'sand_bunker': bunker,
    'sand_outpost': outpost,
    'sand_trench': trench,
    'sand_barricade': barricade,
    'sand_ramp': sand_ramp,
    'sand_crater': crater,
    'sand_wall': sand_wall,
    'rock': rock,
    'rock_cluster': rock_cluster,
    'rock_steps': rock_steps,
    'pebbles': pebbles,
    'stick': stick,
    'forked_branch': fork,
    'stick_bridge': stick_bridge,
}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    write_materials()
    for name,make in PREFABS.items():
        map_text=HEADER+'{\n"classname" "worldspawn"\n'+make()+'}\n'
        (args.output/f'sandbox_{name}.map').write_text(map_text,encoding='ascii')


if __name__ == '__main__':
    main()
