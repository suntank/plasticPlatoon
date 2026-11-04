#!/usr/bin/env python3
"""Check the shipped heavy tank with the engine's one-sided MD2 convention."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/assets"))
from md2_assets import MD2, normal_table, raster


def oriented_corners(vertices, coordinates):
    """Match triangles up to rotation, while preserving winding and UV seams."""
    rotation = -int(np.argmin(vertices))
    return (tuple(int(vertex) for vertex in np.roll(vertices, rotation)),
            np.roll(coordinates, rotation, axis=0))


class HeavyTankTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models = {
            part: MD2.read((ROOT / "baseq2/models/monsters/plastic_tank" /
                            f"{part}.md2").read_bytes())
            for part in ("hull", "turret")
        }

    def test_every_exported_triangle_uses_engine_front_face_winding(self):
        # GL1 and GL3 cull GL_FRONT. MD2 surface winding therefore points into
        # the model, opposite its outward normals used for lighting. Check the
        # actual quantized vertices, rather than only the generator geometry.
        for part, model in self.models.items():
            with self.subTest(part=part):
                triangles = model.positions[0][model.faces]
                cross = np.cross(triangles[:, 1] - triangles[:, 0],
                                 triangles[:, 2] - triangles[:, 0])
                lighting = normal_table()[model.normals[0]][model.faces].mean(axis=1)
                length = np.linalg.norm(cross, axis=1) * np.linalg.norm(lighting, axis=1)
                self.assertTrue(np.all(length > 0), "Degenerate triangle or lighting normal")
                cosine = np.einsum("ij,ij->i", cross, lighting) / length
                self.assertTrue(np.all(cosine < -.5),
                                f"{part}: {np.count_nonzero(cosine >= -.5)} faces "
                                "would expose their backs with engine culling")

    def test_triangle_table_and_gl_commands_preserve_oriented_uv_corners(self):
        # MD2.read already validates every GL strip/fan index and triangle's
        # winding against the triangle table. Also check the corresponding UV
        # corners: reversing indices alone must not mirror the tank's stencils.
        for part, model in self.models.items():
            with self.subTest(part=part):
                table = np.frombuffer(model.data, dtype="<u2",
                                      count=model.header[8] * 6,
                                      offset=model.header[13]).reshape(-1, 6)
                st = np.frombuffer(model.data, dtype="<i2",
                                   count=model.header[7] * 2,
                                   offset=model.header[12]).reshape(-1, 2)
                expected = dict(oriented_corners(row[:3], st[row[3:]])
                                for row in table)
                self.assertEqual(len(expected), len(table))
                # The integer software-renderer ST table rounds the GL UVs to
                # texel centers. Float32 GL coordinates can fall on either side
                # of a rounding tie, so allow half a texel plus float precision.
                gl_st = model.uvs * model.header[2:4] - .5
                actual = dict(oriented_corners(face, coords)
                              for face, coords in zip(model.faces, gl_st))
                self.assertEqual(actual.keys(), expected.keys())
                for vertices, coords in actual.items():
                    np.testing.assert_allclose(coords, expected[vertices],
                                               atol=.50001, rtol=0)
                self.assertEqual(model.command_triangles, model.header[8])

    def test_one_sided_review_hides_an_inverted_surface(self):
        # A camera on +X sees the outside of this outward-lit +X surface only
        # when its MD2 triangle winds toward -X. The previous two-sided review
        # rendered either winding and concealed the exported model defect.
        positions = np.array([[[0., -1., -1.], [0., 0., 1.], [0., 1., -1.]]])
        coords = np.array([[[0., 0.], [.5, 1.], [1., 0.]]])
        normal = np.argmax(normal_table() @ np.array([1., 0., 0.]))
        outside = replace(self.models["hull"], positions=positions,
                          faces=np.array([[0, 1, 2]]), uvs=coords,
                          normals=np.full((1, 3), normal, dtype=np.uint8))
        inside = replace(outside, faces=outside.faces[:, ::-1],
                         uvs=outside.uvs[:, ::-1])
        texture = Image.new("RGB", (2, 2), "white")
        options = dict(angle=0, size=64, framing=(np.zeros(3), 2), elevation=0)
        _, visible = raster(outside, texture, **options, cull_front=True)
        _, hidden = raster(inside, texture, **options, cull_front=True)
        _, two_sided = raster(inside, texture, **options)
        self.assertGreater(np.count_nonzero(visible), 100)
        self.assertFalse(hidden.any())
        np.testing.assert_array_equal(two_sided, visible)

    def test_detail_surfaces_do_not_share_depth_after_md2_quantization(self):
        # Small authored offsets can collapse to the same byte-quantized MD2
        # plane. Test the actual stored geometry at each detail's interior.
        for part, material, expected, axis in (("hull", 12, 4, 0),
                                               ("turret", 11, 2, 0),
                                               ("hull", 6, 4, 2)):
            model = self.models[part]
            projected = [i for i in range(3) if i != axis]
            triangles = model.positions[0][model.faces]
            tiles = np.floor(model.uvs.mean(axis=1) * 4).astype(int)
            detail_faces = np.flatnonzero(tiles[:, 1] * 4 + tiles[:, 0] == material)
            self.assertEqual(len(detail_faces), expected)
            for index in detail_faces:
                triangle = triangles[index]
                self.assertLess(np.ptp(triangle[:, axis]), 1e-5)
                point = triangle[:, projected].mean(axis=0)
                plane = triangle[0, axis]
                covering = []
                for other_index, other in enumerate(triangles):
                    if np.max(np.abs(other[:, axis] - plane)) > 1e-5:
                        continue
                    edges = (other[1:][:, projected] - other[0, projected]).T
                    if abs(np.linalg.det(edges)) < 1e-8:
                        continue
                    u, v = np.linalg.solve(edges, point - other[0, projected])
                    if u >= -1e-6 and v >= -1e-6 and u + v <= 1 + 1e-6:
                        covering.append(other_index)
                self.assertEqual(covering, [index],
                                 f"{part} detail {index} shares its depth plane: {covering}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
