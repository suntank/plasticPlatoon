#!/usr/bin/env python3
"""Generate Operation Nightlight, a self-contained bedroom SP/co-op mission.

Uses the existing MAP brush writer and WAL encoder, without changing Sandkeep.
Regenerating overwrites this mission's source and original procedural materials.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

from PIL import Image, ImageDraw
from platoon_palette import load_palette
from generate_sandkeep_materials import write_wal, text as block_text

import generate_sandkeep as brushes

ROOT = Path(__file__).resolve().parents[2]
WORLD, ENTITIES, ROUTES = [], [], []


def panel(color, accent):
    im = Image.new("RGB", (256,128), color)
    d = ImageDraw.Draw(im)
    d.rectangle((3,3,252,124), outline=accent, width=4)
    return im,d


def text(draw, x, y, value, scale, color):
    # Original block lettering shared with Sandkeep; no installed font file.
    block_text(draw, x, y, value, scale, color)


def box(lo, hi, texture="wood", **kw):
    return brushes.box(lo, hi, texture, **kw).replace("sandkeep/", "bedroom/")


def wb(lo, hi, texture="wood", **kw):
    WORLD.append(box(lo, hi, texture, **kw))


def ent(classname, origin=None, geometry=(), **kw):
    values = {"classname": classname}
    if origin is not None:
        values["origin"] = " ".join(str(v) for v in origin)
    values.update(kw)
    ENTITIES.append("{\n" + "".join(f'"{k}" "{v}"\n' for k, v in values.items())
                    + "".join(geometry) + "}\n")


def light(x, y, z, power=500, color="1 .85 .65"):
    ent("light", (x, y, z), light=power, _color=color)


def pickup(kind, x, y, floor=0, **kw):
    ent(kind, (x, y, floor + 24), **kw)


def sign(cx, y, z, texture):
    wb((cx-128, y, z), (cx+128, y+8, z+128), "wood", detail=True,
       face_overrides={2: dict(texture=texture, shift=(128-cx, z+128))})


def trigger(lo, hi, target, **kw):
    ent("trigger_once", geometry=[box(lo, hi, "metal")], target=target, **kw)


def route(name, points, **kw):
    ROUTES.append(dict(name=name, points=points, **kw))


def materials():
    palette = load_palette()
    dest = ROOT / "baseq2/textures/bedroom"
    dest.mkdir(parents=True, exist_ok=True)
    colors = dict(wood=(133, 86, 48), wall=(112, 139, 164), trim=(222, 210, 173),
                  carpet=(65, 91, 105), quilt=(47, 83, 142), pillow=(226, 218, 189),
                  cardboard=(168, 128, 75), pages=(215, 202, 166), red=(165, 53, 46),
                  green=(63, 116, 76), blue=(48, 94, 150), metal=(54, 61, 67),
                  glow=(234, 193, 103), window=(108, 162, 204))
    for name, base in colors.items():
        im = Image.new("RGB", (128, 128), base)
        d = ImageDraw.Draw(im)
        if name in ("wood", "cardboard"):
            for y in range(0, 128, 5):
                shade = tuple(max(0, c-12-y % 7) for c in base)
                d.line([(0,y), (48,y+2), (96,y), (127,y+1)], fill=shade)
        elif name in ("carpet", "quilt", "pillow", "wall"):
            for y in range(0,128,4):
                for x in range(0,128,4):
                    delta = ((x*7+y*13) % 11)-5
                    d.point((x,y), fill=tuple(max(0,min(255,c+delta)) for c in base))
            if name == "quilt":
                for p in range(0,128,32):
                    d.line((p,0,p,127), fill=(103,139,182), width=2)
                    d.line((0,p,127,p), fill=(103,139,182), width=2)
        elif name == "pages":
            for y in range(0,128,4):
                d.line((0,y,127,y), fill=(153,142,116))
        im.save(dest / f"{name}.png")
        write_wal(dest / f"{name}.wal", f"bedroom/{name}", im, palette)
    labels = {
        "briefing": ["OP NIGHTLIGHT", "1 CELL  2 RADIO", "3 TOY CHEST PAD"],
        "battery": ["1 POWER CELL", "TAKE TO DESK", "CLIMB THE BOOKS"],
        "radio": ["2 DESK RADIO", "TOUCH CELL SLOT", "THEN CROSS BRIDGE"],
        "exit": ["3 EXTRACTION", "POWER RADIO FIRST", "RALLY ON THE H"],
        "book": ["BEDTIME", "ADVENTURES", "VOLUME ONE"],
    }
    for name, lines in labels.items():
        im, d = panel(color=(34,63,65), accent=(236,195,105))
        for y, value in zip((20,55,90), lines):
            text(d,128,y,value,2,(240,229,195))
        im.save(dest / f"{name}.png")
        write_wal(dest / f"{name}.wal", f"bedroom/{name}", im, palette)
    for letter in "abc":
        im = Image.new("RGB",(128,128),(215,183,122))
        d = ImageDraw.Draw(im)
        d.rectangle((4,4,123,123),outline=(120,65,36),width=5)
        block_text(d,64,15,letter.upper(),14,(151,46,40))
        im.save(dest / f"letter_{letter}.png")
        write_wal(dest / f"letter_{letter}.wal",f"bedroom/letter_{letter}",im,palette)
    im = Image.new("RGB", (256,256), (44,91,65))
    d = ImageDraw.Draw(im)
    d.ellipse((12,12,243,243), outline=(236,223,167), width=9)
    d.rectangle((88,65,104,191), fill=(236,223,167))
    d.rectangle((151,65,167,191), fill=(236,223,167))
    d.rectangle((88,120,167,136), fill=(236,223,167))
    im.save(dest / "helipad.png")
    write_wal(dest / "helipad.wal", "bedroom/helipad", im, palette)


def room():
    # A sealed, genuinely room-sized envelope. Everything has a physical back.
    wb((-2368,-1984,-64),(2368,1984,0),"carpet")
    wb((-2368,-1984,2048),(2368,1984,2112),"trim")
    for lo,hi in [((-2368,-1984,0),(-2304,1984,2048)),
                  ((2304,-1984,0),(2368,1984,2048)),
                  ((-2304,-1984,0),(2304,-1920,2048)),
                  ((-2304,1920,0),(2304,1984,2048))]:
        wb(lo,hi,"wall")
    for y in (-1920,1896):
        wb((-2304,y,0),(2304,y+24,96),"trim",detail=True)
    for x in (-2304,2280):
        wb((x,-1920,0),(x+24,1920,96),"trim",detail=True)
    # Recess-like luminous window, curtains and a large closed bedroom door.
    wb((-1536,1888,896),(-448,1916,1760),"window",detail=True,
       face_overrides={2:dict(texture="window",flags=1,value=110)})
    for x in (-1568,-1024,-448):
        wb((x,1856,864),(x+32,1888,1792),"trim",detail=True)
    for z in (864,1312,1760):
        wb((-1568,1856,z),(-416,1888,z+32),"trim",detail=True)
    for x in (-1744,-416):
        for i in range(5):
            wb((x+i*24,1824-i%2*16,640),(x+i*24+24,1856,1824),"quilt",detail=True)
    wb((560,-1916,0),(1664,-1880,1792),"wood",detail=True)
    for x in (528,1664):
        wb((x,-1880,0),(x+32,-1848,1824),"trim",detail=True)
    wb((528,-1880,1792),(1696,-1848,1824),"trim",detail=True)
    wb((1488,-1848,800),(1536,-1800,848),"metal",detail=True)
    # Soft broad fill plus localized warm lamp and blue window light.
    for x in (-1600,0,1600):
        for y in (-1280,0,1280):
            light(x,y,1400,1600,".78 .85 1")
    for x in (-1600,-800):
        light(x,1600,1100,1000,".65 .80 1")


def bed_and_start():
    # Raised bed: the complete insertion area and a combat lane fit underneath.
    for x in (-2112,-704):
        for y in (-896,1280):
            wb((x,y,0),(x+96,y+96,448),"wood")
    wb((-2144,-928,400),(-576,1440,448),"wood")
    wb((-2112,-896,448),(-608,1408,640),"pillow")
    wb((-2120,-904,480),(-600,864,656),"quilt",detail=True)
    wb((-2144,1408,0),(-576,1472,1008),"wood")
    wb((-1984,992,640),(-800,1328,736),"pillow",detail=True)
    for x in (-2144,-640):
        wb((x,-960,0),(x+64,-896,736),"wood",detail=True)
    # Shoebox command post, with a broad opening facing east.
    wb((-2032,-1744,0),(-1056,-1120,8),"cardboard",detail=True)
    for lo,hi in [((-2032,-1744,8),(-2008,-1120,160)),
                  ((-2008,-1744,8),(-1056,-1720,160)),
                  ((-2008,-1144,8),(-1056,-1120,160)),
                  ((-1080,-1720,8),(-1056,-1568,160)),
                  ((-1080,-1344,8),(-1056,-1144,160))]:
        wb(lo,hi,"cardboard",detail=True)
    sign(-1520,-1156,24,"briefing")
    starts = [(-1840,-1488,32),(-1712,-1488,32),(-1840,-1360,32),(-1712,-1360,32)]
    ent("info_player_start", starts[0], angle=0)
    for p in starts[1:]:
        ent("info_player_coop",p,angle=0)
    for i,kind in enumerate(("weapon_shotgun","weapon_shotgun","weapon_machinegun","weapon_machinegun")):
        pickup(kind,-1904+i*160,-1632,8)
    for i in range(4):
        pickup("ammo_shells",-1904+i*144,-1216,8)
        pickup("ammo_bullets",-1904+i*144,-1280,8)
    pickup("item_armor_jacket",-1184,-1632,8)
    light(-1520,-1456,256,600)
    for x,y in [(-1504,-640),(-1024,256),(-1760,1104)]:
        light(x,y,256,440,".9 .85 .7")
    trigger((-1984,-1680,8),(-1120,-1184,104),"briefing")
    ent("target_help",targetname="briefing",spawnflags=1,
        message="Recover the dresser power cell. Touch the desk radio slot. Extract on the toy chest.")
    ent("trigger_relay",targetname="briefing",
        message="OPERATION NIGHTLIGHT\\nFind the power cell on the dresser.\\nFollow the green books, then the red books.")
    route("shoebox_to_underbed",[starts[0],[-1152,-1488,32],[-944,-1456,24],[-944,-1024,24],[-944,0,24],[-400,0,28]])


def stairs(cx, y0, count, width, base=0, color="green", direction=1):
    points = [[cx,y0-direction*40,base+24]]
    for i in range(count):
        y = y0+direction*i*32
        lo,hi = sorted((y,y+direction*32))
        top = base+(i+1)*16
        wb((cx-width/2,lo,base),(cx+width/2,hi,top),color,detail=True,
           face_overrides={2:dict(texture="pages"),3:dict(texture="pages")})
        points.append([cx,y+direction*16,top+24])
    return points


def dresser():
    wb((-320,1280,0),(640,1840,384),"wood")
    wb((-344,1256,368),(664,1856,400),"wood",detail=True)
    for z in (48,160,272):
        wb((-288,1264,z),(608,1280,z+88),"cardboard",detail=True)
        for x in (-64,352):
            wb((x,1240,z+32),(x+96,1264,z+48),"metal",detail=True)
    points = stairs(160,456,25,288,color="green")
    route("dresser_book_stair",points+[[160,1320,424],[320,1488,424]])
    pickup("key_power_cube",320,1488,400,target="cell_acquired")
    sign(320,1768,416,"battery")
    light(320,1520,608,500,".7 1 .7")
    # Giant bedside lamp with a tapered fabric shade above its slender stem.
    wb((-240,1360,400),(-80,1520,432),"metal",detail=True)
    wb((-168,1432,432),(-152,1448,912),"metal",detail=True)
    low = [(-368,1232,736),(48,1232,736),(48,1648,736),(-368,1648,736)]
    high = [(-272,1328,1008),(-48,1328,1008),(-48,1552,1008),(-272,1552,1008)]
    WORLD.append(brushes.convex([low,high]+[[low[i],high[i],high[(i+1)%4],low[(i+1)%4]]
                                           for i in range(4)],"pillow").replace("sandkeep/","bedroom/"))
    light(-160,1440,688,720,"1 .78 .45")
    ent("target_help",targetname="cell_acquired",spawnflags=1,
        message="Power cell recovered. Climb the red books to the desk and touch the radio slot.")
    ent("trigger_relay",targetname="cell_acquired",
        message="POWER CELL RECOVERED\\nClimb the RED books to the desk radio.")
    pickup("weapon_supershotgun",-160,1648,400)
    pickup("ammo_shells",-32,1648,400)
    pickup("item_health_large",480,1648,400)


def desk_and_exit():
    for x in (1280,2048):
        for y in (-256,544):
            wb((x,y,0),(x+80,y+80,672),"wood")
    wb((1248,-288,672),(2176,656,704),"wood")
    points = stairs(1488,-1696,44,288,color="red")
    route("desk_book_stair",points+[[1488,-192,728],[1744,176,728]])
    # Desk radio: speaker grille, tuning display, knobs and tall antenna.
    wb((1632,320,704),(2080,576,976),"green",detail=True)
    for x in range(1664,1888,32):
        wb((x,312,752),(x+12,320,944),"metal",detail=True)
    wb((1920,308,848),(2048,320,912),"glow",detail=True,
       face_overrides={2:dict(texture="glow",flags=1,value=150)})
    for x in (1944,2016):
        wb((x,288,752),(x+32,312,784),"metal",detail=True)
    wb((2048,512,976),(2064,528,1328),"metal",detail=True)
    sign(1856,304,992,"radio")
    # Repeatable touch trigger permits trying the slot before finding the cell.
    ent("trigger_multiple",geometry=[box((1696,200,704),(1984,304,784),"metal")],
        target="radio_key",wait=1)
    ent("trigger_key",targetname="radio_key",item="key_power_cube",target="radio_online")
    ent("target_help",targetname="radio_online",spawnflags=1,
        message="Radio online! Cross the ruler bridge and rally on the toy chest extraction pad.")
    ent("trigger_relay",targetname="radio_online",
        message="RADIO ONLINE - EXTRACTION READY\\nCross the ruler bridge. Rally on the H.")
    # Ruler bridge and its real safety rails; gate stays open after activation.
    wb((1936,656,688),(2128,1040,704),"pages",detail=True)
    for x in (1920,2128):
        wb((x,640,704),(x+16,1040,752),"wood",detail=True)
    ent("func_door",geometry=[box((1936,752,704),(2128,776,864),"red")],
        targetname="radio_online",angle=-1,speed=120,wait=-1,lip=2,sounds=1)
    # Oversized toy chest; the roof is reached only through the elevated route.
    wb((1184,1024,0),(2208,1792,480),"blue")
    wb((1168,1008,480),(2224,1808,512),"wood")
    for x in (1200,2152):
        wb((x,1000,80),(x+40,1008,432),"metal",detail=True)
    wb((1648,992,336),(1744,1008,432),"metal",detail=True)
    # Descending books make all of the extraction route walkable.
    # High at the bridge, low at the chest interior.
    for i in range(12):
        wb((1936,1024+i*32,512),(2128,1056+i*32,704-i*16),"blue",detail=True)
    wb((1392,1376,512),(1904,1760,520),"green",detail=True)
    wb((1520,1440,520),(1776,1696,522),"green",detail=True,
       face_overrides={5:dict(texture="helipad",shift=(-1520,1696))})
    sign(1648,1776,536,"exit")
    for x in (1424,1872):
        for y in (1408,1728):
            wb((x-8,y-8,520),(x+8,y+8,544),"glow",detail=True,
               face_overrides={5:dict(texture="glow",flags=1,value=160)})
            light(x,y,592,220,".6 1 .6")
    trigger((1536,1456,522),(1760,1680,624),"mission_complete",
            targetname="radio_online",spawnflags=4,
            message="OPERATION NIGHTLIGHT COMPLETE\\nThe platoon is coming home.")
    ent("target_changelevel",targetname="mission_complete",map="*pp_bedroom")
    ent("info_player_intermission",(1072,832,1088),angles="20 48 0")
    points = [[2032,624,728],[2032,992,728]]
    points += [[2032,1040+i*32,728-i*16] for i in range(12)]
    points += [[2032,1440,536],[1840,1440,544],[1648,1568,546]]
    route("radio_to_extraction",points,opened_doors=["radio_online"])
    light(1832,128,1120,800)


def floor_cover_and_combat():
    # A rug, scattered alphabet-sized blocks, a toy tunnel and pencil cover.
    wb((-448,-704,0),(1024,320,4),"quilt",detail=True)
    for i,(x,y,h,col) in enumerate([(-352,-960,80,"red"),(320,-640,96,"green"),(736,-160,80,"blue"),
                      (784,880,96,"red"),(-400,848,64,"green"),(-1504,448,64,"red")]):
        wb((x,y,4),(x+144,y+144,h),col,detail=True,
           face_overrides={2:dict(texture="letter_"+"abc"[i%3],scale=(144/128,(h-4)/128),
                                  shift=(-x/(144/128),h/((h-4)/128)))})
    # Two low boxes under the bed interrupt long enemy sightlines.
    for x,y in [(-1872,-320),(-1376,768)]:
        wb((x,y,0),(x+352,y+224,88),"cardboard",detail=True)
    wb((608,-1360,0),(1056,-1120,72),"red",detail=True)
    wb((624,-1344,72),(1040,-1136,80),"pages",detail=True)
    # A roofed toy block tunnel offers a second approach and resupply.
    for y in (512,768):
        wb((720,y,0),(1120,y+48,128),"blue",detail=True)
    wb((720,512,128),(1120,816,160),"red",detail=True)
    for kind,x,y,z in [("ammo_bullets",800,656,0),("item_health",1008,656,0),
                        ("weapon_machinegun",-1760,96,0),("ammo_bullets",-1648,96,0),
                        ("item_health_large",-1536,96,0),("ammo_shells",32,352,0),
                        ("ammo_bullets",336,352,0),("item_health_large",480,352,0),
                        ("item_armor_combat",944,-960,0),("ammo_shells",1168,-1440,0),
                        ("ammo_bullets",1168,-1312,0),("item_health_large",1168,-1184,0),
                        ("weapon_grenadelauncher",1824,-128,704),
                        ("ammo_grenades",1984,-128,704),("item_health_large",2080,96,704),
                        ("ammo_shells",1328,1184,512),("item_health_large",1328,1312,512)]:
        pickup(kind,x,y,z)
    # Ambush enemies stay in their arenas instead of waking across the bedroom.
    positions = [("light",-1600,-640,0),("shot",-1184,288,0),("light",-1824,1040,0),
                 ("shot",-400,192,4),("light",560,-448,4),("heavy",1008,400,0),
                 ("shot",416,1040,0),("light",-224,1728,400),("heavy",544,1696,400),
                 ("shot",1120,-752,0),("light",800,-1648,0),("heavy",2112,-128,704),
                 ("shot",1376,416,704),("heavy",1776,96,704),("shot",1360,1488,512),
                 ("light",1872,1664,520)]
    extra = [("heavy",-1744,544,0),("shot",1056,960,0),("heavy",1488,576,704),
             ("shot",656,-1040,0),("heavy",-448,1136,0),("shot",1232,1632,512)]
    classes = dict(light="monster_soldier_light",shot="monster_soldier",heavy="monster_soldier_ss")
    for i,(kind,x,y,z) in enumerate(positions+extra):
        # 16 easy, 19 normal, 22 hard, with all required items on every skill.
        skill = 0 if i < 16 else (256 if i < 19 else 256|512)
        ent(classes[kind],(x,y,z+24),angle=270,spawnflags=1|skill)
    route("underbed_to_dresser",[[-400,0,28],[-400,352,24],[160,352,24],[160,416,24]])
    route("dresser_to_desk_floor",[[480,416,24],[1168,416,24],[1168,-1744,24],[1488,-1744,24]])


def main():
    materials()
    room()
    bed_and_start()
    dresser()
    desk_and_exit()
    floor_cover_and_combat()
    header = '{\n"classname" "worldspawn"\n"message" "Operation Nightlight"\n"sky" "unit1_"\n"maxrange" "8192"\n'
    path = ROOT / "maps/source/pp_bedroom.map"
    path.write_text("// Generated by tools/maps/generate_bedroom.py\n"+header+"".join(WORLD)+"}\n"+"".join(ENTITIES))
    (ROOT / "tools/maps/bedroom_routes.json").write_text(json.dumps(dict(routes=ROUTES),indent=2)+"\n")
    print(f"Wrote {path}: {len(WORLD)} world brushes, {len(ENTITIES)} entities")


if __name__ == "__main__":
    main()
