"""Exact finite experiment denominator; a successful subset is never full PASS."""
SEEDS=(101,211,307)
SCENARIOS=('nominal','peer_bias','wall_bias','peer_gap','car1_common_wall_bias')
METHODS=('G0','G1','G2')
EXPECTED={(s,k,m) for s in SCENARIOS for k in SEEDS for m in METHODS}
def validate(index,require_done=True):
 cells=index['cells'];keys=[(r['scenario'],r['seed'],r['method']) for r in cells]
 if len(keys)!=45 or len(set(keys))!=45 or set(keys)!=EXPECTED:raise ValueError('Matrix is missing, duplicate, or extra; exactly 45 required')
 for sc,seed in {(s,k) for s,k,m in EXPECTED}:
  rows=[r for r in cells if r['scenario']==sc and r['seed']==seed]
  if len({r['events_sha256'] for r in rows})!=1 or len({r['config_sha256'] for r in rows})!=1:raise ValueError('Unpaired input/config bytes')
 if require_done and (index['status']!='DONE' or any(r['status']!='DONE' for r in cells)):raise ValueError('Not all 45 complete')
 return True
