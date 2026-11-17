"""Validate actual frozen receipts/Jacobians and Hessian without additional fitting."""
from common import *
from model import CFG,validate_inputs
from adapter import V
import argparse,inspect

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True,type=Path);ap.add_argument('--output',required=True,type=Path);args=ap.parse_args();rows=list(records(args.run/'INPUTS.jsonl.gz'));inputs={r['id']:r for r in rows};checks=validate_inputs(rows);mr=mj=mh=0.;n=0
    for z in records(args.run/'ENDPOINTS.jsonl.gz'):
        rec=inputs[z['id']];u=copy.deepcopy(rec['input']);u['obs']['start']=rec['initials'][z['init']];m=z['method'];fun,start,receipt=V.objective(SOURCE,u['obs'],m,np.array(u['oracle']) if m=='B3' else None)
        assert receipt['range_sigma']==u['obs']['range_sigma'] and receipt['motion_sigma']==u['obs']['motion_sigma'];assert np.array_equal(start[:24],rec['initials'][z['init']]);assert z['stages']['P0']['solver_input_sha256']==V.digest(receipt)
        x=np.array(z['stages']['P1']['estimate']);r,j=objective(u,m,x);rr,jj=fun(x);mr=max(mr,float(max(abs(r-rr))));mj=max(mj,float(np.max(abs(j-jj))));assert mr<1e-10 and mj<1e-10
        h=exact_hessian(u,m,x);fd=np.empty_like(h)
        for k in range(len(x)):
            dx=np.zeros_like(x);dx[k]=5e-6;rp,jp=objective(u,m,x+dx);rm,jm=objective(u,m,x-dx);fd[:,k]=(jp.T@rp-jm.T@rm)/1e-5
        mh=max(mh,float(np.linalg.norm(h-fd)/np.linalg.norm(h)));assert mh<1e-6;n+=1
    checks.update(configurations=n,max_residual_difference=mr,max_jacobian_difference=mj,max_hessian_relative_difference=mh,extra_optimizer_calls=0);save(args.output,checks);print(checks)
if __name__=='__main__':main()
