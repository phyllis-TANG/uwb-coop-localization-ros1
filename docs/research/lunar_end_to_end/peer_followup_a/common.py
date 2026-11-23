import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PILOT = HERE.parent/'layout_peer_pilot'
CFG = json.loads((HERE/'config.json').read_text())
JOBS = HERE/'cases'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_source():
    for name, expected in CFG['source_sha256'].items():
        if sha(PILOT/name) != expected:
            raise ValueError(f'source mismatch: {name}')


def obs(key):
    return json.loads((PILOT/'results/observations'/f'{key}.json').read_text())


def mode(cm):
    return {None:'anchor_only',60:'peer_bounded',0:'peer_known_zero'}.get(cm,f'width_{cm}')


def files(key,cm):
    parent=JOBS/f'{key}_{cm}' if cm in CFG['new_cm'] else PILOT/'results'
    job=key+'_'+mode(cm)
    return parent/'trees'/f'{job}.gz', [parent/'certificates'/f'{job}_Car{c}.json' for c in (1,2)]


def receipt(key,cm):
    path=JOBS/f'{key}_{cm}'/'receipt.json'
    r=json.loads(path.read_text())
    assert (r['key'],r['cm'],r['config_sha256'])==(key,cm,sha(HERE/'config.json'))
    for name,expected in r['sha256'].items():
        assert sha(path.parent/name)==expected
