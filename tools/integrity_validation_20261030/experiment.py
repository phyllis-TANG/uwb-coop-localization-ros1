"""PR81 read-only wrapper; generated inputs in RAM, immutable unit outputs."""
import sys, json, copy, gzip, time, csv, subprocess, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/cooperative_integrity_baselines_20261029'))
from binding import simulate, frontend, numeric
from common import SPEC, digest, sha, write_json, csv_write, source_lock
from engine import run
from evaluate import evaluate
from run import compact
import numpy as np
OUT=ROOT/'docs/research/integrity_validation_20261030'
CONDITIONS={'nominal':(0,38,0),'peer_bias':(0,38,0),'car1_common_wall_bias':(.3,38,0),'wall_015':(.15,38,0),'wall_060':(.6,38,0),'wall_short':(.3,31,0),'wall_long':(.3,52,0),'wall_ar07':(.3,38,.7)}
def make(seed,condition):
    bias,end,rho=CONDITIONS[condition]
    config,events,truth,labels=simulate.make_case(seed,'peer_bias' if condition=='peer_bias' else 'nominal')
    before=copy.deepcopy(events); template=json.loads(simulate.CONFIG.read_text()); previous={}; changed=0
    for row,old in zip(events,before):
        car=row['vehicle_id']; t=(row['header_epoch_ns']-simulate.EPOCH_NS)/1e9
        if row['kind']=='uwb':
            for key,xyz in config['models'][car]['anchors_xyz_m'].items():
                delta=0.
                if rho:
                    model=template['models'][car]
                    a=simulate.antenna_xyz(simulate.true_pose(t,car,model),model)
                    distance=float(np.linalg.norm(a-np.asarray(xyz)))
                    innovation=old['value'][key]-distance
                    identity=(car,key)
                    noise=innovation if identity not in previous else rho*previous[identity]+np.sqrt(1-rho*rho)*innovation
                    previous[identity]=noise; delta=noise-innovation
                if car=='car1' and 24<=t<end: delta+=bias
                row['value'][key]+=delta
                changed+=int(delta!=0)
        assert {k:v for k,v in row.items() if k!='value'}=={k:v for k,v in old.items() if k!='value'}
        for key,v in old['value'].items():
            allowed=row['kind']=='uwb' and key in config['models'][car]['anchors_xyz_m'] and (rho or (car=='car1' and 24<=t<end and bias))
            if not allowed: assert row['value'][key]==v
    receipt=dict(seed=seed,condition=condition,events_sha256=digest(events),base_events_sha256=digest(before),config_sha256=digest(config),truth_sha256=digest(truth),changed_wall_scalars=changed,adapter_only_registered_fields=True,end_s=end,rho=rho)
    return config,events,truth,receipt

def guard():
    size=sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())
    if size>90_000_000 or shutil.disk_usage(OUT).free<500_000_000: raise RuntimeError('unit-boundary storage guard')

def one(seed,condition,phase):
    guard(); dest=OUT/'units'/f'{seed}_{condition}';dest.mkdir(parents=True,exist_ok=False)
    config,events,truth,receipt=make(seed,condition); write_json(dest/'INPUT.json',receipt)
    rows=[]; start=time.perf_counter();run(events,config,rows.append)
    assert len(rows)==63
    if seed==4101:
        plain=[]; worker=frontend.JointReplay(config,'D1',plain.append,events[0]['receive_epoch_ns'])
        for event in events:worker.ingest(event)
        worker.finish();assert [numeric(r) for r in rows]==[numeric(r) for r in plain]
    # Save all monitor decisions and scores, but no truth/error during calibration.
    with gzip.open(dest/'scores.json.gz','wt') as f:
        json.dump([dict(t=r['state_time_s'],accepted=r['accepted_graph'],monitor={k:r['monitor'][k] for k in ('ss','b0','b1','declarations')}) for r in rows],f)
    audit=seed==4101 or (seed==5101 and phase=='validation')
    if audit:
        with gzip.open(dest/'monitor.jsonl.gz','wt') as f:
            for r in rows:f.write(json.dumps(compact(r))+'\n')
        write_json(dest/'config.json',config)
    if phase!='calibration':
        end=CONDITIONS[condition][1]
        SPEC['evaluation_intervals']={'all':[1,64],'pre':[1,24],'fault':[24,end],'recovery':[end,end+10],'late':[end+10,64]}
        values=evaluate(condition,rows,truth,config)
        for name,table in values.items():
            with gzip.open(dest/(name+'.csv.gz'),'wt') as f:
                w=csv.DictWriter(f,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
    write_json(dest/'RUN.json',dict(seed=seed,condition=condition,phase=phase,publications=len(rows),accepted=sum(r['accepted_graph'] for r in rows),elapsed_s=time.perf_counter()-start,emit_s=sum(r['total_monitored_emit_wall_s'] for r in rows),source_sha256=source_lock(),wrapper_sha256=sha(__file__),execution_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),status='DONE'))
    print(seed,condition,'DONE',flush=True)

def calibration():
    for seed in range(4101,4107):one(seed,'nominal','calibration')
    result=[]
    for seed in range(4101,4107):
        rows=json.load(gzip.open(OUT/'units'/f'{seed}_nominal'/'scores.json.gz','rt'))
        for scale in (.25,1.,2.):
            for ci in range(2):
                ds=[r['monitor']['declarations'][f'B2_local|scale={scale}|a=0.01'][ci] for r in rows]
                n=sum(d['computable'] for d in ds);a=sum(d['alarm'] and d['computable'] for d in ds)
                result.append(dict(seed=seed,car=f'car{ci+1}',scale=scale,computable_s=n,alarm_s=a,alarm_occupancy=a/n if n else 1,unknown_s=63-n,available_s=sum(d['available'] for d in ds),all_published_s=63))
    csv_write(OUT/'CALIBRATION.csv',result)
    eligible=[]
    for scale in (.25,1.,2.):
        if all(np.mean([r['alarm_occupancy'] for r in result if r['scale']==scale and r['car']==car])<=.05 and max(r['alarm_occupancy'] for r in result if r['scale']==scale and r['car']==car)<=.1 for car in ('car1','car2')):eligible.append(scale)
    write_json(OUT/'FROZEN_VALIDATION.json',dict(selected_scale=min(eligible) if eligible else 1.,calibration_target_met=bool(eligible),eligible_scales=eligible,alpha=.01,calibration_seeds=list(range(4101,4107)),validation_seeds=list(range(5101,5109)),calibration_sha256=sha(OUT/'CALIBRATION.csv'),wrapper_sha256=sha(__file__),baseline_sources=source_lock(),rule='both cars mean<=.05 each<=.10; minimum scale; fallback1',truth_used_for_selection=False))

if __name__=='__main__':
    phase=sys.argv[1]
    if phase=='calibration':calibration()
    else:
        frozen=json.loads((OUT/'FROZEN_VALIDATION.json').read_text());assert frozen['wrapper_sha256']==sha(__file__)
        subprocess.run(['git','diff','--exit-code','HEAD','--',str(OUT/'FROZEN_VALIDATION.json')],check=True)
        assert subprocess.check_output(['git','ls-files',str(OUT/'FROZEN_VALIDATION.json')],text=True).strip()
        seeds=[5101] if phase=='checkpoint' else range(5102,5109) if phase=='validation' else range(5101,5109)
        conditions=list(CONDITIONS)[:3] if phase in ('checkpoint','validation') else list(CONDITIONS)[3:]
        for seed in seeds:
            for condition in conditions:one(seed,condition,'validation' if phase in ('checkpoint','validation') else 'boundary')
