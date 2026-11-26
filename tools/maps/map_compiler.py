#!/usr/bin/env python3
"""Compile and playtest Plastic Platoon maps from the desktop."""

from contextlib import ExitStack
import os
from pathlib import Path
import re
import shlex
import shutil
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
from zipfile import BadZipFile, ZipFile

import gi

gi.require_version('GdkPixbuf', '2.0')
gi.require_version('Gtk', '3.0')
from gi.repository import GdkPixbuf, GLib, Gtk

from build_endline import BASE, LOCAL_TOOL, ROOT, stage_compile_asset
from map_inventory import map_inventory
from package_garden_infiltration import asset_name

APP_ID = 'io.plasticplatoon.MapCompiler'
ICON = ROOT / 'packaging/branding/map-compiler-icon.png'
SOURCE_DIR = ROOT / 'maps/source'
BUILD_DIR = ROOT / 'build/map-compiler'
RELEASE = ROOT / 'release'
PLAYTEST_GAME = 'pp-map-playtest'
OUTPUT_DIR = RELEASE / PLAYTEST_GAME / 'maps'
TEXTURE_ALIASES = {
    '__TB_empty': 'sandkeep/trim',
    'sandbox/bluesky1': 'sandkeep/sky',
}


def prepare_compile_assets(textures, destination):
    """Stage the used materials, including animation frames and packed art."""
    with ExitStack() as stack:
        packages = {}
        for directory in (RELEASE / 'baseq2', BASE):
            for path in sorted(directory.glob('*.pk3')):
                archive = stack.enter_context(ZipFile(path))
                packages.update((name, archive) for name in archive.namelist()
                                if name.startswith('textures/'))

        def read_asset(relative):
            for directory in (BASE, RELEASE / 'baseq2'):
                path = directory / relative
                if path.is_file():
                    return path.read_bytes()
            if relative in packages:
                return packages[relative].read(relative)
            return None

        stage_compile_asset((BASE / 'pics/colormap.pcx').read_bytes(),
                            destination / 'pics/colormap.pcx')
        pending, staged = list(textures), set()
        while pending:
            name = asset_name(pending.pop())
            if name in staged:
                continue
            staged.add(name)
            wal = read_asset(f'textures/{name}.wal')
            if wal is None and name in TEXTURE_ALIASES:
                wal = read_asset(f'textures/{TEXTURE_ALIASES[name]}.wal')
            variants = {'.wal': wal}
            for suffix in ('.png', '.tga'):
                variants[suffix] = read_asset(f'textures/{name}{suffix}')
            if not any(data is not None for data in variants.values()):
                raise ValueError(f'Missing compile texture {name}')
            if wal is not None:
                if len(wal) < 100:
                    raise ValueError(f'Truncated compile texture {name}.wal')
                following, = struct.unpack_from('<32s', wal, 56)
                following = following.split(b'\0', 1)[0].decode('ascii')
                if following:
                    pending.append(following)
            for suffix, data in variants.items():
                if data is not None:
                    stage_compile_asset(data, destination / f'textures/{name}{suffix}')


def compile_map(source, threads, large_bounds, subdiv, ambient, smooth, report):
    tool = os.environ.get('Q2TOOL', str(LOCAL_TOOL) if LOCAL_TOOL.is_file() else 'q2tool')
    tool = shutil.which(os.path.expanduser(tool))
    if not tool:
        raise FileNotFoundError('q2tool was not found. Set Q2TOOL or build ~/q2tools-220.')
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    report(f'Preparing assets for {source.name} from {source.parent}')
    with TemporaryDirectory(prefix='input-', dir=BUILD_DIR) as temporary:
        snapshot = Path(temporary) / source.name
        shutil.copyfile(source, snapshot)
        inventory = map_inventory(snapshot)
        assets = snapshot.parent / 'compile-assets'
        prepare_compile_assets(inventory['textures'], assets)
        command = [
            sys.executable, '-u', str(ROOT / 'tools/performance/compile_map.py'),
            '--source', str(snapshot), '--tool', tool, '--basedir', str(assets),
            '--build-dir', str(BUILD_DIR), '--output-dir', str(OUTPUT_DIR),
            '--profile', 'release', '--threads', str(threads),
            '--rad-subdiv', str(subdiv), '--rad-ambient', str(ambient),
            '--rad-smooth', str(smooth),
        ]
        if large_bounds:
            command.append('--large-bounds')
        report(shlex.join(command))
        with subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, errors='replace') as process:
            for line in process.stdout:
                report(line.rstrip())
            if process.wait():
                raise RuntimeError(f'Compile failed. See {BUILD_DIR / source.stem} for stage logs.')
    return inventory['classes']


def launch_game(map_name, entity_counts):
    launcher = RELEASE / 'play-portable.sh'
    deathmatch = not entity_counts.get('info_player_start') and entity_counts.get('info_player_deathmatch')
    log = BUILD_DIR / map_name / 'game.log'
    command = [
        str(launcher), '+set', 'game', PLAYTEST_GAME,
        '+set', 'coop', '0', '+set', 'deathmatch', '1' if deathmatch else '0',
        '+set', 'singleplayer', '0' if deathmatch else '1', '+map', map_name,
    ]
    with log.open('ab') as output:
        process = subprocess.Popen(command, cwd=RELEASE, stdout=output,
                                   stderr=subprocess.STDOUT, start_new_session=True)
    return process, log


class MapCompiler(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)
        self.window = None
        self.building = False

    def do_activate(self):
        if self.window is None:
            self.create_window()
        self.window.present()

    def create_window(self):
        self.window = Gtk.ApplicationWindow(application=self, title='Plastic Platoon Map Compiler')
        self.window.set_default_size(700, 480)
        self.window.set_icon(GdkPixbuf.Pixbuf.new_from_file_at_scale(str(ICON), 128, 128, True))
        self.window.connect('delete-event', self.close_window)
        self.window.connect('destroy', self.clear_window)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin=16)
        self.window.add(content)
        self.controls = Gtk.Grid(column_spacing=12, row_spacing=8)
        self.controls.set_column_homogeneous(False)
        content.pack_start(self.controls, False, False, 0)

        self.maps = Gtk.ComboBoxText(hexpand=True)
        for path in sorted(SOURCE_DIR.glob('*.map')):
            self.maps.append(str(path), path.name)
        self.maps.connect('changed', self.update_compile_button)
        browse = Gtk.Button(label='Browse…')
        browse.connect('clicked', self.browse)
        self.controls.attach(Gtk.Label(label='Map', xalign=0), 0, 0, 1, 1)
        self.controls.attach(self.maps, 1, 0, 3, 1)
        self.controls.attach(browse, 4, 0, 1, 1)
        self.controls.attach(Gtk.Label(label=str(SOURCE_DIR), xalign=0, selectable=True), 1, 1, 4, 1)

        self.subdiv = self.add_number('RAD subdivision', 256, 8, 1024, 0, 2)
        self.ambient = self.add_number('RAD ambient', 16, 0, 255, 2, 2)
        self.threads = self.add_number('Threads', 8, 1, 256, 0, 3)
        self.angle = self.add_number('Smooth angle (°)', 60, 0, 90, 2, 3, digits=1)

        self.smooth = Gtk.CheckButton(label='Smooth (Phong)', active=True)
        self.smooth.connect('toggled', lambda button: self.angle.set_sensitive(button.get_active()))
        self.controls.attach(self.smooth, 0, 4, 2, 1)
        self.large_bounds = Gtk.CheckButton(label='Large bounds', active=True)
        self.controls.attach(self.large_bounds, 2, 4, 3, 1)
        self.play = Gtk.CheckButton(label='Launch game after compile', active=True)
        self.controls.attach(self.play, 0, 5, 3, 1)
        self.compile_button = Gtk.Button(label='Compile', sensitive=False)
        self.compile_button.get_style_context().add_class('suggested-action')
        self.compile_button.connect('clicked', self.start_compile)
        self.controls.attach(self.compile_button, 4, 5, 1, 1)

        self.status = Gtk.Label(label='Choose a map to compile.', xalign=0)
        content.pack_start(self.status, False, False, 0)
        scroll = Gtk.ScrolledWindow(shadow_type=Gtk.ShadowType.IN)
        self.log = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        scroll.add(self.log)
        content.pack_start(scroll, True, True, 0)
        self.window.show_all()

    def add_number(self, label, initial, minimum, maximum, column, row, digits=0):
        field = Gtk.SpinButton.new_with_range(minimum, maximum, 1)
        field.set_digits(digits)
        field.set_value(initial)
        caption = Gtk.Label(label=label, xalign=0)
        caption.set_mnemonic_widget(field)
        self.controls.attach(caption, column, row, 1, 1)
        self.controls.attach(field, column + 1, row, 1, 1)
        return field

    def browse(self, _button):
        dialog = Gtk.FileChooserNative.new('Choose a map', self.window,
                                           Gtk.FileChooserAction.OPEN, 'Select', 'Cancel')
        dialog.set_current_folder(str(SOURCE_DIR))
        maps = Gtk.FileFilter()
        maps.set_name('Quake II map sources (*.map)')
        maps.add_pattern('*.map')
        dialog.add_filter(maps)
        if dialog.run() == Gtk.ResponseType.ACCEPT:
            path = Path(dialog.get_filename())
            if not self.maps.set_active_id(str(path)):
                self.maps.append(str(path), path.name)
                self.maps.set_active_id(str(path))
        dialog.destroy()

    def update_compile_button(self, _combo):
        self.compile_button.set_sensitive(bool(self.maps.get_active_id()))

    def start_compile(self, _button):
        source = Path(self.maps.get_active_id())
        # A Quake map name is also used in a console command and a MAX_QPATH path.
        if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,53}', source.stem):
            self.status.set_text('Use a map filename with up to 54 letters, digits, dots, hyphens, or underscores.')
            return
        for field in (self.threads, self.subdiv, self.ambient, self.angle):
            field.update()
        settings = (
            self.threads.get_value_as_int(), self.large_bounds.get_active(),
            self.subdiv.get_value_as_int(), self.ambient.get_value_as_int(),
            self.angle.get_value() if self.smooth.get_active() else 0,
        )
        self.log.get_buffer().set_text('')
        self.status.set_text(f'Compiling {source.name}…')
        self.controls.set_sensitive(False)
        self.building = True
        self.hold()
        Thread(target=self.build, args=(source, settings, self.play.get_active()), daemon=True).start()

    def build(self, source, settings, play):
        def report(text):
            GLib.idle_add(self.append_log, text)

        status = 'Compile complete.'
        try:
            entity_counts = compile_map(source, *settings, report=report)
        except (OSError, ValueError, RuntimeError, BadZipFile) as error:
            report(str(error))
            status = 'Compile failed.'
        else:
            if play:
                try:
                    process, log = launch_game(source.stem, entity_counts)
                    report(f'Game log: {log}')
                    status = 'Compile complete. Game started.'
                    GLib.idle_add(self.watch_game, process, log)
                except OSError as error:
                    report(str(error))
                    status = 'Compile complete. Game could not start.'
        GLib.idle_add(self.finish, status)

    def watch_game(self, process, log):
        def check():
            result = process.poll()
            if result is None:
                return GLib.SOURCE_CONTINUE
            if result and self.window is not None:
                self.append_log(f'Game exited with status {result}. See {log}.')
            return GLib.SOURCE_REMOVE

        GLib.timeout_add_seconds(1, check)

    def append_log(self, text):
        buffer = self.log.get_buffer()
        buffer.insert(buffer.get_end_iter(), text + '\n')
        self.log.scroll_to_iter(buffer.get_end_iter(), 0, False, 0, 0)

    def finish(self, status):
        self.status.set_text(status)
        self.controls.set_sensitive(True)
        self.building = False
        if not self.window.get_visible():
            self.window.destroy()
        self.release()

    def close_window(self, window, _event):
        if self.building:
            window.hide()
            return True
        return False

    def clear_window(self, _window):
        self.window = None


if __name__ == '__main__':
    GLib.set_prgname(APP_ID)
    sys.exit(MapCompiler().run(sys.argv))
