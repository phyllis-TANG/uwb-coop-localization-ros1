"""Stage-durable two-worker runner, no selection and no old experiment replay."""
import argparse,collections,fcntl,hashlib,importlib,multiprocessing as mp,os,platform,shutil,subprocess,time
from pathlib import Path
import numpy as np
import scipy
from io_utils import ROOT,DOC,read,save,digest,canonical
from adapter import config,conditions,generate,solve,V
G={}
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def hashes():
    paths=list((ROOT/'tools/midterm_prior_mechanism_b').glob('*.py'))+[ROOT/'tools/midterm_simulation_validation/core.py',ROOT/'tools/midterm_simulation_s2/prototype.py',ROOT/'tools/midterm_simulation_phase1/identifiability.py']
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
def versions():return dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__)
def event(path,name,**kw):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('ab') as f:f.write(canonical(dict(event=name,utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**kw))+b'\n');f.flush();os.fsync(f.fileno())
def init(out,c,meta):G.update(out=Path(out),c=c,meta=meta)
def process(item,override=None,stop_after=None):
    out=G['out'];c=G['c'];meta=G['meta'];uid=item['id'];log=out/'events'/f'{uid}.jsonl';ip=out/'inputs'/f'{uid}.json.gz';made=0
    oldevents=[] if not log.exists() else [__import__('json').loads(x) for x in log.read_text().splitlines()]
    attempts=collections.Counter((x['method'],x['stage']) for x in oldevents if x['event']=='STAGE_STARTED')
    event(log,'UNIT_STARTED')
    if ip.exists():u=read(ip)
    else:
        if (out/'stages'/uid).exists():raise ValueError('Missing input with existing stages')
        try:u=importlib.import_module(c.get('adapter_module','adapter')).generate(c,item['condition'],item['seed'])
        except Exception as e:u=dict(condition=item['condition'],seed=item['seed'],generation_exception=repr(e))
        save(ip,u)
    for method in c['methods']:
        prev=None
        if (out/'stages'/uid/f'{method}-P1.json.gz').exists() and not (out/'stages'/uid/f'{method}-P0.json.gz').exists():raise ValueError('P1 without P0')
        for stage in ['P0','P1','LINEAR']:
            path=out/'stages'/uid/f'{method}-{stage}.json.gz'
            if path.exists():
                old=read(path)
                assert (old['input_sha256'],old['config_sha256'],old['method'],old['stage'])==(digest(u),meta['config_sha256'],method,stage)
                prev=old['result'];continue
            attempt=attempts[method,stage]+1;event(log,'STAGE_STARTED',method=method,stage=stage,attempt=attempt,retry_reason='unfinished_before_durable_record' if attempt>1 else None)
            if 'generation_exception' in u:
                r=V.blank(stage);r.update(category='INPUT_EXCEPTION',execution='EXCEPTION',exception=u['generation_exception'])
            else:r=solve(c,u,method,stage,prev,solver=override(method,stage) if override else None)
            save(path,dict(unit=uid,method=method,stage=stage,attempt=attempt,input_sha256=digest(u),config_sha256=meta['config_sha256'],result=r));prev=r;made+=1
            event(log,'STAGE_DONE',method=method,stage=stage,category=r['category'])
            if stop_after is not None and made>=stop_after:raise KeyboardInterrupt('development interruption fixture')
    event(log,'UNIT_DONE',new_stages=made);return uid,made

def plan(c,mode,ids=None):
    qs=importlib.import_module(c.get('adapter_module','adapter')).conditions(c)
    if ids is not None:
        if mode=='formal':raise ValueError('No formal filtering')
        qs=[q for q in qs if q['id'] in ids]
    return [dict(id=f"{q['id']}-s{s}",condition=q,seed=s) for q in qs for s in c['seeds'][mode]]
def run(out,c,mode,freeze=None,resume=False,ids=None,workers=None,override=None,stop_after=None):
    out=Path(out);head=git('rev-parse','HEAD')
    if mode=='formal':
        if head!=freeze or git('status','--porcelain','--untracked-files=no'):raise ValueError('Formal requires exact clean frozen HEAD')
        mf=read(DOC/'FREEZE_MANIFEST.json')
        for p,h in mf['files'].items():
            if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h:raise ValueError('Freeze content changed: '+p)
        if digest(c)!=mf['config_sha256']:raise ValueError('Config changed')
        dep=c['required_dependencies'];v=versions()
        assert v['python'].startswith(dep['python_major_minor']+'.') and v['numpy']==dep['numpy'] and v['scipy']==dep['scipy']
        assert all(os.environ.get(k)=='1' for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'])
        assert shutil.disk_usage(out.parent).free>c['execution']['minimum_free_disk_GB']*10**9
    if not resume:out.mkdir(parents=True,exist_ok=False)
    with (out/'run.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if resume:
            meta=read(out/'RUN.json');assert meta['config_sha256']==digest(c) and meta['frozen_commit']==head and meta['sources']==hashes() and meta['versions']==versions() and meta['mode']==mode
        else:
            tasks=plan(c,mode,ids)
            if mode=='formal':assert len(tasks)==c['expected']['formal_paired_units']
            meta=dict(frozen_commit=head,config=c,config_sha256=digest(c),plan=tasks,plan_sha256=digest(tasks),sources=hashes(),versions=versions(),mode=mode,threads={k:os.environ.get(k) for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']},start_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
            save(out/'RUN.json',meta)
        event(out/'RUN_EVENTS.jsonl','RESUME' if resume else 'RUN_STARTED')
        nw=workers or c['execution']['workers'];init(out,c,meta);done=0;made=0;pool=None
        try:
            if nw==1:
                for task in meta['plan']:
                    _,n=process(task,override,stop_after);done+=1;made+=n
                    if done%100==0:print(f'completed_units={done}/{len(meta["plan"])} new_stages={made}',flush=True)
            else:
                if override or stop_after:raise ValueError('Fault injection fixtures are serial only')
                pool=mp.get_context('spawn').Pool(nw,initializer=init,initargs=(str(out),c,meta))
                for _,n in pool.imap_unordered(process,meta['plan'],chunksize=1):
                    done+=1;made+=n
                    if done%100==0:print(f'completed_units={done}/{len(meta["plan"])} new_stages={made}',flush=True)
                pool.close();pool.join();pool=None
            event(out/'RUN_EVENTS.jsonl','RUN_COMPLETED',units=done,new_stages=made)
        except BaseException as e:
            if pool:pool.terminate();pool.join()
            event(out/'RUN_EVENTS.jsonl','INTERRUPTED',reason=repr(e),returned_units=done,new_stages=made)
            raise
    return dict(units=done,new_stages=made)
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--out',type=Path,required=True);a.add_argument('--mode',choices=['development','formal'],required=True);a.add_argument('--freeze');a.add_argument('--resume',action='store_true');a.add_argument('--ids',nargs='+');z=a.parse_args();print(run(z.out,config(),z.mode,z.freeze,z.resume,z.ids))
