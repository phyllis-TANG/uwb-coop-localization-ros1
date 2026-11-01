"""Explicit dynamic field adapter, frozen numerical kernels, A1/B1 only."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
import argparse
import bisect
import collections
import copy
from decimal import Decimal
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
import types
import numpy as np
from scipy.optimize import least_squares

HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[2]
FIELD=PROJECT/'outputs/field_measurements_20261101/v001'
SNAP=PROJECT/'outputs/two_car_imu_integration_20261031/v001/source_snapshot'
sys.path.insert(0,str(SNAP/'tools/two_car_imu_fgo'))
import core
import pinned
CARS=('car1','car2')
NS=10**9

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()

class WeightedObjective(core.Objective):
    def evaluate(self,x):
        r,j=super().evaluate(x);r,j=r.copy(),j.copy()
        if self.peers:r[-len(self.peers):]*=.5;j[-len(self.peers):]*=.5
        return r,j
def clone(f,**bindings):
    g=dict(f.__globals__);g.update(bindings)
    return types.FunctionType(f.__code__,g,f.__name__,f.__defaults__,f.__closure__)
weighted_eliminate=clone(core.eliminate,Objective=WeightedObjective)
weighted_update=clone(core.WindowGraph.update,Objective=WeightedObjective,eliminate=weighted_eliminate)
class WeightedGraph(core.WindowGraph):
    def __init__(self,cfg):super().__init__(cfg,True)
    def update(self,*a):return weighted_update(self,*a)

def prepare(case):
    out=HERE/case
    out.mkdir(exist_ok=False)
    receipt=read(FIELD/(case+'_technical_QC.json'));bag=Path(receipt['bag_path'])
    if sha(bag)!=receipt['bag_sha256']:raise ValueError('Bag identity changed')
    decoder=PROJECT/'outputs/field_measurements_20261031/v001/P00_QC/bag_decoder_snapshot.py'
    spec=importlib.util.spec_from_file_location('dynamic_bag_decoder',decoder)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    con,msgs=mod.load_bag(bag)
    dec={cid:mod.Decoder(c['type'],c['definition']) for cid,c in con.items()
         if c['topic'] in [f'/{car}/{kind}' for car in CARS for kind in ('odom','imu','uwb/ranges')]}
    streams={car:{'odom':[],'imu':[],'uwb':collections.defaultdict(list)} for car in CARS}
    availability=0;last=0;rejected=collections.Counter()
    with gzip.open(out/'sensor_records.jsonl.gz','xt',encoding='utf-8') as sink:
        for idx,(cid,rt,payload) in enumerate(msgs):
            availability=max(availability,rt);last=max(last,rt)
            if cid not in dec:continue
            topic=con[cid]['topic'];car=topic.split('/')[1];kind=topic.split('/')[2]
            m=dec[cid].decode(payload,con[cid]['type'])
            h=m['header'];header=h['stamp']['secs']*NS+h['stamp']['nsecs']
            row=dict(record_index=idx,topic=topic,receive_epoch_ns=rt,availability_epoch_ns=availability,
                     header_epoch_ns=header,frame_id=h['frame_id'])
            if kind=='odom':
                p=m['pose']['pose']['position'];q=m['pose']['pose']['orientation']
                yaw=math.atan2(2*(q['w']*q['z']+q['x']*q['y']),1-2*(q['y']**2+q['z']**2))
                value=[p['x'],p['y'],yaw]
                if not all(math.isfinite(v) for v in value):rejected['odom_nonfinite']+=1;continue
                streams[car]['odom'].append((rt,availability,idx,value));row['value']=value
            elif kind=='imu':
                value=[m['angular_velocity'][k] for k in ('x','y','z')]
                if h['frame_id']!=car+'/gyro_link' or m['angular_velocity_covariance'][0]==-1 or not all(math.isfinite(v) for v in value):
                    rejected['imu_unusable']+=1;continue
                streams[car]['imu'].append((rt,availability,idx,value[2]));row['value']=value
            else:
                value={}
                for link in m['ranges']:
                    r=float(link['range'])
                    if math.isfinite(r) and r>0:
                        key=link['anchor_id'];value[key]=r
                        streams[car]['uwb'][key].append((rt,availability,idx,r))
                row['value']=value
            sink.write(json.dumps(row,allow_nan=False)+'\n')
    del msgs
    for car in CARS:
        for kind in ('imu','odom'):streams[car][kind].sort()
        for values in streams[car]['uwb'].values():values.sort()
    times={}
    for line in Path(str(bag)+'.events.txt').read_text().splitlines():
        stamp,label=line.split(' ',1);times[label]=int(Decimal(stamp)*NS)
    begin=times[case+'_START_STABLE_BEGIN'];first=((begin+5*NS+NS-1)//NS)*NS
    cfg=read(PROJECT/'outputs/static_benefit_development_20261031/v001/run002/P00_NORMAL/config.json')
    protocol=read(HERE/'protocol.json');cfg['scope']='field_dynamic_conditional_development'
    cfg['adapter']=protocol;cfg['extensions']['imu']='enabled_gyro_bias';cfg['replay']['imu']='gyro+bias replaces angular odom factor'
    cfg['angular']={}
    angular=read(SNAP/'tools/single_car_imu_fgo/config.template.json')['angular']
    keys={};audit={'bag_path':str(bag),'bag_sha256':receipt['bag_sha256'],'initialization':{},'rejected':dict(rejected)}
    for car in CARS:
        for kind in ('imu','odom'):keys[(car,kind)]=[x[0] for x in streams[car][kind]]
        for link,vs in streams[car]['uwb'].items():keys[(car,link)]=[x[0] for x in vs]
    def select(car,kind,start,end,cutoff):
        data=streams[car][kind] if kind in ('imu','odom') else streams[car]['uwb'].get(kind,[])
        ts=keys.get((car,kind),[])
        return [r for r in data[bisect.bisect_left(ts,start):bisect.bisect_right(ts,end)] if r[1]<=cutoff]
    for car in CARS:
        m=cfg['models'][car];m['base_to_antenna_body_xy_m']=protocol['lever_arms_body_xy_m'][car]
        anchors=m['anchors_xyz_m'];init={k:select(car,k,begin,begin+5*NS,first) for k in anchors}
        if any(len(v)<5 for v in init.values()):raise ValueError('Insufficient initial four-wall data')
        med={k:float(np.median([r[3] for r in vs])) for k,vs in init.items()}
        def fun(x):return [np.linalg.norm(np.r_[x,m['antenna_height_m']]-a)-med[k] for k,a in anchors.items()]
        fit=least_squares(fun,np.mean(np.array(list(anchors.values()))[:,:2],axis=0))
        if not fit.success or not np.isfinite(fit.x).all():raise ValueError('Range initialization failed')
        m['start_antenna_xyz_m']=[*fit.x.tolist(),m['antenna_height_m']];m['initial_heading_deg']=0.
        m['range_bias_m']={k:0. for k in anchors}
        cfg['angular'][car]=copy.deepcopy(angular)
        cfg['angular'][car]['imu_frame_id'].update(value=car+'/gyro_link',source='actual recorded frame')
        cfg['angular'][car]['body_z_in_imu_frame'].update(source='conditional published-Z engineering assumption',source_kind='engineering_assumption')
        audit['initialization'][car]={'antenna_xy_m':fit.x.tolist(),'reference_coordinates_used':False,'wall_medians_m':med,'n':{k:len(v) for k,v in init.items()}}
    bins=[];prev=None;skipped=0
    for state in range(first,(last//NS)*NS,NS):
        cutoff=state+NS
        if cutoff>last:break
        local=[];deps=[];ages={}
        for car in CARS:
            sample=select(car,'odom',state-500000000,state,cutoff)
            if not sample:break
            r=sample[-1];local.append(r[3]);deps.append(r[1]);ages[car]=(state-r[0])/NS
        if len(local)!=2:
            bins.append(dict(state_ns=state,cutoff_ns=cutoff,skip_reason='missing_fresh_odom'));skipped+=1;continue
        wall={};counts={};peer=None
        for car in CARS:
            wall[car]={};counts[car]={}
            for k in cfg['models'][car]['anchors_xyz_m']:
                rs=select(car,k,state-400000000,state+400000000,cutoff);counts[car][k]=len(rs)
                if len(rs)>=5:wall[car][k]=float(np.median([r[3] for r in rs]));deps.extend(r[1] for r in rs)
        rs=select('car1','node_0',state-400000000,state+400000000,cutoff)
        if len(rs)>=5:peer=float(np.median([r[3] for r in rs]));deps.extend(r[1] for r in rs)
        intervals=None
        if prev is not None:
            intervals={}
            for car in CARS:
                buf=pinned.integration.AngularBuffer(100000000,512)
                for rt,av,idx,rate in select(car,'imu',prev-100000000,state,cutoff):
                    buf.add(dict(mapped_header_epoch_ns=rt,receive_epoch_ns=av,record_index=idx,topic='/'+car+'/imu'),rate)
                intervals[car]=buf.integrate(prev,state,cutoff)
                deps.extend(s['dependency']['receive_epoch_ns'] for s in intervals[car]['segments'])
        assert not deps or max(deps)<=cutoff
        bins.append(dict(state_ns=state,cutoff_ns=cutoff,second=(state-first)/NS,local=local,wall=wall,peer=peer,
                         intervals=intervals,counts=counts,odom_age_s=ages,dependency_max_ns=max(deps)))
        prev=state
    moving=1 if case=='A1' else 0
    positions=np.array([b['local'][moving][:2] for b in bins if 'local' in b])
    audit.update(first_state_ns=first,last_receipt_ns=last,frames=len(bins),skipped_odom=skipped,
                 observed_odom_xy_excursion_m=float(np.max(np.linalg.norm(positions-positions[0],axis=1))),
                 clock='receipt association, not physical sample time',dynamic_use='conditional development only')
    if audit['observed_odom_xy_excursion_m']<.5:raise ValueError('Motion was not preserved')
    write(out/'config.json',cfg);write(out/'input_audit.json',audit)
    with gzip.open(out/'bins.jsonl.gz','xt',encoding='utf-8') as f:
        for b in bins:f.write(json.dumps(b,allow_nan=False)+'\n')
    write(out/'INPUT_LOCK.json',{str(p):sha(p) for p in (HERE/'protocol.json',Path(__file__),out/'config.json',out/'bins.jsonl.gz',decoder,SNAP/'tools/two_car_imu_fgo/core.py')})
    print(json.dumps({'prepared':case,**audit}),flush=True)

def run(case,method):
    base=HERE/case;out=base/method;out.mkdir(exist_ok=False)
    cfg=read(base/'config.json')
    with gzip.open(base/'bins.jsonl.gz','rt',encoding='utf-8') as f:bins=[json.loads(l) for l in f]
    graph=WeightedGraph(cfg) if method=='M3W025' else core.WindowGraph(cfg,method=='M3')
    started=time.monotonic();rows=[]
    with gzip.open(out/'updates.jsonl.gz','xt',encoding='utf-8') as sink:
        for i,b in enumerate(bins):
            if time.monotonic()-started>1200:raise TimeoutError('Development cell limit1200s')
            if 'skip_reason' in b:
                row=dict(state_ns=b['state_ns'],cutoff_ns=b['cutoff_ns'],status=b['skip_reason'],pose=None,valid={c:False for c in CARS})
            else:
                graph.next_intervals=b['intervals']
                r=graph.update(b['second'],b['local'],b['wall'],b['peer'])
                row=dict(state_ns=b['state_ns'],cutoff_ns=b['cutoff_ns'],status=r['status'],pose=r['pose'],valid=r['estimate_valid'],accepted=r['accepted_graph'])
                sink.write(json.dumps({'state_ns':b['state_ns'],'result':r},allow_nan=False)+'\n')
            rows.append(row)
            if (i+1)%100==0:print(json.dumps({'case':case,'method':method,'done':i+1,'total':len(bins)}),flush=True)
    write(out/'trajectory.json',rows)
    write(out/'summary.json',dict(case=case,method=method,elapsed_s=time.monotonic()-started,frames=len(rows),
          accepted=sum(r.get('accepted',False) for r in rows),valid={c:sum(r['valid'][c] for r in rows) for c in CARS},
          statuses=dict(collections.Counter(r['status'] for r in rows)),marginalizations=graph.marginalizations,
          inputs_sha256=sha(base/'bins.jsonl.gz'),config_sha256=sha(base/'config.json'),script_sha256=sha(__file__)))
    print(json.dumps(read(out/'summary.json')),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run']);p.add_argument('case',choices=['A1','B1']);p.add_argument('--method',choices=['M2','M3','M3W025']);a=p.parse_args()
    if a.action=='prepare':prepare(a.case)
    else:
        if not a.method:p.error('--method required')
        run(a.case,a.method)
