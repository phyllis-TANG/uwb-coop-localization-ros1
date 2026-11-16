"""Audit baseline configuration/registration text; run from repository root."""
import subprocess,json,hashlib,re,pathlib
base='df323eccdffd375a2fb255ebbfd734b6c2be4aac'
out=pathlib.Path('docs/research/midterm_simulation_s1b')
items=subprocess.check_output(['git','ls-tree','-r',base],text=True).splitlines()
checked=[];skipped=[];selected=[]
seeds=json.loads((out/'CONFIG.json').read_text())['seeds']
for line in items:
    meta,path=line.split('\t',1);parts=meta.split()
    if not re.search(r'seed|protocol|config|freeze|register',path,re.I):continue
    if pathlib.Path(path).suffix.lower() not in ['.json','.csv','.md','.txt','.py','.yaml','.yml']:
        skipped.append(path);continue
    selected.append((path,parts[2]))
# Explicit selected blobs in one fetch avoids ls-tree -l materializing every historical artifact.
subprocess.run(['git','-c','gc.auto=0','fetch','--no-tags','--no-write-fetch-head','origin','--stdin'],input='\n'.join(sorted(set(oid for _,oid in selected)))+'\n',text=True,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
for path,oid in selected:
    b=subprocess.check_output(['git','show',base+':'+path],timeout=60)
    if len(b)>2000000:
        skipped.append(path);continue
    assert not any(re.search(rb'(?<!\d)'+str(s).encode()+rb'(?!\d)',b) for s in seeds),path
    checked.append(dict(path=path,git_blob=oid,bytes=len(b),sha256=hashlib.sha256(b).hexdigest()))
with (out/'SEED_BASELINE_AUDIT.json').open('x') as f:
    json.dump(dict(base=base,seeds=seeds,status='NO_CONFLICT',selection='All baseline tracked seed/protocol/config/freeze/register text paths <=2MB; plus pre-registration readable docs/tools scan in SEED_AUDIT. Not an audit of inaccessible unregistered records.',checked=checked,excluded_nontext_or_large=skipped),f,indent=2)
print('checked',len(checked),'excluded',len(skipped))
