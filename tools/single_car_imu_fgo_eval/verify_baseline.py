"""Independent frozen-publication and frontend readback, without graph imports."""
import argparse
import bisect
import csv
import gzip
import json
import math
from pathlib import Path
import statistics

from meta import LEGACY,ROOT,finish,save,sha,start

ARMS=('legacy_cold_full_history','analytic_warm_full_history','analytic_warm_fixed_20s')
POSE_FIELDS=('base_x_m','base_y_m','yaw_rad','antenna_x_m','antenna_y_m','aligned_odom_antenna_x_m','aligned_odom_antenna_y_m')


def compare_publications(actual,archived,tolerance):
    if len(actual)!=len(archived):raise ValueError('publication coverage changed')
    maxima={key:0. for key in POSE_FIELDS};status={}
    for a,b in zip(actual,archived):
        for key in ('state_time_s','availability_cutoff_s','status','accepted_graph','graph_states','marginalizations'):
            if a[key]!=b[key]:raise ValueError('frozen discrete behavior changed: '+key)
        for key in POSE_FIELDS:
            d=float(a[key])-float(b[key])
            if key=='yaw_rad':d=math.atan2(math.sin(d),math.cos(d))
            maxima[key]=max(maxima[key],abs(d))
        for key in ('range_medians_json','sample_counts_json'):
            if json.loads(a[key])!=json.loads(b[key]):raise ValueError('frozen frontend changed: '+key)
        status[a['status']]=status.get(a['status'],0)+1
    if max(maxima.values())>tolerance:raise ValueError('pose differs beyond inherited reproduction tolerance: '+str(maxima))
    return {'rows':len(actual),'max_abs_component_difference':maxima,'status_counts':status,
            'timing_and_iteration_counts_excluded_from_numerical_equality':True,'tolerance_from_old_protocol':tolerance}


def interpolate(available,stamp):
    times=[r['header_s'] for r in available];index=bisect.bisect_left(times,stamp)
    if index<len(times) and times[index]==stamp:return available[index]['value'],available[index]['received_s']
    if index==0 or index==len(times):return None,None
    a,b=available[index-1],available[index];t=(stamp-a['header_s'])/(b['header_s']-a['header_s'])
    return [x+t*(y-x) for x,y in zip(a['value'],b['value'])],max(a['received_s'],b['received_s'])


def check_frontend(events,updates,protocol):
    odom=[];uwb=[];last_yaw=None
    for event in events:
        if event['kind']=='odom':
            e=dict(event);e['value']=list(e['value']);angle=e['value'][2]
            if last_yaw is not None:angle=last_yaw+math.atan2(math.sin(angle-last_yaw),math.cos(angle-last_yaw))
            e['value'][2]=angle;last_yaw=angle;odom.append(e)
        elif event['kind']=='uwb':uwb.append(event)
    checked=0
    for u in updates:
        stamp,deadline=u['state_time_s'],u['availability_cutoff_s']
        if deadline!=stamp+protocol['replay']['release_delay_s']:raise ValueError('one-second waiting changed')
        local,dependency=interpolate([e for e in odom if e['received_s']<=deadline],stamp)
        if local is None:
            if u['pose'] is not None:raise ValueError('missing odom bracket hidden')
            continue
        if max(abs(x-y) for x,y in zip(local,u['local_odom']))>1e-12:raise ValueError('local interpolation differs')
        grouped={};receipts=[dependency]
        for e in uwb:
            if e['received_s']>deadline or abs(e['header_s']-stamp)>protocol['replay']['range_bin_half_width_s']:continue
            accepted=False
            for anchor,value in e['value'].items():
                if anchor not in protocol['model']['anchors_xyz_m'] or not math.isfinite(value) or value<=0 or value-protocol['model']['range_bias_m'][anchor]<=0:continue
                grouped.setdefault(anchor,[]).append(value);accepted=True
            if accepted:receipts.append(e['received_s'])
        expected={k:statistics.median(v) for k,v in grouped.items() if len(v)>=protocol['replay']['minimum_samples_per_link']}
        if expected!=u['range_medians_m'] or {k:len(grouped.get(k,[])) for k in protocol['model']['anchors_xyz_m']}!=u['range_sample_counts']:
            raise ValueError('median/sample policy or arrival cutoff changed')
        if max(receipts)>deadline or u['dependency_receipt_max_s']>deadline:raise ValueError('future input entered a publication')
        checked+=1
    return {'publications_with_independent_bracket_and_range_reconstruction':checked,
            'late_or_future_data_used':False,'header_not_reinterpreted_as_calibrated_physical_time':True}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--packets',type=Path,required=True)
    p.add_argument('--baseline',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();run=start(args.output,'single_car_FGO_independent_legacy_publication_readback')
    try:
        protocol=json.loads(LEGACY.read_text());checks=[]
        for case in protocol['cases']:
            with gzip.open(args.packets/case['id']/'legacy_events.jsonl.gz','rt') as f:events=[json.loads(line) for line in f]
            for arm in ARMS:
                directory=args.baseline/case['id']/arm;old=ROOT/'docs/field_tests/single_car_fixed_lag_20261022/results'/case['id']/arm
                with (directory/'published.csv').open() as f:a=list(csv.DictReader(f))
                with (old/'published.csv').open() as f:b=list(csv.DictReader(f))
                exact=compare_publications(a,b,protocol['evaluation_only']['baseline_reproduction_tolerance_m'])
                updates=json.loads((directory/'updates.json').read_text());front=check_frontend(events,updates,protocol)
                if arm=='analytic_warm_fixed_20s':
                    if max(int(r['graph_states']) for r in a)>21:raise ValueError('old window state bound')
                    prior=json.loads((directory/'final_boundary_prior.json').read_text())
                    if len(prior['matrix'])!=3 or len(prior['offset'])!=3:raise ValueError('unexpected original prior dimension')
                checks.append({'case_id':case['id'],'arm':arm,'numerical':exact,'independent_frontend':front})
        save(args.output/'verification.json',{'status':'DONE','all_passed':True,'checks':checks,
            'online_optimizer_or_jacobian_imported':False,'new_IMU_FGO_runs':0,
            'scope':'all original three-arm outputs and old frontend; F1-F3/4D bias marginalization not executed'})
        finish(args.output,run,'DONE');return 0
    except Exception as e:finish(args.output,run,'FAILED',e);raise


if __name__=='__main__':raise SystemExit(main())
