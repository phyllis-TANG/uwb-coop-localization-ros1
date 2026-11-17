"""Frozen eight-case execution, exclusive attempts and stage-1 acceptance gate."""
import argparse,json,gzip,os,fcntl,hashlib,subprocess,sys,platform,decimal,shutil
from pathlib import Path
from interval import threshold_certificate
from invert import solve
from check import audit,metrics,contains,rational_bound,unpack
ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'docs/research/midterm_nonlinear_region_b'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,z):
 with p.open('x') as f:json.dump(z,f,indent=2);f.flush();os.fsync(f.fileno())
def acceptance(case,r):
 e=case['evaluation'];truth=e['truth'];z=dict(truth_retained=contains(r,truth),truth_in_domain=all(a<=x<=b for (a,b),x in zip(unpack(case['model']['domain']),map(__import__('fractions').Fraction,truth))))
 if case['kind']=='empty':assert r['empty_proved']
 else:
  q=__import__('fractions').Fraction(case['settings']['q']);lo,hi=rational_bound(tuple((__import__('fractions').Fraction(x),)*2 for x in truth),case['model']);assert hi<=q
  assert z['truth_retained'];z['noise_event_upper']=str(hi)
 if e['mirror_truth'] is not None:
  z['mirror_retained']=contains(r,e['mirror_truth']);assert z['mirror_retained']
 if case['kind']=='boundary':assert r['boundary_contact']
 if case['kind']=='budget':assert r['termination']=='BOX_BUDGET' and r['counts'].get('PENDING',0)>0
 assert r['failure'] is None
 assert r['processed']<=case['settings']['max_boxes']
 return z

def run(out,freeze,reuse_from=None):
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();assert head==freeze
 manifest=json.loads((DOC/'FREEZE_MANIFEST.json').read_text())
 for p,h in manifest['files'].items():assert sha(ROOT/p)==h,p
 cfg=json.loads((DOC/'CONFIG.json').read_text());cases=json.loads((DOC/'INPUTS.json').read_text());assert len(cases)==8
 reuse={}
 if reuse_from is not None:
  reuse=json.loads((DOC/'RESUME_PLAN.json').read_text());assert sha(reuse_from/'RUN.json')==reuse['source_run_sha256']
  original=json.loads((reuse_from/'RUN.json').read_text());assert original['freeze']==reuse['source_freeze']
  for p in reuse['unchanged_files']:assert sha(ROOT/p)==original['manifest']['files'][p],p
  for file,h in reuse['result_hashes'].items():assert sha(reuse_from/file)==h,file
 out.mkdir(parents=True,exist_ok=True)
 with (out/'LOCK').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  if any(out.glob('*.attempt.json')):raise RuntimeError('Existing attempts: read back only; no automatic rerun')
  save(out/'RUN.json',dict(freeze=freeze,versions=dict(python=platform.python_version(),libmpdec=decimal.__libmpdec_version__),manifest=manifest,reuse=reuse,threshold=threshold_certificate(cfg['settings']['q']),planned_cases=8))
  if reuse:shutil.copyfile(reuse_from/'RUN.json',out/'ORIGINAL_RUN.json')
  reports=[]
  for c in cases:
   identity=dict(id=c['id'],input_sha=hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest(),freeze=freeze)
   searched=c['id'] not in reuse.get('cases',[])
   if searched:
    save(out/(c['id']+'.attempt.json'),identity)
    r=solve(c['model'],c['settings'])
    # Persist outcome before any acceptance assertion, including real failure.
    record=dict(**c,result=r,metrics=metrics(c['model'],r),identity=identity)
    with gzip.open(out/(c['id']+'.json.gz'),'xt') as f:json.dump(record,f)
   else:
    source=reuse_from/(c['id']+'.json.gz')
    with gzip.open(source,'rt') as f:record=json.load(f)
    assert all(record[k]==v for k,v in c.items());r=record['result']
    shutil.copyfile(source,out/source.name)
    save(out/(c['id']+'.reuse.json'),dict(source_freeze=reuse['source_freeze'],sha256=sha(source),search_calls=0))
   check=audit(c['model'],c['settings'],r);check.update(acceptance(c,r));save(out/(c['id']+'.check.json'),check)
   reports.append(dict(case=c['id'],searched_this_revision=searched,stage=c['stage'],processed=r['processed'],termination=r['termination'],seconds=r['elapsed_seconds'],counts=r['counts'],area_upper_m2=record['metrics']['area_upper_m2'],boundary_contact=r['boundary_contact'],empty_proved=r['empty_proved']))
   print(json.dumps(reports[-1]),flush=True)
   if c['id']=='s1_empty':save(out/'STAGE1_GATE.json',dict(status='PASS',cases=4,stage2_authorized=True))
  save(out/'SUMMARY.json',reports)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--freeze',required=True);p.add_argument('--reuse-from',type=Path);a=p.parse_args();run(a.out,a.freeze,a.reuse_from)
