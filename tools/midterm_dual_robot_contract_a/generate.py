"""Freeze inputs without importing or calling a localization searcher."""
import argparse
import gzip
import json
import platform
import random
import re
import subprocess
from pathlib import Path
from core import *

GEOMETRIES={'normal':[['-4','-3'],['4','-3'],['4','3'],['-4','3']],
            'near_collinear':[['-4','0'],['-1','1/50'],['1','-1/50'],['4','0']],
            'collinear':[['-4','0'],['-1','0'],['1','0'],['4','0']]}
TRUTH=['-1','1','2','3/2']
DIRECTION=['1','-1','1/2','-1/2','1','-1','1/2','-1/2','1']

def make(case,geometry='normal',bias='0',noise=None,truth=None):
    truth=truth or TRUTH; noise=noise or ['0']*9
    p=list(map(F,truth[:2])); s=list(map(F,truth[2:]))
    obs=[]
    for pos in (p,s):
        for anchor in GEOMETRIES[geometry]:
            a=list(map(F,anchor)); d=sqrt_bounds(sum((v-w)**2 for v,w in zip(pos,a)))
            e=F(noise[len(obs)]); obs.append([str(d[0]+e),str(d[1]+e)])
    d=sqrt_bounds(sum((v-w)**2 for v,w in zip(p,s))); e=F(noise[8])+F(bias)
    obs.append([str(d[0]+e),str(d[1]+e)])
    x={'schema_version':VERSION,'model_id':'dual_robot_single_epoch_diagonal_v1','state_order':ORDER,
       'measurement_ids':IDS,'anchor_map':{f'a{k}':a for k,a in enumerate(GEOMETRIES[geometry])},
       'bias_incidence':[0]*8+[1], 'domains':[['-6','6'] for _ in range(4)]+[['-3/5','3/5']],
       'observation_intervals':obs,'noise_model':{'kind':'known_diagonal_gaussian','dimension':9,
       'variance':['1/625']*9,'independence':'nine_unique_raw_errors','bias_evolution':'single_constant'},
       'threshold_certificate':threshold(9),'arithmetic_policy':POLICY,
       'budget':{'max_nodes':100001,'max_seconds':'120','position_resolution':'1/8','bias_resolution':'1/20'},
       'source_commit':BASE,'case_id':case,'units':'m','frame':'synthetic_xy','epoch':'t0',
       'antenna_reference':'2d_antenna','representation':'enclosing_closed_cartesian_intervals','position_prior':None,'motion':None}
    evaluation={'case_id':case,'geometry':geometry,'truth_position':truth,'truth_bias':bias,'noise':noise,
                'noise_norm_squared':str(sum((F(e)*25)**2 for e in noise)), 'usage':'EVALUATION_ONLY_NEVER_SEARCH_INPUT'}
    return seal(x),evaluation

def write(path,x):
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')

def generate(root):
    root=Path(root); out=root/'docs/research/midterm_dual_robot_contract_a'
    inputs=[]; evaluations=[]
    for geo in GEOMETRIES:
        for b in ('0','3/5'):
            for noisy in (False,True):
                noise=[str(F(v)/25) for v in DIRECTION] if noisy else None
                name=f'{geo}_b{0 if b=="0" else 6}_{"direction" if noisy else "zero"}'
                x,e=make(name,geo,b,noise); inputs.append(x); evaluations.append(e)
    x,e=make('empty_in_domain'); x['observation_intervals'][0]=['100','100']; seal(x)
    e['expectation']='EMPTY: first distance <= sqrt(181), so standardized residual > tau'; inputs.append(x); evaluations.append(e)
    x,e=make('domain_closed_contact',truth=['6','0','2','0'],bias='3/5'); inputs.append(x); evaluations.append(e)
    x,e=make('coincident_zero_distance',truth=['1','1','1','1']); inputs.append(x); evaluations.append(e)
    x,e=make('forced_budget'); x['budget']['max_nodes']=1; seal(x); inputs.append(x); evaluations.append(e)
    # New 20 seeds PER condition: no reuse across six conditions; each used by all methods.
    seeds=list(range(2026111709000000,2026111709000120))
    paths=subprocess.check_output(['git','ls-tree','-r','--name-only',BASE],cwd=root,text=True).splitlines()
    audit=[]; collisions=[]
    for path in paths:
        if 'seed' not in path.lower() and 'registry' not in path.lower(): continue
        if not path.endswith(('.json','.jsonl','.csv','.md','.gz','.py','.txt')): continue
        blob=subprocess.check_output(['git','show',f'{BASE}:{path}'],cwd=root)
        raw=gzip.decompress(blob) if path.endswith('.gz') else blob
        numbers=set(re.findall(rb'(?<!\d)\d{16}(?!\d)',raw))
        collisions.extend(s for s in seeds if str(s).encode() in numbers)
        audit.append({'path':path,'sha256':hashlib.sha256(blob).hexdigest()})
    need(not collisions,'SEED_COLLISION')
    random_inputs=[]; random_eval=[]; j=0
    for geo in GEOMETRIES:
        for b in ('0','3/5'):
            for _ in range(20):
                seed=seeds[j]; j+=1; rng=random.Random(seed)
                # Exact rational value of each saved IEEE Gaussian draw, not rounded decimal.
                noise=[str(F.from_float(rng.gauss(0,1))/25) for _ in range(9)]
                x,e=make(f'random_{seed}',geo,b,noise); e['seed']=seed
                random_inputs.append(x); random_eval.append(e)
    for x in inputs+random_inputs: validate(x)
    write(out/'inputs/deterministic.json',inputs); write(out/'inputs/random_conditional.json',random_inputs)
    write(out/'evaluation_only.json',{'deterministic':evaluations,'random_conditional':random_eval})
    write(out/'SEED_REGISTRY.json',{'source_commit':BASE,'generator_version':'DUAL-A-V1-generate-1',
          'python':platform.python_version(),'algorithm':'CPython random.Random MT19937 + gauss; saved IEEE draws as exact rational; no seed rejection',
          'seeds':seeds,'count':120,'paired_methods':['5d','4d','no_peer'],'prior_registry_audit':audit,
          'collision_count':len(collisions),'scope':'all seed/registry-named tracked text/gzip files at fixed baseline; no assertion about future or external registrations'})
    write(out/'INPUT_INDEX.json',{'deterministic':[{'case_id':x['case_id'],'input_hash':x['input_hash']} for x in inputs],
          'random_conditional':[{'case_id':x['case_id'],'input_hash':x['input_hash']} for x in random_inputs]})
    print(json.dumps({'deterministic':len(inputs),'conditional_random':len(random_inputs),'audited_seed_files':len(audit),'collisions':len(collisions)}))

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('root'); a=p.parse_args(); generate(a.root)
