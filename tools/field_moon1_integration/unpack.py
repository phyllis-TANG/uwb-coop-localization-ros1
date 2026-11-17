"""Restore portable JSON files into an exclusively new directory; no optimization."""
import gzip,json,sys
from pathlib import Path
from common import write
source,dest=map(Path,sys.argv[1:]);dest.mkdir(parents=True,exist_ok=False)
with gzip.open(source,'rt') as f:items=json.load(f)
for rel,data in items.items():
 p=Path(rel)
 if p.is_absolute() or '..' in p.parts:raise ValueError('unsafe relative path')
 write(dest/p,data)
print('Restored',len(items),'JSON files; optimizer_calls=0')
