"""Private file-driven controls shared by isolated visual capture tools."""
from pathlib import Path
import json
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]


def compile_controls(source, output, extra_sources=(), defines=()):
    library = output / 'controls.so'
    flags = subprocess.check_output(['pkg-config', '--cflags', 'sdl2'], text=True).split()
    subprocess.run(['cc', '-shared', '-fPIC', '-O2', '-D_DEFAULT_SOURCE',
                    '-DYQ2ARCH="test"', '-DYQ2OSTYPE="test"', *flags,
                    *('-D' + value for value in defines),
                    str(ROOT / 'tests/input/color_variants_runtime.c'),
                    str(ROOT / 'tests/input/color_variants_game.c'),
                    *(str(path) for path in extra_sources),
                    '-ldl', '-o', str(library)], check=True)
    environment = {}
    groups = [('PP_COLOR_', source / 'quake2',
               ['cl', 'cls', 'svs', 'ge', 'maxclients', 'Cmd_TokenizeString',
                'Info_SetValueForKey', 'SS_GetSlot', 'Cvar_Set', 'Cbuf_AddText',
                'CL_GetModelADSBlend', 'pp_viewmodel_recoil', 'R_RegisterModel', 're']),
              ('PP_COLOR_GAME_', source / 'baseq2/game.so',
               ['FindItem', 'ChangeWeapon', 'itemlist', 'gi', 'level'])]
    if 'PP_BOSS_QA' in defines:
        groups[1][2].extend(['T_Damage', 'boss2_move_attack_rocket'])
    if 'PP_ADS_RECOIL_QA' in defines:
        groups[0][2].extend(['ss_state','pp_viewmodel_muzzle_seq'])
    for prefix, path, names in groups:
        symbols = subprocess.check_output(['nm', str(path)], text=True)
        for name in names:
            found = re.search(r'^([0-9a-fA-F]+) [a-zA-Z] ' + name + r'$', symbols, re.M)
            if not found:
                raise RuntimeError('Missing QA symbol: ' + name)
            environment[prefix + name] = found[1]
    return library, environment


class FileControls:
    def __init__(self, path, log, process):
        self.path, self.log, self.process = path, log, process
        self.serial = 0

    def action(self, command):
        with self.path.open('a') as handle:
            handle.write(command + '\n')

    def console(self, command):
        self.action('console ' + command)

    def record(self, command, marker, label=None, timeout=30):
        self.serial += 1
        label = label or ('qa-' + str(self.serial))
        self.action(command + ' ' + label)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for line in self.log.read_text(errors='replace').splitlines():
                if marker not in line:
                    continue
                try:
                    item = json.loads(line.split(marker, 1)[1])
                except json.JSONDecodeError:
                    continue
                if item.get('label') == label:
                    return item
            if self.process.poll() is not None:
                raise RuntimeError('Engine exited before ' + label)
            time.sleep(.04)
        raise RuntimeError('Timed out waiting for ' + label)

    def state(self, label=None):
        return self.record('state', 'PP_COLOR_STATE ', label)
