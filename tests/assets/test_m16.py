#!/usr/bin/env python3
"""Validate the exported M16's budget, all weapon poses, skins and sight alignment."""
import io
from collections import Counter
import json
from pathlib import Path
import sys
import unittest

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/assets"))
import build_m16 as builder
from asset_sources import source_bytes
from md2_assets import MD2, normal_table
from m16_geometry import build_m16


class M16Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets, cls.report = builder.build_assets()
        cls.originals = json.loads(builder.ORIGINALS.read_text())
        cls.meshes = {detail: build_m16(detail) for detail in ("world", "view")}

    def test_checked_outputs_and_manifest_match_rebuild(self):
        for path, expected in self.assets.items():
            with self.subTest(path=path):
                self.assertEqual((ROOT / "baseq2" / path).read_bytes(), expected)
        self.assertEqual(json.loads(builder.MANIFEST.read_text()), self.report)
        inventory = {entry["path"]: entry for entry in self.report["files"]}
        self.assertEqual(set(inventory), set(self.assets))
        for path, data in self.assets.items():
            self.assertEqual(inventory[path]["sha256"], builder.sha(data))
            self.assertEqual(inventory[path]["bytes"], len(data))

    def test_budget_includes_view_arms_and_preserves_single_frame_cache(self):
        expected_frames = {"pickup": 1, "view": 1, "player": 198, "enemy": 475, "enemy_tall": 475}
        for entry in self.report["models"]:
            with self.subTest(path=entry["path"]):
                model = MD2.read(self.assets[entry["path"]])
                self.assertEqual(model.header[10], expected_frames[entry["role"]])
                # The view budget includes two sculpted mitten silhouettes.
                # World meshes retain the original, stricter reduction target.
                self.assertLess(len(model.faces), 900 if entry["role"] == "view"
                                else entry["baseline"]["triangles"] * .5)
                self.assertLess(model.header[6], 1024 if entry["role"] == "view"
                                else entry["baseline"]["position_vertices"])
                self.assertEqual(model.header[4], 40 + model.header[6] * 4)
                self.assertEqual(model.command_triangles, len(model.faces))
                for skin in model.skins:
                    self.assertIn(skin, self.assets)
        view_names = {part["name"] for part in self.meshes["view"]["parts"]}
        world_names = {part["name"] for part in self.meshes["world"]["parts"]}
        self.assertTrue(any(name.startswith("arm_") for name in view_names))
        self.assertTrue(any(name.startswith("hand_") for name in view_names))
        self.assertFalse(any(name.startswith(("arm_", "hand_")) for name in world_names))

    def test_every_player_and_enemy_pose_follows_archived_rigid_motion(self):
        mesh = self.meshes["world"]
        for path, role in builder.MODELS.items():
            if role not in ("player", "enemy"):
                continue
            with self.subTest(path=path):
                original = MD2.read(source_bytes(self.originals, "baseq2/" + path), source_compat=True)
                output = MD2.read(self.assets[path])
                self.assertEqual(output.names, original.names)
                rotations, offsets, errors = builder.rigid_transforms(original)
                self.assertLess(errors.max(), .12)
                matrix, offset, _ = builder.placement(role)
                new_reference = np.asarray(mesh["vertices"]) @ matrix + offset
                expected = np.asarray([new_reference @ r + t for r, t in zip(rotations, offsets)])
                distances = np.linalg.norm(output.positions - expected, axis=2)
                limits = np.linalg.norm(output.scales, axis=1) / 2 + 1e-5
                self.assertTrue(np.all(distances <= limits[:, None]))
                # Validate every interpolated-animation endpoint, not frame zero alone.
                triangles = output.positions[:, output.faces]
                areas = np.linalg.norm(np.cross(triangles[:, :, 1] - triangles[:, :, 0],
                                                triangles[:, :, 2] - triangles[:, :, 0]), axis=2)
                self.assertGreater(areas.min(), 1e-9)

    def test_tall_enemy_keeps_foot_anchored_transform_and_frame_layout(self):
        normal = MD2.read(self.assets["models/monsters/soldier/weapon_machinegun.md2"])
        tall = MD2.read(self.assets["models/monsters/soldier/tall/weapon_machinegun.md2"])
        self.assertEqual(tall.names, normal.names)
        np.testing.assert_array_equal(tall.faces, normal.faces)
        np.testing.assert_array_equal(tall.normals, normal.normals)
        expected = normal.positions * 1.2
        expected[:, :, 2] += 4.8
        np.testing.assert_allclose(tall.positions, expected, atol=8e-6)

    def test_handguard_and_flash_hider_are_closed_from_both_ends(self):
        for detail, mesh in self.meshes.items():
            vertices = np.round(np.asarray(mesh["vertices"]), 7)
            for name in ("handguard", "flash_hider"):
                with self.subTest(detail=detail, part=name):
                    part = next(p for p in mesh["parts"] if p["name"] == name)
                    faces = mesh["faces"][part["first_triangle"]:
                                          part["first_triangle"] + part["triangle_count"]]
                    edges = Counter()
                    for face in faces:
                        points = [tuple(vertices[i]) for i in face]
                        for a, b in zip(points, points[1:] + points[:1]):
                            edges[tuple(sorted((a, b)))] += 1
                    # Weld hard-normal seams geometrically: no boundary edge
                    # may expose the background through either tube end.
                    self.assertTrue(edges)
                    self.assertTrue(all(count == 2 for count in edges.values()),
                                    "open tube surface exposes the background")

    def test_view_sights_and_muzzle_share_reviewed_coordinate_system(self):
        entry = next(item for item in self.report["models"] if item["role"] == "view")
        anchors = entry["anchors_frame0"]
        rear, front, muzzle = (np.array(anchors[key]) for key in ("rear_sight", "front_sight", "muzzle"))
        np.testing.assert_allclose(rear[1:], front[1:], atol=1e-9)
        self.assertGreater(front[0] - rear[0], 30)
        self.assertGreater(muzzle[0], front[0])
        self.assertAlmostEqual(muzzle[0], 56.49812462925911, places=6)
        self.assertAlmostEqual(muzzle[1], -7.95, places=6)
        # Arms must not rescale the rifle or shift its authored muzzle.
        self.assertLess(MD2.read(self.assets[entry["path"]]).positions[0, :, 2].min(), -20)

    def test_winding_normals_and_skin_atlas_are_consistent(self):
        output = MD2.read(self.assets["models/weapons/g_machn/tris.md2"])
        p, f = output.positions[0], output.faces
        geometric = np.cross(p[f[:, 1]] - p[f[:, 0]], p[f[:, 2]] - p[f[:, 0]])
        geometric /= np.linalg.norm(geometric, axis=1)[:, None]
        stored = normal_table()[output.normals[0, f]].mean(axis=1)
        # Quake culls GL_FRONT; the face winding must oppose outward normals.
        self.assertLess(np.median(np.sum(geometric * stored, axis=1)), -.65)
        self.assertTrue(np.all(output.uvs > 0))
        self.assertTrue(np.all(output.uvs < 1))
        for path in builder.TEXTURES:
            with Image.open(io.BytesIO(self.assets[path])) as image:
                self.assertEqual(image.size, (256, 256))
                self.assertEqual(image.mode, "RGB")

    def test_tied_normal_selection_ignores_floating_point_noise(self):
        table = normal_table()
        midpoint = (table[7] + table[8]) / 2
        positions = np.array([[[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]]])
        for noise in (-1e-14, 0., 1e-14):
            directions = np.tile(midpoint + noise * (table[8] - table[7]), (1, 3, 1))
            raw, _ = builder.encode_md2(positions, directions, [[0, 1, 2]],
                                       [[[.1, .1], [.9, .1], [.1, .9]]],
                                       [builder.TEXTURES[0]], ["frame_1"])
            np.testing.assert_array_equal(MD2.read(raw).normals, [[7, 7, 7]])

    def test_runtime_plastic_value_matches_existing_soldier(self):
        # Team-green recoloring preserves V. Compare the pigmented pixels that
        # survive that mask, not black unused areas in the existing body atlas.
        medians = []
        for image in (Image.open(io.BytesIO(self.assets[builder.TEXTURES[2]])),
                      Image.open(ROOT / "baseq2/players/soldier/green.png")):
            with image:
                hsv = np.asarray(image.convert("RGB").convert("HSV"))
                mask = ((hsv[:, :, 0] >= 45) & (hsv[:, :, 0] <= 125) &
                        (hsv[:, :, 1] >= 45) & (hsv[:, :, 2] >= 8))
                medians.append(float(np.median(hsv[:, :, 2][mask])))
        self.assertLessEqual(abs(medians[0] - medians[1]), 3,
                             "M16 plastic would be much brighter than the selected soldier body")


if __name__ == "__main__":
    unittest.main(verbosity=2)
