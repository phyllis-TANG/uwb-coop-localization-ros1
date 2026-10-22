#!/usr/bin/env python3
"""Run the frozen three-bag independent/joint comparison and static checks."""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import sys

import numpy as np
import scipy

from single_car_sequential_replay import rotation, wrap
from two_car_updated_comparison import (
    CARS, PEERS, JointObjective, build_inputs, fit_static_wall_bias, read_bag, sha256, solve)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = ROOT/'docs/field_tests/two_car_updated_comparison_20261022/protocol.json'


def serial(value):
    if isinstance(value, np.ndarray):return value.tolist()
    if isinstance(value, np.generic):return value.item()
    if isinstance(value, dict):return {str(k):serial(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)):return [serial(v) for v in value]
    return value


def write_json(path, value):
    path.write_text(json.dumps(serial(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def write_csv(path, rows):
    if not rows:raise ValueError('Empty CSV output '+str(path))
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n')
        writer.writeheader();writer.writerows(rows)


def fingerprint(value):
    return hashlib.sha256(json.dumps(serial(value),sort_keys=True,separators=(',',':'),
                                    allow_nan=False).encode()).hexdigest()


def stats(values):
    values=np.asarray(values,dtype=float)
    if not len(values):return dict(count=0,median_m=None,median_abs_m=None,rms_m=None,max_abs_m=None)
    return dict(count=len(values),median_m=float(np.median(values)),
                median_abs_m=float(np.median(np.abs(values))),rms_m=float(np.sqrt(np.mean(values*values))),
                max_abs_m=float(np.max(np.abs(values))))


def static_checks(protocol,out):
    training=protocol['calibration']['car1']
    run=read_bag(ROOT/training['path'],training['sha256'])
    fitted=fit_static_wall_bias(run,'car1',training['reference_antenna_xyz_m'],protocol['anchors_xyz_m'])
    biases=dict(car1={k:v['bias_m'] for k,v in fitted.items()},
                car2=protocol['calibration']['car2']['range_bias_m'])
    write_json(out/'calibration.json',dict(car1_source=training,car1_link_fit=fitted,
        applied_biases_m=biases,car2_policy=protocol['calibration']['car2'],peer_correction_m=None,
        calibration_diagnostics=run['diagnostics'],dynamic_endpoints_used=False))
    rows,peer_rows=[] ,[]
    validation=[]
    for case in protocol['static_validation']:
        raw=read_bag(ROOT/case['path'],case['sha256'])
        detail=dict(path=case['path'],sha256=case['sha256'],diagnostics=raw['diagnostics'],cars={})
        for car in CARS:
            target=case['antenna_xyz_m'][car]
            errors=[]
            for key,xyz in sorted(protocol['anchors_xyz_m'].items()):
                values=[v[key] for _,v in raw['uwb'][car] if key in v]
                if not values:raise AssertionError('Missing static validation link')
                geometry=float(np.linalg.norm(np.asarray(target)-xyz))
                raw_median=float(np.median(values))
                corrected=raw_median-biases[car][key]
                errors.append(corrected-geometry)
                rows.append(dict(bag=Path(case['path']).name,car=car,anchor=key,
                    samples=len(values),geometry_m=geometry,raw_median_m=raw_median,
                    applied_bias_m=biases[car][key],raw_median_minus_geometry_m=raw_median-geometry,
                    corrected_median_minus_geometry_m=corrected-geometry,reference_source=case['source']))
            detail['cars'][car]=dict(corrected_link_median_errors=stats(errors),
                odom_path_m=float(np.sum(np.linalg.norm(np.diff(np.asarray(raw['odom'][car])[:,1:3],axis=0),axis=1))))
        validation.append(detail)
        distance=float(np.linalg.norm(np.asarray(case['antenna_xyz_m']['car1'])-
                                      case['antenna_xyz_m']['car2']))
        for car in CARS:
            samples=[v[PEERS[car]] for _,v in raw['uwb'][car] if PEERS[car] in v]
            peer_rows.append(dict(bag=Path(case['path']).name,direction=car,
                samples=len(samples),coordinate_reference_3d_m=distance,
                raw_peer_median_m=float(np.median(samples)) if samples else None,
                raw_peer_median_minus_coordinate_reference_m=float(np.median(samples)-distance) if samples else None,
                reference_source=case['source']))
    write_csv(out/'static_wall_transfer.csv',rows)
    write_csv(out/'static_peer_reference_checks.csv',peer_rows)
    write_json(out/'static_validation.json',validation)
    return biases


def evaluate(inputs,fit,evaluation,stationary_car):
    states,ant=fit['states'],fit['antenna_xy']
    endpoint=np.median(ant[:,-5:,:],axis=1)
    target=np.asarray([evaluation['end_antenna_xyz_m'][c][:2] for c in CARS])
    out=dict(optimizer=fit['optimizer'],keyframes=len(inputs['times']),
        first_last_keyframe_s=[float(inputs['times'][0]),float(inputs['times'][-1])],
        endpoint_window_s=inputs['times'][-5:].tolist(),
        endpoint_antenna_xy_m={car:endpoint[ci].tolist() for ci,car in enumerate(CARS)},
        endpoint_difference_m={car:float(np.linalg.norm(endpoint[ci]-target[ci])) for ci,car in enumerate(CARS)},
        wall_factor_count=fit['wall_factor_count'],peer_factor_count=fit['peer_factor_count'],
        cars={},wall_residual_by_link={},stationary_car=stationary_car)
    objective=JointObjective(inputs,fit['peer_factor_count']>0)
    ledger={}
    for ci,car in enumerate(CARS):
        data=inputs['cars'][car];model=data['model'];local=data['local']
        d=np.diff(states[ci,:,:2],axis=0);dl=np.diff(local[:,:2],axis=0)
        body=np.array([rotation(-th)@v for th,v in zip(states[ci,:-1,2],d)])
        local_body=np.array([rotation(-th)@v for th,v in zip(local[:-1,2],dl)])
        errors=np.linalg.norm(body-local_body,axis=1)
        yaw_error=np.array([wrap(x) for x in np.diff(states[ci,:,2])-np.diff(local[:,2])])
        odom_tail_displacement=float(np.max(np.linalg.norm(local[-5:,:2]-local[-5,:2],axis=1)))
        odom_tail_yaw=float(np.degrees(np.max(np.abs(local[-5:,2]-local[-5,2]))))
        r=objective.parts[ci].fun(states[ci].ravel());n=len(inputs['times'])
        ledger[car]=dict(prior=.5*float(r[:3]@r[:3]),odom=.5*float(r[3:3*n]@r[3:3*n]),
                         wall=.5*float(r[3*n:]@r[3*n:]))
        out['cars'][car]=dict(
            estimated_base_path_m=float(np.sum(np.linalg.norm(d,axis=1))),
            estimated_antenna_path_m=float(np.sum(np.linalg.norm(np.diff(ant[ci],axis=0),axis=1))),
            estimated_antenna_net_displacement_m=float(np.linalg.norm(ant[ci,-1]-ant[ci,0])),
            aligned_odom_path_m=float(np.sum(np.linalg.norm(dl,axis=1))),
            start_antenna_prior_displacement_m=float(np.linalg.norm(ant[ci,0]-model['start_antenna_xyz_m'][:2])),
            odom_between_translation_errors=stats(errors),
            odom_between_yaw_rms_deg=float(np.degrees(np.sqrt(np.mean(yaw_error*yaw_error)))),
            last_five_odom_max_translation_from_window_start_m=odom_tail_displacement,
            last_five_odom_max_yaw_from_window_start_deg=odom_tail_yaw,
            last_five_odom_stationary=odom_tail_displacement<1e-6 and odom_tail_yaw<1e-4)
        links={key:[] for key in model['anchors_xyz_m']}
        for i,row in enumerate(data['observations']):
            point=np.r_[ant[ci,i],model['antenna_height_m']]
            for key,raw in row.items():
                predicted=np.linalg.norm(point-model['anchors_xyz_m'][key])
                links[key].append(float(predicted-(raw-model['range_bias_m'][key])))
        out['wall_residual_by_link'][car]={key:stats(values) for key,values in links.items()}
    peer=[]
    for i,row in enumerate(inputs['peers']):
        if row['range_m'] is not None:
            dz=inputs['cars']['car1']['model']['antenna_height_m']-inputs['cars']['car2']['model']['antenna_height_m']
            peer.append(float(np.linalg.norm(np.r_[ant[0,i]-ant[1,i],dz])-row['range_m']))
    out['peer_residual_m']=stats(peer)
    dz=evaluation['end_antenna_xyz_m']['car1'][2]-evaluation['end_antenna_xyz_m']['car2'][2]
    end_distance=float(np.linalg.norm(np.r_[endpoint[0]-endpoint[1],dz]))
    reference_distance=float(np.linalg.norm(np.asarray(evaluation['end_antenna_xyz_m']['car1'])-
                                            evaluation['end_antenna_xyz_m']['car2']))
    tape=evaluation['direct_tape_endpoint_distance_m']
    out['endpoint_distance']=dict(estimated_3d_m=end_distance,coordinate_reference_3d_m=reference_distance,
        estimated_minus_coordinate_reference_m=end_distance-reference_distance,
        direct_tape_reference_m=tape,estimated_minus_tape_m=end_distance-tape if tape is not None else None,
        coordinate_reference_minus_tape_m=reference_distance-tape if tape is not None else None)
    r=objective.fun(states.ravel())
    count=fit['peer_factor_count']
    ledger['peer']=.5*float(r[-count:]@r[-count:]) if count else 0.
    cost=sum(sum(v.values()) if isinstance(v,dict) else v for v in ledger.values())
    if abs(cost-fit['optimizer']['cost'])>1e-9*(1+abs(cost)):
        raise AssertionError('Factor cost ledger differs from optimizer')
    out['factor_cost_ledger']=ledger
    return out


def effect(independent,joint):
    return dict(endpoint_difference_joint_minus_independent_m={c:
        joint['endpoint_difference_m'][c]-independent['endpoint_difference_m'][c] for c in CARS},
        antenna_path_joint_minus_independent_m={c:joint['cars'][c]['estimated_antenna_path_m']-
                                              independent['cars'][c]['estimated_antenna_path_m'] for c in CARS})


def reproduce_legacy(protocol,archive,out):
    import two_car_offline_graph as old
    archived=json.loads((ROOT/'docs/field_tests/20261018/results/two_car_graph_summary.json').read_text())
    config=json.loads(old.ANCHORS.read_text())
    report={}
    for case in protocol['cases']:
        name=case['legacy_name']
        if name is None:continue
        print('Reproducing archived legacy '+name,flush=True)
        run=old.read_run(archive,name)
        report[name]={}
        for label in ['primary','car2_P1_wall_bias_only']:
            inputs=old.build_inputs(run,config['anchors_xyz_m'],old.scenarios(name,config['calibration']['frozen_bias_m'])[label])
            record={}
            for method,joint in [('independent',False),('joint',True)]:
                fit=old.graph(inputs,joint)
                actual=old.metrics(run,inputs,fit)
                before=archived['runs'][name]['scenarios'][label][method]
                delta=max(abs(actual['manual_end_xy_error_m'][c]-before['manual_end_xy_error_m'][c]) for c in CARS)
                if delta>protocol['evaluation_only']['tolerance_archived_endpoint_m']:
                    raise AssertionError('Archived two-car results not reproduced')
                record[method]=dict(metrics=actual,archived_endpoint_reproduction_max_delta_m=delta)
            report[name][label]=record
    write_json(out/'legacy_reproduction.json',report)


def run_case(case,protocol,biases,out,trajectories,table):
    run=read_bag(ROOT/case['path'],case['sha256'])
    write_json(out/'input_diagnostics.json',run['diagnostics'])
    model_case={key:copy.deepcopy(case[key]) for key in ['start_antenna_xyz_m','initial_heading_deg']}
    results,cache={},{}
    for configuration in protocol['configurations']:
        name=configuration['id']
        print(f"Starting {case['id']} / {name}",flush=True)
        inputs=build_inputs(run,model_case,protocol,configuration,biases)
        before=fingerprint(inputs)
        write_json(out/(name+'_inputs.json'),inputs)
        pair={}
        for method,joint in [('independent',False),('joint',True)]:
            independent_key=fingerprint(dict(times=inputs['times'],cars=inputs['cars']))
            reused=None
            if not joint and independent_key in cache:
                fit,reused=cache[independent_key]
            else:
                fit=solve(inputs,joint,protocol['optimizer'])
                if not joint:cache[independent_key]=(fit,name)
            if fingerprint(inputs)!=before:raise AssertionError('Solver mutated matched inputs')
            metrics=evaluate(inputs,fit,case['evaluation_only'],case['stationary_car'])
            metrics['independent_solve_reused_from_configuration']=reused
            pair[method]=metrics
            for ci,car in enumerate(CARS):
                for i,stamp in enumerate(inputs['times']):
                    pose,xy=fit['states'][ci,i],fit['antenna_xy'][ci,i]
                    trajectories.append(dict(case=case['id'],configuration=name,method=method,car=car,
                        elapsed_s=float(stamp),base_x_m=float(pose[0]),base_y_m=float(pose[1]),
                        yaw_rad=float(pose[2]),antenna_x_m=float(xy[0]),antenna_y_m=float(xy[1])))
            table.append(dict(case=case['id'],role=case['role'],configuration=name,method=method,
                car1_endpoint_difference_m=metrics['endpoint_difference_m']['car1'],
                car2_endpoint_difference_m=metrics['endpoint_difference_m']['car2'],
                car1_path_m=metrics['cars']['car1']['estimated_antenna_path_m'],
                car2_path_m=metrics['cars']['car2']['estimated_antenna_path_m'],
                car1_start_prior_displacement_m=metrics['cars']['car1']['start_antenna_prior_displacement_m'],
                car2_start_prior_displacement_m=metrics['cars']['car2']['start_antenna_prior_displacement_m'],
                peer_median_abs_residual_m=metrics['peer_residual_m']['median_abs_m'],
                wall_factors=metrics['wall_factor_count'],peer_factors=metrics['peer_factor_count'],
                endpoint_distance_m=metrics['endpoint_distance']['estimated_3d_m'],
                solve_wall_s=metrics['optimizer']['solve_wall_s'],solve_reused_from=reused))
        if pair['independent']['wall_factor_count']!=pair['joint']['wall_factor_count']:
            raise AssertionError('Independent/joint wall factor counts differ')
        if pair['independent']['peer_factor_count']!=0:
            raise AssertionError('Independent method used peer observations')
        pair.update(effect=effect(pair['independent'],pair['joint']),matched_input_sha256=before)
        results[name]=pair
        write_json(out/(name+'_comparison.json'),pair)
        print(json.dumps(dict(case=case['id'],configuration=name,
            independent_m=pair['independent']['endpoint_difference_m'],joint_m=pair['joint']['endpoint_difference_m'],
            effect_m=pair['effect']['endpoint_difference_joint_minus_independent_m'])),flush=True)
    # Historical input association is checked independently from the new optimizer.
    if case['legacy_name'] is not None:
        import two_car_offline_graph as old
        config=json.loads(old.ANCHORS.read_text())
        old_input=old.build_inputs(dict(run,name=case['legacy_name']),config['anchors_xyz_m'],
                                  old.scenarios(case['legacy_name'])['primary'])
        raw_cfg=next(x for x in protocol['configurations'] if x['id']=='raw_walls')
        new_input=build_inputs(run,model_case,protocol,raw_cfg,biases)
        assert np.array_equal(old_input['times'],new_input['times'])
        delta=max(float(np.max(np.abs(old_input['cars'][c]['local']-new_input['cars'][c]['local']))) for c in CARS)
        if delta>1e-10 or any(old_input['cars'][c]['walls']!=new_input['cars'][c]['observations'] for c in CARS):
            raise AssertionError('Archived/new input bins differ')
        if old_input['peers']!=new_input['peers']:raise AssertionError('Archived/new peer bins differ')
        frontend=dict(passed=True,max_local_component_delta=delta)
    else:frontend=dict(passed=None,note='No archived optimizer case; expanded historical development recording')
    result=dict(case=case['id'],role=case['role'],path=case['path'],sha256=case['sha256'],
                stationary_car=case['stationary_car'],configurations=results,frontend_verification=frontend)
    write_json(out/'comparison.json',result)
    return result


def report(results):
    lines=['# 新版双车离线对照：各自融合与加入车间测距','','终点仅用于评价；两方法共享输入与模型，联合方法增加每时刻一个车间测距因子。',
        'Car1 独立静态包校正＋Car2 既有 P1 校正为主对照，权重冻结；无独立 IMU 因子。','',
        '| 包 | 修正 | Car1 各自→联合/cm | Car2 各自→联合/cm | 静止车轨迹 各自→联合/cm |',
        '|---|---|---:|---:|---:|']
    labels={'raw_walls':'均不修正','car2_p1_only':'只修正 Car2','per_car_walls':'分别修正（主对照）'}
    for case in results:
        for name,label in labels.items():
            pair=case['configurations'][name];a,b=pair['independent'],pair['joint']
            static=case['stationary_car']
            text=(f"{100*a['cars'][static]['estimated_antenna_path_m']:.2f}→{100*b['cars'][static]['estimated_antenna_path_m']:.2f}" if static else '无静止车')
            lines.append(f"| {case['case']} | {label} | {100*a['endpoint_difference_m']['car1']:.2f}→{100*b['endpoint_difference_m']['car1']:.2f} | "
                         f"{100*a['endpoint_difference_m']['car2']:.2f}→{100*b['endpoint_difference_m']['car2']:.2f} | {text} |")
    lines += ['', '单位为与人工终点的差，非全程轨迹精度；静止车轨迹用于暴露模型不一致，未把静止位置固定进优化。',
        '原版复现、静态迁移、加弱车间权重、人工移除墙测距及 ±0.1 s 车间统计窗关联敏感性均完整保留。',
        '原双车模型的 XY 起点先验定义在天线位置；新版复用单车模型，定义在外部起点/朝向换算得到的车体位置。',
        '新旧模型对照同时涉及该先验定义及数值求解器；每个新版配置内部的各自/联合对照只有车间因子这一项差别。',
        '人工移除观测是合成缺测条件，不是实录 NLOS；同包重复配置不是独立统计样本。',
        '车间拟合残差减小仅表示更符合已加入的观测，不构成独立精度证据。',
        '完整批量求解读取整包，不能作为在线回放或固定窗口结果。', '']
    return '\n'.join(lines)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol',type=Path,default=DEFAULT_PROTOCOL)
    parser.add_argument('--archive',type=Path,required=True,help='Unmodified October 18 archive, used only to reproduce the archived baseline')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--dependency-path',type=Path)
    args=parser.parse_args()
    if args.dependency_path:sys.path.append(str(args.dependency_path.resolve()))
    for key in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS']:
        if os.environ.get(key)!='1':raise ValueError(key+' must equal 1')
    protocol=json.loads(args.protocol.read_text())
    archived=json.loads((ROOT/'docs/field_tests/20261018/results/two_car_graph_summary.json').read_text())
    if sha256(args.archive)!=archived['archive_sha256']:raise ValueError('Original archive hash mismatch')
    paths=[ROOT/'tools'/name for name in ['two_car_updated_comparison.py','run_two_car_updated_comparison.py',
        'plot_two_car_updated_comparison.py','test_two_car_updated_comparison.py','two_car_offline_graph.py',
        'test_two_car_offline_graph.py','single_car_fixed_lag.py','single_car_sequential_replay.py']]
    sources={str(p.relative_to(ROOT)):sha256(p) for p in paths}
    protocol_hash=sha256(args.protocol)
    args.output.mkdir(parents=True,exist_ok=False)
    write_json(args.output/'protocol.json',protocol)
    reproduce_legacy(protocol,args.archive,args.output)
    biases=static_checks(protocol,args.output)
    trajectories,table,results=[],[],[]
    for case in protocol['cases']:
        target=args.output/case['id'];target.mkdir()
        results.append(run_case(case,protocol,biases,target,trajectories,table))
        write_csv(args.output/'trajectories.csv',trajectories)
        write_csv(args.output/'comparison.csv',table)
        write_json(args.output/'summary.json',dict(cases=results,limitations=protocol['assumptions']))
    if sources!={str(p.relative_to(ROOT)):sha256(p) for p in paths} or protocol_hash!=sha256(args.protocol):
        raise AssertionError('Sources or protocol changed during the experiment')
    write_json(args.output/'input_manifest.json',dict(base_main_sha=protocol['base_main_sha'],
        python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,
        rosbags=importlib.metadata.version('rosbags'),platform=platform.platform(),
        thread_environment={k:os.environ.get(k) for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS']},
        protocol_sha256=protocol_hash,source_files=sources,archive_sha256=sha256(args.archive),
        data_files={x['path']:x['sha256'] for x in protocol['cases']+protocol['static_validation']+[protocol['calibration']['car1']]},
        source_and_protocol_unchanged_during_run=True))
    (args.output/'REPORT.md').write_text(report(results))
    print('Completed all matched comparisons and baseline/static checks',flush=True)


if __name__=='__main__':main()
