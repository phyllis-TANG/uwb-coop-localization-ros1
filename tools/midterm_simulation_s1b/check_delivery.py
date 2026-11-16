"""Check committed evidence identity, dimensions, frozen protocol and addition-only scope."""
import csv,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
P=ROOT/'docs/research/midterm_simulation_s1b'
freeze='005c78f3c466f6892b53ae7c34410ef177cee377'
for name in ['CONFIG.json','PROTOCOL.md','SEED_AUDIT.json','SOURCES.json']:
    assert (P/name).read_bytes()==subprocess.check_output(['git','show',freeze+':docs/research/midterm_simulation_s1b/'+name],cwd=ROOT)
for name,sha in json.loads((P/'SOURCES.json').read_text()).items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha,name
r=json.loads((P/'results/RUN.json').read_text())
for name,sha in r['sources'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha,name
infos=json.loads((P/'results/INFORMATION.json').read_text())
assert len(infos)==76
for a in infos:
    assert len(a['singular_values'])==25
    assert len(a['nullspace_scaled'])==25 and all(len(row)==25-a['rank'] for row in a['nullspace_scaled'])
    if a['scene'].startswith(('weak/static','weak/straight')) and a['information']=='data_motion':
        assert a['rank']==23 and a['bias_null_norm_scaled']<1e-12 and a['bias_information_m_minus2']>2000
rows=list(csv.DictReader((P/'results/PER_RUN.csv').open()))
assert len(rows)==2717
assert sum(r['solver_failed']=='True' for r in rows if r['peer_only']=='False')==0
assert sum(r['solver_failed']=='True' for r in rows if r['peer_only']=='True')==7
assert json.loads((P/'SEED_BASELINE_AUDIT.json').read_text())['status']=='NO_CONFLICT'
assert json.loads((P/'results/READBACK.json').read_text())['status']=='PASS'
assert json.loads((P/'checks/ISOLATION_REPLAY.json').read_text())['status']=='PASS'
allowed=('docs/research/midterm_simulation_s1b/','tools/midterm_simulation_s1b/')
changed=subprocess.check_output(['git','diff','--name-status','df323eccdffd375a2fb255ebbfd734b6c2be4aac'],cwd=ROOT,text=True).splitlines()
for line in changed:
    status,path=line.split('\t');assert status=='A' and path.startswith(allowed),line
for path in subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines():assert path.startswith(allowed),path
for path,sha in json.loads((P/'SHA256SUMS.json').read_text()).items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha,path
print('PASS: frozen protocol unchanged; baseline source/script SHA; 76 full spectra/nullspaces; 2717 fits; failure counts; seed audit; independent readback; isolation replay; addition-only scope; delivery SHA index')
