"""Immutable experiment IO; no sensor or solver equations."""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DOC = ROOT/'docs/research/two_car_mechanism_20261101'
CARS = ('car1', 'car2')
METHODS = ('M2', 'M3', 'M3W025')
MOTIONS = ('static_moving', 'both_moving')
CONDITIONS = ('nominal', 'car1_wall_14', 'car2_wall_14')


def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(x):
    return hashlib.sha256(canonical(x).encode()).hexdigest()


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def dump(p, x):
    Path(p).write_text(json.dumps(x, indent=2, sort_keys=True, allow_nan=False)+'\n')


def lines(p):
    with (gzip.open(p, 'rt') if str(p).endswith('.gz') else open(p)) as f:
        for row in f:
            if row.strip():
                yield json.loads(row)


def write_lines(p, rows):
    with Path(p).open('xb') as raw, gzip.GzipFile(fileobj=raw, filename='', mode='wb', mtime=0) as stream:
        for row in rows:
            stream.write((canonical(row)+'\n').encode())


def new_output(p):
    p = Path(p).resolve()
    if p == ROOT or ROOT in p.parents:
        raise ValueError('Research run artifacts must be Git-external')
    p.mkdir(parents=True, exist_ok=False)
    return p


def sources():
    lock = json.loads((HERE/'dependency_lock.json').read_text())
    for p, expected in lock.items():
        if sha(ROOT/p) != expected:
            raise ValueError('Frozen dependency changed: '+p)
    return {**lock, **{str(p.relative_to(ROOT)):sha(p) for p in HERE.iterdir() if p.suffix in ('.py', '.json')}}


def git_state():
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()
    return dict(code_commit=git('rev-parse','HEAD'), worktree_dirty=bool(git('status','--porcelain')))


def protocol(path):
    path = Path(path)
    value = json.loads(path.read_text())
    expected = json.loads(path.with_suffix('.sha256.json').read_text())['sha256']
    if sha(path) != expected:
        raise ValueError('Protocol content hash mismatch')
    return value


def compact(row):
    """Lossless removal of repeated immutable graph inputs from journals."""
    row = dict(row)
    full = row['snapshot']
    row['snapshot_sha256_expanded'] = digest(full)
    row['snapshot'] = {k:v for k,v in full.items() if k not in ('local','observations','peers_m','intervals')}
    row['snapshot_encoding'] = 'history_inputs_v1'
    return row


def expanded_rows(path):
    history = {}
    for row in lines(path):
        if row.get('snapshot_encoding') != 'history_inputs_v1':
            raise ValueError('Unknown graph journal encoding')
        history[row['state_time_s']] = row
        snap = row['snapshot']
        times = snap['times_s']
        snap['local'] = [[history[t]['bins'][c]['local_odom'] for c in CARS] for t in times]
        snap['observations'] = [{c:history[t]['bins'][c]['observations'] for c in CARS} for t in times]
        snap['peers_m'] = [history[t]['peer_median_m'] if snap['peer_enabled'] else None for t in times]
        snap['intervals'] = [history[t]['angular_intervals'] for t in times[1:]]
        if digest(snap) != row['snapshot_sha256_expanded']:
            raise ValueError('Graph input reconstruction differs from online snapshot')
        # Bounded reader history covers the oldest incident state as well.
        history = {t:v for t,v in history.items() if t >= times[0]-1}
        yield row
