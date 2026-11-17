"""No fitting: source hashes, construction, same starts, persistence failure paths."""
from common import *
from model import CFG,conditions,generate,validate_inputs,reference_geometry
from persistence import exclusive_output,ensure_no_orphans
import argparse,tempfile,subprocess,sys

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    n=0
    for folder in ['midterm_noise_scale_a','midterm_weak_geometry_a']:
        for path,h in read(ROOT/'docs/research'/folder/'SHA256SUMS.json')['files'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==h;n+=1
    rows=[generate(q,CFG['development_seeds'][0]) for q in conditions()];checks=validate_inputs(rows)
    with tempfile.TemporaryDirectory() as temp:
        out=Path(temp)
        with exclusive_output(out):
            code="import fcntl,sys; f=open(sys.argv[1],'a+');\ntry: fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)\nexcept BlockingIOError: sys.exit(23)\nsys.exit(0)"
            z=subprocess.run([sys.executable,'-c',code,str(out/'.run.lock')]);assert z.returncode==23
        (out/'P0.json.gz.attempt').write_text('{}')
        try:
            with exclusive_output(out):raise AssertionError('orphan allowed')
        except RuntimeError as e:assert 'UNRESOLVED_ATTEMPT' in str(e)
        assert (out/'P0.json.gz.attempt').exists()
    original=copy.deepcopy(SOURCE['geometries']['weak']['anchors']);SOURCE['geometries']['weak']['anchors'][0][1]=.1
    try:
        try:reference_geometry();raise RuntimeError('Invalid source accepted')
        except AssertionError:pass
    finally:SOURCE['geometries']['weak']['anchors']=original
    g=np.diag([1.,1.,9.]);e=g+np.diag([.2,-.1,0]);r,w,_,_=project_weak(g,e);assert r['weak_dimension']==2
    for f in (ROOT/'tools/midterm_geometry_perturbation_a').glob('*.py'):compile(f.read_text(),str(f),'exec')
    checks.update(source_hash_checks=n,concurrent_process_lock='REJECTED',orphan_attempt='REJECTED_AND_PRESERVED',bad_geometry='REJECTED',repeated_eigenspace='PASS',optimizer_calls=0);save(a.output,checks);print(checks)
if __name__=='__main__':main()
