"""Execute original-A real prefixes/target interventions, then independent compare."""
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
from .common import begin,finish,lines,write_lines,require,sha,write


def semantic(value):
    if isinstance(value,dict):
        return {k:semantic(v) for k,v in value.items() if not (k.endswith('_wall_s') or k.startswith(('estimated_worker_','host_','processing_','frozen_host_')))}
    if isinstance(value,list):return [semantic(v) for v in value]
    return value


def compare(original,altered,full_graphs,full_ledger,target='node_10'):
    graphs=lines(original/'graphs.jsonl.gz');other=lines(altered/'graphs.jsonl.gz');ledger=lines(original/'ledger.jsonl.gz');caches=lines(original/'caches.jsonl.gz');changed_cache=lines(altered/'caches.jsonl.gz');epochs={g['state_epoch_ns'] for g in graphs};want=[r for r in full_graphs if r['state_epoch_ns'] in epochs]
    require(semantic(graphs)==semantic(want),'real receive-prefix graph/prior/initial guess changed');require(semantic(ledger)==semantic([r for r in full_ledger if r['state_epoch_ns'] in epochs]),'real receive-prefix quality decisions changed')
    for snapshots,records in ((caches,graphs),(changed_cache,other)):
        graphmap={r['record_id']:r for r in records}
        for item in snapshots:
            graph=graphmap[item['record_id']];deadline=graph['row']['availability_cutoff_s'];cache=item['cache']
            require(all(r[2]<=deadline+1e-12 for name in ('odom','ranges') for r in cache.get(name,[])),'future record in actual private cache')
            require(all(r['identity']['receive_epoch_ns']<=graph['availability_cutoff_epoch_ns'] for r in cache.get('angular_rows',[])),'future gyro in actual cache')
    before=[g for g in graphs if g['role']==target];after=[g for g in other if g['role']==target];require(bool(before) and semantic(before)==semantic(after),'target-excluded shadow numeric history/initial guess/prior changed')
    c0=[c for c in caches if c['role']==target];c1=[c for c in changed_cache if c['role']==target];require(c0==c1,'target-excluded actual private cache changed')
    for item in c0:
        cache=item['cache'];require(all(target not in row[1] for row in cache['ranges']),'excluded target present in actual range cache');require(all(target not in obs for obs in cache['graph_observations']),'excluded target in historical cache')
    summary=json.loads((original/'summary.json').read_text());require(summary['marginalizations'][target]>0,'control never crossed actual marginalization')
    main0=[g['row']['pose'] for g in graphs if g['role']=='main'];main1=[g['row']['pose'] for g in other if g['role']=='main'];require(main0!=main1,'intervention ineffective: main graph never changed')
    return dict(status='PASS',prefix_publications=len(epochs),prefix_graph_records=len(graphs),prefix_quality_decisions=len(ledger),target_shadow_records=len(before),actual_private_cache_snapshots=len(c0),target_shadow_marginalizations=summary['marginalizations'][target],
      original_full_graph_non_timing_prefix_identical=True,original_full_quality_prefix_identical=True,target_excluded_state_history_initial_guess_cache_prior_identical=True,main_output_changed=True,
      canonicalization='Remove actual host/compute timing only. Original source/message identities remain references to immutable recorded data; altered serialized input has separate real SHA. Non-target values and all other original metadata remain byte-valued equal.')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepared',type=Path,required=True);p.add_argument('--performance',type=Path,required=True);p.add_argument('--execution-checkout',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();v=begin(a.output,'B_real_input_prefix_and_target_only_shadow_controls');checks=[]
    try:
        binding=json.loads((a.prepared/'binding.json').read_text());env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
        for case in ('004023','005135'):
            ready=a.prepared/'stage1/ready_for_A_001'/case;events=lines(ready/'events.jsonl.gz');origin=events[0]['receive_epoch_ns'];prefix=[r for r in events if r['receive_epoch_ns']<=origin+41_000_000_000];altered=copy.deepcopy(prefix);mutations=0
            for row in altered:
                if row['kind']=='uwb' and 'node_10' in row['value']:row['value']['node_10']+=1.7;mutations+=1
            require(mutations>0,'no target intervention');p0=a.output/(case+'_prefix.jsonl.gz');p1=a.output/(case+'_node10_intervention.jsonl.gz');write_lines(p0,prefix);write_lines(p1,altered)
            for before,after in zip(prefix,altered):
                expected=copy.deepcopy(before)
                if expected['kind']=='uwb' and 'node_10' in expected['value']:expected['value']['node_10']+=1.7
                require(expected==after,'counterfactual changed non-target input')
            for group in ('Q2','Q3'):
                c=json.loads((a.prepared/'configs'/(case+'_'+group+'.json')).read_text());c['timing']=dict(paced=False,scope='accelerated causal verification controls only; excluded from main performance/availability comparison');cp=a.output/(case+'_'+group+'_control_config.json');write(cp,c);jobs=[]
                for variant,path in [('prefix',p0),('intervention',p1)]:
                    out=a.output/(case+'_'+group+'_'+variant);args=[sys.executable,'-m','tools.single_car_quality_fgo_eval.native_v2.probe_runner','--events',str(path),'--config',str(cp),'--output',str(out)];log=(a.output/(out.name+'.log')).open('x');process=subprocess.Popen(args,cwd=a.execution_checkout,env=env,stdout=log,stderr=subprocess.STDOUT);jobs.append((process,log,out,args));v['estimator_runs']+=1
                for process,log,out,args in jobs:
                    rc=process.wait(timeout=180);log.close();require(rc==0,'original A control failed; preserved '+str(out))
                full=a.performance/(case+'_'+group);result=compare(jobs[0][2],jobs[1][2],lines(full/'graphs.jsonl.gz'),lines(full/'quality_ledger.jsonl.gz'));result.update(case_id=case,group=group,original_events_sha256=sha(ready/'events.jsonl.gz'),prefix_file_sha256=sha(p0),altered_file_sha256=sha(p1),original_records=len(events),prefix_records=len(prefix),changed_target_components=mutations,commands=[j[3] for j in jobs]);checks.append(result);print(case,group,'PASS',flush=True)
        write(a.output/'verification.json',dict(status='PASS',checks=checks,control_estimator_runs=v['estimator_runs'],main_performance_runs_added=0,A_kernel_modified=False,original_inputs_modified=False,
          observer='B execution-only wrapper invokes original frozen A Pipeline and snapshots actual private front buffers read-only; offline comparator imports no A policy/graph/Jacobian/qaudit'))
        finish(a.output,v);return 0
    except Exception as e:finish(a.output,v,e);raise


if __name__=='__main__':raise SystemExit(main())
