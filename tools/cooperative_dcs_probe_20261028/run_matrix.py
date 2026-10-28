#!/usr/bin/env python3
"""Full 36 logical index, exactly 27 verified reuses + nine new DCS cells."""
import argparse,json,shutil,sys,time
from pathlib import Path
from collections import Counter
from common import ROOT,HERE,SCENARIOS,SEEDS,METHODS,sha,dump,read,write,external,state,sources,utc
from replay_dcs import execute


def validate(index,complete=False):
    expected={f'{s}_seed{k}__{m}' for s in SCENARIOS for k in SEEDS for m in METHODS};cells=index['cells']
    if len(cells)!=36 or {c['run_id'] for c in cells}!=expected:raise ValueError('exact complete 36-cell membership required')
    for c in cells:
        if c['run_id']!=f"{c['scenario']}_seed{c['seed']}__{c['method']}":raise ValueError('identity mismatch')
        if c['method']=='D3':
            if c['status'] not in (('DONE',) if complete else ('PLANNED_NEW','IN_PROGRESS','DONE')):raise ValueError('new cell invalid status')
        elif c['status']!='REUSED_VERIFIED':raise ValueError('baseline missing verified reuse')
    if complete and index['status']!='DONE':raise ValueError('matrix incomplete')


def freeze(root,testlog,frozenlog):
    root=external(root);reuse=json.loads((root/'REUSE_RECEIPT.json').read_text());cells=list(reuse['cells'])
    if state()['dirty']:raise ValueError('clean committed source required')
    if not all(Path(p).read_text().rstrip().endswith('OK') for p in (testlog,frozenlog)):raise ValueError('test prerequisites')
    if (root/'RUN_PLAN.json').exists():raise FileExistsError('immutable plan')
    for sc in SCENARIOS:
        for seed in SEEDS:
            case=f'{sc}_seed{seed}';files=reuse['inputs'][case]
            cells.append(dict(run_id=case+'__D3',case=case,scenario=sc,seed=seed,method='D3',status='PLANNED_NEW',run_path='new-runs/'+case+'__D3',
                              events_sha256=files['events.jsonl.gz'],config_sha256=files['config.json'],truth_sha256=files['truth.jsonl'],labels_sha256=files['labels.json'],estimator_executed_this_task=True))
    plan=dict(status='FROZEN',created_at_utc=utc(),**state(),source_sha256=sources(),cells=cells,inputs=reuse['inputs'],
        original_reuse_receipt_sha256=sha(root/'REUSE_RECEIPT.json'),dcs_config_sha256=sha(HERE/'dcs_config.json'),phi=1.,test_receipts={str(p):sha(p) for p in (testlog,frozenlog)},
        expected_new=9,expected_reused=27,independent_validation=False)
    validate(plan);dump(root/'RUN_PLAN.json',plan);dump(root/'RUN_INDEX.json',plan)
    for name in plan['source_sha256']:
        dst=root/'source'/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dst)


def run(root):
    root=Path(root);index=json.loads((root/'RUN_INDEX.json').read_text());validate(index)
    if index['status']!='FROZEN' or any(c['status']!='PLANNED_NEW' for c in index['cells'] if c['method']=='D3'):raise ValueError('no retry/resume/overwrite')
    if state()['dirty'] or sources()!=index['source_sha256']:raise ValueError('frozen tested source changed')
    index['status']='RUNNING';dump(root/'RUN_INDEX.json',index)
    for c in index['cells']:
        if c['method']!='D3':continue
        started=time.perf_counter();inp=root/'inputs'/c['case'];out=root/c['run_path'];out.mkdir(parents=True,exist_ok=False)
        assert sha(inp/'events.jsonl.gz')==c['events_sha256'] and sha(inp/'config.json')==c['config_sha256']
        c['status']='IN_PROGRESS';dump(root/'RUN_INDEX.json',index)
        info=dict(status='IN_PROGRESS',**state(),method='D3',source_sha256=index['source_sha256'],command_argv=sys.argv,
                  input_sha256=c['events_sha256'],config_sha256=c['config_sha256'],dcs_config_sha256=index['dcs_config_sha256'],created_at_utc=utc(),timing_origin='current_DCS_virtual_replay')
        dump(out/'run.json',info);shutil.copyfile(inp/'config.json',out/'config.json');shutil.copyfile(HERE/'dcs_config.json',out/'dcs_config.json')
        try:
            config=json.loads((inp/'config.json').read_text());rows=[];worker=execute(read(inp/'events.jsonl.gz'),config,'D3',rows.append)
            write(out/'updates.jsonl.gz',rows)
            dump(out/'summary.json',dict(publications=len(rows),accepted=sum(r['accepted_graph'] for r in rows),status_counts=dict(Counter(r['status'] for r in rows)),
                peak_solve_states=worker.graph.peak_solve_states,peak_transient_states=worker.graph.peak_transient_states,
                sensor_peaks={k:b.sensor_peaks for k,b in worker.binners.items()},peer_peak=worker.peer_peak,
                linearizations=sum(len(r.get('dcs_linearizations',[])) for r in rows),trial_evaluations=sum(len(r.get('dcs_trials',[])) for r in rows),
                actual_peer_factors=sum(r['peer_factor_used'] for r in rows),main_update_wall_s=sum(r['update_wall_s'] for r in rows),marginalizations=worker.graph.marginalizations,
                counters=dict(worker.counters),dcs_phi=1.))
            assert sources()==index['source_sha256']
            info.update(status='DONE',elapsed_with_current_IO_s=time.perf_counter()-started,outputs={p.name:dict(sha256=sha(p),size_bytes=p.stat().st_size) for p in out.iterdir() if p.name!='run.json'})
            dump(out/'run.json',info);c.update(status='DONE',run_sha256=sha(out/'run.json'),elapsed_s=info['elapsed_with_current_IO_s'])
        except BaseException as error:
            info.update(status='FAILED',error=str(error));dump(out/'run.json',info);c.update(status='FAILED',error=str(error));index['status']='FAILED';dump(root/'RUN_INDEX.json',index);raise
        dump(root/'RUN_INDEX.json',index);print(c['run_id'],'DONE',flush=True)
    index['status']='DONE';validate(index,True);dump(root/'RUN_INDEX.json',index)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run']);p.add_argument('--root',type=Path,required=True);p.add_argument('--test-log',type=Path);p.add_argument('--frozen-log',type=Path);a=p.parse_args()
    freeze(a.root,a.test_log,a.frozen_log) if a.phase=='freeze' else run(a.root)
