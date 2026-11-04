#!/usr/bin/env python3
"""Conservative MD2 edge collapses shared by every animation frame.

Vertices remain a subset of the original vertices. A collapse is accepted only
when every pose passes a surface-distance, face-orientation and area check.
Original UV seams and mesh boundaries cannot be removed. No pose is decimated
independently, and surviving quantized coordinates and normal bytes are exact.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import heapq
import math
import struct

import numpy as np

from md2_assets import HEADER, IDENT, MD2, gl_strips


def _st_table(uvs: np.ndarray, dimensions: tuple[int, int]) -> tuple[bytes, np.ndarray]:
    keys, values, indices = {}, [], []
    for triangle in uvs:
        row = []
        for uv in triangle:
            key = tuple(np.rint(uv * dimensions - .5).astype(int))
            if not all(-32768 <= v <= 32767 for v in key):
                raise ValueError("software texture coordinate overflow")
            if key not in keys:
                keys[key] = len(values)
                values.append(key)
            row.append(keys[key])
        indices.append(row)
    if len(values) > 32767:
        raise ValueError("too many software texture coordinates")
    return np.asarray(values, dtype="<i2").tobytes(), np.asarray(indices, dtype=np.int32)


def encode_vertex_subset(source: MD2, source_vertices: np.ndarray,
                         faces: np.ndarray, uvs: np.ndarray,
                         skins: list[str] | None = None) -> bytes:
    """Write one shared topology and exact source vertex bytes for every pose."""
    selected = np.asarray(source_vertices, dtype=np.int32)
    faces = np.asarray(faces, dtype=np.int32)
    uvs = np.asarray(uvs, dtype=np.float64)
    if (selected.ndim != 1 or len(selected) == 0 or len(np.unique(selected)) != len(selected)
            or selected.min() < 0 or selected.max() >= source.header[6]):
        raise ValueError("source vertex subset is invalid")
    if (faces.ndim != 2 or faces.shape[1] != 3 or len(faces) == 0
            or faces.min() < 0 or faces.max() >= len(selected)
            or uvs.shape != (len(faces), 3, 2) or not np.isfinite(uvs).all()):
        raise ValueError("shared triangle topology or UVs are invalid")
    if len(np.unique(faces)) != len(selected):
        raise ValueError("source subset contains unused vertices")
    skins = source.skins if skins is None else skins
    skin_raw = bytearray()
    for skin in skins:
        raw = skin.encode("utf-8")
        if len(raw) >= 64 or b"\0" in raw:
            raise ValueError("skin reference exceeds the MD2 string limit")
        skin_raw.extend(raw.ljust(64, b"\0"))
    st_raw, st_faces = _st_table(uvs, source.header[2:4])
    triangle_raw = np.column_stack((faces, st_faces)).astype("<u2").tobytes()
    frame_raw = bytearray()
    for frame in range(source.header[10]):
        offset = source.header[14] + frame * source.header[4]
        # Copy names, scales and translations without float re-encoding.
        frame_raw.extend(source.data[offset:offset + 40])
        vertices = np.frombuffer(source.data, dtype=np.uint8,
                                 count=source.header[6] * 4, offset=offset + 40).reshape(-1, 4)
        frame_raw.extend(vertices[selected].tobytes())
    command_raw = gl_strips(faces, uvs)
    sections = (bytes(skin_raw), st_raw, triangle_raw, bytes(frame_raw), command_raw)
    offsets, cursor = [], HEADER.size
    for section in sections:
        offsets.append(cursor)
        cursor += len(section)
    header = HEADER.pack(IDENT, 8, *source.header[2:4], 40 + len(selected) * 4,
                         len(skins), len(selected), len(st_raw) // 4, len(faces),
                         len(command_raw) // 4, source.header[10], *offsets, cursor)
    output = header + b"".join(sections)
    result = MD2.read(output)
    if result.names != source.names:
        raise AssertionError("animation frame names changed")
    np.testing.assert_array_equal(result.positions, source.positions[:, selected])
    np.testing.assert_array_equal(result.normals, source.normals[:, selected])
    np.testing.assert_array_equal(result.scales, source.scales)
    np.testing.assert_array_equal(result.translations, source.translations)
    return output


def repair_stale_triangle_table(data: bytes, *, expected_sha256: str) -> tuple[MD2, dict]:
    """Repair a hash-pinned invalid table from a complete, valid GL stream.

    This is deliberately opt-in. It does not accept valid-but-different tables,
    missing GL faces, extra GL faces, or changes to frames/commands. The known
    hyperblaster exporter left indices from an older, larger mesh in its table.
    """
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256:
        raise ValueError("source hash differs from the explicitly authorized repair")
    if len(data) < HEADER.size:
        raise ValueError("truncated MD2 header")
    h = HEADER.unpack_from(data)
    ident, version, sw, sh, stride, ns, nv, nt, nf, nc, nframes, os, ot, of, ofr, oc, end = h
    if ((ident, version) != (IDENT, 8) or not 0 < nv <= 2048 or not 0 < nt <= 32767
            or not 0 < nf <= 4096 or not 0 < nframes <= 512 or not 0 <= ns <= 32
            or sw <= 0 or not 0 < sh <= 480 or stride < 40 + 4 * nv):
        raise ValueError("invalid source MD2 header")
    last = HEADER.size
    for offset, length in ((os, ns * 64), (ot, nt * 4), (of, nf * 12),
                           (ofr, stride * nframes), (oc, nc * 4)):
        if offset < last or length < 0 or offset + length > end or end > len(data):
            raise ValueError("invalid source MD2 section")
        last = offset + length
    old = np.frombuffer(data, dtype="<u2", count=nf * 6, offset=of).reshape(-1, 6)
    invalid_xyz = np.any(old[:, :3] >= nv, axis=1)
    invalid_st = np.any(old[:, 3:] >= nt, axis=1)
    if not invalid_xyz.any() and not invalid_st.any():
        raise ValueError("repair requires a demonstrably invalid triangle table")
    faces, uvs, cursor = [], [], oc
    while cursor + 4 <= oc + nc * 4:
        count = struct.unpack_from("<i", data, cursor)[0]
        cursor += 4
        if not count:
            break
        if abs(count) < 3 or cursor + abs(count) * 12 > oc + nc * 4:
            raise ValueError("invalid GL primitive")
        values = [struct.unpack_from("<ffi", data, cursor + i * 12) for i in range(abs(count))]
        cursor += abs(count) * 12
        if any(not math.isfinite(s) or not math.isfinite(t) or not 0 <= index < nv
               for s, t, index in values):
            raise ValueError("invalid GL vertex")
        for i in range(2, abs(count)):
            corners = ((0, i - 1, i) if count < 0 else
                       ((i - 2, i - 1, i) if i % 2 == 0 else (i - 1, i - 2, i)))
            faces.append([values[j][2] for j in corners])
            uvs.append([[values[j][0], values[j][1]] for j in corners])
    else:
        raise ValueError("GL stream has no terminator")
    if cursor != oc + nc * 4 or len(faces) != nf:
        raise ValueError("GL stream is incomplete or disagrees with triangle count")
    st_raw, st_faces = _st_table(np.asarray(uvs), (sw, sh))
    if len(st_raw) > nt * 4:
        raise ValueError("repaired ST table does not fit the original section")
    patched = bytearray(data)
    patched[ot:ot + nt * 4] = st_raw.ljust(nt * 4, b"\0")
    patched[of:of + nf * 12] = np.column_stack((faces, st_faces)).astype("<u2").tobytes()
    model = MD2.read(bytes(patched))
    if patched[ofr:oc] != data[ofr:oc] or patched[oc:end] != data[oc:end]:
        raise AssertionError("table repair changed frames or GL commands")
    return model, {"policy": "hash-pinned GL-command-authoritative triangle/ST table repair",
                   "source_sha256": digest, "output_sha256": hashlib.sha256(patched).hexdigest(),
                   "invalid_xyz_triangles": int(invalid_xyz.sum()),
                   "invalid_st_triangles": int(invalid_st.sum()),
                   "preserved_gl_triangles": nf, "preserved_frames": nframes}


def simplify_shared(source: MD2, target_triangles: int, *,
                    max_displacement_ratio: float = .02,
                    max_normal_angle_degrees: float = 40,
                    max_uv_displacement: float = .04,
                    min_area_ratio: float = .05) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    """Collapse shared edges conservatively, with every original pose checked.

    The displacement bound is a fraction of EACH pose's original bounding-box
    diagonal. It bounds every original cluster member, not just the last edge.
    Normal/area bounds compare against each affected ORIGINAL source triangle,
    so multiple individually small changes cannot accumulate unchecked drift.
    """
    if (target_triangles < 1 or not 0 < max_displacement_ratio < 1
            or not 0 < max_normal_angle_degrees < 90 or not 0 < max_uv_displacement < 1
            or not 0 < min_area_ratio <= 1):
        raise ValueError("invalid simplification limits")
    positions = source.positions
    original_faces = source.faces
    faces = original_faces.copy()
    uvs = source.uvs.copy()
    nf, nv = len(faces), source.header[6]
    active = np.ones(nf, dtype=bool)
    alive = np.ones(nv, dtype=bool)
    incident = [set() for _ in range(nv)]
    uv_variants = [set() for _ in range(nv)]
    uv_values = [None] * nv
    edge_counts = Counter()
    face_keys = [tuple(sorted(map(int, face))) for face in faces]
    face_counts = Counter(face_keys)
    for i, (face, coords) in enumerate(zip(faces, uvs)):
        for vertex, uv in zip(face, coords):
            incident[int(vertex)].add(i)
            uv_variants[int(vertex)].add(struct.pack("<2f", *uv))
            uv_values[int(vertex)] = uv.copy()
        for a, b in zip(face, np.roll(face, 1)):
            edge_counts[tuple(sorted((int(a), int(b))))] += 1
    pinned = np.array([len(values) != 1 for values in uv_variants])
    for edge, count in edge_counts.items():
        if count != 2:
            pinned[list(edge)] = True
    members = [[i] for i in range(nv)]
    diagonal = np.linalg.norm(positions.max(axis=1) - positions.min(axis=1), axis=1)
    if np.any(diagonal <= 0) or not np.isfinite(diagonal).all():
        raise ValueError("source has an empty or invalid animation pose")
    limit = diagonal * max_displacement_ratio
    area_epsilon = diagonal ** 2 * 1e-12
    triangles = positions[:, original_faces]
    reference_normals = np.cross(triangles[:, :, 1] - triangles[:, :, 0],
                                 triangles[:, :, 2] - triangles[:, :, 0])
    reference_areas = np.linalg.norm(reference_normals, axis=2)
    uv_a, uv_b = source.uvs[:, 1] - source.uvs[:, 0], source.uvs[:, 2] - source.uvs[:, 0]
    reference_uv_area = uv_a[:, 0] * uv_b[:, 1] - uv_a[:, 1] * uv_b[:, 0]
    del triangles
    cosine = math.cos(math.radians(max_normal_angle_degrees))
    generations = np.zeros(nv, dtype=np.int64)
    queue, enqueued, rejected = [], set(), Counter()
    worst_displacement, accepted = 0., 0

    def neighbors(vertex):
        return {int(v) for i in incident[vertex] for v in faces[i] if v != vertex}

    def push(drop, keep):
        if pinned[drop] or not alive[drop] or not alive[keep]:
            return
        key = (drop, keep, int(generations[drop]), int(generations[keep]))
        if key in enqueued:
            return
        distance = np.linalg.norm(positions[:, members[drop]] - positions[:, keep, None], axis=2)
        error = float(np.max(distance / limit[:, None]))
        if error > 1:
            return
        enqueued.add(key)
        heapq.heappush(queue, (error, *key))

    for a, b in sorted(edge_counts):
        push(a, b)
        push(b, a)
    while queue and int(active.sum()) > target_triangles:
        error, drop, keep, drop_generation, keep_generation = heapq.heappop(queue)
        if (not alive[drop] or not alive[keep] or drop_generation != generations[drop]
                or keep_generation != generations[keep]):
            continue
        common = incident[drop] & incident[keep]
        if len(common) != 2:
            rejected["nonmanifold_edge"] += 1
            continue
        opposite = {int(v) for i in common for v in faces[i] if v not in (drop, keep)}
        if neighbors(drop) & neighbors(keep) != opposite:
            rejected["link_condition"] += 1
            continue
        affected = sorted(incident[drop] - common)
        if not affected:
            rejected["empty_fan"] += 1
            continue
        # The edge must stay within one texture chart. A seam endpoint can be
        # kept, but its chart-specific coordinate must agree on both edge faces.
        keep_uvs = [uvs[i, np.flatnonzero(faces[i] == keep)[0]] for i in sorted(common)]
        if not np.array_equal(keep_uvs[0], keep_uvs[1]):
            rejected["uv_seam_edge"] += 1
            continue
        keep_uv = keep_uvs[0]
        drop_original_uvs = np.asarray([uv_values[v] for v in members[drop]])
        if np.max(np.linalg.norm(drop_original_uvs - keep_uv, axis=1)) > max_uv_displacement:
            rejected["uv_displacement"] += 1
            continue
        trial_faces = faces[affected].copy()
        trial_uvs = uvs[affected].copy()
        changed = trial_faces == drop
        trial_faces[changed] = keep
        trial_uvs[changed] = keep_uv
        # Vertex-neighbor links alone miss a shared edge in the full links:
        # collapsing a tetrahedron edge would leave two opposite, coincident
        # triangles. Compare unordered faces to enforce that part of the full
        # link condition, both against unaffected faces and within this trial.
        trial_keys = [tuple(sorted(map(int, face))) for face in trial_faces]
        removed_counts = Counter(face_keys[i] for i in incident[drop])
        if (len(set(trial_keys)) != len(trial_keys)
                or any(face_counts[key] > removed_counts[key] for key in trial_keys)):
            rejected["duplicate_face_full_link"] += 1
            continue
        uv_a, uv_b = trial_uvs[:, 1] - trial_uvs[:, 0], trial_uvs[:, 2] - trial_uvs[:, 0]
        uv_area = uv_a[:, 0] * uv_b[:, 1] - uv_a[:, 1] * uv_b[:, 0]
        old_uv_area = reference_uv_area[affected]
        uv_valid = np.abs(old_uv_area) > 1e-15
        if np.any(uv_valid & ((uv_area * old_uv_area <= 0)
                  | (np.abs(uv_area) < np.abs(old_uv_area) * min_area_ratio))):
            rejected["uv_flip_or_degenerate"] += 1
            continue
        points = positions[:, trial_faces]
        normals = np.cross(points[:, :, 1] - points[:, :, 0], points[:, :, 2] - points[:, :, 0])
        areas = np.linalg.norm(normals, axis=2)
        old_areas = reference_areas[:, affected]
        old_normals = reference_normals[:, affected]
        valid = old_areas > area_epsilon[:, None]
        dots = np.sum(normals * old_normals, axis=2)
        if np.any(valid & ((areas < old_areas * min_area_ratio)
                           | (dots < cosine * old_areas * areas))):
            rejected["pose_flip_area_or_normal"] += 1
            continue
        # Preserve the link condition after every accepted collapse.
        touched = neighbors(drop) | neighbors(keep) | {drop, keep}
        for i in sorted(incident[drop]):
            face_counts[face_keys[i]] -= 1
            for vertex in faces[i]:
                incident[int(vertex)].discard(i)
        for i in common:
            active[i] = False
        faces[affected], uvs[affected] = trial_faces, trial_uvs
        for i, key in zip(affected, trial_keys):
            face_keys[i] = key
            face_counts[key] += 1
            for vertex in faces[i]:
                incident[int(vertex)].add(i)
        incident[drop].clear()
        alive[drop] = False
        members[keep].extend(members[drop])
        members[drop] = []
        generations[list(touched)] += 1
        for vertex in sorted(touched):
            if alive[vertex]:
                for neighbor in sorted(neighbors(vertex)):
                    push(vertex, neighbor)
                    push(neighbor, vertex)
        worst_displacement = max(worst_displacement, error * max_displacement_ratio)
        accepted += 1
    faces, uvs = faces[active], uvs[active]
    selected = np.unique(faces)
    remap = np.full(nv, -1, dtype=np.int32)
    remap[selected] = np.arange(len(selected))
    faces = remap[faces]
    report = {"algorithm": "shared endpoint edge collapse, every pose constrained",
              "frames_checked": int(len(positions)), "target_triangles": int(target_triangles),
              "triangles_before": nf, "triangles_after": len(faces),
              "vertices_before": nv, "vertices_after": len(selected),
              "pinned_uv_seam_boundary_vertices": int(pinned.sum()),
              "accepted_collapses": accepted, "rejected_candidates": dict(sorted(rejected.items())),
              "max_cluster_displacement_ratio": worst_displacement,
              "displacement_limit_ratio": max_displacement_ratio,
              "normal_angle_limit_degrees": max_normal_angle_degrees,
              "uv_displacement_limit": max_uv_displacement,
              "minimum_original_face_area_ratio": min_area_ratio,
              "exact_source_vertex_coordinates_and_normals": True}
    return selected, faces, uvs, report
