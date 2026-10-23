#!/usr/bin/env python3
"""Read-only audit of raw provenance, causal factors, triggers and archive hashes."""
import argparse
import bisect
import collections
import csv
import json
import math
from pathlib import Path
import numpy as np
from run_two_car_independent_integrity import read,verify_lock,verify_record,sha
from two_car_independent_integrity import ROOT,CARS,ANCHORS
from single_car_integrity import digest
from single_car_fixed_lag import initial_prior


def lines(path):return [json.loads(x) for x in path.open()]


def antenna(pose,lever):
    x,y,a=pose;c,s=math.cos(a),math.sin(a)
    return np.array([x+c*lever[0]-s*lever[1],y+s*lever[0]+c*lever[1]])


def audit(out):
    verify_lock(out);records=read(out/'run_inventory.json');protocol=read(out/'protocol.json')
    final_sources=out/'final_source_hashes.json'
    if final_sources.exists():
        for name,h in read(final_sources).items():
            if sha(ROOT/name)!=h:raise ValueError('Final source/provenance mismatch: '+name)
    summaries=read(out/'results/summary.json')['runs']
    assert len(records)==6 and len({r['id'] for r in records})==6
    assert protocol['thresholds']==dict(M1=1.,M2=.062191200771030145)
    assert sum(r['process_wall_s'] for r in records)<=1800
    total=links=exclusions=raw_headers=0;origins=collections.defaultdict(set);final_times={}
    for record in records:
        verify_record(out,record);assert record['process_wall_s']<=180
        path=out/'runs'/record['id']/'output';rows=lines(path/'updates.jsonl')
        trace=lines(path/'sensor_provenance.jsonl');delivery=lines(path/'delivery_times.jsonl')
        summary=next(s for s in summaries if s['id']==record['id'])
        config=read(out/'configs'/(record['id']+'.json'));model=config['model']
        worker=read(path/'worker_summary.json');eof=worker['input_diagnostics']['eof_receipt_s']
        origins[record['bag_id']].add(worker['input_diagnostics']['origin_bag_receipt_ns'])
        assert len(rows)==len(delivery)==worker['output_count']==summary['output_states']
        assert rows[-1]['state_time_s']+1<=eof
        assert all(b['state_time_s']-a['state_time_s']==1 for a,b in zip(rows,rows[1:]))
        for r in trace:
            assert r['car']==record['car'] and r['topic'].startswith('/'+record['car']+'/')
            assert isinstance(r['original_header_ns'],int) and r['original_header_ns']>0
            expected=(r['bag_receipt_ns']-r['origin_bag_receipt_ns'])/1e9
            assert r['bag_receipt_s']==r['association_time_s']==expected
            raw_headers+=1
        odom=[r for r in trace if r['kind']=='odom'];ot=np.array([r['association_time_s'] for r in odom])
        local=np.array([r['local_pose'] for r in odom]);local[:,2]=np.unwrap(local[:,2])
        uwb=[r for r in trace if r['kind']=='uwb']
        lineage={k:digest(dict(initial_point=initial_prior(model).point.tolist(),excluded=k)) for k in ANCHORS}
        consecutive={'M1':0,'M2':0}
        for row,d in zip(rows,delivery):
            t=row['state_time_s'];cutoff=t+1
            assert row['availability_cutoff_s']==cutoff
            assert cutoff<=row['trigger_receipt_s']<=row['M0_available_receipt_s']<=row['M1_available_receipt_s']<=row['M2_available_receipt_s']<=d['result_available_receipt_s']
            assert row['graph_states']<=21
            assert row['dependency_receipt_max_s'] is None or row['dependency_receipt_max_s']<=cutoff
            i=bisect.bisect_left(ot,t)
            if i<len(ot) and ot[i]==t:indices=[i,i]
            elif 0<i<len(ot):indices=[i-1,i]
            else:indices=None
            if indices is None or ot[indices[1]]>cutoff:
                assert row['pose'] is None and row['status']=='missing_odom_bracket'
                continue
            assert row['pose'] is not None
            for j,p in zip(indices,row['odom_endpoint_provenance']):
                assert p['original_header_ns']==odom[j]['original_header_ns']
                assert p['bag_receipt_ns']==odom[j]['bag_receipt_ns']
                assert p['bag_receipt_s']<=cutoff
            interpolated=np.array([np.interp(t,ot,local[:,j]) for j in range(3)])
            np.testing.assert_allclose(row['local_odom'],interpolated,rtol=0,atol=1e-12)
            observations={};support={}
            for k in ANCHORS:
                samples=[r['wall_raw_m'][k] for r in uwb if abs(r['association_time_s']-t)<=.4
                    and r['bag_receipt_s']<=cutoff and k in r['wall_raw_m']
                    and r['wall_raw_m'][k]>0 and r['wall_raw_m'][k]-model['range_bias_m'][k]>0]
                support[k]=len(samples)
                if len(samples)>=5:observations[k]=float(np.median(samples))
            assert row['range_sample_counts']==support
            assert row['range_medians_m']==observations
            assert set(observations)<=set(ANCHORS)
            post={r['anchor']:r for r in row['postfit_current_residuals']}
            for k,raw in observations.items():
                assert post[k]['corrected_median_m']==raw-model['range_bias_m'][k]
                geom=np.linalg.norm(np.r_[antenna(row['pose'],model['base_to_antenna_body_xy_m']),model['antenna_height_m']]-model['anchors_xyz_m'][k])
                np.testing.assert_allclose(post[k]['raw_residual_m'],geom-(raw-model['range_bias_m'][k]),atol=1e-12,rtol=0)
                links+=1
            for k,h in row['exclusion_hypotheses'].items():
                assert k not in h['source_anchor_ids'] and h['excluded_observations_ever_ingested']==0
                assert h['graph_states']<=21
                retained={key:v for key,v in observations.items() if key!=k}
                lineage[k]=digest([lineage[k],t,row['local_odom'],retained])
                assert lineage[k]==h['prior_lineage_sha256']
                if h['pose'] is not None:
                    np.testing.assert_allclose(h['separation_m'],np.linalg.norm(antenna(h['pose'],model['base_to_antenna_body_xy_m'])-row['antenna_xy_m']),atol=1e-12,rtol=0)
                exclusions+=1
            expected_m1=max(abs(r['normalized_raw_residual']) for r in row['prefit_current_residuals'])
            expected_m2=max(h['separation_m'] for h in row['exclusion_hypotheses'].values() if h['separation_m'] is not None)
            assert row['M1']['statistic']==expected_m1 and row['M2']['statistic']==expected_m2
            for m in ['M1','M2']:
                mon=row[m]
                assert mon['threshold']==protocol['thresholds'][m]
                consecutive[m]=consecutive[m]+1 if mon['available'] and mon['statistic']>mon['threshold'] else 0
                assert mon['alarm']==(consecutive[m]>=2) if mon['available'] else mon['alarm'] is None
            total+=1
        for m in ['M1','M2']:
            assert summary[m]['available_s']==sum(r[m]['available'] for r in rows)
            assert summary[m]['alarm_s']==sum(r[m]['alarm'] is True for r in rows)
        final_times[record['id']]=dict(first=rows[0]['state_time_s'],last=rows[-1]['state_time_s'],eof=eof)
        assert summary['endpoint']['full_window_present'] and summary['endpoint']['conditional_stop_supported']
    assert all(len(v)==1 for v in origins.values())
    def count(name):return sum(1 for _ in csv.DictReader((out/'results'/name).open()))
    assert count('states.csv')==total and count('links.csv')==4*total and count('exclusions.csv')==4*total
    assert count('correspondence.csv')==48
    return dict(runs_verified=6,published_states_verified=total,wall_bins_verified=links,
        independent_exclusion_records_verified=exclusions,raw_header_records_verified=raw_headers,
        common_origins_ns={k:next(iter(v)) for k,v in origins.items()},actual_state_ranges=final_times,
        interpolation_and_bin_dependencies_before_cutoff=True,original_headers_preserved=True,
        correction_applied_once=True,exclusion_lineages_verified=True,triggers_verified=True,
        endpoints_frozen_and_conditionally_stopped=True,new_estimator_runs=0,source_and_output_hashes_verified=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--experiment',type=Path,required=True)
    a=parser.parse_args();print(json.dumps(audit(a.experiment.resolve()),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
