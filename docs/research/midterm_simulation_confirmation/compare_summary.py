"""Compare independent results with frozen summarizer, without solving."""
import argparse,gzip,json
from pathlib import Path
import numpy as np

def main():
    p=argparse.ArgumentParser();p.add_argument('--frozen-summary',type=Path,required=True);p.add_argument('--independent',type=Path,required=True);p.add_argument('--out',type=Path,required=True);z=p.parse_args()
    b=json.loads(gzip.decompress(z.frozen_summary.read_bytes()));a=json.loads((z.independent/'GROUPS.json').read_text())
    assert b['planned_methods']==b['completed_methods']==b['formal_method_records']==7200 and b['independent_seeds']==50
    assert len(a)==len(b['groups'])==144
    maximum=0.;metrics=0
    for ga,gb in zip(a,b['groups']):
        for k in ga:
            if k!='metrics':assert ga[k]==gb[k],(ga['condition']['id'],ga['method'],k)
        for k,va in ga['metrics'].items():
            vb=gb['metrics'][k];metrics+=1
            for field in va:
                if field in ['mean','ci95'] and va[field] is not None:
                    d=float(np.max(abs(np.array(va[field])-vb[field])));maximum=max(maximum,d);assert d<1e-12
                else:assert va[field]==vb[field]
    result=dict(passed=True,groups=144,metric_summaries=metrics,max_summary_numeric_difference=maximum,planned=7200,completed=7200,independent_seeds=50)
    with z.out.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
