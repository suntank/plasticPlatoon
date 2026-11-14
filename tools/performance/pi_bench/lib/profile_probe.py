"""Read bounded fresh private-profile stderr, avoiding large UDP RCON replies."""
import hashlib,time
from pathlib import Path

def fresh_dump(path,label,offset_bytes,wait,timeout=6):
 path=Path(path);begin='PP_PICKUP_PROFILE_BEGIN '+label;end='PP_PICKUP_PROFILE_END '+label;deadline=time.monotonic()+timeout
 while time.monotonic()<deadline:
  with path.open('rb')as stream:
   stream.seek(offset_bytes);raw=stream.read(4*1024*1024+1)
  if len(raw)>4*1024*1024:raise RuntimeError('Fresh pickup profile exceeds bounded4MiB transport')
  lines=raw.decode(errors='replace').splitlines()
  if begin in lines:
   first=lines.index(begin)
   if end in lines[first+1:]:
    last=lines.index(end,first+1);chosen=[line for line in lines[first:last+1]if line.startswith('PP_PICKUP_PROFILE_')];text='\n'.join(chosen)+'\n'
    return text,dict(source='fresh_engine_stderr',offset_bytes=offset_bytes,fresh_chunk_bytes=len(raw),profile_sha256=hashlib.sha256(text.encode()).hexdigest(),begin=begin,end=end)
  wait(.1)
 raise RuntimeError('No complete fresh pickup profiler stderr dump')
