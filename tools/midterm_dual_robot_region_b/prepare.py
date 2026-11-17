"""Lock a verified published A commit and convert exact rationals without rounding."""
import argparse,subprocess
from fractions import Fraction as F
from decimal import Decimal
from common import *
from a_bridge import a_module

def decimal_exact(x):
 v=F(x);n,d=v.numerator,v.denominator;a=b=0
 while d%2==0:a+=1;d//=2
 while d%5==0:b+=1;d//=5
 if d!=1:raise ValueError('nonterminating rational requires explicit interval interface')
 places=max(a,b);n*=2**(places-a)*5**(places-b)
 z=Decimal((int(n<0),tuple(map(int,str(abs(n)))),-places));assert F(z)==v
 return str(z)
def convert(x):
 dec=lambda xs:[[decimal_exact(v) for v in row] for row in xs]
 v=x['noise_model']['variance']
 return dict(schema='DUAL-B-INTERNAL-V1',state_order=['px','py','sx','sy','b'],anchors=dec([x['anchor_map'][f'a{k}'] for k in range(4)]),observations=dec(x['observation_intervals']),measurement_ids=x['measurement_ids'],R=[[decimal_exact(v[i]) if i==j else '0' for j in range(9)] for i in range(9)],domain=dec(x['domains'][:4]),bias_domain=[decimal_exact(z) for z in x['domains'][4]],bias_incidence=x['bias_incidence'],units=x['units'],frame=x['frame'],epoch=x['epoch'],representation=x['representation'])
def prepare(source,sha_a):
 ready_path='docs/research/midterm_dual_robot_contract_a/CONTRACT_READY.json';ready=read(source/ready_path)
 assert ready['schema_version']=='DUAL-A-V1' and ready['status']=='CONTRACT_READY' and ready['baseline_sha']==BASE
 assert len(sha_a)==40 and subprocess.check_output(['git','rev-parse',sha_a],text=True).strip()==sha_a
 hashes=dict(ready['file_hashes']);hashes[ready_path]=sha(source/ready_path)
 for p,h in hashes.items():assert sha(source/p)==h,p
 lock=dict(schema='DUAL-B-SOURCE-LOCK-V1',base=BASE,status='LOCKED',a_sha=sha_a,source_root=str(source),ready_path=ready_path,files=hashes,discovered_remote_branch='research/dual-robot-contract-a',compatibility_note='USER_PROTOCOL_PRECEDENCE.md')
 a=a_module(str(source));a.threshold_check(a.threshold(9),9);a.threshold_check(a.threshold(8),8)
 d=source/'docs/research/midterm_dual_robot_contract_a';evaluation=read(d/'evaluation_only.json');output={'thresholds':{'9':a.threshold(9)['tau'],'8':a.threshold(8)['tau']}}
 for stage,file,evkey in [('deterministic','deterministic.json','deterministic'),('random','random_conditional.json','random_conditional')]:
  xs=read(d/'inputs'/file);evs={e['case_id']:e for e in evaluation[evkey]};cases=[]
  for i,x in enumerate(xs):
   a.validate(x);e=evs[x['case_id']];m=convert(x)
   evaluate=dict(truth=e['truth_position']+[e['truth_bias']],noise=e['noise'] if x['case_id']!='empty_in_domain' else None,noise_basis='A_GENERATED_NOISE' if x['case_id']!='empty_in_domain' else 'NOT_APPLICABLE_OBSERVATION_INTENTIONALLY_REPLACED',geometry=e['geometry'],seed=e.get('seed'))
   cases.append(dict(id=x['case_id'],group='main' if stage=='random' or i<12 else 'special',condition=e['geometry']+'_b'+e['truth_bias'],seed=e.get('seed'),model=m,a_input=x,evaluation=evaluate,budget_override=dict(max_boxes=min(50000,x['budget']['max_nodes']),max_seconds=float(F(x['budget']['max_seconds'])))))
  output[stage]=cases
 assert len(output['deterministic'])==16 and len(output['random'])==120
 write(DOC/'SOURCE_LOCK.json',lock);write(DOC/'INPUTS.json.gz',output)
 print(json.dumps(dict(a_sha=sha_a,verified_files=len(hashes),deterministic=16,random=120,thresholds=output['thresholds'])))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--sha',required=True);a=p.parse_args();prepare(a.source,a.sha)
