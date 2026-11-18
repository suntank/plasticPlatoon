#!/usr/bin/env python3
"""Export unmarked, editable Quake II props for a toy-scale attic."""

import argparse
from math import cos, pi, sin, tau
from pathlib import Path

from PIL import Image, ImageDraw

from generate_bathroom import BASE, disc, material
from generate_bath_prefabs import HEADER, bevel, block, bottle_shape, loft, oval, straight_oval
from generate_build_prefabs import prism, timber_texture
from generate_garage_prefabs import finish, flat_ring, ring_band, slab
from generate_sandkeep_materials import write_wal
from platoon_palette import load_palette

OAK = 'bedroom/attic_wood'
HIDE = 'bedroom/attic_leather'
TAN = 'bedroom/attic_tan'
DUST = 'bedroom/attic_sheet'
QUILT = 'bedroom/attic_quilt'
BRASS = 'bedroom/attic_brass'
PAPER = 'bedroom/attic_paper'
CARD = 'garage_kraft'
INK = 'toy_ink'
FOAM = 'rubber'
STEEL = 'garage_steel'
ECRU = 'enamel'
MINT = 'kid_cotton_mint'
ROSE = 'kid_cotton_rose'
BLUE = 'toy_navy'


def dial():
    background = (216, 199, 156)
    hand = (49, 48, 44)
    image = Image.new('RGB', (128,128), background)
    draw = ImageDraw.Draw(image)
    draw.ellipse((7,7,120,120), outline=(126, 109, 82), width=2)
    for i in range(60):
        angle = tau*i/60
        outer = 53
        inner = 43 if i%5==0 else 50
        draw.line([(64+round(radius*sin(angle)),64+round(radius*cos(angle)))
                   for radius in (inner,outer)],fill=hand,width=3 if i%5==0 else 1)
    draw.line((64,64,43,50),fill=hand,width=5)
    draw.line((64,64,86,33),fill=hand,width=3)
    draw.ellipse((61,61,67,67),fill=hand)
    return image


def write_materials():
    # Archive fabrics have a broad fade and a fine weave visible at toy height.
    weave = lambda x,y: 5*cos(tau*(x+y)/4)+3*cos(tau*x/8)
    surfaces = {
        OAK: timber_texture((118,83,60)),
        HIDE: finish((104,69,57),lambda x,y: 3*cos(tau*(x-y)/8)+3*cos(tau*y/32)),
        TAN: finish((151,110,73),lambda x,y: 4*cos(tau*(x+y)/8)),
        DUST: finish((190,185,166),lambda x,y: weave(x,y)+4*cos(tau*y/128)),
        QUILT: finish((122,126,110),lambda x,y: weave(x,y)+6*cos(tau*(x+y)/32)),
        BRASS: finish((171,138,75),lambda x,y: 5*cos(tau*y/16)+8*cos(tau*y/64)),
        PAPER: finish((199,175,135),lambda x,y: 2*cos(tau*(x+y)/32)),
        'bedroom/attic_clockface': dial(),
    }
    folder = BASE/'textures/bedroom'
    palette = load_palette()
    for name,image in surfaces.items():
        leaf = name.split('/')[-1]
        image.save(folder/(leaf+'.png'))
        write_wal(folder/(leaf+'.wal'),name,image,palette)


def steamer_trunk():
    body = bevel((-200,-108,0,200,108,126),7,OAK)
    arch = [(-109,119),(109,119),(110,142),(86,170),(49,190),(-49,190),(-86,170),(-110,142)]
    lid = prism(arch,-204,204,HIDE)
    bands = [(-113,117),(113,117),(114,144),(88,174),(50,195),(-50,195),(-88,174),(-114,144)]
    trims = ''.join(prism(bands,x,x+18,BRASS) for x in (-164,146))
    latch = bevel((-30,-119,92,30,-106,132),4,BRASS)
    catch = block((-9,-122,104,9,-118,115),INK)
    corner = ''.join(bevel((x,y,0,x+28,Y,37),4,BRASS)
                     for x in (-202,174) for y,Y in ((-112,-98),(98,112)))
    return body+lid+trims+latch+catch+corner


def open_trunk():
    floor = block((-201,-121,0,201,116,12),MINT)
    walls = ''.join(block(bounds,OAK) for bounds in (
        (-208,-123,0,-191,121,110),(191,-123,0,208,121,110),
        (-191,102,0,191,121,108),
        (-191,-123,0,-64,-104,96),(64,-123,0,191,-104,96),
        (-64,-123,0,64,-104,48)))
    lip = ''.join(block(bounds,BRASS) for bounds in (
        (-208,-123,106,-190,121,111),(190,-123,106,208,121,111),
        (-191,101,105,191,121,110)))
    opening = prism([(-287,0),(-123,0),(-123,48)],-57,57,TAN)
    inner = prism([(-104,12),(28,12),(-104,48)],-57,57,TAN)
    lid = prism([(104,102),(120,99),(198,267),(183,274)],-206,206,HIDE)
    hinges = ''.join(block((x,99,95,x+41,127,118),BRASS) for x in (-160,119))
    return floor+walls+lip+opening+inner+lid+hinges


def suitcase():
    body = bevel((-143,-61,0,143,61,149),10,TAN)
    seam = bevel((-134,-63,9,134,-51,138),4,HIDE)
    face = bevel((-131,-67,14,131,-54,133),4,TAN)
    hardware = ''.join(bevel((x,-39,144,x+31,25,157),3,BRASS) for x in (-109,78))
    grip = (block((-57,-10,146,-43,10,182),HIDE)
            +block((43,-10,146,57,10,182),HIDE)
            +bevel((-57,-13,174,57,13,190),4,HIDE))
    feet = ''.join(block((x,y,0,x+33,y+13,13),INK)
                   for x in (-113,80) for y in (-61,48))
    return body+seam+face+hardware+grip+feet


def suitcase_steps():
    pieces = []
    for i,tint in enumerate((HIDE,TAN,BLUE,MINT,ROSE)):
        x,z = -201+66*i,16*i
        y,Y = -91+i*2,91-i*2
        X = 195-i*2
        pieces.append(bevel((x,y,z,X,Y,z+16),2,tint))
        pieces.append(block((x+6,y-1,z+6,X-6,y+2,z+9),HIDE))
        for latch_x in (x+16,min(x+43,X-26)):
            pieces.append(block((latch_x,y-4,z+6,latch_x+12,y+1,z+13),BRASS))
    return ''.join(pieces)


def files():
    base = block((-124,-88,0,124,88,12),CARD)
    walls = ''.join(block(bounds,CARD) for bounds in (
        (-124,-88,11,124,-78,93),(-124,78,11,124,88,100),
        (-124,-78,11,-115,78,100),(115,-78,11,124,78,92)))
    folders = ''.join(block((-105,y,12,104,y+11,z),tint)
                      +block((x,y, z-1,x+42,y+10,z+10),tint)
                      for y,z,x,tint in ((-54,105,-77,PAPER),(-28,127,45,MINT),
                                         (0,122,-5,PAPER),(26,119,-59,ROSE),(52,128,26,PAPER)))
    tape = block((-37,-91,22,37,-86,53),'garage_tape')
    return base+walls+folders+tape


def sheeted_chair():
    legs = ''.join(bevel((x,y,0,x+24,y+24,60),3,OAK)
                   for x in (-107,84) for y in (-95,81))
    seat = bevel((-122,-109,42,122,106,92),9,DUST)
    back = prism([(53,57),(105,57),(109,196),(86,223),(54,210)],-106,106,DUST)
    arms = ''.join(bevel((x,-93,60,X,71,134),8,DUST) for x,X in ((-127,-86),(86,127)))
    front = prism([(-109,33),(-95,28),(-94,99),(-110,100)],-92,90,DUST)
    folds = ''.join(prism([(-107,31),(-95,z),(-91,83),(-107,87)],x,x+w,DUST)
                    for x,w,z in ((-91,29,19),(-41,21,13),(14,36,24),(56,27,17)))
    return legs+seat+back+arms+front+folds


def rocking_chair():
    rails = []
    for x in (-83,67):
        rails.append(prism([(-107,0),(108,0),(108,16),(-107,16)],x,x+16,OAK))
        rails.append(prism([(-153,16),(-107,0),(-107,16),(-151,29)],x,x+16,OAK))
        rails.append(prism([(108,0),(154,17),(152,29),(108,16)],x,x+16,OAK))
    seat = bevel((-103,-82,93,103,63,112),5,OAK)
    legs = ''.join(block((x,y,11,x+13,y+15,104),OAK)
                   for x in (-81,69) for y in (-65,42))
    runners = ''.join(prism([(42,101),(60,102),(93,247),(75,249)],x,x+14,OAK)
                      for x in (-84,71))
    spindles = ''.join(prism([(49,110),(58,110),(90,237),(80,237)],x,x+9,OAK)
                       for x in (-46,-26,-6,14,34))
    crest = bevel((-87,68,233,88,97,259),3,OAK)
    arms = ''.join(bevel((x,-72,155,X,83,170),3,OAK) for x,X in ((-105,-78),(78,105)))
    braces = ''.join(block((x,-64,106,x+10,-53,157),OAK) for x in (-90,79))
    return ''.join(rails)+seat+legs+runners+spindles+crest+arms+braces


def dresser():
    carcass = block((-178,103,0,178,239,109),OAK)
    top = block((-191,103,100,191,243,112),OAK)
    steps = []
    for i in range(6):
        y,z = -277+i*64,i*16
        steps.append(block((-155,y,z,155,115,z+16),OAK))
        steps.append(block((-160,y-2,z+2,160,y+10,z+14),HIDE))
        for x in (-90,64):
            steps.append(bevel((x,y-9,z+4,x+26,y,z+11),2,BRASS))
    return carcass+top+''.join(steps)


def rafters():
    planks = []
    profiles = [[(-231,0),(231,0),(231,23),(-231,23)],
                [(-227,18),(-201,18),(13,251),(-1,275)],
                [(-13,251),(202,18),(228,18),(1,275)],
                [(-12,16),(12,16),(12,252),(-12,252)]]
    for y in (-94,75):
        planks.extend(prism(outline,y,y+18,OAK,axis='y') for outline in profiles)
    return ''.join(planks)+''.join(block((x,-100,0,x+30,102,20),TAN) for x in (-219,189))


def board_ramp():
    board = prism([(-249,0),(-204,0),(206,81),(206,96)],-57,57,OAK,axis='y')
    heel = block((156,-53,0,198,53,82),TAN)
    braces = ''.join(block((a,y,0,X,Y,27),OAK)
                     for a,X in ((35,58),(121,143)) for y,Y in ((-58,-49),(49,58)))
    return board+heel+braces


def hatch_stair():
    front,end,height = -224,192,160
    rail = prism([(front,0),(-175,0),(end,143),(end,height)],-64,64,OAK,axis='y')
    deck = block((end,-70,143,254,70,160),TAN)
    heel = block((165,-63,0,193,63,143),OAK)
    def rise(x):
        return (x-front)*height/(end-front)
    pieces = []
    for x in range(-194,167,42):
        z,Z = rise(x),rise(x+12)
        pieces.append(prism([(x,z-2),(x+12,Z-2),(x+12,Z+5),(x,z+5)],
                            -51,51,TAN,axis='y'))
    for a,b in ((-68,-57),(57,68)):
        pieces.append(prism([(front+8,1),(end,151),(end,175),(front+8,10)],a,b,OAK,axis='y'))
    for y in (-59,41):
        pieces.append(block((211,y,147,238,y+18,162),BRASS))
    return rail+deck+heel+''.join(pieces)


def gramophone():
    base = bevel((-109,-88,0,109,88,83),6,OAK)
    trim = bevel((-116,-94,75,116,94,91),5,TAN)
    disc_record = straight_oval(-21,-1,66,66,90,98,INK)+straight_oval(-21,-1,16,16,98,102,HIDE)
    pipe = (straight_oval(49,28,17,17,91,151,BRASS)
            +prism([(38,130),(56,130),(105,162),(105,178),(80,176)],18,40,BRASS,axis='y'))
    horn = ''.join(ring_band(30,168,a,b,BRASS,axis='x',sides=12) for a,b in (
        ((100,9,14),(127,16,22)),((127,16,22),(157,41,50)),((157,41,50),(166,47,54))))
    crank = bevel((106,-48,44,141,-35,63),3,BRASS)+bevel((133,-62,48,151,-43,69),3,INK)
    return base+trim+disc_record+pipe+horn+crank


def radio():
    shell = bevel((-124,-53,0,124,53,157),9,OAK)
    panel = bevel((-111,-58,14,111,-48,145),3,TAN)
    cloth = bevel((-103,-63,54,103,-56,137),3,QUILT)
    grill = ''.join(block((x,-65,58,x+5,-62,134),TAN) for x in range(-88,93,18))
    glass = bevel((-47,-64,19,47,-55,47),3,INK)
    knobs = ''.join(straight_oval(x,32,15,15,-72,-53,BRASS,axis='y') for x in (-81,81))
    return shell+panel+cloth+grill+glass+knobs


def film_reel():
    # Four rounded windows in each flange reveal the empty space between reels.
    base = flat_ring(0,0,87,103,0,9,STEEL)
    cap = flat_ring(0,0,87,103,46,55,STEEL)
    drum = flat_ring(0,0,12,47,8,47,INK)
    spokes = ''.join(slab(points,z,Z,STEEL) for z,Z in ((0,9),(46,55)) for points in (
        [(-11,-95),(11,-95),(18,95),(-18,95)],
        [(-95,-18),(95,-11),(95,11),(-95,18)]))
    hub = flat_ring(0,0,12,29,47,60,STEEL)
    ribbon = slab([(75,38),(91,26),(143,72),(136,81)],0,4,HIDE)
    ribbon += slab([(136,76),(145,72),(182,66),(185,77)],0,4,HIDE)
    return base+cap+drum+spokes+hub+ribbon


def camera():
    body = bevel((-98,-51,0,98,51,123),8,INK)
    trim = bevel((-94,-55,16,94,-47,115),3,TAN)
    mount = bevel((-57,-68,27,45,-51,102),5,STEEL)
    lens = (straight_oval(-5,65,42,42,-85,-61,INK,axis='y')
            + ring_band(-5,65,(-98,25,39),(-81,27,39),STEEL,axis='y',sides=12)
            + straight_oval(-5,65,27,27,-88,-83,'window',axis='y'))
    glass = bevel((55,-65,82,82,-51,103),3,'window')
    winder = bevel((-68,-25,118,-33,24,137),4,STEEL)
    return body+trim+mount+lens+glass+winder


def sewing_machine():
    platform = bevel((-160,-77,0,160,77,20),5,OAK)
    foot = bevel((-145,-53,18,143,53,47),6,INK)
    post = bevel((61,-41,37,131,41,164),8,INK)
    arm = prism([(-112,104),(-94,144),(114,164),(116,125)],-34,34,INK,axis='y')
    jaw = bevel((-124,-29,81,-85,29,122),6,INK)
    needle = straight_oval(-101,0,5,5,47,85,STEEL)+block((-117,-10,45,-94,14,48),STEEL)
    wheel = ring_band(0,120,(117,26,38),(141,27,39),STEEL,axis='x',sides=12)
    center = straight_oval(0,120,15,15,122,149,INK,axis='x')
    bridges = block((125,-32,116,133,32,123),STEEL)+block((125,-5,86,133,5,155),STEEL)
    return platform+foot+post+arm+jaw+needle+wheel+center+bridges


def form():
    iron = straight_oval(0,0,7,7,0,101,INK)
    feet = ''.join(slab(points,0,9,INK) for points in (
        [(-7,-6),(-54,-49),(-43,-59),(12,-14)],
        [(-8,-14),(47,-58),(57,-48),(8,-6)],
        [(-7,1),(-8,65),(8,65),(7,1)]))
    torso = bottle_shape(63,39,21,[(93,.69,0,0),(126,1,0,0),(151,.8,0,0),
                                     (187,.74,0,0),(231,1,0,0),(248,.51,0,0)],DUST)
    neck = straight_oval(0,0,20,20,244,262,TAN)
    knob = straight_oval(0,0,24,24,259,273,OAK)
    return iron+feet+torso+neck+knob


def rolled_rug():
    # The aged layers are visible through both ends of the rolled carpet.
    outer = ring_band(0,47,(-121,34,48),(121,34,48),QUILT,axis='x')
    lining = ring_band(0,47,(-124,30,40),(124,30,40),ROSE,axis='x')
    inner = ring_band(0,47,(-126,15,34),(126,15,34),TAN,axis='x')
    flare = prism([(-185,0),(0,0),(0,10),(-185,5)],-121,121,QUILT)
    border = ''.join(block((x,-179,4,x+5,-6,10),TAN) for x in (-115,109))
    return outer+lining+inner+flare+border


def frames():
    # Sloped front/back planes give the two frames an actual lean from the floor.
    def rail(x,X,z,Z,tint):
        def base(z):
            return -41+z*.31
        return prism([(base(z),z),(base(z)+10,z),(base(Z)+10,Z),(base(Z),Z)],x,X,tint)
    dark = (rail(-151,-33,0,12,OAK)+rail(-151,-33,135,147,OAK)
            +rail(-151,-139,11,137,OAK)+rail(-45,-33,11,137,OAK))
    small = (rail(3,107,0,11,TAN)+rail(3,107,114,126,TAN)
             +rail(3,14,10,115,TAN)+rail(96,107,10,115,TAN))
    painting = rail(10,101,8,119,'kid_hills')
    return dark+small+painting


def birdcage():
    base = straight_oval(0,0,88,88,0,13,BRASS)
    rim = flat_ring(0,0,76,87,72,81,BRASS)
    upper = flat_ring(0,0,76,87,128,137,BRASS)
    bars = []
    for i in range(16):
        t = i*tau/16
        x,y = round(81*cos(t),2),round(81*sin(t),2)
        bars.append(block((x-2.5,y-2.5,12,x+2.5,y+2.5,136),BRASS))
        tip_x,tip_y = round(18*cos(t),2),round(18*sin(t),2)
        # Each roof bar slants from the circular rim to the cap.
        bars.append(loft([[(u,v,z) for u,v in ((X-3,Y-3),(X+3,Y-3),(X+3,Y+3),(X-3,Y+3))]
                          for X,Y,z in ((x,y,133),(tip_x,tip_y,182))],BRASS))
    cap = straight_oval(0,0,24,24,179,190,BRASS)
    handle = ring_band(0,202,(-4,10,16),(4,10,16),BRASS,axis='y',sides=12)
    perch = straight_oval(0,63,7,7,-84,84,OAK,axis='x')
    return base+rim+upper+''.join(bars)+cap+handle+perch


def sled():
    runners = ''.join(prism(profile,y,y+13,STEEL,axis='y') for y in (-65,52) for profile in (
        [(-155,0),(139,0),(139,13),(-155,13)],
        [(139,0),(176,23),(175,42),(166,43),(139,13)]))
    legs = ''.join(block((x,y,10,x+17,y+13,44),STEEL) for x in (-117,-11,107) for y in (-65,52))
    slats = ''.join(bevel((-150,y,39,148,y+17,51),2,OAK) for y in range(-66,61,22))
    yoke = bevel((109,-94,49,138,94,66),4,HIDE)
    return runners+legs+slats+yoke


def ornaments():
    tints = (HIDE,MINT,'toy_lemon')
    chunks = []
    for (x,y,r),tint in zip(((-60,-31,39),(28,11,47),(103,-43,27)),tints):
        chunks.append(oval([(0,x,y,r*.44),(r*.43,x,y,r*.9),(r,x,y,r),
                            (r*1.52,x,y,r*.78),(r*1.79,x,y,r*.4)],tint))
        chunks.append(straight_oval(x,y,9,9,r*1.7,r*1.9,BRASS))
    return ''.join(chunks)


def blankets():
    return (bevel((-119,-90,0,119,90,28),5,QUILT)
            +bevel((-101,-77,27,109,72,53),5,ROSE)
            +bevel((-84,-65,50,99,64,74),4,DUST)
            +bevel((-83,-35,71,97,-25,77),2,QUILT))


def clock():
    x,z,r = 0,86,74
    rim = ring_band(x,z,(-25,67,83),(-8,67,83),OAK,axis='y')
    face = loft([disc(x,z,r,r,y,16) for y in (-17,13)],TAN,axis='y')
    # Rotate the texture onto the face. The plane at Y -17 is first.
    lines = face.splitlines(keepends=True)
    prefix = lines[1].split(material(TAN),1)[0]
    scale = 2*r/128
    lines[1] = prefix+f'bedroom/attic_clockface {r/scale:g} {(r+z)/scale:g} 0 {scale:g} {scale:g} 134217728 0 0\n'
    foot = bevel((-69,-11,0,69,35,21),3,OAK)
    return rim+''.join(lines)+foot


PREFABS = {
    'steamer_trunk': steamer_trunk, 'trunk_open': open_trunk, 'suitcase': suitcase,
    'suitcase_steps': suitcase_steps, 'file_box': files, 'sheeted_armchair': sheeted_chair,
    'rocking_chair': rocking_chair, 'dresser_steps': dresser, 'rafters': rafters,
    'board_ramp': board_ramp, 'hatch_stair': hatch_stair, 'gramophone': gramophone,
    'radio': radio, 'film_reel': film_reel, 'camera': camera, 'sewing_machine': sewing_machine,
    'dress_form': form, 'rolled_rug': rolled_rug, 'picture_frames': frames,
    'birdcage': birdcage, 'sled': sled, 'ornaments': ornaments, 'blanket_stack': blankets, 'clock': clock,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    write_materials()
    for name,make in PREFABS.items():
        body = HEADER+'{\n"classname" "worldspawn"\n'+make()+'}\n'
        (args.output/f'attic_{name}.map').write_text(body,encoding='ascii')


if __name__=='__main__':
    main()
