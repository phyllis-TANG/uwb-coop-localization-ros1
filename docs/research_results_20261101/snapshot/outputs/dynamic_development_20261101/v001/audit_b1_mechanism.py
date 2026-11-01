import dynamic_compare as d
import gzip,json,math
import numpy as np
OUT=d.HERE/'anomaly_audit001';OUT.mkdir(exist_ok=True)
base=d.HERE/'B1';cfg=d.read(base/'config.json')
with gzip.open(base/'bins.jsonl.gz','rt',encoding='utf-8') as f:bins=[json.loads(l) for l in f]
rows={m:d.read(base/m/'trajectory.json') for m in ('M2','M3','M3W025')}
select=set([20,100,200,215,235,250,300,350,364,400,450,483,500,528])
saved={};margins=[]
with gzip.open(base/'M3W025/updates.jsonl.gz','rt',encoding='utf-8') as f:
    for i,l in enumerate(f):
        r=json.loads(l)['result']
        if i in select:saved[i]=r;margins.extend((i,a) for a in r['marginalization_details'])
inputs=[]
for start,end in ((0,200),(200,240),(240,350),(350,480),(480,530)):
    record={'indices':[start,end],'cars':{}}
    for car in d.CARS:
        c=d.CARS.index(car);vs=[b['intervals'][car] for b in bins[start+1:end+1]]
        vals=np.array([v['raw_angle_rad'] for v in vs if v['valid']]);odom=np.array([b['local'][c] for b in bins[start:end+1]])
        record['cars'][car]={'valid_angles':len(vals),'gaps':[start+1+i for i,v in enumerate(vs) if not v['valid']],
           'angle_sum_rad':float(vals.sum()),'angle_min_max': [float(vals.min()),float(vals.max())],
           'odom_yaw_delta_rad':float(np.unwrap(odom[:,2])[-1]-np.unwrap(odom[:,2])[0]),'odom_xy_displacement_m':(odom[-1,:2]-odom[0,:2]).tolist(),
           'estimated_yaw_end_rad':{m:rows[m][end]['pose'][4*c+2] for m in rows}}
    inputs.append(record)
schur=[]
for i,a in margins:
    prior=d.core.Prior(**{k:np.array(v) for k,v in a['before'].items()})
    obj=d.WeightedObjective(a['times_s'],a['local'],[a['old_observations'],{c:{} for c in d.CARS}],[a['old_peer_m'],None],a['intervals'],cfg,prior,True)
    r,J=obj.evaluate(np.array(a['states']).ravel());A=J[:,:8];B=J[:,8:]
    # independent SVD column-space projection, not the original pivoted QR
    U,s,V=np.linalg.svd(A,full_matrices=False);tol=max(A.shape)*np.finfo(float).eps*s[0];U=U[:,s>tol]
    projected=B-U@(U.T@B);residual=r-U@(U.T@r)
    M=np.array(a['after']['matrix']);v=np.array(a['after']['offset'])
    H=projected.T@projected;g=projected.T@residual
    h_err=float(np.linalg.norm(H-M.T@M)/max(1.,np.linalg.norm(H)))
    g_err=float(np.linalg.norm(g-M.T@v)/max(1.,np.linalg.norm(g)))
    cost_err=abs(float(residual@residual-v@v)-a['constant'])
    assert h_err<1e-8 and g_err<1e-8 and cost_err<1e-7,(i,h_err,g_err,cost_err)
    schur.append(dict(index=i,H_relative_error=h_err,g_relative_error=g_err,constant_abs_error=cost_err))
objectives=[]
for i,r in saved.items():
    if not r['accepted_graph']:continue
    n=r['graph_states'];bb=bins[i-n+1:i+1];prior=d.core.Prior(**{k:np.array(v) for k,v in r['prior'].items()})
    obj=d.WeightedObjective([b['second'] for b in bb],[b['local'] for b in bb],[b['wall'] for b in bb],[b['peer'] for b in bb],[b['intervals'] for b in bb[1:]],cfg,prior,True)
    x=np.array(r['candidate_states']).ravel();res,J=obj.evaluate(x)
    cost=float(res@res/2);assert abs(cost-r['optimizer']['cost'])<1e-7
    cols=range(len(x)) if i in (250,400,500) else []
    err=0.
    for k in cols:
        off=np.zeros(len(x));off[k]=1e-6;fd=(obj.fun(x+off)-obj.fun(x-off))/(2e-6)
        err=max(err,float(np.max(np.abs(fd-J[:,k]))))
    assert err<1e-4,(i,err)
    # Position-reference-free comparison: same objective, fresh initial warmstart cost
    warm=np.array(r['optimizer_warmstart_states']).ravel()
    costs={'saved':cost,'warmstart':float(np.sum(obj.fun(warm)**2)/2)}
    objectives.append(dict(index=i,state_ns=bins[i]['state_ns'],weighted_yaw=r['pose'][2],xy=r['pose'][:2],costs=costs,
        jacobian_fd_columns=len(cols),jacobian_fd_max_abs_error=err,
        prior_yaw_point=prior.point[[2,6]].tolist(),state_minus_prior_oldest_yaw_rad=(x.reshape(-1,8)[0,[2,6]]-prior.point[[2,6]]).tolist()))
d.write(OUT/'AUDIT.json',{'inputs':inputs,'schur_checks':schur,'objective_checks':objectives,'scope':'saved-state objective reconstruction + SVD marginal checks + sampled full Jacobian finite difference, no refit'})
print(json.dumps({'inputs':inputs,'schur_max_H_error':max(x['H_relative_error'] for x in schur),'objective_checks':objectives}),flush=True)
