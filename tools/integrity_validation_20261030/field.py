from experiment import OUT,ROOT,sha,write_json,csv_write
from monitors import four_anchor
import json,gzip,math
import numpy as np
from collections import defaultdict
cache=__import__('pathlib').Path('/home/ubuntu22/uwb-static-to-method-02-20261029-artifacts/stats-v1')
manifest=json.loads((cache/'RUN_MANIFEST.json').read_text());entry=next(r for r in manifest['inputs'] if r['id']=='T02')
assert sha(cache/'T02_ranges.jsonl.gz')==entry['decoded_cache_sha256']
g=json.loads((ROOT/'docs/field_tests/20261024_25/geometry.json').read_text());anchors=g['anchors']['xyz_m'];bins=defaultdict(lambda:defaultdict(list))
windows=[('initial',5,35),('wall_operation',45,75),('recovery',85,155),('peer_operation',165,195),('tail',205,238.7543)]
for line in gzip.open(cache/'T02_ranges.jsonl.gz','rt'):
 r=json.loads(line);t=(r['receive_ns']-entry['start_receive_ns'])/1e9
 for name,a,b in windows:
  if a<=t<b:
   for v in r['ranges']:
    if v['anchor'] in anchors and v['range'] is not None and v['range']>0:bins[(name,int(t),r['car'])][v['anchor']].append(v['range'])
rows=[]
for (window,t,car),values in sorted(bins.items()):
 model=dict(anchors_xyz_m=anchors,antenna_height_m=.17 if car=='car1' else .20,range_bias_m={k:0. for k in anchors})
 test=four_anchor({k:float(np.median(v)) for k,v in values.items()},model,{k:len(v) for k,v in values.items()},'engineering_0.2m')
 rows.append(dict(window=window,t_receive_s=t,car=car,computable=test['computable'],statistic=test['statistic'],alarm=test['computable'] and test['statistic']>-2*math.log(.01)))
csv_write(OUT/'T02_B1.csv',rows)
write_json(OUT/'FIELD_INPUT.json',dict(cache_sha256=sha(cache/'T02_ranges.jsonl.gz'),geometry_sha256=sha(ROOT/'docs/field_tests/20261024_25/geometry.json'),input=entry,scope='conditional B1 only; no position HMI/FAR/FNR/accuracy',B2_status='missing bound Odom/initial XY-yaw/extrinsics/clock model'))
