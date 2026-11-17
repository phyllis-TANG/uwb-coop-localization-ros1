"""Create immutable execution manifest before any formal method invocation."""
from common import *
from runtime import plans
if __name__=='__main__':
 lock=read(DOC/'SOURCE_LOCK.json');assert lock['status']=='LOCKED'
 inp=read(DOC/'INPUTS.json.gz');assert len(plans(inp,'deterministic'))==44 and len(plans(inp,'random'))==240
 if (DOC/'FREEZE_MANIFEST.json').exists():raise RuntimeError('FREEZE_ALREADY_EXISTS')
 names=['MATH.md','PROTOCOL.md','IMPLEMENTATION_CONTRACT.md','USER_PROTOCOL_PRECEDENCE.md','SOURCE_LOCK.json','INPUTS.json.gz']
 files=list(TOOL.glob('*.py'))+[DOC/n for n in names]+[ROOT/'tools/midterm_nonlinear_region_b/interval.py']
 write(DOC/'FREEZE_MANIFEST.json',dict(schema='DUAL-B-FREEZE-V1',base=BASE,a_sha=lock['a_sha'],files={str(p.relative_to(ROOT)):sha(p) for p in sorted(files)},plan_sha256={s:digest(plans(inp,s)) for s in ('deterministic','random')},formal_searches_before_freeze=0))
 print('Frozen',len(files),'files, 44 deterministic methods; conditional 240 random methods')
