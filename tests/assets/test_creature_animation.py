#!/usr/bin/env python3
"""Check that creature deaths visibly roll onto their backs and settle quickly."""
from pathlib import Path
import sys
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/assets'))
from md2_assets import MD2


class CreatureAnimationTests(unittest.TestCase):
    def test_death_finishes_upside_down_and_on_the_floor_by_frame_49(self):
        for species in ('ant', 'spider'):
            with self.subTest(species=species):
                model = MD2.read((ROOT / f'baseq2/models/monsters/{species}/tris.md2').read_bytes())
                # The first 180 vertices are the abdomen. Compare its axes
                # before and after the roll, independent of floor translation.
                upright = model.positions[44, :180]
                inverted = model.positions[49, :180]
                upright = upright - upright.mean(axis=0)
                inverted = inverted - inverted.mean(axis=0)
                alignment = (upright * inverted).sum(axis=0) / (
                    np.linalg.norm(upright, axis=0) * np.linalg.norm(inverted, axis=0))
                self.assertGreater(alignment[0], .95)
                self.assertLess(alignment[1], -.95)
                self.assertLess(alignment[2], -.95)
                for frame in range(44, 54):
                    self.assertAlmostEqual(float(model.positions[frame,:,2].min()), -24, delta=.2)
                # The abdomen itself, not just an antenna or toe, meets the
                # floor in the final pose so the creature rests on its back.
                self.assertLessEqual(float(model.positions[49,:180,2].min()), -22)
                # Once rolled over, no late snapping back to the old side pose.
                np.testing.assert_allclose(model.positions[49], model.positions[53], atol=.35)


if __name__ == '__main__':
    unittest.main()
