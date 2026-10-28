#!/usr/bin/env python3
"""Read-only proof evidence and scope checks, no new numerical configurations."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
DOCS = ROOT/'docs/research/cooperative_followup_20261029/b_method'
BASE = '0ef38e8b84dc88cb7b0e26fea595ac05c5162676'
ALLOWED = ('tools/cooperative_followup_20261029/b_method/',
           'docs/research/cooperative_followup_20261029/b_method/')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify():
    run=json.loads((DOCS/'results/run.json').read_text())
    for rel,h in run['source_input_sha256'].items(): assert sha(ROOT/rel)==h,rel
    for name,h in run['outputs'].items(): assert sha(DOCS/'results'/name)==h,name
    for rel in ['tools/cooperative_followup_20261029/b_method/analyze.py',
                'tools/cooperative_followup_20261029/b_method/PROOF_CONFIG.json']:
        frozen=subprocess.check_output(['git','show',run['code_commit']+':'+rel],cwd=ROOT)
        assert hashlib.sha256(frozen).hexdigest()==sha(ROOT/rel),rel
    index=json.loads((DOCS/'SOURCE_INDEX.json').read_text())
    for item in index['files']:
        p=ROOT/item['path'];assert sha(p)==item['sha256'],p
        raw=subprocess.check_output(['git','show',item['fixed_read_ref']+':'+item['path']],cwd=ROOT)
        assert hashlib.sha256(raw).hexdigest()==item['sha256']
    proof=json.loads((DOCS/'results/exact_worlds.json').read_text())
    compact=json.loads((DOCS/'results/pr72_compact_check.json').read_text())
    assumptions=json.loads((DOCS/'B_ASSUMPTIONS.json').read_text())
    assert proof['status']=='PASS' and proof['world_count']==2
    assert len(proof['exact_checks'])==10 and not proof['online_health_or_truth_used']
    a,b=proof['worlds'];assert a['accurate_source']!=b['accurate_source']
    assert a['reconstructed_online_observations']==b['reconstructed_online_observations']
    assert [x['antenna_positions_m'] for x in a['outputs']]==[x['antenna_positions_m'] for x in b['outputs']]
    assert len(compact['contrasts'])==4 and len(compact['cost_rows'])==8
    assert not compact['original_RMSE_recomputed'] and not compact['original_timestep_budget_rechecked']
    assert assumptions['candidate_mechanism'] is None and assumptions['decision']=='必须先补可信信息'
    assert run['new_FGO_runs']==run['new_seeds']==run['new_static_2D_configs']==0
    assert run['B4_candidate_experiment']=='NOT_OPENED'
    changed=subprocess.check_output(['git','diff',BASE,'--name-only'],cwd=ROOT,text=True).splitlines()
    extra=subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()
    assert all(p.startswith(ALLOWED) for p in changed+extra),changed+extra
    if (DOCS/'SHA256SUMS.txt').exists():
        for line in (DOCS/'SHA256SUMS.txt').read_text().splitlines():
            h,rel=line.split('  ',1);assert sha(ROOT/rel)==h,rel
    result=dict(status='PASS',exact_worlds=2,exact_math_check_classes=10,
        compact_difference_rows=4,cost_summary_rows=8,original_fixed_source_files=len(index['files']),
        frozen_B_source_matches_commit=True,ownership='only assigned b_method paths',
        new_FGO_runs=0,new_seeds=0,new_static_2D_configs=0,
        check_source_sha256=sha(Path(__file__)),
        limitations='evidence/identity checks only; no original PR72 optimizer or full-journal re-audit, no real accuracy validation')
    print(json.dumps(result,ensure_ascii=False,sort_keys=True));return result


if __name__=='__main__': verify()
