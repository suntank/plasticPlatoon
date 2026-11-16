#!/usr/bin/env python3
"""Flight-oriented versions of the authored ammo, using the existing origins.

Quake's flying rocket points along +X with its exhaust at the entity origin.
The spinning grenade and launcher/mortar round stay centered on that origin.
An armed hand grenade retains its body and fuse after the pin/lever release.
"""
import numpy as np
from ammo_geometry import build_ammo

KINDS = ('rocket', 'gl_round', 'hand_grenade')
AMMO_KINDS = {'rocket':'rockets', 'gl_round':'gl_ammo', 'hand_grenade':'grenades'}
FLIGHT_ROTATION = np.array([[0.,0.,-1.], [0.,1.,0.], [1.,0.,0.]])


def placement(kind):
    if kind == 'rocket':
        return FLIGHT_ROTATION.copy(), np.array([11.8,0.,0.])
    if kind == 'gl_round':
        return FLIGHT_ROTATION @ np.diag([1.,1.14,1.14]), np.array([7.,0.,0.])
    if kind == 'hand_grenade':
        return FLIGHT_ROTATION*.84, np.array([5.082,0.,0.])
    raise ValueError('Unknown projectile: '+kind)


def component_mesh(mesh, selected=None):
    faces,uvs,materials,parts = [],[],[],[]
    for part in mesh['parts']:
        if selected is not None and part['name'] not in selected:
            continue
        a = part['first_triangle']; b = a+part['triangle_count']
        parts.append(dict(part,first_triangle=len(faces)))
        faces.extend(mesh['faces'][a:b])
        uvs.extend(mesh['uvs'][a:b])
        materials.extend(mesh['materials'][a:b])
    used = sorted({vertex for face in faces for vertex in face})
    indices = {old:new for new,old in enumerate(used)}
    return dict(vertices=[mesh['vertices'][i] for i in used],
                normals=[mesh['normals'][i] for i in used],
                faces=[[indices[i] for i in face] for face in faces],
                uvs=uvs,materials=materials,parts=parts)


def build_projectile(kind):
    if kind not in KINDS:
        raise ValueError('Unknown projectile: '+kind)
    ammo = build_ammo(AMMO_KINDS[kind])
    selected = {'grenade_body','fuse'} if kind=='hand_grenade' else None
    mesh = component_mesh(ammo,selected)
    matrix,offset = placement(kind)
    mesh['vertices'] = (np.asarray(mesh['vertices']) @ matrix+offset).tolist()
    normals = np.asarray(mesh['normals']) @ np.linalg.inv(matrix).T
    mesh['normals'] = (normals/np.linalg.norm(normals,axis=1)[:,None]).tolist()
    mesh['kind'] = kind
    mesh['detail'] = 'projectile'
    mesh['anchors'] = {'origin':[0.,0.,0.], 'forward':[1.,0.,0.]}
    if kind == 'rocket':
        mesh['anchors'].update(exhaust=[0.,0.,0.],nose=[24.1,0.,0.])
    return mesh
