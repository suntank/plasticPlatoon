#!/usr/bin/env python3
"""Build the hand-authored Attic spaces, then compile and package the map."""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from attic_creature_assets import creature_assets
from attic_materials import DIFFUSER, FLOOR, PANEL, WALL, write_materials
from build_endline import BASE, LOCAL_TOOL, ROOT, bsp_inventory, prepare_assets
from generate_attic_prefabs import PREFABS as ATTIC_PROPS
from generate_bedroom_prefabs import PREFABS as BEDROOM_PROPS
from generate_switchyard import box, convex, cross, merge_boxes, subtract

SOURCE = ROOT / 'maps/source/pp_attic.map'
WOOD = 'bedroom/attic_wood'
TRIM = 'bedroom/trim'
CARD = 'bedroom/cardboard'
STEEL = 'bathroom/garage_steel'
BRASS = 'bedroom/attic_brass'
SKY = 'sandkeep/sky'
PROPS = ATTIC_PROPS | BEDROOM_PROPS

# These volumes are hand positioned; overlapping volumes share the same air.
# Independent ceilings and floor heights let rooms pass through one another.
ENVELOPE = (-3328, -3808, -176, 3296, 3664, 654)
SPACES = (
    ('Hatch',                  (-416,-3696,   0,  416,-3088, 462)),
    ('Hatch throat',           (-104,-3120,   0,  104,-2784, 180)),
    ('Pillar field',           (-848,-2848,   0,  864,-1968, 184)),
    ('West offset',           (-1112,-2304,   0, -800,-2080, 176)),
    ('Storage that opens',    (-2432,-2416,   0,-1056,-1152, 240)),
    ('Upper carton flight',   (-2032,-1220,   0,-1648, -864, 258)),
    ('Lower carton flight',   (-1536,-1248,-104,-1200, -864, 218)),
    ('Bridge and atrium',     (-2240, -896,-104, -496,  512, 392)),
    ('Low route to nowhere',   (-552, -512,-104,   16, -280, 113)),
    ('Basement fragment',      (-80, -704,-104,  784,  192, 156)),
    ('Ungated shore',         (-2056,  464,  96,-1752,  784, 302)),
    ('Gable behind ceiling',  (-2368,  720,  96,-1136, 1336, 432)),
    ('Roof break',            (-2256,  808, 432,-1536, 1288, 576)),
    ('Service concourse',     (-1328,  990,  96, 1264, 1584, 278)),
    ('Blocked stair',          (-544, 1536,  96,  128, 1832, 316)),
    ('Down to the counter',     (796, 1488, -32, 1112, 2024, 276)),
    ('Counter floor',          (-432, 1944, -32, 1920, 2736, 164)),
    ('Missing tile',           (1008, 2376, -56, 1208, 2544, -32)),
    ('Stalled lobby',          (-432, 2672, -32,  192, 3296, 184)),
    ('Service fold',           (1712, 2672, -32, 1936, 3040, 134)),
    ('Last ceiling',           (1640, 2944, -32, 3056, 3496, 235)),
    ('Waiting hall throat',     (824,-2792,   0, 1152,-2600, 144)),
    ('Waiting hall',           (1088,-3072,   0, 2232,-2128, 195)),
    ('East apron',             (1832,-2192,   0, 2168,-1256, 176)),
    ('Blank annex',            (1440,-1320,   0, 2632, -392, 208)),
    ('Unoccupied aisle',       (2450, -464,   0, 3024, 1096, 164)),
    ('Shallow turnout',         (432,-2016,   0,  656,-1800, 138)),
    ('Copy of a waiting room',   (-16,-1888,   0, 1008,-1424, 152)),
)

# Wall fragments, piers, raised walks, and railings occupy the open volumes.
# Their endpoints deliberately miss the ceiling grid and the adjacent walls.
MASSES = (
    ('Pillar field', (
        (-585,-2580,0,-493,-2472,184), (-386,-2280,0,-290,-2184,184),
        ( 231,-2472,0, 341,-2352,184), ( 391,-2208,0, 480,-2104,184),
        (-735,-2848,0,-683,-2614,184), ( 675,-2318,0, 864,-2254,184),
        (-126,-2060,0, 250,-1968,184),
    )),
    ('Storage', (
        (-2216,-2024,0,-2144,-1712,240), (-1592,-2416,0,-1516,-2188,240),
        (-1512,-1896,0,-1432,-1712,240), (-2392,-1512,0,-2272,-1168,240),
        (-1320,-2152,0,-1056,-2080,240),
    )),
    ('Atrium raised floors', (
        (-2240,-864,-104,-1584,-658,96),
        (-1912,-658,72,-1688,272,96),
        (-2240,272,-104,-496,512,96),
        (-1384,-225,70,-1024,108,96),
        (-2240,-96,-104,-2152,160,392),
        (-960,66,-104,-888,272,392),
    )),
    ('Service concourse', (
        (-784,990,96,-716,1230,278), (-112,1280,96,-40,1584,278),
        (338,990,96,414,1180,278), (1134,1264,96,1264,1320,278),
        (-912,1456,96,-836,1534,278),
    )),
    ('Counter hall', (
        (101,1944,-32,176,2192,164), (456,2276,-32,528,2536,164),
        (1296,2584,-32,1352,2736,164), (835,2100,-32,910,2240,164),
        (-240,2396,-32,-168,2736,164), (1552,1944,-32,1624,2232,164),
    )),
    ('East copies', (
        (1352,-2872,0,1428,-2784,195), (1656,-2648,0,1736,-2568,195),
        (1530,-2216,0,1650,-2128,195), (2008,-3032,0,2080,-2900,195),
        (1784,-1056,0,1880,-976,208), (2352,-824,0,2424,-656,208),
        (2720,-296,0,2800,336,164), (2450,590,0,2656,646,164),
    )),
)

# Waypoints describe swept routes through the spaces, independently of their
# brush boundaries. The lower floor has its own nodes under the bridge.
PATHS = (
    (None, (
        ('sill',(0,-2988,25)), ('entry',(0,-2736,25)),
        ('lobby_west',(-380,-2560,25)), ('lobby_offset',(-677,-2208,25)),
        ('west_throat',(-962,-2192,25)), ('west_entry',(-1216,-2216,25)),
        ('west_centre',(-1680,-2078,25)), ('west_stack',(-1810,-1736,25)),
        ('upper_foot',(-1810,-1256,25)), ('upper_head',(-1810,-818,121)),
        ('bridge_start',(-1800,-590,121)), ('bridge_middle',(-1800,-214,121)),
        ('bridge_end',(-1800,126,121)), ('shelf',(-1888,392,121)),
        ('gable_gate',(-1888,678,121)), ('gable_front',(-1840,900,121)),
        ('gable_east',(-1536,1080,121)), ('concourse_entry',(-1170,1226,121)),
        ('concourse_west',(-874,1310,121)), ('concourse_bend',(-462,1330,121)),
        ('concourse_middle',(63,1160,121)), ('concourse_east',(569,1283,121)),
        ('ramp_approach',(960,1424,121)), ('drop_foot',(957,1544,121)),
        ('drop_head',(957,2050,-7)), ('counter_entry',(1100,2170,-7)),
        ('counter_mid',(1290,2330,-7)), ('counter_east',(1884,2300,-7)),
        ('counter_bend',(1884,2456,-7)),
        ('fold',(1818,2820,-7)), ('last_room',(1838,3128,-7)),
        ('last_bend',(2296,3170,-7)), ('cache',(2752,3184,-7)),
    )),
    ('entry', (
        ('east_lobby',(420,-2670,25)), ('east_mouth',(952,-2688,25)),
        ('waiting_west',(1288,-2640,25)), ('waiting_middle',(1538,-2476,25)),
        ('waiting_east',(1990,-2416,25)), ('apron',(1990,-1976,25)),
        ('apron_end',(1990,-1450,25)), ('annex',(1996,-1130,25)),
        ('annex_gap',(2170,-784,25)), ('annex_turn',(2150,-502,25)),
        ('long_aisle',(2584,-519,25)), ('aisle_low',(2548,-332,25)),
        ('aisle_middle',(2500,222,25)), ('aisle_turn',(2800,490,25)),
        ('aisle_far',(2790,880,25)),
    )),
    ('east_lobby', (
        ('copy_approach',(550,-2472,25)), ('copy_lobby',(550,-2072,25)),
        ('copy_throat',(544,-1870,25)), ('copy_hall',(530,-1622,25)),
        ('copy_blind',(166,-1570,25)),
    )),
    ('west_stack', (
        ('lower_approach',(-1328,-1460,25)), ('lower_foot',(-1358,-1224,25)),
        ('lower_head',(-1358,-820,-79)), ('lower_south',(-1290,-660,-79)),
        ('lower_under',(-1770,-375,-79)), ('lower_west',(-2090,-300,-79)),
        ('lower_far',(-2040,154,-79)),
    )),
    ('lower_south', (
        ('lower_east',(-850,-396,-79)), ('lower_mouth',(-514,-384,-79)),
        ('basement_front',(74,-384,-79)), ('basement_end',(570,-340,-79)),
    )),
    ('concourse_bend', (('stalled_stair',(-346,1610,121)),)),
    ('counter_mid', (
        ('counter_cross',(1020,2273,-7)), ('counter_side',(638,2250,-7)),
        ('counter_west',(246,2244,-7)), ('stalled_lobby',(48,2800,-7)),
        ('stalled_end',(-83,3120,-7)),
    )),
)

def xyz(values):
    return ' '.join(f'{v:g}' for v in values)


def entity(classname, origin=None, brushes='', **keys):
    if origin is not None:
        keys = dict(origin=xyz(origin), **keys)
    properties = ''.join(f'"{key}" "{value}"\n' for key, value in keys.items())
    return f'{{\n"classname" "{classname}"\n{properties}{brushes}}}\n'


def group(name, group_id, brushes):
    return entity('func_group', brushes=brushes, _tb_type='_tb_group', _tb_name=name,
                  _tb_id=group_id)


def prefab(name, origin, scale, upside_down=False):
    transformed = []
    for line in PROPS[name]().splitlines(keepends=True):
        if not line.startswith('('):
            transformed.append(line)
            continue
        values = re.findall(r'\(\s*([^)]+)\)', line)
        points = [tuple(map(float, value.split())) for value in values]
        u = tuple(b - a for a, b in zip(points[0], points[1]))
        v = tuple(c - a for a, c in zip(points[0], points[2]))
        normal = cross(u, v)
        axis = max(range(3), key=lambda i: abs(normal[i]))
        mapped = [(origin[0] + scale * x,
                   origin[1] + scale * (-y if upside_down else y),
                   origin[2] + scale * (-z if upside_down else z)) for x, y, z in points]
        texture, s, t, rotation, sx, sy, *flags = line.rsplit(')', 1)[1].split()
        sx, sy = float(sx) * scale, float(sy) * scale
        s = float(s) - origin[1 if axis == 0 else 0] / sx
        t = float(t) + origin[1 if axis == 2 else 2] / sy
        coords = ' '.join(f'( {xyz(point)} )' for point in mapped)
        transformed.append(f'{coords} {texture} {s:g} {t:g} {rotation} {sx:g} {sy:g} {" ".join(flags)}\n')
    return ''.join(transformed)



def skin(bounds, *, wall=WALL, floor=FLOOR, ceiling=PANEL, detail=False):
    return box(bounds, wall, scale=1.5, detail=detail, overrides={
        4: {'texture': ceiling, 'scale': 2},
        5: {'texture': floor, 'scale': 1.5},
    })


def layout_shells():
    solid = [ENVELOPE]
    for _, space in SPACES:
        solid = [part for wall in solid for part in subtract(wall, space)]
    return ''.join(skin(bounds) for bounds in merge_boxes(solid))


def slope(x, y, X, Y, bottom, south, north, surface=FLOOR):
    points = [(x,y,south), (X,y,south), (X,Y,north), (x,Y,north)]
    base = [(a,b,bottom) for a,b,_ in points]
    faces = [[base[i], points[i], points[(i+1)%4], base[(i+1)%4]] for i in range(4)]
    return convex([base, points, *faces], CARD, top_texture=surface)


def wedge(points, low, high):
    base = [(x,y,low) for x,y in points]
    top = [(x,y,high) for x,y in points]
    sides = [[base[i],top[i],top[(i+1)%len(top)],base[(i+1)%len(top)]] for i in range(len(top))]
    return convex([base, top, *sides], WALL)


def light(origin, power, tint='1 .95 .82', style=0):
    return entity('light', origin, light=power, _color=tint, style=style)


def fixture(x, y, z, width, length, *, dark=False, style=0):
    outer = (x-width/2, y-length/2, z-4, x+width/2, y+length/2, z+1)
    panel = (outer[0]+4,outer[1]+4,z-7,outer[3]-4,outer[4]-4,z-4)
    layers = box(outer, TRIM, detail=True)
    if dark:
        return layers + box(panel, PANEL, detail=True), ''
    layers += box(panel, DIFFUSER, detail=True, overrides={4: {'flags': 1, 'value': 205}})
    return layers, light((x,y,z-45), 325, '1 .94 .76', style)


# Lighting groups follow remembered ceiling grids, which end or change
# alignment in adjacent spans. The darkness between them is part of the route.
LIGHTS = (
    ('Pillar field lights', 184, 60, 120, (
        (-668,-2710),(-260,-2710),(136,-2710),(526,-2710),(750,-2710),
        (-670,-2422),(-274,-2422),(121,-2422),(552,-2422),
        (-668,-2188),(-172,-2188),(246,-2188),(660,-2188),
    )),
    ('Storage lights', 240, 120, 60, (
        (-1196,-2242),(-1658,-2242),(-2042,-2202),(-2248,-2080),
        (-1730,-1832),(-1980,-1456),(-1256,-1312),
    )),
    ('Atrium lights', 392, 112, 72, (
        (-1984,-814),(-1778,-525),(-1708,-105),(-1778,214),(-1200,324),
        (-784,-300),(-1272,-658),(-1986,374),
    )),
    ('Fluorescent concourse', 278, 68, 128, (
        (-1168,1336),(-942,1336),(-730,1336),(-510,1336),(-296,1336),
        (-70,1156),(151,1156),(509,1336),(743,1336),(966,1336),(1194,1496),
    )),
    ('Counter lights', 164, 104, 60, (
        (-268,2104),(149,2280),(616,2100),(658,2456),(1064,2330),
        (1336,2144),(1680,2272),(1460,2520),(1772,2570),
    )),
    ('Last-room lights', 235, 100, 60, (
        (1780,3188),(2240,3188),(2584,3188),(2910,3436),
    )),
    ('Light left on', 195, 112, 64, (
        (1288,-2656),(1504,-2450),(1976,-2466),(2050,-2840),
    )),
    ('Light copied badly', 208, 60, 120, (
        (1500,-1120),(1750,-854),(2144,-1120),(2200,-527),(2526,-1004),
    )),
    ('Lights running nowhere', 164, 60, 116, (
        (2592,-370),(2550,-120),(2532,140),(2580,428),(2846,711),(2760,968),
    )),
)


def lighting():
    parts = []
    for group_id, (name, z, width, length, placements) in enumerate(LIGHTS, 20):
        brushes, entities = [], []
        for index, (x, y) in enumerate(placements):
            model, light_entity = fixture(x,y,z,width,length,
                                          dark=index % 7 == 4,
                                          style=6 if index % 11 == 2 else 0)
            brushes.append(model)
            entities.append(light_entity)
        # World detail surfaces emit in RAD while leaving the VIS hull alone.
        parts.append(group(name, group_id, ''.join(brushes)))
        parts.extend(entities)
    parts.extend(light(*setting) for setting in (
        ((-1,-3450,184),475,'1 .69 .38'), ((70,-3150,132),255,'1 .78 .48'),
        ((-965,-2192,140),240,'1 .94 .70'), ((-1840,-1064,207),230,'1 .81 .61'),
        ((-1308,-1054,113),220,'1 .92 .69'), ((-1916,-358,31),330,'1 .92 .69'),
        ((-1250,-292,96),320,'1 .93 .66'), ((-590,-388,77),192,'1 .93 .68'),
        ((-1038,-582,246),315,'1 .89 .68'), ((-757,102,158),238,'1 .90 .64'),
        ((-404,-2318,124),255,'1 .94 .73'), ((462,-2592,126),245,'1 .93 .72'),
        ((255,-430,115),207,'1 .82 .57'), ((-1860,655,243),207,'1 .74 .46'),
        ((-2080,1056,342),405,'1 .70 .42'), ((-1504,1120,258),300,'1 .83 .54'),
        ((955,1744,196),250,'1 .91 .72'), ((1818,2824,85),220,'1 .90 .64'),
        ((-270,1299,201),255,'1 .91 .71'), ((578,1168,216),250,'1 .92 .77'),
        ((234,2376,111),270,'1 .94 .73'), ((1414,2366,111),270,'1 .94 .73'),
        ((2752,3184,108),440,'.56 .98 .89'), ((544,-1730,94),166,'.92 .94 .67'),
        ((-68,3108,143),138,'1 .85 .59'),
    ))
    return ''.join(parts)


def add_decks():
    brushes = [
        slope(-2032,-1220,-1648,-864,-32,0,96,CARD),
        skin((-1536,-1248,-104,-1200,-1184,0)),
        slope(-1536,-1184,-1200,-864,-128,0,-104,CARD),
        skin((796,1488,-32,1112,1584,96)),
        slope(796,1584,1112,2024,-57,96,-32),
        slope(-516,1576,-204,1818,72,96,159,CARD),
        wedge([(-630,-2472),(-781,-2310),(-825,-2310),(-685,-2506)],0,184),
        wedge([(736,2496),(890,2590),(866,2640),(704,2536)],-32,164),
    ]
    return ''.join(brushes)


def hatch():
    brushes = skin((-414,-3694,-8,414,-3092,2), floor=WOOD, detail=True)
    brushes += box((-97,-3514,2,97,-3330,4), STEEL, detail=True)
    for x in (-114,102):
        brushes += box((x,-3512,4,x+12,-3333,7), BRASS, detail=True)
    brushes += prefab('rafters', (0,-3432,259), 1.12)
    brushes += box((-416,-3696,452,416,-3090,460), PANEL, overrides={4:{'texture': SKY}})
    return brushes


def rails_and_marks():
    # Counter fragments, rails where a passage goes nowhere, and floor-level
    # brass thresholds that can be read from either direction.
    rails = (
        (-1912,-638,96,-1897,237,136), (-1702,-655,96,-1688,-138,138),
        (-1702,-12,96,-1688,247,138), (-1688,272,96,-1120,288,140),
        (-613,245,96,-498,272,141), (-1384,-225,96,-1024,-209,141),
        (-1540,1476,96,-1224,1494,139),
        (540,1970,-32,556,2211,21), (556,2196,-32,820,2211,21),
        (1552,2348,-32,1845,2364,24), (1098,2602,-32,1250,2618,12),
        (2032,-1346,0,2045,-1137,38), (2608,612,0,2696,628,42),
    )
    thresholds = (
        (-92,-3060,1,92,-3046,6), (-1048,-2290,0,-1038,-2090,4),
        (-1920,-816,96,-1680,-802,100), (-1936,598,96,-1816,612,100),
        (-1242,1140,96,-1230,1280,100), (868,1554,96,1076,1566,100),
        (1722,2828,-32,1926,2840,-28),
    )
    finish = ''.join(box(bounds, WALL, detail=True,
                        overrides={5:{'texture': BRASS}}) for bounds in rails)
    finish += ''.join(box(bounds, BRASS, detail=True) for bounds in thresholds)
    for bounds in (
        (-101,-3092,142,101,-3064,154), (-1052,-2302,139,-1038,-2082,147),
        (-1926,538,204,-1813,548,211), (-1264,1122,230,-1254,1300,237),
        (803,1534,224,1107,1542,231), (1723,2798,108,1920,2810,115),
    ):
        finish += box(bounds, BRASS, detail=True)
    return finish


def baseboards():
    # Only the nearer posts carry complete trim. Along some partitions the
    # baseboard breaks off or continues past what looks like the end of a wall.
    bases = (*MASSES[0][1][:4], *MASSES[3][1][:3], *MASSES[4][1][:3])
    return ''.join(box((x-5,y-5,z,X+5,Y+5,z+10), TRIM, detail=True)
                   for x,y,z,X,Y,_ in bases)


def false_connections():
    # Familiar components cut across incompatible elevations. The open
    # rail around the re-used risers has no matching stair on the other side.
    brushes = box((-2240,26,148,-2038,162,177), CARD, detail=True)
    brushes += box((-2038,93,148,-2004,153,180), WOOD, detail=True)
    brushes += box((-570,-163,-24,-498,-92,109), WALL, detail=True)
    brushes += box((-618,-96,72,-496,24,111), CARD, detail=True)
    brushes += box((616,-680,-104,766,-637,97), WALL, detail=True)
    # A bricked-up opening repeats behind the basement's landing.
    brushes += box((646,-635,-44,741,-630,69), WOOD, detail=True)
    brushes += box((-507,1722,157,-208,1808,166), CARD, detail=True)
    for a in (112, 136, 160):
        brushes += box((-514,1790,a,-205,1818,a+8), WOOD, detail=True)
    return brushes


FURNITURE = (
    ('Attic familiar', (
        ('sheeted_armchair',(252,-3390,2),.90,False),
        ('steamer_trunk',(-240,-3490,2),.70,False),
    )),
    ('Stored in the wallpaper', (
        ('picture_frames',(-773,-2725,0),.51,False),
        ('rocking_chair',(752,-2090,0),.57,False),
    )),
    ('Storage stacks', (
        ('teddy',(-2068,-2190,0),.70,False),
        ('toy_rocket',(-2330,-2140,0),.70,False),
        ('suitcase',(-2128,-1320,0),.71,False),
        ('dresser_steps',(-2260,-1680,0),.57,False),
        ('picture_frames',(-1192,-1632,0),.66,False),
    )),
    ('Half floors', (
        ('sheeted_armchair',(-1110,-64,96),1.0,False),
        ('sheeted_armchair',(-995,-698,392),.78,True),
        ('blanket_stack',(-735,133,-104),.67,False),
        ('clock',(455,-527,-104),.74,False),
        ('clock',(250,-566,-104),.38,False),
    )),
    ('Gable remembers the attic', (
        ('rafters',(-1944,1060,308),1,False),
        ('steamer_trunk',(-2170,1255,96),.79,False),
        ('gramophone',(-1454,1244,96),.68,False),
        ('picture_frames',(-1610,810,96),.75,False),
        ('trunk_open',(-2230,890,96),.62,False),
    )),
    ('Waiting for nothing', (
        ('rocking_chair',(1440,-2807,0),.44,False),
        ('rocking_chair',(1650,-2882,0),.39,False),
        ('rocking_chair',(1840,-2920,0),.68,False),
        ('rocking_chair',(1810,-2916,174),.40,False),
        ('sheeted_armchair',(1540,-706,0),.71,False),
    )),
    ('Wrong end of the counter', (
        ('dress_form',(-250,3078,-32),.65,False),
        ('picture_frames',(184,2152,-32),.5,False),
        ('rocking_chair',(643,2648,-32),.48,False),
        ('blanket_stack',(1832,2164,-32),.39,False),
    )),
    ('Last supply', (
        ('trunk_open',(2774,3372,-32),.81,False),
        ('clock',(2482,3400,-32),1.02,False),
        ('clock',(2368,3370,-32),.62,False),
        ('rolled_rug',(2989,3138,-32),.44,False),
    )),
)


def props():
    return ''.join(entity('func_wall', brushes=''.join(prefab(*placement) for placement in placements),
                          _tb_name=name) for name, placements in FURNITURE)


def paths():
    depth = {}
    parts = []
    for parent, path in PATHS:
        for name, origin in path:
            depth[name] = depth[parent] + 1 if parent else 0
            targets = {'target': f'attic_node_{parent}'} if parent else {}
            parts.append(entity('info_melted_path', origin, targetname=f'attic_node_{name}',
                                count=depth[name], **targets))
            parent = name
    return ''.join(parts)


def trigger(classname, bounds, **keys):
    return entity(classname, brushes=box(bounds, WOOD), **keys)


def mission_entities():
    parts = [
        entity('info_player_start', (0,-3424,34), angle=90),
        *(entity('info_player_coop', origin, angle=90)
          for origin in ((-62,-3424,34),(62,-3424,34),(0,-3354,34))),
        entity('trigger_always', delay=1, target='attic_brief'),
        entity('target_help', targetname='attic_brief', spawnflags=1,
               message=r'Find the flamethrower.\nBrass thresholds mark the way back.'),
        trigger('trigger_once', (-104,-2998,0,104,-2948,144),
                message=r'Find the M1 beyond the low halls.\nRemember the brass thresholds.'),
        entity('weapon_shotgun', (112,-2752,32)),
        entity('ammo_shells', (-1980,-1916,34), count=12),
        entity('item_health', (-1824,-729,126)),
        entity('item_health', (1068,2138,0)),
        trigger('trigger_once', (-1956,494,96,-1780,582,226), target='attic_scrape'),
        entity('target_speaker', (-1536,1030,135), targetname='attic_scrape',
               noise='attic/scrape.wav', volume=.65, attenuation=1),
        trigger('trigger_once', (-1352,1004,96,-1182,1336,251),
                target='attic_wake', message=r'Shots slow it down.\nKeep moving.'),
        entity('monster_melted', (-612,1494,122),
               targetname='attic_wake', spawnflags=2, angle=210),
        entity('weapon_hyperblaster', (2752,3184,5), target='attic_armed',
               message=r'M1 acquired.\nFollow the brass back to the hatch.'),
        entity('ammo_cells', (2841,3136,2), count=40),
        entity('ammo_cells', (556,-328,-71), count=30),
        entity('target_help', targetname='attic_armed', spawnflags=1,
               message=r'Return to the hatch.\nFire can destroy the Melted Soldier.'),
        trigger('trigger_platoon_extract', (-146,-3568,1,144,-3334,143),
                targetname='attic_armed', spawnflags=4, target='attic_exit'),
        entity('target_goal', (0,-3410,58), targetname='attic_exit', target='attic_end'),
        entity('trigger_relay', targetname='attic_end', message='Attic escaped.'),
        entity('target_help', targetname='attic_end', spawnflags=1, message='Attic escaped.'),
    ]
    for origin in ((-622,-2324,26), (-2093,-1840,26), (-1188,-1552,26),
                   (1824,-2540,26), (2216,-826,26), (-1960,-435,-78),
                   (702,-116,-78), (-114,2860,-6), (1461,2450,-6)):
        parts.append(entity('monster_spider', origin, health=82, spawnflags=1, angle=205))
    for origin in ((-270,-2422,166), (599,-2200,160), (-1766,-133,354),
                   (-452,1320,247), (633,2474,148), (2540,140,149)):
        parts.append(entity('target_speaker', origin, noise='attic/ballast.wav', spawnflags=1))
    bounds = (-104,-3084,0,104,-3070,180)
    parts.append(entity('func_door', brushes=box(bounds, STEEL), targetname='attic_end',
                        angle=-1, spawnflags=1, wait=-1, lip=-1, speed=260, sounds=1))
    return ''.join(parts)


def make_map():
    parts = ['// Game: Quake 2\n// Format: Quake2\n',
             entity('worldspawn', message='The Rooms Remember', sky='pp_attic', sounds=0)]
    parts.append(group('Carved shell', 1, layout_shells()))
    for index, (name, spans) in enumerate(MASSES, 2):
        parts.append(group(name, index, ''.join(skin(bounds) for bounds in spans)))
    clip = box((-104,-3084,0,104,-3070,180), WOOD).replace(' 0 0 0\n', ' 131072 128 0\n')
    sky_opening = box((-2256,808,575,-1536,1288,576), PANEL, overrides={4:{'texture': SKY}})
    parts.append(group('Slopes, attic hatch and roof cutout', 8,
                       add_decks() + hatch() + sky_opening + clip))
    parts.append(group('Countertops and brass thresholds', 9, rails_and_marks() + baseboards()))
    parts.append(group('Broken landings and false openings', 10, false_connections()))
    parts.extend((props(), lighting(), paths(), mission_entities()))
    return ''.join(parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tool', default=LOCAL_TOOL)
    parser.add_argument('--regenerate-map', action='store_true',
                        help='replace the editable MAP with the authored layout before compiling')
    args = parser.parse_args()
    if args.regenerate_map:
        SOURCE.write_text(make_map(), encoding='ascii')
    write_materials()
    stage = ROOT / 'build/attic-maze'
    materials = prepare_assets(SOURCE, stage / 'assets')
    subprocess.run([
        sys.executable, str(ROOT / 'tools/performance/compile_map.py'),
        '--source', str(SOURCE), '--tool', str(args.tool), '--basedir', str(stage / 'assets'),
        '--build-dir', str(stage / 'compile'), '--rad-subdiv', '128', '--rad-ambient', '58',
        '--output-dir', str(stage / 'compiled'),
    ], check=True)
    bsp = 'maps/pp_attic.bsp'
    compiled = stage / 'compiled/pp_attic.bsp'
    if bsp_inventory(compiled)['lumps']['planes']['count'] > 32768:
        raise ValueError('Too many BSP planes for the renderers’ signed face indices')
    assets = {'maps/pp_attic.map': SOURCE.read_bytes(), bsp: compiled.read_bytes()}
    assets.update((path.relative_to(BASE).as_posix(), path.read_bytes())
                  for path in (BASE / 'env').glob('pp_attic*.png'))
    assets.update((entry['path'], (BASE / entry['path']).read_bytes())
                  for entry in materials['files'] if entry['path'].startswith('textures/'))
    assets.update(creature_assets())
    output = BASE / 'operation-attic.pk3'
    staged = output.with_suffix('.pk3.tmp')
    with ZipFile(staged, 'w') as pack:
        for name, data in sorted(assets.items()):
            entry = ZipInfo(name)
            entry.external_attr = 0o100644 << 16
            pack.writestr(entry, data, ZIP_DEFLATED, compresslevel=9)
    shutil.copyfile(compiled, BASE / bsp)
    staged.replace(output)
    print(output)


if __name__ == '__main__':
    main()
