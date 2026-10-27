"""Resealed corrupt private output copies must fail semantic FGO readback."""
import argparse
import copy
import gzip
import json
from pathlib import Path
import shutil
from meta import LEGACY,finish,save,sha,start
from verify_fgo import inspect_run,loadlines,require


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--packets',type=Path,required=True);p.add_argument('--adapted',type=Path,required=True);p.add_argument('--matrix',type=Path,required=True);p.add_argument('--execution-checkout',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run=start(a.output,'B_FGO_semantic_negative_controls')
    try:
        case='004023';source=a.matrix/(case+'_F3');before=sha(source/'updates.jsonl.gz');original=loadlines(source/'updates.jsonl.gz');entry=next(x for x in json.loads((a.adapted/'index.json').read_text())['cases'] if x['case_id']==case)
        flat=loadlines(a.adapted/case/'events.jsonl.gz');events=loadlines(a.packets/case/'legacy_events.jsonl.gz');legacy=json.loads(LEGACY.read_text());checks=[]
        for mode in ('gyro_sign','future_dependency','hidden_odom_yaw','lost_bias_cross_information','lost_affine_offset','retained_UWB_double_count'):
            dest=a.output/mode;shutil.copytree(source,dest);rows=copy.deepcopy(original)
            if mode=='gyro_sign':rows[2]['angular_interval']['segments'][0]['rate_rad_s']+=.1
            elif mode=='future_dependency':rows[2]['angular_interval']['segments'][0]['dependency']['receive_epoch_ns']=rows[2]['availability_cutoff_epoch_ns']+1
            elif mode=='hidden_odom_yaw':rows[2]['prediction_pose'][2]+=.1
            else:
                r=next(x for x in rows if x.get('marginalization_details'));m=r['marginalization_details'][0]
                if mode=='lost_bias_cross_information':
                    matrix=m['prior_after']['matrix']
                    for i in range(4):
                        for j in range(4):
                            if i!=j:matrix[i][j]=0.
                elif mode=='lost_affine_offset':m['prior_after']['offset']=[0.]*4
                else:m['linearization_input']['observations'][1]={'node_2':3.}
            path=dest/'updates.jsonl.gz'
            # This is an intentionally corrupted private COPY, never original input/output.
            with gzip.open(path,'wt') as f:
                for r in rows:f.write(json.dumps(r,allow_nan=False)+'\n')
            metadata=json.loads((dest/'run.json').read_text())
            for output in metadata['outputs']:output['sha256']=sha(dest/output['relative_path'])
            (dest/'run.json').write_text(json.dumps(metadata,indent=2)+'\n')
            try:inspect_run(dest,flat,events,legacy,a.execution_checkout,entry['config_sha256']['F3'])
            except ValueError as e:
                reason=str(e);require('SHA' not in reason,'semantic negative failed only at hash gate');checks.append(dict(mutation=mode,status='REJECTED',reason=reason,hashes_resealed=True))
            else:raise ValueError('semantic mutation was accepted: '+mode)
        require(before==sha(source/'updates.jsonl.gz'),'original run changed')
        save(a.output/'verification.json',dict(status='PASS',checks=checks,original_unchanged=True,real_additional_estimator_runs=0))
        finish(a.output,run,'DONE');return 0
    except Exception as e:finish(a.output,run,'FAILED',e);raise


if __name__=='__main__':raise SystemExit(main())
