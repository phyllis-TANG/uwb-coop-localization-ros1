"""Validate saved output consistency without rerunning optimization."""
import gzip, json, hashlib
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
checks=[]
for case in ('A1','B1'):
    for method in ('M2','M3','M3W025'):
        base=HERE/case/method;rows=read(base/'trajectory.json');summary=read(base/'summary.json')
        assert summary['frames']==len(rows)
        assert summary['inputs_sha256']==sha(HERE/case/'bins.jsonl.gz')
        assert summary['config_sha256']==sha(HERE/case/'config.json')
        assert summary['accepted']==sum(r.get('accepted',False) for r in rows)
        for c in ('car1','car2'):assert summary['valid'][c]==sum(r['valid'][c] for r in rows)
        bytime={r['state_ns']:r for r in rows};n=0;marg=0
        with gzip.open(base/'updates.jsonl.gz','rt',encoding='utf-8') as f:
            for line in f:
                item=json.loads(line);r=item['result'];row=bytime[item['state_ns']];n+=1
                assert row['pose']==r['pose'] and row['valid']==r['estimate_valid'] and row['status']==r['status']
                assert np.isfinite(row['pose']).all()
                assert not r['odom_yaw_fallback']
                for c in ('car1','car2'):
                    assert r['estimate_valid'][c]==bool(r['accepted_graph'] and r['angular_valid'][c] and r['numerical_full_rank'])
                marg+=len(r['marginalization_details'])
        assert n==len(rows) and marg==summary['marginalizations']
        checks.append({'case':case,'method':method,'frames_checked':n,'marginalization_records':marg,'trajectory_sha256':sha(base/'trajectory.json'),'summary_sha256':sha(base/'summary.json'),'passed':True})
(HERE/'SAVED_OUTPUT_READBACK.json').write_text(json.dumps({'scope':'saved detailed/compact output and counts consistency; not independent re-solve or full Schur audit','checks':checks},indent=2)+'\n',encoding='utf-8')
print(json.dumps(checks),flush=True)
