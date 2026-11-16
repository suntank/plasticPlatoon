#!/usr/bin/env python3
"""Experimental anatomy-pinned fork of md2_animation.simplify_shared.

The canonical animation tools are untouched. This private trial adds immutable
face/helmet, hands and boot vertices; all frames share one checked topology.
"""
from collections import Counter
import heapq
import math
import struct
import numpy as np
from md2_assets import MD2

def simplify_shared(source: MD2, target_triangles: int, *,
                    max_displacement_ratio: float = .02,
                    max_normal_angle_degrees: float = 40,
                    max_uv_displacement: float = .04,
                    min_area_ratio: float = .05, protected_vertices=()) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
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
    pinned = np.zeros(nv, dtype=bool)
    for edge, count in edge_counts.items():
        if count != 2:
            pinned[list(edge)] = True
    protected = np.asarray(protected_vertices, dtype=int)
    if protected.size and (protected.min() < 0 or protected.max() >= nv):
        raise ValueError("invalid protected anatomy vertex")
    pinned[protected] = True
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
        # This optional art trial retains each surviving face's original
        # UV triangle. Chart endpoints may remain split; anatomy is pinned.
        # Geometry displacement/area/orientation are checked in EVERY pose.
        trial_faces = faces[affected].copy()
        trial_uvs = uvs[affected].copy()
        changed = trial_faces == drop
        trial_faces[changed] = keep
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
    report = {"algorithm": "anatomy-pinned endpoint retopology, every pose constrained",
              "source_face_indices": np.flatnonzero(active).tolist(),
              "frames_checked": int(len(positions)), "target_triangles": int(target_triangles),
              "triangles_before": nf, "triangles_after": len(faces),
              "vertices_before": nv, "vertices_after": len(selected),
              "protected_anatomy_and_boundary_vertices": int(pinned.sum()),
              "accepted_collapses": accepted, "rejected_candidates": dict(sorted(rejected.items())),
              "max_cluster_displacement_ratio": worst_displacement,
              "displacement_limit_ratio": max_displacement_ratio,
              "normal_angle_limit_degrees": max_normal_angle_degrees,
              "uv_policy": "retained original face UVs; protected anatomy and boundaries",
              "minimum_original_face_area_ratio": min_area_ratio,
              "exact_source_vertex_coordinates_and_normals": True}
    return selected, faces, uvs, report
