"""Compact portable evidence; preserve complete matrix spectra outside Git."""
import argparse,shutil,platform,subprocess
from common import *
import scipy,matplotlib

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--artifacts',type=Path,required=True);ap.add_argument('--destination',type=Path,required=True);a=ap.parse_args();out=a.destination/'results';out.mkdir(parents=True,exist_ok=False)
 shutil.copy2(a.artifacts/'source001/SOURCE_CHECKS.json',out/'SOURCE_CHECKS.json')
 for f in ['FORMULA_CHECKS.json','FAULT_INDEPENDENT_CHECKS.json','NOISE_INDEPENDENT_CHECKS.json']:shutil.copy2(a.artifacts/f,out/f)
 externals={}
 for batch in CFG['batches']:
  dest=out/batch;dest.mkdir();externals[batch]={}
  for src in sorted((a.artifacts/batch).glob('shard-[0-9][0-9][0-9]')):
   target=dest/src.name;target.mkdir();old=json.loads((src/'DONE.json').read_text());keep=['POINTS.npz','RUNS.csv.gz','INFORMATION.csv.gz','CHECKS.json']
   for name in keep:assert sha(src/name)==old['outputs'][name];shutil.copy2(src/name,target/name)
   externals[batch][src.name]={'SPECTRA.npz':old['outputs']['SPECTRA.npz']}
   old['external_outputs']=externals[batch][src.name];old['outputs']={name:old['outputs'][name] for name in keep};old['delivery_note']='Full spectra external; source and code receipts preserved; use fresh external output for full regeneration'
   write_json(target/'DONE.json',old)
  shutil.copytree(a.artifacts/(batch+'-summary-final'),dest/'summary')
  plots=a.artifacts/('fault-figures' if batch=='fault' else 'noise-figures-final');shutil.copytree(plots,a.destination/'figures'/batch)
 write_json(out/'EXTERNAL_SPECTRA.json',externals)
 write_json(out/'ENVIRONMENT.json',dict(actual_cwd=str(ROOT),branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),source_sha=CFG['source_sha'],protocol_commit='9b885e9fea0eb594479ecd48a4d4b7b88e681765',python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,matplotlib=matplotlib.__version__,venv_prefix=sys.prefix,threads={'OPENBLAS_NUM_THREADS':1,'OMP_NUM_THREADS':1},initial_worktree='/home/ubuntu22/uwb-midterm-uncertainty-a',initial_branch='research/midterm-uncertainty-a',initial_head='d39c99589bd15938484d64871981d45a9dd74efe',initial_status='clean',applicable_AGENTS='none found in ancestors or source tree',disk_free_initial_GB=33,process_scope='Only current sandbox namespace visible; no host-wide claim',remote='https://github.com/phyllis-TANG/uwb-coop-localization-ros1.git'))
 logs=out/'execution_logs';logs.mkdir()
 for name in ['fault.log','noise.log','noise-resume.log','source001.log','fault-summary-final.log','noise-summary-final.log','fault-figures.log','fault-figures-final.log','noise-figures-final.log']:
  shutil.copy2(a.artifacts/name,logs/name)
 print('Packaged',out)
if __name__=='__main__':main()
