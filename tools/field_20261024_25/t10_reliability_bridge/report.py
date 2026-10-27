"""Descriptive output response only. No field position-error computation."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import sys

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'causal_reliability'))
from io_utils import gzread,sha


def antenna(state,lever):
    x,y,yaw=state
    return np.array([x+math.cos(yaw)*lever[0]-math.sin(yaw)*lever[1],
                     y+math.sin(yaw)*lever[0]+math.cos(yaw)*lever[1]])


def metrics(root,name,origin):
    path=root/name;config=json.loads((path/'config.json').read_text())
    ticks=list(gzread(path/'states.jsonl.gz'));shift={};valid=Counter();covariance_null=Counter();final={};series={}
    for car in ('car1','car2'):
        lever=config['vehicles'][car]['antenna_body_xy_m']['value']
        for method in ticks[0]['methods']:
            values=[];times=[];points=[];epochs=[]
            for tick in ticks:
                item=tick['methods'][method]['vehicles'][car];base=tick['methods']['independent']['vehicles'][car]
                if item['pose'] is not None:
                    point=antenna(item['pose'],lever);final.setdefault(method,{})[car]=point.tolist()
                if item['valid']:
                    valid[method+':'+car]+=1;covariance_null[method+':'+car]+=int(item['covariance'] is None)
                    times.append((tick['publish_receive_epoch_ns']-origin)/1e9);points.append(point);epochs.append(item['state_epoch_ns'])
                if item['valid'] and base['valid'] and item['state_epoch_ns']==base['state_epoch_ns']:
                    values.append(float(np.linalg.norm(antenna(item['pose'],lever)-antenna(base['pose'],lever))))
            shift.setdefault(method,{})[car]=dict(samples=len(values),median_m=float(np.median(values)),p95_m=float(np.percentile(values,95)),maximum_m=max(values),is_accuracy_gain=False)
            series[method,car]=dict(time=times,xy=np.array(points),epoch=epochs)
    counts=Counter();max_z=Counter()
    for event in gzread(path/'events.jsonl.gz'):
        for method,item in event['methods'].items():
            d=item['decision'];counts[method+':'+d['status']]+=1
            if d.get('reliability'):
                r=d['reliability'];max_z[method]=max(max_z[method],abs(r['z']))
                for i,flag in enumerate(r.get('clipped',[])):counts[method+':clipped_car'+str(i+1)]+=int(flag)
    return dict(shift_to_independent=shift,valid_rows=dict(valid),null_covariance_valid_rows=dict(covariance_null),
        final_antenna_xy_under_hypotheses=final,event_status_counts=dict(counts),maximum_abs_policy_z=dict(max_z)),series


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--results',required=True,type=Path)
    p.add_argument('--audit',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    args=p.parse_args(argv);run=json.loads((args.results/'run.json').read_text());audit=json.loads(args.audit.read_text())
    if run['status']!='DONE_EXPLORATORY_ONLY' or audit['status']!='DONE':raise ValueError('complete verified results required')
    args.output.mkdir(parents=True,exist_ok=False)
    summary=dict(scope='T10 conditional output response; no accuracy evaluation',code_commit=run['code_commit'],run_sha256=sha(args.results/'run.json'),audit_sha256=sha(args.audit),
        actual_elapsed_s=run['elapsed_s'],field_accuracy_evaluated=False,profiles={})
    for name in run['profiles']:
        stats,series=metrics(args.results,name,run['origin_epoch_ns']);summary['profiles'][name]=stats
        if name=='nominal':nominal_series=series
    (args.output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    display=['independent','joint','huber','shadow_only','gate_cap_shadow']
    fig,axes=plt.subplots(2,2,figsize=(12,9),layout='constrained')
    colors=dict(zip(display,['#333333','#d55e00','#0072b2','#009e73','#cc79a7']))
    styles={'shadow_only':'--','gate_cap_shadow':':'}
    for col,car in enumerate(('car1','car2')):
        for m in display:
            s=nominal_series[m,car];xy=s['xy'];base=nominal_series['independent',car]['xy']
            reference=nominal_series['independent',car]
            if s['time']!=reference['time'] or s['epoch']!=reference['epoch']:raise ValueError('unmatched plot time/epoch')
            axes[0,col].plot(xy[:,0],xy[:,1],label=m,color=colors[m],linestyle=styles.get(m,'-'))
            axes[1,col].plot(s['time'],np.linalg.norm(xy-base,axis=1)*100,label=m,color=colors[m],linestyle=styles.get(m,'-'))
        axes[0,col].set(title=car+' antenna output under PR53 hypotheses',xlabel='Room X (m)',ylabel='Room Y (m)')
        axes[0,col].set_aspect('equal',adjustable='datalim')
        axes[1,col].set(xlabel='Recorder-relative publication time (s)',ylabel='Output difference to independent (cm)')
        for row in range(2):axes[row,col].grid(alpha=.25)
    axes[0,0].legend(fontsize=8);axes[1,1].legend(fontsize=8)
    fig.suptitle('T10 real-input policy response | no accepted position reference | not accuracy gain',fontsize=12)
    fig.savefig(args.output/'T10_policy_response.svg');fig.savefig(args.output/'T10_policy_response.png',dpi=150)
    print(json.dumps({'profiles':len(summary['profiles']),'summary':str(args.output/'summary.json')}))


if __name__=='__main__':main()
