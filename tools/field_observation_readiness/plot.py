"""Fixed three-case observation plots, not localization performance."""
import gzip,json,sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from audit import valid_range,PEER
p=Path(sys.argv[1]);out=Path(sys.argv[2]);fig,axes=plt.subplots(3,2,figsize=(12,9),constrained_layout=True)
for i,case in enumerate(['015334','033248','050447']):
 with gzip.open(p/case/'measurements.jsonl.gz','rt') as f:rows=[json.loads(x) for x in f]
 origin=next(x['bag_origin_ns'] for x in json.loads((p/'SOURCES.json').read_text()) if x['case']==case)
 for car in ['car1','car2']:
  od=[x for x in rows if x['topic']=='/'+car+'/odom'];uw=[x for x in rows if x['topic']=='/'+car+'/uwb/ranges'];good=[x for x in uw if valid_range(x,PEER[car]) is not None]
  axes[i,0].plot([(x['receipt_ns']-origin)*1e-9 for x in od],[np.linalg.norm(x['linear_mps'][:2]) for x in od],label=car)
  axes[i,1].plot([(x['receipt_ns']-origin)*1e-9 for x in good],[valid_range(x,PEER[car]) for x in good],label=car+' receiver',lw=.6)
 axes[i,0].set(title=case+' recorded odom speed (not truth)',ylabel='m/s');axes[i,1].set(title=case+' raw directed peer ranges',ylabel='m')
 for ax in axes[i]:ax.set_xlabel('bag receipt elapsed time (s)');ax.legend();ax.grid(alpha=.2)
fig.savefig(out,dpi=150);plt.close(fig)
