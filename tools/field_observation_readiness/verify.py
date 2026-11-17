"""Zero-solver portable checks of exported counts, motion and pairing denominators."""
import csv,gzip,json,sys
from pathlib import Path
import numpy as np
from audit import pair,valid_range,PEER
p=Path(sys.argv[1]);cars=list(csv.DictReader((p/'CARS.csv').open()));pairs=list(csv.DictReader((p/'PAIRING.csv').open()));decoded=0
for case in json.loads((p/'SOURCES.json').read_text()):
 cid=case['case'];streams={}
 with gzip.open(p/cid/'measurements.jsonl.gz','rt') as f:
  for line in f:
   x=json.loads(line);assert not {'truth','reference','fault','injected_bias'}&x.keys();streams.setdefault(x['topic'],[]).append(x);decoded+=1
 for topic,rows in streams.items():assert len(rows)==case['topics'][topic]
 for row in [r for r in cars if r['case']==cid]:
  car=row['car'];od=streams['/'+car+'/odom'];xy=np.array([x['position_m'][:2] for x in od]);assert abs(float(row['odom_path_m'])-np.linalg.norm(np.diff(xy,axis=0),axis=1).sum())<1e-12
  assert int(row['peer_valid'])==sum(valid_range(x,PEER[car]) is not None for x in streams['/'+car+'/uwb/ranges'])
 aa=[x for x in streams['/car1/uwb/ranges'] if valid_range(x,PEER['car1']) is not None];bb=[x for x in streams['/car2/uwb/ranges'] if valid_range(x,PEER['car2']) is not None]
 for row in [r for r in pairs if r['case']==cid]:
  found=pair(aa,bb,int(row['tolerance_ms'])*10**6);assert len(found)==int(row['matched']);assert len(found)+int(row['unmatched_car1'])==len(aa);assert len(found)+int(row['unmatched_car2'])==len(bb)
  assert len({i for i,j,g in found})==len(found) and len({j for i,j,g in found})==len(found)
  if found:assert abs(np.median([(bb[j]['header_ns']-aa[i]['header_ns'])*1e-6 for i,j,g in found])-float(row['header_delta_median']))<1e-9
assert decoded==json.loads((p/'RUN.json').read_text())['decoded_messages']
# Explicit malformed-range and association boundary controls.
assert valid_range({'ranges':[{'anchor_id':'a','range_m':1.},{'anchor_id':'a','range_m':2.}]},'a') is None
assert valid_range({'ranges':[{'anchor_id':'a','range_m':0.}]},'a') is None
assert valid_range({'ranges':[]},'a') is None
assert pair([{'receipt_ns':0},{'receipt_ns':4}],[{'receipt_ns':2}],2)==[(0,0,2)]
assert pair([{'receipt_ns':0}],[{'receipt_ns':3}],2)==[]
print(json.dumps(dict(passed=True,cases=5,decoded_messages=decoded,pairing_rows=len(pairs),optimizer_calls=0,scope='Portable arithmetic and schema checks; shared parser/pair function, not fully independent implementation.')))
