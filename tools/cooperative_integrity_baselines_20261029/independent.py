"""Independent scalar/finite-difference reader. No online estimator/policy imports.

Shared only: JSON schema, frozen numerical config, primitive naming convention.
This proves the declared frozen-linearization computation, not calibration.
"""
import argparse
import copy
import gzip
import json
import math
from pathlib import Path
import numpy as np

CARS=('car1','car2')
GROUPS=('car1_absolute','car2_absolute','peer')


def wrap(x):return math.atan2(math.sin(x),math.cos(x))


def ant(p,m):
    c,s=math.cos(p[2]),math.sin(p[2]);lx,ly=m['base_to_antenna_body_xy_m']
    return np.array([p[0]+c*lx-s*ly,p[1]+s*lx+c*ly,m['antenna_height_m']])


def noise_keys():
    keys=['initial|'+str(i) for i in range(6)]
    for car in CARS:
        keys += [f'odom|{car}|{left}|{left+1}|{i}' for left in range(1,63) for i in range(3)]
        keys += [f'wall|{car}|{t}|{k}' for t in range(1,64) for k in ('node_10','node_2','node_3','node_8')]
    keys += [f'peer|{t}' for t in range(1,64)]
    return keys


def body(a,b):
    c,s=math.cos(a[2]),math.sin(a[2]);dx,dy=b[0]-a[0],b[1]-a[1]
    return np.array([c*dx+s*dy,-s*dx+c*dy])


def robust(pred,meas,sigma):
    u=(pred-meas)/sigma
    return u*math.sqrt(2/(math.hypot(1.,u)+1))


def residuals(flat,snapshot,config):
    x=np.asarray(flat).reshape(-1,6);s=snapshot;times=s['times_s'];local=np.asarray(s['local'])
    d=x[0]-s['prior']['point'];d[2]=wrap(d[2]);d[5]=wrap(d[5])
    values=list(np.asarray(s['prior']['matrix'])@d+s['prior']['offset'])
    for ci,car in enumerate(CARS):
        m=config['models'][car];pars=m['graph_parameters']
        for i in range(1,len(times)):
            p=x[i,ci*3:ci*3+3];q=x[i-1,ci*3:ci*3+3]
            delta=body(q,p)-body(local[i-1,ci],local[i,ci]);scale=math.sqrt(times[i]-times[i-1])
            values.extend(delta/(pars['odom_translation_sigma_m']*scale))
            values.append(wrap(p[2]-q[2]-wrap(local[i,ci,2]-local[i-1,ci,2]))/
                          (math.radians(pars['odom_yaw_sigma_deg'])*scale))
        for i,obs in enumerate(s['observations']):
            for key,raw in sorted(obs[car].items()):
                pred=np.linalg.norm(ant(x[i,ci*3:ci*3+3],m)-m['anchors_xyz_m'][key])
                values.append(robust(pred,raw-m['range_bias_m'][key],pars['range_sigma_m']))
    if s['peer_enabled']:
        for i,p in enumerate(s['peers_m']):
            if p is not None:
                rho=np.linalg.norm(ant(x[i,:3],config['models']['car1'])-ant(x[i,3:],config['models']['car2']))
                values.append(robust(rho,p,config['peer']['sigma_m']))
    return np.asarray(values)


def finite_jac(flat,snapshot,config):
    x=np.asarray(flat).ravel();cols=[]
    for i in range(len(x)):
        d=np.zeros_like(x);d[i]=1e-6
        cols.append((residuals(x+d,snapshot,config)-residuals(x-d,snapshot,config))/2e-6)
    return np.column_stack(cols)


def make_b(snapshot,config,prior_b):
    keys=noise_keys();index={k:i for i,k in enumerate(keys)};rows=[v.copy() for v in prior_b]
    s=snapshot;x=np.asarray(s['states']);times=s['times_s']
    for ci,car in enumerate(CARS):
        m=config['models'][car]
        for left,right in zip(times,times[1:]):
            for component in range(3):
                row=np.zeros(len(keys));row[index[f'odom|{car}|{left:g}|{right:g}|{component}']]=-1;rows.append(row)
        for i,obs in enumerate(s['observations']):
            for key,raw in sorted(obs[car].items()):
                pred=np.linalg.norm(ant(x[i,ci*3:ci*3+3],m)-m['anchors_xyz_m'][key])
                u=(pred-raw+m['range_bias_m'][key])/m['graph_parameters']['range_sigma_m']
                # Numerical derivative of signed transform with respect to a
                # unit normalized measurement perturbation (independent formula).
                eps=1e-5;sigma=m['graph_parameters']['range_sigma_m'];meas=raw-m['range_bias_m'][key]
                derivative=(robust(pred,meas+eps*sigma,sigma)-robust(pred,meas-eps*sigma,sigma))/(2*eps)
                row=np.zeros(len(keys));row[index[f'wall|{car}|{times[i]:g}|{key}']]=derivative;rows.append(row)
    if s['peer_enabled']:
        for i,p in enumerate(s['peers_m']):
            if p is None:continue
            pred=np.linalg.norm(ant(x[i,:3],config['models']['car1'])-ant(x[i,3:],config['models']['car2']))
            sigma=config['peer']['sigma_m'];eps=1e-5
            value=(robust(pred,p+eps*sigma,sigma)-robust(pred,p-eps*sigma,sigma))/(2*eps)
            row=np.zeros(len(keys));row[index[f'peer|{times[i]:g}']]=value;rows.append(row)
    return np.asarray(rows)


def verify_input_prefix(rows,events,config):
    origin=events[0]['receive_epoch_ns'];checks=0
    assert all(type(e['receive_epoch_ns']) is int and type(e['record_index']) is int for e in events)
    for r in rows:
        ns=r['availability_cutoff_epoch_ns'];stamp=r['state_time_s']
        assert r['dependency_receipt_max_s'] is None or r['dependency_receipt_max_s']<=(ns-origin)/1e9
        for car in CARS:
            selected=[e for e in events if e['kind']=='uwb' and e['vehicle_id']==car and e['representation']=='bridge'
                      and e['receive_epoch_ns']<=ns and abs((e['header_epoch_ns']-origin)/1e9-stamp)<=config['replay']['range_bin_half_width_s']]
            for key in config['models'][car]['anchors_xyz_m']:
                values=[e['value'][key] for e in selected if key in e['value']]
                assert len(values)==r['bins'][car]['sample_counts'][key]
                if len(values)>=5:assert abs(float(np.median(values))-r['bins'][car]['observations'][key])<1e-12
            odom=[e for e in events if e['kind']=='odom' and e['vehicle_id']==car and e['receive_epoch_ns']<=ns]
            headers=[(e['header_epoch_ns']-origin)/1e9 for e in odom]
            pos=np.searchsorted(headers,stamp)
            if pos<len(headers) and headers[pos]==stamp:
                expected=odom[pos]['value']['pose']
            elif pos>0 and pos<len(headers):
                before=np.array(odom[pos-1]['value']['pose']);after=np.array(odom[pos]['value']['pose'])
                after[2]=before[2]+wrap(after[2]-before[2])
                expected=before+(stamp-headers[pos-1])/(headers[pos]-headers[pos-1])*(after-before)
            else:expected=None
            if expected is None:assert r['bins'][car]['local_odom'] is None
            else:np.testing.assert_allclose(r['bins'][car]['local_odom'],expected,atol=1e-10,rtol=0)
            for dep in r['peer_dependencies']+r['reverse_diagnostic_dependencies']:
                assert dep['identity']['receive_epoch_ns']<=ns
            checks+=1
    return dict(status='PASS',integer_prefix_bins=checks)


def verify(rows,config):
    counts=dict(publications=0,ss_scores=0,b1_scores=0,schur_steps=0,linear_snapshots=0,declarations=0)
    priors={role:np.c_[-np.eye(6),np.zeros((6,len(noise_keys())-6))] for role in ('main',*GROUPS)}
    consumed={role:set() for role in priors};worst_k=0.;worst_prior=0.
    for r in rows:
        assert type(r['state_epoch_ns']) is int and type(r['availability_cutoff_epoch_ns']) is int
        assert r['state_epoch_ns']<r['availability_cutoff_epoch_ns'];m=r['monitor']
        assert not r['accepted_graph'] or r['status']=='graph'
        for role,details in r['marginal_evidence'].items():
            for d in details:
                s=dict(times_s=d['times_s'],local=d['local'],observations=[d['old_observations'],{c:{} for c in CARS}],
                       peers_m=[d['old_peer_m'],None],peer_enabled=role!='peer',states=d['states'],prior=d['before'])
                if role.endswith('_absolute'):assert not d['old_observations'][role.split('_')[0]]
                if role=='peer':assert d['old_peer_m'] is None
                x=np.asarray(d['states']).ravel();rv=residuals(x,s,config);j=finite_jac(x,s,config);b=make_b(s,config,priors[role])
                h=j.T@j;g=j.T@rv
                hs=h[6:,6:]-h[6:,:6]@np.linalg.solve(h[:6,:6],h[:6,6:])
                gs=g[6:]-h[6:,:6]@np.linalg.solve(h[:6,:6],g[:6])
                cs=rv@rv-g[:6]@np.linalg.solve(h[:6,:6],g[:6])
                a=np.asarray(d['after']['matrix']);o=np.asarray(d['after']['offset'])
                np.testing.assert_allclose(a.T@a,hs,atol=1e-5,rtol=2e-6)
                np.testing.assert_allclose(a.T@o,gs,atol=1e-6,rtol=2e-6)
                np.testing.assert_allclose(o@o+d['constant'],cs,atol=1e-6,rtol=2e-6)
                # Independently propagate measurement RHS via Schur information,
                # not the online QR implementation. a.T @ B_new = RHS_Schur.
                rhs=j.T@b
                rhs_s=rhs[6:]-h[6:,:6]@np.linalg.solve(h[:6,:6],rhs[:6])
                priors[role]=np.linalg.solve(a.T,rhs_s)
                t=d['times_s'][0]
                ids={f'wall|{car}|{t:g}|{key}' for car in CARS for key in d['old_observations'][car]}
                ids.update(f'odom|{car}|{t:g}|{d["times_s"][1]:g}|{i}' for car in CARS for i in range(3))
                if role!='peer' and d['old_peer_m'] is not None:ids.add(f'peer|{t:g}')
                assert not consumed[role]&ids;consumed[role].update(ids)
                counts['schur_steps']+=1
        if r.get('linear_evidence'):
            ks={}
            for role,e in r['linear_evidence'].items():
                s=e['snapshot'];x=np.asarray(s['states']).ravel();pb=np.asarray(e['prior_b'])
                delta=float(np.max(np.abs(pb-priors[role])));worst_prior=max(worst_prior,delta)
                np.testing.assert_allclose(pb,priors[role],atol=2e-6,rtol=2e-5)
                j=finite_jac(x,s,config);b=make_b(s,config,priors[role])
                k=-np.linalg.lstsq(j,b,rcond=None)[0][-6:];target=np.asarray(e['k'])
                worst_k=max(worst_k,float(np.max(np.abs(k-target))))
                np.testing.assert_allclose(k,target,atol=2e-6,rtol=3e-5)
                if role!='main':
                    prefix='peer|' if role=='peer' else 'wall|'+role.split('_')[0]+'|'
                    indices=[i for i,key in enumerate(noise_keys()) if key.startswith(prefix)]
                    np.testing.assert_allclose(pb[:,indices],0,atol=0,rtol=0)
                    np.testing.assert_allclose(k[:,indices],0,atol=0,rtol=0)
                ks[role]=target
                counts['linear_snapshots']+=1
            # Rebuild antenna sensitivities from independently finite-differenced lever rotation.
            main=r['linear_evidence']['main']['snapshot']
            for ci,car in enumerate(CARS):
                def current_a(role):
                    e=r['linear_evidence'][role];p=np.asarray(e['snapshot']['states'][-1])[3*ci:3*ci+3];cols=[]
                    for i in range(3):
                        d=np.eye(3)[i]*1e-6;cols.append((ant(p+d,config['models'][car])[:2]-ant(p-d,config['models'][car])[:2])/2e-6)
                    return np.column_stack(cols)@ks[role][3*ci:3*ci+3]
                kf=current_a('main')
                for group in GROUPS:
                    kd=kf-current_a(group)
                    np.testing.assert_allclose(kd@kd.T,m['ss'][group][ci]['covariance'],atol=1e-10,rtol=1e-6)
        for pair in m['ss'].values():
            for s in pair:
                if not s['computable']:assert s['statistic'] is None;continue
                c=np.asarray(s['covariance']);d=np.asarray(s['delta_xy_m']);cross=np.asarray(s['cross_covariance'])
                np.testing.assert_allclose(c,np.asarray(s['full_covariance'])+s['subset_covariance']-cross-cross.T,atol=1e-12)
                assert np.linalg.matrix_rank(c)==2 and np.min(np.linalg.eigvalsh(c))>0
                assert abs(float(d@np.linalg.solve(c,d))-s['statistic'])<1e-8
                counts['ss_scores']+=1
        for noise,local in m['b1'].items():
            for car,s in local.items():
                if not s['computable']:continue
                p=np.r_[s['antenna_xy_m'],config['models'][car]['antenna_height_m']]
                residual=[];model=config['models'][car]
                for key in sorted(model['anchors_xyz_m']):
                    residual.append(np.linalg.norm(p-model['anchors_xyz_m'][key])-r['bins'][car]['observations'][key]+model['range_bias_m'][key])
                residual=np.asarray(residual);score=float(np.sum((residual/np.asarray(s['sigma_m']))**2))
                assert abs(score-s['statistic'])<1e-7
                counts['b1_scores']+=1
        # Independent chi2(df=2) quantile = -2log(alpha), no online decisions import.
        for name,pair in m['declarations'].items():
            local=[]
            for ci,car in enumerate(CARS):
                if name=='B0':
                    ready=m['b0']['state'] in ('accepted','rejected');alarm=ready and m['b0']['engineering_q']>3
                elif name.startswith('B1'):
                    _,noise,a=name.split('|');alpha=float(a.split('=')[1]);s=m['b1'][noise][car]
                    ready=s['computable'];alarm=ready and s['statistic']>-2*math.log(alpha)
                else:
                    _,sc,a=name.split('|');scale=float(sc.split('=')[1]);alpha=float(a.split('=')[1]);tests=[m['ss'][g][ci] for g in GROUPS]
                    ready=all(s['computable'] for s in tests);alarm=any(s['computable'] and s['statistic']/scale**2>-2*math.log(alpha/3) for s in tests)
                ready=bool(ready and r['accepted_graph']);local.append(dict(computable=ready,alarm=bool(ready and alarm),available=bool(ready and not alarm)))
            if '_network|' in name:
                shared=dict(computable=all(d['computable'] for d in local),alarm=any(d['alarm'] for d in local),
                            available=all(d['computable'] for d in local) and not any(d['alarm'] for d in local))
                local=[shared,shared]
            for actual,expected in zip(pair,local):
                for key in ('computable','alarm','available'):assert actual[key]==expected[key]
                counts['declarations']+=1
        counts['publications']+=1
    return dict(status='PASS',counts=counts,maximum_fd_k_abs_difference=worst_k,maximum_fd_prior_b_abs_difference=worst_prior,
                imports='numpy/stdlib only; no graph/Jacobian/policy imports',scope='frozen linearization algebra, not physical calibration')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    with gzip.open(a.run/'monitor.jsonl.gz','rt') as f:rows=[json.loads(line) for line in f]
    result=verify(rows,json.loads((a.run/'config.json').read_text()))
    with a.output.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(result)
if __name__=='__main__':main()
