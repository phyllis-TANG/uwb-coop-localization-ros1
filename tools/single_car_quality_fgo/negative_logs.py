#!/usr/bin/env python3
"""Resign private corrupted copies; require semantic rejection, never touch source."""
import argparse
import copy
import json
from pathlib import Path
import shutil
from qaudit import audit
from qio import append,dump,gzip_writer,read_jsonl,sha


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);reports=[]
    for mode in ['score','weight','shadow_leak','availability','affine','posterior_reference']:
        target=a.output/mode;shutil.copytree(a.run,target)
        name='quality_ledger.jsonl.gz' if mode in ('score','posterior_reference') else 'availability.jsonl.gz' if mode=='availability' else 'graphs.jsonl.gz';path=target/name;rows=list(read_jsonl(path))
        if mode=='score':next(r for r in rows if r['engineering_score'] is not None)['engineering_score']+=1.
        elif mode=='posterior_reference':
            r=next(r for r in rows if r['engineering_score'] is not None);graphs=list(read_jsonl(target/'graphs.jsonl.gz'));main=next(g for g in graphs if g['role']=='main' and g['state_epoch_ns']==r['state_epoch_ns']);r['reference_record_id']=main['record_id'];r['engineering_score']=0.
        elif mode=='availability':rows[0]['available_receive_epoch_ns']=rows[0]['state_epoch_ns']
        elif mode=='weight':
            r=next(r for r in rows if r['role']=='main' and r['row']['accepted_graph']);snapshot=r['row']['objective_snapshot'];key=next(iter(snapshot['quality_weights'][-1]));snapshot['quality_weights'][-1][key]=.37
        elif mode=='shadow_leak':
            r=next(r for r in rows if r['role']!='main' and r['row']['accepted_graph']);r['row']['objective_snapshot']['observations'][-1][r['role']]=4.;r['row']['objective_snapshot']['quality_weights'][-1][r['role']]=1.
        else:
            r=next(r for r in rows if r['row'].get('marginalization_details'));r['row']['marginalization_details'][0]['prior_after']['offset'][0]+=.2
        path.unlink()
        with gzip_writer(path) as stream:
            for r in rows:append(stream,r)
        metadata=json.loads((target/'run.json').read_text())
        for f in metadata['outputs']:
            file=target/f['relative_path'];f['sha256']=sha(file);f['size_bytes']=file.stat().st_size
        dump(target/'run.json',metadata)
        try:report=audit(target,sample_every=1)
        except Exception as error:report=dict(status='FAIL',errors=[type(error).__name__+': '+str(error)])
        reports.append(dict(mode=mode,rejected=report['status']=='FAIL',storage_SHA_resigned=True,errors=report['errors']));print(mode,report['status'],flush=True)
    dump(a.output/'negative_checks.json',dict(status='PASS' if all(r['rejected'] for r in reports) else 'FAIL',cases=reports,original_unchanged=True));return 0 if all(r['rejected'] for r in reports) else 1


if __name__=='__main__':raise SystemExit(main())
