"""Two targeted raw scans for footprint coverage gaps; never overwrite old assets."""
import importlib.util,json,hashlib,signal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
DOC=ROOT/'docs/research/lunar_end_to_end/continuous'
ART=Path('/home/ubuntu22/uwb-lunar-continuous-artifacts')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
source=Path('/home/ubuntu22/LuSNAR-reproduction')
spec=importlib.util.spec_from_file_location('historical_range_fetch',source/'fetch_sample.py');f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
entries=f.entries();origin=1693274724086398300
names=[k for k in entries if k.startswith('Moon_1/LiDAR/') and k.endswith('.txt') and Path(k).stem.isdigit()]
selected=[]
for t in [5.22,18.93]:
 name=min(names,key=lambda k:abs(int(Path(k).stem)-origin-t*1e9));selected.append(dict(relative_path=name,requested_time_s=t,**entries[name]))
plan=dict(rule='Only midpoint-nearest scans for blocking footprint coverage gaps near Car2 5.0-5.42s and Car1 18.86-19s. Existing frame disagreement is not resolved by deleting scans.',frames=selected,central_sha256=sha(f.CENTRAL),fetch_code_sha256=sha(source/'fetch_sample.py'),max_files=2,max_wall_seconds=150)
write(DOC/'SUPPLEMENT_PLAN.json',plan)
receipt=dict(status='STARTED',files=[]);out=ART/'supplement';out.mkdir(exist_ok=False);f.OUT=out
signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError()));signal.alarm(150)
try:
 url=f.get_url()
 for item in selected:
  f.fetch_one(url,item['relative_path'],entries[item['relative_path']]);p=out/item['relative_path'];receipt['files'].append(dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size,crc_verified=True));write(DOC/'SUPPLEMENT_RECEIPT.json',receipt)
 receipt['status']='COMPLETE'
except Exception as e:receipt.update(status='BLOCKED',error_type=type(e).__name__,reason='Targeted download failed or fixed 150s budget reached; no unverified bytes accepted.')
finally:signal.alarm(0);write(DOC/'SUPPLEMENT_RECEIPT.json',receipt)
