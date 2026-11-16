"""Frozen P-S1b diagnostic; no production backend or hardware access."""
import argparse
import csv
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / 'docs/research/midterm_simulation_s1b'
C = json.loads((DOC / 'CONFIG.json').read_text())
SCALE = np.array(C['state_scales'])
PRIOR = np.eye(25)[:4]
MOTION = np.zeros((20,25))
for i in range(20):
    MOTION[i,i], MOTION[i,i+4] = -1, 1


def design(geometry, motion):
    t = np.linspace(0,1,6)
    a = np.array([[0,0],[5,0],[5,5],[0,5.]], dtype=float) if geometry == 'good' else np.array([[-3,0],[-1,0],[4,0],[6,0.]], dtype=float)
    x = np.zeros((6,2,2))
    x[:,0] = [1,1 if geometry == 'good' else 0]
    x[:,1] = [2,2 if geometry == 'good' else 0]
    if geometry == 'near':
        a[:,1] = C['near_anchor_y']
        x[:,:,1] = C['near_initial_y']
    if motion == 'straight':
        x[:,:,0] += .5*t[:,None]
    if motion == 'turn':
        x[:,:,0] += (.5*np.sin(np.pi*t))[:,None]
        x[:,:,1] += (.5*(1-np.cos(np.pi*t)))[:,None]
    return a, np.r_[x.ravel(), C['bias_truth_m']]


def model(z, anchors, kind, peer_only=False):
    x = z[:24].reshape(6,2,2)
    d = x[:,:,None,:] - anchors[None,None,:,:]
    r = np.linalg.norm(d,axis=-1)
    dp = x[:,1] - x[:,0]
    rp = np.linalg.norm(dp,axis=-1)
    if np.min(r) <= 1e-12 or np.min(rp) <= 1e-12:
        raise ValueError('Non-differentiable zero range')
    v = np.concatenate([r.reshape(6,8),rp[:,None]],axis=1)
    j = np.zeros((6,9,25))
    for t in range(6):
        for c in range(2):
            j[t,4*c:4*c+4,4*t+2*c:4*t+2*c+2] = d[t,c]/r[t,c,:,None]
        j[t,8,4*t:4*t+2] = -dp[t]/rp[t]
        j[t,8,4*t+2:4*t+4] = dp[t]/rp[t]
    col = 0 if kind == 'wall' else 8
    v[:,col] += z[-1]
    j[:,col,-1] = 1
    if peer_only:
        return v[:,8], j[:,8]
    return v.ravel(), j.reshape(54,25)


def effective(a):
    p,q = a[:,:24],a[:,24]
    u,s,_ = np.linalg.svd(p,full_matrices=False)
    tol = s[0]*C['rank_rtol'] if len(s) else 0
    rank = int(np.sum(s>tol))
    qp = q-u[:,:rank]@(u[:,:rank].T@q)
    # Independent least-squares residual, no Tikhonov term.
    coef = np.linalg.lstsq(p,q,rcond=C['rank_rtol'])[0]
    info = float(qp@qp)
    return dict(position_rank=rank,position_singular_values=s.tolist(),position_threshold=float(tol),bias_information_m_minus2=info,bias_local_sigma_m=1/np.sqrt(info) if info>1e-18 else None,projection_lstsq_difference=float(abs(info-np.linalg.norm(q-p@coef)**2)))


def information(a):
    _,s,vh = np.linalg.svd(a*SCALE,full_matrices=True)
    tol = s[0]*C['rank_rtol']
    rank = int(np.sum(s>tol))
    n = vh[rank:].T
    physical = SCALE[:,None]*n
    result = dict(rank=rank,dimension=25,singular_values=np.pad(s,(0,25-len(s))).tolist(),rank_rtol=C['rank_rtol'],rank_absolute_threshold=float(tol),ranks_by_rtol={str(t):int(np.sum(s>s[0]*t)) for t in C['rank_sensitivity']},nullspace_scaled=n.tolist(),nullspace_physical=physical.tolist(),nullity=25-rank,bias_null_components_scaled=n[-1].tolist(),bias_null_components_physical=physical[-1].tolist(),bias_null_norm_scaled=float(np.linalg.norm(n[-1])),null_residual=float(np.linalg.norm(a@physical)),null_orthogonality_error=float(np.linalg.norm(n.T@n-np.eye(n.shape[1]))))
    result.update(effective(a))
    return result


def fd(fun,z,h):
    return np.column_stack([(fun(z+e*h)-fun(z-e*h))/(2*h) for e in np.eye(25)])


def survey(geom):
    return np.array(C['survey_good' if geom=='good' else 'survey_weak_near'])


def variants(geom, truth_initial):
    center = survey(geom)
    out=[]
    for name in C['variants']:
        init = 'plus' if name.endswith('_plus') and name.startswith(('no_prior','nominal')) else 'minus' if name.endswith('_minus') and name.startswith(('no_prior','nominal')) else 'base'
        sigma = None if name.startswith('no_prior') else .05 if name=='strong' else 5. if name=='weak_prior' else .5
        pc = center.copy()
        if name=='center_plus': pc += C['prior_center_delta']
        if name=='center_minus': pc -= C['prior_center_delta']
        if name=='ideal_truth_center': pc = truth_initial.copy()
        out.append((name,init,sigma,pc))
    return out


def solve(anchors,kind,peer_only,obs,mv,start,sigma,center):
    # No truth argument: all data and initialization inputs are explicit.
    def fun(z):
        parts=[(model(z,anchors,kind,peer_only)[0]-obs)/C['range_sigma_m'],(MOTION@z-mv)/C['motion_sigma_m']]
        if sigma is not None: parts.append((z[:4]-center)/sigma)
        return np.concatenate(parts)
    def jac(z):
        parts=[model(z,anchors,kind,peer_only)[1]/C['range_sigma_m'],MOTION/C['motion_sigma_m']]
        if sigma is not None: parts.append(PRIOR/sigma)
        return np.vstack(parts)
    return least_squares(fun,start,jac=jac,x_scale=SCALE,**C['optimizer'])


def write_csv(path,rows):
    with path.open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    out=args.out
    config_sha=hashlib.sha256((DOC/'CONFIG.json').read_bytes()).hexdigest()
    source_shas={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),DOC/'CONFIG.json']}
    (out/'RUN.json').write_text(json.dumps(dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),config_sha256=config_sha,sources=source_shas),indent=2))
    spec=importlib.util.spec_from_file_location('pr97',ROOT/'tools/midterm_simulation_phase1/identifiability.py')
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    scenes=[(g,m,k,False) for g in C['geometries'] for m in C['motions'] for k in C['kinds']]+[('good','static','peer',True)]
    infos=[];checks=[];rows=[];raw=[];global_checks=[]
    for gi,(geom,motion,kind,po) in enumerate(scenes):
        label='/'.join([geom,motion,kind])+('/peer_only' if po else '')
        anchors,truth=design(geom,motion)
        clean,j=model(truth,anchors,kind,po);clean_mv=MOTION@truth
        if geom!='near' and not po:
            oa,ox=old.design(geom,motion)
            ov,oj=old.model(truth,oa,kind)
            assert np.array_equal(anchors,oa) and np.array_equal(truth[:-1],ox.ravel())
            assert np.max(abs(clean-ov))<1e-14 and np.max(abs(j-oj))<1e-14
        for point in ['truth','off_truth']:
            z=truth.copy()
            if point=='off_truth': z[:24]+=np.tile([.17,.23,-.11,.19],6);z[-1]=-.2
            for h in C['fd_steps']:
                f=lambda q:np.r_[model(q,anchors,kind,po)[0],MOTION@q,PRIOR@q]
                jac=np.vstack([model(z,anchors,kind,po)[1],MOTION,PRIOR])
                err=float(np.max(np.abs(fd(f,z,h)-jac)))
                checks.append(dict(scene=label,point=point,step=h,jacobian_max_error=err))
                assert err<C['fd_tolerance']
        for name,a in [('measurements',j/.04),('data_motion',np.vstack([j/.04,MOTION/.02])),('with_initial_prior',np.vstack([j/.04,MOTION/.02,PRIOR/.5])),('pr97_strong_prior',np.vstack([j/.04,MOTION/.02,PRIOR/.05]))]:
            item=dict(scene=label,geometry=geom,motion=motion,kind=kind,peer_only=po,information=name,**information(a))
            assert item['null_residual']<C['svd_check_tolerance'] and item['null_orthogonality_error']<C['svd_check_tolerance']
            assert item['projection_lstsq_difference']<C['svd_check_tolerance']
            infos.append(item)
        if po:
            alternative=truth.copy();xx=alternative[:24].reshape(6,2,2);d=xx[0,1]-xx[0,0];xx[:,1]+=.2*d/np.linalg.norm(d);alternative[-1]-=.2
            global_checks.append(dict(scene=label,type='exact_distinct_bias_same_observations',truth=truth.tolist(),alternative=alternative.tolist(),max_measurement_difference=float(np.max(abs(model(alternative,anchors,kind,po)[0]-clean))),max_motion_difference=float(np.max(abs(MOTION@alternative-clean_mv)))))
        if geom=='weak' and motion in ['static','straight'] and not po:
            for eps in [.1,.01]:
                q=truth.copy();q[:24].reshape(6,2,2)[:,0,1]+=eps
                global_checks.append(dict(scene=label,type='transverse_first_order_null_but_finite_change',epsilon=eps,linearized_change=float(np.max(abs(j@(q-truth)))),max_measurement_difference=float(np.max(abs(model(q,anchors,kind)[0]-clean)))))
        for seed in [0]+C['seeds']:
            rng=np.random.default_rng(np.random.SeedSequence([seed,C['geometries'].index(geom),C['motions'].index(motion),C['kinds'].index(kind)]))
            noise_r=np.zeros(len(clean)) if seed==0 else rng.normal(0,.04,len(clean))
            noise_m=np.zeros(20) if seed==0 else rng.normal(0,.02,20)
            obs,mv=clean+noise_r,clean_mv+noise_m
            raw.append(dict(scene=label,seed=seed,range_observed=obs.tolist(),motion_observed=mv.tolist(),range_noise=noise_r.tolist(),motion_noise=noise_m.tolist(),truth=truth.tolist(),anchors=anchors.tolist()))
            for name,init,sigma,center in variants(geom,truth[:4]):
                first=survey(geom)+np.array(C['init_offsets'][init])
                start=np.r_[np.vstack([first,first+np.cumsum(mv.reshape(5,4),axis=0)]).ravel(),C['init_bias'][init]]
                fit=solve(anchors,kind,po,obs,mv,start,sigma,center)
                e=(fit.x[:24]-truth[:24]).reshape(6,2,2)
                prmse=float(np.sqrt(np.mean(np.sum(e**2,axis=-1))))
                be=float(fit.x[-1]-truth[-1])
                sf=not fit.success or not np.all(np.isfinite(fit.x))
                pf=prmse>C['failure']['position_rmse_2d_gt_m'];bf=abs(be)>C['failure']['absolute_bias_error_gt_m']
                a=np.vstack([model(fit.x,anchors,kind,po)[1]/.04,MOTION/.02])
                eff=effective(a)
                rows.append(dict(scene=label,geometry=geom,motion=motion,kind=kind,peer_only=po,seed=seed,noise='zero' if seed==0 else 'gaussian',variant=name,initialization=init,prior_sigma_m='' if sigma is None else sigma,prior_center_initial_rmse_m=float(np.sqrt(np.mean((center-truth[:4])**2))) if sigma else '',position_rmse_2d_m=prmse,position_rmse_coordinate_m=float(np.sqrt(np.mean(e**2))),car1_rmse_2d_m=float(np.sqrt(np.mean(np.sum(e[:,0]**2,axis=-1)))),car2_rmse_2d_m=float(np.sqrt(np.mean(np.sum(e[:,1]**2,axis=-1)))),bias_estimate_m=float(fit.x[-1]),bias_error_m=be,solver_failed=sf,position_failed=pf,bias_failed=bf,any_failed=sf or pf or bf,status=int(fit.status),nfev=fit.nfev,cost=float(fit.cost),optimality=float(fit.optimality),endpoint_data_bias_information=eff['bias_information_m_minus2']))
                raw.append(dict(scene=label,seed=seed,variant=name,estimate=fit.x.tolist(),initial_state=start.tolist(),prior_center=center.tolist() if sigma else None,solver_message=fit.message))
        print(f'{gi+1}/{len(scenes)} {label}: {len(rows)} fits',flush=True)
    write_csv(out/'PER_RUN.csv',rows)
    (out/'INFORMATION.json').write_text(json.dumps(infos,indent=2))
    (out/'CHECKS.json').write_text(json.dumps(dict(jacobian=checks,global_checks=global_checks,total_fits=len(rows),information_cases=len(infos),max_jacobian_error=max(x['jacobian_max_error'] for x in checks)),indent=2))
    with (out/'RAW.jsonl').open('x') as f:
        for r in raw:f.write(json.dumps(r)+'\n')
    assert len(rows)==C['main_runs']+C['negative_control_runs']
    print('PASS: finite differences, PR97 parity, full nullspace, projection residual, frozen run count',flush=True)

if __name__=='__main__':main()
