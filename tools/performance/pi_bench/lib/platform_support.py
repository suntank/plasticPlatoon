"""Keep device controls confined to the Pi; desktop tests use dummy audio."""
from pathlib import Path
import platform
import subprocess
from quiet_audio import ensure_quiet

def is_pi():
    path=Path('/proc/device-tree/model')
    return path.exists() and 'Raspberry Pi Zero 2 W' in path.read_text()

def shell_active(target):
    return target=='pi' and subprocess.run(['sudo','-n','systemctl','is-active','--quiet','gbshell.service']).returncode==0

def set_shell(target, active):
    if target=='pi':subprocess.run(['sudo','-n','systemctl','start' if active else 'stop','gbshell.service'],check=True)

def quiet(target):
    if target=='pi':return ensure_quiet()
    return dict(passed=True,method='SDL_AUDIODRIVER=dummy in test process',global_mixer_unchanged=True,game_audio_engine_unchanged=True)

def device_name(target):
    return Path('/proc/device-tree/model').read_text().strip('\0') if target=='pi' else platform.platform()+' '+platform.machine()
