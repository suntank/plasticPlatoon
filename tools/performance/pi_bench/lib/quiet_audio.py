"""Keep the Pi physical PCM muted; leave the game's mixing workload enabled."""
import re,subprocess,time
def ensure_quiet():
 commands=[['amixer','sset','PCM','0%'],['amixer','sset','PCM','mute']];applied=[]
 for command in commands:
  run=subprocess.run(command,text=True,capture_output=True);applied.append(dict(command=command,returncode=run.returncode,stdout=run.stdout,stderr=run.stderr))
  if run.returncode:raise RuntimeError('Could not preserve requested quiet PCM output')
 read=subprocess.run(['amixer','sget','PCM'],text=True,capture_output=True);percent=re.findall(r'\[(\d+)%\]',read.stdout);switches=re.findall(r'\[(on|off)\]',read.stdout)
 passed=read.returncode==0 and bool(percent)and all(int(n)==0 for n in percent)and bool(switches)and all(s=='off'for s in switches)
 if not passed:raise RuntimeError('Requested physical PCM0%/off could not be verified')
 return dict(passed=True,checked_at=time.time(),commands=applied,readonly_query=dict(command=['amixer','sget','PCM'],stdout=read.stdout,stderr=read.stderr,returncode=read.returncode),game_audio_engine_unchanged=True,leave_muted=True)
