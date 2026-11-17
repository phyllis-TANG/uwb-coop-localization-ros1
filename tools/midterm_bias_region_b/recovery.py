"""Conservative per-stage execution ledger for cooperative local POSIX filesystems.
No optimizer dependency. An attempt without a valid result is NEVER retried.
"""
import fcntl,hashlib,json,os,tempfile,time,uuid
from pathlib import Path

class UncertainExecution(RuntimeError):pass
class IdentityMismatch(RuntimeError):pass
class ConcurrentExecution(RuntimeError):pass

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(x):return hashlib.sha256(canonical(x)).hexdigest()
def fsync_dir(p):
 fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
def publish(p,value):
 """Atomic exclusive publication plus file and directory durability; never replace."""
 p=Path(p);fd,tmp=tempfile.mkstemp(prefix='.pending-',dir=p.parent)
 try:
  with os.fdopen(fd,'wb') as f:f.write(canonical(value)+b'\n');f.flush();os.fsync(f.fileno())
  os.link(tmp,p);fsync_dir(p.parent)
 finally:
  os.unlink(tmp);fsync_dir(p.parent)
def read(p):
 try:return json.loads(Path(p).read_text())
 except (ValueError,OSError) as e:raise IdentityMismatch(f'Unreadable ledger: {p}') from e

def identity(unit,method,stage,input_value,config,source_files):
 sources={str(p):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in sorted(map(str,source_files))}
 if not sources:raise ValueError('Explicit code sources required')
 return dict(unit=unit,method=method,stage=stage,input_sha256=digest(input_value),config_sha256=digest(config),code_sha256=digest(sources))
def validate(i):
 if set(i)!={'unit','method','stage','input_sha256','config_sha256','code_sha256'}:raise IdentityMismatch('Missing or unexpected identity fields')
 if any(not isinstance(i[k],str) or not i[k] for k in i):raise IdentityMismatch('Empty identity')
 for k in ['input_sha256','config_sha256','code_sha256']:
  if len(i[k])!=64 or any(c not in '0123456789abcdef' for c in i[k]):raise IdentityMismatch('Invalid SHA256')
def stage_path(root,i):return Path(root)/digest({k:i[k] for k in ['unit','method','stage']})
def execute(root,i,solver,hook=lambda phase:None):
 """Caller computes identity from actual inputs/config/code. solver is zero-argument.
 Hook is only for interruption fixtures. Ordinary exceptions are durable failures;
 BaseException (e.g. process interrupt) leaves uncertainty instead of retry permission.
 """
 validate(i);root=Path(root);root.mkdir(parents=True,exist_ok=True);fsync_dir(root.parent)
 p=stage_path(root,i);p.mkdir(exist_ok=True);fsync_dir(root)
 with (p/'LOCK').open('a') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError as e:raise ConcurrentExecution(str(p)) from e
  ap=p/'ATTEMPT.json';rp=p/'RESULT.json';dp=p/'DONE.json';up=p/'UNCERTAIN.json'
  if ap.exists():
   a=read(ap)
   if a.get('identity')!=i or not isinstance(a.get('attempt_id'),str):raise IdentityMismatch('Attempt identity mismatch')
   if rp.exists():
    r=read(rp)
    if r.get('identity')!=i or r.get('attempt_id')!=a['attempt_id'] or r.get('payload_sha256')!=digest(r.get('payload')):raise IdentityMismatch('Result identity/hash mismatch')
    expected=dict(identity=i,attempt_id=a['attempt_id'],result_sha256=digest(r))
    if dp.exists():
     if read(dp)!=expected:raise IdentityMismatch('Completion identity/hash mismatch')
    else:publish(dp,expected)
    return dict(mode='RESTORED',attempt_id=a['attempt_id'],payload=r['payload'])
   if dp.exists():raise IdentityMismatch('Completion without result')
   u=dict(identity=i,attempt_id=a['attempt_id'],state='EXECUTION_UNCERTAIN',reason='attempt exists without durable result; automatic invocation forbidden')
   if up.exists():
    if read(up)!=u:raise IdentityMismatch('Uncertainty identity mismatch')
   else:publish(up,u)
   raise UncertainExecution(str(p))
  if rp.exists() or dp.exists() or up.exists():raise IdentityMismatch('Orphan ledger records')
  hook('before_attempt')
  a=dict(identity=i,attempt_id=str(uuid.uuid4()),created_ns=time.time_ns());publish(ap,a)
  hook('after_attempt')
  try:payload=dict(execution='RETURNED',value=solver())
  except Exception as e:payload=dict(execution='EXCEPTION',exception_type=type(e).__name__,message=str(e))
  hook('after_call')
  r=dict(identity=i,attempt_id=a['attempt_id'],payload=payload,payload_sha256=digest(payload));publish(rp,r)
  hook('after_result')
  publish(dp,dict(identity=i,attempt_id=a['attempt_id'],result_sha256=digest(r)))
  hook('after_done')
  return dict(mode='EXECUTED',attempt_id=a['attempt_id'],payload=payload)
