#!/usr/bin/env python3
"""Read-only link/source/count checks for this documentation package."""
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[5]
OWN = Path(__file__).resolve().parent.parent


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def validate():
    claims = list(csv.DictReader((OWN/'CLAIM_EVIDENCE.csv').open()))
    assert len(claims) == 16 and len({r['claim_id'] for r in claims}) == 16
    for row in claims:
        for k in ('code_provenance_json','config_sha256_json','inputs_json','complete_fault_labels','result_paths_json','result_sha256_json'):
            json.loads(row[k])
        for p, h in json.loads(row['result_sha256_json']).items(): assert sha(ROOT/p) == h, p
    source = json.loads((OWN/'SOURCE_INDEX.json').read_text())
    for p in source['files']: assert sha(ROOT/p['path']) == p['sha256'], p['path']
    figures = json.loads((OWN/'FIGURES.json').read_text()); assert len(figures)==6
    for f in figures:
        assert not f['redrawn']; assert sha(ROOT/f['path'])==f['sha256']
        assert sha(ROOT/f['evidence'])==f['evidence_sha256']
    links = 0
    for p in OWN.glob('*.md'):
        for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', p.read_text()):
            if target.startswith(('http:', 'https:', '#')): continue
            target = target.split('#')[0]
            assert (p.parent/target).resolve().exists(), (p.name, target)
            links += 1
    n = json.loads((OWN/'numeric_check/receipt.json').read_text())
    assert (n['status'],n['rows_read'],n['valid'],n['warmup'],n['stop_samples']) == ('PASS',752,736,16,40)
    assert n['estimator_runs'] == n['video_processing_runs'] == 0
    assert sha(OWN/'tools/recompute_pr65.py') == n['source_script_sha256']
    for p,h in n['source_sha256'].items(): assert sha(ROOT/p)==h,p
    allowed = 'docs/research/paper_scope_20261028/evidence/'
    changed = subprocess.check_output(['git','diff','7b67c66f2470d23f6c876f45b6543f72fab66391','--name-only'],cwd=ROOT,text=True).splitlines()
    untracked = subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()
    assert all(p.startswith(allowed) for p in changed+untracked), changed+untracked
    result = dict(status='PASS',claims=len(claims),figures=len(figures),source_files=len(source['files']),
        local_markdown_links=links,numeric_receipt='PASS',ownership='all changes in owned evidence directory',
        estimator_runs=0,video_processing_runs=0,validator_sha256=sha(Path(__file__)),
        scope='documentation links, bytes and compact numeric counts; not algorithm or physical reference acceptance')
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    return result


if __name__ == '__main__': validate()
