"""Seed 101 causal development example. The filter only accepts observation packets."""
import gzip
import json
import subprocess
from pathlib import Path

import numpy as np
from statistics import NormalDist

SHA='01e588021e7e3ddd918b1d1fc9561973373758c6'
SRC='docs/research/ground_continuous_b/runs/101_nominal/'
CFG='docs/field_tests/20261024_25/two_car_imu_fgo_20261028/configs/nominal_seed101.json'
TARGET=10
R=np.eye(9)*.04**2
Q=np.diag([.03**2]*4+[.01**2]*9)
AL=.1
RISK=.01


def read(path):
    raw=subprocess.check_output(['git','show',SHA+':'+path])
    return json.loads(gzip.decompress(raw) if path.endswith('.gz') else raw)


def rotation(angle):
    return np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])


def antenna_offset(odom,model):
    x,y,yaw=odom
    lever=np.array(model['base_to_antenna_body_xy_m'])
    heading=np.deg2rad(model['initial_heading_deg'])
    return rotation(heading)@(np.array([x,y])+rotation(yaw)@lever-lever)


def packet(record,models):
    t=record['t']
    motion=[]
    for car in ('car1','car2'):
        b=record['bins'][car]
        assert b['state_time_s']==t and b['dependency_receipt_max_s']<=record['cutoff']
        motion.append(b['local_odom'])
    obs=record['obs']
    assert obs['received']<=record['cutoff']
    assert obs['ids']==[f'{car}:uwb:{20*t}' for car in ('car1','car2')]
    return dict(t=t,ranges=obs['ranges'],heights=obs['heights'],anchors=obs['anchors'],
                range_ids=obs['ids'],peer_id=obs['peer_id'],anchor_order=obs['anchor_order'],
                odom=motion,odom_ids=[f'{c}:odom:{20*t}' for c in models],cutoff=record['cutoff'],range_received=obs['received'],
                bin_receipts=[record['bins'][c]['dependency_receipt_max_s'] for c in models])


def geometry(x,packet):
    xyz=np.column_stack((x[:4].reshape(2,2),packet['heights']))
    offsets=xyz[:,None,:]-np.array(packet['anchors'])
    ranges=np.linalg.norm(offsets,axis=2)
    peer=xyz[0]-xyz[1]
    d=np.linalg.norm(peer)
    H=np.column_stack((np.zeros((9,4)),np.eye(9)))
    for car in range(2):
        H[4*car:4*car+4,2*car:2*car+2]=offsets[car,:,:2]/ranges[car,:,None]
    H[-1,:4]=np.r_[peer[:2]/d,-peer[:2]/d]
    return np.r_[ranges.ravel(),d]+x[4:],H


def rank_report(H):
    sv=np.linalg.svd(H,compute_uv=False)
    return dict(rank=int(np.sum(sv>sv[0]*1e-9)),columns=H.shape[1],
                singular_values=sv.tolist(),threshold=float(sv[0]*1e-9))


def ranks(history,links):
    n=len(history)
    dim=4+links
    measurement=np.zeros((9*n,dim*n))
    motion=np.zeros((4*(n-1),dim*n))
    process=np.zeros((links*(n-1),dim*n))
    for i,H in enumerate(history):
        block=np.column_stack((H[:,:4],np.eye(9) if links==9 else H[:,[-1]]))
        measurement[9*i:9*i+9,i*dim:(i+1)*dim]=block/.04
        if i:
            for matrix,offset,size,sd in [(motion,0,4,.03),(process,4,links,.01)]:
                for j,sign in [(i-1,-1),(i,1)]:
                    matrix[(i-1)*size:i*size,j*dim+offset:j*dim+offset+size]=sign*np.eye(size)/sd
    data=np.vstack([measurement,motion])
    smooth=np.vstack([data,process])
    prior=np.zeros((dim,dim*n))
    prior[:,:dim]=np.diag([1/.2]*4+[1/.3]*links)
    return dict(measurement=rank_report(measurement),motion=rank_report(motion),
                data=rank_report(data),with_bias_process=rank_report(smooth),
                with_initial_prior=rank_report(np.vstack([smooth,prior])))


def estimate(packets,models):
    x=np.r_[np.concatenate([m['start_antenna_xyz_m'][:2] for m in models.values()]),np.zeros(9)]
    P=np.diag([.2**2]*4+[.3**2]*9)
    previous=np.zeros(4)
    transfer=np.zeros((13,0))
    Hs=[]
    history=[]
    for p in packets:
        delta=np.concatenate([antenna_offset(o,m) for o,m in zip(p['odom'],models.values())])
        u=delta-previous
        previous=delta
        prior=x+np.r_[u,np.zeros(9)]
        prior_cov=P+Q
        pred,H=geometry(prior,p)
        Hs.append(H)
        innovation=p['ranges']-pred
        S=H@prior_cov@H.T+R
        K=np.linalg.solve(S,H@prior_cov).T
        A=np.eye(13)-K@H
        x=prior+K@innovation
        P=A@prior_cov@A.T+K@R@K.T
        transfer=np.column_stack((A@transfer,K))
        history.append(dict(t=p['t'],u=u.tolist(),prior=prior.tolist(),prior_cov=prior_cov.tolist(),
            predicted=pred.tolist(),innovation=innovation.tolist(),H=H.tolist(),S=S.tolist(),
            gain=K.tolist(),posterior=x.tolist(),posterior_cov=P.tolist()))
    stat=float(innovation@np.linalg.solve(S,innovation))
    threshold=21.665994333461924
    cars=[]
    for i in range(2):
        axes=slice(2*i,2*i+2)
        sigma=np.sqrt(np.diag(P)[axes])
        bias=.02*np.abs(transfer[axes]).sum(axis=1)
        variants={}
        current=.02*np.abs(K[axes]).sum(axis=1)
        for label,alpha,bound in [('eq13_to_16',RISK,current),('axis_preallocated',RISK/2,current),
                                  ('history_preallocated',RISK/2,bias)]:
            k=NormalDist().inv_cdf(1-alpha/2)
            cpl=bound+k*sigma
            hcpl=float(np.linalg.norm(cpl))
            variants[label]=dict(axis_alpha=alpha,k=k,CPL=cpl.tolist(),HCPL=hcpl,
                alarm=bool(stat>threshold or hcpl>AL),available=bool(stat<=threshold and hcpl<=AL))
        cars.append(dict(car=i+1,state_time=packets[-1]['t'],published_antenna_xy=x[axes].tolist(),
            decision_ready_time=None,AL=AL,sigma=sigma.tolist(),history_bias_bound=bias.tolist(),current_bias_bound=current.tolist(),variants=variants))
    # Single-epoch witness: horizontal error is canceled by link biases.
    direction=np.r_[1.,0.,0.,0.]
    null=np.r_[direction,-Hs[0][:,:4]@direction]
    return dict(first_epoch_failure=dict(H=Hs[0].tolist(),null_vector=null.tolist(),
                residual_norm=float(np.linalg.norm(Hs[0]@null))),packets=packets,history=history,R=R.tolist(),Q=Q.tolist(),transfer=transfer.tolist(),
        remaining_range_bias_bound=.02,axis_nominal_alpha=RISK,innovation_test=dict(statistic=stat,
        rank=int(np.linalg.matrix_rank(S)),threshold=threshold,alarm=bool(stat>threshold)),cars=cars,
        ranks={str(n):ranks(Hs,n) for n in (1,9)})


def main():
    records=read(SRC+'records.json.gz')
    models=read(CFG)['models']
    models={c:models[c] for c in ('car1','car2')}
    packets=[packet(r,models) for r in records if 1<=r['t']<=TARGET]
    assert [p['t'] for p in packets]==list(range(1,TARGET+1))
    output=estimate(packets,models)
    output['survey_init']={c:{k:models[c][k] for k in ('initial_heading_deg','start_antenna_xyz_m','base_to_antenna_body_xy_m')} for c in models}
    output['source_sha']=SHA
    truth=read(SRC+'truth.json.gz')[20*TARGET]
    output['evaluation_only']=[dict(truth_xy=v,error_m=float(np.linalg.norm(np.array(v)-car['published_antenna_xy']))) for v,car in zip(truth,output['cars'])]
    output['independent_epoch_baseline']=next(r['aug'] for r in records if r['t']==TARGET)
    print(json.dumps(output,indent=2,allow_nan=False))


if __name__=='__main__':
    main()
