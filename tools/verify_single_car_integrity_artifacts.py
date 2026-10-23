#!/usr/bin/env python3
"""Read-only scientific artifact audit, optionally persist a new audit JSON."""
import argparse
import csv
import json
from pathlib import Path
from run_single_car_integrity_experiment import ROOT,verify,sha,write
from single_car_integrity_compat import VERSION,verify_record


def audit(out):
    p=json.loads((out/'protocol.json').read_text());verify(out)
    inventory=json.loads((out/'run_inventory.json').read_text());count=0;hypotheses=0;imports=0;resolutions=[]
    for record in inventory:
        assert record['status']=='completed',record['id']
        path=out/'runs'/record['id']
        resolutions.append(verify_record(out,ROOT,record,p))
        rows=[json.loads(line) for line in (path/'output/updates.jsonl').open()]
        assert len(rows)==record['output_count']
        assert all(r['graph_states']<=21 for r in rows)
        assert all(r['dependency_receipt_max_s'] is None or r['dependency_receipt_max_s']<=r['availability_cutoff_s'] for r in rows)
        for row in rows:
            assert row['state_time_s']+1==row['availability_cutoff_s']
            assert row['availability_cutoff_s']<=row['M0_available_receipt_s']<=row['M1_available_receipt_s']<=row['M2_available_receipt_s']
            for method in ['M1','M2']:
                if not row[method]['available']:assert row[method]['alarm'] is None
            for excluded,h in row['exclusion_hypotheses'].items():
                assert excluded not in h['source_anchor_ids'];assert h['excluded_observations_ever_ingested']==0
                assert h['graph_states']<=21
                if h['available']:
                    assert h['current_anchor_count']>=3 and h['xy_rank']==2
                    assert h['graph_jacobian_rank']==3*h['graph_states']
                hypotheses+=1
        count+=len(rows)
        if record.get('imported_from') and record['group']!='historical':
            imports+=1  # Verify archived input bytes; do not regenerate sensors during audit.
    results=out/'results_reviewed';metrics=list(csv.DictReader((results/'metrics.csv').open()))
    assert len(metrics)==87
    assert sum(r['group']=='diagnostic' for r in metrics)==72
    assert sum(r['group']=='development' for r in metrics)==15
    for record in inventory:
        if record['group']=='historical':continue
        rows=list(csv.DictReader((results/'evaluated_runs'/record['id']/'timeseries.csv').open()))
        methods={m:[r for r in rows if r['method']==m] for m in ['M0','M1','M2']}
        for a,b,c in zip(*methods.values()):
            assert all(a[k]==b[k]==c[k] for k in ['state_time_s','published_antenna_x_m','published_antenna_y_m','error_m'])
    assert all(float(r['unalerted_exceed_0p5_s'])==0 for r in metrics if r['group']=='diagnostic')
    carry=next(r for r in metrics if r['id']=='test_two_anchors_1702' and r['method']=='M2')
    assert carry['alarm_already_active_at_fault_onset']=='True' and carry['new_alarm_onset_during_fault']=='False'
    return dict(runs_checked=len(inventory),updates_checked=count,independent_hypothesis_records_checked=hypotheses,
                imported_nominal_sensor_inputs_hash_verified=imports,synthetic_inputs_regenerated=0,
                development_metric_rows=15,diagnostic_metric_rows=72,total_metric_rows=87,
                M0_M1_M2_position_and_error_identical=True,unavailable_never_concluded_no_alarm=True,
                future_receipts_not_used=True,execution_sources_verified=True,compatibility_version=VERSION,
                supplemental_onset_audit_passed=True,input_resolution_records=resolutions)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--experiment',type=Path,required=True);parser.add_argument('--output',type=Path)
    args=parser.parse_args();result=audit(args.experiment.resolve())
    if args.output:
        if args.output.exists():raise FileExistsError(args.output)
        write(args.output,result)
    print(json.dumps(result))


if __name__=='__main__':main()
