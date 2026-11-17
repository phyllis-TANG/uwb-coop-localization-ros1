"""Seed-cluster transverse information summaries and independent Schur check."""
from common import *
from model import CFG
from summarize import interval,mean
from information import analyze
import argparse

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--results',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();out=a.output;out.mkdir(parents=True,exist_ok=False)
    sel=read(a.results/'readback/SELECTION.json');info={(int(r['index']),r['component']):r for r in csv.DictReader((a.results/'information/ENDPOINT_INFORMATION.csv').open())};metrics=list(csv.DictReader((a.results/'readback/ENDPOINT_METRICS.csv').open()));summary=[];paired=[]
    names=['conditional_trace','effective_trace','conditional_min','effective_min','effective_max','transverse_effective_rank','full_rank']
    for cid in sorted({s['condition'] for s in sel}):
      for m in CFG['methods']:
       group=[s for s in sel if s['condition']==cid and s['method']==m]
       for mode in ['original','selected']:
        for component in ['range','range_motion','total']:
         for metric in names:
            v=[float(info[s[mode+'_index'],component][metric]) if s[mode+'_index'] is not None and (s[mode+'_index'],component) in info else np.nan for s in group];lo,hi,status=interval(v,40);summary.append(dict(condition=cid,perturbation_m=float(metrics[group[0]['original_index']]['perturbation_m']),method=m,mode=mode,component=component,metric=metric,planned_seeds=40,available=int(np.isfinite(v).sum()),mean=mean(v),ci_low=lo,ci_high=hi,ci_status=status))
    for m in CFG['methods']:
      for component in ['range','range_motion','total']:
       for metric in names:
        for cid in ['g01','g02']:
            ds=[]
            for seed in CFG['seeds']:
                s0=next(s for s in sel if s['condition']=='g00' and s['method']==m and s['seed']==seed);s1=next(s for s in sel if s['condition']==cid and s['method']==m and s['seed']==seed)
                i,j=s0['selected_index'],s1['selected_index'];ds.append(float(info[j,component][metric])-float(info[i,component][metric]) if i is not None and j is not None else np.nan)
            lo,hi,status=interval(ds,40);paired.append(dict(method=m,component=component,metric=metric,contrast=cid+'-minus-g00',planned=40,available=int(np.isfinite(ds).sum()),difference=mean(ds),ci_low=lo,ci_high=hi,ci_status=status))
    # Check the effective transverse block against an independent inverse marginal,
    # only for full-rank total information at predeclared first-seed original endpoints.
    inputs={r['id']:r['input'] for r in records(a.results/'INPUTS.jsonl.gz')};maxdiff=0.;ncheck=0
    for z in records(a.results/'ENDPOINTS.jsonl.gz'):
        u=inputs[z['id']]
        if u['seed']!=CFG['seeds'][0] or z['init']!='I0' or not z['stages']['P1']['endpoint_valid']:continue
        x=np.array(z['stages']['P1']['estimate']);_,j=objective(u,z['method'],x);rows,mat=analyze(u,z['method'],x);n=len(x);t=np.zeros((n,12))
        for k in range(12):t[2*k+1,k]=1
        cov=np.linalg.solve(j.T@j,np.eye(n));eff=np.linalg.solve(t.T@cov@t,np.eye(12));expected=np.array(mat[-1]['effective']);err=float(np.linalg.norm(eff-expected)/np.linalg.norm(expected));maxdiff=max(maxdiff,err);assert err<1e-7;ncheck+=1
    csvsave(out/'SUMMARY.csv',summary);csvsave(out/'PAIRED.csv',paired);save(out/'CHECKS.json',dict(first_seed_schur_checks=ncheck,max_relative_error=maxdiff,optimizer_calls=0))
if __name__=='__main__':main()
