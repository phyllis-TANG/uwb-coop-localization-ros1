"""Eager NPZ loading adapter for the unchanged frozen independent verifier.
Only removes repeated decompression; all arithmetic and assertions remain in verify.py.
"""
import argparse,json
from pathlib import Path
import verify
from regions import save

def run(results):
 original=verify.np.load
 def eager(*args,**kwargs):
  with original(*args,**kwargs) as archive:return {key:archive[key] for key in archive.files}
 verify.np.load=eager
 try:return verify.verify(results)
 finally:verify.np.load=original
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();r=run(a.results);save(a.out,r);print(json.dumps(r))
