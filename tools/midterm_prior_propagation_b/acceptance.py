"""Portable delivery audit and isolated missing-endpoint fixture; never calls an optimizer."""
import argparse
from model import *
from analyze import streams,analyze

def main(out):
 out.mkdir(parents=True,exist_ok=False)
 for path,h in read(DOC/'FREEZE_MANIFEST.json')['files'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==h,path
 mf=DOC/'SHA256SUMS.json'
 if mf.exists():
  for path,h in read(mf).items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==h,path
 def fixture():
  altered=False
  for z in streams(DOC/'results/EVIDENCE.jsonl.gz'):
   if not altered and z['type']=='PAIR' and z['value']['study']=='new' and z['value']['method']=='B0':
    r=z['value']['target'];r.update(usable_estimate=False,endpoint_valid=False,accepted=False,estimate=None,residual=None,jacobian=None,cost=None,gradient_inf=None,position_mse=[None,None],category='ARTIFICIAL_MISSING_ENDPOINT',execution='EXCEPTION');altered=True
   yield z
 counts=analyze(fixture(),out/'isolated_failure_fixture',archive=False)
 assert counts['new_method_pairs']==960 and counts['new_target_unavailable']==1
 result=dict(status='PASS',freeze_manifest_verified=True,delivery_hashes_verified=mf.exists(),fixture_only=True,main_performance_statistics_unchanged=True,fixture_B0_unavailable=1,full_new_denominator=960,optimizer_calls=0)
 save(out/'ACCEPTANCE.json',result);print(json.dumps(result))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();main(a.out)
