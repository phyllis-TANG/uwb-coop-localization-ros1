"""Bind actual A freeze to exact PR59 field configs, no estimator calls."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tarfile
import jsonschema
from .common import A_SHA,A_DELIVERY,ROOT,begin,finish,lines,require,sha,write


def extract_verified(indexdir,index,output,select):
    archive=indexdir/index.get('archive_relative_path',index.get('archive',{}).get('relative_path',''));expected=index.get('sha256',index.get('archive',{}).get('sha256'))
    receipt=json.loads((indexdir/index['receipt_relative_path']).read_text());require(sha(archive)==expected==receipt['sha256'],'archive byte SHA');seen={}
    with tarfile.open(archive,'r:gz') as tar:
        for member in tar:
            require(member.isfile() and member.name in receipt['member_sha256'] and member.name not in seen,'archive member identity');raw=tar.extractfile(member).read();h=hashlib.sha256(raw).hexdigest();require(h==receipt['member_sha256'][member.name],'archive member SHA');seen[member.name]=h
            relative=member.name.split('/',1)[1]
            if select(relative):
                path=output/relative;require('..' not in path.parts,'safe member path');path.parent.mkdir(parents=True,exist_ok=True)
                with path.open('xb') as f:f.write(raw)
    require(seen==receipt['member_sha256'],'complete archive');return dict(sha256=expected,members=len(seen))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run=begin(a.output,'B_native_field_configuration_freeze')
    try:
        d=ROOT/'docs/field_tests/20261024_25';stage=d/'single_car_quality_fgo_eval_v1';old=d/'single_car_imu_fgo_eval_20261027'
        proof=[extract_verified(stage,json.loads((stage/'ARTIFACTS.json').read_text()),a.output/'stage1',lambda r:r.startswith('ready_for_A_001/')),
          extract_verified(old,json.loads((old/'ARTIFACTS.json').read_text()),a.output/'prior',lambda r:r.startswith('F0_F3/') and r.split('/')[1].endswith(('_F0','_F3')) and r.split('/')[-1] in ('published.csv','run.json','config.json','summary.json'))]
        binding=json.loads((d/'single_car_quality_fgo_v1/A_BINDING.json').read_text());require(binding['quality_execution_commit']==A_SHA,'A exact execution SHA')
        for name,digest in binding['quality_source_sha256'].items():
            path=ROOT/'tools/single_car_quality_fgo'/name;require(sha(path)==digest,'A source freeze '+name)
            blob=subprocess.check_output(['git','show',A_SHA+':tools/single_car_quality_fgo/'+name],cwd=ROOT);require(hashlib.sha256(blob).hexdigest()==digest,'A pinned Git blob '+name)
        require(sha(ROOT/'tools/single_car_quality_fgo/protocol.json')==binding['protocol_sha256'],'A protocol freeze')
        require(sha(ROOT/'tools/single_car_quality_fgo/config.schema.json')==binding['native_schema_sha256'],'A config schema freeze')
        template=json.loads((ROOT/'tools/single_car_quality_fgo/config.template.json').read_text());schema=json.loads((ROOT/'tools/single_car_quality_fgo/config.schema.json').read_text());configs=a.output/'configs';configs.mkdir();matrix=[];casefacts=[]
        for case in ('004023','005135'):
            ready=a.output/'stage1/ready_for_A_001'/case;events=lines(ready/'events.jsonl.gz');origin=events[0]['receive_epoch_ns'];duration=(events[-1]['receive_epoch_ns']-origin)/1e9;limit=max(180,math.ceil(3*duration+30));casefacts.append(dict(case_id=case,records=len(events),duration_s=duration,origin_receive_epoch_ns=origin,max_seconds=limit,event_sha256=sha(ready/'events.jsonl.gz')))
            for group in ('Q0','Q1','Q2','Q3'):
                arm='F0' if group in ('Q0','Q2') else 'F3';base=json.loads((ready/(arm+'_baseline_config.json')).read_text());require(base['scope']=='field','PR59 real config, not synthetic template')
                require(all(item['source_kind']!='synthetic_design' for item in list(base['angular'].values())+list(base['clock_maps'].values())),'synthetic provenance cannot become field calibration')
                prior=a.output/'prior/F0_F3'/(case+'_'+arm);meta=json.loads((prior/'run.json').read_text());require(meta['input']['sha256']==sha(ready/'events.jsonl.gz') and meta['config_sha256']==sha(ready/(arm+'_baseline_config.json')),'prior input/base config identity')
                for name,h in meta['source_sha256'].items():require(sha(ROOT/name)==h,'unchanged native F0/F3 dependency '+name)
                c=copy.deepcopy(template);c.update(group=group,quality_enabled=group in ('Q2','Q3'),base=base);c['timing']=dict(paced=True,scope='same-host recorded-receive paced historical development; host mapping is not physical clock calibration')
                for item in c['controller'].values():item['source']='A exact frozen '+A_SHA+' engineering design; not selected from field residuals/endpoints'
                c['assumptions']+=['Inherited PR59 conditional geometry/lever/initial pose/clock/axes are unchanged; physical uncertainty remains unknown','No manual endpoint/window/fault label passed to estimator or shadow; no tuning from these bags']
                jsonschema.Draft202012Validator(schema).validate(c);target=configs/(case+'_'+group+'.json');write(target,c)
                matrix.append(dict(case_id=case,group=group,base_arm=arm,events_relative_path=str(ready.relative_to(a.output)/'events.jsonl.gz'),input_sha256=sha(ready/'events.jsonl.gz'),config_relative_path=str(target.relative_to(a.output)),config_sha256=sha(target),prior_base_config_sha256=meta['config_sha256'],prior_publication_sha256=sha(prior/'published.csv'),max_seconds=limit))
        write(a.output/'binding.json',dict(status='BOUND_ACTUAL_NATIVE_RULES',A_execution_commit=A_SHA,A_delivery_commit=A_DELIVERY,A_protocol_sha256=binding['protocol_sha256'],A_config_schema_sha256=binding['native_schema_sha256'],source_sha256=binding['quality_source_sha256'],archive_verification=proof,
          native_rule='abs(excluded shadow slant innovation)/.20m; warn1.5x2,disable3x2,clear.75x3+3; unknown holds previous gain; actual missing multiplier null; sqrt(g) post-pseudoHuber exactly once',
          B_fixture_policy_used=False,physical_clock_error_bound_ns=None,physical_axes_verified=False,
          baseline_remeasurement_reason='prior numeric outputs/config/source can be reused, but prior available times were virtual; run four groups under shared same-host paced anchor to measure comparable actual delays',
          performance_runs=8,control_plan=dict(receive_prefix_ns=41000000000,groups=['Q2','Q3'],cases=['004023','005135'],target_intervention='node_10 raw range +1.7m only, private serialized prefix copy; original files immutable',counterfactual_scope='controls not performance runs; use original A Pipeline and read-only buffer observer, no second estimator'),casefacts=casefacts,matrix=matrix))
        run['inputs']=[dict(path=str(stage/'ARTIFACTS.json'),sha256=sha(stage/'ARTIFACTS.json')),dict(path=str(old/'ARTIFACTS.json'),sha256=sha(old/'ARTIFACTS.json'))];finish(a.output,run);return 0
    except Exception as e:finish(a.output,run,e);raise


if __name__=='__main__':raise SystemExit(main())
