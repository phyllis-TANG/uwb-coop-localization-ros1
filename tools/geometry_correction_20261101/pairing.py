"""Independent primitive, rigid geometry, processing and sensor-init readback."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from local_support import CARS,EPOCH,dump,lines,protocol,sha

def design(t,car,p):
    pts=p['trajectory']['trajectories'][car]
    for a,b in zip(pts,pts[1:]):
        if t<=b['t_s']:
            u=(t-a['t_s'])/(b['t_s']-a['t_s']);s=u*u*(3-2*u)
            return np.array([(1-s)*a['antenna_xy_m'][j]+s*b['antenna_xy_m'][j] for j in (0,1)])
    raise ValueError('Design time')

def read_initial(case,p,primitive):
    cfg=json.loads((case/'config.json').read_text());receipt=json.loads((case/'INITIALIZATION.json').read_text());events=list(lines(case/'startup_events.jsonl.gz'))
    if max(e['receive_epoch_ns'] for e in events)>EPOCH+6_050_000_000:raise ValueError('Initializer future data')
    for car in CARS:
        m=cfg['models'][car];r=receipt['cars'][car];z=primitive[car+'_initial'];heading=math.radians(2)*z[2]
        od={e['header_epoch_ns']:e['value']['pose'] for e in events if e['vehicle_id']==car and e['kind']=='odom' and e['header_epoch_ns']<=EPOCH+6*10**9}
        gy={e['header_epoch_ns']:e['value']['angular_velocity_rad_s'][2] for e in events if e['vehicle_id']==car and e['kind']=='imu'}
        motion={EPOCH:([0.,0.],heading)};x=y=0.;a=heading
        for i in range(1,121):
            before=EPOCH+(i-1)*50_000_000;now=EPOCH+i*50_000_000;o0,o1=od[before],od[now];dx=o1[0]-o0[0];dy=o1[1]-o0[1]
            bx=math.cos(o0[2])*dx+math.sin(o0[2])*dy;by=-math.sin(o0[2])*dx+math.cos(o0[2])*dy
            x+=math.cos(a)*bx-math.sin(a)*by;y+=math.sin(a)*bx+math.cos(a)*by;a+=gy[before]*.05
            motion[now]=([x,y],a)
        observations=[e for e in events if e['kind']=='uwb' and e['vehicle_id']==car and e['header_epoch_ns']<EPOCH+5*10**9]
        if len(observations)!=100:raise ValueError('Initializer window/count')
        px,py=r['fit_base_at_t0_xy_m'];lx,ly=m['base_to_antenna_body_xy_m'];cost=gx=gyv=0.
        for e in observations:
            (dx,dy),angle=motion[e['header_epoch_ns']];xx=px+dx+math.cos(angle)*lx-math.sin(angle)*ly;yy=py+dy+math.sin(angle)*lx+math.cos(angle)*ly
            for key in p['wall_nodes']:
                ax,ay,az=m['anchors_xyz_m'][key];rho=math.dist([xx,yy,m['antenna_height_m']],[ax,ay,az]);res=rho-e['value'][key]
                cost+=res*res/2;gx+=res*(xx-ax)/rho;gyv+=res*(yy-ay)/rho
        if abs(cost-r['cost'])>1e-8*max(1.,cost) or math.hypot(gx,gyv)>1e-3:raise ValueError('Initializer objective/stationarity')
        prior=[px+.08*z[0]+x+math.cos(a)*lx-math.sin(a)*ly,py+.08*z[1]+y+math.sin(a)*lx+math.cos(a)*ly]
        if not np.allclose(prior,m['start_antenna_xyz_m'][:2],atol=1e-11,rtol=0) or abs(a-math.radians(m['initial_heading_deg']))>1e-12:raise ValueError('Initializer prior reconstruction')
        if r['initial_standard_normal_primitive']!=z.tolist():raise ValueError('Initial primitive changed')
    return True

def check(seed_root):
    root=Path(seed_root);p=protocol();seed=int(root.name);bundle=json.loads((root/'PRIMITIVES.json').read_text());pr=np.load(root/'primitives.npz')
    if sha(root/'primitives.npz')!=bundle['file_sha256']:raise ValueError('Primitive container SHA')
    rng=np.random.default_rng(seed);draws=[rng.normal(size=1921)]
    for car in CARS:
        draws.extend([rng.normal(size=3),rng.normal(size=(1920,3)),rng.normal(size=1921),rng.normal(size=(1921,4)),
                      rng.normal(0,.04,1921),rng.normal(0,.0007*math.sqrt(.05),1920),rng.normal(0,.006,1921)])
    for call,expected in zip(bundle['calls'],draws,strict=True):
        value=pr[call['name']]
        if not np.array_equal(value,expected) or hashlib.sha256(value.tobytes()).hexdigest()!=call['array_sha256']:raise ValueError('Random primitive pairing/reproduction')
    underlying={g:list(lines(root/(g+'-underlying.jsonl.gz'))) for g in ('G1','G2')};measures=0;inits=0;car1_prior=[]
    for g in ('G1','G2'):
        cfg=json.loads((root/(g+'-raw')/'config.json').read_text())
        for a,b in zip(underlying['G1'],underlying[g],strict=True):
            if (a['kind'],a['vehicle_id'],a['record_index'],a['header_epoch_ns'],a['receive_epoch_ns'])!=(b['kind'],b['vehicle_id'],b['record_index'],b['header_epoch_ns'],b['receive_epoch_ns']):raise ValueError('Paired clocks/IDs')
            if b['kind'] in ('odom','imu') and a['value']!=b['value']:raise ValueError('Translation changed measured odom/gyro')
            if b['kind']!='uwb':continue
            t=(b['header_epoch_ns']-EPOCH)/1e9;i=int(round(t*20));car=b['vehicle_id'];model=cfg['models'][car]
            positions={c:np.r_[design(t,c,p)+(np.array(p['geometry_translation_m'][g]) if c=='car2' else 0),cfg['models'][c]['antenna_height_m']] for c in CARS}
            for j,key in enumerate(sorted(p['wall_nodes'])):
                expected=math.dist(positions[car],model['anchors_xyz_m'][key])+.04*pr[car+'_iid_wall'][i,j]
                if car=='car2':expected+=dict(zip(p['wall_nodes'],p['bias_vector_m']))[key]
                if abs(b['value'][key]-expected)>2e-12:raise ValueError('Wall primitive or placement recomputation')
                measures+=1
            peer='node_0' if car=='car1' else 'node_1';expected=math.dist(positions['car1'],positions['car2'])+pr[car+'_peer'][i]
            if abs(b['value'][peer]-expected)>2e-12:raise ValueError('Peer geometry/primitive')
            measures+=1
        for processing in ('raw','historical'):
            case=root/(g+'-'+processing);read_initial(case,p,pr);inits+=2
            cfg=json.loads((case/'config.json').read_text());car1_prior.append(cfg['models']['car1'])
            online=list(lines(case/'events.jsonl.gz'));base={e['record_index']:e for e in underlying[g]}
            for e in online:
                if e['kind']=='clock':continue
                b=base[e['record_index']]
                for key,value in b['value'].items():
                    corrected=e['kind']=='uwb' and e['vehicle_id']=='car2' and key in p['wall_nodes'] and processing=='historical'
                    expected=value-dict(zip(p['wall_nodes'],p['bias_vector_m']))[key] if corrected else value
                    if e['value'][key]!=expected:raise ValueError('Processing modified extra measurements')
                if e['header_epoch_ns']<EPOCH+5*10**9 or e['availability_epoch_ns']!=max(e['receive_epoch_ns'],EPOCH+6_050_000_000):raise ValueError('Online cutoff/filter')
    if any(v!=car1_prior[0] for v in car1_prior[1:]):raise ValueError('Car1 prior changed by geometry/processing')
    return dict(status='PASS',seed=seed,random_arrays=15,primitive_file_sha256=sha(root/'primitives.npz'),measurement_geometry_checks=measures,initializers_independently_checked=inits,
        shared_odom_gyro_initial_primitives=True,Car1_trajectory_and_initializer_invariant=True,no_true_position_in_initializer=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('No overwrite')
    r=check(a.input);dump(a.output,r);print(json.dumps(r))
