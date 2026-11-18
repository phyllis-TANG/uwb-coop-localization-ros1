"""Require all 44 paired samples and exact equality before publishing metrics."""
import argparse
import json
from pathlib import Path
import statistics
from core import need
from check import read_json


def summarize(directory):
    root=Path(directory);old=[read_json(root/f'v1_{i:02d}.json') for i in range(44)];new=[read_json(root/f'v2_{i:02d}.json') for i in range(44)]
    env1=read_json(root/'v1_environment.json');env2=read_json(root/'v2_environment.json')
    need({k:v for k,v in env1.items() if k!='kernel'}=={k:v for k,v in env2.items() if k!='kernel'},'BENCHMARK_ENVIRONMENT_DIFFERS')
    rows=[]
    for a,b in zip(old,new):
        fields=('index','case_id','mode','result','projection_hash','queue_hash','recovery_hash','region_status','nodes')
        equal={k:a[k]==b[k] for k in fields}
        need(all(equal.values()) and a['result']['certificate_valid'] and b['result']['certificate_valid'],'CHECKER_PARITY_FAILURE')
        rows.append({'case_id':a['case_id'],'mode':a['mode'],'consistency':equal,'all_equal':True,'nodes':a['nodes'],
                     'v1':a,'v2':b,'check_speedup':a['check_seconds']/b['check_seconds']})
    groups={}
    for mode in ('all','5d','4d','no_peer'):
        rs=[r for r in rows if mode=='all' or r['mode']==mode]
        stat={'count':len(rs)}
        for version in ('v1','v2'):
            stat[version]={}
            for key in ('check_seconds','cold_process_wall_seconds','import_seconds','load_seconds','peak_rss_bytes','child_cpu_seconds'):
                vals=[r[version][key] for r in rs]
                stat[version][key]={'sum':sum(vals),'median':statistics.median(vals),'min':min(vals),'max':max(vals)}
        stat['aggregate_check_speedup']=stat['v1']['check_seconds']['sum']/stat['v2']['check_seconds']['sum']
        stat['aggregate_cold_process_speedup']=stat['v1']['cold_process_wall_seconds']['sum']/stat['v2']['cold_process_wall_seconds']['sum']
        stat['min_individual_check_speedup']=min(r['check_speedup'] for r in rs)
        groups[mode]=stat
    return {'status':'PASS','planned':44,'v1_passed':44,'v2_passed':44,'consistent':44,'failed':0,'unexecuted':0,
            'tree_nodes_checked_per_version':sum(r['nodes'] for r in rows),'search_calls':0,
            'environment':env1,'timing_scope':'One measured pass/version; old pass first, then new pass; no repeated trials or fastest-sample selection. Fresh processes and empty application caches; OS cache not flushed. Results are descriptive, not statistical speed guarantees.',
            'groups':groups,'rows':rows}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    r=summarize(a.directory);Path(a.out).write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k!='rows'},indent=2))
