#!/usr/bin/env python3
"""Author Operation End of the Line with original Plastic Platoon materials.

The generated Quake-format MAP is editable in TrenchBroom. This generator owns
only pp_endline; it never reads commercial game data or overwrites other maps.
All distances are engine units. Player standing origin is floor + 24.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import generate_sandkeep as brush

ROOT = Path(__file__).resolve().parents[2]
WORLD, ENTITIES, ROUTES = [], [], []
RAIL_HALF_GAUGE = 100
RAIL_HEAD_Z = 257


def material(text):
    return text if "/" in text else "endline/" + text


def box(lo, hi, texture="cardboard", **kw):
    # The shared writer always adds sandkeep/; normalize qualified textures.
    overrides = kw.pop("face_overrides", {})
    overrides = {i: {**v, **({"texture": material(v["texture"])} if "texture" in v else {})}
                 for i, v in overrides.items()}
    return brush.box(lo, hi, material(texture), face_overrides=overrides, **kw).replace("sandkeep/endline/", "endline/").replace("sandkeep/sandkeep/", "sandkeep/").replace("sandkeep/sandbox/", "sandbox/").replace("sandkeep/bedroom/", "bedroom/")


def wb(lo, hi, texture="cardboard", **kw):
    WORLD.append(box(lo, hi, texture, **kw))


def convex(polys, texture="cardboard"):
    return brush.convex(polys, material(texture)).replace("sandkeep/endline/", "endline/").replace("sandkeep/sandkeep/", "sandkeep/").replace("sandkeep/sandbox/", "sandbox/").replace("sandkeep/bedroom/", "bedroom/")


def ent(classname, origin=None, geometry=(), **values):
    data = {"classname": classname}
    if origin is not None:
        data["origin"] = " ".join(f"{v:g}" for v in origin)
    data.update(values)
    ENTITIES.append("{\n" + "".join(f'"{k}" "{v}"\n' for k, v in data.items()) + "".join(geometry) + "}\n")


def relay(name, target=None, delay=0, message=None, **kw):
    if target:
        kw["target"] = target
    if delay:
        kw["delay"] = delay
    if message:
        kw["message"] = message.replace("\n", "\\n")
    ent("trigger_relay", targetname=name, **kw)


def helptext(name, message):
    ent("target_help", targetname=name, message=message, spawnflags=1)


def trigger(lo, hi, target, **kw):
    ent("trigger_once", geometry=[box(lo, hi, "rail_metal")], target=target, **kw)


def light(x, y, z, power=450, color="1 .85 .64", **kw):
    ent("light", (x, y, z), light=power, _color=color, **kw)


def pickup(kind, x, y, floor=0, area="yard", **kw):
    ent(kind, (x, y, floor + 24), _endline_area=area, **kw)


def soldier(kind, x, y, floor=0, angle=180, tier=0, area="yard", wave=False):
    name = {"pistol": "monster_soldier_light", "shotgun": "monster_soldier",
            "rifle": "monster_soldier_ss", "heavy": "monster_soldier_heavy"}[kind]
    flags = (0, 256, 768)[tier] | (2 if wave else 0)
    kw = {"targetname": "endline_wave", "deathtarget": "endline_wave_down"} if wave else {}
    if wave:
        release=f"endline_release_{abs(x)}_{abs(y)}"
        kw.update(combattarget=release, _endline_reserve=area)
        if area == "yard":
            ent("point_combat",(2224,-1392,24),targetname=release,target=release+"_exit")
            ent("point_combat",(2032,-1392,24),targetname=release+"_exit")
        else:
            point=(x,-264,264) if area == "upper" else (-256,720,24)
            ent("point_combat",point,targetname=release)
    ent(name, (x, y, floor + 24), angle=angle, spawnflags=flags,
        _endline_area=area, **kw)


def sign(cx, y, z, name, width=256, height=128, facing="south"):
    x = cx - width / 2
    sx, sy = width / 256, height / 128
    horizontal = sx if facing == "south" else -sx
    offset = -x/sx if facing == "south" else (x+width)/sx
    wb((x, y, z), (x + width, y + 4, z + height), "rail_metal", detail=True,
       face_overrides={2 if facing == "south" else 3:
                       dict(texture=name, scale=(horizontal, sy), shift=(offset, (z+height)/sy))})


def crate(x, y, z=0, size=96, friendly=False):
    wb((x, y, z), (x+size, y+size, z+size), "sandkeep/plastic_green" if friendly else "sleeper_wood", detail=True)
    for t in (8, size-16):
        wb((x+t,y-2,z),(x+t+8,y+size+2,z+size),"rail_metal",detail=True)
    wb((x-2,y+8,z+size),(x+size+2,y+size-8,z+size+4),"cardboard",detail=True)


def stair_x(x, y, n, width=192, floor=0, direction=1, texture="sandkeep/plastic_green_smooth", thin=False):
    points = [[x-direction*32,y+width/2,floor+24]]
    for i in range(n):
        a,b = sorted((x+direction*i*32,x+direction*(i+1)*32))
        top = floor + (i+1)*16
        wb((a,y,top-16 if thin else floor),(b,y+width,top),texture,detail=True)
        points.append([(a+b)/2,y+width/2,top+24])
    return points


def stair_y(x, y, n, width=192, floor=0, direction=1, texture="sandkeep/plastic_blue_smooth"):
    points = [[x+width/2,y-direction*32,floor+24]]
    for i in range(n):
        a,b = sorted((y+direction*i*32,y+direction*(i+1)*32))
        top = floor+(i+1)*16
        wb((x,a,floor),(x+width,b,top),texture,detail=True)
        points.append([x+width/2,(a+b)/2,top+24])
    return points


def route(name, points, **kw):
    ROUTES.append(dict(name=name, points=points, **kw))


def cylinder(cx, cy, radius, z0, z1, texture, sides=12):
    low=[(round(cx+radius*math.cos(i*2*math.pi/sides),3),round(cy+radius*math.sin(i*2*math.pi/sides),3),z0) for i in range(sides)]
    high=[(x,y,z1) for x,y,z in low]
    return convex([low,high]+[[low[i],high[i],high[(i+1)%sides],low[(i+1)%sides]] for i in range(sides)],texture)


def wheel(cx, y, cz, radius, width, texture="rubber"):
    """Twelve-sided toy wheel, axle along the track's transverse Y axis."""
    low=[(round(cx+radius*math.cos(i*math.pi/6),3),y,
          round(cz+radius*math.sin(i*math.pi/6),3)) for i in range(12)]
    high=[(x,y+width,z) for x,_,z in low]
    return convex([low,high]+[[low[i],high[i],high[(i+1)%12],low[(i+1)%12]] for i in range(12)],texture)


def envelope():
    wb((-3968,-1856,-64),(3968,1856,0),"concrete",scale=2)
    wb((-3968,-1856,1152),(3968,1856,1216),"sandbox/wood1",scale=4)
    for lo,hi in [((-3968,-1856,0),(-3904,1856,1152)),((3904,-1856,0),(3968,1856,1152)),
                  ((-3904,-1856,0),(3904,-1792,1152)),((-3904,1792,0),(3904,1856,1152))]:
        wb(lo,hi,"concrete",scale=2)
    # Huge bench legs, cross braces and drawers establish the miniature scale.
    for x,y in [(-2832,-720),(-2832,1168),(2352,-1504),(2528,1248)]:
        wb((x,y,0),(x+208,y+208,1152),"sandbox/wood1",scale=2)
        wb((x-16,y-16,0),(x+224,y+224,32),"rubber",detail=True)
    for y in (-1744,1504):
        wb((-2864,y,800),(2768,y+112,976),"sandbox/wood1",scale=3)
    wb((-1024,-1776,832),(1536,-1344,1120),"sleeper_wood",scale=2)
    for x in (-768,0,768):
        wb((x,-1352,944),(x+192,-1304,976),"rail_metal",detail=True)
    # Storage boxes end the floor lanes and occlude both offstage train pockets.
    for x,X in [(-3680,-2944),(2704,3680)]:
        for y,Y in [(-1728,-208),(208,1728)]:
            wb((x,y,0),(X,Y,704),"cardboard",scale=2)
        wb((x,-208,592),(X,208,736),"corrugation",scale=2)
    for x,y,w,d,h in [(-2600,1000,600,650,640),(-1984,1280,640,448,384),
                       (-896,1168,896,576,736),(160,1488,1600,240,608),
                       (-1280,-1760,1344,224,720),(80,-1760,784,32,640)]:
        wb((x,y,0),(x+w,y+d,h),"cardboard",scale=2)
        wb((x+16,y-4,h-80),(x+w-16,y,h-56),"hazard",detail=True,scale=.5)
    # Daylight at the garage-door threshold; this becomes the ending backdrop.
    wb((-3900,-544,96),(-3888,544,592),"signal_green",detail=True,
       face_overrides={1:dict(texture="sandkeep/lamp",flags=1,value=180)})
    for x in range(-2560,2561,768):
        for y in (-1152,896):
            light(x,y,640,1100,".78 .83 1")
    for x in (-2304,-768,768,2304):
        wb((x-96,-40,1088),(x+96,40,1120),"rail_metal",detail=True)
        wb((x-88,-32,1080),(x+88,32,1088),"sandkeep/lamp",detail=True,
           face_overrides={4:dict(texture="sandkeep/lamp",flags=1,value=160)})
        light(x,0,1000,1200)
    # Side fill makes the wheels and couplers readable at the tunnel mouths.
    light(2768,0,552,450,".88 .93 1")
    light(-3008,0,552,380,".83 .90 1")
    light(-3750,0,384,900,".72 .90 1")


def railway():
    # Solid deck carries ties; side walks leave the rolling stock clearance.
    wb((-3712,-160,216),(3712,160,232),"sleeper_wood",detail=True)
    for x in range(-3680,3681,128):
        wb((x,-152,232),(x+32,152,240),"sleeper_wood",detail=True)
    # A foot, web and running surface make the track readable at wheel height.
    # The mover's one-unit padded bounds put its 256-unit treads at z=257.
    for y in (-RAIL_HALF_GAUGE, RAIL_HALF_GAUGE):
        wb((-3712,y-7,238),(3712,y+7,243),"rail_metal",detail=True)
        wb((-3712,y-2,243),(3712,y+2,252),"rail_metal",detail=True)
        wb((-3712,y-5,252),(3712,y+5,RAIL_HEAD_Z),"rail_metal",detail=True)
    # Colorful wooden block piers; the lower approach winds between them.
    for n,x in enumerate((-3504,-2864,-2464,-1936,-960,0,640,2208,2672,3392)):
        for y in (-128,32):
            wb((x,y,0),(x+128,y+96,208),f"sandbox/abc_block_{'efabcdefab'[n]}",detail=True,scale=1)
        wb((x-16,-176,208),(x+144,176,216),"sandbox/wood1",detail=True)
    for x,X in [(-2464,-1808),(-1808,-832),(-832,128),(128,768),(768,2336)]:
        for y in (-168,152):
            wb((x,y,192),(X,y+16,216),"loco_red",detail=True)
    # Pools of light under the bridge reveal the block piers and lower lane.
    for x in (-1584,-528,432):
        wb((x-28,80,204),(x+28,128,216),"rail_metal",detail=True,
           face_overrides={4:dict(texture="sandkeep/lamp",flags=1,value=55)})
        light(x,104,190,185,".93 .84 .65")
    # Upper service walk deliberately has broken chest-high cover and railing.
    wb((-1856,-352,224),(352,-176,240),"sleeper_wood",detail=True)
    upper_steps=stair_x(352,-352,4,floor=240)
    wb((480,-352,288),(1040,-160,304),"sleeper_wood",detail=True)
    for x in (-1712,-864,-624,-144):
        wb((x,-352,240),(x+128,-320,288),"toolbox_blue",detail=True)
    for x in range(-1824,321,192):
        wb((x,-184,240),(x+8,-176,300),"rail_metal",detail=True)
    wb((-1840,-184,292),(336,-176,300),"rail_metal",detail=True)
    climb=stair_x(-2336,-640,15,width=208,texture="bedroom/pillow")
    wb((-1856,-640,224),(-1664,-352,240),"bedroom/pillow",detail=True)
    route("upper_signal",[[-2400,-1200,32],[-2264,-944,32],[-2264,-800,24],
          [-2464,-800,24],[-2464,-536,24]]+climb+
          [[-1760,-496,264],[-1760,-264,264],[320,-264,264]]+upper_steps+
          [[560,-264,328],[624,-392,328],[624,-592,328],[656,-864,328]],objective="signal",approach="upper")
    route("intro_rider_return",[[-3440,0,264],[352,0,264],[352,-144,264],[368,-208,280],
          [320,-256,264],[-1760,-264,264],[-1760,-496,264]]+list(reversed(climb))+
          [[-2464,-536,24]],train_at={"endline_train":"endline_siding"})
    # A midway stair reconnects upper/lower before either objective entrance.
    crossover=stair_y(-800,-1056,15,width=192,texture="sandkeep/plastic_blue_smooth")
    wb((-800,-576,224),(-608,-352,240),"sleeper_wood",detail=True)
    route("midway_crosslink",crossover+[[-704,-496,264],[-704,-264,264]])


def insertion():
    # Tipped shipping box with two torn, uneven exits and low cardboard floor.
    wb((-2624,-1488,0),(-1744,-848,8),"cardboard",detail=True)
    wb((-2624,-1488,8),(-2600,-848,256),"corrugation")
    wb((-2600,-1488,8),(-1744,-1464,256),"cardboard")
    wb((-2624,-1488,256),(-1744,-848,280),"cardboard")
    for lo,hi in [((-2600,-872,8),(-2400,-848,216)),((-2128,-872,8),(-1744,-848,176)),
                  ((-1768,-1464,8),(-1744,-1328,240)),((-1768,-1088,8),(-1744,-872,208))]:
        wb(lo,hi,"corrugation")
    sign(-2176,-1460,96,"sign_mission",width=384,height=144,facing="north")
    starts=[(-2448,-1200,32),(-2320,-1200,32),(-2448,-1328,32),(-2320,-1328,32)]
    for i,p in enumerate(starts):
        ent("info_player_start" if i==0 else "info_player_coop",p,angle=20)
    for kind,x,y in [("weapon_shotgun",-2048,-1360),("weapon_machinegun",-1904,-1360),
                      ("ammo_shells",-2056,-1216),("ammo_shells",-1984,-1216),
                      ("ammo_bullets",-1904,-1216),("ammo_bullets",-1824,-1216),
                      ("item_armor_jacket",-2192,-1360),("item_health_large",-2192,-1216)]:
        pickup(kind,x,y,8,area="insertion")
    light(-2160,-1152,216,500,"1 .8 .5")
    trigger((-2576,-1432,8),(-1800,-920,144),"endline_intro")
    relay("endline_intro","endline_train",delay=3)
    helptext("endline_intro","1. Capture the signal cabin. 2. Clear the counterattack. 3. Board the train and depart together.")
    relay("endline_intro",message="OPERATION END OF THE LINE\nRaid the signal cabin. Capture the ammunition train.\nUpper walkway or lower freight passage: choose your approach.")
    # Ruler firing perch and scattered screw container in the first firefight.
    stair_x(-2384,-768,6,width=96,texture="sleeper_wood")
    wb((-2192,-800,0),(-1968,-656,96),"cardboard",detail=True)
    for x,y in [(-1504,-1232),(-1312,-976),(-1976,-496)]:
        crate(x,y,size=96)
    wb((-1328,-1440,0),(-1104,-1200,160),"toolbox_blue",detail=True)
    for x,y in [(-1824,-1120),(-1408,-1120),(-1104,-1280)]:
        wb((x,y,0),(x+96,y+8,8),"rail_metal",detail=True)
        WORLD.append(cylinder(x+96,y+4,20,0,16,"rail_metal",8))
    soldier("pistol",-1600,-1088,angle=180,area="insertion")
    soldier("pistol",-1184,-816,angle=210,area="insertion")
    soldier("pistol",-1088,-1472,angle=160,tier=1,area="insertion")
    soldier("rifle",-1856,-384,angle=235,tier=2,area="insertion")
    # Both routes pass this deliberately prominent new weapon alcove.
    wb((-1664,-784,0),(-1376,-744,160),"cardboard",detail=True)
    sign(-1520,-740,32,"sign_double_barrel",facing="north")
    pickup("weapon_supershotgun",-1552,-624,area="insertion",target="endline_double")
    pickup("ammo_shells",-1456,-624,area="insertion")
    pickup("ammo_shells",-1456,-536,area="insertion")
    pickup("item_health",-1648,-528,area="insertion")
    pickup("weapon_supershotgun",-1760,-496,240,area="upper",target="endline_double")
    pickup("ammo_shells",-1760,-424,240,area="upper")
    relay("endline_double",message="DOUBLE BARREL SHOTGUN\nTwo shells. Close range. Make the first shot count.\nShell caches mark both approaches.")
    sign(-1760,-328,320,"sign_upper",width=192,height=96)
    sign(-1328,320,128,"sign_lower",width=192,height=96)
    light(-1520,-608,224,440,"1 .75 .35")


def toolbox_and_lower():
    wb((-384,-1120,0),(384,-384,608),"toolbox_blue",scale=2)
    wb((-408,-1144,592),(408,-360,640),"toolbox_blue",detail=True,scale=2)
    for x in (-336,272):
        wb((x,-1152,384),(x+64,-1120,528),"rail_metal",detail=True)
    for x in (-208,176):
        wb((x,-832,640),(x+32,-672,736),"rail_metal",detail=True)
    wb((-208,-832,712),(208,-672,744),"rubber",detail=True)
    # North of the bridge: low cardboard culverts with two openings each.
    for x in (-1632,-896,0):
        wb((x,352,0),(x+24,784,192),"corrugation")
        wb((x,784,0),(x+464,808,208),"cardboard")
        wb((x+440,352,0),(x+464,480,192),"corrugation")
        wb((x,352,192),(x+464,808,216),"cardboard")
        crate(x+280,624,size=80)
        light(x+232,512,168,320,".68 .82 1")
    # Insulated cable under the crossing is low enough to step over.
    for x,y,X,Y in [(-1760,160,-1024,176),(-1040,160,-1024,304),(-1040,288,480,304),
                     (464,288,480,448)]:
        wb((x,y,0),(X,Y,10),"rubber",detail=True)
    for x,y in [(-1408,512),(-672,528),(224,560),(544,1008)]:
        soldier("shotgun",x,y,angle=225,area="lower")
    soldier("rifle",-1056,944,tier=1,area="lower")
    soldier("shotgun",64,960,tier=1,area="lower")
    soldier("rifle",544,672,tier=2,area="lower")
    for x,y in [(-1456,688),(-640,688),(176,688)]:
        pickup("ammo_shells",x,y,area="lower")
        pickup("item_health",x-64,y,area="lower")
    pickup("ammo_bullets",-1248,688,area="lower")
    pickup("item_armor_jacket",384,960,area="lower")
    # South service alley is a loop back to insertion; shortcut opens on switch.
    for x,y in [(-864,-1488),(-560,-1408),(352,-1440)]:
        crate(x,y,size=112)
    ent("func_door", geometry=[box((-1040,-1568,0),(-1008,-1168,176),"hazard")],
        targetname="endline_shortcut",angle=-2,speed=160,wait=-1,lip=0,sounds=1)
    wb((-1040,-1792,0),(-1008,-1568,608),"cardboard")
    wb((-1040,-1168,0),(-1008,-1120,176),"cardboard")
    sign(-672,-1596,64,"sign_ammo",width=192,height=96,facing="north")
    pickup("ammo_bullets",-736,-1392,area="lower")
    pickup("ammo_shells",-624,-1264,area="lower")
    pickup("item_health_large",-800,-1264,area="lower")
    route("lower_signal",[[-2400,-1200,32],[-1824,-1200,32],[-1640,-1200,24],[-1640,-920,24],
          [-1728,-920,24],[-1728,-704,24],[-1552,-624,24],[-1728,-400,24],
          [-1728,272,24],[-1408,272,24],[-1408,512,24],[-1200,512,24],
          [-1056,512,24],[-1056,288,24],[-672,288,24],[-672,512,24],[-416,512,24],
          [-224,512,24],[-224,288,24],[224,288,24],[224,512,24],[512,512,24],[864,512,24],
          [864,208,24],[864,-528,24],[1008,-528,24],[1008,-1600,24],
          [1008,-1696,24],[704,-1696,24]] +
          CABIN_STEPS + [[704,-1056,328],[704,-928,328],[656,-864,328]],objective="signal",approach="lower")


CABIN_STEPS=[]


def station():
    # Cabin on the toolbox side, with independent north and south entrances.
    wb((448,-1056,288),(864,-432,304),"sleeper_wood")
    for x in (448,840):
        wb((x,-1056,304),(x+24,-432,360),"cardboard")
        wb((x,-1056,464),(x+24,-432,520),"corrugation")
        for y in (-1056,-768,-456):
            wb((x,y,360),(x+24,y+24,464),"sleeper_wood",detail=True)
    for y in (-1056,-456):
        for x,X in ((472,560),(752,840)):
            wb((x,y,304),(X,y+24,520),"cardboard")
        wb((560,y,464),(752,y+24,520),"corrugation")
    wb((424,-1080,520),(888,-408,544),"loco_red",detail=True)
    wb((544,-432,288),(736,-352,304),"sleeper_wood",detail=True)
    CABIN_STEPS.extend(stair_y(608,-1664,19,width=192))
    wb((608,-1056,288),(800,-1024,304),"sandkeep/plastic_blue_smooth",detail=True)
    # The animated face presses into a fixed cabinet. Keep the bezel behind
    # the face at both ends of its travel so a player can reach the switch.
    wb((524,-964,304),(604,-876,312),"rail_metal",detail=True)
    wb((528,-960,312),(600,-880,420),"toolbox_blue",detail=True)
    wb((524,-964,420),(604,-876,428),"rail_metal",detail=True)
    for lo,hi in [((600,-960,344),(604,-952,420)),((600,-888,344),(604,-880,420)),
                  ((600,-952,344),(604,-888,352)),((600,-952,416),(604,-888,420))]:
        wb(lo,hi,"rail_metal",detail=True)
    ent("func_button",geometry=[box((600,-952,352),(616,-888,416),"rail_metal",
        face_overrides={1:dict(texture="signal_switch",scale=(.5,1),shift=(1904,416))})],
        angle=180,lip=12,speed=32,wait=-1,sounds=1,target="endline_divert",
        _endline_objective="signal")
    light(680,-904,456,140,"1 .92 .78")
    sign(672,-1048,376,"sign_signal",width=144,height=72,facing="north")
    # Large external red/green signal switches its glowing lenses physically.
    wb((472,-488,544),(488,-472,768),"rail_metal",detail=True)
    wb((440,-512,680),(520,-448,784),"rail_metal",detail=True)
    ent("func_wall",geometry=[box((448,-516,696),(512,-512,760),"signal_red",
        face_overrides={2:dict(texture="signal_red",flags=1,value=120)})],
        targetname="endline_signal_red",spawnflags=3)
    ent("func_wall",geometry=[box((448,-516,696),(512,-512,760),"signal_green",
        face_overrides={2:dict(texture="signal_green",flags=1,value=120)})],
        targetname="endline_signal_green",spawnflags=1)
    # func_wall red starts on (1+4), green starts off. No stock light model.
    ENTITIES[-2]=ENTITIES[-2].replace('"spawnflags" "3"','"spawnflags" "7"')
    light(656,-736,480,420,"1 .8 .5")
    soldier("shotgun",736,-672,304,angle=270,area="cabin")
    soldier("rifle",496,-560,304,angle=180,tier=1,area="cabin")
    pickup("ammo_shells",792,-848,304,area="cabin")
    pickup("ammo_bullets",792,-944,304,area="cabin")
    pickup("item_health_large",504,-800,304,area="cabin")
    for x,y,kind,tier in [(-1440,-264,"rifle",0),(-912,-256,"pistol",0),(-400,-240,"rifle",1),
                            (144,-256,"rifle",2)]:
        soldier(kind,x,y,240,angle=180,tier=tier,area="upper")
    for x in (-1600,-992,-208):
        pickup("ammo_bullets",x,-256,240,area="upper")
        pickup("ammo_shells",x+80,-256,240,area="upper")
    pickup("item_health_large",-1232,-256,240,area="upper")


def parked_car(x,y,broken=False):
    # Both static freight cars can be approached at either end and crawled under.
    for a in (x+48,x+432):
        for b in (y+16,y+208):
            WORLD.append(wheel(a+32,b,40,40,32))
            WORLD.append(wheel(a+32,b-2,40,16,36,"rail_metal"))
    if broken:
        wb((x,y,80),(x+176,y+256,96),"sleeper_wood",detail=True)
        wb((x+304,y,80),(x+544,y+256,96),"sleeper_wood",detail=True)
        wb((x+176,y,80),(x+304,y+64,96),"sleeper_wood",detail=True)
        wb((x+176,y+192,80),(x+304,y+256,96),"sleeper_wood",detail=True)
    else:
        wb((x,y,80),(x+544,y+256,96),"sleeper_wood",detail=True)
    for Y in (y,y+240):
        wb((x,Y,96),(x+544,Y+16,248),"loco_red",detail=True)
    for X in (x,x+528):
        wb((X,y+16,96),(X+16,y+240,248),"loco_red",detail=True)
    if broken:
        # Gap and low step reach an otherwise hidden armor compartment.
        wb((x+192,y+80,0),(x+288,y+176,16),"sleeper_wood",detail=True)
        wb((x+192,y+96,16),(x+288,y+160,32),"sleeper_wood",detail=True)
        pickup("item_armor_combat",x+240,y+128,32,area="yard")
        trigger((x+176,y+64,24),(x+304,y+192,200),"endline_secret_car")
        ent("target_secret",targetname="endline_secret_car",message="SECRET: Broken freight floor - captured armor.",sounds=1)


def yard():
    parked_car(1056,400,broken=True)
    parked_car(1744,864)
    # Cardboard station store, with separate west/north doors for flanking.
    for lo,hi in [((2112,-1712,0),(2592,-1688,208)),((2568,-1688,0),(2592,-1120,208)),
                  ((2112,-1688,0),(2136,-1488,208)),((2112,-1296,0),(2136,-1120,208)),
                  ((2136,-1144,0),(2208,-1120,208)),((2400,-1144,0),(2568,-1120,208))]:
        wb(lo,hi,"cardboard")
    wb((2096,-1728,208),(2608,-1104,232),"corrugation")
    sign(2496,-1116,80,"sign_freight",width=160,height=80,facing="north")
    light(2256,-1520,184,380,"1 .87 .67")
    pickup("ammo_shells",2448,-1584,area="yard")
    pickup("item_health",2512,-1584,area="yard")
    # Platform and two 19-step loading ramps stay available on all skills.
    wb((1040,-464,0),(2016,-160,304),"cardboard")
    wb((1024,-480,288),(2032,-160,304),"sleeper_wood",detail=True)
    wb((1456,-160,288),(1904,-136,304),"sleeper_wood",detail=True)
    wb((864,-352,288),(1040,-176,304),"sleeper_wood",detail=True)
    ramp=stair_y(1744,-1088,19,width=240,texture="sleeper_wood")
    # Eastern stair comes up to the far end, an alternative if the ramp is held.
    east=stair_y(2096,-96,19,width=192,direction=-1,texture="sandkeep/plastic_red")
    wb((2032,-736,288),(2288,-672,304),"sleeper_wood",detail=True)
    wb((1984,-736,288),(2096,-464,304),"sleeper_wood",detail=True)
    sign(1504,-484,152,"sign_board",width=384,height=144)
    for x,y in [(1072,-432),(1360,-432),(1840,-432)]:
        crate(x,y,304,size=80,friendly=True)
    for kind,x,y in [("ammo_shells",1216,-368),("ammo_shells",1288,-368),
                      ("ammo_bullets",1512,-384),("ammo_bullets",1584,-384),
                      ("ammo_shells",1664,-384),("item_health_large",1664,-272),
                      ("item_armor_jacket",1472,-256)]:
        pickup(kind,x,y,304,area="platform")
    for x,y in [(1088,-1168),(1408,-736),(2240,416),(1888,592),(896,1040),(1472,1376)]:
        crate(x,y,size=112)
    for x,y,kind,tier in [(1216,176,"rifle",0),(1664,688,"rifle",0),(2112,288,"pistol",0),
                         (1920,-1392,"shotgun",0),(1392,-960,"shotgun",0),(1344,1120,"rifle",1),
                         (2272,1088,"rifle",1),(2560,-912,"rifle",1),(1552,224,"heavy",2),
                         (2368,-1056,"shotgun",2),(1696,1360,"rifle",2)]:
        soldier(kind,x,y,angle=200,tier=tier,area="yard")
    for kind,x,y in [("ammo_shells",928,928),("ammo_shells",1728,592),("ammo_bullets",2064,592),
                      ("item_health_large",2368,800),("ammo_bullets",1200,1328),
                      ("item_health",1328,-1280),("ammo_shells",1440,-1280),
                      ("item_health_large",2288,-1008),("ammo_bullets",2288,-928)]:
        pickup(kind,x,y,area="yard")
    # Short stair across the tracks at the east end reconnects the yard lanes.
    cross=stair_y(2336,784,15,width=192,direction=-1,texture="bedroom/pillow")
    wb((2336,-352,224),(2528,304,240),"bedroom/pillow",detail=True)
    stair_y(2336,-832,15,width=192,texture="bedroom/pillow")
    route("boarding_loading_ramp",[[704,-928,328],[704,-1056,328]]+list(reversed(CABIN_STEPS))+
          [[704,-1696,24],[1600,-1696,24],[1864,-1200,24]]+ramp+
          [[1760,-496,328],[1760,-256,328],[1760,-64,329]],objective="boarding",approach="ramp",
          train_at={"endline_train":"endline_siding"},opened_doors=["endline_control_cover"])
    route("boarding_upper_walk",[[656,-864,328],[624,-592,328],[624,-392,328],
          [624,-256,328],[960,-256,328],[1232,-256,328],[1760,-256,328],[1760,-64,329]],
          objective="boarding",approach="walkway",train_at={"endline_train":"endline_siding"},opened_doors=["endline_control_cover"])
    route("yard_under_freight",[[928,528,24],[928,736,24],[1648,736,24],[1648,352,24],
          [1312,352,24],[1312,464,24],[1312,496,56],[1296,528,56]],secret="endline_secret_car")


def secrets():
    # Friendly medic station: a torn label and two openings behind the start.
    wb((-2600,-1736,0),(-1776,-1712,224),"cardboard")
    wb((-2600,-1736,224),(-1776,-1488,248),"cardboard")
    wb((-2600,-1712,0),(-2576,-1488,224),"corrugation")
    sign(-2192,-1500,80,"sign_medic",width=192,height=96)
    pickup("item_health_mega",-2352,-1600,area="insertion")
    pickup("ammo_shells",-2064,-1600,area="insertion")
    trigger((-2512,-1704,0),(-1936,-1520,160),"endline_secret_medic")
    ent("target_secret",targetname="endline_secret_medic",message="SECRET: The lost friendly medic station.",sounds=1)
    light(-2256,-1616,192,300,".6 1 .7")
    route("friendly_medic_secret",[[-2400,-1200,32],[-1824,-1200,32],[-1712,-1200,24],
          [-1712,-1600,24],[-1840,-1600,24],[-2352,-1600,24]],secret="endline_secret_medic")
    # Cable spool and ruler stair: optional high perch above the cabin.
    for z0,z1,r in [(0,24,160),(24,144,96),(144,160,160)]:
        WORLD.append(cylinder(128,-1360,r,z0,z1,"sleeper_wood"))
    perch_low=stair_x(-352,-1496,10,width=96,texture="sleeper_wood")
    wb((-32,-1496,144),(176,-1408,160),"sleeper_wood",detail=True)
    perch_high=stair_x(176,-1456,24,width=96,floor=160,texture="sleeper_wood",thin=True)
    wb((944,-1456,528),(1088,-1120,544),"sleeper_wood",detail=True)
    wb((864,-1120,528),(1088,-1024,544),"sleeper_wood",detail=True)
    pickup("ammo_grenades",784,-880,544,area="cabin")
    pickup("ammo_bullets",784,-736,544,area="cabin")
    pickup("ammo_shells",608,-512,544,area="cabin")
    trigger((736,-992,544),(848,-640,688),"endline_secret_perch")
    ent("target_secret",targetname="endline_secret_perch",message="SECRET: Railway inspector's perch.",sounds=1)
    route("inspector_perch_secret",perch_low+[[128,-1448,184]]+perch_high+
          [[1008,-1408,568],[1008,-1168,568],[1008,-1072,568],[832,-1072,568],
           [784,-880,568]],secret="endline_secret_perch")


def train():
    # One compound brush model: red shunter, covered ammunition van, rear flatcar.
    # Authored at its initial hidden east pocket. Paths specify model minimum.
    X=2496
    geo=[]
    def tb(lo,hi,tex,**kw):
        geo.append(box((lo[0]+X,lo[1],lo[2]),(hi[0]+X,hi[1],hi[2]),tex,**kw))
    for a,b in [(0,304),(328,664),(688,1152)]:
        tb((a,-136,288),(b,136,304),"sleeper_wood")
        tb((a,-144,272),(b,144,288),"loco_red")
        for x in (a+32,b-80):
            # Center the 32-unit treads on the rails after the mover's +1 Y offset.
            for y in (-RAIL_HALF_GAUGE-17,RAIL_HALF_GAUGE-17):
                geo.append(wheel(X+x+24,y,280,24,32))
                geo.append(wheel(X+x+24,y-2,280,10,36,"rail_metal"))
    # Coupling walkways are wide and flush, with no mandatory jumping.
    for a,b in [(304,328),(664,688)]:
        tb((a,-64,292),(b,64,304),"rail_metal")
    tb((16,-104,304),(176,104,400),"loco_red")
    tb((24,-88,400),(144,88,424),"loco_red")
    tb((48,-32,424),(80,32,480),"rail_metal")
    tb((32,-48,468),(96,48,484),"rail_metal")
    tb((192,-112,304),(288,-88,480),"loco_red")
    tb((192,88,304),(288,112,480),"loco_red")
    tb((176,-128,480),(304,128,496),"loco_red")
    tb((0,-80,352),(16,-32,400),"sandkeep/lamp",face_overrides={0:dict(texture="sandkeep/lamp",flags=1,value=100)})
    tb((0,32,352),(16,80,400),"sandkeep/lamp",face_overrides={0:dict(texture="sandkeep/lamp",flags=1,value=100)})
    # The ammunition van's south and north doors leave a straight interior aisle.
    for y in (-136,120):
        for a,b in [(336,416),(560,656)]:
            tb((a,y,304),(b,y+16,432),"cardboard")
    tb((336,-136,432),(656,136,448),"cardboard")
    for x in (352,576):
        tb((x,32,304),(x+64,112,368),"sandkeep/plastic_green")
    # Rear deck holds four players behind ammunition crates; both sides board.
    for a in (720,1040):
        tb((a,40,304),(a+80,120,384),"sandkeep/plastic_green")
        tb((a+16,36,304),(a+24,124,384),"rail_metal")
    tb((1128,-136,304),(1152,136,352),"loco_red")
    tb((704,128,304),(1128,136,344),"loco_red")
    # The moving brushes carry the lighting baked in the east pocket.
    # Light the running gear from both sides and the van from below its roof.
    for y in (-180, 180):
        light(X+128,y,302,160,".83 .90 1")
    light(X+496,0,386,150,"1 .90 .76")
    light(X+880,0,544,250,"1 .90 .76")
    # Compile the brushes around a local pivot so the moving origin fits the
    # signed 16-bit network coordinate range across the entire route.
    ent("func_train",(X+576,0,320),geometry=geo,targetname="endline_train",target="endline_intro_start",speed=176,
        spawnflags=6,dmg=0,noise="endline/wheels.wav",_endline_objective="train")
    ent("path_corner",(2496,-144,256),targetname="endline_intro_start",target="endline_hold")
    ent("path_corner",(-3552,-144,256),targetname="endline_hold",target="endline_loop",wait=-1,pathtarget="endline_intro_done")
    ent("path_corner",(2496,-144,256),targetname="endline_loop",target="endline_siding",spawnflags=1)
    ent("path_corner",(800,-144,256),targetname="endline_siding",target="endline_exit",wait=-1,pathtarget="endline_arrived")
    ent("path_corner",(-3200,-144,256),targetname="endline_exit",wait=-1,pathtarget="endline_complete")
    relay("endline_intro_done","endline_dispatch",delay=.3)
    relay("endline_divert","endline_dispatch")
    ent("trigger_counter",targetname="endline_dispatch",target="endline_train",count=2,spawnflags=1)
    relay("endline_divert","endline_shortcut")
    relay("endline_divert","endline_signal_red")
    relay("endline_divert","endline_signal_green")
    ent("target_speaker",(1400,-144,384),targetname="endline_divert",noise="endline/whistle.wav",volume=1,attenuation=0)
    relay("endline_divert","endline_wave",delay=2)
    relay("endline_divert","endline_reserve_doors",delay=2.5)
    relay("endline_divert",message="SIGNAL GREEN - SUPPLY TRAIN DIVERTED\nCounterattack! Watch the walkway, freight passage and storage room.\nService shortcut open behind the toolbox.")
    helptext("endline_divert","2. Secure the siding. Counterattack from the upper walk, lower passage and storage room.")
    # Closed deployment rooms keep players out of trigger-spawn KillBox volumes.
    # Doors open half a second after every defender has materialized safely.
    for kind,x,y,z,tier,area in [
        ("rifle",-1344,-528,240,0,"upper"),("shotgun",-640,1008,0,0,"lower"),
        ("rifle",-448,1008,0,0,"lower"),("shotgun",2200,-1456,0,0,"yard"),
        ("rifle",2288,-1600,0,0,"yard"),("shotgun",2288,-1300,0,0,"yard"),
        ("rifle",-1184,-528,240,1,"upper"),("shotgun",-256,1008,0,1,"lower"),
        ("rifle",2288,-1456,0,1,"yard"),
        ("rifle",-1024,-528,240,2,"upper"),("heavy",2200,-1600,0,2,"yard"),
        ("shotgun",2200,-1300,0,2,"yard")]:
        soldier(kind,x,y,z,tier=tier,area=area,wave=True)
    for count,flags in ((6,1536),(9,1280),(12,768)):
        ent("trigger_counter",targetname="endline_wave_down",target="endline_secured",count=count,spawnflags=flags|1)
    relay("endline_secured","endline_board_condition")
    relay("endline_secured",message="SIDING SECURE\nTrain boarding unlocks when the shipment stops.\nResupply on the platform and rally on the rear flatcar.")
    relay("endline_arrived","endline_board_condition")
    ent("trigger_counter",targetname="endline_board_condition",target="endline_board_ready",count=2,spawnflags=1)
    relay("endline_board_ready","endline_control_cover")
    relay("endline_board_ready","endline_depart_permission")
    relay("endline_board_ready",message="TRAIN READY - DEPARTURE CONTROL UNLOCKED\nTouch the departure control beside the rear flatcar.\nThe train waits until every living squad member is aboard.")
    helptext("endline_board_ready","3. Touch DEPART on the loading platform. Assemble every living player on the rear flatcar. Ride out together.")
    # The departure face sits in a backed cabinet. Its security cover slides
    # between two fixed guides and remains visibly mounted when raised.
    wb((1904,-248,304),(2000,-172,316),"rail_metal",detail=True)
    wb((1912,-240,316),(1992,-176,424),"toolbox_blue",detail=True)
    wb((1904,-244,424),(2000,-172,432),"rail_metal",detail=True)
    for x in (1904,1992):
        wb((x,-264,316),(x+8,-236,526),"rail_metal",detail=True)
    wb((1904,-264,526),(2000,-236,538),"rail_metal",detail=True)
    for lo,hi in [((1912,-244,344),(1920,-240,424)),((1984,-244,344),(1992,-240,424)),
                  ((1920,-244,344),(1984,-240,352)),((1920,-244,408),(1984,-240,424))]:
        wb(lo,hi,"rail_metal",detail=True)
    ent("func_button",geometry=[box((1920,-248,352),(1984,-240,408),"rail_metal",
        face_overrides={2:dict(texture="depart_switch",scale=(.5,.875),shift=(-3840,408/.875))})],
        target="depart_arm",angle=90,lip=6,speed=16,wait=-1,sounds=1,_endline_objective="departure")
    ent("func_door",geometry=[box((1912,-264,336),(1992,-248,432),"hazard")],
        targetname="endline_control_cover",angle=-1,speed=64,wait=-1,lip=0,sounds=1)
    light(1952,-344,460,175,"1 .92 .78")
    relay("depart_arm","endline_depart_permission")
    ent("trigger_counter",targetname="endline_depart_permission",target="endline_extract",count=2,spawnflags=1)
    relay("depart_arm",message="DEPARTURE REQUESTED\nAll living players: board the REAR flatcar.\nThe train will leave when everyone is aboard.")
    ent("trigger_platoon_extract",geometry=[box((1456,-128,305),(1920,128,440),"rail_metal")],
        targetname="endline_extract",spawnflags=4,target="endline_depart",_endline_objective="rally")
    relay("endline_depart","endline_train")
    relay("endline_depart",message="SHIPMENT CAPTURED - HOLD ON!\nBack across the bridge. Keep clear of the wheels.")
    helptext("endline_depart","Shipment captured. Ride the rear flatcar across the bridge to the garage door.")
    ent("target_platoon_intermission",targetname="endline_complete",map="*pp_endline",count=10,
        message="OPERATION END OF THE LINE\\nAmmunition train captured. Squad extracted.\\nMISSION COMPLETE",_endline_objective="complete")
    ent("info_player_intermission",(-3504,0,480),angles="10 0 0")


def reserve_bays():
    # Roofed packaging rooms, with solid sides and full-height shutter doors.
    wb((-1472,-640,224),(-896,-352,240),"sleeper_wood",detail=True)
    for lo,hi in [((-1472,-640,240),(-1448,-352,432)),
                  ((-920,-640,240),(-896,-352,432)),
                  ((-1448,-640,240),(-920,-616,432)),
                  ((-1472,-376,240),(-1376,-352,432)),
                  ((-960,-376,240),(-896,-352,432))]:
        wb(lo,hi,"toolbox_blue")
    wb((-1472,-640,432),(-896,-352,456),"toolbox_blue")
    light(-1184,-496,400,300,"1 .84 .60")
    for lo,hi in [((-800,864,0),(-776,1136,208)),((-152,864,0),(-128,1136,208)),
                  ((-776,1112,0),(-152,1136,208)),((-800,864,0),(-736,888,208)),
                  ((-192,864,0),(-128,888,208))]:
        wb(lo,hi,"cardboard")
    wb((-800,864,208),(-128,1136,232),"corrugation")
    light(-448,1008,184,360,".74 .84 1")
    for name,lo,hi,point in [
        ("upper",(-1376,-376,240),(-960,-352,432),(-1184,-364,264)),
        ("lower",(-736,864,0),(-192,888,208),(-448,876,24)),
        ("yard_west",(2112,-1488,0),(2136,-1296,208),(2124,-1392,24)),
        ("yard_north",(2208,-1144,0),(2400,-1120,208),(2304,-1132,24))]:
        ent("func_door",geometry=[box(lo,hi,"hazard")],targetname="endline_reserve_doors",
            angle=-1,speed=240,wait=-1,lip=0,sounds=1,_endline_reserve_door=name)


def main():
    envelope()
    railway()
    insertion()
    station()
    toolbox_and_lower()
    yard()
    reserve_bays()
    secrets()
    train()
    world='// Original Plastic Platoon mission. GPL-2.0-or-later.\n// Generated by tools/maps/generate_endline.py; editable Quake2 MAP.\n{\n"classname" "worldspawn"\n"message" "Operation End of the Line"\n"sky" "sandkeep"\n"sounds" "0"\n"_ambient" "12"\n'+''.join(WORLD)+'}\n'
    source=ROOT/"maps/source/pp_endline.map"
    source.write_text(world+''.join(ENTITIES))
    (ROOT/"baseq2/maps/pp_endline.map").write_text(source.read_text())
    (ROOT/"tools/maps/endline_routes.json").write_text(json.dumps(ROUTES,indent=2)+"\n")
    print(f"Wrote {source}: {len(WORLD)} world brushes, {len(ENTITIES)} entities, {len(ROUTES)} routes")


if __name__ == "__main__":
    main()
