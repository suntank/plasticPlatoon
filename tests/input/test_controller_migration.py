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
            (base / 'pak0.pak').symlink_to(ROOT / 'release/baseq2/pak0.pak')
            config = base / 'config.cfg'
            config.write_text('unbindall\nbind SHOULDR_RIGHT "weapnext"\n'
                              'bind TRIG_RIGHT "+attack"\n')

            def launch():
                command = [str(runtime / 'quake2'), '-portable', '-datadir', str(runtime),
                           '+set', 'vid_renderer', 'soft', '+set', 'vid_fullscreen', '0',
                           '+set', 's_initsound', '0', '+bind', 'TRIG_LEFT',
                           '+bind', 'SHOULDR_RIGHT', '+quit']
                result = subprocess.run(command, cwd=runtime,
                    env={**os.environ, 'SDL_VIDEODRIVER': 'dummy', 'SDL_AUDIODRIVER': 'dummy'},
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout)
                return result.stdout

            output = launch()
            self.assertIn('"TRIG_LEFT" = "+ads"', output)
            self.assertIn('"SHOULDR_RIGHT" = "quickgrenade"', output)
            saved = config.read_text()
            self.assertIn('set pp_controller_bindings "1"', saved)
            self.assertIn('bind TRIG_RIGHT "+attack"', saved)
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
            # An existing custom layout is also preserved on first upgrade.
            config.write_text('unbindall\nbind TRIG_LEFT "+moveup"\n'
                              'bind SHOULDR_RIGHT "+moveright"\n')
            output = launch()
            self.assertIn('"TRIG_LEFT" = "+moveup"', output)
            self.assertIn('"SHOULDR_RIGHT" = "+moveright"', output)


if __name__ == '__main__':
    unittest.main()
