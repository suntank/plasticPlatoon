#!/usr/bin/env python3
"""Dress the green player soldier for the Sandstorm briefing and bake his animation."""
from __future__ import annotations

import math
from pathlib import Path
import subprocess
import tempfile
import wave

import numpy as np
from build_m16 import encode_md2, vertex_normals
from m16_geometry import Mesh
from md2_assets import MD2, ROOT, normal_table

MODEL = 'models/briefing/general/tris.md2'
SKIN = 'models/briefing/general/skin.png'
VOICE = 'sound/briefing/sandstorm.wav'
SCRIPT = (
    'Platoon, gather round. This is Operation Sandstorm.',
    'We drop into the garden beds. Use the dirt banks for cover as you approach the sandbox.',
    'Reach the sandbox wall and breach it. From there, your target is Sandcastle One.',
    'Once you are through the castle, rally at the extraction point on the far side.',
    'First stop, the garden. Move out.',
)
SOLDIER = ROOT / 'baseq2/players/soldier'
REST = 113  # Standing body and open left hand from the start of the soldier's wave.
NEUTRAL, INDICATE, EMPHASIZE = -3, -2, -1  # Authored poses appended to the soldier frames.
# Reuse uniform 5x5 swatches in green.png for every molded addition.
SWATCHES = {'visor': (199, 87), 'band': (122, 147), 'crown': (99, 2),
            'piping': (80, 40), 'rank': (138, 45)}


def voice_track(path, replacement=None):
    with tempfile.TemporaryDirectory(prefix='sandstorm-voice-') as folder:
        if replacement:
            inputs = ['-i', str(replacement), '-c:a', 'pcm_s16le', '-ac', '1', '-ar', '22050']
        else:
            script = Path(folder) / 'briefing.txt'
            script.write_text('\n\n'.join(SCRIPT) + '\n', encoding='ascii')
            inputs = ['-f', 'lavfi', '-i', f'flite=textfile={script}:voice=kal16',
                      '-af', 'highpass=f=100,lowpass=f=5300,acompressor=threshold=0.1:ratio=2:makeup=1.8',
                      '-c:a', 'pcm_s16le', '-ac', '1', '-ar', '22050']
        subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                        '-y', *inputs, str(path)], check=True)
    with wave.open(str(path), 'rb') as clip:
        samples = np.frombuffer(clip.readframes(clip.getnframes()), dtype='<i2').astype(float)
        return samples, clip.getframerate()


def ring_part(mesh, name, rings, material):
    """Join capped elliptical rings for the peaked cap's band and crown."""
    mesh.part(name)
    angles = np.arange(12) * math.tau / 12
    loops = []
    for height, length, width, slope in rings:
        x = length * np.cos(angles)
        y = width * np.sin(angles)
        loops.append(np.column_stack((-.52+x, .22+y, height+slope*x)))
    mesh.poly(loops[0], material, (0, 0, -1), group='bottom')
    mesh.poly(loops[-1], material, (0, 0, 1), group='top')
    for bottom, top in zip(loops, loops[1:]):
        for i in range(len(angles)):
            j = (i+1) % len(angles)
            mesh.poly([bottom[i], bottom[j], top[j], top[i]], material)


def cap_mesh():
    mesh = Mesh()
    ring_part(mesh, 'cap band', ((23.47, 3.66, 3.35, .43), (24.92, 3.73, 3.46, .36)), 'band')
    ring_part(mesh, 'cap piping', ((24.67,3.77,3.50,.36), (25.17,3.91,3.58,.36)), 'piping')
    ring_part(mesh, 'peaked crown', ((25.03,3.89,3.56,.36), (27.13,4.71,4.10,.29),
                                   (27.83,4.41,3.88,.30), (28.08,4.02,3.64,.30)), 'crown')

    # A forward-only brim makes the cap distinct from the infantry helmet.
    outline = [(1.35,-2.95), (3.58,-3.20), (4.95,-2.55), (5.67,-1.43), (5.94,.22),
               (5.67,1.87), (4.95,2.99), (3.58,3.64), (1.35,3.39)]
    upper = [(x,y,25.82-.16*(x-1.35)) for x,y in outline]
    lower = [(x,y,z-.49) for x,y,z in upper]
    mesh.part('cap visor')
    mesh.poly(upper, 'visor', (0,0,1), group='top')
    mesh.poly(lower, 'visor', (0,0,-1), group='bottom')
    for i in range(len(outline)):
        j = (i+1) % len(outline)
        mesh.poly([lower[i], lower[j], upper[j], upper[i]], 'band')
    # A simple diamond badge stays readable at the room's normal viewing distance.
    badge = [(4.53,.22,28.74), (4.53,-.94,27.64), (4.53,.22,26.54), (4.53,1.38,27.64)]
    mount = [(3.72,y,z) for _,y,z in badge]
    mesh.part('cap rank diamond')
    mesh.poly(badge, 'visor', (1,0,0), group='front')
    for i in range(len(badge)):
        previous = i-1
        mesh.poly([mount[previous], mount[i], badge[i], badge[previous]], 'band')
    center = np.array((4.53,.22,27.64))
    relief = (np.asarray(badge)-center)*.60 + center
    raised = relief + (.34,0,0)
    mesh.part('molded cap insignia')
    mesh.poly(raised, 'rank', (1,0,0), group='front')
    for i in range(len(raised)):
        previous = i-1
        mesh.poly([relief[previous], relief[i], raised[i], raised[previous]], 'band')
    return mesh


def rank_boards(reference):
    """Small molded shoulder boards and chest bars, all in the soldier's green."""
    boards = []
    for y, z in ((-5.9,19.42), (4.67,19.55)):
        mesh = Mesh()
        mesh.box('shoulder board', (-2.06,y-1.05,z-1.0), (.79,y+1.05,z+.24), 'band', 'crown')
        for x in (-1.54,-.43):
            mesh.box('shoulder pip', (x,y-.60,z+.21), (x+.59,y+.60,z+.63), 'rank')
        mount = np.array((-.65, y, z))
        distance = np.linalg.norm(reference - mount, axis=1)
        boards.append((mesh, reference, np.argsort(distance)[:12]))
    mesh = Mesh()
    mesh.box('chest rank plate', (3.02,1.48,15.55), (3.98,4.15,17.19), 'band')
    for y in (1.76,2.53,3.30):
        mesh.box('chest bar', (3.90,y,15.92), (4.26,y+.52,16.89), 'rank')
    # Chest-pocket vertices stay with the jacket as the left sleeve moves.
    chest = [695, 732, 737, 746, 782, 813, 826, 833, 834, 838]
    boards.append((mesh, reference, chest))
    return boards


def interpolate_pose(keys, progress):
    """Sample an authored gesture with eased blends between the source poses."""
    for (start, a), (end, b) in zip(keys, keys[1:]):
        if start <= progress <= end:
            amount = (progress-start)/(end-start)
            return a, b, amount*amount*(3-2*amount)
    return NEUTRAL, NEUTRAL, 0


def briefing_pose(progress):
    indicate = ((0, NEUTRAL), (.36, INDICATE), (.61, INDICATE), (1, NEUTRAL))
    emphasize = ((0, NEUTRAL), (.28, INDICATE), (.51, EMPHASIZE), (.66, EMPHASIZE), (1, NEUTRAL))
    salute = ((0, NEUTRAL), (.17, INDICATE), (.33, 86), (.49, 87), (.64, 89),
              (.80, 92), (.89, INDICATE), (1, NEUTRAL))
    for start, end, keys in ((.20,.30,indicate), (.63,.73,emphasize), (.88,.994,salute)):
        if start <= progress <= end:
            return interpolate_pose(keys, (progress-start)/(end-start))
    return NEUTRAL, NEUTRAL, 0


def limb_basis(direction, palm):
    """Use the bone direction and its roll to form a local coordinate frame."""
    axis = direction / np.linalg.norm(direction)
    side = np.cross(axis, palm)
    side /= np.linalg.norm(side)
    return np.stack((axis, np.cross(side, axis), side))


def arm_poses(positions, normals):
    """Repose the left arm about the source shoulder and elbow."""
    rest = positions[REST]
    shoulder = np.array((0., 4.65, 18.5))
    elbow = np.array((2.3, 3.45, 14.3))
    wrist = np.array((7.5, -2.1, 9.5))
    upper = elbow - shoulder
    lower = wrist - elbow
    # The source wave isolates the sleeve from the adjoining torso. Exclude
    # the right arm, which also moves slightly during that clip.
    wave = np.linalg.norm(positions[115] - rest, axis=1)
    left = (rest[:, 1] > 0) | (rest[:, 0] > 3.5)
    shoulder_weight = (np.clip((wave - .9) / 2.9, 0, 1) * left)[:, None]
    along_forearm = (rest - elbow) @ (lower / np.linalg.norm(lower))
    elbow_weight = np.clip((along_forearm + .9) / 3.1, 0, 1)[:, None]
    upper_basis = limb_basis(upper, (0, 1, 0))
    lower_basis = limb_basis(lower, (0, 0, 1))
    rest_normals = normals[REST]
    poses, directions = [], []
    for upper_aim, lower_aim, palm in (
        ((.08, .50, -1), (.10, .13, -1), (.25, -1, 0)),  # Relaxed at his side.
        ((.40, .52, -1), (.95, .46, -.15), (0, -.45, 1)),  # Indicate the table.
        ((.63, .64, -1), (1, .50, .38), (0, -.35, 1)),  # Lift for emphasis.
    ):
        shoulder_rotation = upper_basis.T @ limb_basis(upper_aim, (0, 1, 0))
        forearm_rotation = lower_basis.T @ limb_basis(lower_aim, palm)
        posed_elbow = shoulder + upper @ shoulder_rotation
        upper_pose = (rest - shoulder) @ shoulder_rotation + shoulder
        lower_pose = (rest - elbow) @ forearm_rotation + posed_elbow
        upper_normal = rest_normals @ shoulder_rotation
        lower_normal = rest_normals @ forearm_rotation
        arm = upper_pose + elbow_weight * (lower_pose - upper_pose)
        arm_normal = upper_normal + elbow_weight * (lower_normal - upper_normal)
        poses.append(rest + shoulder_weight * (arm - rest))
        directions.append(rest_normals + shoulder_weight * (arm_normal - rest_normals))
    return poses, directions


def close_head(reference, body_faces, body_uvs):
    """Join the trimmed head to a closed ring tucked inside the officer's cap."""
    rim = {}
    for face, uv in zip(body_faces, body_uvs):
        for i, j in ((0, 1), (1, 2), (2, 0)):
            edge = (face[i], face[j])
            if edge[::-1] in rim:
                del rim[edge[::-1]]
            else:
                rim[edge] = (uv[i], uv[j])
    lower = np.unique(list(rim))
    if (not rim or len(rim) != len(lower) or {a for a, _ in rim} != {b for _, b in rim}
            or np.any(reference[lower, 2] <= 21)):
        raise ValueError('Expected a closed helmet trim perimeter')
    radial = reference[lower, :2] - (-.52, .22)
    radial /= np.linalg.norm(radial, axis=1)[:, None]
    xy = radial * (2.65, 2.20) + (-.52, .22)
    points = np.column_stack((xy, 24.2 + .36 * (xy[:, 0] + .52)))
    points = np.vstack((points, points.mean(axis=0)))
    normals = np.vstack((np.column_stack((radial, np.zeros(len(radial)))), (0, 0, 1)))
    first = len(reference)
    upper = dict(zip(lower, range(first, first + len(lower))))
    center = first + len(lower)
    faces, uvs = [], []
    for (a, b), (uv_a, uv_b) in rim.items():
        # Share the existing head positions and continue the skin from each
        # edge, including the original UV seams.
        faces.extend(((b, a, upper[a]), (b, upper[a], upper[b]), (upper[b], upper[a], center)))
        uvs.extend(((uv_b, uv_a, uv_a), (uv_b, uv_a, uv_b), (uv_b, uv_a, (uv_a + uv_b) / 2)))
    return points, normals, np.asarray(faces), np.asarray(uvs)


def fit_attachment(reference, pose, anchors):
    """Rigidly attach a part to the animated surface around its mounting point."""
    source, target = reference[anchors], pose[anchors]
    origin, center = source.mean(axis=0), target.mean(axis=0)
    left, _, right = np.linalg.svd((source-origin).T @ (target-center))
    rotation = left @ right
    if np.linalg.det(rotation) < 0:
        left[:, -1] *= -1
        rotation = left @ right
    return rotation, center-origin @ rotation


def stable_faces(poses, faces, can_drop):
    """Drop tiny inherited slivers that turn inside out on the new MD2 lattice."""
    keep = np.ones(len(faces), dtype=bool)
    for points in poses:
        minimum = points.min(axis=0).astype('<f4')
        scale = ((points.max(axis=0)-minimum)/255).astype('<f4')
        decoded = np.clip(np.rint((points-minimum)/scale), 0, 255)*scale+minimum
        raw, packed = points[faces], decoded[faces]
        before = np.cross(raw[:, 1]-raw[:, 0], raw[:, 2]-raw[:, 0])
        after = np.cross(packed[:, 1]-packed[:, 0], packed[:, 2]-packed[:, 0])
        invalid = np.flatnonzero(np.einsum('ij,ij->i', before, after) <= 0)
        if np.any(~can_drop[invalid]) or np.any(np.linalg.norm(before[invalid], axis=1) > .6):
            raise ValueError('Briefing MD2 quantization damaged the authored silhouette')
        keep[invalid] = False
    return keep


def build_model(samples, rate, last_frame):
    soldier = MD2.read((SOLDIER/'tris_pistol.md2').read_bytes(), source_compat=True)
    p = soldier.positions
    native_normals = normal_table()[soldier.normals]
    # Frame zero faces square ahead. Trim off the infantry helmet along its
    # sloped rim and fit the officer's cap over the cut on every pose.
    helmet = p[0,:,2] > 23.70 + .36*(p[0,:,0]+.52)
    visible = ~np.any(helmet[soldier.faces], axis=1)
    body_faces = soldier.faces[visible][:, [0,2,1]]
    body_uvs = soldier.uvs[visible][:, [0,2,1]]
    scalp, scalp_normals, scalp_faces, scalp_uvs = close_head(p[0], body_faces, body_uvs)
    trimmed_body = np.concatenate((body_faces, scalp_faces))
    used, remapped = np.unique(trimmed_body, return_inverse=True)
    faces = [remapped.reshape(trimmed_body.shape)]
    uvs = [body_uvs, scalp_uvs]
    segment = len(used)
    attachments = []
    cap_anchors = np.flatnonzero(helmet)
    parts = [(cap_mesh(), p[0], cap_anchors), *rank_boards(p[REST])]
    for mesh, reference, anchors in parts:
        points = np.asarray(mesh.vertices)
        topology = np.asarray(mesh.faces)
        faces.append(topology+segment)
        segment += len(points)
        uvs.append(np.asarray([(np.array(SWATCHES[material])+.5 + (np.asarray(uv)-.5)*2)/256
                                for uv,material in zip(mesh.uvs,mesh.materials)]))
        attachments.append((points, vertex_normals(points, topology), reference, anchors))

    authored_poses, authored_normals = arm_poses(p, native_normals)
    source_poses = np.concatenate((p, authored_poses))
    source_normals = np.concatenate((native_normals, authored_normals))
    poses, normals = [], []
    scale = 1.2
    floor = p[REST,:,2].min()
    duration = len(samples)/rate
    head = np.clip((p[0,:,2]-19.7)/2.5, 0, 1)  # Blend at the neck.
    jaw = np.clip((p[0,:,0]-1.4)/1.7, 0, 1) * np.maximum(0, 1-np.abs(p[0,:,2]-22.15)/1.15)
    for frame in range(last_frame+1):
        time = min(duration, max(0, frame-1)/10)
        progress = time/duration
        a,b,mix = briefing_pose(progress)
        pose = (1-mix)*source_poses[a] + mix*source_poses[b]
        directions = (1-mix)*source_normals[a] + mix*source_normals[b]
        start = int(time*rate)
        window = samples[start:start+rate//10] if frame else samples[:0]
        mouth = min(1, np.sqrt(np.mean(window**2))/4100) if len(window) else 0
        movement = min(1, time*3, (duration-time)*3)
        yaw = movement*(.11*math.sin(progress*math.tau) + .04*math.sin(time*2.7))
        cosine, sine = np.cos(head*yaw), np.sin(head*yaw)
        center = pose[helmet,:2].mean(axis=0)
        x,y = (pose[:,:2]-center).T
        pose[:,:2] = np.column_stack((x*cosine-y*sine, x*sine+y*cosine))+center
        x,y = directions[:,:2].T
        directions[:,:2] = np.column_stack((x*cosine-y*sine, x*sine+y*cosine))
        pose[:,2] -= jaw*mouth*.32
        rotation, shift = fit_attachment(p[0], pose, cap_anchors)
        parts_p = [np.concatenate((pose, scalp @ rotation + shift))[used]]
        parts_n = [np.concatenate((directions, scalp_normals @ rotation))[used]]
        for points, normal, reference, anchors in attachments:
            rotation, shift = fit_attachment(reference, pose, anchors)
            parts_p.append(points @ rotation + shift)
            parts_n.append(normal @ rotation)
        poses.append((np.concatenate(parts_p) - (0,0,floor))*scale)
        normals.append(np.concatenate(parts_n))
    names = ['rest', *(f'brief{i:03}' for i in range(last_frame))]
    triangles, texture_coordinates = np.concatenate(faces), np.concatenate(uvs)
    # Keep the closed head intact even if a future pose exceeds MD2 precision.
    can_drop = np.zeros(len(triangles), dtype=bool)
    can_drop[:len(body_faces)] = np.all(p[0, body_faces, 2] <= 21, axis=1)
    keep = stable_faces(poses, triangles, can_drop)
    model, _ = encode_md2(poses, normals, triangles[keep], texture_coordinates[keep], [SKIN], names)
    return model


def build_general(base, replacement=None):
    for relative in (MODEL, SKIN, VOICE):
        (base / relative).parent.mkdir(parents=True, exist_ok=True)
    samples, rate = voice_track(base / VOICE, replacement)
    duration = len(samples) / rate
    last_frame = math.ceil(duration * 10) + 4
    if duration < .5 or last_frame > 511:
        raise ValueError('Voice-over must be between 0.5 and 50.7 seconds')
    (base / MODEL).write_bytes(build_model(samples, rate, last_frame))
    (base / SKIN).write_bytes((SOLDIER/'green.png').read_bytes())
    return last_frame
