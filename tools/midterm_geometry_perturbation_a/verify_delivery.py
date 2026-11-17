"""Independent primary paired contrasts, call ledger and frozen hashes; no optimization."""
from common import *
from model import CFG
import argparse,collections
from scipy.stats import chi2

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--results',required=True,type=Path);ap.add_argument('--output',required=True,type=Path);a=ap.parse_args();p=a.results;d=cached_npz(p/'readback/POINTS.npz');sel=read(p/'readback/SELECTION.json');rows=list(csv.DictReader((p/'readback/ENDPOINT_METRICS.csv').open()));contrasts=list(csv.DictReader((p/'contrasts/GEOMETRY_CONTRASTS.csv').open()));checks=0;maxdiff=0.;draw=np.random.default_rng(CFG['bootstrap_seed']).integers(0,40,(10000,40));cut=float(chi2.ppf(.95,2))
    for car in [1,2]:
      for metric in ['multiple_groups','selected_group_point95']:
        differences=[]
        for seed in CFG['seeds']:
            values=[]
            for cid in ['g00','g02']:
                s=next(s for s in sel if s['condition']==cid and s['method']=='B2' and s['seed']==seed)
                if metric=='multiple_groups':values.append(float(s['accepted_groups']>1))
                else:
                    members=s['selected_group_indices'];permember=[]
                    for i in members:
                        hits=0
                        for k in range(car-1,12,2):hits+=int(np.isfinite(d['q'][i,0,k]) and d['q'][i,0,k]<=cut)
                        permember.append(hits/6)
                    values.append(sum(permember)/len(permember) if permember else 0.)
            differences.append(values[1]-values[0])
        delta=np.array(differences);lo,hi=np.quantile(delta[draw].mean(axis=1),[.025,.975]);z=next(z for z in contrasts if z['method']=='B2' and z['car']==str(car) and z['contrast']=='0.5-minus-0' and z['metric']==metric)
        for x,key in [(delta.mean(),'difference'),(lo,'ci_low'),(hi,'ci_high')]:maxdiff=max(maxdiff,abs(float(x)-float(z[key])));assert maxdiff<1e-12
        checks+=1
    ledger=list(records(p/'EXECUTION_LEDGER.jsonl.gz'));assert len(ledger)==2400 and len({z['file'] for z in ledger})==2400 and sum(z['optimizer_calls'] for z in ledger)==2400
    for z in ledger:assert hashlib.sha256(canonical(z['attempt'])).hexdigest()==z['attempt_sha256']
    ends=list(records(p/'ENDPOINTS.jsonl.gz'));assert len(ends)==1200
    for stage in ['P0','P1']:
        expected=collections.Counter(z['stages'][stage]['category'] for z in ends);actual=collections.Counter(z['category'] for z in ledger if z['file'].endswith('-'+stage+'.json.gz'));assert expected==actual
    for path,h in read(DOC/'FREEZE_MANIFEST.json')['files'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==h,path
    for folder in ['midterm_noise_scale_a','midterm_weak_geometry_a']:
        for path,h in read(ROOT/'docs/research'/folder/'SHA256SUMS.json')['files'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==h,path
    # Pairwise group invariants, with method known explicitly rather than inferred by size.
    by={(z['id'],z['method'],z['init']):z['stages']['P1'] for z in ends};group_checks=0
    for g in csv.DictReader((p/'readback/GROUPS.csv').open()):
        z=[by[g['id'],g['method'],ini] for ini in g['members'].split(';')]
        for i,x in enumerate(z):
            for y in z[i+1:]:
                assert legacy.distance(x['estimate'],y['estimate'])<=.01
                assert abs(x['cost']-y['cost'])<=1e-6+1e-5*max(1,abs(x['cost']),abs(y['cost']))
                if g['method']=='B2':assert abs(x['estimate'][-1]-y['estimate'][-1])<=.01
                group_checks+=1
    save(a.output,dict(primary_rows_independently_recomputed=checks,max_primary_mean_ci_difference=maxdiff,attempt_stage_pairs=2400,actual_calls=2400,group_pair_constraints_checked=group_checks,frozen_files_unchanged=True,old_deliveries_unchanged=True,optimizer_calls=0));print(read(a.output))
if __name__=='__main__':main()
