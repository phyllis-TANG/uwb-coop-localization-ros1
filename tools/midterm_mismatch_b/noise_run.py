"""Separate config/manifest entry point; same frozen stage engine and objective."""
import argparse
from pathlib import Path
import run as engine
from io_utils import DOC,read
NDOC=DOC/'noise_exploration'
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);p.add_argument('--mode',choices=['development','formal'],required=True);p.add_argument('--freeze');p.add_argument('--resume',action='store_true');a=p.parse_args();engine.DOC=NDOC
    print(engine.run(a.out,read(NDOC/'CONFIG.json'),a.mode,a.freeze,a.resume))
