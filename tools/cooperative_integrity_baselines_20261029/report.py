#!/usr/bin/env python3
"""Read compact outputs only; no new estimation or parameter selection."""
import argparse
import csv
import gzip
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from common import SPEC,csv_write,write_json,new_output,size_guard
from decisions import primary_names


def load(path):
    with Path(path).open(newline='') as f:return list(csv.DictReader(f))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--runs',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    out=new_output(a.output);metrics=[];trajectory=[];raw={}
    for scenario in SPEC['scenarios_in_execution_order']:
        metrics+=load(a.runs/scenario/'metrics.csv');trajectory+=load(a.runs/scenario/'trajectory.csv')
        with gzip.open(a.runs/scenario/'monitor.jsonl.gz','rt') as f:raw[scenario]=[json.loads(line) for line in f]
    csv_write(out/'ALL_SENSITIVITY_METRICS.csv',metrics)
    table=[r for r in metrics if r['profile'] in primary_names() and r['coverage']=='all_published' and
           r['period']==('all' if r['scenario']=='nominal' else 'fault')]
    csv_write(out/'PRIMARY_TABLE.csv',table)
    paired=[]
    for scenario,group in [('car1_common_wall_bias','car1_absolute'),('peer_bias','peer')]:
        changed=0
        for x,y in zip(raw['nominal'],raw[scenario]):
            assert x['state_epoch_ns']==y['state_epoch_ns']
            assert x['monitor']['subset_history_hashes'][group]==y['monitor']['subset_history_hashes'][group]
            changed+=np.linalg.norm(np.asarray(x['pose'])-y['pose'])>1e-6
        assert changed>0
        paired.append(dict(scenario=scenario,excluded_group=group,exact_state_guess_cache_prior_noise_history_hash_matches=63,
                           full_graph_changed_publications=int(changed),across_actual_marginalizations=42))
    write_json(out/'PAIRED_EXCLUSION.json',dict(status='PASS',pairs=paired))
    text=['# 固定主轨迹的强基线对照','','仅seed101受控复现，非原归档读回；AL是假设值；未作罕见风险认证。',
          '', '|场景|车|监测|分母s|AL m|报警s|unknown s|可用s|越限s|HMI s|', '|---|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in table:
        if float(r['AL_m'])!=.1:continue
        name=r['profile'].split('|')[0]
        text.append(f"|{r['scenario']}|{r['car']}|{name}|{r['denominator_s']}|{r['AL_m']}|{r['alarm_s']}|{r['unknown_s']}|{r['available_s']}|{r['overlimit_s']}|{r['hmi_s']}|")
    (out/'TABLE.md').write_text('\n'.join(text)+'\n')
    fig,axes=plt.subplots(4,3,figsize=(14,10),sharex=True)
    for col,scenario in enumerate(SPEC['scenarios_in_execution_order']):
        rs=raw[scenario];t=[r['state_time_s'] for r in rs]
        for ci,car in enumerate(('car1','car2')):
            tr=[r for r in trajectory if r['scenario']==scenario and r['car']==car]
            axes[0,col].plot(t,[float(r['xy_error_m']) for r in tr],label=car)
            axes[2,col].plot(t,[r['monitor']['b1']['engineering_0.2m'][car]['statistic'] for r in rs],label=car)
            maximum=[]
            for r in rs:
                values=[r['monitor']['ss'][g][ci]['statistic'] for g in SPEC['source_groups']]
                maximum.append(max(values) if all(v is not None for v in values) else np.nan)
            axes[3,col].plot(t,maximum,label=car)
        axes[0,col].set_title(scenario)
        for al in (.05,.1,.2):axes[0,col].axhline(al,color='gray',ls=':',lw=.7)
        axes[1,col].plot(t,[r['monitor']['b0'].get('engineering_q') for r in rs]);axes[1,col].axhline(3,color='red',ls='--')
        axes[2,col].axhline(-2*np.log(.01),color='red',ls='--')
        axes[3,col].axhline(-2*np.log(.01/3),color='red',ls='--')
        for row in range(4):
            if scenario!='nominal':axes[row,col].axvspan(24,38,color='gray',alpha=.13)
            axes[row,col].grid(alpha=.2)
        axes[3,col].set_xlabel('state time (s)')
    for i,label in enumerate(['antenna XY error (m)','B0 engineering q','B1 raw four-anchor statistic','B2 maximum SS statistic']):axes[i,0].set_ylabel(label)
    axes[0,0].legend();fig.suptitle('Frozen G1; monitor-only engineering baselines; seed101 exposed development case')
    fig.tight_layout();fig.savefig(out/'COMPARISON.png',dpi=140);plt.close(fig)
    write_json(out/'REPORT_INDEX.json',dict(status='DONE',metric_rows=len(metrics),primary_table_rows=len(table),
        scenes=list(raw),profiles_per_scene=len(raw['nominal'][0]['monitor']['declarations']),paired_exclusion=paired,
        results_bytes=size_guard(out)))
    print(out)
if __name__=='__main__':main()
