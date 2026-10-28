#!/usr/bin/env python3
"""Stage C exact T08/T10 member extraction and input audit only, no estimator."""
import argparse
import json
from pathlib import Path
import shutil
import tarfile
from io_utils import ROOT,sha,dump,external,git_state,sources
from field_inputs import export
from field_readback import verify

ARCHIVE_SHA='b7cec6f75584e583e66946fd669dc7495d10e3bcbebc0b67fa480b65b53fd1bf'

def run(archive,output,stage_b):
    output=external(output);output.mkdir(exist_ok=False);stage_b=Path(stage_b)
    if git_state()['worktree_dirty']:raise ValueError('commit input adapter before export')
    for receipt in ('old-readback-v2/audits.json','old-prefix-v2/receipt.json'):
        if json.loads((stage_b/receipt).read_text())['status']!='PASS':raise ValueError('Stage B prerequisite')
    if sha(archive)!=ARCHIVE_SHA:raise ValueError('Release asset SHA')
    manifest_path=ROOT/'docs/field_tests/20261024_25/manifest.json';manifest=json.loads(manifest_path.read_text())
    entries={x['id']:x for x in manifest['formal_bags'] if x['id'] in ('T08','T10')}
    if len(entries)!=2 or 'retry' not in entries['T10']['relative_path']:raise ValueError('successful retry only')
    index=dict(stage='C',**git_state(),source_sha256=sources(),release_sha256=ARCHIVE_SHA,manifest_sha256=sha(manifest_path),cells=[],input_checks=[])
    for case in ('T08','T10'):
        e=entries[case]
        for method in ('M0','M1','M2','M3'):
            index['cells'].append(dict(case=case,method=method,status='BLOCKED',execution='NOT_RUN',bag_sha256=e['sha256'],
                missing=['approved per-car odom/base to antenna transform','bound per-car initial room yaw (T10 Car2 candidate null)','per-session common sampling clock mapping and physical timing uncertainty','per-car/day axis/noise approval'],
                rationale='No complete frozen numerical candidate; no identity transform/clock invention; input audit may proceed'))
    dump(output/'RUN_PLAN.json',index)
    for case in ('T08','T10'):
        e=entries[case];bag=output/Path(e['relative_path']).name
        with tarfile.open(archive,'r:gz') as tf:
            member=tf.getmember(e['relative_path'])
            if not member.isfile() or member.size!=e['size_bytes']:raise ValueError('member identity/size')
            with tf.extractfile(member) as src,bag.open('xb') as dst:shutil.copyfileobj(src,dst)
        if sha(bag)!=e['sha256']:raise ValueError('member SHA')
        exported=export(case,bag,output/case,e['sha256']);checked=verify(bag,output/case)
        if checked['packets_checked']!=e['expected_messages']:raise ValueError('message count')
        dump(output/(case+'_readback.json'),checked)
        index['input_checks'].append(dict(case=case,status='PASS',packets=checked['packets_checked'],bag_sha256=e['sha256'],
            input_manifest_sha256=sha(output/case/'manifest.json'),readback_sha256=sha(output/(case+'_readback.json'))))
        print(case,checked['status'],checked['packets_checked'],flush=True)
    index['status']='INPUT_AUDIT_COMPLETE_GLOBAL_RUNS_BLOCKED';dump(output/'RUN_INDEX.json',index)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--archive',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--stage-b-artifacts',required=True,type=Path)
    a=p.parse_args();run(a.archive,a.output,a.stage_b_artifacts)
