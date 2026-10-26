"""Read frozen pilot outputs; draw scientific diagnostics, never score accuracy."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from pilot import ROOT, antenna_xy, digest, save


def read_states(directory):
    config=json.loads((directory/'config.json').read_text())
    result={}
    with (directory/'estimate.csv').open() as f:
        for r in csv.DictReader(f):
            if r['valid']!='1':continue
            key=r['method_id'],r['vehicle_id']
            p=antenna_xy([float(r[k]) for k in ('x_m','y_m','yaw_rad')],config['vehicles'][r['vehicle_id']]['antenna_body_xy_m']['value'])
            result.setdefault(key,{})[int(r['publish_receive_epoch_ns'])]=(float(r['canonical_time_s']),p,int(r['state_epoch_ns']))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    run=json.loads((a.results/'run.json').read_text())
    assert run['status']=='DONE_EXPLORATORY_ONLY' and not run['worktree_dirty']
    for relative,sha in run['outputs'].items():assert digest(a.results/relative)==sha
    nominal=read_states(a.results/'nominal');sensitivity={}
    for name in run['profiles']:
        current=read_states(a.results/name);sensitivity[name]={}
        for method,car in nominal:
            old,new=nominal[method,car],current[method,car]
            keys=sorted(set(old)&set(new));d=[float(np.linalg.norm(new[k][1]-old[k][1])) for k in keys]
            sensitivity[name][method+':'+car]=dict(paired_publications=len(d),maximum_output_shift_m=max(d),p95_output_shift_m=float(np.percentile(d,95)),
                compared_at_same_publication_not_necessarily_same_hypothesized_measurement_epoch=True)
    kernel={}
    for relative in ['tools/field_20261024_25/causal_baselines/model.py','tools/field_20261024_25/causal_baselines/replay.py']:
        original=subprocess.check_output(['git','show','8dd0bbcc495996a0ffff0bd900fc70409e907814:'+relative],cwd=ROOT)
        assert hashlib.sha256(original).hexdigest()==digest(ROOT/relative)
        kernel[relative]=digest(ROOT/relative)
    summary=dict(scope='T10 hypothesis-only output diagnostics, not real accuracy or robust-candidate validation',
        source_commit=run['code_commit'],source_dirty=run['worktree_dirty'],algorithm_base_commit='8dd0bbcc495996a0ffff0bd900fc70409e907814',
        protocol_sha256=run['protocol_sha256'],source_sha256=run['sources'],kernel_unchanged_sha256=kernel,
        input_packet=run['packet'],profiles=len(run['profiles']),method_configurations=3*len(run['profiles']),independent_field_trials=1,
        verified_estimate_rows=sum(x['verification']['rows'] for x in run['profiles'].values()),
        numerical_failure_events=sum(x['verification']['numerical_failure_events'] for x in run['profiles'].values()),
        elapsed_seconds=run['elapsed_seconds'],uwb_only=run['uwb_only'],
        profiles_summary=run['profiles'],sensitivity_vs_nominal=sensitivity,
        reference_approved=False,holdout_localization_used=False,RMSE_m=None,ATE_m=None,accuracy_improvement_percent=None,
        postprocess_source_sha256=digest(Path(__file__)),postprocess_worktree_dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()))
    save(a.output/'summary.json',summary)
    colors={'odom_only':'#777777','independent':'#0072B2','joint':'#D55E00'}
    fig,axes=plt.subplots(2,2,figsize=(12,9),constrained_layout=True)
    for ax,car in zip(axes[0],['car1','car2']):
        for method in colors:
            points=np.array([v[1] for _,v in sorted(nominal[method,car].items())])
            ax.plot(points[:,0],points[:,1],color=colors[method],label=method,lw=1.6)
            if np.ptp(points,axis=0).max()<1e-10:
                ax.scatter(points[0,0],points[0,1],s=30,marker='s',color=colors[method])
        with (a.results/'uwb_only.csv').open() as f:
            points=np.array([[float(r['x_antenna_m']),float(r['y_antenna_m'])] for r in csv.DictReader(f) if r['vehicle_id']==car])
        ax.scatter(points[:,0],points[:,1],s=5,alpha=.25,c='#009E73',label='UWB-only diagnostic')
        ax.set_title(car+' antenna trajectories under nominal hypotheses')
        ax.set_xlabel('Room X (m), geometry/placement assumed');ax.set_ylabel('Room Y (m)')
        ax.set_aspect('equal',adjustable='datalim');ax.grid(alpha=.2);ax.legend(fontsize=8)
    ax=axes[1,0]
    for car,color in [('car1','#0072B2'),('car2','#D55E00')]:
        left,right=nominal['independent',car],nominal['joint',car]
        keys=sorted(set(left)&set(right))
        ax.plot([left[k][0] for k in keys],[100*np.linalg.norm(right[k][1]-left[k][1]) for k in keys],label=car,color=color)
    ax.set_title('Effect of peer on output (not accuracy gain/harm)');ax.set_xlabel('Bag recorder relative time (s)');ax.set_ylabel('Joint - independent position magnitude (cm)');ax.legend();ax.grid(alpha=.2)
    ax=axes[1,1];names=[n for n in sensitivity if n!='nominal'];x=np.arange(len(names))
    for car,dx,color in [('car1',-.18,'#0072B2'),('car2',.18,'#D55E00')]:
        ax.bar(x+dx,[100*sensitivity[n]['joint:'+car]['maximum_output_shift_m'] for n in names],width=.34,label=car,color=color)
    ax.set_xticks(x,['C1 Lx -5cm','C1 Lx +5cm','C2 Lx -5cm','C2 Lx +5cm','C2 time -20ms','C2 time +20ms'],rotation=35,ha='right',fontsize=8)
    ax.set_title('Joint-output sensitivity (not uncertainty bounds)');ax.set_ylabel('Maximum shift vs nominal at matched publication (cm)');ax.legend();ax.grid(axis='y',alpha=.2)
    fig.suptitle('T10 exploratory pilot: actual observations, unverified engineering hypotheses\nNo independent localization-accuracy evaluation',fontsize=13)
    fig.savefig(a.output/'T10_exploratory.png',dpi=160);fig.savefig(a.output/'T10_exploratory.svg');plt.close(fig)
    nominal_metrics=run['profiles']['nominal']['metrics']
    lines=['# T10有限试跑结果：可以解算，尚不是精度验证','',
        '实际执行版本：`'+run['code_commit']+'`，工作树干净。PR51严格配置与参考裁决未改；本轮不运行A端候选，也不打开整包留出。','',
        '## 执行与核验','',
        f'- 7个假设配置×3种原有方法，属于1个开发实包，不是21次独立实车实验。实际运行约{run["elapsed_seconds"]:.1f}秒。',
        f'- {summary["verified_estimate_rows"]:,}行状态逐行核验；数值失败事件{summary["numerical_failure_events"]}。准入/拒绝、原始记录、整数时间、as-of支持和每车协方差PSD均有回读记录。',
        '- UWB-only额外诊断：Car1 267帧、Car2 270帧收敛，原始测距未校正；距离拟合残差中位数约0.262/0.374m，不能称为位置误差。','',
        '## 当前可说的结果','',
        '| 假设名义组 | Car1 | Car2 |','|---|---:|---:|',
        '| 加入peer相对独立解的输出变化中位数 | %.2fcm | %.2fcm |' % tuple(100*nominal_metrics['peer_vs_independent_output_shift_m'][c]['median'] for c in ['car1','car2']),
        '| 同上最大值 | %.2fcm | %.2fcm |' % tuple(100*nominal_metrics['peer_vs_independent_output_shift_m'][c]['maximum'] for c in ['car1','car2']),
        '| 末10秒独立解输出变化 | %.2fcm | %.2fcm |' % tuple(100*nominal_metrics['methods']['independent'][c]['terminal_10s_output_excursion_m'] for c in ['car1','car2']),
        '| 末10秒联合解输出变化 | %.2fcm | %.2fcm |' % tuple(100*nominal_metrics['methods']['joint'][c]['terminal_10s_output_excursion_m'] for c in ['car1','car2']),
        '',
        '这些是估计输出的差异/变化，不是已验证的真实位置误差或协同收益。末10秒没有被升级为独立验真的连续静止区间。',
        '',
        '安装杆臂X方向分别改变±5cm、同时保持初始天线位置时，这段近直线场景的联合输出相对名义组最大变化不到0.8mm；这只针对已测试因素，不能推广到转弯、其他杆臂方向或真实误差范围。Car2总时间调整±20ms时，联合输出最大变化约1.40cm，peer准入数为228/242/247；它们是数值敏感性，不是测得的时钟误差或定位上界。',
        '','## 原始输入还可以如何使用','',
        '1. 原始墙距可以直接解天线位置，base原点与跨机/视频时钟缺项不阻止这条单车诊断路径。',
        '2. 原有三基线能在显式工程假设下执行；真正的source-backed入口继续BLOCKED，两个层次不能混用。',
        '3. 当前应继续核查测距/几何一致性；不要仅因轨迹可解就宣布误差小，也不按人工终点反调偏置。',
        '4. A端可复用本轮输入和假设配置，在自己的统一机制框架中重新冻结/执行；不能直接把不同估计器或版本的数值拼成方法对照。',
        '',
        '## 限制与复现','',
        '几何中心作为base、名义起点/朝向、时间调整均为假设；测试步长不是实际误差范围。固定R/Q未标定。`uncertainty_ns`只是显式未验证的接口工程参数，本轮没有时钟误差界、协方差覆盖率、概率完好性或实包RMSE。',
        '',
        '源工具：[README](../../../../tools/field_20261024_25/t10_exploratory/README.md)。紧凑数值见[summary.json](summary.json)，完整逐事件记录在Git外归档；源输入使用PR51可迁移T10包。',
        '',
        '![T10探索性轨迹与输出响应](T10_exploratory.svg)','']
    (a.output/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({'profiles':summary['profiles'],'rows':summary['verified_estimate_rows'],'numerical_failures':summary['numerical_failure_events'],'sensitivity':sensitivity},ensure_ascii=False))


if __name__=='__main__':main()
