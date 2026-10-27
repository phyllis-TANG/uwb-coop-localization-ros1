#!/usr/bin/env python3
"""Stdlib-only second reader: no online/evaluation module imports."""
import argparse, bisect, csv, gzip, hashlib, json, math
from pathlib import Path

def lines(p):
    with gzip.open(p, 'rt') as f:
        return [json.loads(s) for s in f if s.strip()]

def main():
    p=argparse.ArgumentParser();p.add_argument('--experiment',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    root=a.experiment
    with (root/'metrics.csv').open() as f: rows=list(csv.DictReader(f))
    details=[];normal=[];costs=[]
    for metric in rows:
        case=f"{metric['scenario']}_seed{metric['seed']}";run=root/'runs'/f"{case}__{metric['group']}"
        truth=lines(root/'inputs'/case/'truth.jsonl.gz');stamps=[t['epoch_ns'] for t in truth]
        def at(t):
            if not stamps[0]<=t<=stamps[-1]:return None
            i=bisect.bisect_right(stamps,t)-1;x=truth[i]
            if t==stamps[i]:return x
            y=truth[i+1];u=(t-stamps[i])/(stamps[i+1]-stamps[i])
            return {'pose':[v+u*(w-v) for v,w in zip(x['pose'],y['pose'])], 'bias_rad_s':x['bias_rad_s']+u*(y['bias_rad_s']-x['bias_rad_s'])}
        pubs=lines(run/'publications.jsonl.gz');av={v['publication_id']:v for v in lines(run/'availability.jsonl.gz')}
        for pub in pubs:
            v=av[pub['publication_id']]
            cycle=(v['data_flushed_host_monotonic_ns']-pub['processing_cycle_start_monotonic_ns'])/1e9
            assert cycle>=0
            costs.append(dict(case_id=case,group=metric['group'],publication_id=pub['publication_id'],release_cycle_wall_s=cycle,actual_release_delay_s=v['actual_release_delay_s'],legacy_instrumented_processor_wall_s=v['complete_processor_wall_s'],post_ready_diagnostic_and_output_wall_s=(v['data_flushed_host_monotonic_ns']-pub['host_data_ready_monotonic_ns'])/1e9))
        errors={'all_xy_rmse_state_m':[],'all_yaw_rmse_rad':[],'all_bias_rmse_rad_s':[],'all_xy_rmse_actual_available_m':[]}
        for pub in pubs:
            row=pub['row'];pose=row['pose'];t=at(pub['state_epoch_ns']);now=at(av[pub['publication_id']]['available_receive_epoch_ns'])
            if pose is not None and t:
                errors['all_xy_rmse_state_m'].append(math.hypot(pose[0]-t['pose'][0],pose[1]-t['pose'][1]))
                errors['all_yaw_rmse_rad'].append(math.atan2(math.sin(pose[2]-t['pose'][2]),math.cos(pose[2]-t['pose'][2])))
                if row.get('bias_rad_s') is not None:errors['all_bias_rmse_rad_s'].append(row['bias_rad_s']-t['bias_rad_s'])
            if pose is not None and now:errors['all_xy_rmse_actual_available_m'].append(math.hypot(pose[0]-now['pose'][0],pose[1]-now['pose'][1]))
        checks={}
        for k,v in errors.items():
            actual=math.sqrt(math.fsum(e*e for e in v)/len(v)) if v else None;expected=float(metric[k]) if metric[k] else None
            assert (actual is None and expected is None) or math.isclose(actual,expected,abs_tol=1e-12,rel_tol=1e-12),(case,k,actual,expected)
            checks[k]=actual
        assert len(pubs)==int(metric['publications'])
        details.append({'case_id':case,'group':metric['group'],'publications':len(pubs),'verified':checks})
        if metric['scenario']=='nominal' and metric['group'] in ('Q2','Q3'):
            ledger=lines(run/'quality_ledger.jsonl.gz');by={v['publication_id']:[] for v in pubs}
            for v in ledger:by[v['publication_id']].append(v)
            known=unknown=attenuated=0.;events=0;before=False
            for i,pub in enumerate(pubs):
                t=av[pub['publication_id']]['available_receive_epoch_ns'];end=av[pubs[i+1]['publication_id']]['available_receive_epoch_ns'] if i+1<len(pubs) else t;dt=(end-t)/1e9;assert dt>=0
                ls=by[pub['publication_id']];active=any(v['policy']['information_multiplier']<1 for v in ls)
                known+=dt*any(v['policy']['monitorable'] is True for v in ls);unknown+=dt*sum(v['policy']['monitorable'] is not True for v in ls);attenuated+=dt*active;events+=int(active and not before);before=active
            normal.append(dict(case_id=case,group=metric['group'],vehicle_monitorable_seconds=known,unknown_link_seconds=unknown,vehicle_attenuation_seconds=attenuated,vehicle_events=events))
    output={'status':'PASS','scope':'independent stdlib truth interpolation + math.fsum RMSE + normal event/exposure reader; no estimator reruns','rows':len(rows),'publications':sum(d['publications'] for d in details),'normal':normal,'details':details,'reader_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    with a.output.with_suffix('.release_costs.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(costs[0]));w.writeheader();w.writerows(costs)
    a.output.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:output[k] for k in ['status','rows','publications','normal']}))

if __name__=='__main__':main()
