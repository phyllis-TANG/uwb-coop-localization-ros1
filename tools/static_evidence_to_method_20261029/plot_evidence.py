#!/usr/bin/env python3
"""Plots of measurement differences only, no trajectory/position errors."""
import argparse,csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def run(src,out):
 with src.open() as f:allrows=list(csv.DictReader(f))
 rows=[r for r in allrows if r['origin']=='supplement_this_run']
 def one(b,w,c,l):return next(r for r in rows if (r['bag'],r['window'],r['car'],r['link'])==(b,w,c,l))
 fig,ax=plt.subplots(2,2,figsize=(12,8),constrained_layout=True)
 cases=['clear_A','human_B','human_B_repeat','clear_C']
 for car,link,label in [('car1','node_0','Car1 to Car2'),('car2','node_1','Car2 to Car1')]:
  rr=[one(b,'whole',car,link) for b in cases]
  ax[0,0].plot(range(4),[100*float(r['median_minus_reference_m']) for r in rr],marker='o',label=label)
 ax[0,0].set_xticks(range(4),['clear A','human B','B repeat','clear C']);ax[0,0].set_title('B: median range minus 2.93 m manual tape');ax[0,0].set_ylabel('Measurement minus manual reference (cm)');ax[0,0].legend()
 for car,link,label in [('car1','node_0','Car1 to Car2'),('car2','node_1','Car2 to Car1')]:
  rr=[one(b,'trim5',car,link) for b in ['T01','T03','T04']]
  ax[0,1].plot(range(3),[100*float(r['median_minus_reference_m']) for r in rr],marker='o',label=label)
 ax[0,1].set_xticks(range(3),['T01 +Y','T03 +X','T04 -X']);ax[0,1].set_title('C: own tape reference; heading/return confounded');ax[0,1].set_ylabel('Measurement minus manual reference (cm)');ax[0,1].legend()
 ww=['pre','wall_action','recovery1','peer_action','recovery2']
 for car,link,label in [('car2','node_10','Car2 N10'),('car1','node_2','Car1 N2'),('car1','node_0','Car1 peer'),('car2','node_1','Car2 peer')]:
  rr=[one('T02',w,car,link) for w in ww];base=float(rr[0]['median_m'])
  ax[1,0].plot(range(5),[100*(float(r['median_m'])-base) for r in rr],marker='o',label=label)
 ax[1,0].set_xticks(range(5),['pre','wall action','recover 1','peer action','recover 2'],rotation=15);ax[1,0].set_title('T02: median change from fixed pre window');ax[1,0].set_ylabel('Same nominal setup range change (cm)');ax[1,0].legend()
 mad=[100*float(one('T02',w,'car2','node_10')['MAD_m']) for w in ww]
 std=[100*float(next(r for r in allrows if r['bag']=='T02' and r['window']==w and r['metric_kind']=='population_std_original_report_not_median_uncertainty')['std_m_original_report']) for w in ww]
 ax[1,1].plot(range(5),mad,'o-',label='MAD (supplemented)');ax[1,1].plot(range(5),std,'s-',label='STD (reused original report)')
 ax[1,1].set_xticks(range(5),['pre','wall action','recover 1','peer action','recover 2'],rotation=15);ax[1,1].set_title('T02 Car2 N10: scatter, not confidence bounds');ax[1,1].set_ylabel('Range distribution scale (cm)');ax[1,1].legend()
 for a in ax.flat:a.grid(alpha=.25);a.axhline(0,color='grey',linewidth=.5)
 fig.suptitle('Ten exposed static bags: measurement evidence only (not positioning error)\nData: COMPACT_RESULTS.csv; windows fixed before supplementary decoding',fontsize=12)
 fig.savefig(out,dpi=140);plt.close(fig)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--csv',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists();run(a.csv,a.output)
