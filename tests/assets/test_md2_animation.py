#!/usr/bin/env python3
"""Synthetic multi-pose regression fixtures for shared MD2 simplification."""
from pathlib import Path
import hashlib
import json
import struct
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/assets"))
from md2_assets import HEADER, IDENT, MD2, gl_strips
import md2_assets as md2
from md2_animation import encode_vertex_subset, repair_stale_triangle_table, simplify_shared


def grid(side=3, raised=False, seam=False):
    vertices = np.array([[x, y, 0] for y in range(side) for x in range(side)], dtype=float)
    frames = [vertices.copy(), vertices.copy()]
    if raised:
        frames[1][len(vertices) // 2, 2] = side * 2
    else:
        frames[1][:, 2] = np.sin(vertices[:, 0]) * np.sin(vertices[:, 1]) * .1
    faces = []
    for y in range(side - 1):
        for x in range(side - 1):
            a = y * side + x
            faces.extend(((a, a + 1, a + side + 1), (a, a + side + 1, a + side)))
    faces = np.asarray(faces)
    uvs = vertices[faces, :2] / (side - 1)
    if seam:
        # The center now has two genuinely different UV chart coordinates.
        center = len(vertices) // 2
        first = np.flatnonzero(np.any(faces == center, axis=1))[0]
        uvs[first, faces[first] == center, 0] += .125
    return model_from_poses(frames, faces, uvs)


def model_from_poses(frames, faces, uvs):
    vertices = frames[0]
    skins = b"models/test/skin.png".ljust(64, b"\0")
    st = np.rint(uvs.reshape(-1, 2) * 256 - .5).astype("<i2").tobytes()
    table = np.column_stack((faces, np.arange(len(faces) * 3).reshape(-1, 3))).astype("<u2").tobytes()
    frame_data = bytearray()
    # Nonstandard padding is intentional: the writer must compact it safely.
    stride = 40 + len(vertices) * 4 + 17
    for i, positions in enumerate(frames):
        scale = np.maximum(positions.max(axis=0) - positions.min(axis=0), .01) / 250
        trans = positions.min(axis=0)
        quantized = np.rint((positions - trans) / scale).astype(np.uint8)
        normals = (np.arange(len(vertices)) + i * 7) % 162
        frame_data.extend(struct.pack("<6f", *scale, *trans))
        frame_data.extend(f"pose{i}".encode().ljust(16, b"\0"))
        frame_data.extend(np.column_stack((quantized, normals)).astype(np.uint8).tobytes())
        frame_data.extend(b"padding-for-frame")
    commands = gl_strips(faces, uvs)
    sections = (skins, st, table, bytes(frame_data), commands)
    offsets, cursor = [], HEADER.size
    for section in sections:
        offsets.append(cursor)
        cursor += len(section)
    data = HEADER.pack(IDENT, 8, 256, 256, stride, 1, len(vertices), len(st) // 4,
                       len(faces), len(commands) // 4, len(frames), *offsets, cursor) + b"".join(sections)
    return MD2.read(data)


class SharedAnimationTests(unittest.TestCase):
    def test_roundtrip_preserves_all_frame_bytes_and_compacts_stride(self):
        source = grid(5)
        selected = np.arange(source.header[6])
        output = MD2.read(encode_vertex_subset(source, selected, source.faces, source.uvs))
        self.assertEqual(output.header[4], 40 + len(selected) * 4)
        self.assertEqual(output.names, source.names)
        np.testing.assert_array_equal(output.positions, source.positions)
        np.testing.assert_array_equal(output.normals, source.normals)
        np.testing.assert_array_equal(output.scales, source.scales)
        np.testing.assert_array_equal(output.translations, source.translations)

    def test_shared_reduction_preserves_pose_subset_and_distance_bound(self):
        source = grid(7)
        selected, faces, uvs, report = simplify_shared(source, 45,
            max_displacement_ratio=.19, max_uv_displacement=.3)
        self.assertLess(len(faces), len(source.faces))
        self.assertLessEqual(report["max_cluster_displacement_ratio"], .19)
        output = MD2.read(encode_vertex_subset(source, selected, faces, uvs))
        self.assertEqual(output.header[10], 2)
        np.testing.assert_array_equal(output.positions, source.positions[:, selected])
        np.testing.assert_array_equal(output.normals, source.normals[:, selected])
        # Independently check that every original animated vertex has one
        # surviving vertex within the displacement bound in BOTH poses.
        diagonal = np.linalg.norm(np.ptp(source.positions, axis=1), axis=1)
        distance = np.linalg.norm(source.positions[:, :, None] - output.positions[:, None], axis=3)
        joint_error = (distance / diagonal[:, None, None]).max(axis=0)
        self.assertLessEqual(float(joint_error.min(axis=1).max()), .19 + 1e-12)

    def test_a_later_pose_blocks_a_collapse_that_the_first_pose_allows(self):
        source = grid(3, raised=True)
        first = MD2.read(encode_vertex_subset(source, np.arange(9), source.faces, source.uvs))
        # A one-pose source with identical topology, for the comparison only.
        first.positions = first.positions[:1]
        first.header = (*first.header[:10], 1, *first.header[11:])
        args = {"max_displacement_ratio": .99, "max_uv_displacement": .9,
                "max_normal_angle_degrees": 20}
        _, one_faces, _, _ = simplify_shared(first, 6, **args)
        _, all_faces, _, report = simplify_shared(source, 6, **args)
        self.assertLess(len(one_faces), len(source.faces))
        self.assertEqual(len(all_faces), len(source.faces))
        self.assertGreater(report["rejected_candidates"].get("pose_flip_area_or_normal", 0), 0)

    def test_uv_seam_vertex_and_open_boundary_cannot_be_removed(self):
        source = grid(3, seam=True)
        selected, faces, _, report = simplify_shared(source, 2,
            max_displacement_ratio=.9, max_uv_displacement=.9)
        self.assertEqual(set(selected), set(range(9)))
        self.assertEqual(len(faces), len(source.faces))
        self.assertEqual(report["pinned_uv_seam_boundary_vertices"], 9)

    def test_tetrahedron_edge_cannot_collapse_into_opposite_duplicate_faces(self):
        vertices = np.array([[0, 0, 0], [.01, 0, 0], [0, 1, 0], [0, 0, 1.]])
        faces = np.array([[0, 2, 1], [0, 1, 3], [1, 2, 3], [2, 0, 3]])
        vertex_uvs = np.array([[0, 0], [.0001, 0], [0, .0001], [.0001, .0001]])
        source = model_from_poses([vertices, vertices.copy()], faces, vertex_uvs[faces])
        selected, output_faces, _, report = simplify_shared(source, 2,
            max_displacement_ratio=.025)
        self.assertEqual(len(selected), 4)
        self.assertEqual(len(output_faces), 4)
        self.assertEqual(len({tuple(sorted(face)) for face in output_faces}), 4)
        self.assertGreater(report["rejected_candidates"].get("duplicate_face_full_link", 0), 0)

    def test_repair_requires_pinned_invalid_table_and_preserves_gl_and_frames(self):
        source = grid(3)
        broken = bytearray(source.data)
        struct.pack_into("<H", broken, source.header[13], source.header[6] + 10)
        struct.pack_into("<H", broken, source.header[13] + 6, source.header[7] + 10)
        digest = hashlib.sha256(broken).hexdigest()
        with self.assertRaises(ValueError):
            MD2.read(bytes(broken))
        repaired, report = repair_stale_triangle_table(bytes(broken), expected_sha256=digest)
        np.testing.assert_array_equal(repaired.positions, source.positions)
        np.testing.assert_array_equal(repaired.normals, source.normals)
        np.testing.assert_array_equal(repaired.faces, source.faces)
        np.testing.assert_array_equal(repaired.uvs, source.uvs)
        self.assertEqual(repaired.data[source.header[14]:], source.data[source.header[14]:])
        self.assertEqual(report["invalid_xyz_triangles"], 1)
        self.assertEqual(report["invalid_st_triangles"], 1)
        with self.assertRaisesRegex(ValueError, "source hash"):
            repair_stale_triangle_table(bytes(broken), expected_sha256="0" * 64)
        with self.assertRaisesRegex(ValueError, "demonstrably invalid"):
            repair_stale_triangle_table(source.data, expected_sha256=hashlib.sha256(source.data).hexdigest())

    def test_repair_rejects_missing_or_extra_gl_geometry(self):
        source = grid(3)
        broken = bytearray(source.data)
        struct.pack_into("<H", broken, source.header[13], 999)
        struct.pack_into("<i", broken, source.header[15], 0)
        with self.assertRaises(ValueError):
            repair_stale_triangle_table(bytes(broken), expected_sha256=hashlib.sha256(broken).hexdigest())

    def test_repeated_conversion_is_byte_identical(self):
        source = grid(5)
        outputs = []
        for _ in range(2):
            selected, faces, uvs, _ = simplify_shared(source, 20,
                max_displacement_ratio=.25, max_uv_displacement=.4)
            outputs.append(encode_vertex_subset(source, selected, faces, uvs))
        self.assertEqual(outputs[0], outputs[1])

    def test_production_animated_outputs_preserve_every_pose_and_source_vertex(self):
        manifest_path = ROOT / "tools/assets/platoon-manifest.json"
        if not manifest_path.exists():
            self.skipTest("complete production outputs have not been installed")
        from build_platoon import read_source
        manifest = json.loads(manifest_path.read_text())
        checked = 0
        for entry in manifest["models"]:
            if entry["before"]["frames"] < 2:
                continue
            with self.subTest(model=entry["path"]):
                raw = md2.source_bytes(manifest, "baseq2/" + entry["path"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), entry["input_sha256"])
                source, _ = read_source(raw, entry["path"])
                output = MD2.read((ROOT / "baseq2" / entry["path"]).read_bytes())
                self.assertEqual(output.stats(), entry["after"])
                self.assertEqual(output.names, source.names)
                self.assertEqual(output.header[10], source.header[10])
                self.assertEqual(output.header[4], 40 + output.header[6] * 4)
                np.testing.assert_array_equal(output.scales, source.scales)
                np.testing.assert_array_equal(output.translations, source.translations)
                # Joint animation signatures include ALL quantized positions
                # and normal indices. A match in just frame zero is insufficient.
                def signatures(model):
                    frames = np.stack([np.frombuffer(model.data, dtype=np.uint8,
                        count=model.header[6] * 4,
                        offset=model.header[14] + frame * model.header[4] + 40).reshape(-1, 4)
                        for frame in range(model.header[10])])
                    return [frames[:, vertex].tobytes() for vertex in range(model.header[6])]
                original_signatures = set(signatures(source))
                self.assertTrue(all(value in original_signatures for value in signatures(output)))
                validation = entry["collapse_validation"]
                if validation:
                    self.assertEqual(validation["frames_checked"], source.header[10])
                    self.assertLessEqual(validation["max_cluster_displacement_ratio"],
                                         validation["displacement_limit_ratio"] + 1e-12)
                    self.assertTrue(validation["exact_source_vertex_coordinates_and_normals"])
                checked += 1
        self.assertGreater(checked, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
