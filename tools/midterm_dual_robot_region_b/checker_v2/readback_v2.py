"""Zero-search verification of persisted v2 outputs, exact gate and denominators."""
import argparse,statistics,sys,time,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import read,write,sha,digest,DOC
from runtime import plans,identity,inspect_unit
from a_bridge import make_certificate as reference_conversion
from certificate import audit
from geometry import projections,evaluate
from checker_v2.a_loader import load_a

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--stage',choices=['deterministic','random'],required=True);ap.add_argument('--limit',type=int,default=44);args=ap.parse_args();out=args.root/args.stage;checks=args.root/(args.stage+'_readback');checks.mkdir(exist_ok=True);lock=read(DOC/'checker_v2/A_SOURCE_LOCK.json');_,a=load_a(lock);inputs=read(DOC/'INPUTS.json.gz');plan=plans(inputs,args.stage);freeze=read(DOC/'checker_v2/FREEZE.json')['freeze_sha'];count=0
 for item in plan:
  unit=item['id'];dest=checks/(unit+'.json');rp=out/(unit+'.receipt.json')
  if dest.exists():
   cached=read(dest);assert cached['freeze_sha']==freeze and cached['a_sha']==lock['a_sha'];assert sha(out/(unit+'.result.json.gz'))==cached['record_sha256'] and sha(out/(unit+'.certificate.json.gz'))==cached['certificate_sha256'];continue
  if count>=args.limit:break
  if not rp.exists():continue
  try:
   expected=identity(item,freeze,lock);row=inspect_unit(out,item,expected)
   if row['status']!='COMPLETED':continue
   rpath=out/(unit+'.result.json.gz');cpath=out/(unit+'.certificate.json.gz');assert sha(rpath)==row['record_sha256'] and sha(cpath)==row['certificate_sha256'];r=read(rpath);c=read(cpath);assert r['case']==item['case'] and r['settings']==item['settings'] and r['method']==item['method'] and r['identity']==expected
   # Reference B checker remains frozen PR133; no locator imports.
   b=audit(item['case']['model'],item['method'],item['settings'],r['result']);assert b==r['certificate_b'];p=projections(item['case']['model'],r['result']);assert p==r['projections'];assert reference_conversion(item['case'],item['method'],item['settings'],r['result'],r['projections'])==c;av=a.check(item['case']['a_input'],c);assert av==r['certificate_a']['validation'] and av['certificate_valid'];assert c['queue']==r['result']['queue'];ev=evaluate(item['case']['model'],item['method'],item['settings'],r['result'],item['case']['evaluation']);assert ev==r['evaluation']
   old_same=None
   if args.stage=='deterministic':
    old=read(args.root/'old_delivery/certificates'/(unit+'.json'));old_same={k:v for k,v in old.items() if k!='cost'}=={k:v for k,v in c.items() if k!='cost'}
   write(dest,dict(id=unit,status='PASS',a_sha=lock['a_sha'],freeze_sha=freeze,record_sha256=sha(rpath),certificate_sha256=sha(cpath),nodes=len(r['result']['nodes']),old_scientific_certificate_equal=old_same,search_calls=0));count+=1;print(unit,'READBACK_PASS',flush=True)
  except Exception as error:
   write(dest,dict(id=unit,status='FAIL',error=repr(error),freeze_sha=freeze,a_sha=lock['a_sha'],nodes=0,record_sha256=sha(out/(unit+'.result.json.gz')) if (out/(unit+'.result.json.gz')).exists() else None,certificate_sha256=sha(out/(unit+'.certificate.json.gz')) if (out/(unit+'.certificate.json.gz')).exists() else None));count+=1;print(unit,'READBACK_FAIL',repr(error),flush=True)
 rows=[read(checks/(x['id']+'.json')) for x in plan if (checks/(x['id']+'.json')).exists()];status=dict(status='PASS' if len(rows)==len(plan) and all(r['status']=='PASS' for r in rows) else 'FAIL' if any(r['status']=='FAIL' for r in rows) else 'INCOMPLETE',planned=len(plan),completed=sum(r['status']=='PASS' for r in rows),failed=sum(r['status']=='FAIL' for r in rows),unexecuted=[j['id'] for j in plan if not (checks/(j['id']+'.json')).exists()],nodes=sum(r['nodes'] for r in rows),rows=rows,search_calls=0,freeze_sha=freeze,a_sha=lock['a_sha']);write(checks/'PROGRESS.json',status)
 if args.stage=='deterministic' and len(rows)==44:
  wallrows=list(map(json.loads,(out/'WALL_COSTS.jsonl').read_text().splitlines()));assert len(wallrows)==44 and len({x['id'] for x in wallrows})==44;wall={x['id']:x['wall_seconds'] for x in wallrows};main={m:[] for m in ['P4','N4']};terms={m:[] for m in main};reasons=[] if status['status']=='PASS' else ['INDEPENDENT_READBACK_NOT_COMPLETE_PASS']
  for item in plan:
   unit=item['id'];receipt=read(out/(unit+'.receipt.json'));r=read(out/(unit+'.result.json.gz'))
   if receipt['status']!='COMPLETED' or r['certificate_b']['status']!='PASS' or r['certificate_a']['status']!='PASS':reasons.append('RUN_NOT_PASS:'+unit)
   ev=r.get('evaluation',{})
   if ev.get('truth_in_declared_domain') and ev.get('noise_event') and ev['noise_event']['holds'] and not ev.get('finite_joint_outer_contains'):reasons.append('NOISE_EVENT_CONTAINMENT_FAILED:'+unit)
   if item['case']['group']=='main' and item['method'] in main:main[item['method']].append(wall[unit]);terms[item['method']].append(r['result']['termination'])
  med={m:statistics.median(v) if v else None for m,v in main.items()}
  for m in main:
   if len(main[m])!=12:reasons.append(m+'_MAIN_DENOMINATOR_NOT_12')
   if any(t!='RESOLUTION_COMPLETE' for t in terms[m]):reasons.append(m+'_MAIN_SEARCH_NOT_COMPLETE')
   if med[m] is None or med[m]>2:reasons.append(m+'_MEDIAN_FULL_COST_EXCEEDS_2_SECONDS')
  gate=dict(status='PASS' if not reasons else 'FAIL',freeze_sha=freeze,a_sha=lock['a_sha'],formal_records=44,main_cost_median_seconds=med,main_terminations=terms,random_planned=240,random_authorized_to_execute=not reasons,reasons=reasons);write(DOC/'checker_v2/GATE.json',gate);print(json.dumps(gate))
 print('Readback',len(rows),'/',len(plan))
if __name__=='__main__':main()
