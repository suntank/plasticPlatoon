#!/usr/bin/env python3
"""Author Switchyard, an original low-cost Plastic Platoon deathmatch depot.

All coordinates are Quake II units. Solid walls are built by subtracting the
room volumes from a sealed block, so outside faces do not inflate VIS or RAD.
Only attached architectural details and embedded track are furnished; the four
loading floors remain available for the player's own ABC blocks and cover.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORLD_BOUNDS = (-1088,-1024,-192,1088,1024,544)
CONCRETE = 'endline/concrete'
CREAM = 'bedroom/trim'
METAL = 'bedroom/metal'
BLUE = 'endline/toolbox_blue'
RED = 'endline/loco_red'
WOOD = 'endline/sleeper_wood'
RUBBER = 'endline/rubber'
RAIL = 'endline/rail_metal'
SKY = 'sandkeep/sky'

# Named empty volumes are the architectural master, not imported level data.
ROOMS = [
    ('blue_north',(-1024,96,0,-384,736,352)),
    ('blue_south',(-1024,-736,0,-384,-96,320)),
    ('red_north',(384,96,0,1024,736,352)),
    ('red_south',(384,-736,0,1024,-96,320)),
    ('west_dogleg',(-864,-128,0,-736,128,128)),
    ('east_dogleg',(608,-128,0,736,128,128)),
    ('north_loop',(-800,768,0,800,960,176)),
    ('south_loop',(-800,-960,0,800,-768,176)),
    ('north_blue_entry',(-768,704,0,-672,832,128)),
    ('north_red_entry',(672,704,0,768,832,128)),
    ('south_blue_entry',(-608,-832,0,-512,-704,128)),
    ('south_red_entry',(672,-832,0,768,-704,128)),
    ('west_dock_walk',(-320,-800,0,-192,800,144)),
    ('east_dock_walk',(192,-800,0,320,800,144)),
    ('blue_north_dock',(-416,144,0,-192,240,112)),
    ('blue_south_dock',(-416,-496,0,-192,-400,112)),
    ('red_north_dock',(192,320,0,416,416,112)),
    ('red_south_dock',(192,-688,0,416,-592,112)),
    ('track_lantern',(-192,-800,-128,192,800,512)),
    ('north_track_entry',(-160,768,0,160,960,176)),
    ('south_track_entry',(-160,-960,0,160,-768,176)),
    ('west_ramp_lobby',(-800,-80,0,-640,80,144)),
    ('west_ramp',(-640,-80,-128,-192,80,144)),
    ('east_ramp',(192,128,-128,704,256,144)),
    ('west_gallery',(-352,-704,160,-192,704,352)),
    ('east_gallery',(192,-704,160,352,704,352)),
    ('northwest_landing',(-416,592,160,-192,688,288)),
    ('southeast_landing',(192,-688,160,416,-592,288)),
    ('south_bridge',(-192,-320,160,192,-192,352)),
    ('north_bridge',(-192,256,160,192,384,352)),
]


def point(p):
    return '( '+' '.join(f'{v:g}' for v in p)+' )'


def face(points, texture, *, detail=False, scale=1, shift=(0,0), flags=0, value=0):
    sx,sy = (scale,scale) if isinstance(scale,(int,float)) else scale
    return (' '.join(point(p) for p in points)+f' {texture} {shift[0]:g} {shift[1]:g} 0 '
            f'{sx:g} {sy:g} {134217728 if detail else 0} {flags} {value}\n')


def box(bounds, texture=CREAM, *, detail=False, overrides=None, scale=1):
    x,y,z,X,Y,Z = bounds
    assert x<X and y<Y and z<Z, bounds
    planes = [((x,y,z),(x,Y,Z),(x,y,Z)),((X,y,z),(X,Y,Z),(X,Y,z)),
              ((x,y,z),(X,y,Z),(X,y,z)),((x,Y,z),(X,Y,Z),(x,Y,Z)),
              ((x,y,z),(X,Y,z),(x,Y,z)),((x,y,Z),(X,Y,Z),(X,y,Z))]
    out = []
    for i,plane in enumerate(planes):
        options = dict(texture=texture,detail=detail,scale=scale)
        options.update((overrides or {}).get(i,{}))
        if options['texture']==SKY:
            options['flags']=4
        out.append(face(plane,**options))
    return '{\n'+''.join(out)+'}\n'


def sub(a,b):
    return tuple(x-y for x,y in zip(a,b))


def cross(a,b):
    return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])


def convex(polygons, texture, *, detail=False, top_texture=None):
    points = [p for poly in polygons for p in poly]
    center = [sum(p[i] for p in points)/len(points) for i in range(3)]
    out=[]
    for poly in polygons:
        a,b,c=poly[:3]
        n=cross(sub(a,b),sub(c,b))
        if sum(n[i]*(center[i]-b[i]) for i in range(3))>0:
            a,c=c,a
            n=tuple(-v for v in n)
        out.append(face((a,b,c),top_texture if top_texture and n[2]>0 else texture,detail=detail))
    return '{\n'+''.join(out)+'}\n'


def ramp(bounds, axis, low, high):
    x,y,_,X,Y,_=bounds
    zbase=min(low,high)-32
    height=lambda a,b: low+(high-low)*((a-x)/(X-x) if axis=='x' else (b-y)/(Y-y))
    top=[(a,b,height(a,b)) for a,b in ((x,y),(X,y),(X,Y),(x,Y))]
    bottom=[(a,b,zbase) for a,b,_ in top]
    sides=[[bottom[i],top[i],top[(i+1)%4],bottom[(i+1)%4]] for i in range(4)]
    # Slopes are structural so VIS can use them to occlude the bays behind.
    return convex([bottom,top,*sides],RAIL,top_texture=CONCRETE)


def subtract(bounds, hole):
    low=[max(bounds[i],hole[i]) for i in range(3)]
    high=[min(bounds[i+3],hole[i+3]) for i in range(3)]
    if any(a>=b for a,b in zip(low,high)):
        return [bounds]
    x,y,z,X,Y,Z=bounds
    a,b,c=low;A,B,C=high
    pieces=[(x,y,z,a,Y,Z),(A,y,z,X,Y,Z),(a,y,z,A,b,Z),
            (a,B,z,A,Y,Z),(a,b,z,A,B,c),(a,b,C,A,B,Z)]
    return [p for p in pieces if all(p[i]<p[i+3] for i in range(3))]


def merge_boxes(boxes):
    """Remove construction seams without opening any of the solid partitions."""
    changed=True
    while changed:
        changed=False
        for axis in range(3):
            other=[i for i in range(6) if i not in (axis,axis+3)]
            groups={}
            for b in boxes:
                groups.setdefault(tuple(b[i] for i in other),[]).append(b)
            merged=[]
            for group in groups.values():
                group.sort(key=lambda b:b[axis])
                current=list(group[0])
                for nxt in group[1:]:
                    if current[axis+3]==nxt[axis]:
                        current[axis+3]=nxt[axis+3]
                        changed=True
                    else:
                        merged.append(tuple(current));current=list(nxt)
                merged.append(tuple(current))
            boxes=merged
    return sorted(boxes)


def entity(classname, origin=None, **values):
    keys={'classname':classname}
    if origin is not None:
        keys['origin']=' '.join(f'{v:g}' for v in origin)
    keys.update(values)
    return '{\n'+''.join(f'"{k}" "{v}"\n' for k,v in keys.items())+'}\n'


def generate():
    solids=[WORLD_BOUNDS]
    for _,volume in ROOMS:
        solids=[piece for solid in solids for piece in subtract(solid,volume)]
    solids=merge_boxes(solids)
    brushes=[]
    for b in solids:
        bottom=SKY if b[2]==512 else METAL
        top=RUBBER if b[5]==-128 else CONCRETE
        brushes.append('// Sealed architectural shell\n'+box(b,scale=2,overrides={4:dict(texture=bottom),5:dict(texture=top)}))

    def solid(b,t=RAIL,**kw):
        brushes.append(box(b,t,**kw))
    # The dispatch house is an opaque station building across the service bay.
    # Offset lower doors make an S passage; small dock/gallery doorways retain
    # all circuits while preventing a single view from submitting the depot.
    dispatch=[(-352,-160,-128,352,160,512)]
    passages=[(32,-160,-128,160,-48,16),(-160,-48,-128,160,48,16),
              (-160,48,-128,-32,160,16),(-352,-48,-128,-160,48,16),
              (-304,-160,0,-208,160,112),(208,-160,0,304,160,112),
              (-336,-160,160,-208,160,288),(208,-160,160,336,160,288)]
    for opening in passages:
        dispatch=[piece for part in dispatch for piece in subtract(part,opening)]
    for b in merge_boxes(dispatch):
        solid(b,METAL,scale=2)
    # Attached bridge/landing abutments screen the two long dock sightlines.
    # They occupy the inner edge of the dock walks, outside the loading pads.
    solid((-256,128,-128,-192,256,512),BLUE,scale=2)
    solid((192,-704,-128,256,-576,512),RED,scale=2)
    # Enclosed dock walks and staggered gallery windows prevent broad PVS
    # connections to every pickup/player across the entire central bay.
    for x,X,color,windows in [(-208,-192,BLUE,[(-624,-560),(432,496)]),
                               (192,208,RED,[(-496,-432),(560,624)])]:
        panels=[(x,-800,0,X,800,352)]
        openings=[(x,-320,160,X,-192,288),(x,256,160,X,384,288)]
        openings += [(x,y,192,X,Y,256) for y,Y in windows]
        for opening in openings:
            panels=[piece for panel in panels for piece in subtract(panel,opening)]
        for panel in merge_boxes(panels):
            solid(panel,color,scale=2)
    # Walking elevations: track -128, dock 0, galleries 160. All slopes <=1:2.
    brushes.extend([ramp((-160,544,-128,160,800,0),'y',-128,0),
                    ramp((-160,-800,-128,160,-544,0),'y',0,-128),
                    ramp((-640,-80,-128,-320,80,0),'x',0,-128),
                    ramp((320,128,-128,640,256,0),'x',-128,0),
                    ramp((-592,256,0,-400,576,160),'y',0,160),
                    ramp((400,-576,0,592,-256,160),'y',160,0)])
    # Open bridges over the lower track, and ground-level crossings above its
    # two side access tunnels. Their underside clearance is at least112units.
    for b in [(-192,-320,144,192,-192,160),(-192,256,144,192,384,160),
              (-592,576,144,-192,704,160),(192,-704,144,592,-576,160),
              (-320,-80,-16,-192,80,0),(192,128,-16,320,256,0),
              (640,128,-128,704,256,0)]:
        solid(b,WOOD,overrides={5:dict(texture=RAIL)})
    # Covered bridge structures hide the gallery above from the lower track.
    for y,Y in [(-320,-192),(256,384)]:
        solid((-192,y,288,192,Y,512),METAL,scale=2)
        solid((-192,y,16,192,Y,144),WOOD,scale=2)
        for x,X in [(-192,-112),(112,192)]:
            solid((x,y,-128,X,Y,16),RAIL,scale=2)

    # Wall-mounted molded panels and broad toy timber roof frames. Nothing is
    # placed on the four free construction rectangles listed in the route file.
    halls=[(-1024,96,736,352,BLUE),(-1024,-736,-96,320,BLUE),
           (1024,96,736,352,RED),(1024,-736,-96,320,RED)]
    for outer,ya,yb,ceiling,color in halls:
        west=outer<0
        xa,xb=(outer,outer+8) if west else (outer-8,outer)
        for y in range(ya,yb,128):
            solid((xa,y,16,xb,min(y+128,yb),144),color,detail=True,
                  overrides={1 if west else 0:dict(texture=color,shift=(-y,144))})
        # Two broad wall/ceiling frames per hall establish warehouse scale.
        for y in (ya+160,ya+480):
            xa,xb=(-1024,-384) if west else (384,1024)
            solid((xa,y-12,ceiling-32,xb,y+12,ceiling-8),WOOD,detail=True)
            for x in (xa,xb-16):
                solid((x,y-12,0,x+16,y+12,ceiling-8),WOOD,detail=True)
            # A single textured panel supplies the whole toy light fixture.
            cx=(xa+xb)/2
            solid((cx-40,y-12,ceiling-38,cx+40,y+12,ceiling-32),METAL,detail=True,
                  overrides={4:dict(texture='sandkeep/lamp',scale=(2.5,.75),
                                    shift=(-(cx-40)/2.5,(y+12)/.75),flags=1,value=100)})
        # Rubber kick plate sits against the outside wall, clear of movement.
        solid((xa if west else outer-9,ya,0,(outer+9) if west else outer,yb,16),RUBBER,detail=True)

    # Attached gallery edging leaves both broad bridge crossings open. It is a
    # small8unitstep, not cover; the galleries can be furnished by the player.
    for x,X,color in [(-200,-192,BLUE),(192,200,RED)]:
        for y,Y in [(-704,-320),(-192,256),(384,704)]:
            solid((x,y,160,X,Y,168),color,detail=True)
    # Flush embedded toy rails and ties: no train, wheels or prop entities.
    for y in range(-480,545,128):
        solid((-144,y-8,-130,144,y+8,-127.5),WOOD,detail=True)
    for x in (-68,60):
        solid((x,-544,-130,x+8,544,-127.5),RAIL,detail=True)
    # Sparse hazard paint on bridge lips and ramp entrances.
    for y in (-320,376):
        solid((-192,y,152,192,y+8,160),RAIL,detail=True,
              overrides={2:dict(texture='endline/hazard',scale=.5),3:dict(texture='endline/hazard',scale=.5)})

    def sign(cx,y,z,texture,w=192,h=96,north=False):
        x=cx-w/2;sx,sy=w/256,h/128
        horizontal=-sx if north else sx
        offset=(x+w)/sx if north else -x/sx
        solid((x,y,z,x+w,y+4,z+h),RAIL,detail=True,
              overrides={3 if north else 2:dict(texture=texture,scale=(horizontal,sy),shift=(offset,(z+h)/sy))})
    sign(-720,731,224,'endline/sign_freight',256,128)
    sign(720,-731,192,'endline/shipping_label',256,128,north=True)
    sign(-496,731,224,'endline/sign_upper',128,64)
    sign(832,731,48,'endline/sign_lower',128,64)

    # Warm warehouse bays, cooler open track. Static lights, no animated props.
    entities=[]
    for x in (-816,-544,544,816):
        for y in (-608,-256,256,608):
            entities.append(entity('light',(x,y,224),light=330,_color='1 .89 .71'))
    for y in (-832,-448,0,448,832):
        for x in (-256,256):
            entities.append(entity('light',(x,y,96),light=200,_color='.72 .87 1'))
    for x in (-720,-400,0,400,720):
        for y in (-864,864):
            entities.append(entity('light',(x,y,104),light=210,_color='1 .94 .82'))
    for x in (-272,272):
        for y in (-608,-64,608):
            entities.append(entity('light',(x,y,256),light=230,_color='.75 .88 1'))
    for y in (-480,-128,192,480):
        entities.append(entity('light',(0,y,-24),light=300,_color='.77 .89 1'))
    for x in (-480,480):
        entities.append(entity('light',(x,0 if x<0 else 192,40),light=250,_color='.76 .88 1'))
    for y in (-256,320):
        entities.append(entity('light',(0,y,264),light=250,_color='.78 .89 1'))
    entities.append(entity('light',(-800,0,96),light=230,_color='1 .88 .68'))
    entities.append(entity('light',(672,0,96),light=230,_color='1 .88 .68'))

    # Bay starts face their own dock exits rather than opposing bay starts.
    spawns=[((-832,-576,24.125),15),((-832,480,24.125),330),
            ((832,512,24.125),180),((832,-544,24.125),90),
            ((-800,0,24.125),0),((480,864,24.125),180),
            ((-480,-864,24.125),0),((480,-640,184.125),90)]
    for pos,angle in spawns:
        entities.append(entity('info_player_deathmatch',pos,angle=angle))
    for i,(x,y) in enumerate([(-832,-576),(-768,-576),(-832,-512),(-768,-512)]):
        entities.append(entity('info_player_start' if i==0 else 'info_player_coop',(x,y,24.125),angle=90))
    entities.append(entity('info_player_intermission',(-272,320,208),angles='12 15 0'))

    pickups=[]
    def pickup(kind,x,y,z=0):
        pos=[x,y,z+24]
        entities.append(entity(kind,pos))
        pickups.append(dict(classname=kind,origin=pos))
    for kind,x,y,z in [
        ('weapon_shotgun',-848,-448,0),('weapon_shotgun',848,448,0),
        ('weapon_machinegun',-848,448,0),('weapon_machinegun',848,-448,0),
        ('weapon_supershotgun',-800,0,0),('weapon_chaingun',-480,640,160),
        ('weapon_grenadelauncher',272,320,160),('weapon_rocketlauncher',0,0,-128),
        ('item_armor_body',848,640,0),('item_health_large',-848,640,0),
        ('item_health_large',848,-640,0),
        ('ammo_shells',-912,-448,0),('ammo_shells',912,448,0),
        ('ammo_shells',-736,0,0),('ammo_shells',-736,-864,0),
        ('ammo_bullets',-912,448,0),('ammo_bullets',912,-448,0),
        ('ammo_bullets',-432,640,160),('ammo_bullets',-528,640,160),
        ('ammo_bullets',736,864,0),('ammo_bullets',-256,-448,0),
        ('ammo_gl_rounds',272,448,160),('ammo_gl_rounds',272,512,160),
        ('ammo_rockets',96,-96,-128),('ammo_rockets',-96,192,-128)]:
        pickup(kind,x,y,z)

    header=('// Operation Switchyard. Original Plastic Platoon deathmatch architecture.\n'
            '// Editable source; regeneration overwrites manual changes.\n'
            '// Main loading floors deliberately empty for user-supplied ABC blocks.\n'
            '{\n"classname" "worldspawn"\n"message" "Operation Switchyard"\n'
            '"sky" "sandkeep"\n"sounds" "0"\n')
    text=header+''.join(brushes)+'}\n'+''.join(entities)
    routes=route_document(spawns,pickups)
    return text,routes,dict(shell_brushes=len(solids),world_brushes=len(brushes),entities=len(entities),
                            authored_rooms=[dict(name=n,bounds=b) for n,b in ROOMS],
                            empty_build_areas=routes['open_build_areas'])


def route_document(spawns,pickups):
    nodes={
        'blue_south':[-832,-416,0],'blue_north':[-832,416,0],
        'red_north':[832,416,0],'red_south':[832,-416,0],
        'west_junction':[-800,0,0],'east_junction':[672,0,0],
        'north_loop':[0,864,0],'south_loop':[0,-864,0],
        'west_dock_north':[-256,448,0],'west_dock_south':[-256,-448,0],
        'east_dock_north':[256,368,0],'east_dock_south':[256,-400,0],
        'track_center':[0,0,-128],'track_north':[0,512,-128],'track_south':[0,-512,-128],
        'west_gallery_north':[-272,640,160],'west_gallery_south':[-272,-640,160],
        'east_gallery_north':[272,640,160],'east_gallery_south':[272,-640,160],
        'blue_upper':[-496,640,160],'red_upper':[496,-640,160],
    }
    routes=[]
    def connect(a,b,*points):
        routes.append(dict(name=a+'__'+b,**{'from':a,'to':b},
                           points=[nodes[a],*map(list,points),nodes[b]],bidirectional=True))
    connect('blue_south','west_junction',(-800,-160,0))
    connect('west_junction','blue_north',(-800,160,0))
    connect('red_south','east_junction',(704,-320,0),(704,-96,0))
    connect('east_junction','red_north',(736,192,0),(736,288,0))
    connect('blue_north','north_loop',(-720,640,0),(-720,864,0))
    connect('north_loop','red_north',(720,864,0),(720,640,0))
    connect('blue_south','south_loop',(-560,-640,0),(-560,-864,0))
    connect('south_loop','red_south',(720,-864,0),(720,-640,0))
    connect('blue_north','west_dock_north',(-672,192,0),(-288,192,0),(-288,288,0))
    connect('blue_south','west_dock_south',(-640,-448,0))
    connect('red_north','east_dock_north',(640,368,0))
    connect('red_south','east_dock_south',(704,-640,0),(288,-640,0),(288,-544,0))
    connect('west_dock_south','west_dock_north',(-288,96,0),(-288,288,0))
    connect('east_dock_south','east_dock_north')
    connect('west_dock_north','north_loop',(-256,864,0))
    connect('east_dock_south','south_loop',(288,-544,0),(288,-736,0),(256,-800,0),(256,-864,0))
    connect('track_center','track_north',(-96,0,-128),(-96,192,-128),(0,256,-128))
    connect('track_center','track_south',(96,0,-128),(96,-192,-128),(0,-256,-128))
    connect('track_north','north_loop',(0,544,-128),(0,800,0))
    connect('track_south','south_loop',(0,-544,-128),(0,-800,0))
    connect('west_junction','track_center',(-640,0,0),(-320,0,-128),(0,0,-128))
    connect('east_junction','track_center',(672,192,0),(640,192,0),(320,192,-128),
            (0,192,-128),(-96,192,-128),(-96,0,-128))
    connect('blue_north','blue_upper',(-672,224,0),(-496,224,0),(-496,256,0),(-496,576,160))
    connect('blue_upper','west_gallery_north')
    connect('red_south','red_upper',(672,-224,0),(496,-224,0),(496,-256,0),(496,-576,160))
    connect('red_upper','east_gallery_south')
    connect('west_gallery_south','west_gallery_north')
    connect('east_gallery_south','east_gallery_north')
    connect('west_gallery_north','east_gallery_north',(-272,320,160),(272,320,160))
    connect('west_gallery_south','east_gallery_south',(-272,-256,160),(272,-256,160))
    areas=[dict(name='blue_north_build_pad',min=[-960,352],max=[-640,640],z=0),
           dict(name='blue_south_build_pad',min=[-960,-640],max=[-640,-352],z=0),
           dict(name='red_north_build_pad',min=[640,352],max=[960,640],z=0),
           dict(name='red_south_build_pad',min=[640,-640],max=[960,-352],z=0)]
    probes=[dict(name=n,point=p) for n,p in nodes.items()]
    for i,(pos,_) in enumerate(spawns):
        probes.append(dict(name=f'spawn_floor_{i}',point=[pos[0],pos[1],pos[2]-24.125]))
    return dict(schema_version=1,map='pp_switchyard',nodes=nodes,routes=routes,
                floor_probes=probes,open_build_areas=areas,
                spawns=[dict(origin=p,angle=a) for p,a in spawns],pickups=pickups,
                budget_note='At most7/6 Temple compiled/renderable triangles; runtime samples reported separately.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'maps/source/pp_switchyard.map')
    args=parser.parse_args()
    text,routes,report=generate()
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(text)
    (ROOT/'tools/maps/switchyard_routes.json').write_text(json.dumps(routes,indent=2)+'\n')
    out=ROOT/'build/maps/pp_switchyard';out.mkdir(parents=True,exist_ok=True)
    (out/'layout.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'{args.output}: {report["shell_brushes"]} shell brushes, {report["world_brushes"]} total, {len(routes["routes"])} routes')


if __name__=='__main__':
    main()
