#!/usr/bin/env python3
"""Launch the real client with isolated configs to check controller migration."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class ControllerMigrationTest(unittest.TestCase):
    def test_saved_bindings_and_later_customization(self):
        with tempfile.TemporaryDirectory(prefix='pp-controller-test-') as folder:
            runtime = Path(folder)
            base = runtime / 'baseq2'
            base.mkdir()
            for name in ('quake2', 'ref_soft.so'):
                shutil.copy2(ROOT / 'release' / name, runtime / name)
            (base / 'plastic-platoon.pk3').symlink_to(ROOT / 'baseq2/plastic-platoon.pk3')
            config = base / 'config.cfg'
            config.write_text('unbindall\nbind SHOULDR_RIGHT "weapnext"\n'
                              'bind TRIG_RIGHT "+attack"\n')

            def launch():
                command = [str(runtime / 'quake2'), '-portable', '-datadir', str(runtime),
                           '+set', 'vid_renderer', 'soft', '+set', 'vid_fullscreen', '0',
                           '+set', 's_initsound', '0', '+bind', 'TRIG_LEFT',
                           '+bind', 'SHOULDR_RIGHT', '+bind', 'TRIG_RIGHT',
                           '+bind', 'BTN_SOUTH', '+bind', 'BTN_BACK', '+quit']
                result = subprocess.run(command, cwd=runtime,
                    env={**os.environ, 'SDL_VIDEODRIVER': 'dummy', 'SDL_AUDIODRIVER': 'dummy'},
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout)
                return result.stdout

            output = launch()
            self.assertIn('"TRIG_LEFT" = "+ads"', output)
            self.assertIn('"SHOULDR_RIGHT" = "quickgrenade"', output)
            saved = config.read_text()
            self.assertIn('set pp_controller_bindings "2"', saved)
            self.assertIn('bind TRIG_RIGHT "+attack"', saved)
            for key, command in {
                'TRIG_RIGHT': '+attack', 'BTN_SOUTH': '+moveup',
                'BTN_EAST': '+movedown', 'BTN_WEST': '+use',
                'BTN_NORTH': 'quickgrenade', 'SHOULDR_LEFT': 'weapprev',
                'STICK_LEFT': '+speed', 'DP_UP': 'invuse', 'DP_DOWN': 'inven',
                'DP_LEFT': 'weapprev', 'DP_RIGHT': 'weapnext', 'BTN_BACK': 'score',
            }.items():
                self.assertIn(f'bind {key} "{command}"', saved)
            # Normal shutdown/restart retains the upgraded bindings.
            output = launch()
            self.assertIn('"TRIG_LEFT" = "+ads"', output)
            self.assertIn('"SHOULDR_RIGHT" = "quickgrenade"', output)
            # Later remaps and intentional unbinds are not overwritten.
            config.write_text(config.read_text().replace('bind TRIG_LEFT "+ads"\n', '')
                              .replace('bind SHOULDR_RIGHT "quickgrenade"',
                                       'bind SHOULDR_RIGHT "weapnext"'))
            output = launch()
            self.assertNotIn('"TRIG_LEFT" = "+ads"', output)
            self.assertIn('"SHOULDR_RIGHT" = "weapnext"', output)
            # Version 2 must not refill deliberate unbinds after its first upgrade.
            config.write_text(config.read_text().replace('bind BTN_SOUTH "+moveup"\n', '')
                              .replace('bind TRIG_RIGHT "+attack"', 'bind TRIG_RIGHT "+use"'))
            output = launch()
            self.assertNotIn('"BTN_SOUTH" = "+moveup"', output)
            self.assertIn('"TRIG_RIGHT" = "+use"', output)
            # Existing v1 users get the missing controls without reviving an
            # intentionally unbound v1 ADS button or overwriting custom fire.
            config.write_text('unbindall\nset pp_controller_bindings "1"\n'
                              'bind TRIG_RIGHT "+use"\n')
            output = launch()
            self.assertIn('"BTN_SOUTH" = "+moveup"', output)
            self.assertIn('"BTN_BACK" = "score"', output)
            self.assertIn('"TRIG_RIGHT" = "+use"', output)
            self.assertNotIn('"TRIG_LEFT" = "+ads"', output)
            # An existing custom layout is also preserved on first upgrade.
            config.write_text('unbindall\nbind TRIG_LEFT "+moveup"\n'
                              'bind SHOULDR_RIGHT "+moveright"\n')
            output = launch()
            self.assertIn('"TRIG_LEFT" = "+moveup"', output)
            self.assertIn('"SHOULDR_RIGHT" = "+moveright"', output)


if __name__ == '__main__':
    unittest.main()
