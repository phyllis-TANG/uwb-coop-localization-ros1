"""Use the locked pilot solver with the one registered model change."""
from concurrent.futures import ProcessPoolExecutor
from fractions import Fraction as F
import json
import sys
import tempfile
from pathlib import Path
from common import CFG,HERE,PILOT,JOBS,check_source,mode,obs,receipt,sha

sys.path.insert(0,str(PILOT))
import run as pilot


def solve(job):
    key,cm=job
    dest=JOBS/f'{key}_{cm}'
    if dest.exists():
        receipt(key,cm)
        return
    with tempfile.TemporaryDirectory(dir=JOBS) as tmp:
        work=Path(tmp)/'output'
        pilot.OUT=work
        pilot.MODES[mode(cm)]=('P4',F(cm,100))
        pilot.run_job((obs(key),mode(cm)))
        hashes={str(p.relative_to(work)):sha(p) for p in work.rglob('*') if p.is_file()}
        assert len(hashes)==3
        (work/'receipt.json').write_text(json.dumps(dict(key=key,cm=cm,config_sha256=sha(HERE/'config.json'),sha256=hashes),indent=2)+'\n')
        work.rename(dest)


if __name__=='__main__':
    check_source()
    JOBS.mkdir(exist_ok=True)
    with ProcessPoolExecutor(CFG['workers']) as pool:
        list(pool.map(solve,[(key,b) for key in CFG['inputs'] for b in CFG['new_cm']]))
