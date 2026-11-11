#!/usr/bin/env python3
"""Generate material-only enemy/player-held color skins without changing models.

Canonical textures remain untouched, including pickup and player-debris skins.
Runtime entities opt into these variants with their existing skin override.
Only Pillow and the Python standard library are needed by the normal build.
"""
from __future__ import annotations

import argparse
import colorsys
import hashlib
import io
import inspect
import json
import math
from pathlib import Path
import re
import struct
import zipfile

from PIL import Image, ImageChops, ImageDraw, ImageStat, __version__ as PILLOW_VERSION

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'baseq2'
MANIFEST = ROOT / 'tools/assets/color-variants-manifest.json'
REVIEW = ROOT / 'build/color-variants'
SCHEMA = 1
BODY_SOURCE = 'players/soldier/green.png'
BODY_MODELS = ('players/soldier/tris.md2', 'players/soldier/tris_pistol.md2')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def md2_skins(path):
    data = path.read_bytes()
    if len(data) < 68:
        raise ValueError(f'Truncated MD2: {path}')
    header = struct.unpack('<17i', data[:68])
    if header[:2] != (844121161, 8):
        raise ValueError(f'Invalid MD2: {path}')
    return [data[header[11] + i * 64:header[11] + (i + 1) * 64].split(b'\0')[0].decode('ascii')
            for i in range(header[5])]


def canonical_model(name):
    # Taller soldiers have identical UVs and skins, so share registered images.
    return name.replace('models/monsters/soldier/tall/', 'models/monsters/soldier/')


def variant_path(model, color, skin_index=0):
    path = Path(canonical_model(model))
    suffix = f'_{skin_index}' if skin_index else ''
    result = (path.parent / 'colors' / f'{path.stem}_{color}{suffix}.png').as_posix()
    if len(result.encode('ascii')) >= 64:
        raise ValueError(f'Variant exceeds engine image path limit: {result}')
    return result


def supported_palette():
    palette, inputs = {}, {}
    directory = BASE / 'players/soldier'
    for path in sorted(directory.glob('*.png')):
        name = path.stem
        if name.endswith('_i') or not re.fullmatch('[a-z0-9_]+', name):
            continue
        # An icon identifies the selectable skin inventory, not arbitrary art.
        if not any((directory / f'{name}_i{ext}').is_file() for ext in ('.pcx', '.png')):
            continue
        with Image.open(path) as image:
            median = ImageStat.Stat(image.convert('RGB')).median
        hue, saturation, value = colorsys.rgb_to_hsv(*(c / 255 for c in median))
        palette[name] = {'rgb_median': median, 'hue': hue, 'saturation': saturation, 'value': value}
        inputs[path.relative_to(BASE).as_posix()] = sha(path.read_bytes())
    if 'green' not in palette:
        raise ValueError('The required green player fallback skin is missing')
    reference = palette['green']['value']
    for entry in palette.values():
        # Anchored to the selected body pigment, while avoiding clipped white
        # highlights or flattened shadows on the more contrasted weapon art.
        gamma = math.log(max(entry['value'], 1 / 255)) / math.log(reference)
        entry['value_gamma'] = max(.45, min(1.5, gamma))
    return palette, inputs


def tile_mask(size, selected):
    result = Image.new('L', size)
    draw = ImageDraw.Draw(result)
    w, h = size
    for index in selected:
        x, y = index % 4 * w // 4, index // 4 * h // 4
        draw.rectangle((x, y, (index % 4 + 1) * w // 4 - 1,
                        (index // 4 + 1) * h // 4 - 1), fill=255)
    return result


def material_mask(image, source, role):
    """A binary pigment mask; every unselected RGBA pixel remains exact."""
    rgba = image.convert('RGBA')
    hue, saturation, value = rgba.convert('RGB').convert('HSV').split()
    green = hue.point(lambda v: 255 if 45 <= v <= 125 else 0)
    warm = hue.point(lambda v: 255 if v <= 55 else 0)
    colored = saturation.point(lambda v: 255 if v >= 45 else 0)
    visible = value.point(lambda v: 255 if v >= 8 else 0)
    rule = 'green plastic; preserve neutral mechanics and black shadows'
    mask = ImageChops.multiply(green, ImageChops.multiply(colored, visible))

    if source.startswith('models/monsters/plastic_'):
        # Original procedural atlas material IDs: tracks/rubber/ports/lamps/
        # dark mechanics stay contrasting. Helicopter tile 3 is cockpit glass.
        mask = ImageChops.multiply(warm, colored)
        mask = ImageChops.multiply(mask, tile_mask(image.size, set(range(16)) - {2, 3, 7, 11, 12, 13, 15}))
        pale_marking = ImageChops.multiply(saturation.point(lambda v: 255 if v < 90 else 0),
                                           value.point(lambda v: 255 if v > 205 else 0))
        mask = ImageChops.subtract(mask, pale_marking)
        dark_vent = ImageChops.multiply(tile_mask(image.size, {6}), value.point(lambda v: 255 if v < 115 else 0))
        mask = ImageChops.subtract(mask, dark_vent)
        rule = 'painted vehicle plastic; glass, lamps, rubber, tracks, dark mechanics and pale stencils preserved'
    elif source.startswith('models/monsters/ant/'):
        mask = tile_mask(image.size, set(range(16)) - {3})
        rule = 'ant carapace and legs; compound-eye material 3 preserved'
    elif source.startswith('models/monsters/spider/'):
        mask = tile_mask(image.size, set(range(16)) - {2, 3})
        rule = 'spider carapace and legs; fang and eye materials 2/3 preserved'
    elif source.startswith(('models/objects/gibs/ant/', 'models/objects/gibs/spider/')):
        mask = tile_mask(image.size, {i for i in range(16) if i % 6 < 3})
        rule = 'insect shell pigment; exposed wound/flesh shades preserved'
    elif source.startswith('models/objects/gibs/') or source.startswith('models/monsters/soldier/'):
        mask = ImageChops.multiply(warm, ImageChops.multiply(colored, visible))
        rule = 'tan molded plastic; neutral/dark details and contrasting non-plastic hues preserved'
    elif source == 'models/support/plastic_atlas.tga':
        # Grenade casing plus its molded hand/glove, leaving metal pin/lever.
        mask = tile_mask(image.size, {0, 2, 8, 9, 10})
        rule = 'held grenade plastic and molded hand; dark strap and metal lever preserved'
    elif source.startswith('pics/ads_'):
        if Path(source).stem in ('ads_railgun', 'ads_handgrenade'):
            mask = Image.new('L', image.size)
            rule = 'scope overlay has no plastic material; original optics retained'
        else:
            optic = ImageChops.multiply(saturation.point(lambda v: 255 if v >= 160 else 0),
                                       value.point(lambda v: 255 if v >= 180 else 0))
            mask = ImageChops.subtract(mask, optic)
            rule = 'rendered ADS plastic; alpha, neutral optics and bright sight dots retained'
    mask = ImageChops.multiply(mask, rgba.getchannel('A').point(lambda v: 255 if v else 0))
    return mask, rule


def recolor(image, source, role, color, palette):
    original = image.convert('RGBA')
    mask, rule = material_mask(original, source, role)
    hue, saturation, value = original.convert('RGB').convert('HSV').split()
    pigment = palette[color]
    new_hue = Image.new('L', original.size, round(pigment['hue'] * 255))
    if role == 'enemy':
        # Use the same rich pigment for bodies, parts and held weapons. Keeping
        # the source tan saturation made bodies noticeably paler than weapons.
        new_saturation = Image.new('L', original.size, round(pigment['saturation'] * 255))
        new_value = value
    else:
        new_saturation = Image.new('L', original.size, round(pigment['saturation'] * 255))
        gamma = pigment['value_gamma']
        new_value = value.point([round(255 * (v / 255) ** gamma) for v in range(256)])
    painted = Image.merge('HSV', (new_hue, new_saturation, new_value)).convert('RGB')
    output = Image.composite(painted, original.convert('RGB'), mask).convert('RGBA')
    output.putalpha(original.getchannel('A'))
    return output, mask, rule


def body_material_mask(image):
    """The body atlas includes green plastic in its deepest authored shadows."""
    rgba = image.convert('RGBA')
    hue, saturation, _ = rgba.convert('RGB').convert('HSV').split()
    green = hue.point(lambda v: 255 if 45 <= v <= 125 else 0)
    colored = saturation.point(lambda v: 255 if v >= 45 else 0)
    visible = rgba.getchannel('A').point(lambda v: 255 if v else 0)
    return ImageChops.multiply(green, ImageChops.multiply(colored, visible))


def recolor_body(image, color, palette):
    """Apply the existing player weapon pigment and value LUT to body plastic."""
    original = image.convert('RGBA')
    mask = body_material_mask(original)
    pigment = palette[color]
    value = original.convert('RGB').convert('HSV').getchannel('V')
    value = value.point([round(255 * (v / 255) ** pigment['value_gamma']) for v in range(256)])
    hue = Image.new('L', original.size, round(pigment['hue'] * 255))
    saturation = Image.new('L', original.size, round(pigment['saturation'] * 255))
    painted = Image.merge('HSV', (hue, saturation, value)).convert('RGB')
    output = Image.composite(painted, original.convert('RGB'), mask).convert('RGBA')
    output.putalpha(original.getchannel('A'))
    return output, mask, 'body plastic including deep shadows; same weapon pigment/value curve; neutral accents preserved'


def body_inventory():
    entries = []
    with Image.open(BASE / BODY_SOURCE) as source:
        dimensions = list(source.size)
    for name in BODY_MODELS:
        path = BASE / name
        raw = path.read_bytes()
        header = struct.unpack_from('<17i', raw)
        if list(header[2:4]) != dimensions:
            raise ValueError(f'Player body atlas layout differs: {name}')
        entries.append({'model': name, 'model_sha256': sha(raw),
                        'skins': md2_skins(path), 'skin_coordinate_dimensions': dimensions})
    if entries[0]['skins'] != entries[1]['skins']:
        raise ValueError('Soldier body model variants must share the same atlas')
    return entries


def inventory():
    models = []
    for directory, role in (('models/monsters', 'enemy'), ('models/objects/gibs', 'enemy'),
                            ('models/objects/debris1', 'enemy'), ('models/objects/debris2', 'enemy'),
                            ('players/soldier', 'player'), ('models/weapons', 'player')):
        for path in sorted((BASE / directory).rglob('*.md2')):
            name = path.relative_to(BASE).as_posix()
            if role == 'player':
                if directory == 'models/weapons' and not path.parent.name.startswith('v_'):
                    continue
                if directory == 'players/soldier' and path.name != 'weapon.md2' and not path.name.startswith('w_'):
                    continue
            skins = md2_skins(path)
            if not skins:
                raise ValueError(f'Colorable model has no skin: {name}')
            for source in skins:
                if not (BASE / source).is_file():
                    raise ValueError(f'Missing skin source: {name} -> {source}')
            models.append({'model': name, 'role': role, 'skins': skins})
    return models


def archive_coverage(models):
    """Every bundled enemy mesh must resolve to a loose canonical color source."""
    available = {entry['model']: entry for entry in models if entry['role'] == 'enemy'}
    coverage = []
    for path in sorted(BASE.glob('operation-*.pk3')):
        entries = []
        with zipfile.ZipFile(path) as archive:
            for name in sorted(archive.namelist()):
                if not name.endswith('.md2') or not name.startswith(('models/monsters/', 'models/objects/gibs/', 'models/objects/debris')):
                    continue
                if name not in available:
                    raise ValueError(f'Bundled enemy lacks a canonical color source: {path.name}:{name}')
                raw = archive.read(name)
                header = struct.unpack('<17i', raw[:68])
                skins = [raw[header[11] + i * 64:header[11] + (i + 1) * 64].split(b'\0')[0].decode('ascii')
                         for i in range(header[5])]
                if skins != available[name]['skins']:
                    raise ValueError(f'Bundled enemy skin layout differs: {path.name}:{name}')
                entries.append({'model': name, 'sha256': sha(raw), 'skins': skins})
        if entries:
            coverage.append({'archive': path.name, 'models': entries})
    return coverage


def png_bytes(image):
    output = io.BytesIO()
    image.save(output, format='PNG', compress_level=9)
    return output.getvalue()


def algorithm_hash():
    # Inventory/manifest maintenance need not re-encode full-HD overlays; every
    # pixel-producing recipe and palette transform is still an exact cache key.
    functions = (supported_palette, tile_mask, material_mask, recolor, png_bytes)
    return sha('\n'.join(inspect.getsource(function) for function in functions).encode())


def body_algorithm_hash():
    # Body-only changes reuse all unchanged weapon/enemy/HD-overlay encodings.
    return sha((algorithm_hash() + '\n' + '\n'.join(inspect.getsource(function)
                for function in (body_material_mask, recolor_body))).encode())


def generate():
    palette, palette_inputs = supported_palette()
    models = inventory()
    manifest = {'schema': SCHEMA, 'generator_sha256': sha(Path(__file__).read_bytes()),
                'algorithm_sha256': algorithm_hash(),
                'body_algorithm_sha256': body_algorithm_hash(),
                'tools': {'Pillow': PILLOW_VERSION}, 'palette_inputs': palette_inputs,
                'palette': palette, 'fallback': 'green', 'models': [], 'overlays': [], 'files': [],
                'bodies': {'source': BODY_SOURCE, 'models': body_inventory(), 'variants': {}},
                'bundled_enemy_coverage': archive_coverage(models)}
    outputs, cache = {}, {}
    previous = json.loads(MANIFEST.read_text()) if MANIFEST.is_file() else {}
    reusable = {}
    if (previous.get('algorithm_sha256') == manifest['algorithm_sha256'] and
            previous.get('palette') == palette):
        reusable = {(entry['source'], entry['role'], entry['color']): entry for entry in previous['files']
                    if entry['role'] != 'player_body' or
                    previous.get('body_algorithm_sha256') == manifest['body_algorithm_sha256']}

    def variant(source, role, color, destination):
        key = source, role, color
        if key not in cache:
            raw = (BASE / source).read_bytes()
            old = reusable.get(key)
            if old and old['source_sha256'] == sha(raw):
                candidate = BASE / old['path']
                if candidate.is_file():
                    data = candidate.read_bytes()
                    if sha(data) == old['sha256']:
                        cache[key] = data, {k: v for k, v in old.items() if k != 'path'}
        if key not in cache:
            with Image.open(io.BytesIO(raw)) as image:
                if role == 'player_body':
                    output, mask, rule = recolor_body(image, color, palette)
                else:
                    output, mask, rule = recolor(image, source, role, color, palette)
                data = png_bytes(output)
                metadata = {'source': source, 'source_sha256': sha(raw), 'role': role,
                            'color': color, 'size': list(output.size), 'mask_sha256': sha(mask.tobytes()),
                            'plastic_pixels': mask.histogram()[255], 'mask_rule': rule,
                            'sha256': sha(data), 'bytes': len(data)}
            cache[key] = data, metadata
        data, metadata = cache[key]
        entry = dict(metadata, path=destination)
        if destination in outputs and outputs[destination][0] != data:
            raise ValueError(f'Conflicting variant output: {destination}')
        outputs[destination] = data, entry

    for model in models:
        colors = ['red'] if model['role'] == 'enemy' else sorted(palette)
        entry = dict(model, model_sha256=sha((BASE / model['model']).read_bytes()), variants={})
        for color in colors:
            paths = []
            # Player overrides select one material skin; enemy pain skins keep
            # their original per-index image, including future distinct art.
            sources = model['skins'] if model['role'] == 'enemy' else model['skins'][:1]
            for index, source in enumerate(sources):
                path = variant_path(model['model'], color, index)
                variant(source, model['role'], color, path)
                paths.append(path)
            entry['variants'][color] = paths
        manifest['models'].append(entry)

    for path in sorted((BASE / 'pics').glob('ads_*.png')):
        print(f'Color variants: {path.name}', flush=True)
        source = path.relative_to(BASE).as_posix()
        entry = {'source': source, 'variants': {}}
        for color in sorted(palette):
            destination = f'pics/colors/{path.stem}_{color}.png'
            variant(source, 'player', color, destination)
            entry['variants'][color] = destination
        manifest['overlays'].append(entry)

    for color in sorted(palette):
        destination = f'players/soldier/colors/body_{color}.png'
        variant(BODY_SOURCE, 'player_body', color, destination)
        manifest['bodies']['variants'][color] = destination

    for destination, (data, metadata) in sorted(outputs.items()):
        target = BASE / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_file() or target.read_bytes() != data:
            target.write_bytes(data)
        manifest['files'].append(metadata)
    if MANIFEST.is_file():
        old = json.loads(MANIFEST.read_text())
        for entry in old.get('files', []):
            name = entry['path']
            if name not in outputs and '/colors/' in name and '..' not in Path(name).parts:
                (BASE / name).unlink(missing_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Generated {len(outputs)} color skins for {len(models)} models, '
          f'{len(manifest["overlays"])} ADS overlays and {len(palette)} player body palettes')
    return manifest


def verify():
    manifest = json.loads(MANIFEST.read_text())
    if manifest['schema'] != SCHEMA or manifest['generator_sha256'] != sha(Path(__file__).read_bytes()):
        raise ValueError('Color generator changed; regenerate the variants')
    if manifest['algorithm_sha256'] != algorithm_hash():
        raise ValueError('Color pixel recipe changed; regenerate the variants')
    if manifest['body_algorithm_sha256'] != body_algorithm_hash():
        raise ValueError('Player body pixel recipe changed; regenerate the variants')
    palette, palette_inputs = supported_palette()
    if manifest['palette'] != palette or manifest['palette_inputs'] != palette_inputs:
        raise ValueError('Selectable player palette changed; regenerate the variants')
    if manifest['bodies']['source'] != BODY_SOURCE or manifest['bodies']['models'] != body_inventory():
        raise ValueError('Player body source/model layout changed; regenerate the variants')
    if manifest['bodies']['variants'] != {color: f'players/soldier/colors/body_{color}.png' for color in sorted(palette)}:
        raise ValueError('Player body palette inventory changed; regenerate the variants')
    actual = inventory()
    expected = [{key: entry[key] for key in ('model', 'role', 'skins')} for entry in manifest['models']]
    if actual != expected:
        raise ValueError('Colorable model inventory changed; regenerate the variants')
    if archive_coverage(actual) != manifest['bundled_enemy_coverage']:
        raise ValueError('Bundled enemy coverage changed; regenerate the variants')
    for entry in manifest['models']:
        if sha((BASE / entry['model']).read_bytes()) != entry['model_sha256']:
            raise ValueError(f'Model changed: {entry["model"]}')
    sources = {}
    for entry in manifest['files']:
        source, output = BASE / entry['source'], BASE / entry['path']
        if entry['source'] not in sources:
            sources[entry['source']] = source.read_bytes()
        if sha(sources[entry['source']]) != entry['source_sha256']:
            raise ValueError(f'Color source changed: {source}')
        data = output.read_bytes()
        if sha(data) != entry['sha256'] or len(data) != entry['bytes']:
            raise ValueError(f'Variant differs: {output}')
        with Image.open(io.BytesIO(sources[entry['source']])) as original, Image.open(io.BytesIO(data)) as painted:
            original, painted = original.convert('RGBA'), painted.convert('RGBA')
            if original.size != painted.size or list(painted.size) != entry['size']:
                raise ValueError(f'Texture dimensions changed: {output}')
            if original.getchannel('A').tobytes() != painted.getchannel('A').tobytes():
                raise ValueError(f'Transparency changed: {output}')
            if entry['role'] == 'player_body':
                mask = body_material_mask(original)
            else:
                mask, _ = material_mask(original, entry['source'], entry['role'])
            difference = ImageChops.difference(original.convert('RGB'), painted.convert('RGB'))
            protected = ImageChops.invert(mask)
            if ImageChops.multiply(difference, Image.merge('RGB', (protected, protected, protected))).getbbox():
                raise ValueError(f'Contrasting detail changed: {output}')
    print(f'Verified {len(manifest["files"])} material variants: hashes, dimensions, alpha and protected details')
    return manifest


def review(manifest):
    REVIEW.mkdir(parents=True, exist_ok=True)
    entries, seen = [], set()
    for entry in manifest['files']:
        if entry['color'] != 'red' or (entry['source'], entry['role']) in seen:
            continue
        seen.add((entry['source'], entry['role']))
        entries.append(entry)
    tile, height = 160, 190
    canvas = Image.new('RGB', (tile * 8, ((len(entries) + 3) // 4) * height), '#26262a')
    draw = ImageDraw.Draw(canvas)
    for index, entry in enumerate(entries):
        x, y = index % 4 * tile * 2, index // 4 * height
        for offset, name in ((0, entry['source']), (tile, entry['path'])):
            with Image.open(BASE / name) as image:
                image = image.convert('RGBA')
                image.thumbnail((tile - 8, tile - 8))
                canvas.paste(image, (x + offset, y), image)
        label = f'{entry["role"]}: {entry["source"]}'
        for line in range(0, len(label), 47):
            draw.text((x + 2, y + tile + line // 47 * 10), label[line:line + 47], fill='white')
    destination = REVIEW / 'red-material-review.png'
    canvas.save(destination)
    print(f'Review: {destination}')
    canvas = Image.new('RGB', (1600, ((len(manifest['palette']) + 4) // 5) * 190), '#26262a')
    draw = ImageDraw.Draw(canvas)
    for index, (color, path) in enumerate(manifest['bodies']['variants'].items()):
        x, y = index % 5 * 320, index // 5 * 190
        for offset, name in ((0, f'players/soldier/{color}.png'), (160, path)):
            with Image.open(BASE / name) as image:
                image = image.convert('RGBA')
                image.thumbnail((152, 152))
                canvas.paste(image, (x + offset, y + 18), image)
        draw.text((x + 2, y + 2), f'{color}: original / weapon-matched body', fill='white')
    destination = REVIEW / 'player-body-review.png'
    canvas.save(destination)
    print(f'Review: {destination}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--review', action='store_true')
    args = parser.parse_args()
    manifest = verify() if args.verify else generate()
    if args.review:
        review(manifest)


if __name__ == '__main__':
    main()
