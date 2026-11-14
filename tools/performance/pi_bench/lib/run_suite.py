#!/usr/bin/env python3
"""Run an isolated, bounded hardware split-screen suite on the Game Bird Pi."""
import argparse,csv,hashlib,json,os,re,shutil,signal,socket,subprocess,sys,time,zipfile
from pathlib import Path
from content_identity import content_identity
import input_isolation
from model_probe import fresh_model_query
from profile_probe import fresh_dump as fresh_pickup_dump
from platform_support import quiet,shell_active,set_shell,device_name
from experiment_support import hashes,player_deaths
import scene_controls
import prelaunch_memory

def textcmd(*args):
 try:p=subprocess.run(args,text=True,capture_output=True);return p.stdout.strip() or p.stderr.strip()
 except FileNotFoundError:return ''
def sample(pid):
 out={'time':time.time()}
 for name,path in [('mem','/proc/meminfo'),('vm','/proc/vmstat'),('status',f'/proc/{pid}/status')]:
  try:out[name]=Path(path).read_text()
  except OSError:pass
 for name,args in [('temp',['vcgencmd','measure_temp']),('throttled',['vcgencmd','get_throttled'])]:out[name]=textcmd(*args)
 try:out['cpu_khz']=int(Path('/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq').read_text());out['proc_stat']=Path(f'/proc/{pid}/stat').read_text()
 except OSError:pass
 return out

def resource_window(before, after, policy):
 def procstat(sample):
  try:
   fields=sample['proc_stat'].rsplit(') ',1)[1].split()
   return int(fields[19]),int(fields[9])
  except (KeyError,IndexError,ValueError):return None,None
 def rss(sample):
  found=re.search(r'^VmRSS:\s+(\d+)',sample.get('status',''),re.M)
  return int(found[1]) if found else None
 identity_a,maj_a=procstat(before);identity_b,maj_b=procstat(after)
 rss_a,rss_b=rss(before),rss(after)
 match=re.search(r'0x([0-9a-fA-F]+)',after.get('throttled',''))
 bits=int(match[1],16)&15 if match else None
 delta=maj_b-maj_a if identity_a is not None and identity_a==identity_b and maj_a is not None and maj_b>=maj_a else None
 rss_delta=abs(rss_b-rss_a)/max(rss_a,rss_b,1) if rss_a is not None and rss_b is not None else None
 checks=dict(same_process=identity_a is not None and identity_a==identity_b,
  no_own_major_faults=delta==policy.get('own_major_faults',0),
  no_current_throttle=bits==policy.get('current_throttle_bits',0),
  rss_stable=rss_delta is not None and rss_delta<=policy.get('rss_relative_delta_max',.05))
 return dict(passed=all(checks.values()),checks=checks,process_major_fault_delta=delta,
  rss_relative_delta=rss_delta,current_throttle_bits=bits,before=before,after=after)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--plan',type=Path,required=True);ap.add_argument('--shim',type=Path,required=True);ap.add_argument('--runtime-source',type=Path,required=True);ap.add_argument('--saves',type=Path,required=True);ap.add_argument('--map-file',type=Path);ap.add_argument('--addon',type=Path);ap.add_argument('--target',choices=['pi','pc'],default='pi');ap.add_argument('--size',default='240x240');a=ap.parse_args()
 width,height=map(int,a.size.split('x'))
 out=a.output;out.mkdir(parents=True,exist_ok=False)
 package=a.runtime_source.resolve();real_save=a.saves.resolve()
 assert subprocess.run(['pgrep','-x','quake2'],capture_output=True).returncode!=0,'Close the game before starting a benchmark'
 before=hashes(real_save);installed=hashes(package);source=package
 stage=out/'runtime';shutil.copytree(source,stage)
 plan=json.loads(a.plan.read_text());shutil.copy2(a.plan,out/'plan.json')
 if a.addon:shutil.copy2(a.addon,stage/'baseq2'/a.addon.name)
 if a.map_file:
  assert len({s['map'] for s in plan})==1
  target=stage/'baseq2/maps'/(plan[0]['map']+'.bsp');target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a.map_file,target)
 variant={'runtime_cvars':{}};prepared_activation=None
 active=shell_active(a.target)
 stage_before=hashes(stage)
 content_before=content_identity(stage,stage_before)
 preparation_release=prelaunch_memory.release()
 meta={'started':time.time(),'package_hashes':installed,'runtime_source':str(source),'runtime_hashes':stage_before,'save_hashes_before':before,'system':textcmd('uname','-a'),'device':device_name(a.target),'target':a.target,'framebuffer':a.size,'initial':sample(os.getpid()),'clock_ticks':os.sysconf('SC_CLK_TCK'),'input_driver_sha256':hashlib.sha256(a.shim.read_bytes()).hexdigest() if a.shim else None,'sessions':[]}
 meta['content_identity']=content_before
 meta['experiment']='Current runtime and maps fingerprinted afresh for this run; no historical asset or save pins.'
 (out/'metadata.json').write_text(json.dumps(meta,indent=2))
 proc=None
 def terminate(*_):raise KeyboardInterrupt()
 signal.signal(signal.SIGTERM,terminate)
 try:
  set_shell(a.target,False)
  for session in plan:
   label=session['label'];folder=out/label;base=folder/'saves/baseq2';base.mkdir(parents=True)
   if a.map_file:
    override=base/'maps'/(session['map']+'.bsp');override.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a.map_file,override)
   token=os.urandom(16).hex()
   with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
   def rcon(command):
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:
     s.settimeout(.8);s.sendto(b'\xff'*4+b'rcon '+token.encode()+b' '+command.encode()+b'\n\0',('127.0.0.1',port));parts=[]
     while True:
      try:parts.append(s.recv(65535)[4:].decode(errors='replace'));s.settimeout(.03)
      except socket.timeout:return ''.join(parts)
   settings=dict(rcon_password=token,cheats=1,logfile=2,name='PiBench',con_notifytime=0,skill=1,allow_download=0,r_vsync=0,vid_maxfps=1000,cl_async=1,cl_maxfps=60,s_initsound=1,s_openal=0,r_perf_gpu=0,cl_perf_frames=0,cl_perf_quit=0,cl_perf_screenshot=0)
   settings.update(session.get('settings',{}))
   if a.target=='pc':
    settings.update(vid_fullscreen=0,vid_renderer='gl1',r_mode=-1,r_customwidth=width,r_customheight=height)
   settings.update(variant.get('runtime_cvars',{}))
   if a.map_file:settings['fs_debug']=1
   cfg=''.join(f'set {k} "{v}"\n' for k,v in settings.items())
   cfg+=input_isolation.config()
   cfg+=f'cl_bench_local {session["players"]} {session["map"]}\n'
   if session.get('dm'):cfg+='set coop 0\nset deathmatch 1\nset singleplayer 0\n'
   (base/'test.cfg').write_text(cfg)
   env=dict(os.environ,GAMEBIRD_GAME_DIR=str(stage),GAMEBIRD_SAVE_DIR=str(folder/'saves'),PLASTIC_PLATOON_RENDERER=session.get('renderer','gl1'))
   if a.target=='pc':
    env['SDL_AUDIODRIVER']='dummy'
    if env.get('SDL_VIDEODRIVER')=='KMSDRM':env.pop('SDL_VIDEODRIVER')
   if a.shim:
    env['LD_PRELOAD']=str(a.shim.resolve())
    symbols={n:v for v,_,n in re.findall(r'^([0-9a-fA-F]+) ([a-zA-Z]) (\S+)$',textcmd('nm',str(stage/'quake2')),re.M)}
    for n,k in {'Cbuf_AddText':'CBUF_ADD','Cmd_AddCommand':'CMD_ADD','Cmd_Argv':'CMD_ARGV','Cmd_Argc':'CMD_ARGC','SS_GetSlot':'GET_SLOT','SS_SendSlotStringCmdNow':'SEND_SLOT','cl':'CLIENT','SS_IsDeviceConnected':'DEVICE_CONNECTED'}.items():env['PP_TEST_'+k+'_OFFSET']=symbols[n]
    renderer_symbols={n:v for v,_,n in re.findall(r'^([0-9a-fA-F]+) ([a-zA-Z]) (\S+)$',textcmd('nm',str(stage/'ref_gl1.so')),re.M)}
    for n,k in {'mod_known':'GL1_MODELS','mod_numknown':'GL1_NUM_MODELS'}.items():env['PP_TEST_'+k+'_OFFSET']=renderer_symbols[n]
   if a.target=='pc':
    command=[str(stage/'quake2'),'-datadir',str(stage),'-cfgdir',os.path.relpath(folder/'saves',Path.home()),'+set','vid_renderer','gl1','+set','vid_fullscreen','0','+set','r_mode','-1','+set','r_customwidth',str(width),'+set','r_customheight',str(height),'+set','s_openal','0']
   else:command=[str(stage/'launch.sh')]
   command+=['+set','ip','127.0.0.1','+set','port',str(port)]
   for name,value in session.get('startup_settings',{}).items():command+=['+set',name,str(value)]
   command+=['+exec','test.cfg']
   member='maps/'+session['map']+'.bsp';map_hashes={}
   loose=stage/'baseq2'/member
   if loose.exists():map_hashes['loose:'+member]=hashlib.sha256(loose.read_bytes()).hexdigest()
   for archive in sorted((stage/'baseq2').glob('*.pk3')):
    with zipfile.ZipFile(archive) as z:
     if member in z.namelist():map_hashes[archive.name+':'+member]=hashlib.sha256(z.read(member)).hexdigest()
   map_lumps={key:value for key,value in content_before['maps'].items() if key.endswith(member)}
   entry={'label':label,'map':session['map'],'players':session['players'],'renderer':session.get('renderer','gl1'),'phases':[],'command':command,'comparison':session.get('comparison'),'map_candidates_sha256':map_hashes,'map_lump_identities':map_lumps}
   meta['sessions'].append(entry)
   entry['quiet_audio_before_launch']=quiet(a.target)
   entry['parent_prelaunch_release']=prelaunch_memory.release()
   log=(folder/'engine.log').open('w');proc=subprocess.Popen(command,cwd=stage,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   actions=[]
   def cmd(c):
    reply=rcon(c);actions.append({'time':time.time(),'command':c,'reply':reply});return reply
   def wait(seconds):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
     if proc.poll() is not None:raise RuntimeError(f'{label} engine exited {proc.returncode}')
     time.sleep(min(.2,max(.001,end-time.monotonic())))
   def console():
    q=base/'qconsole.log'
    return q.read_text(errors='replace') if q.exists() else ''
   def state_probe():
    offset=len((folder/'engine.log').read_text(errors='replace'));cmd('pp_test_state')
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
     found=re.findall(r'PP_TEST_STATE (.+)',(folder/'engine.log').read_text(errors='replace')[offset:])
     if found:return json.loads(found[-1])
     wait(.1)
    raise RuntimeError('No fresh driver state snapshot')
   def asset_command(command):
    if command!='pp_test_models':return cmd(command)
    reply,evidence=fresh_model_query(cmd,folder/'engine.log',wait)
    entry.setdefault('model_probe_log_reads',[]).append(evidence);return reply
   def validate_state(state,attack=False):
    slots=state.get('slots',[])
    ready=len(slots)==4 and all(s.get('active') and s.get('device_connected') and not s.get('menu_open') and s.get('connection')==4 and s.get('snapshot') for s in slots)
    if not ready:raise RuntimeError('Four controllers/clients not ready: '+json.dumps(state))
    if attack and not all(s.get('cmd_buttons',0)&1 for s in slots):raise RuntimeError('Four attack commands not present: '+json.dumps(state))
   def alive(state):
    return len(state.get('slots',[]))==4 and all(s.get('gunindex',0)>0 for s in state['slots'])
   def weapon_matches(state,model):
    return alive(state) and all(s.get('gunmodel')==model for s in state['slots'])
   def prepare_deathmatch(preparation,equip=True,record_key='deathmatch_preparation'):
    states=[];started=time.monotonic();deadline=started+preparation.get('timeout',75)
    entry[record_key]={'passed':False,'started':time.time(),'states':states,
                      'scope':'Sequential ordinary attack respawns, immediately parked at the unchanged fixed scene positions.'}
    def record(label):
     state=state_probe();validate_state(state)
     states.append({'label':label,'time':time.time(),'state':state});return state
    for slot in range(4):cmd(f'pp_test_input {slot} attack 0')
    state=record('initial')
    # Park currently living players first; then revive one dead client at a
    # time and immediately move it to its unchanged fixed scene position.
    # Re-check everyone: a random respawn can telefrag another living client.
    for slot in range(4):
     if state['slots'][slot].get('gunindex',0)>0:
      cmd(preparation['poses'][slot]);wait(.4);state=record(f'park-alive-{slot}')
    while not alive(state):
     if time.monotonic()>deadline:raise RuntimeError('Sequential DM respawn did not converge')
     dead=next(s['slot'] for s in state['slots'] if s.get('gunindex',0)<=0)
     cmd(f'pp_test_input {dead} attack 0');wait(.3)
     cmd(f'pp_test_input {dead} attack 1');wait(.65)
     cmd(f'pp_test_input {dead} attack 0');wait(.25)
     state=record(f'respawn-pulse-{dead}')
     if state['slots'][dead].get('gunindex',0)>0:
      cmd(preparation['poses'][dead]);wait(.45);state=record(f'park-revived-{dead}')
    for slot in range(4):cmd(f'pp_test_input {slot} attack 0')
    wait(.4);state=record('all-alive-and-parked')
    if not alive(state):raise RuntimeError('A parked DM client died before equipment')
    if not equip:
     entry[record_key].update(passed=True,seconds=time.monotonic()-started,
       weapon_requirement='Normal respawn weapon; any positive gunindex',god_commands_once_per_slot=False)
     (out/'metadata.json').write_text(json.dumps(meta,indent=2));return
    # Protection normally uses same-team/no-friendly-fire flags. Historical
    # god-mode shells are explicit opt-in, never silently enabled.
    if preparation.get('god',False):
     for slot in range(4):cmd(f'pp_test_slot {slot} god');wait(.15)
    equipment_deadline=time.monotonic()+preparation.get('equip_timeout',15)
    first_equipment_pass=True
    while True:
     for slot in range(4):
      if first_equipment_pass or state['slots'][slot].get('gunmodel')!=preparation['gunmodel']:
       for item in ('give Machinegun','give bullets 10000','use Machinegun'):
        cmd(f'pp_test_slot {slot} {item}');wait(.15)
     first_equipment_pass=False
     wait(1.0);state=record('equipped')
     if weapon_matches(state,preparation['gunmodel']):break
     if not alive(state):raise RuntimeError('A DM client died during equipment preparation')
     if time.monotonic()>equipment_deadline:raise RuntimeError('Four Machineguns did not become ready')
    entry[record_key].update(passed=True,seconds=time.monotonic()-started,
      gunmodel=preparation['gunmodel'],god_commands_once_per_slot=preparation.get('god',False))
    (out/'metadata.json').write_text(json.dumps(meta,indent=2))
   def train_probe():
    offset=len(console());cmd('listentities all');deadline=time.monotonic()+8
    while time.monotonic()<deadline:
     found=re.search(r'(?m)^func_train:\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s*$',console()[offset:])
     if found:return [float(v) for v in found.groups()]
     wait(.15)
    raise RuntimeError('No fresh train entity position')
   medians={};camera_targets={}
   try:
    deadline=time.monotonic()+120
    while True:
     status=rcon('status')
     # status prints active player names after entering the real local server.
     if len(re.findall(r'(?m)^\s*\d+\s+-?\d+\s+\d+\s+\S+',status))>=session['players']:break
     if time.monotonic()>deadline or proc.poll() is not None:raise RuntimeError('Startup failed: '+status)
     time.sleep(1)
    if a.map_file:
     expected="'maps/"+session['map']+".bsp' (found in '"+str(base)+"')"
     startup=(folder/'engine.log').read_text(errors='replace')
     if expected not in startup:raise RuntimeError('Experimental BSP load source was not confirmed: '+expected)
     entry['experimental_map_load']={'passed':True,'source':str(override),'sha256':hashlib.sha256(override.read_bytes()).hexdigest(),'log_marker':expected}
     cmd('set fs_debug 0')
    entry['status_start']=status;entry['startup_telemetry']=sample(proc.pid)
    entry['parent_after_startup']=prelaunch_memory.snapshot()
    print('START '+label+' '+status.replace('\n',' | '),flush=True)
    wait(session.get('warmup',12))
    entry['input_isolation']=input_isolation.neutralize(cmd,wait)
    entry['registration_model_list']=cmd('modellist');entry['registration_resource']=sample(proc.pid)
    startup_log=(folder/'engine.log').read_text(errors='replace')
    for marker in session.get('required_startup_messages',[]):
     if marker not in startup_log:raise RuntimeError('Renderer startup setting not confirmed: '+marker)
    if session.get('prepare_deathmatch'):prepare_deathmatch(session['prepare_deathmatch'])
    entry['quiet_audio_after_startup']=quiet(a.target)
    for phase in session['phases']:
     phase_label=phase['label'];commands=phase.get('commands',[])
     input_isolation.update_targets(commands,camera_targets)
     for c in commands:cmd(c);wait(.12)
     if phase.get('sequential_respawn'):
      prepare_deathmatch(phase['sequential_respawn'],equip=False,record_key='functional_respawn_preparation')
     wait(phase.get('settle',2))
     policy=phase.get('resource_qualification',{'mode':'observe_only'})
     qualification={'policy':policy,'attempts':[],'qualified':None,'scope':'Preregistered pre-capture resource windows; all attempts retained.'}
     if policy.get('mode')=='gate':
      qualification_start=time.monotonic();consecutive=0
      while time.monotonic()-qualification_start<policy.get('maximum_seconds',20):
       probe_before=sample(proc.pid);wait(policy.get('window_seconds',2));probe_after=sample(proc.pid)
       attempt=resource_window(probe_before,probe_after,policy);qualification['attempts'].append(attempt)
       consecutive=consecutive+1 if attempt['passed'] else 0
       if consecutive>=policy.get('consecutive_windows',2):break
      qualification['qualified']=consecutive>=policy.get('consecutive_windows',2)
      qualification['seconds']=time.monotonic()-qualification_start
     else:qualification['observation']=sample(proc.pid)
     isolation_queries=input_isolation.verify(cmd)
     state_before=state_probe()
     if phase.get('require_four_ready'):validate_state(state_before,phase.get('require_four_attack',False))
     if phase.get('require_alive') and not alive(state_before):raise RuntimeError('A required living client is dead before '+phase_label)
     if phase.get('required_gunmodel') and not weapon_matches(state_before,phase['required_gunmodel']):raise RuntimeError('Required gunmodel missing before '+phase_label+': '+json.dumps(state_before))
     for marker in phase.get('require_messages',[]):
      if marker not in console():raise RuntimeError('Missing required mission marker: '+marker)
     train_before=train_probe() if phase.get('probe_train') else None
     if phase.get('screenshot',True):cmd('screenshot png');wait(.8)
     duration=phase['seconds']
     def game_clock():
      q=base/'qconsole.log';offset=len(q.read_text(errors='replace')) if q.exists() else 0
      cmd('cmd playerlist');wait(.35)
      chunk=q.read_text(errors='replace')[offset:] if q.exists() else ''
      m=re.search(r'(?m)^(\d+):(\d{2})\s+\d+\s+-?\d+\s+PiBench\s*$',chunk)
      return {'server_seconds':int(m[1])*60+int(m[2]) if m else None,'wall_monotonic':time.monotonic(),'line':m[0] if m else chunk[-250:]}
     clock_before=game_clock()
     capture_console_offset=len(console())
     cmd('cl_perf_start '+phase_label)
     alias_profile=None;pickup_profile=None
     if phase.get('pickup_profile'):
      raise RuntimeError('Private profile instrumentation is not supported by pp-bench')
      pickup_profile_offset=(folder/'engine.log').stat().st_size
      begin=cmd('pp_pickup_profile_start '+phase_label)
      assert 'PP_PICKUP_PROFILE_BEGIN '+phase_label in begin,'Pickup profiler did not start: '+begin
     if phase.get('alias_profile'):
      raise RuntimeError('Private profile instrumentation is not supported by pp-bench')
      begin=cmd('pp_alias_profile_start '+phase_label)
      assert 'PP_ALIAS_PROFILE_BEGIN '+phase_label in begin,'Alias profiler did not start: '+begin
     telemetry=[];start=time.monotonic();next_sample=start
     print('CAPTURE '+label+'/'+phase_label+' '+str(duration)+'s',flush=True)
     while time.monotonic()-start<duration:
      if time.monotonic()>=next_sample:
       point=sample(proc.pid);point['parent']=prelaunch_memory.process_snapshot();telemetry.append(point);next_sample+=2
      wait(min(.5,max(.001,duration-(time.monotonic()-start))))
     if phase.get('alias_profile'):
      dump=cmd('pp_alias_profile_stop');profile_path=folder/(phase_label+'-alias-profile.txt');profile_path.write_text(dump)
      assert 'PP_ALIAS_PROFILE_END '+phase_label in dump,'Alias profiler dump incomplete'
      alias_profile=dict(path=str(profile_path),sha256=hashlib.sha256(profile_path.read_bytes()).hexdigest(),scope='Actual post-cull submitted models; CPUwall unsynchronized, instrumentation affects timing.')
     if phase.get('pickup_profile'):
      reply=cmd('pp_pickup_profile_stop');assert 'PP_PICKUP_PROFILE_END '+phase_label in reply,'Pickup profiler stop not acknowledged'
      dump,log_read=fresh_pickup_dump(folder/'engine.log',phase_label,pickup_profile_offset,wait);profile_path=folder/(phase_label+'-pickup-profile.txt');profile_path.write_text(dump)
      pickup_profile=dict(path=str(profile_path),sha256=hashlib.sha256(profile_path.read_bytes()).hexdigest(),log_read=log_read,scope='Fresh bounded engine stderr, never large UDP payloads. Private GLbuffer/world stages/counts; CPUwall unsynchronized, instrumentation affects timing, no main FPS claim.')
     cmd('cl_perf_stop');wait(.25)
     clock_after=game_clock()
     (folder/(phase_label+'-telemetry.json')).write_text(json.dumps(telemetry,indent=2))
     data=list(csv.DictReader((base/'perf'/f'{phase_label}-frames.csv').open()))
     views=list(csv.DictReader((base/'perf'/f'{phase_label}-views.csv').open()))
     import statistics
     medians[phase_label]={str(slot):statistics.median(float(v['x']) for v in views if int(v['slot'])==slot) for slot in range(4)}
     capture_deaths=player_deaths(console()[capture_console_offset:])
     state_after=state_probe()
     input_audit=input_isolation.phase_audit(phase,state_before,state_after,views,camera_targets)
     if phase.get('require_four_ready'):validate_state(state_after,phase.get('require_four_attack',False))
     train_after=train_probe() if phase.get('probe_train') else None
     effective=dict(line.split('=',1) for line in (base/'perf'/f'{phase_label}-settings.txt').read_text().splitlines() if '=' in line)
     scene=scene_controls.audit(dict(label=phase_label,state_before=state_before,state_after=state_after,train_after=train_after),session,entry,views)
     counter_proof=scene_controls.ordinary_counters(data,views)
     assertions={'hard_input_controls':scene['hard_input']['passed'],'ordinary_renderer_counters':counter_proof['passed'],'four_views':set(r['views'] for r in data)=={'4'},'framebuffer':all((int(r['width']),int(r['height']))==(width,height) for r in data),'viewports':all((int(r['width']),int(r['height']))==(width//2,height//2) for r in views),'mode':effective.get('deathmatch')==('1' if session.get('dm') else '0') and effective.get('coop')==('0' if session.get('dm') else '1'),'lod_setting':effective.get('r_pickup_lod')==str(session['settings']['r_pickup_lod'])}
     comparison=session.get('comparison',{})
     if comparison.get('kind')=='gl_world_renderer_pair':
      assertions['profiling_disabled']=effective.get('r_drawprofile')=='0'
     if comparison.get('kind')=='paired':
      assertions['optimization_setting']=effective.get(comparison['feature_cvar'])==str(comparison['feature'])
      assertions['profiling_disabled']=effective.get('r_drawprofile')=='0'
     if comparison.get('kind')=='final_corrected_layout':
      assertions['lightmap_optimization_enabled']=effective.get('r_gl1_lightmap_opt')=='1'
      assertions['profiling_disabled']=effective.get('r_drawprofile')=='0'
     assertions['inline_batching_enabled']=effective.get('r_gl1_batch_inline')=='1'
     assertions['world_batching_enabled']=effective.get('r_gl1_batch_world')=='1'
     assertions['lightmap_copies_disabled']=effective.get('gl1_lightmapcopies')=='0'
     required_cvars={**session.get('require_cvars',{}),**variant.get('runtime_cvars',{})}
     cvar_queries={name:cmd(name) for name in required_cvars}
     for name,expected in required_cvars.items():
      found=re.search(r'"'+re.escape(name)+r'" is "([^"\r\n]*)"',cvar_queries[name])
      assertions['actual_cvar_'+name]=bool(found) and found[1]==str(expected)
      if found:effective[name]=found[1]
     if phase.get('expected_camera_xy'):
      tolerance=phase.get('camera_xy_tolerance',2)
      scene['matched_scene']['explicit_fixed_xy_passed']=all(abs(float(view[axis])-float(phase['expected_camera_xy'][view['slot']][i]))<=tolerance for view in views for i,axis in enumerate(('x','y')))
      scene['matched_scene']['passed']=scene['matched_scene']['passed']and scene['matched_scene']['explicit_fixed_xy_passed']
     if phase.get('profile_required'):
      assertions['profiling_enabled']=effective.get('r_drawprofile')=='1'
      assertions['profile_columns_present']=bool(data) and all(name in data[0] for name in ('dp_world_draws','dp_inline_draws','dp_pickup_draws','dp_world_mark_ms','dp_brush_light_ms','dp_lm_regen_ms','dp_lm_build_ms','dp_lm_upload_ms','dp_world_chain_ms','dp_world_blend_ms','dp_world_sky_ms','dp_world_alpha_ms','dp_world_visible_surfaces','dp_world_flush_lightmap','dp_mtex_enabled','dp_lm_copy_enabled','dp_lm_atlas_count'))
      assertions['profile_counters_valid']=bool(data) and all(float(row['dp_world_draws'])>=0 and float(row['dp_inline_draws'])>=0 for row in data)
      assertions['fine_lightmap_columns_present']=bool(data) and all(field in data[0] for field in phase.get('required_profile_columns',()))
      assertions['fine_lightmap_counters_valid']=bool(data) and all(float(row.get(field,'nan'))>=0 for row in data for field in phase.get('required_profile_columns',()))
     if 'expected_alive' in phase:
      assertions['all_four_weapon_state']=all((s.get('gunindex',0)>0)==phase['expected_alive'] for s in state_after['slots'])
     if phase.get('require_alive'):
      assertions['all_four_alive']=alive(state_before) and alive(state_after)
      assertions['no_player_deaths_during_capture']=not capture_deaths
     if phase.get('required_gunmodel'):assertions['all_four_machineguns']=weapon_matches(state_before,phase['required_gunmodel']) and weapon_matches(state_after,phase['required_gunmodel'])
     if phase.get('motion_reference'):
      previous=medians[phase['motion_reference']]
      assertions['all_four_carried']=all(previous[str(s)]-medians[phase_label][str(s)]>=phase.get('minimum_camera_x_shift',24) for s in range(4))
     if phase.get('require_train_x'):
      lo,hi=phase['require_train_x'];assertions['train_at_bridge']=train_after is not None and lo<=train_after[0]<=hi
     entry['phases'].append({'label':phase_label,'seconds':duration,'frames':len(data),'view_counts':sorted({r['views'] for r in data}),'viewports':sorted({(r['width'],r['height']) for r in views}),'commands':commands,'status':cmd('status'),'game_clock_before':clock_before,'game_clock_after':clock_after,'state_before':state_before,'state_after':state_after,'capture_obituaries':capture_deaths,'train_before':train_before,'train_after':train_after,'camera_median_x':medians[phase_label],'effective_settings':effective,'resource_qualification':qualification,'input_isolation_queries':isolation_queries,'input_audit':input_audit,'hard_input_audit':scene['hard_input'],'matched_scene_qualification':scene['matched_scene'],'ordinary_counter_proof':counter_proof,'assertions':assertions,'map_candidates_sha256':map_hashes})
     if cvar_queries:entry['phases'][-1]['required_cvar_queries']=cvar_queries
     if alias_profile:entry['phases'][-1]['alias_profile']=alias_profile
     if pickup_profile:entry['phases'][-1]['pickup_profile']=pickup_profile
     print('DONE '+label+'/'+phase_label+' '+str(len(data))+' frames; views '+str(entry['phases'][-1]['view_counts']),flush=True)
     (out/'metadata.json').write_text(json.dumps(meta,indent=2))
     if not all(assertions.values()):raise RuntimeError('Capture validation failed: '+json.dumps(assertions))
    entry['status_end']=cmd('status');entry['final_telemetry']=sample(proc.pid)
    if a.shim:cmd('pp_test_state');wait(.15)
    cmd('quit');proc.wait(timeout=15);entry['returncode']=proc.returncode;assert proc.returncode==0
   finally:
    if proc.poll() is None:
     rcon('quit')
     try:proc.wait(timeout=10)
     except subprocess.TimeoutExpired:
      os.killpg(proc.pid,signal.SIGTERM)
      try:proc.wait(timeout=5)
      except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=5)
    log.close();(folder/'actions.json').write_text(json.dumps(actions,indent=2));(base/'test.cfg').write_text(cfg.replace(token,'REDACTED_LOCAL_TOKEN'))
    meta['save_hashes_unchanged']=hashes(real_save)==before;meta['package_hashes_unchanged']=hashes(package)==installed
    (out/'metadata.json').write_text(json.dumps(meta,indent=2))
 except BaseException as e:
  meta['error']=repr(e);raise
 finally:
  if active:set_shell(a.target,True)
  meta['shell_restored']=shell_active(a.target)==active
  try:meta['quiet_audio_after_restore']=quiet(a.target)
  except RuntimeError as error:meta['quiet_audio_after_restore']={'passed':False,'error':str(error)};meta['error']=repr(error)
  meta['save_hashes_unchanged']=hashes(real_save)==before;meta['package_hashes_unchanged']=hashes(package)==installed;meta['ended']=time.time()
  stage_after=hashes(stage)
  meta['runtime_hashes_unchanged']=stage_after==stage_before
  meta['content_identity_after']=content_identity(stage,stage_after)
  meta['assets_maps_visibility_unchanged']=meta['content_identity_after']==content_before
  (out/'metadata.json').write_text(json.dumps(meta,indent=2))
  print('RESULT '+str(out/'metadata.json'),flush=True)
  if not all(meta.get(k) is True for k in ('save_hashes_unchanged','package_hashes_unchanged','runtime_hashes_unchanged','assets_maps_visibility_unchanged','shell_restored')) or not meta.get('quiet_audio_after_restore',{}).get('passed'):
   raise RuntimeError('Post-test preservation checks failed; inspect metadata.json')
if __name__=='__main__':main()
