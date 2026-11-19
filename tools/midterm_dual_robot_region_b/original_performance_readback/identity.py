"""Bind receipts and the scientific outputs to the frozen jobs and old PR133 trees."""
import argparse
import gzip
import json
from pathlib import Path
import sys
import tarfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'original_performance'))
from study import D,DOC,read,schedule,sha,digest

FREEZE='cdb35b0c7ebcd550bdb8933b438da236b1b179ed'


def main():
    plan=read(D/'FROZEN_PLAN.json')
    counts={}
    for stage in ('pilot','deterministic','random'):
        folder=D/stage
        if not folder.exists():
            counts[stage]=0
            continue
        count=0
        for spec in plan[stage]:
            unit=spec['id']
            directory=folder/unit
            job=read(directory/'job.json')
            receipt=read(directory/'receipt.json')
            ident=receipt['identity']
            assert ident==job['identity'] and ident['freeze_sha']==FREEZE
            assert ident['case_sha256']==digest(job['case'])==spec['case_hash']
            assert job['settings']==spec['settings'] and ident['settings_sha256']==digest(spec['settings'])
            assert job['arm']==spec['arm'] and job['method']==ident['method']
            assert sha(directory/(unit+'.result.json.gz'))==receipt['record_sha256']
            assert sha(directory/(unit+'.certificate.json.gz'))==receipt['certificate_sha256']
            count+=1
        counts[stage]=count
    print('Verified frozen identities and payload hashes:',counts)

    archive=DOC/'checker_v2/evidence/deterministic.tar.gz'
    manifest=read(archive.parent/'MANIFEST.json')
    assert sha(archive)==manifest['archives'][archive.name]['sha256']
    compared=0
    with tarfile.open(archive) as tar:
        for member in tar:
            if not member.name.endswith('.result.json.gz'):continue
            unit=Path(member.name).name.removesuffix('.result.json.gz')
            directory=D/'deterministic'/unit
            if not directory.exists():continue
            old=json.loads(gzip.decompress(tar.extractfile(member).read()))
            new=read(directory/(unit+'.result.json.gz'))
            for key in ('nodes','queue','termination','counts','dimension','empty_proved'):
                assert old['result'][key]==new['result'][key],(unit,key)
            for key in ('projections','evaluation','certificate_b','certificate_a'):
                assert old[key]==new[key],(unit,key)
            compared+=1
    print('Identical old/new trees, queues, projections, point evaluations and verdicts:',compared)

if __name__=='__main__':main()
