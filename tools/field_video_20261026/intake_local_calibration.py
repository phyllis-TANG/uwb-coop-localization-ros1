"""Copy user-provided calibration originals, verify known identity and safely extract."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'field_20261024_25'))
import prepare
import common

EXPECTED={
    'IMG_7336.zip': ('bc73edf107b01d73c3de3cf4846e93e965d0b8fd7ee13ff67270d44a0740090a',
        'c2b63890aa764c2128b6103163540073607dd7a131cdcdf05cf14ee916dc72c8'),
    'IMG_7337.zip': ('0f7bf0ba120716ea5c15292c4e45b50ff726c3ff9a863549a17e3215620822d4',
        '3abd6bfe961b6b7a5a9d184f1cd6dda61fc8569d4bf5e41f5024fcb4ddd03dd6')}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--files',nargs=2,required=True,type=Path)
    p.add_argument('--data-root',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    root=prepare.validate_data_root(a.data_root)
    (root/'downloads').mkdir(parents=True,exist_ok=True)
    results=[]
    for src in a.files:
        expected_zip,expected_mov=EXPECTED[src.name]
        if common.sha256(src)!=expected_zip:
            raise ValueError('Provided ZIP differs from historical identity: '+src.name)
        target=root/'downloads'/src.name
        with src.open('rb') as f,target.open('xb') as out:
            shutil.copyfileobj(f,out,1024*1024)
        if common.sha256(target)!=expected_zip:
            raise ValueError('Copy verification failed')
        with zipfile.ZipFile(target) as z:
            if z.testzip() is not None:raise ValueError('CRC failed')
        asset=dict(id=src.stem,name=src.name,sha256=expected_zip,size_bytes=src.stat().st_size)
        destination=root/'extracted'/src.stem
        prepare.extract_asset(target,destination,asset)
        receipt=prepare.verify_extraction(destination,asset)
        movies=[r for r in receipt['files'] if r['path'].endswith(src.stem+'.MOV') and '__MACOSX' not in r['path']]
        if len(movies)!=1 or movies[0]['sha256']!=expected_mov:
            raise ValueError('MOV historical identity mismatch')
        results.append(dict(asset_id=src.stem,archive_sha256=expected_zip,crc='passed',
            original_source='user_provided_local_attachment',receipt=receipt))
    common.write_json(a.output,results)
    print(json.dumps(results,indent=2))

if __name__=='__main__':main()
