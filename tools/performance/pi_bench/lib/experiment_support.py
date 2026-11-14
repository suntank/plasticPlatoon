"""Read-only per-run fingerprints; no fixed map or save assumptions."""
import hashlib
import re
from pathlib import Path
def hashes(root):
 out={}
 for p in sorted(Path(root).rglob('*')):
  if p.is_symlink():raise RuntimeError('Symlink in runtime/save tree: '+str(p))
  if p.is_file():
   h=hashlib.sha256()
   with p.open('rb') as f:
    for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
   out[p.relative_to(root).as_posix()]=h.hexdigest()
 return out

def player_deaths(console_chunk):
 """Recognize this build's ClientObituary lines, including death then respawn."""
 verbs=r"died\.|suicides\.|cratered\.|was |sank |melted\.|does a back flip |blew |found a way out\.|saw |got blasted\.|tried |tripped |killed |should have |ate |almost dodged |couldn't hide |caught |didn't see |feels "
 return re.findall(r'(?m)^PiBench(?: P[234])? (?:'+verbs+r')[^\r\n]*',console_chunk)
