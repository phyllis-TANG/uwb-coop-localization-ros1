"""External audit history; no feedback into the bounded estimator graph."""
import copy,csv,gzip,hashlib,json
from pathlib import Path
from probe import digest

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def dump(p,obj):Path(p).write_text(json.dumps(obj,indent=2,sort_keys=True,allow_nan=False)+'\n')
def read(p):
 op=gzip.open if str(p).endswith('.gz') else open
 with op(p,'rt') as f:
  for line in f:
   if line.strip():yield json.loads(line)
def write_gzip(p,rows):
 with Path(p).open('xb') as raw,gzip.GzipFile(fileobj=raw,filename='',mode='wb',mtime=0,compresslevel=2) as z:
  for row in rows:z.write((json.dumps(row,sort_keys=True,allow_nan=False)+'\n').encode())
def csv_write(p,rows):
 with Path(p).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)

class Provenance:
 def __init__(self,origin):self.origin=origin;self.previous={};self.consumed={};self.previous_prior={}
 def add(self,row):
  for role,obj in [('main',row),('auxiliary',row.get('auxiliary'))]:
   if obj is None:continue
   s=obj['snapshot'];seen=self.consumed.setdefault(role,set());changes=[]
   for md in obj['marginalization_details']:
    before=digest(md['before']);after=digest(md['after'])
    assert before==self.previous_prior[role],('prior discontinuity',role)
    self.previous_prior[role]=after;old_ep=self.origin+round(md['times_s'][0]*1e9);fid='peer|'+str(old_ep)
    actual=s['peer_enabled'] and md['old_peer_m'] is not None
    if actual:
     assert fid not in seen;seen.add(fid)
    changes.append(dict(old_state_epoch_ns=old_ep,prior_before_id=before,prior_after_id=after,consumed_peer_factor_id=fid if actual else None,consumed_wall_factor_ids=['wall|'+c+'|'+k+'|'+str(old_ep) for c,obs in md['old_observations'].items() for k in obs],cross_information_norm=md['cross_information_norm'],affine_offset_norm=sum(x*x for x in md['after']['offset'])**.5,eliminated_constant=md['constant']))
   current=digest(s['prior'])
   if role in self.previous_prior:assert self.previous_prior[role]==current
   self.previous_prior[role]=current
   active=['peer|'+str(self.origin+round(t*1e9)) for t,p in zip(s['times_s'],s['peers_m']) if s['peer_enabled'] and p is not None]
   assert not set(active)&seen
   obj['provenance']=dict(previous_record_id=self.previous.get(role),current_prior_id=current,window_peer_factor_ids=active,prior_peer_factor_ids=sorted(seen),marginalizations=changes)
   rid=digest(dict(epoch=row['state_epoch_ns'],role=role,snapshot=s,prior_parent=self.previous.get(role)));obj['audit_record_id']=rid;self.previous[role]=rid
  return row
