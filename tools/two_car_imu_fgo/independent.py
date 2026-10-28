"""Independent scalar equations and receipt support reader, no online imports.

Shares JSON/config definitions and numpy linear algebra only. FD differentiates
these scalar equations, never the production residual or analytic Jacobian.
"""
import bisect
import copy
import gzip
import hashlib
import json
import math
from pathlib import Path
import numpy as np

CARS=('car1','car2')

def lines(path):
    with (gzip.open(path,'rt') if str(path).endswith('.gz') else open(path)) as f:return [json.loads(s) for s in f if s.strip()]
def require(ok,message):
    if not ok:raise ValueError(message)
def wrap(v):return math.atan2(math.sin(v),math.cos(v))
def ant(p,m):
    lx,ly=m['base_to_antenna_body_xy_m'];c,s=math.cos(p[2]),math.sin(p[2])
    return np.array([p[0]+c*lx-s*ly,p[1]+s*lx+c*ly,m['antenna_height_m']])
def body(a,b):
    dx,dy=b[0]-a[0],b[1]-a[1];c,s=math.cos(a[2]),math.sin(a[2])
    return np.array([c*dx+s*dy,-s*dx+c*dy])
def robust(p,z,sigma):
    e=(p-z)/sigma;return e*math.sqrt(2/(math.hypot(1,e)+1))


def residual(snapshot,states,config,d):
    x=np.asarray(states).reshape(-1,d);stride=d//2;prior=snapshot['prior']
    delta=x[0]-np.asarray(prior['point']);delta[[2,stride+2]]=np.arctan2(np.sin(delta[[2,stride+2]]),np.cos(delta[[2,stride+2]]))
    r=list(np.asarray(prior['matrix']).reshape(-1,d)@delta+prior['offset']);local=np.asarray(snapshot['local'])
    for k,t in enumerate(snapshot['times_s']):
        for i,c in enumerate(CARS):
            m=config['models'][c];p=m['graph_parameters'];state=x[k,i*stride:(i+1)*stride]
            if k:
                prev=x[k-1,i*stride:(i+1)*stride];dt=t-snapshot['times_s'][k-1]
                r.extend((body(prev,state)-body(local[k-1,i],local[k,i]))/(p['odom_translation_sigma_m']*math.sqrt(dt)))
                if d==6:r.append(wrap(state[2]-prev[2]-wrap(local[k,i,2]-local[k-1,i,2]))/(math.radians(p['odom_yaw_sigma_deg'])*math.sqrt(dt)))
                else:
                    a=snapshot['intervals'][k-1][c];params=config['angular'][c];qg=params['angle_noise_density_rad_sqrt_s']['value']**2;qb=params['bias_random_walk_rad_s_sqrt_s']['value']**2
                    if a['valid']:
                        e=[wrap(state[2]-prev[2]-a['raw_angle_rad']+prev[3]*dt),state[3]-prev[3]]
                        S=np.array([[qg*dt+qb*dt**3/3,-qb*dt**2/2],[-qb*dt**2/2,qb*dt]])
                        r.extend(np.linalg.solve(np.linalg.cholesky(S),e))
                    else:r.append((state[3]-prev[3])/math.sqrt(qb*dt))
            point=ant(state,m)
            for key,z in sorted(snapshot['observations'][k][c].items()):
                r.append(robust(np.linalg.norm(point-m['anchors_xyz_m'][key]),z-m['range_bias_m'][key],p['range_sigma_m']))
        if snapshot['peer_enabled'] and snapshot['peers_m'][k] is not None:
            r.append(robust(np.linalg.norm(ant(x[k,:stride],config['models']['car1'])-ant(x[k,stride:],config['models']['car2'])),snapshot['peers_m'][k],config['peer']['sigma_m']))
    return np.array(r)


def incident(detail,enabled):
    return dict(times_s=detail['times_s'],states=detail['states'],local=detail['local'],
        observations=[detail['old_observations'],{c:{} for c in CARS}],peers_m=[detail['old_peer_m'],None],
        intervals=detail.get('intervals'),prior=detail['before'],peer_enabled=enabled)


def marginal(detail,config,d,enabled):
    snap=incident(detail,enabled);x=np.asarray(snap['states']).ravel()
    fun=lambda x:residual(snap,x,config,d);r=fun(x);j=[]
    for i in range(len(x)):
        h=np.zeros_like(x);h[i]=1e-6;j.append((fun(x+h)-fun(x-h))/2e-6)
    j=np.array(j).T;a,b=j[:,:d],j[:,d:]
    # Projection with SVD least squares permits genuine rank deficiency.
    jp=b-a@np.linalg.lstsq(a,b,rcond=None)[0];rp=r-a@np.linalg.lstsq(a,r,rcond=None)[0]
    M=np.asarray(detail['after']['matrix']).reshape(-1,d);o=np.asarray(detail['after']['offset'])
    H=M.T@M;g=M.T@o;want=jp.T@jp;grad=jp.T@rp
    require(np.allclose(H,want,atol=1e-5,rtol=1e-8),'Schur information/cross')
    require(np.allclose(g,grad,atol=1e-6,rtol=1e-8),'Schur affine')
    err=abs(o@o+detail['constant']-rp@rp);require(err<1e-6,'Schur constant')
    return dict(h_abs=float(np.max(abs(H-want))),g_abs=float(np.max(abs(g-grad))),constant_abs=float(err),
        cross=float(np.linalg.norm(H[:d//2,d//2:])),bias_cross=None if d==6 else float(np.linalg.norm(H[[3,7]][:,[0,1,2,4,5,6]])))


def mapped(e,config):
    policy=config['clock_policy'][e['vehicle_id']][e['kind']]['kind']
    return e['receive_epoch_ns'] if policy=='bag_receipt_association' else e['header_epoch_ns']


def controls(events,config):
    out={c:[] for c in CARS};last={c:None for c in CARS}
    for e in events:
        if e['kind']!='imu':continue
        c=e['vehicle_id'];v=e['value'];a=config['angular'][c];t=mapped(e,config)
        if v.get('units')!='rad/s' or v.get('frame_id')!=a['imu_frame_id']['value']:continue
        vec=v.get('angular_velocity_rad_s')
        if not isinstance(vec,list) or len(vec)!=3 or not all(math.isfinite(x) for x in vec):continue
        if t>e['receive_epoch_ns'] or (last[c] is not None and t<=last[c]):continue
        row=copy.deepcopy(e);row['mapped_header_epoch_ns']=t;row['rate']=sum(x*y for x,y in zip(vec,a['body_z_in_imu_frame']['value']));out[c].append(row);last[c]=t
    return out


def edge_check(edge,control,cutoff,hold):
    eligible=[e for e in control if e['receive_epoch_ns']<=cutoff];ts=[e['mapped_header_epoch_ns'] for e in eligible]
    cursor=edge['start_epoch_ns'];end=edge['end_epoch_ns'];segments=[];gaps=[];integral=0.
    while cursor<end:
        i=bisect.bisect_right(ts,cursor)-1;next_t=ts[i+1] if i+1<len(ts) else end
        if i<0 or cursor>=ts[i]+hold:
            stop=min(end,next_t);gaps.append((cursor,stop));cursor=stop;continue
        stop=min(end,next_t,ts[i]+hold);segments.append((cursor,stop,eligible[i]));integral+=eligible[i]['rate']*(stop-cursor)/1e9;cursor=stop
    require(gaps==[(g['start_epoch_ns'],g['end_epoch_ns']) for g in edge['gaps']],'gyro gaps')
    require(len(segments)==len(edge['segments']),'gyro support count')
    for (a,b,e),s in zip(segments,edge['segments']):
        require((a,b)==(s['start_epoch_ns'],s['end_epoch_ns']) and b-a==s['dt_ns'],'gyro partition')
        for k in ('record_index','header_epoch_ns','receive_epoch_ns','source_file_sha256','topic','raw_message_sha256','mapped_header_epoch_ns'):
            require(s['dependency'][k]==e.get(k),'gyro source identity '+k)
        require(abs(s['rate_rad_s']-e['rate'])<1e-12 and abs(s['angle_rad']-e['rate']*(b-a)/1e9)<1e-12,'gyro units/sign/integral')
    require(abs(integral-edge['partial_angle_rad'])<1e-12,'gyro total')
    require(edge['valid']==(not gaps),'gyro validity')
    require(abs(edge['raw_angle_rad']-integral)<1e-12 if not gaps else edge['raw_angle_rad'] is None,'gap falsely integrated')
    return len(segments)


def bins_check(row,events,config,origin):
    cutoff=row['availability_cutoff_epoch_ns'];t=row['state_time_s'];state=row['state_epoch_ns'];half=config['replay']['range_bin_half_width_s']
    for c in CARS:
        selected=[e for e in events if e.get('vehicle_id')==c and e['kind']=='uwb' and e['receive_epoch_ns']<=cutoff and e.get('representation')=='bridge' and abs((mapped(e,config)-origin)/1e9-t)<=half]
        grouped={k:[] for k in config['models'][c]['anchors_xyz_m']};ps=[];ids=[];peer_key='node_0' if c=='car1' else 'node_1'
        for e in selected:
            for k,v in e['value'].items():
                if not isinstance(v,(float,int)) or not math.isfinite(v) or v<=0:continue
                if k in grouped and v-config['models'][c]['range_bias_m'][k]>0:grouped[k].append(v)
                if k==peer_key:ps.append(v);ids.append(e['source_observation_id'])
        want={k:float(np.median(v)) for k,v in grouped.items() if len(v)>=5}
        require(want==row['bins'][c]['observations'],'wall objective input differs from raw receive prefix')
        require({k:len(v) for k,v in grouped.items()}==row['bins'][c]['sample_counts'],'wall supports')
        target='peer_median_m' if c=='car1' else 'reverse_peer_median_m'
        require((float(np.median(ps)) if len(ps)>=5 else None)==row[target],'peer aggregation')
        deps=row['peer_dependencies' if c=='car1' else 'reverse_diagnostic_dependencies']
        require(ids==[p['identity']['source_observation_id'] for p in deps],'peer identities')
        odom=[e for e in events if e.get('vehicle_id')==c and e['kind']=='odom' and e['receive_epoch_ns']<=cutoff]
        ts=[mapped(e,config) for e in odom];values=np.array([e['value']['pose'] for e in odom],float)
        for i in range(1,len(values)):values[i,2]=values[i-1,2]+wrap(values[i,2]-values[i-1,2])
        k=bisect.bisect_left(ts,state)
        if k<len(ts) and ts[k]==state:want=values[k]
        elif k==0 or k==len(ts):want=None
        else:
            ratio=((state-origin)/1e9-(ts[k-1]-origin)/1e9)/((ts[k]-origin)/1e9-(ts[k-1]-origin)/1e9)
            want=values[k-1]+ratio*(values[k]-values[k-1])
        actual=row['bins'][c]['local_odom']
        require(actual is None if want is None else actual is not None and np.allclose(actual,want,atol=3e-12,rtol=1e-13),'odom interpolation/cutoff')


def audit_run(root,events_path,all_marginals=True):
    root=Path(root);meta=json.loads((root/'run.json').read_text());config=json.loads((root/'config.json').read_text())
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    require(meta['status']=='DONE','run status');require(sha(events_path)==meta['input_sha256'],'input SHA')
    for name,digest in meta['outputs'].items():require(sha(root/name)==digest,'output SHA '+name)
    events=lines(events_path);rows=lines(root/'updates.jsonl.gz');controls_by_car=controls(events,config);d=8 if meta['method_id'] in ('M2','M3') else 6;stride=d//2
    seen=set();history={};prior=None;counts=dict(publications=0,objectives=0,angular_intervals=0,segments=0,marginalizations=0,bins=0)
    maxcost=0.;margin=[];previous=None;previous_ns=None
    for row in rows:
        counts['publications']+=1;state=row['state_epoch_ns'];cutoff=row['availability_cutoff_epoch_ns']
        require(type(state) is int and type(cutoff) is int and cutoff-state==10**9,'integer publication/wait')
        require(cutoff<=events[-1]['receive_epoch_ns'],'future EOF')
        if previous_ns is not None:require(state-previous_ns==10**9,'omitted common keyframes')
        previous_ns=state;bins_check(row,events,config,meta['epoch_origin_ns']);counts['bins']+=1
        snap=row['snapshot'];require(len(snap['times_s'])<=21 and row['scalar_variables']==len(snap['times_s'])*d,'scalar/window bound')
        if row['pose'] is not None:
            if d==6:require(row['bias_rad_s']=={c:None for c in CARS},'absent bias must null')
            else:
                for i,c in enumerate(CARS):require(row['bias_rad_s'][c]==row['pose'][4*i+3],'zero bias output invalid')
        current=row.get('angular_intervals')
        if d==8 and current:
            for i,c in enumerate(CARS):
                edge=current[c];counts['angular_intervals']+=1
                require(edge['start_epoch_ns']==meta['epoch_origin_ns']+round(snap['times_s'][-2]*1e9) if len(snap['times_s'])>=2 else True,'angular state binding')
                counts['segments']+=edge_check(edge,controls_by_car[c],cutoff,config['angular'][c]['max_hold_ns']['value'])
                if previous is not None:
                    want=previous[4*i+2]+(edge['raw_angle_rad']-previous[4*i+3]*(edge['dt_ns']/1e9) if edge['valid'] else 0.)
                    require(abs(wrap(row['prediction_pose'][4*i+2]-want))<1e-10,'hidden odom yaw prediction')
                require(row['odom_yaw_fallback'] is False,'gyro odom fallback')
        if row['pose'] is not None:previous=row['pose']
        history[row['state_time_s']]=row
        for t,obs,lo,peer in zip(snap['times_s'],snap['observations'],snap['local'],snap['peers_m']):
            require(obs=={c:history[t]['bins'][c]['observations'] for c in CARS},'retained wall changed')
            require(lo==[history[t]['bins'][c]['local_odom'] for c in CARS],'retained translation changed')
            if snap['peer_enabled']:require(peer==history[t]['peer_median_m'],'retained peer changed')
            elif d==8:require(peer is None,'independent graph consumed peer')
        for item in row['marginalization_details']:
            t0,t1=item['times_s'];require(t0 not in seen,'old factor repeated');seen.add(t0);counts['marginalizations']+=1
            require(item['old_observations']=={c:history[t0]['bins'][c]['observations'] for c in CARS},'marginal old wall')
            if d==8:require(item['intervals']==[history[t1]['angular_intervals']],'marginal angle support changed')
            if prior is not None:require(item['before']==prior,'prior lineage lost/duplicated')
            prior=item['after']
            if all_marginals:margin.append(marginal(item,config,d,snap['peer_enabled']))
        if prior is not None:require(snap['prior']==prior,'current full prior differs')
        require(row['marginalizations']==len(seen),'missing marginalization record')
        if row['accepted_graph']:
            r=residual(snap,snap['states'],config,d);err=abs(r@r/2-row['optimizer']['cost']);require(err<1e-7,'full objective/actual factor cost')
            maxcost=max(maxcost,err);counts['objectives']+=1
        require(row['peer_factor_used']==bool(snap['peer_enabled'] and row['peer_median_m'] is not None and row['state_time_s'] in snap['times_s']),'peer applied identity')
    return dict(status='PASS',counts=counts,max_cost_abs=float(maxcost),max_h_abs=max((m['h_abs'] for m in margin),default=0),
        max_g_abs=max((m['g_abs'] for m in margin),default=0),max_constant_abs=max((m['constant_abs'] for m in margin),default=0),
        marginalizations_FD_checked=len(margin),all_marginalizations_FD_checked=all_marginals,online_optimizer_or_Jacobian_imported=False)
