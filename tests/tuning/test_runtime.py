#!/usr/bin/env python3
"""Exercise the real release's weapon-profile loading from different folders."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]


class TuningRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='pp-tuning-runtime-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.runtime = cls.root / 'game'
        cls.base = cls.runtime / 'baseq2'
        cls.base.mkdir(parents=True)
        cls.outside = cls.root / 'other-folder'
        cls.outside.mkdir()
        cls.artifacts = ROOT / 'build/tuning-qa'
        cls.artifacts.mkdir(parents=True, exist_ok=True)
        for name in ('quake2',):
            shutil.copy2(ROOT / 'release' / name, cls.runtime / name)
        for name in ('game.so', 'plastic-platoon.pk3'):
            shutil.copy2(ROOT / 'release/baseq2' / name, cls.base / name)
        (cls.base / 'pak0.pak').symlink_to(ROOT / 'release/baseq2/pak0.pak')
        shutil.copytree(ROOT / 'release/baseq2/tuning', cls.base / 'tuning')

    def run_game(self, cwd, *, datadir=True, profile_dir=None, rate=35, spread=3):
        command = [str(self.runtime / 'quake2'), '-portable']
        if datadir:
            command += ['-datadir', str(datadir if isinstance(datadir, Path) else self.runtime)]
        command += ['+set', 'dedicated', '1', '+set', 'logfile', '2']
        if profile_dir:
            command += ['+set', 'sv_weapon_profile_dir', str(profile_dir)]
        command += ['+map', 'base1']
        console = self.base / 'qconsole.log'
        console.unlink(missing_ok=True)
        artifact = self.artifacts / (self._testMethodName + '.log')
        with artifact.open('w') as output:
            process = subprocess.Popen(command, cwd=cwd, text=True, stdin=subprocess.PIPE,
                                       stdout=output, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    log = console.read_text(errors='replace') if console.exists() else ''
                    server = log.find('------- server initialization ------')
                    if server >= 0 and '\n------------------------------------' in log[server:]:
                        break
                    self.assertIsNone(process.poll(), artifact.read_text()[-4000:])
                    time.sleep(.03)
                else:
                    self.fail('Server failed to initialize; see ' + str(artifact))
                # A map defers startup commands until a client joins. A dedicated
                # check must send its dump/quit through stdin after map startup.
                process.communicate('sv weapon_dump\nquit\n', timeout=10)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
        log = artifact.read_text()
        self.assertEqual(process.returncode, 0, log[-4000:])
        self.assertNotIn('not found, using defaults', log)
        self.assertRegex(log,
                         rf'M60:\s+Ammo:[^\n]+\s+Damage: 12, RPS: {rate:.1f}, Spread: {spread:.2f}')
        self.assertNotIn('/home/austin/.yq2/', log)
        return log

    def test_launch_from_release_folder(self):
        self.run_game(self.runtime)

    def test_datadir_loads_release_tuning_from_another_folder(self):
        self.run_game(self.outside)

    def test_binary_folder_fallback_without_datadir(self):
        self.run_game(self.outside, datadir=False)

    def test_explicit_custom_profile_directory_still_works(self):
        custom = self.root / 'custom'
        custom.mkdir()
        profile = json.loads((self.base / 'tuning/default.json').read_text())
        profile['weapon_overrides']['M60']['fire_mode']['rate_rps'] = 31
        (custom / 'default.json').write_text(json.dumps(profile))
        self.run_game(self.outside, profile_dir=custom, rate=31)

    def test_selected_datadir_has_priority_over_binary_folder(self):
        data = self.root / 'selected-data'
        (data / 'baseq2/tuning').mkdir(parents=True)
        profile = json.loads((self.base / 'tuning/default.json').read_text())
        profile['weapon_overrides']['M60']['fire_mode']['rate_rps'] = 42
        (data / 'baseq2/tuning/default.json').write_text(json.dumps(profile))
        self.run_game(self.outside, datadir=data, rate=42)


if __name__ == '__main__':
    unittest.main(verbosity=2)
