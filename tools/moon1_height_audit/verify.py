#!/usr/bin/env python3
"""Independent readback of saved evidence; never regenerates scenes or solves poses."""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np


def read_trace(root):
    path=root/'SUPPORT_TRACE.json'
    if path.exists():return json.loads(path.read_text())
    with gzip.open(root/'SUPPORT_TRACE.json.gz','rt') as f:return json.load(f)


def verify(root):
    cfg=json.loads((root/'CONFIG.json').read_text())
    rows=list(csv.DictReader((root/'TIMESERIES.csv').open()))
    stats=list(csv.DictReader((root/'METRICS.csv').open()))
    trace=read_trace(root)
    index={(r['sequence'],int(r['index']),int(r['car'])):r for r in trace}
    max_formula=0.; max_summary=0.
    scene_path=root/'scene/moon1_scene.npz'
    scene=np.load(scene_path,allow_pickle=False) if scene_path.is_file() else None
    ranks=[]
    for r in rows:
        a=np.array([float(r['car1_'+v+'_m']) for v in 'xyz'])
        b=np.array([float(r['car2_'+v+'_m']) for v in 'xyz'])
        xy=float(np.linalg.norm(a[:2]-b[:2])); dz=float(a[2]-b[2]); distance=float(np.hypot(xy,dz))
        denominator=xy+distance
        exact=dz*dz/denominator if denominator else 0.
        for k,v in [('r_xy_m',xy),('r_3d_m',distance),('delta_z_m',dz),('ignore_error_m',exact),('fixed_error_m',distance-np.hypot(xy,cfg['fixed_delta_z_m']))]:
            diff=abs(float(r[k])-v);max_formula=max(max_formula,diff);assert diff<1e-12,(k,diff)
        pair=[]
        for c in (1,2):
            t=index[(r['sequence'],int(r['index']),c)]
            w=np.array(t['weights']);observed=np.array(t['observed'])
            assert abs(w.sum()-1)<1e-14 and (w>=0).all()
            nodes=np.array(t['nodes']); assert nodes.shape==(4,2)
            if scene is not None:
                ix,iy=nodes.T
                np.testing.assert_array_equal(observed,scene['observed'][ix,iy])
                np.testing.assert_allclose(t['node_observation_distance_m'],scene['distance_to_observation'][ix,iy],atol=1e-14,rtol=0)
                donors=np.array(t['donors'])
                assert scene['observed'][donors[:,0],donors[:,1]].all()
                z=scene['vertices'][:,2].reshape(*scene['grid_shape'])[ix,iy]@w
                assert abs(z-float(r[f'car{c}_z_m'])+1.16)<1e-12
            fill=bool(np.any((w>0)&~observed))
            rank=3 if t['clipped'] else 2 if fill else 1 if t['fill_mass']>0 or t['reflected'] else 0
            assert rank==t['rank'];pair.append(rank)
        labels=['supported_smoothed','smoothing_inferred_or_edge','filled_node','clipped']
        assert r['stratum']==labels[max(pair)]
        if distance>0:
            j=np.r_[(a-b)/distance,-(a-b)/distance]
            # One row has one nonzero singular value sqrt(2), six states minus one constraint.
            assert abs(np.linalg.norm(j)-np.sqrt(2))<1e-14
            ranks.append(1)
    for s in stats:
        chosen=[r for r in rows if r['sequence']==s['sequence'] and (s['stratum']=='all' or r['stratum']==s['stratum'])]
        assert int(s['n'])==len(chosen)
        if not chosen:
            assert all(s[k]=='' for k in ['mean','rms','min','p05','p50','p95','p99','max','abs_max']);continue
        x=np.array([float(r[s['metric']]) for r in chosen])
        computed=dict(mean=x.mean(),rms=np.linalg.norm(x)/np.sqrt(len(x)),min=min(x),p05=np.quantile(x,.05),p50=np.quantile(x,.5),p95=np.quantile(x,.95),p99=np.quantile(x,.99),max=max(x),abs_max=max(abs(x)))
        for k,v in computed.items():
            difference=abs(float(s[k])-v);max_summary=max(max_summary,difference);assert difference<1e-12
    # Current delivered inputs can be checked separately against absolute source paths if available.
    source_verified=0;source_unavailable=0
    for i in json.loads((root/'INPUTS.json').read_text()):
        p=Path(i['path'])
        if i['exists'] and p.is_file():
            assert hashlib.sha256(p.read_bytes()).hexdigest()==i['sha256'],str(p);source_verified+=1
        elif i['exists']:source_unavailable+=1
    run=json.loads((root/'RUN.json').read_text())
    output_verified=0;output_unavailable=[]
    for o in run['outputs']:
        p=Path(o['path'])
        if p.is_file():
            assert hashlib.sha256(p.read_bytes()).hexdigest()==o['sha256'],str(p);output_verified+=1
        else:output_unavailable.append(str(p))
    # Delivery copies are protected separately by SHA256SUMS.json; do not claim absent big files verified.
    return dict(status='PASS',scene_support_rechecked=scene is not None,time_rows=len(rows),support_records=len(trace),summary_rows=len(stats),
                formula_max_abs_error_m=max_formula,summary_max_abs_error=max_summary,
                rank_one_pairs=len(ranks),source_hashes_verified=source_verified,source_hashes_unavailable=source_unavailable,
                generated_output_hashes_verified=output_verified,generated_outputs_unavailable=output_unavailable,
                formal_runs=0,nonlinear_solver_calls=0)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():raise ValueError('Refusing to overwrite existing receipt')
    result=verify(a.input);a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
