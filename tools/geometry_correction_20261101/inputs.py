"""One traced PR91 draw per seed; geometry/processing share its primitives."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import types
import numpy as np
from local_support import CARS,EPOCH,ROOT,clone,digest,dump,new,protocol,sha,sources,write
from reuse import generator
from initialize import initialize

NAMES=['global_wall']+[f'{c}_{k}' for c in CARS for k in ('initial','odom','vehicle_wall','iid_wall','peer','bias_steps','gyro_white')]

class Trace:
    def __init__(self,seed):self.rng=np.random.default_rng(seed);self.draws={};self.calls=[]
    def normal(self,*a,**kw):
        value=self.rng.normal(*a,**kw);name=NAMES[len(self.calls)];self.draws[name]=value.copy()
        self.calls.append(dict(name=name,shape=list(value.shape),dtype=str(value.dtype),array_sha256=hashlib.sha256(value.tobytes()).hexdigest()))
        return value

class NPProxy:
    def __init__(self,trace):self.random=types.SimpleNamespace(default_rng=lambda seed:trace)
    def __getattr__(self,name):return getattr(np,name)

def base_case(p,seed):
    if seed not in p['seeds']:raise ValueError('Unfrozen seed')
    spec=copy.deepcopy(p['trajectory']);spec['seed']=seed
    trace=Trace(seed)
    def validate(s):
        if s!=spec or s['duration_s']!=96 or s['motion']!='both_moving':raise ValueError('Unfrozen trajectory configuration')
    make=clone(generator.make,np=NPProxy(trace),validate=validate,sources=sources)
    config,events,truth,labels=make(spec,'nominal')
    if len(trace.calls)!=15:raise ValueError('PR91 random draw order changed')
    return events,truth,trace

def build_seed(output,seed):
    p=protocol();root=new(output);events,truth,trace=base_case(p,seed)
    np.savez_compressed(root/'primitives.npz',**trace.draws)
    dump(root/'PRIMITIVES.json',dict(seed=seed,file_sha256=sha(root/'primitives.npz'),calls=trace.calls,shared_across_all_geometry_and_processing=True))
    initial={c:trace.draws[c+'_initial'].tolist() for c in CARS}
    cfg0=generator.default_config();models=cfg0['models'];spec=p['trajectory']
    original={c:np.array([generator.pose(i*.05,c,spec,models[c])[1] for i in range(1921)]) for c in CARS}
    cases=[]
    for geometry in ('G1','G2'):
        shift=np.array(p['geometry_translation_m'][geometry]);ant={c:original[c].copy() for c in CARS};ant['car2'][:,:2]+=shift
        shifted_truth=copy.deepcopy(truth)
        for row in shifted_truth:
            row['cars']['car2']['pose'][:2]=(np.array(row['cars']['car2']['pose'][:2])+shift).tolist()
            row['cars']['car2']['antenna_xyz_m'][:2]=(np.array(row['cars']['car2']['antenna_xyz_m'][:2])+shift).tolist()
        underlying=[]
        for original_event in events:
            e=copy.deepcopy(original_event);e['case_id']=f'synthetic_mechanism_seed{seed}_geometry_correction'
            if e['kind']=='uwb':
                car=e['vehicle_id'];i=(e['header_epoch_ns']-EPOCH)//50_000_000
                for j,key in enumerate(sorted(models[car]['anchors_xyz_m'])):
                    noise=.04*trace.draws[car+'_iid_wall'][i,j]
                    e['value'][key]=float(np.linalg.norm(ant[car][i]-models[car]['anchors_xyz_m'][key])+noise)
                peer_key='node_0' if car=='car1' else 'node_1'
                e['value'][peer_key]=float(np.linalg.norm(ant['car1'][i]-ant['car2'][i])+trace.draws[car+'_peer'][i])
                if car=='car2':
                    for key,bias in zip(p['wall_nodes'],p['bias_vector_m']):e['value'][key]+=bias
            e['source_file_sha256']=digest(dict(seed=seed,geometry=geometry,protocol=p,primitive_sha256=sha(root/'primitives.npz')))
            e['raw_message_sha256']=digest(e['value']);underlying.append(e)
        write(root/(geometry+'-underlying.jsonl.gz'),underlying)
        for processing in ('raw','historical'):
            target=root/(geometry+'-'+processing);target.mkdir()
            processed=copy.deepcopy(underlying)
            if processing=='historical':
                for e in processed:
                    if e['kind']=='uwb' and e['vehicle_id']=='car2':
                        for key,bias in zip(p['wall_nodes'],p['bias_vector_m']):e['value'][key]-=bias
                        e['raw_message_sha256']=digest(e['value'])
            init_config,receipt=initialize(cfg0,processed,initial,p)
            dump(target/'config.json',init_config);dump(target/'INITIALIZATION.json',receipt)
            write(target/'startup_events.jsonl.gz',[e for e in processed if e['receive_epoch_ns']<=EPOCH+6_050_000_000])
            selected=[e for e in processed if e['kind']!='clock' and e['header_epoch_ns']>=EPOCH+5*10**9]
            clock=copy.deepcopy(processed[0]);clock.update(header_epoch_ns=EPOCH+5*10**9,receive_epoch_ns=EPOCH+5*10**9,value=dict(clock_epoch_ns=EPOCH+5*10**9))
            clock['raw_message_sha256']=digest(clock['value'])
            online=[clock,*selected]
            for e in online:e['availability_epoch_ns']=max(e['receive_epoch_ns'],EPOCH+6_050_000_000)
            write(target/'events.jsonl.gz',online);write(target/'truth.jsonl.gz',shifted_truth)
            info=dict(seed=seed,geometry=geometry,processing=processing,primitive_file_sha256=sha(root/'primitives.npz'),
                source_sha256=sources(),protocol_sha256=sha(ROOT/'docs/research/geometry_correction_20261101_private/PROTOCOL.json'),
                files={q.name:sha(q) for q in target.iterdir()},estimator_inputs=['config.json','events.jsonl.gz'],truth_estimator_input=False)
            dump(target/'MANIFEST.json',info);cases.append(info)
    dump(root/'SEED_INPUT_INDEX.json',dict(seed=seed,cases=cases,underlying={g:sha(root/(g+'-underlying.jsonl.gz')) for g in ('G1','G2')},source_sha256=sources()))
    return cases

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--seed',required=True,type=int);a.add_argument('--output',required=True,type=Path);v=a.parse_args()
    print(json.dumps(dict(seed=v.seed,cases=len(build_seed(v.output,v.seed)))))
