#!/usr/bin/env python3
"""Export unmarked, toy-scale backyard brushes and their Quake II materials."""

import argparse
from math import cos, pi, sin, tau
from pathlib import Path
from random import Random
from shutil import copyfile

from PIL import ImageDraw

from generate_bathroom import BASE, material
from generate_bath_prefabs import HEADER, bevel, block, bottle_shape, loft, oval, straight_oval
from generate_build_prefabs import prism, timber_texture
from generate_garage_prefabs import finish, flat_ring, ring_band, slab
from generate_kitchen_prefabs import bowl_shell
from generate_sandbox_prefabs import arch_ring
from generate_sandkeep_materials import write_wal
from generate_switchyard import convex
from platoon_palette import load_palette

CLAY = 'sandkeep/garden_clay'
SOIL = 'sandkeep/garden_loam'
LEAF = 'sandkeep/garden_leaf'
PALE = 'sandkeep/garden_leaf_pale'
FABRIC = 'sandkeep/garden_canvas'
STONE = 'sandkeep/garden_paver'
CEDAR = 'sandkeep/garden_cedar'
STEEL = 'garage_steel'
CREAM = 'enamel'
TEAL = 'toy_aqua'
RED = 'toy_coral'
BLUE = 'toy_blue'
NAVY = 'toy_navy'
YELLOW = 'toy_lemon'
DARK = 'toy_ink'
RUBBER = 'garage_tread'
BRASS = 'bedroom/attic_brass'


def write_materials():
    def grit(x,y):
        return ((x*13+y*21) ^ (x*y*17)) % 15 - 7

    surfaces={
        CLAY:finish((174,104,71),lambda x,y:grit(x,y)*.4+5*cos(tau*y/16)),
        SOIL:finish((105,76,51),lambda x,y:grit(x,y)*1.6),
        LEAF:finish((61,114,62),lambda x,y:4*cos(tau*(x+y)/32)),
        PALE:finish((111,153,84),lambda x,y:6*cos(tau*x/16)),
        FABRIC:finish((144,167,155),lambda x,y:5*cos(tau*x/4)+5*cos(tau*y/8)),
        STONE:finish((155,149,125),lambda x,y:grit(x,y)+4*cos(tau*(x-y)/32)),
        CEDAR:timber_texture((160,107,70)),
    }
    rng=Random(71)
    for surface,colors in ((SOIL,((79,53,38),(139,105,74))),
                           (STONE,((134,127,108),(175,167,140)))):
        mark=ImageDraw.Draw(surfaces[surface])
        for i in range(181):
            x,y=rng.randrange(128),rng.randrange(128)
            r=rng.choice((1,1,1,2,3))
            mark.ellipse((x-r,y-r,x+r,y+r),fill=colors[i%2])
    palette=load_palette()
    folder=BASE/'textures/sandkeep'
    for name,image in surfaces.items():
        leaf=name.split('/')[-1]
        image.save(folder/(leaf+'.png'))
        write_wal(folder/(leaf+'.wal'),name,image,palette)


def blade(x,y,z,angle,length,rise,width,tint):
    """One thin solid leaf with a tapered point and an inclined blade."""
    co,si=cos(angle),sin(angle)
    outline=[(0,0),(.39,-1),(.71,-.65),(1,0),(.71,.65),(.39,1)]
    low=[(round(x+t*length*co-s*width*si,3),round(y+t*length*si+s*width*co,3),
          round(z+t*rise,3)) for t,s in outline]
    high=[(X,Y,Z+3) for X,Y,Z in low]
    sides=[[low[i-1],low[i],high[i],high[i-1]] for i in range(len(low))]
    return convex([low,high,*sides],material(tint),detail=True)


def petals(x,y,z,tint,radius):
    shape=[(.25,-.11),(.63,-.23),(.91,-.19),(1,0),(.91,.19),(.63,.23),(.25,.11)]
    pieces=[]
    for i in range(8):
        theta=i*tau/8
        co,si=cos(theta),sin(theta)
        footprint=[(round(x+radius*(a*co-b*si),3),round(y+radius*(a*si+b*co),3))
                   for a,b in shape]
        pieces.append(slab(footprint,z,z+5,tint))
    return ''.join(pieces)+straight_oval(x,y,radius*.27,radius*.27,z-1,z+8,YELLOW)


def sprig(x,y,base,height,spread,phase=0,flower=None):
    stem=straight_oval(x,y,3.5,3.5,base-3,base+height+2,LEAF)
    leaves=''.join(blade(x,y,base+height*u,phase+i*2.3,spread*s,r,w,
                        PALE if i%2==0 else LEAF)
                   for i,(u,s,r,w) in enumerate(((.26,1,22,11),(.43,.96,25,11),
                                                  (.59,.79,20,10),(.73,.62,16,8))))
    bloom=petals(x,y,base+height,flower,spread*.70) if flower else ''
    return stem+leaves+bloom


def terracotta():
    body=bowl_shell(0,0,0,133,69,104,CLAY,CLAY)
    edge=ring_band(0,0,(117,92,107),(126,92,107),CLAY)
    return body+edge


def daisies():
    soil=straight_oval(0,0,82,82,89,104,SOIL)
    stems=''.join(sprig(x,y,102,h,scale,i*.81,flower) for i,(x,y,h,scale,flower) in enumerate((
        (-38,-32,80,43,CREAM),(-13,31,133,48,CREAM),(34,4,108,45,CREAM),
        (23,-36,70,39,CREAM),(-47,16,103,41,CREAM))))
    return terracotta()+soil+stems


def trough(x,y,height,tint,soil=True):
    sides=''.join(block(bounds,tint) for bounds in (
        (-x,-y,8,x,-y+11,height),(-x,y-11,8,x,y,height),
        (-x,-y+11,8,-x+11,y-11,height),(x-11,-y+11,8,x,y-11,height)))
    bottom=bevel((-x,-y,0,x,y,15),3,tint)
    cap=''.join(block(bounds,tint) for bounds in (
        (-x-3,-y-3,height-10,x+3,-y+13,height+2),
        (-x-3,y-13,height-10,x+3,y+3,height+2),
        (-x-3,-y+13,height-10,-x+13,y-13,height+2),
        (x-13,-y+13,height-10,x+3,y-13,height+2)))
    dirt=block((-x+10,-y+10,height-35,x-10,y-10,height-14),SOIL) if soil else ''
    return sides+bottom+cap+dirt


def herb_box():
    case=trough(190,83,87,CEDAR)
    crowns=''.join(sprig(x,y,72,h,56,i*.42) for i,(x,y,h) in enumerate((
        (-143,-22,58),(-103,27,80),(-57,-24,65),(-6,26,76),
        (45,-25,78),(96,29,94),(141,-19,58))))
    return case+crowns


def window_box():
    basin=trough(191,68,85,TEAL)
    blooms=''.join(sprig(x,y,71,h,35,i*.42,flower) for i,(x,y,h,flower) in enumerate((
        (-145,-21,58,RED),(-102,20,89,CREAM),(-59,-22,61,RED),
        (-16,21,96,YELLOW),(40,-19,63,RED),(91,19,94,CREAM),(143,-20,59,YELLOW))))
    ribs=''.join(block((x,-72,6,x+6,-67,75),NAVY) for x in range(-158,165,39))
    return basin+blooms+ribs


def raised_bed():
    fill=block((-232,-134,0,232,134,96),SOIL)
    boards=''.join(block(bounds,CEDAR) for z,Z in ((0,46),(47,96)) for bounds in (
        (-244,-146,z,244,-132,Z),(-244,132,z,244,146,Z),
        (-244,-132,z,-230,132,Z),(230,-132,z,244,132,Z)))
    posts=''.join(block((x,y,0,x+19,y+19,99),CEDAR)
                  for x in (-247,228) for y in (-149,130))
    plants=''.join(sprig(x,y,96,h,40,i*.63,flower) for i,(x,y,h,flower) in enumerate((
        (-135,-95,72,CREAM),(-66,95,108,RED),(-27,-92,80,None),
        (51,94,91,YELLOW),(87,-94,89,CREAM),(160,89,102,RED),(175,-86,84,None))))
    return fill+boards+posts+plants


def seed_tray():
    floor=bevel((-148,-96,0,148,96,16),3,NAVY)
    wells=''.join(bowl_shell(x,y,13,58,33,41,NAVY,TEAL)
                   for x in (-94,0,94) for y in (-45,45))
    plugs=''.join(straight_oval(x,y,34,34,28,36,SOIL)+sprig(x,y,34,h,23,i*.93)
                   for i,(x,y,h) in enumerate((
        (-94,-45,47),(-94,45,37),(0,-45,33),(0,45,47),(94,-45,44),(94,45,54))))
    return floor+wells+plugs


def trellis_planter():
    basin=trough(146,79,99,CEDAR)
    pickets=''.join(bevel((x,37,86,x+9,49,275),2,CEDAR) for x in (-125,-70,-16,39,94,123))
    crossbars=''.join(block((-127,36,z,133,50,z+10),CEDAR) for z in (126,177,230,266))
    vines=''.join(sprig(x,y,85,h,40,i*.71,None if i%2 else RED)
                  for i,(x,y,h) in enumerate((
        (-107,18,145),(-67,-26,94),(-36,21,156),(7,-24,90),
        (44,21,183),(77,-26,107),(112,24,158))))
    return basin+pickets+crossbars+vines


def trowel():
    grip=bevel((-172,-23,0,-60,23,35),6,RED)
    ferrule=bevel((-77,-12,12,17,12,27),3,STEEL)
    profile=[(-5,-47),(52,-70),(114,-48),(154,0),(110,52),(52,67),(-5,44)]
    scoop=loft([[(x*(.94 if z==0 else 1),y*(.90 if z==0 else 1),z)
                  for x,y in profile] for z in (0,7)],STEEL)
    lips=''.join(prism(profile,a,b,STEEL) for a,b,profile in (
        (-48,-41,[(-1,5),(78,5),(103,11),(37,22),(-4,18)]),
        (41,48,[(-1,5),(78,5),(103,11),(37,22),(-4,18)])))
    return grip+ferrule+scoop+lips


def hand_fork():
    handle=bevel((-161,-22,0,-60,22,31),6,CEDAR)
    shaft=straight_oval(0,19,10,10,-68,46,STEEL,axis='x')
    neck=bevel((25,-53,5,78,53,24),5,STEEL)
    prongs=''.join(slab([(71,y),(146,y-1),(161,y+5),(145,y+12),(71,y+13)],1,16,STEEL)
                   for y in (-43,-6,31))
    return handle+shaft+neck+prongs


def shears():
    blades=slab([(5,-21),(59,-42),(101,-35),(132,-11),(104,8),(1,6)],4,19,STEEL)
    blades+=slab([(5,4),(134,19),(108,37),(54,36),(2,23)],9,25,STEEL)
    handles=''
    for sign in (-1,1):
        outline=[(x,y*sign) for x,y in ((-148,59),(-132,34),(-7,4),(13,13),(0,32),
                                      (-83,68),(-125,79))]
        handles+=slab(outline,0,27,RED)
    bolt=straight_oval(9,2,15,15,17,32,STEEL)
    return blades+handles+bolt


def fan_rake():
    shaft=straight_oval(0,14,14,14,-212,0,CEDAR,axis='x')
    handle=bevel((-239,-18,0,-187,18,29),4,NAVY)
    holder=slab([(-12,-10),(9,-30),(45,-62),(45,62),(9,30),(-12,10)],8,25,STEEL)
    fingers=''
    for y in range(-112,113,28):
        fingers+=slab([(36,y*.54-3),(154,y-4),(154,y+5),(36,y*.54+3)],3,9,STEEL)
        fingers+=block((150,y-3,0,157,y+4,8),STEEL)
    return shaft+handle+holder+fingers


def watering_can():
    base=straight_oval(0,0,85,85,0,11,STEEL)
    drum=bottle_shape(96,72,27,[(8,.92,0,0),(18,1,0,0),(129,1,0,0),
                                   (149,.89,0,0)],TEAL)
    lip=flat_ring(-25,0,40,53,144,161,STEEL)
    top_handle=arch_ring(-28,147,54,63,-6,6,STEEL)
    top_handle+=block((-93,-9,131,-75,9,153),STEEL)
    pour=oval([(78,0,67,25),(124,0,84,21),(173,0,120,18),(216,0,165,19)],
               STEEL,axis='x')
    rose=straight_oval(0,165,31,31,212,234,STEEL,axis='x')
    return base+drum+lip+top_handle+pour+rose


def wheelbarrow():
    tray=block((-158,-104,43,121,104,56),TEAL)
    rail=''.join(bevel((-160,y,53,121,Y,116),6,TEAL) for y,Y in ((-111,-94),(94,111)))
    nose=prism([(110,49),(139,70),(153,113),(120,117)],-105,105,TEAL,axis='y')
    ramp=prism([(-330,0),(-158,0),(-158,56)],-62,62,CEDAR,axis='y')
    axle=straight_oval(128,49,48,48,-22,22,RUBBER,axis='y')
    hub=''.join(straight_oval(128,49,25,25,a,b,STEEL,axis='y') for a,b in ((-29,-17),(17,29)))
    handles=''.join(prism(profile,y,Y,STEEL,axis='y') for y,Y in ((-96,-79),(79,96)) for profile in (
        [(-271,42),(-154,31),(-154,46),(-270,58)],
        [(-159,30),(104,32),(102,47),(-159,47)]))
    grips=''.join(bevel((-281,y,43,-223,Y,62),4,NAVY) for y,Y in ((-100,-77),(77,100)))
    legs=''.join(prism([(-120,39),(-101,40),(-68,0),(-89,0)],y,Y,STEEL,axis='y')
                 +block((-92,y,0,-38,Y,9),STEEL) for y,Y in ((-94,-78),(78,94)))
    return tray+rail+nose+ramp+axle+hub+handles+grips+legs


def hose():
    coil=''.join(flat_ring(0,0,r,r+12,0,13,LEAF,sides=16) for r in (63,84,105))
    extension=''.join(slab(points,0,13,LEAF) for points in (
        [(53,-17),(125,-13),(141,-20),(122,-28),(53,-29)],
        [(126,-26),(142,-25),(161,-58),(151,-64),(138,-48)],
        [(147,-59),(159,-64),(202,-65),(208,-50),(167,-48)]))
    tip=straight_oval(-58,8,9,9,200,221,BRASS,axis='x')
    return coil+extension+tip


def chair():
    poles=''.join(block((x,y,0,x+11,y+15,116),STEEL)
                  for x in (-77,66) for y in (-75,59))
    slats=''.join(bevel((-82,y,98,82,y+25,112),2,CEDAR) for y in range(-80,61,34))
    supports=''.join(prism([(51,103),(65,100),(100,242),(85,243)],x,x+11,STEEL)
                     for x in (-78,67))
    back=''.join(prism([(73,z),(88,z),(90,z+24),(76,z+24)],-83,83,CEDAR) for z in (166,198,224))
    arms=''.join(bevel((x,-69,142,X,79,156),3,CEDAR) for x,X in ((-91,-66),(66,91)))
    braces=''.join(block((x,-63,109,x+9,-52,148),STEEL) for x in (-80,71))
    return poles+slats+supports+back+arms+braces


def table():
    surface=flat_ring(0,0,14,165,146,160,CEDAR,sides=16)
    trim=flat_ring(0,0,145,166,138,149,STEEL,sides=16)
    feet=''.join(prism([(72,139),(85,144),(109,0),(93,0)],lo,hi,STEEL,axis='y')
                 for lo,hi in ((-96,-80),(80,96)))
    feet+=''.join(prism([(-85,144),(-72,139),(-93,0),(-109,0)],lo,hi,STEEL,axis='y')
                  for lo,hi in ((-96,-80),(80,96)))
    apron=''.join(block((x,y,127,x+16,155,148),STEEL) for x,y in ((-91,-90),(78,-90)))
    return surface+trim+feet+apron


def bench():
    feet=''.join(bevel((x,y,0,x+19,y+19,113),3,STEEL)
                 for x in (-194,175) for y in (-67,49))
    deck=''.join(bevel((-216,y,96,216,y+25,112),3,CEDAR) for y in range(-85,62,34))
    back_posts=''.join(prism([(49,109),(65,109),(94,219),(78,219)],x,x+14,STEEL)
                       for x in (-197,183))
    back=''.join(prism([(69,z),(87,z),(91,z+24),(74,z+24)],-216,216,CEDAR) for z in (150,179,209))
    ends=''.join(bevel((x,-72,141,X,68,155),3,CEDAR) for x,X in ((-214,-190),(190,214)))
    struts=''.join(block((x,-66,109,x+13,-53,144),STEEL) for x in (-200,189))
    return feet+deck+back_posts+back+ends+struts


def lounger():
    leg_frame=''.join(bevel((x,y,0,x+14,y+14,83),3,STEEL)
                       for x in (-177,-19,142) for y in (-58,45))
    deck=bevel((-198,-63,72,58,63,87),4,FABRIC)
    back=prism([(47,75),(163,154),(171,170),(46,90)],-65,65,FABRIC,axis='y')
    piping=''.join(prism([(49,72),(157,155),(165,175),(49,91)],y,Y,STEEL,axis='y')
                    for y,Y in ((-70,-61),(61,70)))
    slats=''.join(block((x,-62,84,x+5,62,89),STEEL) for x in range(-176,52,32))
    return leg_frame+deck+back+piping+slats


def parasol():
    base=straight_oval(0,0,75,75,0,18,STEEL)
    pole=straight_oval(0,0,8,8,10,400,STEEL)
    contour=[(24,10),(10,24),(-10,24),(-24,10),(-24,-10),(-10,-24),(10,-24),(24,-10)]
    panels=[]
    for i,(x,y) in enumerate(contour):
        a,b=contour[i-1]
        # Fixed radial directions give adjacent canopy panels the same seam planes.
        lower=[(a*7.5,b*7.5,330),(x*7.5,y*7.5,330),(x*.9,y*.9,391),(a*.9,b*.9,391)]
        upper=[(X,Y,Z+8) for X,Y,Z in lower]
        sides=[[lower[k-1],lower[k],upper[k],upper[k-1]] for k in range(4)]
        shell=convex([lower,upper,*sides],material(CREAM if i%2 else TEAL),detail=True)
        panels.append(shell)
    return base+pole+''.join(panels)+straight_oval(0,0,30,30,391,406,TEAL)


def stool():
    legs=''.join(bevel((x,y,0,x+15,y+15,58),3,STEEL)
                 for x in (-56,42) for y in (-48,34))
    cushion=bevel((-70,-61,46,70,61,64),5,FABRIC)
    return legs+cushion


def birdbath():
    foot=oval([(0,0,0,91),(15,0,0,91),(27,0,0,64),(39,0,0,43)],STONE)
    pedestal=oval([(34,0,0,47),(58,0,0,34),(122,0,0,32),(144,0,0,57)],STONE)
    base=straight_oval(0,0,83,83,140,155,STONE)
    basin=ring_band(0,0,(152,75,84),(178,120,132),STONE)
    water=straight_oval(0,0,93,93,159,163,'window')
    trim=ring_band(0,0,(176,122,136),(184,122,136),STONE)
    return foot+pedestal+base+basin+water+trim


def paver_steps():
    pieces=[]
    for i in range(6):
        x,z=-220+i*64,16*i
        X=226
        width=113-i*3
        pieces.append(bottle_shape((X-x)/2,width,16,
                                  [(z,1,(x+X)/2,0),(z+16,1,(x+X)/2,0)],STONE))
        for y,Y in ((-width-1,-width+1),(width-1,width+1)):
            pieces.append(block((x+16,y,z+2,X-14,Y,z+6),SOIL))
    return ''.join(pieces)


def planter_steps():
    parts=[]
    for i,tint in enumerate((CLAY,CLAY,TEAL,CLAY,TEAL)):
        x,top=-181+72*i,16*(i+1)
        parts.append(bottle_shape(36,94,11,[(0,1,x+36,0),(top,1,x+36,0)],tint))
        for y,Y in ((-95,-91),(91,95)):
            parts.append(block((x+10,y,top-12,x+62,Y,top-5),CREAM))
    return ''.join(parts)


def plank_ramp():
    board=prism([(-259,0),(-211,0),(176,97),(176,112)],-62,62,CEDAR,axis='y')
    upper=block((176,-66,96,249,66,112),CEDAR)
    support=block((155,-57,0,223,57,100),STONE)
    return board+upper+support


def soil_bag():
    bag=bottle_shape(153,87,40,[(0,.83,0,0),(13,1,0,0),(55,1,0,0),
                                   (78,.8,7,5)],SOIL)
    wrap=bevel((-98,-83,19,66,83,69),9,FABRIC)
    folds=''.join(prism([(-153,15),(-125,9),(-100,42),(-121,52)],y,Y,SOIL,axis='y')
                   for y,Y in ((-50,-20),(7,44)))
    return bag+wrap+folds


def gloves():
    pairs=[]
    for offset,tint in ((-74,FABRIC),(58,TEAL)):
        pairs.append(bevel((-57,offset-39,0,35,offset+38,17),5,tint))
        pairs.append(bevel((-87,offset-29,0,-45,offset+29,14),4,NAVY))
        for y,x in ((-33,58),(-16,78),(1,85),(18,77),(35,61)):
            width=11
            pairs.append(bevel((22,offset+y-3,0,x,offset+y+width,13),3,tint))
    return ''.join(pairs)


PREFABS={
    'terracotta_pot':terracotta, 'daisy_pot':daisies,
    'herb_box':herb_box, 'window_box':window_box, 'raised_bed':raised_bed,
    'seedling_tray':seed_tray, 'trellis_planter':trellis_planter,
    'hand_trowel':trowel, 'hand_fork':hand_fork, 'pruning_shears':shears,
    'fan_rake':fan_rake, 'watering_can':watering_can,
    'wheelbarrow':wheelbarrow, 'coiled_hose':hose,
    'patio_chair':chair, 'patio_table':table, 'bench':bench, 'lounger':lounger,
    'parasol':parasol, 'patio_stool':stool, 'birdbath':birdbath,
    'paver_steps':paver_steps, 'planter_steps':planter_steps, 'plank_ramp':plank_ramp,
    'soil_bag':soil_bag, 'gloves':gloves,
}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    write_materials()
    for name,make in PREFABS.items():
        data=HEADER+'{\n"classname" "worldspawn"\n'+make()+'}\n'
        (args.output/f'garden_{name}.map').write_text(data,encoding='ascii')
    for source in (BASE.parent / 'maps/prefabs').glob('garden_*.map'):
        destination = args.output / source.name
        if source.resolve() != destination.resolve():
            copyfile(source, destination)


if __name__=='__main__':
    main()
