"""Frozen per-condition statistics and prespecified descriptive case selection."""
import argparse,collections,json
from pathlib import Path
import numpy as np
from io_utils import read,save,csvsave,interval

def ranks(a):
    a=np.asarray(a);order=np.argsort(a,kind='stable');out=np.empty(len(a),float);i=0
    while i<len(a):
        j=i+1
        while j<len(a) and a[order[j]]==a[order[i]]:j+=1
        out[order[i:j]]=(i+j-1)/2;i=j
    return (out+.5)/len(a)
def analyze(results,out):
    out.mkdir(parents=True,exist_ok=False);meta=read(results/'RUN.json');c=meta['config'];rows=read(results/'ROWS.json.gz');summaries=[];intervals=[];joint=[]
    metrics=['mse1','mse2','rmse1','rmse2','D1','D2','D_accepted1','D_accepted2','B2_B1_1','B2_B1_2','B2_B1_accepted1','B2_B1_accepted2','bias_estimate','b_minus_candidate_mean_m','unabsorbed_injection_rms_m','unabsorbed_candidate_rms_m','unabsorbed_other_rms_m','residual_rms','range_residual_rms_m']
    for q in dict((x['condition']['id'],x['condition']) for x in meta['plan']).values():
        for m in c['methods']:
            rs=sorted([r for r in rows if r['id']==q['id'] and r['method']==m],key=lambda r:r['seed']);n=len(rs);complete=all(r['completed'] for r in rs)
            s={**q,'method':m,'planned':n,'completed':sum(r['completed'] for r in rs),'valid':sum(r['usable'] for r in rs),'accepted':sum(r['accepted'] for r in rs),'numerical_failure':sum(r['completed'] and not r['accepted'] for r in rs),'missing':sum(not r['completed'] for r in rs),'unavailable':sum(not r['usable'] for r in rs),'categories':json.dumps(dict(collections.Counter(r['category'] for r in rs))),'large1':sum(r['large1'] is True for r in rs),'large2':sum(r['large2'] is True for r in rs),'large1_accepted':sum(r['large1'] is True and r['accepted'] for r in rs),'large2_accepted':sum(r['large2'] is True and r['accepted'] for r in rs),'bias_error_valid':sum(r['bias_error'] is not None for r in rs),'bias_error_exceeds':sum(r['bias_error_exceeds'] is True for r in rs)}
            for key in metrics:
                if (key.startswith('B2_B1') or key.startswith('unabsorbed') or key.startswith('bias') or key.startswith('b_minus')) and m!='B2':continue
                a=[r.get(key) for r in rs if r.get(key) is not None];ci=interval(a,n,c,complete);intervals.append({**q,'method':m,'metric':key,**ci});s[key+'_mean']=ci['mean']
                if key in ['rmse1','rmse2','residual_rms','bias_estimate']:
                    for quant in [.5,.9,.95,.99]:s[f'{key}_q{int(quant*100)}']=float(np.quantile(a,quant)) if a else None
                    s[key+'_max']=max(a) if a else None
                    accepted=[r[key] for r in rs if r['accepted'] and r.get(key) is not None];s[key+'_accepted_n']=len(accepted);s[key+'_accepted_mean']=float(np.mean(accepted)) if accepted else None
            for car in [1,2]:
                pairs=[(r['residual_rms'],r[f'rmse{car}']) for r in rs if r['residual_rms'] is not None and r[f'rmse{car}'] is not None]
                corr=None
                if len(pairs)>1:
                    a=np.array(pairs);rx=ranks(a[:,0]);ry=ranks(a[:,1]);corr=float(np.corrcoef(rx,ry)[0,1]) if np.std(rx)>0 and np.std(ry)>0 else None
                joint.append({**q,'method':m,'car':car,'n':len(pairs),'spearman_residual_error':corr})
            summaries.append(s)
    b2=[r for r in rows if r['method']=='B2' and r['usable']];cases=[]
    for r in b2:
        if r['seed']==c['representative_cases']['fixed_seed']:cases.append(dict(rule='fixed_seed',car=None,unit=r['unit'],condition=r['id'],seed=r['seed'],injection=r['injection']))
    for fault in c['matrix']['injections']:
        for car in [1,2]:
            rs=[r for r in b2 if r['injection']==fault];key=f'rmse{car}'
            if not rs:continue
            worst=sorted(rs,key=lambda r:(-r[key],r['id'],r['seed']))[0];cases.append(dict(rule='worst_B2_error',car=car,unit=worst['unit'],condition=worst['id'],seed=worst['seed'],injection=fault,error=worst[key],accepted=worst['accepted']))
            candidates=[]
            for cid in sorted(set(r['id'] for r in rs)):
                xs=[r for r in rs if r['id']==cid and r['residual_rms'] is not None];px=ranks([r['residual_rms'] for r in xs]);py=ranks([r[key] for r in xs])
                for r,x,y in zip(xs,px,py):candidates.append((float(y-x),float(y),r))
            score,pct,chosen=sorted(candidates,key=lambda t:(-t[0],-t[1],t[2]['id'],t[2]['seed']))[0]
            cases.append(dict(rule='residual_error_rank_gap',car=car,unit=chosen['unit'],condition=chosen['id'],seed=chosen['seed'],injection=fault,rank_gap=score,error_percentile=pct,error=chosen[key],residual_rms=chosen['residual_rms'],accepted=chosen['accepted']))
    csvsave(out/'SUMMARY.csv',summaries);csvsave(out/'PAIRED_INTERVALS.csv',intervals);csvsave(out/'RESIDUAL_ERROR.csv',joint);save(out/'SUMMARY.json',summaries);save(out/'INTERVALS.json',intervals);save(out/'CASES.json',cases)
    counts=dict(planned_inputs=len(meta['plan']),planned_methods=len(rows),completed=sum(r['completed'] for r in rows),valid=sum(r['usable'] for r in rows),accepted=sum(r['accepted'] for r in rows),categories=dict(collections.Counter(r['category'] for r in rows)),warning_count=sum(r['warnings'] or 0 for r in rows),by_method={},by_injection={})
    for label,key in [('by_method','method'),('by_injection','injection')]:
        for value in dict.fromkeys(r[key] for r in rows):
            xs=[r for r in rows if r[key]==value];counts[label][value]=dict(n=len(xs),valid=sum(r['usable'] for r in xs),accepted=sum(r['accepted'] for r in xs),large1=sum(r['large1'] is True for r in xs),large2=sum(r['large2'] is True for r in xs))
    save(out/'COUNTS.json',counts);return counts
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();print(analyze(a.results,a.out))
