"""Exact obtainable file identities; never synthesize unavailable source hashes."""
import hashlib,json
from pathlib import Path
def receipt(output, parameters, files, unavailable=None):
    records={}
    for role,path in files.items():
        path=Path(path)
        h=hashlib.sha256()
        if path.is_file():
            with path.open('rb') as f:
                for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
            records[role]=dict(path=str(path.resolve()),sha256=h.hexdigest(),status='readable')
        else:records[role]=dict(path=str(path),sha256=None,status='unavailable')
    for role,reason in (unavailable or {}).items():records[role]=dict(sha256=None,status='unavailable',reason=reason)
    Path(output).write_text(json.dumps(dict(parameters={k:str(v) if isinstance(v,Path) else v for k,v in parameters.items()},artifacts=records),indent=2)+'\n')
