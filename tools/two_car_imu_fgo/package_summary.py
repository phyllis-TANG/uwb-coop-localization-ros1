#!/usr/bin/env python3
"""Copy compact saved evidence into the owned documentation directory."""
import argparse
import csv
import gzip
import json
from pathlib import Path
import shutil
from io_utils import ROOT,sha,dump,sources

DOC=ROOT/'docs/field_tests/20261024_25/two_car_imu_fgo_20261028'

def package(a):
    a=Path(a);fig=DOC/'figures';fig.mkdir(exist_ok=True);review=DOC/'review';review.mkdir(exist_ok=True)
    for p in (a/'synthetic-report-v2').glob('*.png'):shutil.copyfile(p,fig/p.name)
    for p in (a/'old-readback-v2').glob('*.png'):shutil.copyfile(p,fig/('old_'+p.name))
    shutil.copyfile(a/'synthetic-report-v2/TABLES.md',DOC/'SYNTHETIC_TABLES.md')
    for name,src in [('contracts-final.log','tests-final/contracts.log'),('old-prefix.json','old-prefix-v2/receipt.json'),('unaffected.json','tests-bug01-v3/unaffected.json')]:shutil.copyfile(a/src,review/name)
    for name in ('synthetic-readback-v2','old-readback-v2'):
        for f in ('evaluation.json','audits.json','costs.csv'):
            shutil.copyfile(a/name/f,review/(name+'_'+f))
        for f in ('metrics.csv','contrasts.csv','propagation.csv','responses.csv'):
            if (a/name/f).exists():
                with (a/name/f).open('rb') as src,gzip.GzipFile(filename=str(review/(name+'_'+f+'.gz')),mode='wb',mtime=0) as dst:shutil.copyfileobj(src,dst)
    configs=DOC/'configs';configs.mkdir(exist_ok=True)
    for p in (a/'synthetic-v1/inputs').glob('*/config.json'):shutil.copyfile(p,configs/(p.parent.name+'.json'))
    for c in ('015334','033248'):shutil.copyfile(a/'old-inputs-v2'/c/'config.json',configs/(c+'.json'))
    stages=[];commands=[];versions={}
    for indexname in ('synthetic-v1','old-matrix-v1','repair-v2','synthetic-selected-v2','old-selected-v2','new-inputs-v1'):
        ix=json.loads((a/indexname/'RUN_INDEX.json').read_text());cells=[]
        for c in ix['cells']:
            compact={k:v for k,v in c.items() if k not in ('expected_source_sha256','input_directory','original_run')}
            code=c.get('expected_code_commit',ix.get('code_commit'));compact['code_commit']=code
            versions[code]=c.get('expected_source_sha256',ix.get('source_sha256'))
            if c.get('run_sha256'):
                run=(a/c['run_path']) if 'run_path' in c else a/indexname/'runs'/c['run_id']
                meta=json.loads((run/'run.json').read_text());commands.append(dict(run_id=c['run_id'],index=indexname,execution_commit=meta['code_commit'],argv=meta['command_argv']))
            cells.append(compact)
        stages.append(dict(stage=indexname,status=ix['status'],original_index_sha256=sha(a/indexname/'RUN_INDEX.json'),cells=cells))
    dump(DOC/'RUN_INDEX.json',dict(logical_cells=dict(synthetic=40,old_conditional=8,new_global_blocked=8),
        physical_executions=dict(synthetic_original=40,synthetic_bug_repair=2,old_original=8,old_bug_repair=2,old_prefix_controls=8,new_global=0),
        selection='38+2 synthetic, 6+2 old; all original failures preserved; no new independent validation',stages=stages))
    dump(DOC/'SOURCE_VERSIONS.json',dict(execution_versions=versions,current_delivery_sources=sources(),algorithm_base='ca8fbac4dbdf678074be5fb80bf6aff472d258e6'))
    dump(DOC/'RUN_COMMANDS.json',dict(actual_cwd=str(ROOT),python='/home/ubuntu22/uwb-single-car-quality-fgo-v1-artifacts/venv/bin/python',
        environment={'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1','TMPDIR':str(a/'tmp')},captured_execution_argv=commands))
    evidence=['docs/field_tests/20261024_25/manifest.json','docs/field_tests/20261024_25/geometry.json',
        'docs/field_tests/20261024_25/two_car_fixed_lag_fgo_v1/historical_readiness.json',
        'docs/field_tests/20261017/session_config.json']
    evidence += [f'tools/field_20261024_25/parameter_clock_prep/results/{c}_input_template.json' for c in ('T08','T10')]
    inputs=[]
    for name,cases in [('old-inputs-v2',('015334','033248')),('new-inputs-v1',('T08','T10'))]:
        for c in cases:
            m=json.loads((a/name/c/'manifest.json').read_text());r=json.loads((a/name/(c+'_readback.json')).read_text())
            inputs.append(dict(case=c,manifest=m,readback=r));shutil.copyfile(a/name/(c+'_readback.json'),review/(c+'_input_readback.json'))
    dump(DOC/'FIELD_INPUTS.json',dict(evidence_sha256={p:sha(ROOT/p) for p in evidence},inputs=inputs))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--artifacts',type=Path,required=True);a=p.parse_args();package(a.artifacts)
