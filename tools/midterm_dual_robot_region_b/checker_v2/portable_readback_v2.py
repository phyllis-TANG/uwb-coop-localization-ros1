"""Unpack and independently recheck delivered v2 records; no search import/call."""
import argparse,json,statistics,sys,tarfile,tempfile,hashlib,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import read,write,sha,DOC,ROOT
from runtime import plans,identity,inspect_unit
from certificate import audit
from geometry import projections,evaluate
from a_bridge import make_certificate
from checker_v2.a_loader import load_a

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--evidence',type=Path,default=DOC/'checker_v2/evidence');ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();manifest=read(args.evidence/'MANIFEST.json');started=time.monotonic()
 with tempfile.TemporaryDirectory() as td:
  root=Path(td);seen={}
  for name,meta in manifest['archives'].items():
   assert sha(args.evidence/name)==meta['sha256']
   with tarfile.open(args.evidence/name) as tar:
    for member in tar:
     path=Path(member.name);assert member.isfile() and not path.is_absolute() and '..' not in path.parts and member.name not in seen;dest=root/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(tar.extractfile(member).read());seen[member.name]=sha(dest);assert seen[member.name]==meta['files'][member.name]
  assert seen==manifest['files'];freeze=read(root/'metadata/FREEZE.json');assert freeze['freeze_sha']==manifest['freeze_sha'];inputs_path='docs/research/midterm_dual_robot_region_b/INPUTS.json.gz';assert sha(root/'metadata/INPUTS.json.gz')==freeze['files'][inputs_path]

  for path,h in freeze['files'].items():
   if path.startswith('tools/'):
    assert sha(ROOT/path)==h, 'Frozen implementation mismatch: '+path
  lock=read(root/'metadata/A_SOURCE_LOCK.json');lock['source_root']=str(root/'a_source');_,a=load_a(lock);inputs=read(root/'metadata/INPUTS.json.gz');gate=read(root/'metadata/GATE.json');totals={};node_count=0;main_cost={m:[] for m in ['P4','N4']};terms={m:[] for m in main_cost}
  for stage in ['deterministic','random']:
   plan=plans(inputs,stage);complete=failed=interrupted=notrun=0;folder=root/stage;lp=folder/'WALL_COSTS.jsonl';ledger=list(map(json.loads,lp.read_text().splitlines())) if lp.exists() else [];wall={x['id']:x['wall_seconds'] for x in ledger};assert len(wall)==len(ledger)
   for item in plan:
    unit=item['id'];rp=folder/(unit+'.receipt.json')
    expected=identity(item,freeze['freeze_sha'],lock)
    if not rp.exists():
     if (folder/(unit+'.attempt.json')).exists():interrupted+=1
     else:notrun+=1
     continue
    row=inspect_unit(folder,item,expected);assert row['identity']==expected
    if row['status']!='COMPLETED':failed+=1;continue
    rpath=folder/(unit+'.result.json.gz');cpath=folder/(unit+'.certificate.json.gz');assert sha(rpath)==row['record_sha256'] and sha(cpath)==row['certificate_sha256'];r=read(rpath);c=read(cpath);assert r['case']==item['case'] and r['method']==item['method'] and r['settings']==item['settings'] and r['identity']==expected
    assert audit(item['case']['model'],item['method'],item['settings'],r['result'])==r['certificate_b'];assert projections(item['case']['model'],r['result'])==r['projections'];assert make_certificate(item['case'],item['method'],item['settings'],r['result'],r['projections'])==c;av=a.check(item['case']['a_input'],c);assert av==r['certificate_a']['validation'] and av['certificate_valid'];assert r['certificate_b']['status']=='PASS' and r['certificate_a']['status']=='PASS';assert evaluate(item['case']['model'],item['method'],item['settings'],r['result'],item['case']['evaluation'])==r['evaluation'];node_count+=len(r['result']['nodes']);complete+=1
    if stage=='deterministic' and item['case']['group']=='main' and item['method'] in main_cost:main_cost[item['method']].append(wall[unit]);terms[item['method']].append(r['result']['termination'])
   totals[stage]=dict(planned=len(plan),completed=complete,failed=failed,interrupted=interrupted,unexecuted=notrun)
  med={m:statistics.median(v) if v else None for m,v in main_cost.items()};assert med==gate['main_cost_median_seconds'];passed=totals['deterministic']['completed']==44 and all(len(main_cost[m])==12 and all(t=='RESOLUTION_COMPLETE' for t in terms[m]) and med[m]<=2 for m in main_cost);assert passed==(gate['status']=='PASS')
  if not passed:assert totals['random']['unexecuted']==240
  result=dict(status='PASS',actual_unpack=True,verified_files=len(seen),rechecked_nodes=node_count,counts=totals,gate_status=gate['status'],main_cost_median_seconds=med,search_calls=0,seconds=time.monotonic()-started,checker='Frozen PR133 B arithmetic and conversion + published A v2, independent of optimized B implementation')
 write(args.output,result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
