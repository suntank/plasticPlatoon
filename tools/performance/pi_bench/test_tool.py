"""Meaningful CLI protection, map override and raw-counter regression checks."""
import contextlib
import copy
import io
import json
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
ASSETS=ROOT/'build/pi-vis-20261112/live-mission/native-assets-host-runtime'
RAW=ROOT/'build/pi-gl-world-20261113/native-results/optimized-data/results/optimized-core'
TOOL=runpy.run_path(str(HERE/'pp-bench'))

class ToolTests(unittest.TestCase):
    def test_cross_machine_resolution_and_software_comparisons_rejected(self):
        check=TOOL['compare_context']
        pc=dict(target='pc',framebuffer='960x960',display_backend='native')
        check(pc,dict(pc))
        check({},dict(target='pi',framebuffer='240x240',display_backend='native'))
        for other in [dict(pc,target='pi'),dict(pc,framebuffer='240x240'),dict(pc,display_backend='headless-software')]:
            with self.assertRaises(ValueError):check(pc,other)

    def test_pc_does_not_control_pi_service_or_global_mixer(self):
        from unittest.mock import patch
        import platform_support
        with patch.object(platform_support.subprocess,'run',side_effect=AssertionError('device command on PC')):
            self.assertFalse(platform_support.shell_active('pc'))
            platform_support.set_shell('pc',False)
            self.assertTrue(platform_support.quiet('pc')['global_mixer_unchanged'])

    def test_death_then_respawn_cannot_hide_in_alive_endpoints(self):
        from experiment_support import player_deaths
        self.assertEqual(len(player_deaths("PiBench died.\nPiBench P2 was machinegunned by PiBench P3\n")),2)
        self.assertEqual(player_deaths("PiBench entered the game\nPiBench P2 entered the game\n"),[])

    def export(self,mapname,*args):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'scene.json'
            subprocess.run([str(HERE/'pp-bench'),'--runtime',str(ASSETS),'--map',mapname,'--quality','normal','--export-scene',str(out),*args],check=True,stdout=subprocess.DEVNULL)
            return json.loads(out.read_text())[0]

    def test_dm_no_god_and_real_team_protection(self):
        s=self.export('pp_sandbox2')
        self.assertEqual(s['settings']['dmflags'],384)
        self.assertEqual(s['require_cvars']['dmflags'],384)
        self.assertFalse(s['prepare_deathmatch']['god'])
        self.assertFalse(any(c.endswith(' god') for p in s['phases'] for c in p['commands']))

    def test_coop_protection_requires_team_flag_too(self):
        s=self.export('pp_sandstorm')
        self.assertEqual(s['settings']['dmflags'],384)
        self.assertFalse(any(c.endswith(' god') for p in s['phases'] for c in p['commands']))

    def test_explicit_legacy_god(self):
        s=self.export('pp_sandstorm','--god')
        self.assertEqual(sum(c.endswith(' god') for p in s['phases'] for c in p.get('commands',[])),4)
        self.assertTrue(self.export('pp_sandbox2','--god')['prepare_deathmatch']['god'])

    def test_generic_dm_uses_real_map_spawns(self):
        s=self.export('pp_sandbox2','--preset','spawn')
        self.assertEqual(len(s['prepare_deathmatch']['poses']),4)
        self.assertEqual(len(set(s['prepare_deathmatch']['poses'])),4)
        self.assertEqual([p['label'] for p in s['phases']],['spawn','four-guns-turning'])

    def test_edited_loose_bsp_supported_without_install(self):
        inventory=TOOL['maps'](ASSETS)
        with tempfile.TemporaryDirectory() as tmp:
            edited=Path(tmp)/'my_experiment.bsp';edited.write_bytes(TOOL['read_map'](inventory['pp_sandbox2']))
            out=Path(tmp)/'plan.json'
            subprocess.run([str(HERE/'pp-bench'),'--runtime',str(ASSETS),'--map-file',str(edited),'--mode','dm','--quality','normal','--export-scene',str(out)],check=True,stdout=subprocess.DEVNULL)
            self.assertEqual(json.loads(out.read_text())[0]['map'],'my_experiment')

    def test_historical_metrics_and_tampered_counter_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp);meta=json.loads((RAW/'metadata.json').read_text())
            # One actual capture is enough for the negative control. Keep its
            # camera/state/provenance metadata, rather than fabricating metrics.
            session=copy.deepcopy(next(s for s in meta['sessions'] if s['map']=='pp_sandbox2'))
            session['phases']=session['phases'][:1];meta['sessions']=[session]
            (target/'metadata.json').write_text(json.dumps(meta))
            import shutil
            shutil.copytree(RAW/session['label'],target/session['label'])
            with contextlib.redirect_stdout(io.StringIO()):self.assertTrue(TOOL['report'](target,{'map':'pp_sandbox2'}))
            r=json.loads((target/'report.json').read_text());self.assertAlmostEqual(r['rows'][0]['fps'],12.128,places=2)
            csv=next((target/session['label']/'saves/baseq2/perf').glob('spawn-frames.csv'))
            import csv as csvlib
            with csv.open() as f:reader=csvlib.DictReader(f);fields=reader.fieldnames;rows=list(reader)
            rows[0]['draws']=str(float(rows[0]['draws'])+1)
            with csv.open('w') as f:w=csvlib.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
            with contextlib.redirect_stdout(io.StringIO()):self.assertFalse(TOOL['report'](target,{'map':'pp_sandbox2'}))

if __name__=='__main__':unittest.main()
