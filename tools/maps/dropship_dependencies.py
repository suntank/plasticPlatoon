"""Exact dedicated friendly transport dependencies for mission packagers."""
from pathlib import Path
import struct


MODELS = ('models/vehicles/platoon_dropship/body.md2',
          'models/vehicles/platoon_dropship/main_rotor.md2')


def dropship_files(base):
    """Collect the dedicated body, rotor and their validated MD2 skin paths."""
    files = {name: base / name for name in MODELS}
    for name in MODELS:
        raw = files[name].read_bytes()
        if len(raw) < 68:
            raise ValueError('Short dropship MD2: ' + name)
        header = struct.unpack_from('<17i', raw)
        if (header[:2] != (844121161, 8) or not 0 < header[5] <= 32
                or header[11] < 68 or header[11] + 64 * header[5] > header[16]
                or header[16] > len(raw)):
            raise ValueError('Invalid dropship skin table: ' + name)
        for index in range(header[5]):
            start = header[11] + 64 * index
            skin = raw[start:start + 64].split(b'\0')[0].decode('ascii')
            path = Path(skin)
            if (not skin or '\\' in skin or path.is_absolute()
                    or any(part in ('', '.', '..') for part in skin.split('/'))
                    or not path.as_posix().startswith('models/vehicles/platoon_dropship/')):
                raise ValueError('Unexpected dropship skin: ' + skin)
            files[skin] = base / skin
    return files
