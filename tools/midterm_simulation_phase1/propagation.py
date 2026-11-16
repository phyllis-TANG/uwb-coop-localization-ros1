"""MT-S0: existing PR88 generator and M2/M3; single-link injection only."""
import sys,copy,json,csv,math,time,gzip,subprocess,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];P=ROOT/'docs/research/midterm_simulation_phase1'
sys.path.insert(0,str(ROOT/'tools/two_car_mechanism_20261101'))
from bindings import generator,adapter,clone
from inputs import make as original_make
from support import digest,sources
from analyze import ant
import numpy as np

def generate(seed,layout,link,bias):
 spec=json.loads((ROOT/'tools/two_car_sim_dev_20261101/development_static_moving.json').read_text());spec['seed']=seed
 if layout=='G2':
  for q in spec['trajectories']['car2']:q['antenna_xy_m']=[q['antenna_xy_m'][0]+1.49,q['antenna_xy_m'][1]+2.01]
 def validate(s):
  check=copy.deepcopy(s);check['seed']=7;generator.validate(check)
  assert seed in [16101,16102] or 17101<=seed<=17150
 make=clone(generator.make,validate=validate)
 c,e,t,l=make(spec,'nominal');before=copy.deepcopy(e);changed=0
 for r in e:
  if r['kind']=='uwb' and r['vehicle_id']=='car1' and 6_000_000_000<=r['header_epoch_ns']-generator.EPOCH_NS<20_000_000_000:
   key='node_2' if link=='wall' else 'node_0';r['value'][key]+=bias;r['raw_message_sha256']=digest(r['value']);changed+=int(bias!=0)
 for a,b in zip(before,e):
  if a!=b:
   assert a['kind']=='uwb' and a['vehicle_id']=='car1'
   for k in a['value']:
    if k!=('node_2' if link=='wall' else 'node_0'):assert a['value'][k]==b['value'][k]
 assert changed==(280 if bias else 0)
 return c,e,t,dict(seed=seed,layout=layout,link=link,bias=bias,config_sha256=digest(c),events_sha256=digest(e),nominal_events_sha256=digest(before),truth_sha256=digest(t),generation_sha256=digest(spec),changed_scalars=changed)

def execute(c,e,t):
 rows={};start=time.perf_counter()
 for method in ['M2','M3']:
  rows[method]=[];worker=adapter.replay(c,method,rows[method].append,e[0]['receive_epoch_ns'])
  for event in e:worker.ingest(event)
  worker.finish()
 a,b=rows.values();assert [r['state_time_s'] for r in a]==[r['state_time_s'] for r in b]
 for x,y in zip(a,b):assert x['bins']==y['bins']
 truth={r['time_s']:r for r in t};out=[]
 for ci,car in enumerate(['car1','car2']):
  common=[i for i,(x,y) in enumerate(zip(a,b)) if 6<=x['state_time_s']<=31 and x['accepted_graph'] and y['accepted_graph']]
  errors={method:[float(np.sum((ant(rows[method][i]['pose'][4*ci:4*ci+3],c['models'][car])-np.array(truth[rows[method][i]['state_time_s']]['cars'][car]['antenna_xyz_m'][:2]))**2)) for i in common] for method in rows}
  ms={k:float(np.mean(v)) if v else None for k,v in errors.items()}
  out.append(dict(car=car,publications=len(a),scheduled_evaluation_s=26,common_accepted=len(common),excluded_evaluation_s=26-len(common),M2_mse_m2=ms['M2'],M3_mse_m2=ms['M3'],D_m2=ms['M3']-ms['M2'] if common else None,M2_rmse_m=math.sqrt(ms['M2']) if common else None,M3_rmse_m=math.sqrt(ms['M3']) if common else None,failed_publications=sum('error' in r['status'] or 'failed' in r['status'] for seq in rows.values() for r in seq),elapsed_s=time.perf_counter()-start))
 return out,rows

def task(args):
 seed,layout,link,bias,phase=args;tag=f'{seed}_{layout}_{link}_{bias}';dest=P/'s0'/phase/tag;dest.mkdir(parents=True,exist_ok=False)
 try:
  c,e,t,receipt=generate(seed,layout,link,bias);out,rows=execute(c,e,t)
  for r in out:r.update(seed=seed,layout=layout,link=link,bias_m=bias,phase=phase)
  record=dict(status='DONE',input=receipt,metrics=out,source_sha256=sources(),execution_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
  with (dest/'RUN.json').open('x') as f:json.dump(record,f,indent=2)
  if seed==16101 and bias==.3:
   with gzip.open(dest/'trajectory.json.gz','wt') as f:json.dump({m:[{k:r[k] for k in ['state_time_s','pose','accepted_graph','status']} for r in seq] for m,seq in rows.items()},f)
  return tag
 except Exception as error:
  (dest/'FAILED.json').write_text(json.dumps(dict(error=repr(error))));raise

def baseline():
 p=json.loads((ROOT/'docs/research/two_car_mechanism_20261101/PROTOCOL.json').read_text());c,e,t,l,s=original_make(p,'development',7,'static_moving','nominal')
 _,rows=execute(c,e,t);old=list(csv.DictReader((ROOT/'docs/research/two_car_mechanism_20261101/results/development/PER_SEED.csv').open()));truth={r['time_s']:r for r in t};checks=[]
 for method,seq in rows.items():
  for ci,car in enumerate(['car1','car2']):
   vals=[float(np.sum((ant(r['pose'][4*ci:4*ci+3],c['models'][car])-np.array(truth[r['state_time_s']]['cars'][car]['antenna_xyz_m'][:2]))**2)) for r in seq if r['accepted_graph']]
   expected=next(r for r in old if r['motion']=='static_moving' and r['condition']=='nominal' and r['method']==method and r['car']==car and r['phase']=='all')
   difference=abs(float(np.mean(vals))-float(expected['mse_valid_m2']));checks.append(dict(method=method,car=car,actual_mse=float(np.mean(vals)),saved_mse=float(expected['mse_valid_m2']),difference=difference,accepted=len(vals)))
  with gzip.open(P/f'BASELINE_{method}.json.gz','wt') as f:json.dump([{k:r[k] for k in ['state_time_s','pose','accepted_graph','status']} for r in seq],f)
 (P/'BASELINE_SIMULATION.json').write_text(json.dumps(dict(checks=checks,status='PASS_EXISTING_1e-10_READBACK_RULE' if max(x['difference'] for x in checks)<1e-10 else 'DIFFERENT_DO_NOT_RETUNE',input_sha256=dict(config=digest(c),events=digest(e),truth=digest(t)),environment='Python3.10.12 versus original3.12.14; numpy/scipy same'),indent=2))
if __name__=='__main__':
 phase=sys.argv[1]
 if phase=='baseline':baseline()
 else:
  if phase=='development':jobs=[(s,g,l,b,phase) for s in [16101,16102] for g in ['G1','G2'] for l in ['wall','peer'] for b in [0.,.1,.3,.5]]
  else:
   assert json.loads((P/'FROZEN.json').read_text())['code_sha256']==hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
   jobs=[(s,'G2',l,b,phase) for s in range(17101,17151) for l,b in [('wall',0.),('wall',.3),('peer',.3)]]
  from concurrent.futures import ProcessPoolExecutor
  with ProcessPoolExecutor(max_workers=4) as pool:
   for result in pool.map(task,jobs):print(result,'DONE',flush=True)
