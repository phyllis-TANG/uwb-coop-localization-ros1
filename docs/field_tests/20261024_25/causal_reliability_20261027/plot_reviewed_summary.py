#!/usr/bin/env python3
"""Report-only addition after matrix freeze; never imports an estimator.

Keeps the original automatic figures intact and gives the heatmap a dedicated
colorbar column. Also exports cost and publication-axis gate/availability tables.
"""
import argparse,csv,gzip,json,statistics
from collections import Counter,defaultdict
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def write_csv(path,rows,fields=None):
    with path.open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields or list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--bundle',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists():raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    p=json.loads((args.bundle/'matrix/frozen_protocol.json').read_text());methods=p['methods']
    with (args.bundle/'report/paired_seed_summary.csv').open() as stream:rows=list(csv.DictReader(stream))
    index={(r['scenario'],r['role'],r['method'],r['vehicle_id'],r['phase']):r for r in rows};roles=sorted({(r['scenario'],r['role']) for r in rows})
    bound=max(abs(float(r['paired_mean_delta_rmse_m'])) for r in rows if r['phase']=='fault')
    fig=plt.figure(figsize=(17,10));grid=fig.add_gridspec(1,3,width_ratios=[1,1,.045],wspace=.15);axes=[fig.add_subplot(grid[0,i]) for i in range(2)]
    for ax,car in zip(axes,('car1','car2')):
        values=np.array([[float(index[scene,role,m,car,'fault']['paired_mean_delta_rmse_m']) for m in methods] for scene,role in roles])
        image=ax.imshow(values,cmap='coolwarm',vmin=-bound,vmax=bound,aspect='auto')
        ax.set_xticks(range(len(methods)),methods,rotation=65,ha='right',fontsize=9);ax.set_title(car+': paired fault RMSE delta vs independent (m)')
        ax.set_yticks(range(len(roles)),[s+' / '+r for s,r in roles] if car=='car1' else [])
    color=fig.add_subplot(grid[0,2]);fig.colorbar(image,cax=color,label='negative = lower synthetic error')
    fig.subplots_adjust(left=.24,right=.93,bottom=.27,top=.94);fig.savefig(args.output/'paired_fault_delta_reviewed.png',dpi=160);fig.savefig(args.output/'paired_fault_delta_reviewed.svg');plt.close(fig)
    with (args.bundle/'report/compute_cost.csv').open() as stream:costs=list(csv.DictReader(stream))
    core=[statistics.mean(float(r['core_s'])*1000 for r in costs if r['method']==m) for m in methods]
    shadow=[statistics.mean(float(r['shadow_s'])*1000 for r in costs if r['method']==m) for m in methods]
    fig,ax=plt.subplots(figsize=(12,5));positions=np.arange(len(methods));ax.bar(positions,core,label='core / policy');ax.bar(positions,shadow,bottom=core,label='private shadow')
    ax.set_xticks(positions,methods,rotation=40,ha='right');ax.set_ylabel('mean process milliseconds per 48-second input');ax.set_title('Diagnostic Python harness; serialization excluded; not onboard latency');ax.legend();fig.tight_layout();fig.savefig(args.output/'compute_cost.png',dpi=160);plt.close(fig)
    inventory=json.loads((args.bundle/'matrix/inventory.json').read_text());transitions=[];availability=[]
    for row in inventory:
        if row['status']!='DONE':continue
        path=args.bundle/'matrix/runs'/row['id'];origin=json.loads((path/'run.json').read_text())['origin_epoch_ns'];previous={};counts=Counter()
        with gzip.open(path/'states.jsonl.gz','rt') as stream:
            for line in stream:
                tick=json.loads(line)
                for method,item in tick['methods'].items():
                    for car,state in item['vehicles'].items():counts[method,car,bool(state['valid']),state['fallback_status']]+=1
                    if item['gate'] is None:continue
                    for car,value in item['gate'].items():
                        key=method,car;before=previous.get(key,False);after=value['closed']
                        if before!=after:transitions.append(dict(run_id=row['id'],scenario=row['scenario'],role=row['role'],seed=row['seed'],method=method,vehicle_id=car,
                            publish_receive_epoch_ns=tick['publish_receive_epoch_ns'],publication_elapsed_s=(tick['publish_receive_epoch_ns']-origin)/1e9,
                            state_epoch_ns=item['vehicles'][car].get('state_epoch_ns'),transition='quarantined' if after else 'reopened',bad=value['bad'],good=value['good']))
                        previous[key]=after
        for (method,car,valid,status),count in sorted(counts.items()):availability.append(dict(run_id=row['id'],scenario=row['scenario'],role=row['role'],seed=row['seed'],method=method,vehicle_id=car,valid=int(valid),status=status,rows=count))
    write_csv(args.output/'gate_publication_transitions.csv',transitions,['run_id','scenario','role','seed','method','vehicle_id','publish_receive_epoch_ns','publication_elapsed_s','state_epoch_ns','transition','bad','good'])
    write_csv(args.output/'availability_rows.csv',availability)
    (args.output/'NOTES.md').write_text('''# 报告补充与图表审阅\n\n本目录只读取冻结结果，不运行估计器、不改变配置或阈值。自动报告及旧图保留于report/。新热图使用独立色条轴，避免色条压住Car2末列；新增计算时间、发布轴gate转换和全部可用性/回退行数。\n\nnormal、peer_bias、pulse、ramp中的role=car1仅是角色不改变输入后的规范索引，不表示发生了Car1墙故障。其他场景role表示墙支持/故障或Odom缺失车辆；所有场景仍只有Car1→Car2 peer更新。\n\ngate转换表是首次在发布轴观察到闭合/重开的时刻；精确逐peer事件转换仍在events.jsonl.gz。状态时刻与发布可获得时刻分列，不把延迟/保持状态解释为当前车辆保护。availability行数含窗口外EOF陈旧保持，不把这些行数当独立试验或风险概率。\n''')
    print(json.dumps(dict(gate_transitions=len(transitions),availability_status_rows=len(availability),actual_runs=sum(r['status']=='DONE' for r in inventory))))


if __name__=='__main__':main()
