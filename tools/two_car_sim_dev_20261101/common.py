"""Development-only artifacts and immutable source provenance."""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CARS = ('car1', 'car2')
EPOCH_NS = 1_790_000_000_000_000_000
DEVELOPMENT_SEED = 7


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n')


def lines(path):
    with (gzip.open(path, 'rt') if str(path).endswith('.gz') else open(path)) as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def write_lines(path, rows):
    with Path(path).open('xb') as raw, gzip.GzipFile(fileobj=raw, filename='', mode='wb', mtime=0) as stream:
        for row in rows:
            stream.write((canonical(row)+'\n').encode())


def new_output(path):
    path = Path(path).resolve()
    if path == ROOT or ROOT in path.parents:
        raise ValueError('Outputs must be outside the Git worktree')
    path.mkdir(parents=True, exist_ok=False)
    return path


def sources():
    lock = json.loads((HERE/'source_lock.json').read_text())
    for path, expected in lock.items():
        if sha(ROOT/path) != expected:
            raise ValueError('Frozen source changed: '+path)
    return {**lock, **{str(p.relative_to(ROOT)):sha(p) for p in HERE.iterdir()
                     if p.suffix in ('.py', '.json')}}


def git_state():
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()
    return dict(code_commit=git('rev-parse', 'HEAD'), worktree_dirty=bool(git('status', '--porcelain')))
