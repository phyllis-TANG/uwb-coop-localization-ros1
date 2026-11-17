"""Independent readback of delivered numeric arrays/counts; no objective/optimizer."""
import csv,gzip,hashlib,json
from pathlib import Path
import numpy as np
from scipy.stats import chi2
root=Path(__file__).resolve().parents[2];d=root/'docs/research/midterm_uncertainty_a';p=d/'results'
def read(name):
 with gzip.open(p/name,'rt') as f:return list(csv.DictReader(f))
runs=read('RUNS.csv.gz');z=np.load(p/'MARGINALS.npz');c=z['covariance_components'];e=z['position_error'][:,None,:,:];det=c[...,0]*c[...,2]-c[...,1]**2
qq=(c[...,2]*e[...,0]**2-2*c[...,1]*e[...,0]*e[...,1]+c[...,0]*e[...,1]**2)/det
assert np.allclose(qq,z['position_q'],rtol=1e-10,atol=1e-10)
assert np.allclose(z['bias_error'][:,None]**2/z['bias_variance'],z['bias_q'],equal_nan=True,rtol=1e-10,atol=1e-10)
assert len(runs)==7200 and sum(r['accepted']=='True' for r in runs)==7175
views=['total_curvature','fixed_prior_noise','data_only'];groups={}
for i,r in enumerate(runs):groups.setdefault((r['id'],r['method']),[]).append(i)
assert len(groups)==144 and all(len(x)==50 for x in groups.values())
checked=0
saved_q=z['position_q']
thresholds={level:chi2.ppf(level,2) for level in [.95,.99]}
for r in read('COVERAGE.csv.gz'):
 ids=groups[r['id'],r['method']];sel=[i for i in ids if r['subset']=='all' or (runs[i]['accepted']=='True')==(r['subset']=='accepted')];vi=views.index(r['view']);blocks=list(range(int(r['car'])-1,12,2));agg=r['aggregation']
 if agg.startswith('t'):blocks=[blocks[int(agg[1:])]]
 a=saved_q[sel,vi][:,blocks];v=np.isfinite(a);co=v&(a<=thresholds[float(r['level'])])
 if agg=='all_times':v=v.all(axis=1);co=co.all(axis=1)
 assert int(r['available'])==v.sum() and int(r['covered'])==co.sum()
 assert int(r['unavailable'])==v.size-v.sum() and int(r['selected_planned'])==v.size
 checked+=1
manifest=d/'SHA256SUMS.json';hashes=0
if manifest.exists():
 for name,h in json.loads(manifest.read_text()).items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==h,name;hashes+=1
print(json.dumps(dict(passed=True,independent_position_quadratic_form_max_relative_error=float(np.max(abs(qq-z['position_q'])/np.maximum(1,abs(qq)))),bias_quadratic_forms_checked=True,coverage_rows_recounted=checked,source_methods=7200,accepted=7175,not_stationary=25,manifest_files_checked=hashes),indent=2))
