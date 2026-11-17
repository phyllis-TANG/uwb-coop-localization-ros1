"""Verify all delivered bytes and authorized source scope without modifying files."""
from common import *
manifest=json.loads((DOC/'SHA256SUMS.json').read_text())
for path,h in manifest.items():assert sha(ROOT/path)==h,path
print(json.dumps(dict(passed=True,files_checked=len(manifest),source_sha=CFG['source_sha'])))
