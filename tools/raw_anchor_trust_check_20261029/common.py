"""Pinned metadata access. Never opens a real bag or invokes a locator."""
import csv,hashlib,io,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
MAIN='ae8ee37841ade972be3875968c6eb1b557c3ffdb'
ACTUAL='3d3c0703c00f369e8828f499c543f2be7aa4193a'
REFS={'pr71':'aa6d272f9dcb7180d7548a06cb11d5d28445b2dd','pr72':'1cc7713a7e48776474788a07a1b41040f9df9330','pr73':'a2028f01c5cd26d6e85961ade71f4ebd07b59b1c','pr74':'eb96853ef80cec39846d6df5d874db8247bbc989','pr75':'709c4127c8835f82c137e604d4c53bb541f52a59'}
DOC='docs/field_tests/20261024_25/'
def digest(data):return hashlib.sha256(data).hexdigest()
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def dump(path,data):
 with Path(path).open('x') as f:json.dump(data,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')
def csvwrite(path,rows):
 with Path(path).open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
class Sources:
 def __init__(self):self.items={}
 def read(self,path,ref=MAIN):
  data=subprocess.check_output(['git','show',ref+':'+path],cwd=ROOT)
  current=subprocess.check_output(['git','show',ACTUAL+':'+path],cwd=ROOT)
  self.items[ref+':'+path]=dict(path=path,git_commit=ref,sha256=digest(data),bytes=len(data),matches_actual_main=digest(data)==digest(current))
  return data.decode('utf-8-sig')
 def json(self,path,ref=MAIN):return json.loads(self.read(path,ref))
 def csv(self,path,ref=MAIN):return list(csv.DictReader(io.StringIO(self.read(path,ref))))
