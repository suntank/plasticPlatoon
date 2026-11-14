"""Read fresh test-shim registry JSON from stderr, never from RCON reply."""
import hashlib,json,re,time
from pathlib import Path
def fresh_model_query(command,log_path,wait):
 log_path=Path(log_path);offset=len(log_path.read_text(errors='replace'));started=time.monotonic();command('pp_test_models');deadline=started+5
 while time.monotonic()<deadline:
  chunk=log_path.read_text(errors='replace')[offset:]
  for match in re.finditer(r'PP_TEST_MODELS ([^\r\n]+)\r?\n',chunk):
   try:json.loads(match[1])
   except json.JSONDecodeError:continue
   text='PP_TEST_MODELS '+match[1];return text,dict(source='fresh_engine_stderr',log=str(log_path),offset_characters=offset,line_sha256=hashlib.sha256(text.encode()).hexdigest(),elapsed_seconds=time.monotonic()-started)
  wait(.1)
 return '',dict(source='fresh_engine_stderr',log=str(log_path),offset_characters=offset,timeout_seconds=5)
