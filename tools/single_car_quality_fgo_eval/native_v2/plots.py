"""Plots of native field actions/bias/host delay, no reference fitting."""
import argparse
import json
from pathlib import Path
import numpy as np
from .common import begin,finish,lines,require,sha


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--performance',type=Path,required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();v=begin(a.output,'B_field_action_bias_actual_delay_figures')
    try:
        require(json.loads((a.report/'summary.json').read_text())['status']=='DONE','report completed');import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
        fig,axes=plt.subplots(2,3,figsize=(14,8),layout='constrained');links=['node_10','node_2','node_3','node_8']
        for i,case in enumerate(('004023','005135')):
            matrix=[];labels=[];times=None
            for group in ('Q2','Q3'):
                ledger=lines(a.performance/(case+'_'+group)/'quality_ledger.jsonl.gz')
                for link in links:
                    rows=[r for r in ledger if r['target']==link];matrix.append([np.nan if r['policy']['state']=='unknown' else r['policy']['information_multiplier'] for r in rows]);labels.append(group+' '+link);times=[(r['state_epoch_ns']-rows[0]['state_epoch_ns'])/1e9 for r in rows]
            cmap=plt.colormaps['viridis'].copy();cmap.set_bad('lightgray');im=axes[i,0].imshow(np.ma.masked_invalid(np.array(matrix)),origin='upper',interpolation='nearest',aspect='auto',vmin=0,vmax=1,extent=[times[0],times[-1],len(labels)-.5,-.5],cmap=cmap);axes[i,0].set_yticks(range(len(labels)),labels,fontsize=8);axes[i,0].set_title(case+' actual information gain (gray=unknown)');axes[i,0].set_xlabel('time from first publication (s)');fig.colorbar(im,ax=axes[i,0],label='g (not probability)',shrink=.7)
            for group in ('Q0','Q1','Q2','Q3'):
                folder=a.performance/(case+'_'+group);pub=lines(folder/'publications.jsonl.gz');avail=lines(folder/'availability.jsonl.gz');t=[r['row']['state_time_s'] for r in pub]
                axes[i,2].plot(t,[r['actual_release_delay_s'] for r in avail],label=group,linewidth=1)
                if group in ('Q1','Q3'):axes[i,1].plot(t,[r['row']['bias_rad_s'] for r in pub],label=group,linewidth=1.2)
            axes[i,1].set_title(case+' model residual bias (no truth)');axes[i,1].set_ylabel('rad/s');axes[i,1].set_xlabel('centered state time (s)');axes[i,2].set_title(case+' actual paced output delay');axes[i,2].set_ylabel('s, including original 1s wait');axes[i,2].set_xlabel('centered state time (s)')
            for ax in axes[i,1:]:ax.grid(alpha=.25);ax.legend(fontsize=8)
        fig.suptitle('Historical development data: actions and output changes do not establish accuracy improvement');fig.savefig(a.output/'actions_bias_delay.png',dpi=130);plt.close(fig);v['inputs']=[dict(path=str(a.report/'summary.json'),sha256=sha(a.report/'summary.json'))];finish(a.output,v);return 0
    except Exception as e:finish(a.output,v,e);raise


if __name__=='__main__':raise SystemExit(main())
