#!/usr/bin/env python3
"""Build Operation Sandkeep, an original Quake II SP/co-op mission.

No engine changes or external map geometry are required.  All coordinates are
on a practical editing grid; the generated MAP remains directly editable.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORLD: list[str] = []
ENTITIES: list[str] = []
DETAIL = 134217728


def point(p):
    return "( " + " ".join(f"{v:g}" for v in p) + " )"


def face(points, texture, *, detail=False, scale=1, shift=(0, 0), flags=0, value=0):
    sx, sy = scale if isinstance(scale, tuple) else (scale, scale)
    return (" ".join(point(p) for p in points)
            + f" sandkeep/{texture} {shift[0]:g} {shift[1]:g} 0 {sx:g} {sy:g}"
            + f" {DETAIL if detail else 0} {flags} {value}\n")


def box(lo, hi, texture="sand_wall", *, detail=False, scale=1, face_overrides=None):
    x, y, z = lo
    X, Y, Z = hi
    assert x < X and y < Y and z < Z, (lo, hi)
    # Quake's MAP plane normal is (p0-p1) cross (p2-p1).
    planes = [((x,y,z),(x,Y,Z),(x,y,Z)),
              ((X,y,z),(X,Y,Z),(X,Y,z)),
              ((x,y,z),(X,y,Z),(X,y,z)),
              ((x,Y,z),(X,Y,Z),(x,Y,Z)),
              ((x,y,z),(X,Y,z),(x,Y,z)),
              ((x,y,Z),(X,Y,Z),(X,y,Z))]
    out = "{\n"
    for i, p in enumerate(planes):
        opts = dict(texture=texture, detail=detail, scale=scale)
        if texture == "sky":
            opts.update(flags=5, value=240)
        if face_overrides and i in face_overrides:
            opts.update(face_overrides[i])
        out += face(p, **opts)
    return out + "}\n"


def wb(lo, hi, texture="sand_wall", **kw):
    WORLD.append(box(lo, hi, texture, **kw))


def convex(polygons, texture="sand_wall", *, detail=True, face_options=None):
    """Make a convex brush, orienting every face away from its interior."""
    vertices = [p for poly in polygons for p in poly]
    center = [sum(p[i] for p in vertices)/len(vertices) for i in range(3)]
    lines = []
    for index, poly in enumerate(polygons):
        a, b, c = poly[:3]
        u, v = [a[i]-b[i] for i in range(3)], [c[i]-b[i] for i in range(3)]
        n = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
        assert sum(t*t for t in n) > 0
        if sum(n[i]*(center[i]-b[i]) for i in range(3)) > 0:
            a, c = c, a
        opts = dict(texture=texture, detail=detail)
        if face_options and index in face_options:
            opts.update(face_options[index])
        lines.append(face((a,b,c), **opts))
    return "{\n" + "".join(lines) + "}\n"


def column(poly, bottom, top, texture="sand_wall"):
    low = [(x,y,bottom) for x,y in poly]
    high = [(x,y,top) for x,y in poly]
    return convex([low, high] + [[low[i],high[i],high[(i+1)%len(poly)],low[(i+1)%len(poly)]]
                                for i in range(len(poly))], texture)


def arch_corner(xz, y0, y1):
    a = [(x,y0,z) for x,z in xz]
    b = [(x,y1,z) for x,z in xz]
    WORLD.append(convex([a,b] + [[a[i],b[i],b[(i+1)%len(a)],a[(i+1)%len(a)]]
                                for i in range(len(a))]))


def prism(cx, cy, radius, bottom, top, texture="sand_wall", sides=8, detail=True):
    grid = 8 if radius >= 100 else 1
    poly = [(round((cx + radius*math.cos((i+.5)*2*math.pi/sides))/grid)*grid,
             round((cy + radius*math.sin((i+.5)*2*math.pi/sides))/grid)*grid)
            for i in range(sides)]
    out = "{\n"
    out += face([(x,y,bottom) for x,y in poly[:3]], texture, detail=detail)
    out += face([(x,y,top) for x,y in reversed(poly[:3])], texture, detail=detail)
    for i, (x,y) in enumerate(poly):
        X,Y = poly[(i+1)%sides]
        out += face(((x,y,bottom),(x,y,top),(X,Y,top)), texture, detail=detail)
    WORLD.append(out + "}\n")


def entity(classname, origin=None, brushes=(), **kv):
    data = {"classname": classname}
    if origin is not None:
        data["origin"] = " ".join(f"{v:g}" for v in origin)
    data.update({k: str(v) for k,v in kv.items()})
    # Literal backslash-n is interpreted by ED_NewString as a line break.
    s = "{\n" + "".join(f'"{k}" "{v}"\n' for k,v in data.items())
    ENTITIES.append(s + "".join(brushes) + "}\n")


def trigger(lo, hi, target, **kv):
    entity("trigger_once", brushes=[box(lo, hi, "trim")], target=target, **kv)


def light(x, y, z, power=320, color="1 0.88 0.67"):
    entity("light", (x,y,z), light=power, _color=color)


def ceiling_lamp(cx,cy,z,power=450,color="1 0.90 0.70"):
    wb((cx-36,cy-12,z),(cx+36,cy+12,z+8),"trim",detail=True)
    # The underside's actual compiled projection is (x,-y), like a floor.
    wb((cx-32,cy-8,z-2),(cx+32,cy+8,z),"trim",detail=True,
       face_overrides={4:dict(texture="lamp",scale=(2,.5),
                              shift=(-(cx-32)/2,(cy+8)/.5),flags=1,value=180)})
    light(cx,cy,z-12,power,color)


def pickup(classname, x, y, z=32, **kv):
    entity(classname, (x,y,z), **kv)


def soldier(kind, x, y, z=24, angle=270, skill=0):
    classname = {"light":"monster_soldier_light", "shot":"monster_soldier",
                 "heavy":"monster_soldier_ss"}[kind]
    entity(classname, (x,y,z), angle=angle, spawnflags=skill)


def panel(cx, y, z, name, width=256, height=128):
    # South-facing sign: use x across and -z vertically, with exact one-tile fit.
    x = cx-width/2
    scale = (width/256, height/128)
    wb((x,y,z),(x+width,y+4,z+height), "trim", detail=True,
       face_overrides={2: dict(texture=name, scale=scale,
                              shift=(-x/scale[0], (z+height)/scale[1]))})
    for px in (x+24,x+width-36):
        wb((px,y+4,z-32),(px+12,y+20,z+height-16),"wood",detail=True)


def block(x, y, sx=128, sy=128, height=96, color="plastic_red"):
    wb((x,y,0),(x+sx,y+sy,height), color, detail=True)
    wb((x-4,y-4,0),(x+sx+4,y+sy+4,8), "trim", detail=True)
    wb((x-4,y-4,height-8),(x+sx+4,y+sy+4,height), "wood_end", detail=True)


def shaped_mound(cx, cy, rx, ry, height, texture="sand", lean=(0,0), clip_y=None):
    """An irregular, sloping bank with a small offset crown, not a flat drum."""
    outline = [(-.96,-.32),(-.66,-.82),(.18,-1),(.85,-.56),
               (1,.12),(.58,.84),(-.18,1),(-.8,.62)]
    p = [(round(rx*x/4)*4,round(ry*y/4)*4) for x,y in outline]
    # Keep the terrain on the exact floor and in its own static brush model.
    # World CSG otherwise makes acute floor slivers that qrad bakes nearly black.
    low = [(cx+x,cy+y,0) for x,y in p]
    high = [(cx+x/4+lean[0],cy+y/4+lean[1],height) for x,y in p]
    brush = convex([low,high]+[[low[i],high[i],high[(i+1)%8],low[(i+1)%8]]
                               for i in range(8)],texture)
    if clip_y is not None:
        # Spill stops at the outside board face. Extending a shallow brush into
        # the closed gate/bunker produces dark samples on its exposed tip.
        x,X,h = cx-rx,cx+rx,max(16,height)
        plane = [(x,clip_y,0),(X,clip_y,h),
                 (X if cy>clip_y else x,clip_y,0 if cy>clip_y else h)]
        brush = brush[:-2] + face(plane,texture,detail=True) + "}\n"
    entity("func_wall",brushes=[brush],_sandkeep_terrain=f"{cx} {cy}")


def rotated_box(cx, cy, width, depth, bottom, top, yaw=0, texture="wood", letters=False):
    """World-aligned grain or exactly fitted letter faces on a canted toy cube."""
    c,s = math.cos(math.radians(yaw)),math.sin(math.radians(yaw))
    p = [(round(cx+x*c-y*s,4),round(cy+x*s+y*c,4))
         for x,y in [(-width/2,-depth/2),(width/2,-depth/2),
                     (width/2,depth/2),(-width/2,depth/2)]]
    low,high = [[(x,y,z) for x,y in p] for z in (bottom,top)]
    sides = [[low[i],high[i],high[(i+1)%4],low[(i+1)%4]] for i in range(4)]
    opts = {}
    if letters:
        for i,poly in enumerate(sides):
            dx,dy = p[(i+1)%4][0]-p[i][0],p[(i+1)%4][1]-p[i][1]
            # Q2's dominant-axis projection on vertical faces is +x or +y.
            axis = 0 if abs(dx) >= abs(dy) else 1
            vals = [v[axis] for v in poly]
            direction = dx if axis==0 else dy
            scale = (max(vals)-min(vals))/256 * (1 if direction>0 else -1)
            offset = min(vals) if scale>0 else max(vals)
            opts[i+2] = dict(texture="abc_"+"abcdef"[i],scale=(scale,(top-bottom)/256),
                             shift=(-offset/scale,top/((top-bottom)/256)))
    WORLD.append(convex([low,high]+sides,texture,face_options=opts))


def spool(cx,cy,height=80,radius=44):
    prism(cx,cy,radius,0,12,"wood_end",sides=12)
    prism(cx,cy,radius*.64,12,height-12,"wood",sides=12)
    prism(cx,cy,radius,height-12,height,"wood_end",sides=12)
    prism(cx,cy,8,height,height+2,"iron",sides=8)


def tipped_bucket(cx, front, radius=152, depth=240, color="plastic_blue_smooth", reverse=False, yaw=0):
    """A thick, hollow half-bucket: recognizable toy and usable overhead cover."""
    back = front + (-depth if reverse else depth)
    def emit(polys):
        c,s = math.cos(math.radians(yaw)),math.sin(math.radians(yaw))
        rotated = [[(round(cx+(x-cx)*c-(y-front)*s,4),
                     round(front+(x-cx)*s+(y-front)*c,4),z) for x,y,z in poly] for poly in polys]
        WORLD.append(convex(rotated,color))
    # Each shell segment is a convex tapered prism, with a distinct rolled rim.
    def ring(r):
        return [(round(cx+r*math.cos(i*math.pi/8),4),round(r*math.sin(i*math.pi/8),4))
                for i in range(9)]
    outer,inner = ring(radius),ring(radius-16)
    for i in range(8):
        section = [outer[i],outer[i+1],inner[i+1],inner[i]]
        a = [(x,front,z) for x,z in section]
        b = [(cx+(x-cx)*.84,back,z*.84) for x,z in section]
        emit([a,b]+[[a[j],b[j],b[(j+1)%4],a[(j+1)%4]] for j in range(4)])
        lip = [((cx+(x-cx)*1.04),front-6 if not reverse else front+6,z*1.04)
               for x,z in section]
        emit([a,lip]+[[a[j],lip[j],lip[(j+1)%4],a[(j+1)%4]] for j in range(4)])
    # Closed base at the rear; the opening remains genuinely hollow.
    section = ring(radius*.84)
    a = [(x,back,z) for x,z in section]
    b = [(x,back+(-12 if reverse else 12),z) for x,z in section]
    emit([a,b]+[[a[i],b[i],b[(i+1)%len(a)],a[(i+1)%len(a)]] for i in range(len(a))])


def garden_spade(cx,cy):
    # Rounded shoulder, tapered blade, long shaft and an open D grip.
    blade = [(cx-64,24),(cx-64,112),(cx-40,136),(cx+40,136),(cx+64,112),(cx+48,16),(cx,0)]
    a,b = [[(x,y,z) for x,z in blade] for y in (cy-12,cy+12)]
    WORLD.append(convex([a,b]+[[a[i],b[i],b[(i+1)%len(a)],a[(i+1)%len(a)]]
                               for i in range(len(a))],"plastic_blue_smooth"))
    wb((cx-10,cy-10,112),(cx+10,cy+10,328),"plastic_blue_smooth",detail=True)
    for x in (cx-44,cx+28):
        wb((x,cy-10,312),(x+16,cy+10,392),"plastic_blue_smooth",detail=True)
    wb((cx-44,cy-10,376),(cx+44,cy+10,392),"plastic_blue_smooth",detail=True)
    wb((cx-44,cy-10,312),(cx+44,cy+10,328),"plastic_blue_smooth",detail=True)


def broken_board_wall(y0,y1,reverse=False):
    """Split sandbox boards with staggered splinters and visible end grain."""
    wb((-1024,y0,0),(-224,y1,320),"wood")
    wb((224,y0,0),(1024,y1,320),"wood")
    for side,edges in [(-1,[-152,-176,-128,-160,-104,-144]),
                       (1,[160,136,184,128,160,112])]:
        heights = [0,64,128,192,256,320]
        for i in range(5):
            edge0,edge1 = edges[i],edges[i+1]
            xz = [(side*224,heights[i]),(edge0,heights[i]),
                  (edge1,heights[i+1]),(side*224,heights[i+1])]
            a,b = [[(x,y,z) for x,z in xz] for y in (y0,y1)]
            WORLD.append(convex([a,b]+[[a[j],b[j],b[(j+1)%4],a[(j+1)%4]] for j in range(4)],
                "wood",detail=False,face_options={3:dict(texture="wood_end")}))
    wb((-1024,y0,320),(1024,y1,800),"sky")


def exterior(y0,y1,north=False):
    """A small playable patch of yard, contained by raised earth and fence boards."""
    wb((-896,y0,-64),(896,y1,0),"soil")
    wb((-896,y0,768),(896,y1,800),"sky")
    for x in (-896,864):
        wb((x,y0,0),(x+32,y1,800),"sky")
    end = y1-32 if north else y0
    wb((-896,end,0),(896,end+32,800),"sky")
    # Garden fence boards have a pointed silhouette rather than a rectangular sky wall.
    for cx in range(-816,817,136):
        peak = 416 + (abs(cx)//136%3)*24
        xz = [(cx-64,0),(cx+64,0),(cx+64,peak-48),(cx,peak),(cx-64,peak-48)]
        a,b = [[(x,y,z) for x,z in xz] for y in (end-12 if north else end+32,end+12 if north else end+56)]
        plank = dict(texture="gate_wood",scale=(4,1),shift=(-(cx-64)/4,0))
        WORLD.append(convex([a,b]+[[a[i],b[i],b[(i+1)%5],a[(i+1)%5]] for i in range(5)],"gate_wood",
                            face_options={0:plank,1:plank,4:dict(texture="wood_end"),
                                          5:dict(texture="wood_end")}))
    # Back rails close the ground-level sightline through the picket gaps.
    rail_y = end-4 if north else end+32
    for z in (32,240):
        wb((-880,rail_y,z),(880,rail_y+12,z+40),"wood",detail=True)
    for x in (-768,768):
        shaped_mound(x,(y0+y1)/2,240,(y1-y0)*.48,176,"grass",lean=(0,16))
        # Broad upright stems reinforce the toy scale without noisy alpha foliage.
        for dx,dy,h,yaw in [(-32,-176,208,-30),(40,96,272,65),(-16,256,224,20)]:
            c,s=math.cos(math.radians(yaw)),math.sin(math.radians(yaw))
            def leafpoint(px,py,pz):
                return (x+dx+px*c-py*s,(y0+y1)/2+dy+px*s+py*c,pz)
            # Varied broad, leaning blades remain visible from the yard path.
            p=[leafpoint(-24,-4,64),leafpoint(24,-4,64),leafpoint(72,0,80+h)]
            q=[leafpoint(-24,4,64),leafpoint(24,4,64),leafpoint(72,8,80+h)]
            WORLD.append(convex([p,q]+[[p[i],q[i],q[(i+1)%3],p[(i+1)%3]] for i in range(3)],"grass"))
    for x in (-448,448):
        light(x,(y0+y1)/2,448,600,"1 .96 .86")


def crenels_x(x0, x1, y, z, depth=40, step=112):
    # A continuous parapet supports each merlon; the embrasures stay open above it.
    wb((x0,y,z),(x1,y+depth,z+16),detail=True)
    for x in range(x0, x1-31, step):
        wb((x,y,z),(min(x+56,x1),y+depth,z+56), detail=True)


def tower(cx, cy, radius=144, height=224):
    def polygon(r):
        return [(cx+round(r*math.cos((i+.5)*math.tau/8)/4)*4,
                 cy+round(r*math.sin((i+.5)*math.tau/8)/4)*4) for i in range(8)]
    def mix(a,b,t):
        return tuple(a[i]+(b[i]-a[i])*t for i in range(2))
    # Tapered packed-sand shaft, a real octagonal coping, and supported battlements.
    WORLD.append(column(polygon(radius+16),0,24))
    p, q = polygon(radius), polygon(radius-12)
    low, high = [(x,y,24) for x,y in p], [(x,y,height-16) for x,y in q]
    WORLD.append(convex([low,high]+[[low[i],high[i],high[(i+1)%8],low[(i+1)%8]] for i in range(8)]))
    WORLD.append(column(polygon(radius),height-16,height))
    outer, inner = polygon(radius), polygon(radius-32)
    for i in range(8):
        j = (i+1)%8
        WORLD.append(column([outer[i],outer[j],inner[j],inner[i]],height,height+16))
        WORLD.append(column([mix(outer[i],outer[j],.2),mix(outer[i],outer[j],.8),
                             mix(inner[i],inner[j],.8),mix(inner[i],inner[j],.2)],height+16,height+64))


def partition(y0, y1, openings):
    """Solid visibility barrier with a generously sized, covered dogleg."""
    xs = sorted({-1024,1024,*[v for a,b,c,d in openings for v in (a,c)]})
    ys = sorted({y0,y1,*[v for a,b,c,d in openings for v in (b,d)]})
    for x,X in zip(xs,xs[1:]):
        for y,Y in zip(ys,ys[1:]):
            mx,my = (x+X)/2,(y+Y)/2
            corridor = any(a <= mx <= c and b <= my <= d for a,b,c,d in openings)
            if not corridor:
                wb((x,y,0),(X,Y,320))
            else:
                wb((x,y,160),(X,Y,320))
    # SKY volumes still seal and occlude, while silhouettes remain castle-like.
    wb((-1024,y0+40,320),(1024,y1-40,768), "sky")
    wb((-1024,y0,400),(1024,y0+40,768), "sky")
    wb((-1024,y1-40,400),(1024,y1,768), "sky")
    crenels_x(-1008,1008,y0,320)
    crenels_x(-1008,1008,y1-40,320)


def supply_shelter(x0, y0, mirror=False):
    X,Y = x0+352,y0+272
    wb((x0,y0,0),(X,y0+24,144))
    wb((x0,Y-24,0),(X,Y,144))
    if mirror:
        wb((X-24,y0,0),(X,Y,144))
    else:
        wb((x0,y0,0),(x0+24,Y,144))
    wb((x0,y0,144),(X,Y,168), "wood")
    wb((x0+24,y0+24,0),(X-24,Y-24,4), "wood", detail=True)
    light((x0+X)/2,(y0+Y)/2,120,240)


def door(name, lo, hi, texture="gate_wood"):
    x,y,z = lo
    X,Y,Z = hi
    sx, sy = (X-x)/256, (Z-z)/256
    fit = dict(texture=texture,scale=(sx,sy),shift=(-x/sx,Z/sy))
    brushes = [box(lo,hi,"wood_end",face_overrides={2:fit,3:fit})]
    # Every strap, stile and rivet belongs to the mover, avoiding stationary trim
    # left behind when the gate rises. Faces meet at distinct physical depths.
    for front, back in ((y-4,y),(Y,Y+4)):
        for h in (z+16,Z-32):
            brushes.append(box((x,front,h),(X,back,h+8),"iron"))
            for bx in (x+12,(x+X)/2-2,X-16):
                a,b = (front-2,front) if front < y else (back,back+2)
                brushes.append(box((bx,a,h+2),(bx+4,b,h+6),"trim"))
        brushes.append(box(((x+X)/2-4,front,z+8),((x+X)/2+4,back,Z-8),"wood_end"))
    entity("func_door", brushes=brushes, targetname=name,
           angle=-1, wait=-1, speed=72, lip=2, sounds=1)


def gate_frame(x0,x1,y0,y1,height=160):
    # Chamfered shoulders form a shallow arch without reducing head clearance.
    arch_corner([(x0,height-32),(x0,height),(x0+32,height)],y0,y1)
    arch_corner([(x1-32,height),(x1,height),(x1,height-32)],y0,y1)
    for x in (x0-16,x1):
        wb((x,y0-8,0),(x+16,y1, height+16),"sand_wall",detail=True)
        wb((x-4,y0-12,0),(x+20,y1,16),"sand_wall",detail=True)
    wb((x0-20,y0-8,height),(x1+20,y1,height+16),"sand_wall",detail=True)


def console(cx,y,z,kind,target):
    # Recessed face, projecting guard rails, and a separate travelling push pad.
    wb((cx-64,y,z),(cx+64,y+32,z+100),"trim",detail=True)
    for x in (cx-64,cx+48):
        wb((x,y-16,z+24),(x+16,y,z+88),"iron",detail=True)
    wb((cx-48,y-12,z+16),(cx+48,y,z+24),"iron",detail=True)
    wb((cx-48,y-12,z+88),(cx+48,y,z+96),"iron",detail=True)
    wb((cx-4,y+8,z+100),(cx+4,y+16,z+144),"iron",detail=True)
    wb((cx-4,y-48,z+136),(cx+4,y+16,z+144),"iron",detail=True)
    sx,sy = 80/128,48/64
    # q2tool stores classic shifts as integers: align face bounds to the UV grid.
    left,top = round((cx-40)/5)*5, round((z+80)/3)*3
    entity("func_button",brushes=[box((left,y-20,top-48),(left+80,y+4,top),"trim",
        face_overrides={2:dict(texture="switch_"+kind,scale=(sx,sy),
                               shift=(-left/sx,top/sy))})],
        target=target,wait=-1,angle=90,lip=16,speed=24,sounds=4)
    ceiling_lamp(cx,y-48,z+136,600,"0.78 0.88 1" if kind=="radio" else "1 0.90 0.70")


def secret_chamber(name,x0,x1,y0,y1,opening,rewards):
    a,b = opening
    wb((x0,y0,0),(x0+32,y1,128))
    wb((x1-32,y0,0),(x1,y1,128))
    wb((x0+32,y1-32,0),(x1-32,y1,128))
    wb((x0,y0,128),(x1,y1,160))
    wb((x0+32,y0,0),(a,y0+24,128))
    wb((b,y0,0),(x1-32,y0+24,128))
    wb((a,y0,112),(b,y0+24,128))
    # Same world-aligned sand courses as the surrounding masonry. Only subtle
    # cracks give it away; the supplies and discovery trigger are fully enclosed.
    entity("func_explosive",brushes=[box((a,y0,0),(b,y0+24,112),"sand_wall",
        face_overrides={2:dict(texture="sand_cracked_offset" if name=="cache_one" else "sand_cracked")})],
        health=40,mass=150,dmg=0,_sandkeep_secret=name)
    trigger((a-16,y0+72,0),(b+16,y1-48,80),name)
    entity("target_secret",targetname=name,
           message="Secret found: "+("buried supply cache." if name=="cache_one" else "marksman's reserve."))
    for classname,x,y in rewards:
        pickup(classname,x,y)
    light((x0+x1)/2,y1-64,104,120)
    if name == "cache_one":
        light((x0+x1)/2,y0-80,104,220)


def main():
    # Three readable combat spaces; structural doglegs keep their PVS separate.
    wb((-1088,-2112,-64),(1088,3136,0),"sand")
    wb((-1088,-2112,768),(1088,3136,800),"sky")
    for lo,hi in [((-1088,-2112,0),(-1024,3136,320)),
                  ((1024,-2112,0),(1088,3136,320))]:
        wb(lo,hi,"wood")
        wb((lo[0],lo[1],320),(hi[0],hi[1],800),"sky")
    broken_board_wall(-2112,-2048)
    broken_board_wall(3072,3136,reverse=True)
    exterior(-2944,-2112)
    exterior(3136,3968,north=True)
    # Broad wood rim, oversized screws, and sand banks sell the tabletop scale.
    for x in (-1024,976):
        wb((x,-2048,288),(x+48,3072,320),"wood_end",detail=True)
        for y in range(-1856,3000,384):
            wb((x+4,y,320),(x+44,y+40,328),"iron",detail=True)
    partition(-768,-384,[(384,-768,608,-544),(-224,-608,608,-448),(-224,-512,0,-384)])
    partition(1152,1536,[(384,1152,608,1376),(-224,1312,608,1472),(-224,1408,0,1536)])
    # Packed-sand buttresses and coping give the curtain walls a supported mass.
    for y in (-768,1152):
        for x in (-944,-352,224,800):
            wb((x-32,y-48,0),(x+32,y,240),detail=True)
            wb((x-40,y-56,0),(x+40,y,24),detail=True)
        gate_frame(384,608,y-8,y+32)
    gate_frame(-224,0,1480,1536)
    for x,y in [(496,-672),(224,-528),(-112,-448),(496,1248),(224,1392),(-112,1456)]:
        ceiling_lamp(x,y,152,420)
    # Start in the yard. Spilled sand, splinters and a full-height split explain
    # how the squad gets inside; no freestanding mission sign or staging box.
    for x,y in [(0,-2688),(-96,-2784),(96,-2784),(0,-2816)]:
        entity("info_player_start" if (x,y)==(0,-2688) else "info_player_coop",(x,y,32),angle=90)
    shaped_mound(0,-2128,288,320,8,lean=(0,48),clip_y=-2112)
    rotated_box(-312,-2296,224,40,0,16,-24,"wood_end")
    rotated_box(288,-2184,160,32,0,24,32,"wood")
    shaped_mound(-440,-2448,180,144,48,"soil")
    spool(352,-2552,64,48)
    pickup("weapon_shotgun",-192,-2576)
    pickup("ammo_shells",-288,-2576)
    pickup("ammo_bullets",192,-2576)
    pickup("item_armor_jacket",288,-2576)
    trigger((-112,-2040,0),(112,-1952,96),"briefing")
    entity("trigger_relay",targetname="briefing",target="briefing_help",
           message="OPERATION SANDKEEP\\nSecure the armory and radio switches.\\nThen breach the keep.")
    entity("target_help",targetname="briefing_help",spawnflags=1,
           message="Touch the ARMORY and RADIO control panels. Both are needed to open the keep.")
    # Entry skirmish, toy blocks, and a discreet side cache.
    rotated_box(-592,-1528,128,128,0,128,12,letters=True)
    rotated_box(-448,-1584,96,96,0,96,-15,letters=True)
    rotated_box(-592,-1528,96,96,128,224,-8,letters=True)
    rotated_box(376,-1376,128,128,0,128,-18,letters=True)
    rotated_box(-128,-1080,112,112,0,112,10,letters=True)
    shaped_mound(-824,-1568,192,256,64)
    shaped_mound(832,-1784,208,224,48)
    shaped_mound(-600,-1936,304,128,72,lean=(32,0))
    shaped_mound(544,-1920,288,128,56,lean=(-32,0))
    tipped_bucket(784,-1616,144,208)
    garden_spade(-704,-1360)
    tower(-672,-944)
    tower(752,-944)
    # Low retaining walls break incoming fire without creating jump gates.
    # Broken crescent breastwork: diagonal ends allow two ways around it.
    WORLD.append(column([(-480,-1008),(-224,-1056),(-96,-992),(-160,-944),(-464,-944)],0,88))
    WORLD.append(column([(-112,-992),(112,-1008),(192,-960),(176,-928),(-64,-944)],0,64))
    secret_chamber("cache_one",-1008,-784,-1216,-992,(-960,-832),[
        ("weapon_supershotgun",-928,-1088),("item_armor_combat",-856,-1088)])
    pickup("weapon_machinegun",80,-1152)
    pickup("ammo_bullets",80,-1248)
    pickup("item_health",192,-1104)
    pickup("ammo_shells",624,-1200)
    pickup("item_health",-544,-1360)
    for kind,x,y,sk in [("light",-336,-1520,0),("light",560,-1472,0),
                         ("shot",96,-1360,0),("light",-512,-1200,0),
                         ("heavy",272,-992,0),("shot",496,-912,0),
                         ("heavy",-384,-912,256),("heavy",880,-1296,768)]:
        soldier(kind,x,y,skill=sk)
    # Bailey courtyard with two looped side objectives.
    trigger((-224,-384,0),(0,-304,96),"bailey_brief")
    entity("trigger_relay",targetname="bailey_brief",
           message="CASTLE BAILEY\\nARMORY left. RADIO up the right stairs.\\nTouch both colored control panels.")
    # Armory has a front door and side door, making a useful combat loop.
    wb((-960,0,0),(-928,864,176))
    wb((-544,0,0),(-512,352,176))
    wb((-544,544,0),(-512,864,176))
    wb((-544,352,128),(-512,544,176))
    wb((-960,0,0),(-816,32,176))
    wb((-656,0,0),(-512,32,176))
    wb((-816,0,128),(-656,32,176))
    wb((-960,832,0),(-512,864,176))
    wb((-960,0,176),(-512,864,208),"wood")
    panel(-736,-6,208,"sign_armory")
    spool(-880,-112,80,40)
    spool(-800,-176,56,32)
    wb((-864,192,0),(-704,288,64),"wood",detail=True)
    wb((-912,576,0),(-848,736,48),"wood",detail=True)
    # Touch console, single use, inset into the rear wall.
    console(-736,800,0,"armory","armory_captured")
    entity("target_goal",targetname="armory_captured",target="objective_counter",
           message="ARMORY SECURED\\nControl panel activated.")
    for x,y in [(-736,112),(-608,704)]:
        pickup("ammo_bullets",x,y)
    pickup("weapon_grenadelauncher",-864,448)
    pickup("ammo_gl_rounds",-800,448)
    pickup("ammo_gl_rounds",-864,512)
    pickup("item_armor_combat",-608,608)
    pickup("item_health_large",-864,736,80)
    pickup("ammo_shells",-608,112)
    for y in (128,448):
        ceiling_lamp(-736,y,168,450)
    # Radio terrace and comfortable 16-unit stair risers.
    wb((512,256,0),(960,864,128))
    for i in range(8):
        wb((256+i*32,320,0),(288+i*32,480,(i+1)*16),"sand",detail=True)
    wb((512,832,128),(960,864,288))
    wb((928,544,128),(960,864,288))
    wb((512,544,128),(544,864,288))
    wb((512,544,288),(960,864,320),"wood")
    wb((512,256,128),(960,280,176),detail=True)
    # Stone stair stringers follow the run, with clear 160-unit-wide treads.
    for i in range(8):
        for sy in (304,480):
            wb((256+i*32,sy,0),(288+i*32,sy+16,(i+1)*16+16),detail=True)
    wb((928,280,128),(960,544,176),detail=True)
    for y,Y in ((280,320),(480,544)):
        wb((512,y,128),(544,Y,176),detail=True)
    # Sign hangs above the player's head, with 96 units of clearance below it.
    panel(736,538,224,"sign_radio",width=256,height=128)
    console(800,800,128,"radio","radio_captured")
    entity("target_goal",targetname="radio_captured",target="objective_counter",
           message="RADIO DISABLED\\nControl panel activated.")
    wb((688,864,0),(784,960,384))
    wb((724,888,384),(740,904,480),"trim",detail=True)
    wb((656,888,432),(808,904,448),"iron",detail=True)
    ceiling_lamp(672,656,280,400,"0.65 0.80 1")
    pickup("weapon_chaingun",608,688,160)
    pickup("ammo_bullets",608,752,160)
    pickup("ammo_bullets",864,608,160)
    pickup("item_health_large",864,688,160)
    # A central low dais and a flag landmark split the two approaches.
    prism(-32,352,176,0,16,"sand")
    prism(-32,352,128,16,32,"sand")
    secret_chamber("cache_two",-208,96,640,896,(-128,-16),[
        ("weapon_railgun",-112,800),("ammo_slugs",-32,800),("ammo_slugs",-112,736)])
    crenels_x(-208,96,640,160,depth=32,step=112)
    crenels_x(-208,96,864,160,depth=32,step=112)
    wb((-64,760,160),(-32,792,184),"sand_wall",detail=True)
    wb((-56,768,184),(-40,784,400),"wood",detail=True)
    wb((-40,770,304),(104,778,384),"plastic_red",detail=True)
    rotated_box(-288,568,112,112,0,112,-12,letters=True)
    rotated_box(192,128,96,96,0,96,16,letters=True)
    rotated_box(200,128,64,64,96,160,-10,letters=True)
    WORLD.append(column([(-448,928),(-272,904),(-80,928),(-96,984),(-432,992)],0,80))
    shaped_mound(96,960,160,64,48)
    shaped_mound(-896,-304,160,160,40)
    shaped_mound(872,-160,144,256,72)
    tower(-784,1040,radius=120,height=240)
    tower(784,1040,radius=120,height=240)
    panel(496,1146,176,"sign_boss")
    pickup("item_health",-352,160)
    pickup("item_health",320,672)
    pickup("ammo_bullets",352,864)
    pickup("ammo_shells",-352,-64)
    pickup("item_armor_shard",-96,352,64)
    pickup("item_armor_shard",-32,352,64)
    pickup("item_armor_shard",32,352,64)
    for kind,x,y,z,angle,sk in [
        ("light",-352,-112,24,270,0),("shot",224,-128,24,225,0),
        ("heavy",-672,352,24,270,0),("shot",-608,720,24,180,0),
        ("light",-864,112,24,270,0),("heavy",-800,656,24,270,256),
        ("shot",192,352,24,180,0),("heavy",672,448,152,180,0),
        ("light",864,352,152,225,0),("heavy",608,736,152,270,0),
        ("shot",880,784,152,270,256),("heavy",224,864,24,270,0),
        ("light",-448,768,24,270,0),("heavy",496,1056,24,270,0),
        ("shot",-128,1056,24,270,256),("heavy",352,576,24,270,768)]:
        soldier(kind,x,y,z,angle,sk)
    entity("trigger_counter",targetname="objective_counter",count=2,spawnflags=1,target="keep_open")
    door("keep_open",(-224,1488,0),(0,1512,160))
    entity("trigger_relay",targetname="keep_open",target="keep_help",
           message="KEEP ACCESS OPEN\\nResupply beyond the gate.\\nThe gunship is waiting.")
    entity("target_help",targetname="keep_help",spawnflags=1,
           message="Both controls secured. Enter the keep, collect rockets, and destroy the helicopter.")
    # Final staging nook. Its low roof keeps the helicopter out of the return route.
    wb((-480,1536,0),(-448,1792,176))
    wb((32,1536,0),(64,1792,176))
    wb((-480,1536,176),(64,1792,208),"wood")
    wb((-480,1760,0),(-320,1792,176))
    wb((-32,1760,0),(64,1792,176))
    panel(-176,1794,224,"sign_boss")
    light(-208,1664,144,400)
    pickup("weapon_rocketlauncher",-352,1648)
    pickup("ammo_rockets",-352,1728)
    pickup("ammo_rockets",-272,1648)
    pickup("ammo_rockets",-272,1728)
    pickup("item_armor_body",-64,1648)
    pickup("item_health_large",-64,1728)
    # Shelters are outside the helicopter's preferred central strafe lanes.
    for x,y,mirror in [(-928,1904,False),(576,1904,True),
                        (-928,2512,False),(576,2512,True)]:
        if (x,y)==(576,1904):
            tipped_bucket(576,2040,184,304,"plastic_green_smooth",yaw=-90)
            light(720,2040,112,260)
        elif (x,y)==(-928,2512):
            tipped_bucket(-576,2648,184,304,"plastic_blue_smooth",yaw=90)
            light(-720,2648,112,260)
        else:
            supply_shelter(x,y,mirror)
        pickup("ammo_rockets",x+96,y+96,36)
        pickup("ammo_rockets",x+192,y+96,36)
        pickup("ammo_bullets",x+96,y+192,36)
        pickup("item_health_large",x+192,y+192,36)
    # Alternating cover presents corners to the gunship and leaves a continuous
    # central retreat lane. Low sand tails soften the cover into the ground.
    WORLD.append(column([(-304,2176),(-144,2224),(-168,2312),(-320,2288)],0,80))
    WORLD.append(column([(160,2424),(280,2392),(320,2504),(176,2552)],0,80))
    rotated_box(-304,2808,144,80,0,96,-18,"wood")
    rotated_box(304,2048,144,80,0,96,20,"wood")
    spool(456,2136,88,48)
    pickup("weapon_machinegun",832,2304)
    pickup("ammo_bullets",832,2384)
    pickup("ammo_rockets",-832,2304)
    pickup("ammo_rockets",-832,2384)
    # 65 loose rockets, plus the launcher pickup; additional hitscan caches.
    # Guard the approach, with only optional guards removed on easier settings.
    for kind,x,y,sk in [("heavy",320,1856,0),("shot",-416,2064,0),
                         ("heavy",448,2720,0),("light",-416,2720,0),
                         ("heavy",416,2240,256),("heavy",-448,2416,768)]:
        soldier(kind,x,y,skill=sk)
    trigger((-320,1792,0),(-32,1840,128),"boss_wake")
    entity("monster_boss2",(0,2528,176),angle=270,spawnflags=2,
           targetname="boss_wake",deathtarget="boss_down")
    entity("trigger_relay",targetname="boss_wake",target="boss_help",
           message="HOSTILE GUNSHIP\\nUse the side bunkers and tipped buckets.\\nRockets and supplies under cover.")
    entity("target_help",targetname="boss_help",spawnflags=1,
           message="Destroy the helicopter. Side bunkers and tipped buckets provide cover and shared ammunition.")
    entity("target_goal",targetname="boss_down",target="victory_delay")
    entity("trigger_relay",targetname="victory_delay",delay=2,target="extract_open")
    entity("trigger_relay",targetname="extract_open",target="victory_help",
           message="GUNSHIP DOWN\\nRear gate released.\\nExit the sandbox and rally at the landing pad.")
    entity("target_help",targetname="victory_help",spawnflags=1,
           message="Gunship destroyed. Leave through the rear gate and reach the landing pad outside the sandbox.")
    # Permanently opened extraction gate. The repeatable mission has a real intermission.
    wb((-288,2880,0),(-96,2912,160))
    wb((96,2880,0),(288,2912,160))
    wb((-288,2880,0),(-256,3072,160))
    wb((256,2880,0),(288,3072,160))
    wb((-288,2880,160),(288,3072,192),"wood")
    panel(0,2874,208,"sign_exit")
    gate_frame(-96,96,2872,2912)
    door("extract_open",(-96,2880,0),(96,2904,160))
    # The gate leads through the broken rear board into a real outdoor rally area.
    shaped_mound(0,3152,288,320,8,lean=(0,-48),clip_y=3136)
    rotated_box(-328,3256,240,40,0,20,-20,"wood_end")
    rotated_box(288,3208,144,32,0,24,32,"wood")
    shaped_mound(-440,3520,208,176,56,"soil")
    shaped_mound(448,3760,208,160,64,"grass")
    wb((-128,3568,0),(128,3824,4),"trim",detail=True,
       face_overrides={5:dict(texture="helipad",shift=(128,3824),scale=1)})
    # Two low lamps make the destination visible through the board split.
    for x in (-184,184):
        wb((x-12,3684,0),(x+12,3708,24),"iron",detail=True)
        wb((x-8,3688,24),(x+8,3704,32),"lamp",detail=True)
        light(x,3696,64,180,".60 1 .68")
    trigger((-112,3664,4),(112,3792,112),"mission_exit")
    # Unit boundary keeps the actual intermission visible in SP and co-op.
    entity("target_changelevel",targetname="mission_exit",map="*pp_sandkeep")
    entity("info_player_intermission",(384,3408,256),angles="20 144 0")
    light(0,2976,128,320)
    # Sunlit outdoor areas, plus local warm fills; all lighting is baked.
    for y in (-1600,-1168,-128,384,864,2000,2448,2832):
        for x in (-560,0,560):
            light(x,y,448,500,"1 0.93 0.79")
    world = ('// Operation Sandkeep, original SP/co-op mission.\n'
             '// Generated by tools/maps/generate_sandkeep.py; directly editable.\n'
             '{\n"classname" "worldspawn"\n"message" "Operation Sandkeep"\n'
             '"sky" "sandkeep"\n"sounds" "0"\n')
    out = ROOT / "maps/source/pp_sandkeep.map"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(world + "".join(WORLD) + "}\n" + "".join(ENTITIES))
    # Independent BSP verifier consumes intended player routes, not brush internals.
    routes = {"routes":[
        {"name":"insertion_to_bailey","points":[[0,-2688,24],[0,-2480,24],[0,-2384,28],
           [0,-2208,28],[0,-2112,28],[0,-2048,24],[0,-1920,24],[0,-1664,24],[32,-1536,24],
           [128,-1456,24],[128,-1328,24],[224,-1200,24],[320,-1088,24],[496,-1088,24],
           [496,-672,24],[496,-528,24],[-112,-528,24],[-112,-320,24]],"opened_doors":[]},
        {"name":"bailey_to_armory","points":[[-112,-320,24],[-736,-144,24],[-736,112,24],
           [-608,112,24],[-608,448,24],[-736,448,24],[-736,760,24]],"opened_doors":[]},
        {"name":"bailey_to_radio","points":[[-112,-320,24],[64,-128,24],[64,240,24],
           [224,400,24],[256,400,40],[288,400,56],[320,400,72],[352,400,88],
           [384,400,104],[416,400,120],[448,400,136],[480,400,152],
           [608,400,152],[800,480,152],[800,760,152]],"opened_doors":[]},
        {"name":"radio_to_keep","points":[[800,760,152],[800,480,152],[608,400,152],
           [512,400,152],[480,400,152],[448,400,136],[416,400,120],[384,400,104],
           [352,400,88],[320,400,72],[288,400,56],[256,400,40],[224,400,24],
           [208,400,24],[208,544,24],[352,736,24],[496,928,24],[496,1248,24],[496,1392,24],[-112,1392,24],
           [-112,1664,24],[-176,1856,24]],"opened_doors":["keep_open"]},
        {"name":"arena_to_extraction","points":[[-176,1856,24],[0,2000,24],[0,2320,24],
           [0,2416,24],[0,2800,24],[0,2976,24],[0,3136,28],[0,3328,28],
           [0,3440,24],[0,3568,28],[0,3696,28]],
         "opened_doors":["keep_open","extract_open"]},
    ], "outdoor_probes":[
        {"name":"entry_breach","point":[0,-2208,64]},
        {"name":"exterior_start","point":[0,-2688,64]},
        {"name":"extraction","point":[0,3696,64]},
    ], "secret_probes":[
        {"name":"cache_one","outside":[-896,-1256,24],"inside":[-896,-1088,24],
         "rewards":[[-928,-1088,32],[-856,-1088,32]]},
        {"name":"cache_two","outside":[-72,600,24],"inside":[-72,784,24],
         "rewards":[[-112,800,32],[-32,800,32],[-112,736,32]]},
    ]}
    routes["routes"].extend([
        {"name":"east_bucket_resupply","points":[[432,2040,24],[640,2040,24],[768,2040,24]],
         "opened_doors":["keep_open"]},
        {"name":"west_bucket_resupply","points":[[-448,2648,24],[-672,2648,24],[-800,2648,24]],
         "opened_doors":["keep_open"]},
        {"name":"buried_cache_after_breach","points":[[-896,-1256,24],[-896,-1120,24],[-896,-1088,24]],
         "opened_doors":[],"destroyed_secrets":["cache_one"]},
        {"name":"flag_cache_after_breach","points":[[-72,600,24],[-72,704,24],[-72,800,24]],
         "opened_doors":[],"destroyed_secrets":["cache_two"]},
    ])
    routes_path = ROOT / "build/maps/pp_sandkeep/route_waypoints.json"
    routes_path.parent.mkdir(parents=True,exist_ok=True)
    routes_path.write_text(json.dumps(routes,indent=2)+"\n")
    print(f"{out}: {len(WORLD)} world brushes, {len(ENTITIES)} entities")


if __name__ == "__main__":
    main()
