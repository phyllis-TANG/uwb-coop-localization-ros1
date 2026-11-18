"""Inspect weakest local information directions, without running an optimizer."""
from fcommon import *
from objective import Field
from readback import csvsave
rows=[];batch=Path(sys.argv[1]);target=Path(sys.argv[2])
for p in sorted((batch/'estimates').glob('*_P1.json')):
 case,method,_=p.stem.split('_');o=read(batch/'measurements'/f'{case}.json');e=read(p);f=Field(o,method);r,j=f.evaluate(np.array(e['x']));u,s,v=np.linalg.svd(j*f.scales,full_matrices=False);mode=v[-1];qpart=mode[:f.posdim].reshape(2,f.n,3)
 row={'case':case,'method':method,'scaled_smallest_singular_value':s[-1]}
 for ci,c in enumerate(CARS):
  row[c+'_weak_mode_xy_energy']=float(np.sum(qpart[ci,:,:2]**2));row[c+'_weak_mode_yaw_energy']=float(np.sum(qpart[ci,:,2]**2))
 row['bias_mode_energy']=float(np.sum(mode[f.posdim:]**2));rows.append(row)
csvsave(target,rows)
