#!/usr/bin/env python3
"""Executable old-package prefix controls and exact frozen-F0 regression.

This is an intervention/contract driver, NOT the independent scalar reader.
It necessarily imports replay kernels. Raw/factor readback is independent.py.
"""
import argparse
import copy
import json
from pathlib import Path
from frontend import execute
from pinned import f0_front
from io_utils import dump,lines,write_lines


def stable(v):
    if isinstance(v,dict):return {k:stable(x) for k,x in v.items() if 'wall_s' not in k and not k.startswith('estimated_worker')}
    if isinstance(v,list):return [stable(x) for x in v]
    return v


def verify(matrix,inputs,output):
    output=Path(output);output.mkdir(exist_ok=False);results=[]
    for case in ('015334','033248'):
        config=json.loads((inputs/case/'config.json').read_text());events=list(lines(inputs/case/'events.jsonl.gz'))
        cutoff=events[0]['receive_epoch_ns']+31*10**9
        prefix=[e for e in events if e.get('availability_epoch_ns',e['receive_epoch_ns'])<=cutoff]
        limit=prefix[-1]['availability_epoch_ns']
        for method in ('M0','M1','M2','M3'):
            rows=[];execute(prefix,config,method,rows.append);write_lines(output/(case+'_'+method+'_prefix.jsonl.gz'),rows)
            complete=[r for r in lines(matrix/'runs'/(case+'_'+method)/'updates.jsonl.gz') if r['availability_cutoff_epoch_ns']<=limit]
            if stable(rows)!=stable(complete):raise ValueError('executable receipt-prefix differs '+case+'/'+method)
            base_equal=None
            if method in ('M0','M1'):
                original=[];f=f0_front.JointReplay(config,'D0' if method=='M0' else 'D1',original.append,prefix[0]['receive_epoch_ns'])
                for raw in prefix:
                    v=copy.deepcopy(raw);v['case_id']='synthetic_adapter_'+case;v['receive_epoch_ns']=raw['availability_epoch_ns']
                    if raw['kind'] in ('imu','odom','uwb'):v['header_epoch_ns']=raw['receive_epoch_ns']
                    f.ingest(v)
                f.finish()
                if len(original)!=len(rows):raise ValueError('F0 counts differ')
                for a,b in zip(original,rows):
                    for key in ('pose','prediction_pose','snapshot','optimizer','bins','marginalization_details'):
                        if a[key]!=b[key]:raise ValueError('frozen F0 regression '+key)
                base_equal=True
            results.append(dict(case=case,method=method,status='PASS',publications=len(rows),
                marginalizations=rows[-1]['marginalizations'],frozen_F0_numeric_equal=base_equal,raw_prefix_records=len(prefix),cutoff_epoch_ns=cutoff))
    dump(output/'receipt.json',dict(status='PASS',checks=results,controls_not_additional_main_runs=True,
        shared_online_code_disclosed=True,independent_evidence='separate scalar/raw packet readers'))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--matrix',required=True,type=Path);p.add_argument('--inputs',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();verify(a.matrix,a.inputs,a.output)
