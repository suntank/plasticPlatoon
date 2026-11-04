#!/usr/bin/env python3
"""Capture remaining approved runtime art and sounds before retiring home overrides."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import struct
import zipfile

from import_soldier_sounds import mono_wav

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'tools/assets/portable-assets-manifest.json'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def repair_boss_skin_paths(data):
    """Replace exporter workstation paths without altering geometry or animation."""
    if len(data) < 68:
        raise ValueError('truncated boss model')
    h = struct.unpack_from('<17i', data)
    if h[:2] != (844121161, 8) or not 1 <= h[5] <= 32 or h[11] < 68 or h[11] + h[5]*64 > len(data):
        raise ValueError('invalid boss model skin table')
    skin = b'models/monsters/boss2/skin.png'.ljust(64, b'\0')
    output = bytearray(data)
    output[h[11]:h[11]+h[5]*64] = skin * h[5]
    return bytes(output)


def find_folder(user, folder):
    for root in (user / 'baseq2', user / 'baseq2/baseq2', user):
        if (root / folder).is_dir():
            return root / folder
    raise ValueError(f'no {folder} sources found under {user}')


def import_assets(user):
    from md2_assets import resize_texture

    destination = ROOT / 'baseq2'
    records = []

    def install(name, original, output=None, conversion='unchanged bytes'):
        output = original if output is None else output
        path = destination / name
        if path.exists() and path.read_bytes() != output:
            raise ValueError(f'refusing to replace an existing release asset: {name}')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(output)
        records.append(dict(path=name, source_sha256=sha(original), sha256=sha(output),
                            bytes=len(output), conversion=conversion))

    pics = find_folder(user, 'pics')
    for path in sorted(pics.glob('*.png')):
        if re.fullmatch(r'(a_|i_|w_|ads_)[a-z0-9_]+\.png', path.name):
            install('pics/' + path.name, path.read_bytes())

    models = find_folder(user, 'models') / 'monsters/boss2'
    for name in ('tris.md2', 'propeller.md2'):
        original = (models / name).read_bytes()
        install('models/monsters/boss2/' + name, original, repair_boss_skin_paths(original),
                'Exporter skin slots repaired; all other model bytes unchanged')
    original = (models / 'skin.png').read_bytes()
    install('models/monsters/boss2/skin.png', original, resize_texture(original, 256),
            'Lanczos resize to the 256-pixel world texture budget')

    sounds = find_folder(user, 'sound')
    effective = {'sound/' + p.relative_to(sounds).as_posix(): p.read_bytes()
                 for p in sorted(sounds.rglob('*.wav')) if 'powerful_gun_firing' not in p.name}
    archive = sounds.parent / 'sound.zip'
    with zipfile.ZipFile(archive) as package:
        # User archives take priority over loose files, matching the engine.
        for name in package.namelist():
            if name.startswith('sound/') and name.endswith('.wav') and '..' not in Path(name).parts:
                effective[name] = package.read(name)
    source_copy = ROOT / 'tools/assets/sources/player-sounds.zip'
    source_copy.parent.mkdir(parents=True, exist_ok=True)
    source_copy.write_bytes(archive.read_bytes())
    for name, original in sorted(effective.items()):
        path = destination / name
        output, conversion = original, 'unchanged bytes'
        if name.startswith('sound/bosshovr/'):
            output = mono_wav(original)[0]
            conversion = 'Spatial mono PCM16; original sample rate and duration retained'
        elif path.exists() and path.read_bytes() != original:
            output = mono_wav(original)[0]
            if output != path.read_bytes():
                raise ValueError(f'unknown existing sound conflict: {name}')
            conversion = 'Previously approved spatial mono conversion retained'
        install(name, original, output, conversion)

    # Freeze the three existing playable sandboxes and their custom materials.
    # Stock Quake II maps/textures remain in the user's original PAKs.
    release = ROOT / 'release/baseq2'
    textures = set()
    for name in ('pp_sandbox1', 'pp_sandbox2', 'pp_sandbox_coop1'):
        data = (release / 'maps' / (name + '.bsp')).read_bytes()
        if data[:4] != b'IBSP' or struct.unpack_from('<i', data, 4)[0] != 38:
            raise ValueError(f'unsupported sandbox BSP: {name}')
        offset, length = struct.unpack_from('<ii', data, 8 + 5*8)
        if length % 76 or offset < 160 or offset + length > len(data):
            raise ValueError(f'invalid sandbox texture table: {name}')
        for pos in range(offset, offset + length, 76):
            texture = data[pos+40:pos+72].split(b'\0')[0].decode('ascii')
            if re.fullmatch(r'sandbox/[a-z0-9_]+', texture):
                textures.add(texture)
        install('maps/' + name + '.bsp', data)
    for texture in sorted(textures):
        for suffix in ('.wal', '.png', '.tga', '.jpg'):
            name = 'textures/' + texture + suffix
            if (release / name).is_file():
                install(name, (release / name).read_bytes())
    for side in ('bk', 'dn', 'ft', 'lf', 'rt', 'up'):
        name = 'env/bluesky1' + side + '.png'
        install(name, (release / name).read_bytes())

    report = dict(schema=1, source='Audited local runtime art and sound.zip',
                  original_sound_archive=dict(path=str(source_copy.relative_to(ROOT)),
                                              sha256=sha(source_copy.read_bytes())),
                  files=records,
                  excluded=['Editor/source PNG with ChatGPT filename',
                            'Unreferenced powerful_gun_firing source recording',
                            'Python conversion scripts and .bak files'])
    MANIFEST.write_text(json.dumps(report, indent=2) + '\n')
    return report


def verify():
    report = json.loads(MANIFEST.read_text())
    for entry in report['files']:
        data = (ROOT / 'baseq2' / entry['path']).read_bytes()
        if sha(data) != entry['sha256'] or len(data) != entry['bytes']:
            raise ValueError(f'portable asset changed: {entry["path"]}')
    archive = report['original_sound_archive']
    if sha((ROOT / archive['path']).read_bytes()) != archive['sha256']:
        raise ValueError('original sound source archive changed')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user-root', type=Path, default=Path.home() / '.yq2')
    parser.add_argument('--verify', action='store_true', help='verify recorded outputs without using home files')
    args = parser.parse_args()
    report = verify() if args.verify else import_assets(args.user_root)
    print(f'{"Verified" if args.verify else "Imported"} {len(report["files"])} portable asset paths.')
