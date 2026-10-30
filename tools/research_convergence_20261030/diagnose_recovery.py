"""Read saved declarations to locate recovery costs; no release rule or rerun."""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
from statistics import mean

PROFILE='B2_local|scale=1.0|a=0.01'
ENDS={'car1_common_wall_bias':38,'wall_short':31,'wall_long':52}
ALS=(.05,.10,.20)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True,help='New JSON file')
    args=parser.parse_args()
    root=args.repo/'docs/research/integrity_validation_20261030'
    with (root/'PER_SEED.csv').open(newline='') as stream: metrics=list(csv.DictReader(stream))
    provenance={};output=[]
    for condition,end in ENDS.items():
        for seed in range(5101,5109):
            path=root/'units'/f'{seed}_{condition}'/'declarations.csv.gz'
            provenance[path.relative_to(args.repo).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
            with gzip.open(path,'rt',newline='') as stream:
                rows=[r for r in csv.DictReader(stream) if r['profile']==PROFILE and float(r['t_s'])>=end]
            for car in ('car1','car2'):
                selected=[r for r in rows if r['car']==car]
                assert [float(r['t_s']) for r in selected]==list(range(end,64))
                for al in ALS:
                    alarm=sum(r['alarm']=='True' for r in selected)
                    available=sum(r['available']=='True' for r in selected)
                    unknown=sum(r['computable']!='True' for r in selected)
                    overlimit=sum(float(r['xy_error_m'])>al for r in selected)
                    joint=sum(r['alarm']=='True' and float(r['xy_error_m'])<=al for r in selected)
                    hmi=sum(r['available']=='True' and r['alarm']!='True' and float(r['xy_error_m'])>al for r in selected)
                    originals=[r for r in metrics if r['condition']==condition and int(r['seed'])==seed and r['car']==car and r['profile']==PROFILE and float(r['AL_m'])==al and r['period'] in ('recovery','late') and r['coverage']=='all_published']
                    assert len(originals)==2
                    for key,value in (('alarm_s',alarm),('available_s',available),('unknown_s',unknown),('overlimit_s',overlimit),('hmi_s',hmi)):
                        assert sum(float(r[key]) for r in originals)==value
                    output.append(dict(condition=condition,seed=seed,car=car,AL_m=al,post_fault_s=64-end,alarm_s=alarm,
                                       available_s=available,unknown_s=unknown,overlimit_s=overlimit,hmi_s=hmi,
                                       alarm_with_error_at_or_below_assumed_AL_s=joint))
    summaries=[]
    keys=('alarm_s','available_s','unknown_s','overlimit_s','hmi_s','alarm_with_error_at_or_below_assumed_AL_s')
    for condition in ENDS:
        for car in ('car1','car2'):
            for al in ALS:
                rows=[r for r in output if r['condition']==condition and r['car']==car and r['AL_m']==al]
                summaries.append(dict(condition=condition,car=car,AL_m=al,seeds=8,post_fault_s=rows[0]['post_fault_s'],
                                      **{k+'_mean':mean(r[k] for r in rows) for k in keys}))
    report=dict(profile=PROFILE,source_sha256=provenance,per_seed=output,summary=summaries,
                validation='144 seed/car/AL rows; five counters exactly matched to existing recovery+late metrics',
                scope='Retrospective diagnosis with synthetic truth and known fault end; neither is permitted as an online release input. Alarm-with-small-error is not proof a release would be safe. No new tolerance approved.')
    with args.output.open('x',encoding='utf-8') as stream: json.dump(report,stream,indent=2);stream.write('\n')
    print(json.dumps([r for r in summaries if r['condition']=='wall_long' and r['car']=='car2']))

if __name__=='__main__':main()
