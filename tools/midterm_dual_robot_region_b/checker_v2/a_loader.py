"""Load published A v2 by its absolute path; its own loader resolves sibling core."""
import sys
from pathlib import Path
from common import load_module,sha

def load_a(lock):
 root=Path(lock['source_root'])
 for path,h in lock['files'].items():
  if sha(root/path)!=h:raise RuntimeError('A_V2_HASH_MISMATCH:'+path)
 sentinel=object();previous=sys.modules.get('core',sentinel)
 fast=load_module('dual_a_v2_kernel_locked',root/'tools/midterm_dual_robot_contract_a/checker_v2.py')
 if fast.CHECKER_VERSION!='DUAL-A-CHECKER-V2':raise RuntimeError('Unexpected A checker API')
 assert sys.modules.get('core',sentinel) is previous
 return fast._core,fast
