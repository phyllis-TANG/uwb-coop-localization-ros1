"""Read-only I/O acceleration of frozen analysis; load compressed arrays once.
No statistic, threshold, seed, model or result is changed. The original frozen
analyze.py stays byte-for-byte intact; this wrapper only caches np.load arrays.
"""
import argparse
from pathlib import Path
import numpy as np
from analyze import analyze
_original=np.load
def cached_load(*args,**kwargs):
    obj=_original(*args,**kwargs)
    if isinstance(obj,np.lib.npyio.NpzFile):
        arrays={key:obj[key] for key in obj.files};obj.close();return arrays
    return obj
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();np.load=cached_load;analyze(a.input,a.out)
