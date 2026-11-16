#!/usr/bin/env python3
"""Add Operation Garden Ghost to the unchanged, user-authored Garden shell."""
from pathlib import Path
import hashlib
import json
import math
import re

import generate_sandkeep as g

ROOT = Path(__file__).resolve().parents[2]
NAME = 'pp_garden_infiltration'
BASE = ROOT / 'baseq2/maps/pp_garden.map'
WORLD, ENTITIES = [], []
g.WORLD = WORLD


def box(lo, hi, texture='sandkeep/soil', **kw):
    texture = texture.removeprefix('sandkeep/')
    return g.box(lo, hi, texture, **kw).replace('sandkeep/sandbox/', 'sandbox/')


def wb(lo, hi, texture='sandkeep/soil', **kw):
    WORLD.append(box(lo, hi, texture, **kw))


def ent(classname, origin=None, geometry=(), **values):
    keys = {'classname': classname}
    if origin is not None:
        keys['origin'] = ' '.join(f'{v:g}' for v in origin)
    keys.update(values)
    ENTITIES.append('{\n' + ''.join(f'"{k}" "{v}"\n' for k, v in keys.items())
                    + ''.join(geometry) + '}\n')


def rock(cx, cy, rx, ry, height, seed=0):
    # A single opaque convex earth buttress, with a grassy crown. World brushes
    # avoid the per-entity submission cost of one model for every decoration.
    outline = [(-1,-.6),(-.65,-1),(.55,-.9),(1,-.3),(.9,.65),(.2,1),(-.8,.8)]
    low = [(round(cx+x*rx), round(cy+y*ry), 8) for x,y in outline]
    high = [(round(cx+x*rx*.62+seed), round(cy+y*ry*.62), 8+height) for x,y in outline]
    polys = [low,high]+[[low[i],high[i],high[(i+1)%7],low[(i+1)%7]] for i in range(7)]
    WORLD.append(g.convex(polys,'soil',detail=True,face_options={1:{'texture':'grass'}}))


def hedge(lo, hi):
    # Tall planted earth breaks sight at a bend and actually splits full VIS.
    wb(lo,hi,'soil',face_overrides={5:{'texture':'grass'}})
    x,y,z=lo; X,Y,Z=hi
    for offset in (16,48):
        if X-x > Y-y:
            wb((x+offset,y+8,24),(min(X,x+offset+24),Y-8,72),'grass',detail=True)
        else:
            wb((x+8,y+offset,24),(X-8,min(Y,y+offset+24),72),'grass',detail=True)


def block(cx, cy, size=80, yaw=0, bottom=8):
    g.rotated_box(cx,cy,size,size,bottom,bottom+size,yaw,texture='plastic_blue_smooth',letters=True)


def grass(cx,cy):
    # Three opaque low-polygon blades; no alpha cards, new models or thinkers.
    for dx,dy,h in ((-7,0,44),(7,4,36),(0,-7,52)):
        a=(cx+dx-4,cy+dy-3,8); b=(cx+dx+4,cy+dy-3,8)
        c=(cx+dx,cy+dy-3,h); A=(a[0],a[1]+4,a[2]); B=(b[0],b[1]+4,b[2]); C=(c[0],c[1]+4,c[2])
        WORLD.append(g.convex([[a,b,c],[A,C,B],[a,A,B,b],[b,B,C,c],[c,C,A,a]],'grass',detail=True))


def open_bunker(cx,cy,facing='south'):
    # Five broad opaque pieces: open sides, rear wall and a low firing front.
    sign=1 if facing=='south' else -1
    def b(x,y,X,Y,z,Z,tex='sand_wall'):
        ya,yb=sorted((cy+y*sign,cy+Y*sign)); wb((cx+x,ya,z),(cx+X,yb,Z),tex)
    b(-112,56,112,80,8,136)
    b(-112,-80,-88,-24,8,136); b(88,-80,112,-24,8,136)
    b(-88,-80,88,-56,8,56); b(-88,-80,88,-56,104,136)
    b(-120,-88,120,88,136,152,'grass')


def tower(cx,cy):
    # Low lookout keeps the guard under the existing 360-unit sky. Four posts,
    # deck, parapet; an open ground-level bypass remains outside its footprint.
    for dx in (-80,68):
        for dy in (-80,68):
            wb((cx+dx,cy+dy,8),(cx+dx+12,cy+dy+12,112),'wood',detail=True)
    wb((cx-88,cy-88,104),(cx+88,cy+88,120),'wood')
    for lo,hi in [((cx-88,cy-88,120),(cx+88,cy-72,152)),
                  ((cx-88,cy+72,120),(cx+88,cy+88,152)),
                  ((cx-88,cy-72,120),(cx-72,cy+72,152)),
                  ((cx+72,cy-72,120),(cx+88,cy+72,152))]:
        wb(lo,hi,'sand_wall',detail=True)
    wb((cx-96,cy-96,224),(cx+96,cy+96,240),'grass',detail=True)
    for dx in (-80,68):
        for dy in (-80,68):
            wb((cx+dx,cy+dy,152),(cx+dx+12,cy+dy+12,224),'wood',detail=True)


def pickup(kind,x,y,z=64):
    ent(kind,(x,y,z))


def soldier(kind,x,y,angle=90,z=56):
    ent('monster_soldier_light' if kind=='pistol' else 'monster_soldier',
        (x,y,z),angle=angle,spawnflags=1)


def materials():
    # Reuse the game's authored material family; only mission labels are new.
    from generate_sandkeep_materials import panel,text,write_wal
    from platoon_palette import load_palette
    pal=load_palette()
    for name,lines in {
        'gg_intro':['GARDEN GHOST','MOVE QUIETLY','SANDBOX PERIMETER'],
        'gg_shotgun':['FIELD CACHE','SHOTGUN AND SHELLS','SHARE WITH SQUAD'],
        'gg_hold':['SANDBOX AHEAD','HOLD AT THE GATE','NEXT OPERATION'],
    }.items():
        im,draw=panel(color=(33,63,43),accent=(226,204,112))
        for y,line in zip((24,56,88),lines): text(draw,128,y,line,2,(242,235,204))
        path=ROOT/'baseq2/textures/sandkeep'/name
        im.save(path.with_suffix('.png')); write_wal(path.with_suffix('.wal'),'sandkeep/'+name,im,pal)


def south_sign(cx,y,z,name,width=192,height=96):
    x=cx-width/2; sx=width/256; sy=height/128
    wb((x,y,z),(x+width,y+4,z+height),'trim',detail=True,
       face_overrides={2:{'texture':name,'scale':(sx,sy),'shift':(-x/sx,(z+height)/sy)}})


def generate():
    WORLD.clear(); ENTITIES.clear(); original=BASE.read_text()
    baseline=hashlib.sha256(BASE.read_bytes()).hexdigest()
    materials()
    # The supplied ground faces carry SURF_SKY. Add grass skins over their
    # collision slabs rather than changing any original face or brush. A
    # quarter-unit grass skin preserves the original collision slabs and starts.
    for x,y,X,Y in ((3272,-1272,4536,-8),(3912,-8,4536,648),
                    (1992,640,4536,1272),(1992,1272,2616,1928),
                    (1992,1928,4536,2552),(3912,2552,4536,3208),
                    (1992,3208,4536,3832),(1992,3832,2616,4488),
                    (1992,4488,3264,5112)):
        wb((x,y,0),(X,Y,8.25),'grass',detail=True)
    # Safe insertion clearing: supplies sit clear of the unchanged four starts.
    south_sign(3712,-1080,48,'gg_intro',256,128)
    for x in (3680,3776): pickup('ammo_grenades',x,-920)
    for x in (3640,3736): pickup('item_armor_jacket',x,-800)
    for x in (3616,3672,3728,3784): pickup('item_armor_shard',x,-680)
    block(3488,-760,96,12); rock(4380,-1050,120,120,96)
    # Entry throat. The staggered tall bank screens the drop-off from gunfire.
    hedge((3912,-120,8),(4140,160,368))
    rock(4450,180,70,112,104); block(4010,460,72,-12)
    soldier('pistol',4320,400,90); soldier('pistol',4420,540,180)
    # First westbound garden lane; two flanking ways around each earth tooth.
    hedge((3072,640,8),(3200,1000,368))
    hedge((2752,1016,8),(2880,1272,368))
    open_bunker(3632,1152)
    soldier('pistol',3624,1144,180)
    soldier('pistol',3330,820,180)
    tower(2440,1080); soldier('pistol',2440,1080,0,z=144)
    rock(3440,720,120,60,104); block(3440,1090,80,18); block(2580,760,96,-9)
    for x in (3520,3600): pickup('item_health',x,1000)
    pickup('ammo_grenades',2570,900); pickup('item_health_small',2520,800)
    # Narrow left turn: an ambush shotgun soldier, facing away from entry.
    rock(2510,1510,80,96,136); rock(2070,1820,64,80,96)
    soldier('shotgun',2150,1670,90); soldier('pistol',2440,1840,0)
    for x in (2100,2160,2220): pickup('item_health_small',x,1450)
    pickup('item_armor_jacket',2290,1810)
    # Second eastbound lane, ending at the shared shotgun depot (~halfway).
    hedge((2880,2200,8),(3024,2552,368))
    hedge((3520,1928,8),(3664,2256,368))
    open_bunker(3300,2020,'north')
    soldier('pistol',3300,2024,0); soldier('pistol',2720,2370,0)
    soldier('pistol',3880,2370,90)
    block(3160,2430,88,-16); rock(4050,2020,112,60,128)
    pickup('ammo_grenades',3130,2090)
    for x in (3200,3260): pickup('item_health',x,2170)
    # Cache before right-hand narrow turn. Weapon stays for co-op teammates.
    wb((4000,2624,8),(4136,2784,24),'wood',detail=True)
    south_sign(4070,2776,96,'gg_shotgun')
    shotgun=(4068,2680,48); pickup('weapon_shotgun',*shotgun)
    for x,y in ((4030,2730),(4110,2730),(4040,2610),(4120,2610)):
        pickup('ammo_shells',x,y,48 if y>2624 else 40)
    pickup('item_health',4380,2700); pickup('item_armor_jacket',4430,2780)
    rock(4470,3000,60,130,160)
    soldier('shotgun',4290,2960,90); soldier('pistol',4370,3140,180)
    # Third westbound row. Cover alternates, keeping the long garden bounded.
    hedge((3440,3208,8),(3584,3544,368))
    hedge((2912,3552,8),(3056,3832,368))
    open_bunker(3220,3730)
    soldier('pistol',3220,3730,180); soldier('pistol',3750,3330,180)
    tower(2520,3650); soldier('pistol',2520,3650,0,z=144)
    block(3860,3720,96,11); block(2690,3360,80,-10)
    rock(3310,3290,120,70,112)
    pickup('ammo_shells',3300,3610); pickup('ammo_grenades',3150,3400)
    for x in (2730,2790): pickup('item_health',x,3710)
    # Last left turn and covered approach to the sandbox perimeter.
    hedge((2416,4040,8),(2616,4184,368))
    rock(2070,4350,70,112,120); soldier('shotgun',2180,4260,90)
    soldier('pistol',2440,4430,0)
    pickup('ammo_shells',2140,4010)
    for x in (2090,2150,2210,2270): pickup('item_health_small',x,3910)
    open_bunker(2520,4980)
    soldier('shotgun',2520,4960,0); soldier('pistol',2920,4640,180)
    block(2790,4920,96,14); rock(2730,4580,96,64,104)
    pickup('ammo_shells',2630,4820); pickup('item_health',2450,4810)
    for x in (2870,2930,2990): pickup('item_armor_shard',x,5040)
    # End destination is scenery only. Added solid boards close the existing
    # opening; none of the user's sky/floor/wall brush records are altered.
    wb((3252,4488,8),(3272,5112,320),'gate_wood')
    wb((3240,4488,128),(3252,5112,144),'iron',detail=True)
    wb((3240,4488,280),(3252,5112,296),'wood',detail=True)
    wb((3272,4232,8),(4536,5496,12),'sand',detail=True)
    # A few block silhouettes establish the sandbox beyond the closed gate.
    block(3710,4850,144,8,bottom=12); block(3980,5100,112,-14,bottom=12)
    block(4250,4660,128,12,bottom=12)
    south_sign(3040,5090,128,'gg_hold',256,128)
    for x,y in ((3430,-1060),(4480,-710),(4470,540),(3360,1140),(2220,700),
                (2020,1530),(2500,1870),(3090,2470),(3760,1980),(4460,2600),
                (4440,3150),(3870,3790),(2710,3780),(2040,4100),(2600,5080)):
        grass(x,y)
    # Static neutral lighting makes sentries readable without dynamic lamps.
    ent('light',(4000,-1000,320),light=240,_color='1 .96 .86')
    for x,y in ((3632,1152),(3300,2020),(4070,2680),(3220,3730),(2520,4980)):
        ent('light',(x,y,120),light=180,_color='1 .94 .80')
    ent('light',(4300,-900,320),target='garden_sun_direction')
    ent('info_null',(3900,-400,40),targetname='garden_sun_direction')
    from garden_mission_logic import add_mission
    add_mission(ent,box)
    # Explicit route snakes around new cover. z56 clears original 32-high
    # ground undulations while staying within normal player step height.
    points=[(3914,-686,56),(4280,-400,56),(4280,280,56),(4270,850,56),
            (3730,900,56),(3500,930,56),(3290,1100,56),(3000,1100,56),(2970,850,56),
            (2680,850,56),(2300,900,56),(2300,1550,56),(2300,2080,56),
            (2770,2080,56),(3140,2080,56),(3320,2360,56),(3760,2360,56),
            (4220,2450,56),(4220,2680,56),(4220,3090,56),(4130,3460,56),
            (3740,3460,56),(3700,3670,56),(3260,3560,56),(3160,3410,56),
            (2800,3410,56),(2300,3500,56),(2300,4240,56),(2300,4780,56),
            (2800,4780,56),(3120,4800,56)]
    # Find the original world entity's closing brace without reserializing it.
    depth=0; end=None
    for match in re.finditer(r'(?m)^\s*([{}])\s*$',original):
        depth+=1 if match[1]=='{' else -1
        if depth==0:
            end=match.start(); break
    assert end is not None
    header=original[:end].replace('"message" "Mission 01: Operation Sandstorm"',
                                 '"message" "Operation Garden Ghost"')
    header=header.replace('"sounds" "0"','"sounds" "0"\n"_sun" "garden_sun_direction"\n"_sun_light" "70"\n"_sun_ambient" "24"\n"_sun_color" "1 .98 .94"')
    source=ROOT/'maps/source'/(NAME+'.map')
    source.write_text(header+'\n// Additive Garden Ghost scenery\n'+''.join(WORLD)+original[end:]+'\n// Additive mission entities\n'+''.join(ENTITIES))
    dest=ROOT/'build/maps'/NAME; dest.mkdir(parents=True,exist_ok=True)
    design={'map':NAME,'title':'Operation Garden Ghost','base_source_sha256':baseline,
            'routes':[{'name':'complete_garden_route','points':points}],
            'shotgun_origin':list(shotgun),'sandbox_boundary_x':3264,'mission_finish':[3120,4800,56],
            'added_world_brushes':len(WORLD),'added_entities':len(ENTITIES),
            'capture_positions':[[4270,760,56,0,180],[2300,1550,56,0,90],
                                 [4220,2850,56,0,90],[3700,3670,56,0,180],[3000,4800,56,0,0]]}
    (dest/'design.json').write_text(json.dumps(design,indent=2)+'\n')
    design['runtime_translation']=[-3200,-2000,0]
    source.with_suffix('.design.json').write_text(json.dumps(design,indent=2)+'\n')
    assert hashlib.sha256(BASE.read_bytes()).hexdigest()==baseline
    print(json.dumps({'source':str(source),**{k:design[k] for k in ('added_world_brushes','added_entities','shotgun_origin')}},indent=2))


if __name__=='__main__': generate()
