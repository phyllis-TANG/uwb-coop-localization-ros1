"""Materialize and hash frozen observation/reference inputs before optimization."""
import itertools,json,subprocess,hashlib
from inputs import *
def main():
 windows=json.loads((DOC/'WINDOWS.json').read_text());seeds=list(range(2026111701,2026111711));root=ART/'evaluation';plan=[];manifest=[]
 for w,seed,peer,motion in itertools.product(windows,seeds,['normal','constant','step','ramp'],['white','correlated','scale','slip_proxy']):
  o,r=generate(w,seed,peer,motion);atomic(root/'observations'/f"{o['id']}.json",o);atomic(root/'references'/f"{o['id']}.json",r);manifest.append(dict(id=o['id'],observation_digest=digest(o),reference_digest=digest(r),window=w['id'],seed=seed,peer=peer,motion=motion,sensitivity='control'))
  for method in ['M0','M1','M2','M3']:plan.append(dict(key=o['id']+'_'+method,input_id=o['id'],method=method,group='core'))
 for w,seed,sensitivity in itertools.product(windows,seeds[:4],['time_plus','time_minus','height_plus','height_minus','missing']):
  o,r=generate(w,seed,'normal','white',sensitivity);atomic(root/'observations'/f"{o['id']}.json",o);atomic(root/'references'/f"{o['id']}.json",r);manifest.append(dict(id=o['id'],observation_digest=digest(o),reference_digest=digest(r),window=w['id'],seed=seed,peer='normal',motion='white',sensitivity=sensitivity))
  for method in ['M0','M1','M2','M3']:plan.append(dict(key=o['id']+'_'+method,input_id=o['id'],method=method,group='sensitivity'))
 atomic(root/'RUN_PLAN.json',plan);atomic(DOC/'RUN_PLAN.json',plan);atomic(DOC/'INPUT_MANIFEST.json',manifest);atomic(DOC/'SEEDS.json',dict(development=[2026111601,2026111602,2026111603],evaluation=seeds,sensitivity=seeds[:4],pairing='Shared seed/window range innovations, motion innovations and initial-prior noise across all conditions and methods. Statistical unit is seed cluster, not window or method.'))
 receipts=[]
 for tree,sha in [('/home/ubuntu22/uwb-field-moon1-integration','1c7e6d14ce65ff1bb41ff2fa36b920eb18c3e4cb'),('/home/ubuntu22/uwb-moon1-trend-height-sensitivity','2049084cd58588fd33fecccf5c965e9810a2ed26')]:
  cmd=['git','-C',tree,'grep','-n','-E','|'.join(map(str,seeds)),sha,'--','tools','docs'];ans=subprocess.run(cmd,capture_output=True,text=True);assert ans.returncode==1,ans.stdout;receipts.append(dict(commit=sha,scope='tracked tools and docs; compressed external archives not searched',matches=0))
 atomic(DOC/'SEED_AUDIT.json',receipts)
 print(dict(inputs=len(manifest),methods=len(plan),core=1920,sensitivity=240))
if __name__=='__main__':main()
