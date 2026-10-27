#!/usr/bin/env python3
"""Post-freeze acceptance v1.1. No estimator, policy, graph or evaluation imports.

The v1 execution-source glob intentionally excludes this versioned subdirectory.
Its hashes are recorded separately; it never edits the execution evidence.
"""
import argparse
import csv
from collections import Counter, defaultdict
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import statistics

VERSION='quality_fgo_acceptance_v1.1'

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()

def load(p):return json.loads(Path(p).read_text())
def jsonl(p):
    with gzip.open(p,'rt') as f:return [json.loads(s) for s in f if s.strip()]
def csvrows(p):
    with Path(p).open() as f:return list(csv.DictReader(f))
def writecsv(p,rows):
    if not rows:return
    with Path(p).open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def expected_cells(protocol):
    return {f'{scene}_seed{seed}__{g}' for scene,seed,g in itertools.product(protocol['validation']['scenarios'],protocol['validation']['seeds'],protocol['groups'])}

def matrix_gate(state,protocol):
    expected=expected_cells(protocol);counts=Counter(c['cell_id'] for c in state['cells']);actual=set(counts);errors=[]
    if state.get('stage')!='validation':errors.append('not a validation checkpoint')
    if state.get('status')!='DONE':errors.append('checkpoint is not DONE')
    if state.get('evaluation_errors'):errors.append('checkpoint evaluation errors')
    if expected-actual:errors.append('missing cells: '+str(sorted(expected-actual)))
    if actual-expected:errors.append('unexpected cells: '+str(sorted(actual-expected)))
    if any(v!=1 for v in counts.values()):errors.append('duplicate cell IDs')
    if any(c.get('status')!='DONE' or c.get('returncode')!=0 for c in state['cells']):errors.append('failed or nonzero-return cells')
    return expected,errors

def recovery(rows,available,end,applicable):
    """Candidate onset is retrospective; confirmation is the THIRD online output."""
    after=[r for r in rows if r['state_epoch_ns']>=end]
    result=dict(recovery_applicable=applicable,trial_start_state_epoch_ns=None,trial_start_available_epoch_ns=None,recovery_onset_state_epoch_ns=None,recovery_onset_available_epoch_ns=None,online_confirm_state_epoch_ns=None,online_confirm_available_epoch_ns=None,onset_delay_s=None,online_confirm_delay_s=None,censored=True)
    if not applicable:return result
    trial=next((r for r in after if r['policy']['state']=='recovering' and r['policy']['monitorable'] is True),None)
    if trial:result.update(trial_start_state_epoch_ns=trial['state_epoch_ns'],trial_start_available_epoch_ns=available[trial['publication_id']]['available_receive_epoch_ns'])
    for i in range(len(after)-2):
        triple=after[i:i+3]
        if all(r['policy']['state']=='normal' and r['policy']['monitorable'] is True and r['policy']['information_multiplier']==1 for r in triple) and triple[-1]['state_epoch_ns']-triple[0]['state_epoch_ns']==2*10**9:
            first,last=triple[0],triple[-1];onset=available[first['publication_id']]['available_receive_epoch_ns'];confirmed=available[last['publication_id']]['available_receive_epoch_ns']
            result.update(recovery_onset_state_epoch_ns=first['state_epoch_ns'],recovery_onset_available_epoch_ns=onset,online_confirm_state_epoch_ns=last['state_epoch_ns'],online_confirm_available_epoch_ns=confirmed,onset_delay_s=(onset-end)/1e9,online_confirm_delay_s=(confirmed-end)/1e9,censored=False);break
    return result

def exposure(rows,available):
    result=dict(observed_link_s=0.,known_link_s=0.,unknown_link_s=0.,known_lowered_positive_s=0.,known_disabled_s=0.,known_attenuated_total_s=0.,unknown_held_lowered_positive_s=0.,unknown_held_disabled_s=0.,unknown_held_attenuated_total_s=0.,known_attenuated_segments=0,unknown_held_attenuated_segments=0)
    previous_known=previous_unknown=False
    for i,r in enumerate(rows):
        now=available[r['publication_id']]['available_receive_epoch_ns'];end=available[rows[i+1]['publication_id']]['available_receive_epoch_ns'] if i+1<len(rows) else now;dt=(end-now)/1e9
        if dt<0:raise ValueError('availability went backwards')
        known=r['policy']['monitorable'] is True;g=r['policy']['information_multiplier'];result['observed_link_s']+=dt;result['known_link_s' if known else 'unknown_link_s']+=dt
        if known:
            result['known_lowered_positive_s']+=dt*(0<g<1);result['known_disabled_s']+=dt*(g==0);result['known_attenuated_total_s']+=dt*(g<1)
        else:
            result['unknown_held_lowered_positive_s']+=dt*(0<g<1);result['unknown_held_disabled_s']+=dt*(g==0);result['unknown_held_attenuated_total_s']+=dt*(g<1)
        active_known=known and g<1;active_unknown=not known and g<1
        result['known_attenuated_segments']+=int(active_known and not previous_known);result['unknown_held_attenuated_segments']+=int(active_unknown and not previous_unknown);previous_known,previous_unknown=active_known,active_unknown
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--experiment',type=Path,required=True);p.add_argument('--readback',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=a.experiment;out=a.output;out.mkdir(parents=True,exist_ok=False)
    state=load(root/'checkpoint.json');protocol=load(root/'protocol.json');expected,errors=matrix_gate(state,protocol);reader=load(a.readback/'readback.json');counts=Counter(c['cell_id'] for c in reader['cells'])
    reader_subset_pass=bool(reader['cells']) and all(c.get('status')=='PASS' for c in reader['cells'])
    if reader.get('status')!='PASS' or set(counts)!=expected or any(v!=1 for v in counts.values()) or not reader_subset_pass:errors.append('independent reader is incomplete, duplicated or failed')
    if set(p.name for p in (root/'runs').iterdir())!=expected:errors.append('run directory set differs from expected matrix')
    expected_inputs={f'{scene}_seed{seed}' for scene,seed in itertools.product(protocol['validation']['scenarios'],protocol['validation']['seeds'])}
    if set(p.name for p in (root/'inputs').iterdir())!=expected_inputs:errors.append('input case directory set differs from expected matrix')
    metrics=csvrows(root/'metrics.csv');metric_ids=[f"{r['scenario']}_seed{r['seed']}__{r['group']}" for r in metrics]
    if set(metric_ids)!=expected or len(metric_ids)!=len(expected):errors.append('metric rows incomplete or duplicated')
    if state.get('metric_rows')!=len(expected):errors.append('checkpoint metric_rows mismatch')
    if sha(root/'protocol.json')!=state['fingerprint']['protocol_sha256']:errors.append('execution protocol SHA changed')
    source_root=Path(__file__).resolve().parents[3]
    for relative,value in state['fingerprint']['source_sha256'].items():
        if sha(source_root/relative)!=value or sha(root/'source'/relative)!=value:errors.append('frozen execution source mismatch '+relative)
    publication_total=0;coverage=[];exposures=[];recoveries=[];cell_checks=[]
    for cell in state['cells']:
        cid=cell['cell_id'];run=root/cell['output'];case=f"{cell['scenario']}_seed{cell['seed']}"
        try:
            meta=load(run/'run.json');pubs=jsonl(run/'publications.jsonl.gz');avrows=jsonl(run/'availability.jsonl.gz');available={r['publication_id']:r for r in avrows};ledger=jsonl(run/'quality_ledger.jsonl.gz');truth=jsonl(root/'inputs'/case/'truth.jsonl.gz');labels=load(root/'inputs'/case/'labels.json');events=jsonl(root/'inputs'/case/'events.jsonl.gz');pubids=[r['publication_id'] for r in pubs]
            if cid!=f"{cell['scenario']}_seed{cell['seed']}__{cell['group']}":errors.append(cid+': scenario/seed/group identity mismatch')
            if len(pubs)!=protocol['validation']['expected_publications_per_run'] or len(set(pubids))!=len(pubs):errors.append(cid+': publication count/duplicates')
            expected_states={meta['origin_receive_epoch_ns']+i*10**9 for i in range(1,protocol['validation']['expected_publications_per_run']+1)}
            if {r['state_epoch_ns'] for r in pubs}!=expected_states:errors.append(cid+': scheduled state timestamp set mismatch')
            if len(avrows)!=len(pubs) or set(available)!=set(pubids):errors.append(cid+': availability incomplete/duplicate')
            if meta['status']!='DONE' or meta['publications']!=len(pubs) or meta['code_commit']!=state['code_commit'] or meta['source_sha256']!=state['fingerprint']['source_sha256']:errors.append(cid+': run metadata/source mismatch')
            publication_total+=len(pubs);actual=[v['available_receive_epoch_ns'] for v in avrows];lo,hi=truth[0]['epoch_ns'],truth[-1]['epoch_ns'];covered=sum(lo<=t<=hi for t in actual);missing=len(actual)-covered;post=[(v['available_receive_epoch_ns']-v['availability_cutoff_epoch_ns'])/1e9 for v in avrows];sort=sorted(post)
            series=csvrows(run/'truth_evaluation.csv');seriescovered=sum(bool(r['xy_error_at_actual_available_m']) for r in series)
            if seriescovered!=covered:errors.append(cid+': available-reference coverage mismatch')
            coverage.append(dict(cell_id=cid,scenario=cell['scenario'],seed=cell['seed'],group=cell['group'],publications=len(pubs),available_truth_covered=covered,available_truth_missing=missing,reference_first_epoch_ns=lo,reference_last_epoch_ns=hi,reference_before_start=sum(t<lo for t in actual),reference_after_end=sum(t>hi for t in actual),post_cutoff_processing_scheduling_queue_mean_s=statistics.fmean(post),post_cutoff_processing_scheduling_queue_max_s=max(post),post_cutoff_processing_scheduling_queue_p95_nearest_rank_s=sort[max(0,(95*len(sort)+99)//100-1)],overdue_past_next_cutoff_count=sum(v['available_receive_epoch_ns']>v['availability_cutoff_epoch_ns']+10**9 for v in avrows),after_recorded_input_EOF_outputs=sum(t>events[-1]['receive_epoch_ns'] for t in actual),actual_release_order_monotonic=all(b>=aa for aa,b in zip(actual,actual[1:]))))
            if cell['group'] in ('Q2','Q3'):
                by=defaultdict(list)
                for r in ledger:by[r['target']].append(r)
                fault_targets={e['target'] for e in labels['uwb_fault_events']}
                for target,rs in by.items():exposures.append(dict(cell_id=cid,scenario=cell['scenario'],seed=cell['seed'],group=cell['group'],target=target,healthy_UWB_link=target not in fault_targets,**exposure(rs,available)))
                original=csvrows(root/'fault_events.csv')
                for event in labels['uwb_fault_events']:
                    old=next(e for e in original if e['scenario']==cell['scenario'] and int(e['seed'])==cell['seed'] and e['group']==cell['group'] and e['event_id']==event['event_id']);rs=by[event['target']];rec=recovery(rs,available,event['end_epoch_ns'],old['detected_new_or_escalated_alert']=='True')
                    recoveries.append(dict(cell_id=cid,event_id=event['event_id'],target=event['target'],fault_end_epoch_ns=event['end_epoch_ns'],legacy_retrospective_onset_available_epoch_ns=old['recovered_available_epoch_ns'] or None,**rec))
                    if rec['recovery_onset_available_epoch_ns']!=(int(old['recovered_available_epoch_ns']) if old['recovered_available_epoch_ns'] else None):errors.append(cid+': legacy recovery onset differs')
            cell_checks.append(dict(cell_id=cid,status='CHECKED',publications=len(pubs)))
        except Exception as e:errors.append(cid+': '+type(e).__name__+': '+str(e));cell_checks.append(dict(cell_id=cid,status='ERROR'))
    if publication_total!=protocol['validation']['expected_total_publications']:errors.append('full publication total differs from registered count')
    writecsv(out/'available_reference_and_backlog.csv',coverage);writecsv(out/'known_unknown_exposure.csv',exposures);writecsv(out/'recovery_onset_and_confirmation.csv',recoveries)
    manifest=[dict(path=str(f.relative_to(root)),size_bytes=f.stat().st_size,sha256=sha(f)) for f in sorted(root.rglob('*')) if f.is_file()]
    (out/'experiment_file_manifest.json').write_text(json.dumps(dict(files=manifest),indent=2)+'\n')
    report=dict(version=VERSION,status='PASS' if not errors else 'FAIL',complete_matrix_pass=not errors,existing_reader_subset_pass=reader_subset_pass,expected_cells=len(expected),actual_cells=len(state['cells']),expected_publications=protocol['validation']['expected_total_publications'],actual_publications=publication_total,missing=sorted(expected-{c['cell_id'] for c in state['cells']}),duplicates={k:v for k,v in Counter(c['cell_id'] for c in state['cells']).items() if v!=1},failed_cells=[c['cell_id'] for c in state['cells'] if c['status']!='DONE' or c['returncode']!=0],checkpoint_status=state['status'],errors=errors,cell_checks=cell_checks,execution_commit=state['code_commit'],protocol_sha256=sha(root/'protocol.json'),acceptance_source_sha256={p.name:sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))},output_sha256={p.name:sha(p) for p in out.iterdir() if p.is_file()},coverage_totals=dict(covered=sum(r['available_truth_covered'] for r in coverage),missing=sum(r['available_truth_missing'] for r in coverage),overdue_past_next_cutoff=sum(r['overdue_past_next_cutoff_count'] for r in coverage),after_input_EOF=sum(r['after_recorded_input_EOF_outputs'] for r in coverage)),notes=['Legacy reader passing a subset does not prove full matrix completion.','Recovery onset is retrospective candidate; online confirmation available only after third consecutive known normal output.','known/unknown segments split at availability changes; these are exposure segments, not independent fault events.','Post-cutoff delay combines processing+scheduling+queue; no unsupported separation of pure queue.','This version only reads preserved v1 outputs; no estimator execution or evidence rewrites.'])
    (out/'acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['version','status','complete_matrix_pass','actual_cells','actual_publications','coverage_totals','errors']}));return 0 if not errors else 1

if __name__=='__main__':raise SystemExit(main())
