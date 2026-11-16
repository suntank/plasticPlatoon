#!/usr/bin/env python3
"""Cheat-assisted Garden Ghost mission checks in an isolated four-player engine.

This checks mission wiring, real shared weapon pickup and collision, not combat
balance or host FPS.  It reuses the existing original-assets-only runtime and
input helpers; a private read-only probe observes goals, inventory and actors.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from check_endline_runtime import Runtime, digest
from verify_sandkeep import entity_bounds, parse_entities

ROOT = Path(__file__).resolve().parents[2]
NAME = 'pp_garden_infiltration'
sys.path.insert(0, str(ROOT / 'tools/performance'))
from qa_controls import FileControls, compile_controls


PROBE = r'''
#define _GNU_SOURCE
#include "@HEADER@"
#include <link.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int base_cb(struct dl_phdr_info *i,size_t n,void *out) {
 const char *s=strrchr(i->dlpi_name,'/');s=s?s+1:i->dlpi_name;
 if(!strcmp(s,"game.so")){*(uintptr_t*)out=i->dlpi_addr;return 1;}return 0;
}
static uintptr_t sym(uintptr_t b,const char *key) {
 char name[128];snprintf(name,sizeof(name),"PP_COLOR_GAME_%s",key);
 const char *v=getenv(name);return v?b+strtoull(v,NULL,16):0;
}
static void quote(const char *s) {
 fputc('"',stderr);for(const unsigned char *p=(const unsigned char*)(s?s:"");*p;p++) {
  if(*p=='"'||*p=='\\')fputc('\\',stderr);
  if(*p<32)fprintf(stderr,"\\u%04x",*p);else fputc(*p,stderr);
 }fputc('"',stderr);
}
int PP_ColorGameDropshipState(void *raw,int stride,int count,const char *label) {
 uintptr_t b=0;dl_iterate_phdr(base_cb,&b);
 level_locals_t *lev=(void*)sym(b,"level");
 game_locals_t *game=(void*)sym(b,"game");
 gitem_t *items=(void*)sym(b,"itemlist");
 gitem_t *(*find)(const char*)=(void*)sym(b,"FindItem");
 fputs("PP_GARDEN_STATE {\"label\":",stderr);quote(label);
 fprintf(stderr,",\"edict_size\":%d,\"probe_edict_size\":%zu",stride,sizeof(edict_t));
 if(!raw||stride!=(int)sizeof(edict_t)||!lev||!game||!items||!find) {
  fputs(",\"error\":\"probe ABI or symbols unavailable\"}\n",stderr);fflush(stderr);return -1;
 }
 fputs(",\"map\":",stderr);quote(lev->mapname);
 fputs(",\"objective\":",stderr);quote(game->helpmessage1);
 fprintf(stderr,",\"time\":%.3f,\"found_goals\":%d,\"total_goals\":%d,\"intermission\":%.3f,\"ships\":[",lev->time,lev->found_goals,lev->total_goals,lev->intermissiontime);
 int first=1,pistol=0,shotgun=0;
 for(int i=0;i<count;i++) {
  edict_t *e=(void*)((byte*)raw+(size_t)stride*i);
  if(!e->inuse||!e->classname)continue;
  if(!strcmp(e->classname,"monster_soldier_light")&&e->health>0)pistol++;
  if(!strcmp(e->classname,"monster_soldier")&&e->health>0)shotgun++;
  if(strcmp(e->classname,"misc_platoon_dropship"))continue;
  fprintf(stderr,"%s{\"origin\":[%.3f,%.3f,%.3f],\"count\":%d}",first?"":",",e->s.origin[0],e->s.origin[1],e->s.origin[2],e->count);first=0;
 }
 fprintf(stderr,"],\"guards\":{\"pistol\":%d,\"shotgun\":%d},\"players\":[",pistol,shotgun);
 first=1;
 for(int i=1;i<count&&i<=4;i++) {
  edict_t *e=(void*)((byte*)raw+(size_t)stride*i);
  if(!e->inuse||!e->client||!e->client->pers.connected)continue;
  gitem_t *gun=find("Shotgun"),*shells=find("Shells");
  fprintf(stderr,"%s{\"slot\":%d,\"health\":%d,\"flags\":%d,\"movetype\":%d,\"showhelp\":%d,\"origin\":[%.3f,%.3f,%.3f],\"shotgun\":%d,\"shells\":%d,\"weapon\":",first?"":",",i-1,e->health,e->flags,e->movetype,e->client->showhelp,e->s.origin[0],e->s.origin[1],e->s.origin[2],e->client->pers.inventory[gun-items],e->client->pers.inventory[shells-items]);
  quote(e->client->pers.weapon?e->client->pers.weapon->pickup_name:"");fputc('}',stderr);first=0;
 }
 fputs("]}\n",stderr);fflush(stderr);return 1;
}
/* Required by the reused observer dispatch; never called by this test. */
int PP_ColorGameDropshipUse(void *a,int b,int c,void *d,const char *e){return -1;}
'''


class GardenRuntime(Runtime):
    def __init__(self, args):
        super().__init__(args)
        (self.out / 'pp_endline.map').rename(self.out / (NAME + '.map'))
        compiled_source = ROOT / 'build/maps' / NAME / 'runtime-source' / (NAME + '.map')
        if compiled_source.exists():
            import shutil
            shutil.copy2(compiled_source, self.out / 'compiled-source.map')
            self.report['compiled_source_sha256'] = digest(compiled_source)
        (self.base / 'maps/pp_endline.bsp').rename(self.base / 'maps' / (NAME + '.bsp'))
        cfg = self.base / 'endline-qa.cfg'
        text = cfg.read_text().replace('pp_endline', NAME)
        text = text.replace('set maxclients "2"', 'set maxclients "4"')
        text = text.replace('set cl_gun "0"', 'set cl_gun "1"')
        text += '\nunbindall\nset dmflags 384\n'
        cfg.write_text(text)
        (self.out / 'settings.cfg').write_text(text.replace(self.token, 'LOCAL_RCON_TOKEN'))
        self.report.update(map=NAME, note='Isolated host functional smoke, with notarget/god for control; not gameplay balance or a hardware performance measurement.')
        self.report['authored_to_runtime_translation'] = args.coordinate_offset
        source = self.out / 'read-only-probe.c'
        source.write_text(PROBE.replace('@HEADER@', str(ROOT / 'src/game/header/local.h')))
        library, environment = compile_controls(args.runtime, self.out,
                                                extra_sources=(source,), defines=('PP_DROPSHIP_QA',))
        game_symbols = subprocess.check_output(['nm', str(args.runtime / 'baseq2/game.so')], text=True)
        game_symbol = re.search(r'^([0-9a-fA-F]+) [a-zA-Z] game$', game_symbols, re.M)
        if not game_symbol:
            raise RuntimeError('Missing read-only observer symbol: game')
        environment['PP_COLOR_GAME_game'] = game_symbol[1]
        driver = self.out / 'input-driver.so'
        flags = subprocess.check_output(['sdl2-config', '--cflags', '--libs'], text=True).split()
        subprocess.run(['cc', '-std=c11', '-D_DEFAULT_SOURCE', '-DYQ2ARCH="test"',
                        '-DYQ2OSTYPE="test"', '-shared', '-fPIC', '-O2', '-I', str(ROOT),
                        str(ROOT / 'tools/performance/pi_bench/input_driver.c'), '-ldl',
                        *flags, '-o', str(driver)], check=True)
        symbols = subprocess.check_output(['nm', str(args.runtime / 'quake2')], text=True)
        for name, suffix in {'Cbuf_AddText':'CBUF_ADD', 'Cmd_AddCommand':'CMD_ADD',
                             'Cmd_Argv':'CMD_ARGV', 'Cmd_Argc':'CMD_ARGC',
                             'SS_GetSlot':'GET_SLOT', 'SS_SendSlotStringCmdNow':'SEND_SLOT',
                             'cl':'CLIENT', 'SS_IsDeviceConnected':'DEVICE_CONNECTED'}.items():
            found = re.search(r'^([0-9a-fA-F]+) [a-zA-Z] ' + name + '$', symbols, re.M)
            if not found:
                raise RuntimeError('Missing input-helper symbol: ' + name)
            environment['PP_TEST_' + suffix + '_OFFSET'] = found[1]
        self.commands = self.out / 'controls.txt'
        self.commands.touch()
        self.environment = {**environment, 'LD_PRELOAD': str(driver) + ':' + str(library),
                            'PP_COLOR_CONTROLS': str(self.commands)}
        self.report['private_helper_sha256'] = {'input':digest(driver), 'observer':digest(library)}
        self.report['states'] = []
        self.state_serial = 0

    def start(self):
        previous = {key:os.environ.get(key) for key in self.environment}
        try:
            os.environ.update(self.environment)
            super().start()
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        self.controls = FileControls(self.commands, self.out / 'console.log', self.process)
        for slot in range(1, 4):
            for command in ('god', 'notarget'):
                self.run(f'pp_test_slot {slot} {command}', .06)

    def state(self, label):
        self.state_serial += 1
        state = self.controls.record('dropship_state', 'PP_GARDEN_STATE ',
                                     f'{label}-{self.state_serial:04d}')
        self.report['states'].append(state)
        if state.get('error'):
            raise RuntimeError(state['error'])
        return state


def mission(runtime, source):
    entities = parse_entities(source.read_text())
    expected = Counter(e['keys']['classname'] for e in entities
                       if e['keys']['classname'].startswith('monster_'))
    initial = runtime.state('initial')
    runtime.check('Correct mission loaded with four living co-op players',
                  initial['map'] == NAME and len(initial['players']) == 4
                  and all(p['health'] > 0 for p in initial['players']), state=initial)
    runtime.check('Only authored pistol and shotgun guards spawned',
                  set(expected) <= {'monster_soldier_light', 'monster_soldier'}
                  and initial['guards'] == {'pistol':expected['monster_soldier_light'],
                                            'shotgun':expected['monster_soldier']},
                  expected=dict(expected), actual=initial['guards'])
    runtime.check('All four diagnostic players use normal walking with explicit god and notarget',
                  all(p['flags'] & 48 == 48 and p['movetype'] == 4
                      for p in initial['players']))
    runtime.check('Friendly insertion helicopter initially exists', len(initial['ships']) == 1,
                  ships=initial['ships'], server_seconds=initial['time'])
    p0_origin = initial['players'][0]['origin']
    heli = initial['ships'][0]['origin']
    dx, dy = heli[0] - p0_origin[0], heli[1] - p0_origin[1]
    yaw = math.degrees(math.atan2(dy, dx))
    pitch = -math.degrees(math.atan2(heli[2] + 66 - p0_origin[2] - 32, math.hypot(dx, dy)))
    runtime.pose([*p0_origin, pitch, yaw], wait=.1)
    runtime.capture('insertion')
    moved = runtime.until(lambda: next((s for s in [runtime.state('departure-sample')]
                                       if s['ships'] and math.dist(s['ships'][0]['origin'], initial['ships'][0]['origin']) > 12), None),
                          15, 'Insertion helicopter never moved')
    runtime.check('Helicopter performs its departure route', True, observed=moved['ships'])
    departed = runtime.until(lambda: next((s for s in [runtime.state('departed')]
                                          if not s['ships']), None),
                             12, 'Insertion helicopter was not removed at terminal corner')
    runtime.check('Insertion helicopter leaves the level', True, server_seconds=departed['time'])
    runtime.check('Shotgun is absent from starting inventories',
                  all(p['shotgun'] == 0 for p in initial['players']))
    shotgun = next(e['keys'] for e in entities if e['keys']['classname'] == 'weapon_shotgun')
    location = [float(v) + runtime.args.coordinate_offset[i]
                for i, v in enumerate(shotgun['origin'].split())]
    for slot in range(4):
        runtime.pose([*location, 0, 90], slot, wait=.45)
        runtime.run(f'pp_test_slot {slot} use Shotgun', .25)
        state = runtime.state('shotgun-slot-' + str(slot))
        player = next(p for p in state['players'] if p['slot'] == slot)
        runtime.check(f'Player {slot + 1} collects and equips the real midpoint shotgun',
                      player['shotgun'] > 0 and player['shells'] > 0 and player['weapon'] == 'Shotgun',
                      player=player, pickup_origin=location)
        runtime.pose([location[0] + 152, location[1] + slot * 72,
                      location[2] + 8, 0, 90], slot)
    runtime.capture('midpoint_cache_four_players')
    all_armed = runtime.state('all-armed')
    runtime.check('All four players retain shotgun after shared pickup',
                  all(p['shotgun'] > 0 for p in all_armed['players']))

    # Ordinary walking, rather than noclip, must stop at the added sandbox gate.
    rally = next(e for e in entities if e['keys']['classname'] == 'trigger_platoon_extract')
    authored_bounds = entity_bounds(rally)
    xmin, ymin, zmin, xmax, ymax, zmax = [
        value + runtime.args.coordinate_offset[i % 3]
        for i, value in enumerate(authored_bounds)
    ]
    center_x, center_y = (xmin + xmax) / 2, (ymin + ymax) / 2
    runtime.pose([center_x + 16, center_y, zmin + 48, 0, 0], wait=.35)
    runtime.run('pp_test_input 0 forward 1', 1.4)
    runtime.run('pp_test_input 0 forward 0', .2)
    gate = runtime.state('gate-blocked')
    p0 = next(p for p in gate['players'] if p['slot'] == 0)
    runtime.check('Solid sandbox gate blocks ordinary forward movement',
                  center_x + 40 < p0['origin'][0] < xmax + 12
                  and abs(p0['origin'][1] - center_y) < 4,
                  player=p0)
    runtime.capture('closed_sandbox_gate')

    # Three players inside may not complete while their living fourth stays out.
    for slot, y in enumerate((ymin + 70, ymin + 150, ymin + 230)):
        runtime.pose([center_x - 4, y, zmin + 48, 0, 0], slot)
    runtime.pose([xmin - 108, ymax - 100, zmin + 48, 0, 0], 3, wait=.6)
    waiting = runtime.state('squad-incomplete')
    runtime.check('Rally waits for the fourth living player',
                  waiting['found_goals'] == 0 and waiting['total_goals'] == 1,
                  state=waiting)
    runtime.pose([center_x - 4, ymax - 90, zmin + 48, 0, 0], 3, wait=.6)
    complete = runtime.state('squad-complete')
    runtime.check('All four living players complete exactly one goal',
                  complete['found_goals'] == 1 and complete['total_goals'] == 1,
                  state=complete)
    runtime.check('Completion retains this level without intermission',
                  complete['map'] == NAME and complete['intermission'] == 0)
    runtime.capture('squad_holds_outside_sandbox')
    time.sleep(.6)
    repeated = runtime.state('completion-once')
    runtime.check('Holding at the perimeter cannot award the goal twice', repeated['found_goals'] == 1)
    runtime.check('Shared objective confirms the sandbox is reached and remains closed',
                  'Sandbox reached.' in repeated['objective']
                  and 'next operation' in repeated['objective'], objective=repeated['objective'])
    runtime.run('r_hudscale 1', .1)
    runtime.run('scr_gamebird_hud 1', .1)
    runtime.run('pp_test_slot 0 help', .3)
    help_state = runtime.state('help-screen')
    runtime.check('Primary player can open the completed shared objective',
                  next(p for p in help_state['players'] if p['slot'] == 0)['showhelp'] == 1)
    runtime.capture('completed_objective_help')
    runtime.report['limitations'] = [
        'The existing secondary-client parser discards center-print messages. Completion is verified through the shared objective and native goal count; the help screen is captured on player one.',
        'God and notarget isolate mission wiring from combat balance. These host timings are not Pi FPS results.',
    ]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bsp', type=Path, default=ROOT / 'baseq2/maps' / (NAME + '.bsp'))
    p.add_argument('--source', type=Path, default=ROOT / 'maps/source' / (NAME + '.map'))
    p.add_argument('--runtime', type=Path, default=ROOT / 'release')
    p.add_argument('--label', required=True)
    p.add_argument('--output-root', type=Path, default=ROOT / 'build/garden-infiltration-qa')
    p.add_argument('--renderer', choices=('gl1', 'gl3', 'soft'), default='gl1')
    p.add_argument('--display-backend', choices=('xvfb', 'offscreen', 'dummy', 'current'), default='xvfb')
    p.add_argument('--size', default='640x640')
    p.add_argument('--keep-runtime', action='store_true')
    p.add_argument('--coordinate-offset', nargs=3, type=float,
                   help='Authored source to compiled-world translation; defaults to design.json runtime_translation')
    a = p.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', a.label):
        p.error('label must be a fresh simple basename')
    if not a.bsp.is_file():
        p.error('compiled mission BSP is not available yet')
    if a.coordinate_offset is None:
        design = ROOT / 'build/maps' / NAME / 'design.json'
        a.coordinate_offset = json.loads(design.read_text()).get('runtime_translation', [0, 0, 0]) if design.exists() else [0, 0, 0]
    a.players, a.skill, a.farsee, a.egl_device = 4, 1, 0, 1
    runtime = GardenRuntime(a)
    try:
        runtime.start()
        mission(runtime, a.source)
        runtime.report['passed'] = True
    except Exception as error:
        runtime.report['error'] = str(error)
        print(str(error), flush=True)
    finally:
        runtime.close()
    return 0 if runtime.report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
