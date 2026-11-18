"""I/O, source identity and strict internal model contract (standard library)."""
import gzip, hashlib, importlib.util, json, os, tempfile
from pathlib import Path
from fractions import Fraction as F
ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'docs/research/midterm_dual_robot_region_b'
TOOL=Path(__file__).resolve().parent
BASE='3ad69c8137183c1986012e354857b73527978c48'
def load_module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
I=load_module('dual_directed_interval',ROOT/'tools/midterm_nonlinear_region_b/interval.py')
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def digest(x):return hashlib.sha256(canonical(x)).hexdigest()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p)
 return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);data=canonical(x)+b'\n'
 if p.suffix=='.gz':data=gzip.compress(data,compresslevel=6,mtime=0)
 fd,tmp=tempfile.mkstemp(dir=p.parent,prefix='.'+p.name+'.')
 try:
  with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
  os.replace(tmp,p)
  fd=os.open(p.parent,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
def validate(m,method,s,thresholds):
 if method not in ('J5','P4','N4'):raise ValueError('method')
 if set(m)!={'schema','state_order','anchors','observations','measurement_ids','R','domain','bias_domain','bias_incidence','units','frame','epoch','representation'}:raise ValueError('unexpected/missing model field; evaluation prohibited')
 if m['schema']!='DUAL-B-INTERNAL-V1' or m['state_order']!=['px','py','sx','sy','b']:raise ValueError('state schema')
 if m['units']!='m' or len(m['anchors'])!=4 or any(len(a)!=2 for a in m['anchors']):raise ValueError('geometry/units')
 if len(m['observations'])!=9 or len(m['measurement_ids'])!=9 or len(set(m['measurement_ids']))!=9:raise ValueError('observations/duplicate identity')
 if m['bias_incidence']!=[0]*8+[1]:raise ValueError('unsupported bias incidence')
 if len(m['domain'])!=4 or len(m['bias_domain'])!=2:raise ValueError('domain')
 I.decode(m['domain']);I.decode([m['bias_domain']]);I.decode(m['observations'])
 for a in m['anchors']:
  for x in a:I.point(x)
 if len(m['R'])!=9 or any(len(r)!=9 for r in m['R']):raise ValueError('R dimensions')
 for i,row in enumerate(m['R']):
  for j,x in enumerate(row):
   I.point(x)
   if (i==j and F(x)<=0) or (i!=j and F(x)!=0):raise ValueError('R must be positive diagonal')
 df=8 if method=='N4' else 9
 if s['df']!=df or F(s['q'])!=F(thresholds[str(df)]):raise ValueError('wrong full-noise threshold')
 if len(s['tolerance'])!=5 or any(F(t)<=0 for t in s['tolerance']):raise ValueError('resolution')
 if s['max_boxes']<0 or s['max_seconds']<0:raise ValueError('budget')
 return True
