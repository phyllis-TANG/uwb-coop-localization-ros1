"""Actual native field logs: reseal private corrupt copies, reject semantically."""
import argparse
import copy
import json
from pathlib import Path
import shutil
from .common import begin,finish,lines,write_lines,require,sha,write
from .reader import check_run


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepared',type=Path,required=True);p.add_argument('--performance',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();v=begin(a.output,'B_actual_native_field_semantic_negative_controls')
    try:
        source=a.performance/'004023_Q3';before=sha(source/'run.json');binding=json.loads((a.prepared/'binding.json').read_text());entry=next(r for r in binding['matrix'] if r['case_id']=='004023' and r['group']=='Q3');ready=a.prepared/'stage1/ready_for_A_001/004023';reports=[]
        variants=['score','unknown_gain','unknown_zero_score','recovery_skip','future_support','actual_gain','weighted_objective','shadow_initial_guess','shadow_prior','zero_information_admission','fake_availability','ledger_omission','postfit_weight','message_SHA']
        for mode in variants:
            dest=a.output/mode;shutil.copytree(source,dest);name='quality_ledger.jsonl.gz';rows=lines(dest/name)
            if mode in ('score','unknown_gain','unknown_zero_score','recovery_skip','future_support','actual_gain','zero_information_admission','ledger_omission'):
                if mode=='score':next(r for r in rows if r['engineering_score'] is not None)['engineering_score']+=.2
                elif mode=='unknown_gain':next(r for r in rows if r['policy']['state']=='unknown')['policy']['information_multiplier']=0.
                elif mode=='unknown_zero_score':next(r for r in rows if r['policy']['state']=='unknown')['engineering_score']=0.
                elif mode=='recovery_skip':next(r for r in rows if r['policy']['state']=='recovering')['policy']['state']='normal'
                elif mode=='future_support':rows[0]['target_dependencies'][0]['identity']['receive_epoch_ns']=rows[0]['availability_cutoff_epoch_ns']+1
                elif mode=='actual_gain':next(r for r in rows if r['actual_information_multiplier']==.1)['actual_information_multiplier']=1.
                elif mode=='zero_information_admission':next(r for r in rows if r['actual_information_multiplier']==0.)['information_admitted']=True
                else:rows.pop()
                (dest/name).unlink();write_lines(dest/name,rows)
            elif mode in ('weighted_objective','shadow_initial_guess','shadow_prior'):
                name='graphs.jsonl.gz';rows=lines(dest/name)
                if mode=='weighted_objective':
                    r=next(r for r in rows if r['role']=='main' and any(any(w<1 for w in x.values()) for x in r['row']['objective_snapshot']['quality_weights']));weights=r['row']['objective_snapshot']['quality_weights'];pair=next((x,k) for x in weights for k,w in x.items() if w<1);pair[0][pair[1]]=1.
                elif mode=='shadow_initial_guess':next(r for r in rows if r['role']=='node_10' and r['row'].get('optimizer_initial_guess') is not None)['row']['optimizer_initial_guess'][-1][0]+=.02
                else:next(r for r in rows if r['role']=='node_10' and r['row']['marginalizations']>0)['row']['objective_snapshot']['prior']['matrix'][0][0]+=.1
                (dest/name).unlink();write_lines(dest/name,rows)
            elif mode=='fake_availability':
                name='availability.jsonl.gz';rows=lines(dest/name);rows[0]['available_receive_epoch_ns']-=1000000;(dest/name).unlink();write_lines(dest/name,rows)
            elif mode=='postfit_weight':
                name='publications.jsonl.gz';rows=lines(dest/name);rows[0]['postfit_factor_diagnostics'][0]['actual_weighted_residual']+=.1;(dest/name).unlink();write_lines(dest/name,rows)
            else:
                name='input_decisions.jsonl.gz';rows=lines(dest/name);rows[0]['input']['raw_message_sha256']='f'*64;(dest/name).unlink();write_lines(dest/name,rows)
            meta=json.loads((dest/'run.json').read_text())
            for item in meta['outputs']:item['sha256']=sha(dest/item['relative_path']);item['size_bytes']=(dest/item['relative_path']).stat().st_size
            (dest/'run.json').write_text(json.dumps(meta,indent=2)+'\n')
            try:check_run(dest,ready,entry['config_sha256'],entry['input_sha256'])
            except ValueError as e:
                reason=str(e);require(not reason.startswith('run output SHA'),'only checksum gate rejected corruption');reports.append(dict(mutation=mode,status='REJECTED',reason=reason,output_manifest_SHA_resealed=True));print(mode,'REJECTED',flush=True)
            else:raise ValueError('semantic corruption accepted: '+mode)
        require(sha(source/'run.json')==before,'original result changed');write(a.output/'verification.json',dict(status='PASS',checks=reports,original_results_unchanged=True,new_estimator_runs=0,A_policy_graph_or_qaudit_imported=False));finish(a.output,v);return 0
    except Exception as e:finish(a.output,v,e);raise


if __name__=='__main__':raise SystemExit(main())
