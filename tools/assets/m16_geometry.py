#!/usr/bin/env python3
"""Original, editable primitive geometry for the Plastic Platoon M16.

All dimensions are artistic model units, not manufacturing dimensions. X runs
from the butt at 0 to the muzzle at 100, Y is lateral, and Z=0 is the bore.
The world and view meshes share a silhouette. Only the view mesh includes
posed hands, forearms, and the functional rear sight used by model-based ADS.
There is no imported or decimated mesh in this file.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

MATERIALS = ('plastic', 'dark', 'edge', 'grip', 'handguard', 'magazine',
             'receiver', 'bore', 'hand', 'cuff', 'fingers', 'palm')


def _area(points):
    return sum(a[0] * b[1] - b[0] * a[1]
               for a, b in zip(points, points[1:] + points[:1])) / 2


def _triangulate(points):
    """Ear-clip a simple CCW 2D polygon, preserving its original vertices."""
    p = np.asarray(points, dtype=float)
    remaining = list(range(len(p)))
    result = []

    def cross(a, b, c):
        u, v = b - a, c - a
        return u[0] * v[1] - u[1] * v[0]

    while len(remaining) > 3:
        for j, b in enumerate(remaining):
            a, c = remaining[j - 1], remaining[(j + 1) % len(remaining)]
            if cross(p[a], p[b], p[c]) <= 1e-9:
                continue
            inside = any(all(cross(p[i], p[k], p[t]) >= -1e-9
                             for i, k in ((a, b), (b, c), (c, a)))
                         for t in remaining if t not in (a, b, c))
            if not inside:
                result.append((a, b, c))
                remaining.pop(j)
                break
        else:
            raise ValueError('Non-simple primitive profile')
    result.append(tuple(remaining))
    return result


class Mesh:
    def __init__(self):
        self.vertices = []
        self.faces = []
        self.uvs = []
        self.materials = []
        self.parts = []
        self._indices = {}

    def part(self, name):
        if self.parts:
            self.parts[-1]['triangle_count'] = len(self.faces) - self.parts[-1]['first_triangle']
        self.parts.append({'name': name, 'first_triangle': len(self.faces),
                           'triangle_count': 0})
        # Parts stay separate so their normals never smear across an overlap.
        self._indices = {}

    def vertex(self, point, group='surface'):
        key = (group,) + tuple(round(float(x), 7) for x in point)
        if key not in self._indices:
            self._indices[key] = len(self.vertices)
            self.vertices.append(list(map(float, point)))
        return self._indices[key]

    def poly(self, points, material='plastic', normal=None, uv=None, group='surface'):
        p = np.asarray(points, dtype=float)
        if normal is not None and np.dot(np.cross(p[1]-p[0], p[2]-p[0]), normal) < 0:
            p = p[::-1]
            uv = None if uv is None else uv[::-1]
        indices = [self.vertex(point, group) for point in p]
        if uv is None:
            if len(p) == 4:
                uv = [(0, 1), (1, 1), (1, 0), (0, 0)]
            else:
                uv = [(.5+.48*math.cos(i*math.tau/len(p)),
                       .5+.48*math.sin(i*math.tau/len(p))) for i in range(len(p))]
        for j in range(1, len(p)-1):
            corners = (0, j, j+1)
            self.faces.append([indices[k] for k in corners])
            self.uvs.append([list(uv[k]) for k in corners])
            self.materials.append(material)

    def profile(self, name, outline, half_width, material='plastic', edge='edge',
                y=0., sharp=True):
        """A capped polygon extruded across Y; ribs and pins remain in paint."""
        self.part(name)
        outline = [list(p) for p in outline]
        if _area(outline) < 0:
            outline.reverse()
        p = np.asarray(outline)
        low, span = p.min(axis=0), np.maximum(np.ptp(p, axis=0), 1e-6)
        uv = np.column_stack(((p[:, 0]-low[0])/span[0], 1-(p[:, 1]-low[1])/span[1]))
        for side in (-1, 1):
            for ids in _triangulate(outline):
                self.poly([(p[i,0],y+side*half_width,p[i,1]) for i in ids],
                          material, [0,side,0], uv[list(ids)].tolist(),
                          f'cap{side}' if sharp else 'surface')
        for i in range(len(p)):
            j = (i+1) % len(p)
            a, b = p[i], p[j]
            self.poly([(a[0],y-half_width,a[1]), (b[0],y-half_width,b[1]),
                       (b[0],y+half_width,b[1]), (a[0],y+half_width,a[1])],
                      edge, [b[1]-a[1],0,a[0]-b[0]])

    def ring_profile(self, name, outer, inner, half_width, material='plastic', y=0.):
        """A truly open extruded ring, used for handle, guard and front sight."""
        self.part(name)
        outer, inner = list(outer), list(inner)
        if _area(outer) < 0:
            outer.reverse(); inner.reverse()
        if len(outer) != len(inner):
            raise ValueError('Ring needs corresponding outer/inner corners')
        for i in range(len(outer)):
            j = (i+1) % len(outer)
            a, b, c, d = outer[i], outer[j], inner[j], inner[i]
            for side in (-1, 1):
                self.poly([(x,y+side*half_width,z) for x,z in (a,b,c,d)],
                          material,[0,side,0],group=f'side{side}')
            self.poly([(a[0],y-half_width,a[1]),(b[0],y-half_width,b[1]),
                       (b[0],y+half_width,b[1]),(a[0],y+half_width,a[1])],
                      'edge',[b[1]-a[1],0,a[0]-b[0]],group='outer')
            self.poly([(d[0],y-half_width,d[1]),(c[0],y-half_width,c[1]),
                       (c[0],y+half_width,c[1]),(d[0],y+half_width,d[1])],
                      'dark',[d[1]-c[1],0,c[0]-d[0]],group='inner')

    def box(self, name, low, high, material='plastic', top=None):
        self.part(name)
        x,y,z = low; X,Y,Z = high
        specs = [([(x,y,z),(X,y,z),(X,Y,z),(x,Y,z)],[0,0,-1],material),
                 ([(x,y,Z),(X,y,Z),(X,Y,Z),(x,Y,Z)],[0,0,1],top or material),
                 ([(x,y,z),(X,y,z),(X,y,Z),(x,y,Z)],[0,-1,0],material),
                 ([(x,Y,z),(X,Y,z),(X,Y,Z),(x,Y,Z)],[0,1,0],material),
                 ([(x,y,z),(x,Y,z),(x,Y,Z),(x,y,Z)],[-1,0,0],material),
                 ([(X,y,z),(X,Y,z),(X,Y,Z),(X,y,Z)],[1,0,0],material)]
        for n,(p,normal,mat) in enumerate(specs):
            self.poly(p,mat,normal,group=f'face{n}')

    def tube(self, name, rings, sides=8, material='plastic', caps=(False,False),
             end_material=None, phase=math.pi/8):
        """X-axis polygonal tapered tube: rings are (x,y,z,ry,rz)."""
        self.part(name)
        loops=[]
        for x,y,z,ry,rz in rings:
            loops.append(np.array([(x,y+ry*math.cos(phase+i*math.tau/sides),
                                    z+rz*math.sin(phase+i*math.tau/sides)) for i in range(sides)]))
        for band,(a,b) in enumerate(zip(loops,loops[1:])):
            for i in range(sides):
                j=(i+1)%sides
                normal=np.array([0.,(a[i,1]+a[j,1])/2-rings[band][1],
                                 (a[i,2]+a[j,2])/2-rings[band][2]])
                self.poly([a[i],a[j],b[j],b[i]],material,normal,
                          [(band/(len(loops)-1),i/sides),
                           (band/(len(loops)-1),(i+1)/sides),
                           ((band+1)/(len(loops)-1),(i+1)/sides),
                           ((band+1)/(len(loops)-1),i/sides)])
        for i,on in enumerate(caps):
            if on:
                k=0 if i==0 else -1
                cap_material = (end_material or material) if i else material
                self.poly(loops[k],cap_material,[-1 if i==0 else 1,0,0],group=f'cap{i}')

    def limb(self,name,start,end,start_radius,end_radius,material='hand',sides=6,caps=(True,True)):
        """Small tapered polygonal limb in any direction."""
        self.part(name)
        a,b=np.array(start,dtype=float),np.array(end,dtype=float)
        axis=(b-a)/np.linalg.norm(b-a)
        helper=np.array([0.,0.,1.]) if abs(axis[2])<.9 else np.array([0.,1.,0.])
        u=np.cross(axis,helper);u/=np.linalg.norm(u)
        v=np.cross(axis,u)
        radial=np.array([u*math.cos(i*math.tau/sides+math.pi/sides)+
                         v*math.sin(i*math.tau/sides+math.pi/sides) for i in range(sides)])
        loops=[a+radial*start_radius,b+radial*end_radius]
        for i in range(sides):
            j=(i+1)%sides
            self.poly([loops[0][i],loops[0][j],loops[1][j],loops[1][i]],material,
                      radial[i]+radial[j],[(0,1),(1,1),(1,0),(0,0)])
        if caps[0]: self.poly(loops[0],material,-axis,group='cap0')
        if caps[1]: self.poly(loops[1],material,axis,group='cap1')

    def loft(self, name, loops, material='hand', uv_axes=None):
        """Closed, softly faceted volume through corresponding section rings."""
        self.part(name)
        loops = np.asarray(loops, dtype=float)
        centers = loops.mean(axis=1)
        sides = loops.shape[1]
        low, span = loops.min(axis=(0,1)), np.maximum(np.ptp(loops,axis=(0,1)),1e-6)
        for band, (a, b) in enumerate(zip(loops, loops[1:])):
            for i in range(sides):
                j = (i + 1) % sides
                outward = a[i]+a[j]+b[i]+b[j]-2*(centers[band]+centers[band+1])
                points = np.array([a[i],a[j],b[j],b[i]])
                uv = ([(band/(len(loops)-1),i/sides),
                       (band/(len(loops)-1),(i+1)/sides),
                       ((band+1)/(len(loops)-1),(i+1)/sides),
                       ((band+1)/(len(loops)-1),i/sides)] if uv_axes is None else
                      [((p[uv_axes[0]]-low[uv_axes[0]])/span[uv_axes[0]],
                        1-(p[uv_axes[1]]-low[uv_axes[1]])/span[uv_axes[1]]) for p in points])
                self.poly(points, material, outward, uv)
        self.poly(loops[0], material, centers[0]-centers[1])
        self.poly(loops[-1], material, centers[-1]-centers[-2])

    def finger(self, name, joints, radii, up=(0,0,1)):
        """One continuous bent digit, tapered at the tip and capped at both ends.

        Used for the mitten's opposing thumb. Fingers stay molded together.
        """
        points = np.asarray(joints, dtype=float)
        loops = []
        for i, (point, radius) in enumerate(zip(points, radii)):
            tangent = points[min(i+1,len(points)-1)]-points[max(0,i-1)]
            tangent /= np.linalg.norm(tangent)
            u = np.cross(tangent, up); u /= np.linalg.norm(u)
            v = np.cross(tangent, u)
            loops.append([point+radius*(u*math.cos(j*math.tau/6)+
                                        v*math.sin(j*math.tau/6)) for j in range(6)])
        self.loft(name, loops)

    def finish(self, detail):
        self.parts[-1]['triangle_count']=len(self.faces)-self.parts[-1]['first_triangle']
        p=np.asarray(self.vertices);f=np.asarray(self.faces)
        normals=np.zeros_like(p)
        area=np.cross(p[f[:,1]]-p[f[:,0]],p[f[:,2]]-p[f[:,0]])
        for j in range(3): np.add.at(normals,f[:,j],area)
        lengths=np.linalg.norm(normals,axis=1)
        if np.any(lengths<1e-8) or np.any(np.linalg.norm(area,axis=1)<1e-8):
            raise ValueError('Degenerate primitive geometry')
        normals/=lengths[:,None]
        return {'detail':detail,'vertices':self.vertices,'faces':self.faces,
                'uvs':self.uvs,'materials':self.materials,'normals':normals.tolist(),
                'parts':self.parts,'rifle_bounds':[[0,-3.6,-18.5],[100,3.6,9.8]],
                'anchors':{'muzzle':[100,0,0],'rear_sight':[32,0,8.6],
                           'front_sight':[82,0,8.6],'grip':[34,0,-8],
                           'support':[62,0,-2]}}


def build_m16(detail='world'):
    if detail not in ('world','view'):
        raise ValueError('detail must be world or view')
    close=detail=='view'
    m=Mesh()
    # Big uninterrupted planes replace the decimator's many noisy facets.
    m.profile('stock',[(0,-9.2),(0,1.2),(5,1.4),(27,.6),(30,-1.2),(27,-2.7)],
              2.7,'plastic','edge')
    m.profile('receiver',[(28,-4.5),(28,2.0),(31,3.0),(49,2.5),(53,1.3),
                          (53,-4.0),(43,-5.2)],2.35,'receiver','plastic')
    m.profile('pistol_grip',[(29,-15.1),(25.8,-13.8),(31,-4.3),(36,-4.7),
                            (34,-7.2),(32.8,-15.3)],1.85,'grip','edge')
    # Six-sided magazine profile retains the familiar forward curve.
    m.profile('magazine',[(42.2,-4.2),(49,-4),(49.5,-10.6),(52,-17.0),
                          (45.8,-18.5),(43.3,-11.4)],1.9,'magazine','edge')
    m.ring_profile('trigger_guard',[(33.9,-4.2),(43.3,-4.2),(43,-8.5),(33.3,-8.2)],
                   [(35.4,-5.3),(42,-5.3),(41.8,-7.2),(34.7,-7.1)],.72)
    # The handle's real hole remains visible from oblique pickup/held views.
    m.ring_profile('carry_handle',[(29.6,2.1),(49.7,2.1),(48.5,6.4),(31.1,7.2)],
                   [(32,3.2),(47.2,3.2),(46.7,5.0),(32.7,5.7)],1.35)
    # Eight sides read rounded at game resolution; one taper carries the shape.
    handguard=[(52,0,0,3.6,3.6),(78.8,0,0,2.45,2.55)]
    if close: handguard.insert(1,(55,0,0,3.6,3.6))
    # The receiver does not cover the wider handguard's whole rear opening.
    m.tube('handguard',handguard,8,'handguard',caps=(True,True),phase=math.pi/8)
    m.tube('barrel',[(78,0,0,.92,.92),(97,0,0,.92,.92)],6,'dark')
    m.tube('flash_hider',[(96.5,0,0,1.35,1.35),(100,0,0,1.35,1.35)],
           8 if close else 6,'edge',caps=(True,True),end_material='bore')
    m.ring_profile('front_sight_frame',[(78.6,-.8),(85,-.8),(82,6.6)],
                   [(80.2,.5),(83.5,.5),(82,4.8)],.66)
    m.box('front_sight_post',(81.6,-.42,6.2),(82.4,.42,8.6),'dark')
    if close:
        # Sight ears are separate so the central line is actually unobstructed.
        for side in (-1,1):
            y=side*1.2
            m.profile(f'front_sight_ear_{side}',[(81.2,6.2),(82.7,6.2),(82.4,9.4),(81.5,9.0)],
                      .32,'plastic','edge',y=y)
        # A U-notch instead of a solid slab keeps ADS clear without an alpha card.
        m.box('rear_sight_base',(30.9,-1.3,6.6),(33.2,1.3,7.4),'dark','edge')
        for side in (-1,1):
            m.profile(f'rear_sight_wing_{side}',
                      [(30.9,7.3),(33.2,7.3),(33.2,9.0),(31.5,9.25),(30.9,9.0)],
                      .29,'plastic','edge',y=side*1.01)
        # Small clean shapes only where they help the first-person read.
        m.profile('butt_plate',[(0,-9.2),(0,1.2),(1.2,1.3),(1.2,-8.8)],2.85,'dark','edge')
        m.profile('ejection_cover',[(35,-.7),(47,-.7),(47,1.1),(35,1.5)],.25,
                  'receiver','edge',y=-2.5)
        m.box('charging_latch',(27.5,-3,2.0),(31.2,3,2.9),'dark','edge')
        add_hands(m)
    else:
        # A single rear block is sufficient for a few on-screen pixels.
        m.box('rear_sight',(30.9,-1.65,6.6),(33.2,1.65,8.7),'edge')
    return m.finish(detail)


def add_right_hand(m):
    """Shared molded mitten: full grip mass, curled finger bank and opposing thumb."""
    # Right forearm approaches the pistol grip from the lower-right of the eye.
    m.limb('arm_right',(8,-10,-28),(28.4,-4.5,-10.7),3.8,2.7,'hand',6)
    m.limb('cuff_right',(25.5,-5.3,-13.4),(28.8,-4.4,-10.5),2.95,2.85,'cuff',6)
    m.limb('hand_right_wrist',(28.2,-4.5,-10.7),(29.6,-2.9,-9.6),2.45,2.35,'hand',6)
    # A rounded hand mass encloses the grip and backstrap. The old thin
    # extrusion lay mostly behind the gun and read as another grip panel.
    # Narrow the heel into the wrist; broaden the upper palm and knuckles.
    sections = [(28.8,-.3,-13.6,2.2,1.9),
                (29.2,-.3,-12.1,3.5,3.15),
                (31.0,-.3,-8.8,4.0,3.5),
                (32.0,-.2,-6.4,3.4,3.0),
                (31.8,-.1,-5.7,2.4,2.2)]
    m.loft('hand_right_palm',
           [[(x+rx*math.cos(i*math.tau/8),y+ry*math.sin(i*math.tau/8),z)
             for i in range(8)] for x,y,z,rx,ry in sections],
           'fingers',uv_axes=(1,2))
    # A broad thumb web rises out of the heel and wraps visibly along the
    # camera-facing side. The narrowed tip stays distinct above the fingers.
    m.finger('hand_right_thumb',
             [(28.4,.8,-7.6),(28.8,2.7,-5.6),(31.6,3.65,-5.2),(35.4,2.8,-5.8)],
             [1.8,1.65,1.3,.85])
    # Fused fingers curl around the front strap as a single molded volume.
    # Three shallow painted grooves suggest four fingers without separate
    # tubes, gaps or articulated knuckles on an army-man mitten.
    m.loft('hand_right_fingers',
           [[(x+rx*math.cos(i*math.tau/8),y,z+rz*math.sin(i*math.tau/8))
             for i in range(8)]
            for x,y,z,rx,rz in ((33.8,-2.3,-9.8,1.8,3.2),
                                (35.0,.0,-9.6,1.75,3.4),
                                (33.8,2.4,-9.8,1.7,3.25),
                                (32.8,3.1,-9.8,1.25,2.9))],
           'fingers',uv_axes=(0,2))


def add_hands(m):
    """Matching molded hands, posed around the grip and under the handguard."""
    add_right_hand(m)
    # Supporting forearm runs forward and up to the handguard's underside.
    m.limb('arm_left',(14,13,-26),(59.5,3.7,-5.3),3.55,2.5,'hand',6)
    m.limb('cuff_left',(55.1,4.6,-7.3),(59.8,3.6,-5.2),2.8,2.7,'cuff',6)
    # A shallow cup under the handguard. Rings run along X with the flatter
    # palm surface up; the wrist sinks into the rear of this volume.
    m.loft('hand_left_palm',
           [[(x,y+ry*math.cos(i*math.tau/8),z+rz*math.sin(i*math.tau/8))
             for i in range(8)]
            for x,y,z,ry,rz in ((57.8,2.1,-5.5,1.8,1.2),
                                (60.0,.6,-4.7,3.3,1.6),
                                (65.8,.0,-4.1,3.2,1.4),
                                (67.2,.0,-3.9,2.4,1.1))])
    # The supporting mitten is a cupped flipper with an opposing thumb.
    # Its fused fingers rise around the handguard's far side.
    m.loft('hand_left_fingers',
           [[(x,y+ry*math.cos(i*math.tau/6),z+rz*math.sin(i*math.tau/6))
             for i in range(6)]
            for x,y,z,ry,rz in ((58.8,-2.2,-3.1,1.2,1.65),
                                (60.5,-2.6,-2.4,1.7,2.6),
                                (65.2,-2.6,-2.1,1.7,2.7),
                                (67.2,-2.0,-2.6,.95,1.85))],
           'fingers',uv_axes=(2,0))
    m.finger('hand_left_thumb',
             [(59.3,2.7,-4.2),(60.5,3.9,-2.4),(63.1,3.2,-.4),(65.0,2.3,-.1)],
             [1.5,1.35,1.05,.75])


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    meshes={key:build_m16(key) for key in ('world','view')}
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(meshes,indent=2)+'\n')
    for key,mesh in meshes.items():
        hand=sum(p['triangle_count'] for p in mesh['parts']
                 if p['name'].startswith(('arm_','hand_','cuff_')))
        print(f'{key}: {len(mesh["faces"])} triangles, {len(mesh["vertices"])} vertices; '
              f'{hand} triangles in hands/forearms')
