#!/usr/bin/env python3
"""Material recolors keep geometry, alpha, accents and unrelated asset bytes."""
import importlib.util
import json
from pathlib import Path
import unittest

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('color_variants', ROOT / 'tools/assets/build_color_variants.py')
colors = importlib.util.module_from_spec(spec)
spec.loader.exec_module(colors)


class MaterialColorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.palette, _ = colors.supported_palette()

    def test_all_selectable_colors_and_green_fallback(self):
        self.assertTrue({'green', 'blue', 'pink', 'red', 'tan', 'orange', 'purple', 'gray', 'white'} <= set(self.palette))
        self.assertIn('skin', self.palette)
        self.assertNotEqual(self.palette['skin']['rgb_median'], self.palette['green']['rgb_median'])

    def test_alpha_dimensions_and_nonplastic_details_are_exact(self):
        image = Image.new('RGBA', (5, 1))
        image.putdata([(0, 40, 0, 255), (0, 80, 0, 63), (23, 23, 23, 255),
                       (20, 40, 180, 255), (0, 60, 0, 0)])
        painted, mask, _ = colors.recolor(image, 'models/weapons/v_machn/skin.png', 'player', 'red', self.palette)
        self.assertEqual(image.size, painted.size)
        self.assertEqual(image.getchannel('A').tobytes(), painted.getchannel('A').tobytes())
        self.assertGreater(painted.getpixel((0, 0))[0], painted.getpixel((0, 0))[1])
        for x in (2, 3, 4):
            self.assertEqual(image.getpixel((x, 0)), painted.getpixel((x, 0)))
            self.assertEqual(mask.getpixel((x, 0)), 0)

    def test_highlights_and_shadows_remain_ordered_for_every_player_color(self):
        image = Image.new('RGBA', (4, 1))
        image.putdata([(0, v, 0, 255) for v in (20, 40, 80, 160)])
        for color in self.palette:
            painted, _, _ = colors.recolor(image, 'models/weapons/v_machn/skin.png', 'player', color, self.palette)
            values = [max(pixel[:3]) for pixel in painted.getdata()]
            self.assertEqual(values, sorted(values), color)
            self.assertEqual(len(set(values)), 4, color)

    def test_body_deep_shadows_use_weapon_pigment_and_preserve_accents(self):
        image = Image.new('RGBA', (5, 1))
        image.putdata([(0, 3, 0, 255), (0, 64, 0, 63), (23, 23, 23, 255),
                       (20, 40, 180, 255), (0, 60, 0, 0)])
        for color in self.palette:
            painted, mask, _ = colors.recolor_body(image, color, self.palette)
            expected, _, _ = colors.recolor(image, 'models/weapons/v_machn/skin.png', 'player', color, self.palette)
            self.assertEqual(painted.size, image.size)
            self.assertEqual(painted.getchannel('A').tobytes(), image.getchannel('A').tobytes())
            self.assertEqual(painted.getpixel((1, 0)), expected.getpixel((1, 0)), color)
            self.assertEqual(mask.getpixel((0, 0)), 255, color)
            for x in (2, 3, 4):
                self.assertEqual(image.getpixel((x, 0)), painted.getpixel((x, 0)), color)
        red, _, _ = colors.recolor_body(image, 'red', self.palette)
        self.assertEqual(red.getpixel((0, 0)), (6, 0, 0, 255))

    def test_every_body_palette_matches_the_existing_weapon_recipe(self):
        image = Image.new('RGBA', (4, 1))
        image.putdata([(0, v, 0, 255) for v in (8, 20, 43, 160)])
        for color in self.palette:
            body, _, _ = colors.recolor_body(image, color, self.palette)
            weapon, _, _ = colors.recolor(image, 'models/weapons/v_machn/skin.png', 'player', color, self.palette)
            self.assertEqual(body.tobytes(), weapon.tobytes(), color)
            values = [max(pixel[:3]) for pixel in body.getdata()]
            self.assertEqual(values, sorted(set(values)), color)
            if color in ('gray', 'white'):
                self.assertTrue(all(r == g == b for r, g, b, _ in body.getdata()), color)

    def test_body_manifest_shares_original_uvs_and_covers_every_selectable_color(self):
        manifest = json.loads(colors.MANIFEST.read_text())
        bodies = manifest['bodies']
        self.assertEqual(bodies['source'], 'players/soldier/green.png')
        self.assertEqual(bodies['models'], colors.body_inventory())
        self.assertEqual([model['model'] for model in bodies['models']], list(colors.BODY_MODELS))
        self.assertEqual(set(bodies['variants']), set(self.palette))
        for color, path in bodies['variants'].items():
            self.assertEqual(path, f'players/soldier/colors/body_{color}.png')
            entry = next(item for item in manifest['files'] if item['path'] == path)
            self.assertEqual(entry['source'], bodies['source'])
            self.assertEqual(entry['role'], 'player_body')
            self.assertEqual(entry['source_sha256'], manifest['palette_inputs'][bodies['source']])
            self.assertEqual(entry['size'], [256, 256])

    def test_enemy_values_and_vehicle_contrasting_materials(self):
        source = 'models/monsters/plastic_helicopter/tan.png'
        with Image.open(ROOT / 'baseq2' / source) as image:
            original = image.convert('RGBA')
            painted, mask, _ = colors.recolor(original, source, 'enemy', 'red', self.palette)
        for tile in (2, 3, 7, 11, 12, 13, 15):
            box = (tile % 4 * 64, tile // 4 * 64, tile % 4 * 64 + 64, tile // 4 * 64 + 64)
            self.assertIsNone(ImageChops.difference(original.crop(box).convert('RGB'), painted.crop(box).convert('RGB')).getbbox())
        self.assertGreater(mask.histogram()[255], 20000)
        for before, after in zip(original.getdata(), painted.getdata()):
            self.assertEqual(max(before[:3]), max(after[:3]))

    def test_enemy_bodies_parts_and_weapons_share_rich_red_pigment(self):
        for source in ('models/monsters/soldier/skin.png',
                       'models/monsters/plastic_helicopter/tan.png',
                       'models/objects/gibs/ant/skin.png',
                       'models/weapons/v_machn/skin.png'):
            with Image.open(ROOT / 'baseq2' / source) as image:
                original = image.convert('RGBA')
                painted, mask, _ = colors.recolor(original, source, 'enemy', 'red', self.palette)
            selected = 0
            for before, after, plastic in zip(original.getdata(), painted.getdata(), mask.getdata()):
                if not plastic:
                    self.assertEqual(before, after)
                    continue
                selected += 1
                self.assertEqual(after[:3], (max(before[:3]), 0, 0), source)
                self.assertEqual(before[3], after[3])
            self.assertGreater(selected, 0, source)

    def test_insect_eyes_fangs_and_exposed_gib_flesh_remain_distinct(self):
        for source, preserved in (
                ('models/monsters/ant/skin.png', (3,)),
                ('models/monsters/spider/skin.png', (2, 3)),
                ('models/objects/gibs/ant/skin.png', (3, 4, 5, 9, 10, 11, 15))):
            with Image.open(ROOT / 'baseq2' / source) as image:
                original = image.convert('RGBA')
                painted, _, _ = colors.recolor(original, source, 'enemy', 'red', self.palette)
            for tile in preserved:
                box = (tile % 4 * 64, tile // 4 * 64, tile % 4 * 64 + 64, tile // 4 * 64 + 64)
                self.assertIsNone(ImageChops.difference(original.crop(box).convert('RGB'), painted.crop(box).convert('RGB')).getbbox(), (source, tile))

    def test_manifest_contract_model_geometry_and_pickup_separation(self):
        manifest = json.loads(colors.MANIFEST.read_text())
        self.assertEqual(manifest['fallback'], 'green')
        self.assertEqual(len(manifest['overlays']), 11)
        for entry in manifest['models']:
            self.assertEqual(entry['model_sha256'], colors.sha((colors.BASE / entry['model']).read_bytes()))
            expected = {'red'} if entry['role'] == 'enemy' else set(self.palette)
            self.assertEqual(set(entry['variants']), expected)
            self.assertFalse(any(source.endswith('/skin_pickup.png') for source in entry['skins']))
            for color, paths in entry['variants'].items():
                for path in paths:
                    self.assertIn('/colors/', path)
                    self.assertLess(len(path), 64)
                    self.assertTrue((colors.BASE / path).is_file(), path)
        boss = next(entry for entry in manifest['models'] if entry['model'] == 'models/monsters/boss2/tris.md2')
        self.assertEqual(len(boss['variants']['red']), 2)
        self.assertTrue(boss['variants']['red'][1].endswith('_red_1.png'))
        for entry in manifest['files']:
            self.assertNotEqual(entry['source'], entry['path'])
            self.assertEqual(entry['source_sha256'], colors.sha((colors.BASE / entry['source']).read_bytes()))
        # Base player gib overrides remain their original green images, never
        # an input/output chosen by the enemy material generator.
        self.assertFalse(any(entry['source'].endswith('/player.png') for entry in manifest['files']))

    def test_canonical_tall_models_share_images_and_bundled_enemies_are_covered(self):
        manifest = json.loads(colors.MANIFEST.read_text())
        for entry in manifest['models']:
            if '/soldier/tall/' in entry['model']:
                self.assertNotIn('/tall/', entry['variants']['red'][0])
        self.assertEqual(colors.archive_coverage(colors.inventory()), manifest['bundled_enemy_coverage'])
        self.assertGreaterEqual(sum(len(entry['models']) for entry in manifest['bundled_enemy_coverage']), 11)

    def test_rebuilding_representative_outputs_reproduces_exact_bytes(self):
        manifest = json.loads(colors.MANIFEST.read_text())
        selected = (
            ('models/monsters/soldier/skin.png', 'enemy', 'red'),
            ('models/weapons/v_machn/skin.png', 'player', 'white'),
            ('models/monsters/plastic_helicopter/tan.png', 'enemy', 'red'),
            ('pics/ads_machinegun.png', 'player', 'blue'),
            ('players/soldier/green.png', 'player_body', 'red'),
            ('players/soldier/green.png', 'player_body', 'white'))
        for source, role, color in selected:
            entry = next(item for item in manifest['files']
                         if (item['source'], item['role'], item['color']) == (source, role, color))
            with Image.open(colors.BASE / source) as image:
                if role == 'player_body':
                    painted, _, _ = colors.recolor_body(image, color, self.palette)
                else:
                    painted, _, _ = colors.recolor(image, source, role, color, self.palette)
            self.assertEqual(colors.sha(colors.png_bytes(painted)), entry['sha256'], (source, color))


if __name__ == '__main__':
    unittest.main()
