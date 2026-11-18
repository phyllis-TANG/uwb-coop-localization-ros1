"""Post-run plots from saved tables, with no search/checker invocation."""
import csv,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
D=Path(__file__).resolve().parents[3]/'docs/research/midterm_dual_robot_region_b/checker_v2';out=D/'figures';out.mkdir(exist_ok=True)
s=json.loads((D/'COST_SUMMARY.json').read_text());rows=list(csv.DictReader((D/'COSTS.csv').open()));methods=['P4','N4'];fig,ax=plt.subplots(1,2,figsize=(11,4),constrained_layout=True);x=np.arange(2)
ax[0].bar(x-.18,[s[m]['old_median_full_wall_seconds'] for m in methods],.36,label='Original PR133');ax[0].bar(x+.18,[s[m]['median_full_wall_seconds'] for m in methods],.36,label='Frozen checker v2 run');ax[0].axhline(2,color='red',ls='--',label='Admission threshold');ax[0].set_xticks(x,methods);ax[0].set(ylabel='Full-pipeline median [s]',title='12 main cases per method');ax[0].legend(fontsize=8)
components=['search','certificate_b','certificate_conversion','projection','certificate_a','compressed_io'];bottom=np.zeros(2)
for key in components+['other']:
 values=[]
 for m in methods:
  sel=[r for r in rows if r['method']==m and r['group']=='main' and r['stage']=='deterministic'];values.append(np.mean([float(r[key]) if key!='other' else float(r['full_wall_seconds'])-sum(float(r[k]) for k in components) for r in sel]))
 ax[1].bar(x,values,bottom=bottom,label=key);bottom+=values
ax[1].set_xticks(x,methods);ax[1].set(ylabel='Mean component time [s]',title='Inclusive cost decomposition (means, not gate)');ax[1].legend(fontsize=7);fig.savefig(out/'costs.png',dpi=170);plt.close(fig)
fig,ax=plt.subplots(figsize=(7,4),constrained_layout=True)
for method in methods:
 sel=[r for r in rows if r['method']==method and r['group']=='main' and r['stage']=='deterministic'];ax.scatter([int(r['nodes']) for r in sel],[float(r['full_wall_seconds']) for r in sel],label=f"{method}: r={s[method]['node_wall_pearson']:.4f}")
ax.set(xlabel='Certificate tree nodes',ylabel='Full-pipeline wall [s]',title='Fixed deterministic cases; descriptive association');ax.axhline(2,color='red',ls='--');ax.legend();fig.savefig(out/'node_cost.png',dpi=170);plt.close(fig)
