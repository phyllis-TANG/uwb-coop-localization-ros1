"""Verify portable saved estimates without original matrix files or optimization."""
import argparse,gzip,json
from pathlib import Path
import numpy as np
from readback import objective,digest,save

def main():
    p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,required=True);p.add_argument('--out',type=Path,required=True);z=p.parse_args();inputs={};count=0;maxg=0.;maxc=0.
    for line in gzip.open(z.evidence,'rt'):
        rec=json.loads(line);v=rec['value']
        if rec['type']=='RUN':meta=v;assert digest(meta['config'])==meta['config_sha256']
        elif rec['type']=='INPUT':
            key=v['condition']['id']+'-s'+str(v['seed']);inputs[key]=v;assert digest(v['obs'])==v['input_sha256']
        else:
            u=inputs[v['unit']];assert digest(u)==v['input_record_sha256']
            for s,r in v['stages'].items():
                x=np.array(r['estimate']);rr,j=objective(u,v['method'],x);g=j.T@rr
                maxg=max(maxg,abs(float(max(abs(g)))-r['gradient_inf']));maxc=max(maxc,abs(float(rr@rr/2)-r['cost']))
                e=x[:24].reshape(6,2,2)-u['truth'];mse=np.mean(np.sum(e*e,axis=-1),axis=0)
                assert np.allclose(mse,r['position_mse'],rtol=0,atol=1e-12)
                assert r['accepted']==(r['endpoint_valid'] and r['scipy_success'] and max(abs(g))<=meta['config']['acceptance']['physical_gradient_inf_max'])
                count+=1
    assert len(inputs)==1800 and count==14400 and maxg<1e-9 and maxc<1e-10
    result=dict(passed=True,inputs=len(inputs),stages=count,max_gradient_norm_difference=maxg,max_cost_difference=maxc,optimizer_calls=0)
    save(z.out,result);print(result)
if __name__=='__main__':main()
