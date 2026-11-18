"""Five additive covariance sources conditional on the frozen replay gains and gates."""
import csv
import gzip
import importlib.util
import json
from pathlib import Path
from statistics import NormalDist
import subprocess
import tempfile
from unittest.mock import patch

import numpy as np

ROOT=Path(__file__).resolve().parents[3]
TOOLS='tools/midterm_dual_robot_contract_a'
DOC='docs/research/midterm_dual_robot_contract_a'
FREEZE='efd9f9560de6d0661f5c3322dfa545515b51594d'
SOURCE='85fbe8aca47f0b8d25b6b97107e91b8550737195'
NAMES=['initial_xy','initial_link_bias','process_xy','process_link_bias','range_noise']
TARGETS=(10,23,24,37,38)
OUT=ROOT/DOC/'round3'


def blob(sha,path):
    return subprocess.check_output(['git','show',sha+':'+path],cwd=ROOT)


def frozen_filter(folder):
    files=[TOOLS+'/round2/trajectory.py',TOOLS+'/ground_hcpl/example.py',
           'docs/research/midterm_sim_review/round1/ground/replay_tta.py']
    for name in files:
        path=folder/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(blob(FREEZE,name))
    spec=importlib.util.spec_from_file_location('frozen_trajectory',folder/files[0])
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def diagonal(xy,bias):
    return np.diag([xy]*4+[bias]*9)


def analyze(module,scene):
    folder='docs/research/ground_b_round2/runtime/101_'+scene
    cfg=json.loads(blob(SOURCE,folder+'/geometry.json'))
    frames=module.groups(blob(SOURCE,folder+'/events.jsonl.gz'),cfg)
    archived=json.loads(gzip.decompress(blob(FREEZE,DOC+'/round2/dev/101_'+scene+'/epochs.json.gz')))
    filt=module.Filter(cfg)
    sources=np.zeros((5,13,13))
    sources[0]=diagonal(.2**2,0)
    sources[1]=diagonal(0,.3**2)
    geom=module.ref.geometry
    jacobians=[]
    def observe(x,packet):
        pred,h=geom(x,packet)
        jacobians.append(h.copy())
        return pred,h
    checks=[]
    rows=[]
    with patch.object(module.ref,'geometry',observe):
        for e in archived:
            t=e['t']
            if t>1:
                sources[2]+=diagonal(.03**2,0)
                sources[3]+=diagonal(0,.01**2)
            result=filt.step(t,frames[t])
            if result['action']!=e['action']:
                raise ValueError('frozen gate changed')
            np.testing.assert_allclose(result['stat'],e['stat'],atol=1e-11,rtol=1e-13)
            np.testing.assert_allclose(filt.P.diagonal(),e['covariance_diag'],rtol=1e-13,atol=1e-15)
            accepted=e['action']=='ACCEPT'
            if accepted:
                # The newest nine columns of the actual residual transfer are exactly K.
                K=filt.transfer[:,-9:]
                A=np.eye(13)-K@jacobians[-1]
                sources=A@sources@A.T
                sources[4]+=K@module.ref.R@K.T
            error=float(np.max(np.abs(sources.sum(axis=0)-filt.P)))
            np.testing.assert_allclose(sources.sum(axis=0),filt.P,atol=1e-13,rtol=0)
            checks.append(dict(scene=scene,t=t,gate=e['action'],max_abs_matrix_error=error))
            if t not in TARGETS:
                continue
            for axis,label in enumerate(('Car1 x','Car1 y','Car2 x','Car2 y')):
                car,coord=divmod(axis,2)
                sigma=np.sqrt(filt.P[axis,axis])
                k=NormalDist().inv_cdf(.995)
                k_split=NormalDist().inv_cdf(.9975)
                B=float(.02*np.abs(K[axis]).sum()) if accepted else None
                hist=e['cars'][car]['history_B'][coord]
                if accepted:
                    pos=slice(2*car,2*car+2)
                    sigmas=np.sqrt(filt.P.diagonal()[pos])
                    original=.02*np.abs(K[pos]).sum(axis=1)+k*sigmas
                    np.testing.assert_allclose(np.linalg.norm(original),e['cars'][car]['hcpl']['original'])
                rows.append(dict(scene=scene,t=t,axis=label,gate=e['action'],
                    **dict(zip(NAMES,sources[:,axis,axis])),total_m2=filt.P[axis,axis],
                    current_B_m=B,history_B_m=hist,gaussian_original_m=k*sigma,
                    gaussian_split_m=k_split*sigma,original_CPL_m=B+k*sigma if accepted else None))
    return rows,checks


def write(name,rows):
    with (OUT/name).open('w') as f:
        w=csv.DictWriter(f,rows[0],lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def plot(rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,2,figsize=(12,7),layout='constrained',sharey=True)
    colors=['#285780','#f1ae4b','#579581','#ac72a1','#929aa5']
    labels=['Initial position','Initial link biases','Position process','Bias process','Range noise']
    for col,scene in enumerate(('nominal','wall')):
        for i,car in enumerate(('Car1','Car2')):
            ax=axes[i,col]
            data=[r for r in rows if r['scene']==scene and car in r['axis']]
            x=np.array([3*j+z for j in range(5) for z in (0,1)])
            bottom=np.zeros(10)
            for key,color,label in zip(NAMES,colors,labels):
                height=np.array([r[key]*1e4 for r in data])
                ax.bar(x,height,bottom=bottom,color=color,label=label,width=.92)
                bottom+=height
            ax.set_xticks(x,[f"{r['t']}\n{r['axis'][-1]}" for r in data])
            ax.set_title(car+' · '+scene)
            if not col: ax.set_ylabel('Position variance (cm²)')
            if i: ax.set_xlabel('State time (s) and coordinate')
    axes[0,0].legend(fontsize=8,ncol=2)
    fig.savefig(OUT/'sources.png',dpi=160)


if __name__=='__main__':
    rows,checks=[],[]
    with tempfile.TemporaryDirectory() as tmp:
        mod=frozen_filter(Path(tmp))
        for scene in ('nominal','wall'):
            r,c=analyze(mod,scene)
            rows.extend(r)
            checks.extend(c)
    write('axis_sources.csv',rows)
    write('matrix_checks.csv',checks)
    plot(rows)
    print('rows',len(rows),'full matrices',len(checks),'max error',max(c['max_abs_matrix_error'] for c in checks))
