"""Coverage, size and availability together, averaging candidates within each seed."""
from common import *
from model import CFG
from summarize import interval,mean
import argparse

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True,type=Path);ap.add_argument('--output',required=True,type=Path);a=ap.parse_args();rows=list(csv.DictReader(a.input.open()));out=[]
    for d in CFG['perturbations_m']:
      for m in CFG['methods']:
       for car in [1,2]:
        rr=[r for r in rows if float(r['perturbation_m'])==d and r['method']==m and r['car']==str(car)];assert len(rr)==40
        for mode in ['original','selected','selected_group','all_finite','all_accepted']:
            z=dict(perturbation_m=d,method=m,car=car,mode=mode,planned_seeds=40,planned_points=240)
            for suffix in ['rmse','sqrt_trace','area95','point95','point99','available95','available99','trajectory95','trajectory99']:
                values=[float(r[mode+'_'+suffix]) if r[mode+'_'+suffix]!='' else np.nan for r in rr];z[suffix+'_available_seeds']=int(np.isfinite(values).sum());z[suffix+'_mean']=mean(values)
                if suffix in ['point95','point99']:lo,hi,status=interval(values,40);z[suffix+'_ci_low']=lo;z[suffix+'_ci_high']=hi;z[suffix+'_ci_status']=status
            z['weighted_available_points']=240*z['available95_mean'];z['weighted_covered_points95']=240*z['point95_mean'];z['valid_coverage95']=z['point95_mean']/z['available95_mean'] if z['available95_mean'] else None;out.append(z)
    csvsave(a.output,out)
if __name__=='__main__':main()
