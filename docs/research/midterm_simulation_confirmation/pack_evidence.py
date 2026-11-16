"""Make a small portable estimate receipt; retain full matrices outside Git."""
import argparse,gzip,hashlib,json
from pathlib import Path
from readback import canonical

def main():
    p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,required=True);p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True);z=p.parse_args();z.out.mkdir(parents=True,exist_ok=False)
    with (z.out/'ESTIMATES.jsonl.gz').open('xb') as raw:
        with gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as dst:
            for line in gzip.open(z.evidence,'rt'):
                row=json.loads(line)
                if row['type']=='METHOD':
                    for stage,r in row['value']['stages'].items():
                        for key in ['residual','gradient','scaled_gradient']:r.pop(key,None)
                        r['information'].pop('singular_values',None)
                dst.write(canonical(row)+b'\n')
    index={str(f.relative_to(z.run)):dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for f in sorted(z.run.rglob('*')) if f.is_file()}
    with (z.out/'RAW_FILE_HASHES.json.gz').open('xb') as raw:
        with gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as dst:dst.write(canonical(dict(directory=str(z.run),files=index)))
    print('portable bytes',(z.out/'ESTIMATES.jsonl.gz').stat().st_size,'raw files',len(index))
if __name__=='__main__':main()
