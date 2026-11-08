#!/usr/bin/env python3
"""Build Operation Sandbreak: original 1–4 player sandbox assault geometry."""
from pathlib import Path
import json
import math
from generate_helicopter_test import box, entity

ROOT = Path(__file__).resolve().parents[2]
NAME = 'pp_sandbreak'
WORLD, ENTITIES, ROUTES = [], [], []
GLYPHS = {
    '0': ('111','101','101','101','111'),
    '1': ('010','110','010','010','111'),
    '2': ('111','001','111','100','111'),
    '3': ('111','001','111','001','111'),
    'A': ('010','101','111','101','101'),
    'B': ('110','101','110','101','110'),
    'C': ('111','100','100','100','111'),
}


def solid(lo, hi, tex='sand', contents=0, flags=0, dest=None, detail=False):
    (WORLD if dest is None else dest).append(box(lo, hi, 'sandkeep/'+tex, contents or (0x08000000 if detail else 0), flags))


def point(cls, xyz=None, **keys):
    k = {'classname': cls}
    if xyz is not None:
        k['origin'] = ' '.join(f'{v:g}' for v in xyz)
    k.update({a: str(b) for a,b in keys.items()})
    ENTITIES.append(entity(k))


def brush_entity(cls, lo, hi, tex='plastic_green_smooth', **keys):
    ENTITIES.append(entity(dict(classname=cls, **{k:str(v) for k,v in keys.items()}),
                           box(lo,hi,'sandkeep/'+tex)))


def prism(poly, bottom, top, tex='sand', detail=False):
    """Convex CCW footprint; top may be a coplanar height list for ramps."""
    zs = [top]*len(poly) if isinstance(top,(int,float)) else top
    low = [(x,y,bottom) for x,y in poly]
    high = [(x,y,z) for (x,y),z in zip(poly,zs)]
    planes = [(low[0],low[1],low[2]),(high[0],high[2],high[1])]
    for i in range(len(poly)):
        j=(i+1)%len(poly)
        planes.append((low[i],high[j],low[j]))
    WORLD.append('{\n'+''.join(' '.join('( '+' '.join(f'{v:.4f}' for v in p)+' )' for p in plane)
                 +f' sandkeep/{tex} 0 0 0 1 1 {0x08000000 if detail else 0} 0 0\n' for plane in planes)+'}\n')


def octagon(x,y,r):
    return [(x+r*math.cos(math.radians(22.5+i*45)),y+r*math.sin(math.radians(22.5+i*45))) for i in range(8)]


def spool(x,y,r=72,h=104):
    prism(octagon(x,y,r),0,16,'wood_end',True)
    prism(octagon(x,y,r*.63),16,h-16,'trim',True)
    prism(octagon(x,y,r),h-16,h,'wood_end',True)


def lettering(text,cx,y,z,size=8,tex='sand'):
    """Raised toy lettering, facing south, with merged horizontal strokes."""
    left=cx-(4*len(text)-1)*size/2
    for n,char in enumerate(text):
        for row,pixels in enumerate(GLYPHS[char]):
            col=0
            while col<len(pixels):
                if pixels[col]=='0':
                    col+=1
                    continue
                end=col+1
                while end<len(pixels) and pixels[end]=='1':
                    end+=1
                solid((left+(n*4+col)*size,y,z+(4-row)*size),
                      (left+(n*4+end)*size,y+2,z+(5-row)*size),tex,detail=True)
                col=end


def arrow(x,y,west=False):
    def rotate(p):
        a,b=p
        return (x-b,y+a) if west else (x+a,y+b)
    for poly in ([(-24,-8),(24,-8),(0,28)], [(-8,-40),(8,-40),(8,-8),(-8,-8)]):
        prism([rotate(p) for p in poly],0,1,'plastic_green_smooth',True)


def block(x,y,w=128,h=112,tex='plastic_red'):
    solid((x-w/2,y-w/2,0),(x+w/2,y+w/2,h),tex,detail=True)
    solid((x-w/2-4,y-w/2-4,h-12),(x+w/2+4,y+w/2+4,h),'wood_end',detail=True)
    # The cream inset and colored letter distinguish alphabet blocks from crates.
    solid((x-w/2+12,y-w/2-1,12),(x+w/2-12,y-w/2+1,h-20),'sand',detail=True)
    letter={'plastic_red':'A','plastic_green_smooth':'B','plastic_blue_smooth':'C'}[tex]
    size=min(12,(h-36)/5)
    lettering(letter,x,y-w/2-3,(h-12-size*5)/2,size,tex)


def shelter(x,y):
    # Two open ends, roof protection, no trapped supply closets.
    solid((x-224,y-160,160),(x+224,y+160,184),'wood_end')
    for yy in (y-160,y+136):
        solid((x-224,yy,0),(x+224,yy+24,160),'plastic_blue_smooth')
    point('light',(x,y,120),light=380,_color='.8 .9 1')
    # A raised medical sign identifies sheltered supplies from the combat lane.
    solid((x-28,y-165,156),(x+28,y-161,212),'plastic_green_smooth',detail=True)
    solid((x-6,y-168,166),(x+6,y-165,202),'sand',detail=True)
    solid((x-18,y-168,178),(x+18,y-165,190),'sand',detail=True)


def pickup(cls,x,y,z=32,**keys):
    point(cls,(x,y,z),**keys)


def supply(x,y,ammo='ammo_bullets'):
    # Four separately collectible portions because ammo/health do not stay in coop.
    for dx,dy in ((-48,-48),(48,-48),(-48,48),(48,48)):
        pickup(ammo,x+dx,y+dy)
    pickup('item_health_large',x,y+100)
    pickup('item_health_large',x-128,y)


def enemy(kind,x,y,z=24,**keys):
    point('monster_'+kind,(x,y,z),angle=270,**keys)


def message(name,text):
    point('target_help',targetname=name,message=text)


def gate(y,name):
    # Central 320 wide aperture, castle shoulders and crenels. Clip over the
    # crest prevents explosive-jump skips without hiding later landmarks.
    for x,X in ((-1216,-160),(160,1216)):
        solid((x,y,0),(X,y+64,320))
        for xx in range(x,X-40,128):
            solid((xx,y,320),(min(xx+64,X),y+64,368))
    solid((-160,y,192),(160,y+64,320))
    solid((-1216,y,368),(1216,y+64,1024),'sand',65536)
    solid((-1216,y,320),(1216,y+64,368),'sand',65536)
    # Red is locked. Braces travel with the door, leaving a green-framed opening.
    panels=[box((-160,y+8,0),(160,y+56,192),'sandkeep/plastic_red')]
    for x in (-112,96):
        panels.append(box((x,y+4,16),(x+16,y+8,176),'sandkeep/iron'))
    panels.append(box((-144,y+4,88),(144,y+8,104),'sandkeep/iron'))
    ENTITIES.append(entity(dict(classname='func_door',targetname=name,
                               angle='-1',speed='80',wait='-1',lip='0',sounds='1'),''.join(panels)))
    number={'assault_gate':'01','air_gate':'02','extraction_gate':'03'}[name]
    solid((-52,y-4,220),(52,y,292),'plastic_blue_smooth',detail=True)
    lettering(number,0,y-6,230,10)
    for x in (-192,176):
        solid((x,y-8,0),(x+16,y,192),'plastic_green_smooth')
    point('light',(0,y-96,220),light=450,_color='1 .95 .7')


def tower(cx):
    cy=-1520; outer=octagon(cx,cy,224); inner=octagon(cx,cy,184)
    for i in range(8):
        j=(i+1)%8
        poly=[outer[i],outer[j],inner[j],inner[i]]
        # Four ground doors; upper cardinal openings are escape windows.
        if i not in (1,3,5,7):
            prism(poly,0,112)
        if i not in (1,3,5,7):
            prism(poly,128,256)
        else:
            prism(poly,240,272)
        prism(poly,272,288,detail=True)
    for x,y in octagon(cx,cy,202):
        solid((x-22,y-22,288),(x+22,y+22,328),detail=True)
    prism(outer,112,128)
    # Straight 1:3.5 sand ramp reaches the southern upstairs opening.
    poly=[(cx-64,-2200),(cx+64,-2200),(cx+64,-1680),(cx-64,-1680)]
    prism(poly,-16,[0,0,148,148])
    point('light',(cx,cy,88),light=400,_color='1 .9 .72')
    side='west' if cx<0 else 'east'
    # A touch button at the upstairs north side stays pressed permanently.
    brush_entity('func_button',(cx-40,-1384,128),(cx+40,-1360,184),'plastic_red',
                 target=side+'_control',angle=90,wait=-1,lip=20,speed=20)
    point('trigger_relay',targetname=side+'_control',target='controls_done',
          message=side.upper()+' CONTROL SECURED')
    pickup('ammo_slugs' if cx<0 else 'ammo_cells',cx,-1540,32)
    pickup('item_health_large',cx,-1450,32)


def build():
    solid((-1248,-3040,-96),(1248,3072,0))
    solid((-1248,-3040,1024),(1248,3072,1056),'wood_end',flags=4)
    for x,X in ((-1248,-1216),(1216,1248)):
        solid((x,-3040,0),(X,3072,320),'wood')
        solid((x,-3040,320),(X,3072,1024),'wood',flags=4)
    for y,Y in ((-3040,-3008),(3040,3072)):
        solid((-1216,y,0),(1216,Y,320),'wood')
        solid((-1216,y,320),(1216,Y,1024),'wood',flags=4)
    for x in (-1216,1192):
        solid((x,-3008,272),(x+24,3040,296),'wood_end')
    # Protected insertion hut: frontal cover and two broad side exits.
    solid((-480,-3008,176),(480,-2544,200),'wood_end')
    solid((-480,-2576,0),(480,-2544,176),'plastic_green_smooth')
    for x in (-480,448):
        solid((x,-3008,0),(x+32,-2880,176),'plastic_green_smooth')
        solid((x,-2672,0),(x+32,-2576,176),'plastic_green_smooth')
    for i,x in enumerate((0,96,-96,192)):
        point('info_player_start' if i==0 else 'info_player_coop',(x,-2880,24),angle=90)
    for x,cls in ((-224,'weapon_shotgun'),(0,'weapon_machinegun'),(224,'item_armor_jacket')):
        pickup(cls,x,-2784)
    for x in (-336,-208,336):
        pickup('item_armor_jacket',x,-2864)
    supply(-240,-2700,'ammo_shells'); supply(240,-2700)
    for x in (-96,0,96,192):
        pickup('ammo_grenades',x,-2960)
    point('light',(0,-2784,130),light=650,_color='1 .95 .8')
    # Landing lane loops: toy blocks and thread spools with crossovers.
    for x,y in ((-680,-2416),(680,-2416),(-1040,-2112),(1040,-2112)):
        spool(x,y)
    block(0,-2320,192,112,'plastic_blue_smooth')
    block(-320,-1940); block(320,-1940,tex='plastic_green_smooth')
    tower(-680); tower(680)
    for x in (-680,680):
        arrow(x,-2288)
    solid((-680,-1576,112),(680,-1464,128),'wood_end')
    pickup('weapon_hyperblaster',0,-1520,160)
    pickup('weapon_railgun',-680,-1520,160)
    pickup('weapon_supershotgun',680,-1520,160)
    pickup('weapon_grenadelauncher',0,-1232)
    for x in (-96,0,96,192):
        pickup('ammo_gl_rounds',x,-1120)
    block(0,-1800,112,80)
    for x,y,k in ((-400,-2240,'soldier_light'),(400,-2200,'soldier_light'),
                  (-1000,-1850,'soldier'),(1000,-1840,'soldier'),
                  (-360,-1300,'soldier_ss'),(360,-1300,'soldier_ss'),
                  (0,-1056,'soldier_heavy')):
        enemy(k,x,y)
    enemy('soldier_ss',-680,-1500,z=152,spawnflags=256)
    enemy('soldier_ss',680,-1500,z=152,spawnflags=256)
    enemy('soldier_rocket',980,-1160,spawnflags=768)
    point('trigger_counter',targetname='controls_done',count=2,spawnflags=1,target='assault_gate',
          message='BOTH CONTROLS SECURED\\nGate 01 open. Collect the rockets.\\nDestroy the courtyard tank.')
    message('assault_gate','ASSAULT GATE OPEN\\nCollect rockets beyond gate 01.\\nDestroy the courtyard tank.')
    gate(-992,'assault_gate')
    # Tank court with protected rearm loops and a water-risk mortar detour.
    pickup('weapon_rocketlauncher',0,-784)
    pickup('weapon_chaingun',360,-752)
    shelter(-880,-600); shelter(880,-600)
    supply(-880,-600,'ammo_rockets'); supply(880,-600)
    pickup('item_armor_combat',0,-672)
    pickup('item_armor_combat',-880,-688)
    pickup('item_armor_combat',880,-688)
    for x,y in ((-320,-512),(320,-240),(-320,200),(320,544)):
        block(x,y,144,144,'plastic_blue_smooth' if x<0 else 'plastic_red')
    for x,y in ((1000,-160),(1000,304),(-1020,544)):
        spool(x,y,80,144)
    # Raised water basin has two broad stair entries and exits, never a key gate.
    solid((-1152,-320,0),(-640,320,64),'plastic_blue_smooth',32,24)
    for x in (-1168,-640):
        solid((x,-336,0),(x+16,336,80),'plastic_blue_smooth')
    for y in (-336,320):
        for x,X in ((-1168,-976),(-816,-624)):
            solid((x,y,0),(X,y+16,80),'plastic_blue_smooth')
    for sign in (-1,1):
        for i in range(1,5):
            # 16-unit steps both outside and inside the pool lip.
            yy=sign*(320+(4-i)*32)
            solid((-976,yy-16,0),(-816,yy+16,i*16),'sand')
            yy=sign*(320-(4-i)*32)
            if i<4:
                solid((-976,yy-16,0),(-816,yy+16,i*16),'sand')
    pickup('weapon_bfg',-896,0,32)
    arrow(-600,-416,west=True)
    # The side entry is deliberately marked; the shelter blocks a straight approach.
    point('light',(-896,-272,144),light=180,_color='.55 .8 1')
    brush_entity('trigger_once',(-1000,-96,0),(-800,96,88),target='mortar_secret')
    point('target_secret',targetname='mortar_secret',message='SUBMERGED MORTAR CACHE FOUND')
    enemy('plastic_tank',0,400,deathtarget='armor_down')
    for x,y,k in ((-480,-256,'soldier_ss'),(480,64,'soldier_ss'),(-480,600,'soldier'),
                  (680,640,'soldier_heavy'),(-1020,760,'soldier_rocket')):
        enemy(k,x,y)
    enemy('soldier',960,512,spawnflags=256)
    enemy('soldier_heavy',480,800,spawnflags=768)
    point('trigger_relay',targetname='armor_down',target='air_gate',
          message='TANK DESTROYED\\nGate 02 open. Down the helicopter.\\nUse the roofs for cover.')
    message('air_gate','AIRFIELD ASSAULT\\nDestroy the helicopter.\\nShelter under roofs between attacks.')
    gate(928,'air_gate')
    # Airfield: high roof cover, circular fighting lanes, supplies off sightlines.
    shelter(-880,1240); shelter(880,1240)
    supply(-880,1240,'ammo_rockets'); supply(880,1240)
    pickup('weapon_rocketlauncher',-880,1160)
    pickup('weapon_chaingun',880,1160)
    pickup('item_armor_body',0,1168)
    block(0,1424,224,176,'plastic_green_smooth')
    shelter(-880,2040); shelter(880,2040)
    supply(-880,2040,'ammo_rockets'); supply(880,2040)
    for x in (-440,440):
        block(x,1824,144,192,'plastic_blue_smooth')
        spool(x,2368,88,144)
    pickup('ammo_slugs',-1056,1740); pickup('ammo_cells',1056,1740)
    pickup('weapon_grenadelauncher',0,2520)
    for x in (-96,0,96,192):
        pickup('ammo_gl_rounds',x,2600)
    enemy('plastic_helicopter',0,2144,z=384,deathtarget='air_down')
    for x,y,k in ((-384,1216,'soldier'),(384,1216,'soldier_ss'),(-1080,1664,'soldier_light'),
                  (1080,1664,'soldier_light'),(-680,2480,'soldier_heavy'),(680,2480,'soldier_rocket')):
        enemy(k,x,y)
    enemy('soldier_ss',-680,1760,spawnflags=256)
    enemy('soldier_rocket',680,1760,spawnflags=768)
    point('trigger_relay',targetname='air_down',target='extraction_gate',
          message='SKY CLEAR\\nGate 03 open.\\nReach the GREEN EXTRACTION BEACON.')
    message('extraction_gate','EXTRACT\\nReach the green beacon past gate 03.')
    gate(2688,'extraction_gate')
    solid((-256,2816,0),(256,3000,8),'plastic_green_smooth')
    for x in (-256,232):
        solid((x,2800,0),(x+24,3008,240),'plastic_green_smooth')
        solid((x,2800,240),(x+24,3008,256),'lamp')
    point('light',(0,2912,160),light=600,_color='.45 1 .55')
    brush_entity('trigger_once',(-208,2848,8),(208,3008,128),target='mission_complete')
    point('target_goal',targetname='mission_complete',target='debrief',
          message='OPERATION SANDBREAK COMPLETE\\nCastle breached. Armor destroyed. Airfield secured.')
    point('target_changelevel',targetname='debrief',map='pp_sandbreak_end')
    point('info_player_intermission',(0,2480,256),angles='0 90 0')
    point('trigger_always',target='mission_brief',delay=1)
    message('mission_brief','OPERATION SANDBREAK\\n01 Secure both tower controls.\\n02 Destroy the courtyard tank.\\n03 Down the helicopter and extract.')
    brush_entity('trigger_once',(-400,-2840,0),(400,-2740,112),target='landing_brief')
    point('trigger_relay',targetname='landing_brief',message='OPERATION SANDBREAK\\nTwo tower controls open the assault gate.\\nUse the sand ramps. Split, flank and regroup.\\nYour final goal is the green extraction beacon.')
    point('light',(500,-1600,900),target='sun_direction')
    point('info_null',(0,0,0),targetname='sun_direction')
    for y in (-2400,-1600,-800,0,800,1600,2400):
        for x in (-700,700):
            point('light',(x,y,640),light=560,_color='1 .94 .82')
    world=dict(classname='worldspawn',message='Operation Sandbreak',sky='bluesky1',sounds='0',
               _sun='sun_direction',_sun_light='85',_sun_ambient='28',_sun_color='1 .97 .9')
    path=ROOT/'maps/source'/f'{NAME}.map'
    path.write_text('// Generated original co-op level. Edit tools/maps/generate_sandbreak.py.\n'+
                    entity(world,''.join(WORLD))+''.join(ENTITIES))
    print(f'Wrote {path}: {len(WORLD)} world brushes, {len(ENTITIES)} entities')
    routes = [
      dict(name='west_insertion_loop',points=[[0,-2880,24],[-320,-2880,24],[-320,-2784,24],[-560,-2784,24],[-1000,-2784,24],[-1000,-2280,24],[-1136,-2280,24],[-1136,-1056,24],[0,-1056,24]]),
      dict(name='east_insertion_loop',points=[[192,-2880,24],[320,-2880,24],[320,-2784,24],[560,-2784,24],[1136,-2784,24],[1136,-1056,24],[0,-1056,24]]),
      dict(name='west_tower_ramp',points=[[-680,-2240,24],[-680,-2200,24],[-680,-1680,172],[-680,-1640,152],[-680,-1450,152]]),
      dict(name='bridge_crossing',points=[[-680,-1520,152],[680,-1520,152]]),
      dict(name='tower_ground_escape',points=[[-680,-1290,24],[-680,-1520,24],[-940,-1520,24]]),
      dict(name='tank_west_loop',opened_doors=['assault_gate'],points=[[0,-1056,24],[0,-608,24],[-560,-608,24],[-560,800,24],[0,800,24]]),
      dict(name='tank_east_loop',opened_doors=['assault_gate'],points=[[0,-1056,24],[0,-608,24],[560,-608,24],[560,800,24],[0,800,24]]),
      dict(name='tank_advance',hull='tank',points=[[0,400,24],[0,-512,24]]),
      dict(name='airfield_west_loop',opened_doors=['air_gate'],points=[[0,800,24],[0,1080,24],[-560,1080,24],[-560,2560,24],[0,2560,24]]),
      dict(name='airfield_east_loop',opened_doors=['air_gate'],points=[[0,800,24],[0,1080,24],[560,1080,24],[560,2560,24],[0,2560,24]]),
      dict(name='extraction',opened_doors=['extraction_gate'],points=[[0,2560,24],[0,2800,24],[0,2800,32],[0,2944,32]])]
    out=ROOT/'build/maps'/NAME; out.mkdir(parents=True,exist_ok=True)
    (out/'routes.json').write_text(json.dumps({'routes':routes},indent=2)+'\n')
    build_debrief()


def build_debrief():
    w=[]
    for lo,hi,tex in [((-416,-416,-32),(416,416,0),'sand'),
                       ((-416,-416,256),(416,416,288),'wood_end'),
                       ((-416,-416,0),(-384,416,256),'wood'),
                       ((384,-416,0),(416,416,256),'wood'),
                       ((-384,-416,0),(384,-384,256),'wood'),
                       ((-384,384,0),(384,416,256),'wood')]:
        w.append(box(lo,hi,'sandkeep/'+tex))
    e=[]
    for i,x in enumerate((-144,-48,48,144)):
        e.append(entity(dict(classname='info_player_start' if i==0 else 'info_player_coop',origin=f'{x} -240 24',angle='90')))
    e += [entity(dict(classname='light',origin='0 0 180',light='700')),
          entity(dict(classname='trigger_always',target='victory_help',delay='1')),
          entity(dict(classname='target_help',targetname='victory_help',message='MISSION COMPLETE\\nOperation Sandbreak secured.\\nThe red button starts another assault.')),
          entity(dict(classname='trigger_relay',targetname='victory_message',message='OPERATION SANDBREAK COMPLETE\\nCastle breached. Armor destroyed. Airfield secured.\\nRed button: replay mission.')),
          entity(dict(classname='trigger_once',target='victory_message'),box((-320,-160,0),(320,160,128),'sandkeep/sand')),
          entity(dict(classname='func_button',target='replay',angle='90',wait='-1'),box((-48,320,32),(48,344,96),'sandkeep/plastic_red')),
          entity(dict(classname='target_changelevel',targetname='replay',map='pp_sandbreak'))]
    (ROOT/'maps/source/pp_sandbreak_end.map').write_text(entity(dict(classname='worldspawn',message='Sandbreak Mission Complete'),''.join(w))+''.join(e))


if __name__=='__main__':
    build()
