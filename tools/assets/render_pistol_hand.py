#!/usr/bin/env python3
"""Render six diagnostic hand/grip views from the actual exported pistol MD2.

Requires only NumPy and Pillow. Temporary contrasting colors expose contacts
and occlusion; the second panel shows the hand/arm/cuff silhouette alone.
These are CPU geometry diagnostics, not game screenshots or final materials.

  .venv/bin/python tools/assets/render_pistol_hand.py --output build/pistol-hand-qa
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from build_pistol import placement
from md2_assets import MD2
from pistol_geometry import build_pistol

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = ROOT / 'baseq2/models/weapons/v_blast/tris.md2'
BACKGROUND = (246, 247, 247)
GUN_COLOR = (115, 139, 157)
HAND_COLOR = (221, 153, 86)
CUFF_COLOR = (174, 111, 58)
SILHOUETTE = (30, 35, 39)
INK = (37, 46, 53)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def unit(vector):
    value = np.asarray(vector, dtype=float)
    return value / np.linalg.norm(value)


def font(size, bold=False):
    try:
        return ImageFont.truetype('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf', size)
    except OSError:
        return ImageFont.load_default()


@dataclass
class View:
    name: str
    label: str
    eye: np.ndarray
    forward: np.ndarray
    perspective: bool = False

    def basis(self):
        right = unit(np.cross(self.forward, (0, 0, 1)))
        up = unit(np.cross(right, self.forward))
        return right, up

    def project(self, points):
        right, up = self.basis()
        relative = points - self.eye
        depth = relative @ self.forward
        xy = np.column_stack((relative @ right, relative @ up))
        if self.perspective:
            xy = xy / depth[:, None]
        return xy, depth


def load_geometry(path):
    """Preserve triangle-table ordering for source part classification."""
    model = MD2.read(path.read_bytes())
    source = build_pistol('view')
    table = np.frombuffer(model.data, dtype='<u2', count=model.header[8]*6,
                          offset=model.header[13]).reshape(-1, 6)
    # The MD2 command stream reorders triangles into strips. Only the raw
    # triangle table retains the source part ranges. Quake exterior winding
    # is clockwise; reverse it to obtain outward CCW geometric normals.
    faces = table[:, :3][:, [0, 2, 1]].astype(np.int32)
    expected_faces = np.asarray(source['faces'], dtype=np.int32)
    if faces.shape != expected_faces.shape or not np.array_equal(faces, expected_faces):
        raise ValueError('Model topology differs from current pistol source; rebuild the pistol first')
    matrix, offset, _ = placement('view')
    expected_positions = np.asarray(source['vertices']) @ matrix + offset
    if model.positions[0].shape != expected_positions.shape:
        raise ValueError('Model vertex count differs from current pistol source')
    error = np.abs(model.positions[0] - expected_positions)
    if np.any(error > model.scales[0]/2 + 1e-5):
        raise ValueError('Model placement/geometry differs from current source; rebuild the pistol first')
    # Every rendered position comes from the quantized exported MD2, never
    # from the unquantized source. Source data supplies part names only.
    positions = (model.positions[0] - offset) @ np.linalg.inv(matrix)
    names = np.empty(len(faces), dtype=object)
    for part in source['parts']:
        first = part['first_triangle']
        names[first:first+part['triangle_count']] = part['name']
    hand = np.array([name.startswith(('hand_', 'arm_', 'cuff_')) for name in names])
    cuff = np.array([name.startswith('cuff_') for name in names])
    # The crop includes the full grip, hand and cuff join. The long muzzle
    # and distant forearm may extend outside the diagnostic crop on purpose.
    roi_faces = np.array([name.startswith(('hand_', 'cuff_')) or name == 'grip'
                          for name in names])
    roi = positions[np.unique(faces[roi_faces])]
    roi = np.vstack((roi, positions[np.unique(faces[names == 'trigger_guard'])]))
    back_slide = positions[np.unique(faces[names == 'slide'])]
    roi = np.vstack((roi, back_slide[back_slide[:, 0] < 30]))
    return model, source, positions, faces, names, hand, cuff, roi


def make_views(roi):
    low, high = roi.min(axis=0), roi.max(axis=0)
    center = (low + high) / 2
    matrix, offset, _ = placement('view')
    inverse = np.linalg.inv(matrix)
    eye = -offset @ inverse
    # This is the exact exported viewmodel eye and forward direction, then
    # cropped/zoomed. The other views use orthographic projection to make
    # silhouette/contact comparisons independent of perspective distortion.
    result = [View('actual-eye', 'Actual eye (perspective crop)', eye,
                   unit(np.array((1., 0., 0.)) @ inverse), True)]
    specifications = [
        ('rear-positive-y', 'Rear three-quarter +Y', (-34, 25, 17)),
        ('rear-negative-y', 'Rear three-quarter -Y', (-34, -25, 17)),
        ('positive-y-side', '+Y side / thumb side', (0, 50, 5)),
        ('negative-y-side', '-Y side / back of hand', (0, -50, 5)),
        ('lower-rear', 'Lower rear / cuff connection', (-35, 18, -20)),
    ]
    for name, label, delta in specifications:
        camera = center + np.asarray(delta, dtype=float)
        result.append(View(name, label, camera, unit(center-camera)))
    return result


def rasterize(positions, faces, hand, cuff, roi, view, size, silhouette=False):
    """Render outward front-facing triangles with perspective-correct depth."""
    width, height = size
    aa = 2
    width *= aa
    height *= aa
    xy, depth = view.project(positions)
    roi_xy, roi_depth = view.project(roi)
    if np.any(roi_depth <= 1e-5):
        raise ValueError('Diagnostic subject crosses the camera near plane')
    low, high = roi_xy.min(axis=0), roi_xy.max(axis=0)
    center = (low+high)/2
    span = np.maximum(high-low, 1e-6)
    scale = min(width/span[0], height/span[1])*.85
    screen = (xy-center)*np.array((scale, -scale)) + np.array((width/2, height/2))
    pixels = np.full((height, width, 3), BACKGROUND, dtype=np.uint8)
    zbuffer = np.full((height, width), np.inf)
    key = unit((-0.4, 0.5, 0.8))
    visible = 0
    for number, ids in enumerate(faces):
        if silhouette and not hand[number]:
            continue
        triangle = positions[ids]
        normal = np.cross(triangle[1]-triangle[0], triangle[2]-triangle[0])
        magnitude = np.linalg.norm(normal)
        if magnitude < 1e-12 or np.any(depth[ids] <= 1e-5):
            continue
        normal /= magnitude
        to_camera = (view.eye-triangle.mean(axis=0)) if view.perspective else -view.forward
        # Culling matters: reversed or missing surfaces must remain visible
        # as such in these diagnostics, rather than receiving two-sided fill.
        if np.dot(normal, to_camera) <= 1e-10:
            continue
        p = screen[ids]
        x0 = max(0, int(np.floor(p[:, 0].min())))
        x1 = min(width-1, int(np.ceil(p[:, 0].max())))
        y0 = max(0, int(np.floor(p[:, 1].min())))
        y1 = min(height-1, int(np.ceil(p[:, 1].max())))
        if x1 < x0 or y1 < y0:
            continue
        denominator = ((p[1, 1]-p[2, 1])*(p[0, 0]-p[2, 0])+
                       (p[2, 0]-p[1, 0])*(p[0, 1]-p[2, 1]))
        if abs(denominator) < 1e-12:
            continue
        xx, yy = np.meshgrid(np.arange(x0, x1+1)+.5, np.arange(y0, y1+1)+.5)
        a = ((p[1, 1]-p[2, 1])*(xx-p[2, 0])+
             (p[2, 0]-p[1, 0])*(yy-p[2, 1]))/denominator
        b = ((p[2, 1]-p[0, 1])*(xx-p[2, 0])+
             (p[0, 0]-p[2, 0])*(yy-p[2, 1]))/denominator
        c = 1-a-b
        inside = (a >= -1e-8) & (b >= -1e-8) & (c >= -1e-8)
        if view.perspective:
            reciprocal = a/depth[ids[0]] + b/depth[ids[1]] + c/depth[ids[2]]
            candidate = np.full_like(reciprocal, np.inf)
            np.divide(1., reciprocal, out=candidate, where=reciprocal > 0)
        else:
            candidate = a*depth[ids[0]] + b*depth[ids[1]] + c*depth[ids[2]]
        target = zbuffer[y0:y1+1, x0:x1+1]
        update = inside & (candidate < target)
        if not np.any(update):
            continue
        if silhouette:
            color = SILHOUETTE
        else:
            base = CUFF_COLOR if cuff[number] else HAND_COLOR if hand[number] else GUN_COLOR
            illumination = .50+.35*max(0., np.dot(normal, key))+.15*max(0., np.dot(normal, -view.forward))
            color = np.clip(np.asarray(base)*illumination, 0, 255).astype(np.uint8)
        pixels[y0:y1+1, x0:x1+1][update] = color
        target[update] = candidate[update]
        visible += 1
    rendered = Image.fromarray(pixels).resize(size, Image.Resampling.LANCZOS)
    framing = dict(projected_roi=[low.tolist(), high.tolist()],
                   pixels_per_projection_unit=float(scale/aa),
                   image_size=list(size), visible_triangles=visible,
                   nonbackground_pixels=int(np.isfinite(zbuffer).sum()/aa**2))
    return rendered, framing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--model', type=Path, default=DEFAULT_MODEL)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    model, source, positions, faces, names, hand, cuff, roi = load_geometry(args.model)
    views = make_views(roi)
    panel_size = (560, 470)
    cell_width, cell_height = 1150, 575
    header_height, footer_height = 110, 60
    sheet = Image.new('RGB', (cell_width*2, header_height+cell_height*3+footer_height), 'white')
    draw = ImageDraw.Draw(sheet)
    draw.text((25, 15), 'Pistol hand / grip: six-angle geometry check', font=font(32, True), fill=INK)
    draw.rectangle((26, 65, 49, 88), fill=GUN_COLOR)
    draw.text((58, 61), 'Gun: blue-gray', font=font(21), fill=INK)
    draw.rectangle((305, 65, 328, 88), fill=HAND_COLOR)
    draw.text((337, 61), 'Hand/arm: clay (temporary diagnostic colors)', font=font(21), fill=INK)
    draw.text((1010, 61), 'Black: hand/arm/cuff silhouette with gun omitted', font=font(21), fill=INK)
    metadata = dict(schema=1, renderer='NumPy/Pillow CPU triangle z-buffer; 2x antialiasing',
                    notice='Geometry diagnostics, not final game materials or gameplay captures',
                    model=dict(path=str(args.model.resolve()), sha256=hashlib.sha256(model.data).hexdigest(),
                               triangles=len(faces), hand_triangles=int(hand.sum()),
                               position_vertices=len(positions)),
                    source_sha256={name:digest(ROOT/'tools/assets'/name) for name in
                                   ('pistol_geometry.py', 'build_pistol.py', 'm16_geometry.py',
                                    'render_pistol_hand.py')},
                    triangle_order='Raw MD2 triangle table, exterior winding reversed to CCW',
                    colors=dict(gun=GUN_COLOR, hand=HAND_COLOR, cuff=CUFF_COLOR, silhouette=SILHOUETTE),
                    views=[], outputs=[])
    for index, view in enumerate(views):
        cell = Image.new('RGB', (cell_width, cell_height), 'white')
        label = ImageDraw.Draw(cell)
        label.text((16, 8), view.label, font=font(26, True), fill=INK)
        label.text((16, 43), 'Contact / occlusion colors', font=font(20), fill=INK)
        label.text((586, 43), 'Hand + cuff silhouette', font=font(20), fill=INK)
        contrast, framing = rasterize(positions, faces, hand, cuff, roi, view, panel_size)
        silhouette, silhouette_framing = rasterize(positions, faces, hand, cuff, roi, view, panel_size, True)
        cell.paste(contrast, (10, 78))
        cell.paste(silhouette, (580, 78))
        cell.save(args.output/(view.name+'.png'))
        contrast.save(args.output/(view.name+'-contact.png'))
        silhouette.save(args.output/(view.name+'-silhouette.png'))
        sheet.paste(cell, ((index%2)*cell_width, header_height+(index//2)*cell_height))
        metadata['views'].append(dict(name=view.name, label=view.label,
                                      eye=view.eye.tolist(), forward=view.forward.tolist(),
                                      projection='perspective crop from actual eye' if view.perspective else 'orthographic',
                                      contact=framing, silhouette=silhouette_framing))
    footer_y = header_height+cell_height*3+10
    draw.text((25, footer_y), 'Crops keep hand, grip and cuff join large. Distant muzzle/forearm can extend outside frame. Only outward front-facing surfaces render.',
              font=font(20), fill=INK)
    sheet.save(args.output/'contact-sheet.png')
    for path in sorted(args.output.glob('*.png')):
        metadata['outputs'].append(dict(path=path.name, sha256=digest(path), bytes=path.stat().st_size))
    (args.output/'metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
    print(args.output/'contact-sheet.png')
    print(args.output/'metadata.json')


if __name__ == '__main__':
    main()
