"""Preregistered hard input/counter checks and separate camera comparability."""
import math
from collections import defaultdict
import input_isolation

def audit(phase,plan,session,views):
 targets={};absolute={};intended=None
 input_isolation.update_targets(plan.get('prepare_deathmatch',{}).get('poses',[]),absolute)
 for candidate in plan.get('phases',[]):
  input_isolation.update_targets(candidate.get('commands',[]),targets);input_isolation.update_targets(candidate.get('commands',[]),absolute)
  if candidate['label']==phase['label']:intended=candidate;break
 if intended is None:raise ValueError('Phase not in frozen plan')
 raw=input_isolation.phase_audit(intended,phase['state_before'],phase['state_after'],views,targets)
 hard={k:v for k,v in raw['checks'].items()if not k.endswith('_fixed_xy_with_recoil')};spans={k:v for k,v in raw['checks'].items()if k.endswith('_fixed_xy_with_recoil')};positions=[]
 hard['all_six_view_coordinates_finite']=bool(views)and all(math.isfinite(float(row[key]))for row in views for key in ('x','y','z','pitch','yaw','roll'))
 if not phase['label'].startswith('functional-'):
  if phase['label']=='bridge-four-guns':
   boarded=next((p for p in session.get('phases',[])if p['label']=='boarding-clear-floor'),{});a=boarded.get('train_after');b=phase.get('train_after')
   if a and b:absolute={slot:[pose[i]+(b[i]-a[i])if i<3 else pose[i]for i in range(5)]for slot,pose in absolute.items()}
  for slot,pose in absolute.items():
   own=[r for r in views if int(r['slot'])==slot];errors={axis:max((abs(float(r[axis])-pose[i])for r in own),default=math.inf)for i,axis in enumerate(('x','y'))};positions.append(dict(slot=slot,expected_xy=pose[:2],maximum_absolute_error=errors,passed=bool(own)and all(math.isfinite(v)and v<=2 for v in errors.values())))
 matched=all(spans.values())and all(row['passed']for row in positions)
 return dict(hard_input=dict(passed=bool(hard)and all(hard.values()),checks=hard,scope='Zero actual endpoint movement, fixed base angles, finite views and unchanged yaw guards. Physical input isolation is independently verified.'),raw_phase_audit=raw,matched_scene=dict(passed=matched,xy_span_checks=spans,absolute_xy_checks=positions,absolute_tolerance_units=2.0,span_tolerance_units=1.001,scope='Preregistered performance qualification only. Natural recoil/knockback XY drift is retained and never triggers a roster retry. A failed camera match prevents a controlled scene performance claim, while hard input/state/counter checks remain mandatory.'))

def ordinary_counters(frames,views):
 grouped=defaultdict(list);serials=[];valid=True
 for view in views:
  grouped[view.get('frame')].append(view)
  try:
   serial=float(view['renderer_serial']);fresh=float(view['renderer_counters'])==1 and math.isfinite(serial)and serial>0;serials.append(serial);valid=valid and fresh
  except (KeyError,ValueError):valid=False
 sums={}
 for key in ('draws','world_triangles','model_triangles'):
  ok=bool(frames)
  for frame in frames:
   own=grouped.get(frame.get('frame'),[])
   try:
    wanted=float(frame[key]);parts=[float(v[key])for v in own];ok=ok and len(own)==4 and len({v.get('slot')for v in own})==4 and math.isfinite(wanted)and all(math.isfinite(v)and v>=0 for v in parts)and abs(wanted-sum(parts))<=.01
   except (KeyError,ValueError):ok=False
  sums[key]=ok
 fresh=bool(views)and valid and len(set(serials))==len(views);complete=len(views)==4*len(frames)and set(grouped)=={f.get('frame')for f in frames}
 return dict(passed=fresh and complete and all(sums.values()),fresh_unique_per_view_serials=fresh,complete_four_view_rows=complete,frame_equals_four_views=sums,scope='All raw frames including warmup. Actual ordinary renderer counters are mandatory; profiling-only DP columns are not assumed.')
