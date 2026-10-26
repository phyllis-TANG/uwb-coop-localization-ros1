"""Bounded HTTP range transfer, preserving failed parts; identity is checked on full bytes."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import urllib.parse


def validate_range(header,received,start,end,total):
    matches=re.findall(r'(?im)^content-range:\s*bytes\s+(\d+)-(\d+)/(\d+)\s*$',header)
    if not matches or tuple(map(int,matches[-1]))!=(start,end,total):
        raise ValueError('HTTP Content-Range mismatch')
    if received!=end-start+1:
        raise ValueError('HTTP range byte count mismatch')


def download(asset,downloads,proxy=None,chunk_size=32*1024*1024):
    import prepare
    downloads=Path(downloads);downloads.mkdir(parents=True,exist_ok=True)
    fd,part=tempfile.mkstemp(prefix=asset['name']+'.ranges-partial-',dir=downloads)
    import os
    os.close(fd);part=Path(part)
    total=asset['size_bytes']
    with part.open('ab') as out:
        for start in range(0,total,chunk_size):
            end=min(total-1,start+chunk_size-1)
            success=False
            for attempt in range(3):
                fd,block=tempfile.mkstemp(prefix=asset['name']+'.range-',dir=downloads)
                os.close(fd);block=Path(block);header=block.with_suffix('.headers')
                sep='&' if '?' in asset['url'] else '?'
                url=asset['url']+sep+urllib.parse.urlencode({'reference_range':f'{start}-{end}'})
                command=['curl.exe','--location','--fail','--silent','--show-error',
                    '--connect-timeout','15','--max-time','90','--range',f'{start}-{end}',
                    '--dump-header',str(header),'--output',str(block)]
                if proxy:command+=['--proxy',proxy]
                r=subprocess.run(command+[url],capture_output=True,text=True)
                try:
                    if r.returncode:raise ValueError('curl failed: '+r.stderr.strip())
                    validate_range(header.read_text(encoding='latin1'),block.stat().st_size,start,end,total)
                    with block.open('rb') as stream:shutil.copyfileobj(stream,out,1024*1024)
                    out.flush()
                    block.unlink();header.unlink()
                    success=True
                    print(f'RANGE {asset["id"]} {end+1}/{total}',flush=True)
                    break
                except Exception as e:
                    print(f'RETRY {asset["id"]} range {start}-{end} attempt {attempt+1}: {e}',flush=True)
            if not success:raise RuntimeError('bounded range attempts exhausted; partials preserved')
    prepare.verify_download(part,asset)
    target=downloads/asset['name']
    if target.exists():raise ValueError('destination appeared during transfer')
    part.rename(target)
    return target
