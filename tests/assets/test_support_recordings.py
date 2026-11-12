import io
import json
from pathlib import Path
import struct
import sys
import unittest
import wave
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/assets'))
from import_support_recordings import run, SOURCE, convert
from build_support_sounds import SOUNDS

class SupportRecordingTests(unittest.TestCase):
    def test_inventory_and_no_regeneration(self):
        report=run(True)
        self.assertEqual(len(report['files']),37)
        for f in report['files']:
            self.assertNotIn(f['target'][6:],SOUNDS)
            with wave.open(str(ROOT/'baseq2'/f['target']),'rb') as w:
                self.assertEqual((w.getnchannels(),w.getsampwidth(),w.getframerate()),(1,2,48000))
                self.assertGreater(w.getnframes(),0)
        self.assertEqual(len(SOUNDS),31)
        self.assertIn('weapons/bfg__x1b.wav',SOUNDS)
    def test_one_shots_exact_and_loops_continuous(self):
        for f in json.loads((SOURCE/'selection.json').read_text()):
            data=(SOURCE/f['source']).read_bytes()
            got=convert(data,f['loop'])
            if not f['loop']: self.assertEqual(got,data)
            else:
                with wave.open(io.BytesIO(got),'rb') as w:
                    s=struct.unpack('<'+'h'*w.getnframes(),w.readframes(w.getnframes()))
                with wave.open(io.BytesIO(data),'rb') as w:
                    original=struct.unpack('<'+'h'*w.getnframes(),w.readframes(w.getnframes()))
                self.assertEqual(len(s),len(original)-1920)
                self.assertEqual(s[-1],original[1919])
                self.assertEqual(s[0],original[1920])
    def test_build_verifies_recordings(self):
        for path in ('Makefile','CMakeLists.txt'):
            self.assertIn('import_support_recordings.py',(ROOT/path).read_text())
