"""Verify PR59 archive and materialize only prior inputs/results, no replays."""
import argparse
import hashlib
import json
from pathlib import Path,PurePosixPath
import tarfile
from evidence import ROOT,begin,finish,require,sha,write

OLD=ROOT/'docs/field_tests/20261024_25/single_car_imu_fgo_eval_20261027'
EXPECTED='1ff7558e155b20297c580df6e92cde3560e04342a059522d0bc897ceccc87ff5'
PREFIX='FGO_B_20261027/'


def selected(relative):
    if relative.startswith(('inputs/','A_inputs/','FGO_readback/','FGO_report/')):return True
    if relative=='F0_F3/matrix.json':return True
    parts=PurePosixPath(relative).parts
    if len(parts)==3 and parts[0]=='F0_F3':
        case,arm=parts[1].split('_');require(case in ('004023','005135') and arm in ('F0','F1','F2','F3'),'case/arm allowlist')
        return arm in ('F0','F3') or parts[2] in ('published.csv','config.json','run.json','summary.json')
    return False


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();v=begin(a.output,'PR59_hash_verified_reuse_no_estimator')
    try:
        index=json.loads((OLD/'ARTIFACTS.json').read_text());archive=OLD/index['archive']['relative_path'];receipt=json.loads((OLD/index['receipt_relative_path']).read_text());require(sha(archive)==receipt['sha256']==EXPECTED,'PR59 archive SHA mismatch')
        expected=receipt['member_sha256'];seen={};copied=[]
        with tarfile.open(archive,'r:gz') as tar:
            for m in tar:
                require(m.isfile() and m.name in expected and m.name not in seen,'unexpected or duplicate member');rel=PurePosixPath(m.name)
                require(m.name.startswith(PREFIX) and '..' not in rel.parts and not rel.is_absolute(),'unsafe member path')
                content=tar.extractfile(m).read();digest=hashlib.sha256(content).hexdigest();require(digest==expected[m.name],'member SHA mismatch');seen[m.name]=digest
                relative=m.name[len(PREFIX):]
                if selected(relative):
                    target=a.output/relative;target.parent.mkdir(parents=True,exist_ok=True)
                    with target.open('xb') as f:f.write(content)
                    copied.append(dict(relative_path=relative,sha256=digest,bytes=len(content)))
        require(seen==expected,'archive missing members')
        # Independently bind all reused publications to original run output manifests.
        bindings=[]
        for case in ('004023','005135'):
            for arm in ('F0','F1','F2','F3'):
                runroot=a.output/'F0_F3'/(case+'_'+arm);meta=json.loads((runroot/'run.json').read_text());require(meta['status']=='DONE' and not meta['worktree_dirty'],'prior run not complete/clean')
                pub=next(x for x in meta['outputs'] if x['relative_path']=='published.csv');require(sha(runroot/'published.csv')==pub['sha256'],'reused publication binding')
                inputpath=a.output/'A_inputs'/case/'events.jsonl.gz';configpath=a.output/'A_inputs'/case/(arm+'.json');require(sha(inputpath)==meta['input']['sha256'] and sha(configpath)==meta['config_sha256'],'prior input/config binding')
                if arm in ('F0','F3'):
                    for x in meta['outputs']:require(sha(runroot/x['relative_path'])==x['sha256'],'full reused Q0/Q1 run output binding')
                bindings.append(dict(case_id=case,arm=arm,publication_sha256=pub['sha256'],input_sha256=meta['input']['sha256'],config_sha256=meta['config_sha256'],source_sha256=meta['source_sha256'],execution_commit=meta['code_commit'],mapped_quality_arm={'F0':'Q0','F3':'Q1'}.get(arm)))
        original=ROOT/'docs/field_tests/single_car_fixed_lag_20261022/protocol.json';protocol=json.loads(original.read_text());write(a.output/'evaluation_only.json',dict(protocol_relative_path=str(original.relative_to(ROOT)),protocol_sha256=sha(original),cases=[{k:c[k] for k in ('id','evaluation_window_s','end_antenna_xyz_m')} for c in protocol['cases']],reference_uncertainty_m=None,reference_is_quality_input=False))
        write(a.output/'reuse_manifest.json',dict(status='PASS',archive_sha256=EXPECTED,members_verified=len(seen),selected_files=copied,reused_run_bindings=bindings,
          reused_original_estimator_runs=8,new_estimator_runs=0,A_quality_interface_status='not yet frozen/consumed; Q2/Q3 not executed',
          disclosure='No matrix rerun. All archived data validated; only selected files materialized into new output. Physical clock/axes/odom-origin conditions remain inherited unknowns.'))
        v['inputs']=[dict(path=str(archive),sha256=EXPECTED)];finish(a.output,v);return 0
    except Exception as e:finish(a.output,v,e);raise


if __name__=='__main__':raise SystemExit(main())
