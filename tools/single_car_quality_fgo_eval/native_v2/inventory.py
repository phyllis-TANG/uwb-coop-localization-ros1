"""Exact frozen eight-run and twenty-control completeness/source verification."""
import argparse
import csv
import json
from pathlib import Path
from .common import begin,finish,lines,require,sha,write


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepared',type=Path,required=True);p.add_argument('--performance',type=Path,required=True);p.add_argument('--controls',type=Path,required=True);p.add_argument('--all-wall',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();v=begin(a.output,'B_complete_frozen_field_matrix_and_controls_inventory')
    try:
        frozen=json.loads((a.prepared/'binding.json').read_text());matrix=json.loads((a.performance/'matrix.json').read_text());wanted={(c,g) for c in ('004023','005135') for g in ('Q0','Q1','Q2','Q3')};actual=[(r['case_id'],r['group']) for r in matrix['runs']];require(len(actual)==8 and set(actual)==wanted and matrix['status']=='DONE','missing/duplicate/failed main run');require({p.name for p in a.performance.iterdir() if p.is_dir()}=={c+'_'+g for c,g in wanted},'unindexed/extra performance run')
        rows=[];source=None
        for case,group in sorted(wanted):
            folder=a.performance/(case+'_'+group);meta=json.loads((folder/'run.json').read_text());entry=next(r for r in frozen['matrix'] if r['case_id']==case and r['group']==group);require(meta['status']=='DONE' and not meta['worktree_dirty'] and meta['code_commit']==matrix['execution_commit'],'main exact clean execution');require(meta['config_sha256']==entry['config_sha256'] and meta['input_sha256']==entry['input_sha256'],'frozen per-run config/input SHA');require(meta['timing_mode']=='paced_actual','nonpaced main result')
            if source is None:source=meta['source_sha256']
            require(source==meta['source_sha256'],'main sources differ by method')
            for item in meta['outputs']:require(sha(folder/item['relative_path'])==item['sha256'],'main result output checksum')
            old=list(csv.DictReader((a.prepared/'prior/F0_F3'/(case+'_'+entry['base_arm'])/'published.csv').open()));published=lines(folder/'publications.jsonl.gz');require([r['row']['state_time_s'] for r in published]==[float(r['state_time_s']) for r in old],'precise original publication grid coverage');rows.append(dict(case_id=case,group=group,run_sha256=sha(folder/'run.json'),publications=len(published),actual_command_argv=meta['command_argv']))
        original_names={c+'_'+g+'_'+variant for c in ('004023','005135') for g in ('Q2','Q3') for variant in ('prefix','intervention')};extended_names={c+'_'+g+'_'+target for c in ('004023','005135') for g in ('Q2','Q3') for target in ('node_2','node_3','node_8')};require({p.name for p in a.controls.iterdir() if p.is_dir()}==original_names,'original controls missing/extra');require({p.name for p in a.all_wall.iterdir() if p.is_dir()}==extended_names,'all-wall controls missing/extra');controls=[]
        for root,names in [(a.controls,original_names),(a.all_wall,extended_names)]:
            for name in sorted(names):
                folder=root/name;meta=json.loads((folder/'run.json').read_text());s=json.loads((folder/'summary.json').read_text());require(meta['status']=='DONE' and not meta['dirty'] and meta['code_commit']==matrix['execution_commit'],'control original clean execution/source');require(s['source_sha256']==source,'control kernel differs from main');require(s['publications']==38,'unexpected control prefix coverage')
                for item in meta['outputs']:require(sha(folder/item['relative_path'])==item['sha256'],'control output checksum')
                for item in meta['inputs']:
                    candidates=[root/Path(item['path']).name for root in (a.controls,a.all_wall)]
                    require(any(p.is_file() and sha(p)==item['sha256'] for p in candidates),'actual control input/config SHA changed or portable input absent')
                controls.append(dict(name=name,run_sha256=sha(folder/'run.json'),publications=s['publications'],actual_command_argv=meta['command_argv'],input_sha256=s['input_sha256'],config_sha256=s['config_sha256']))
        require(len(controls)==20,'all twenty controls required');write(a.output/'verification.json',dict(status='PASS',execution_commit=matrix['execution_commit'],main_runs=rows,controls=controls,main_run_count=8,main_publications=sum(r['publications'] for r in rows),control_run_count=20,control_publications=sum(r['publications'] for r in controls),missing_duplicate_extra_or_failed=0,all_source_sha256=source,no_new_estimator_runs=True));finish(a.output,v);return 0
    except Exception as e:finish(a.output,v,e);raise


if __name__=='__main__':raise SystemExit(main())
