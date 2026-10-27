"""Strict JSON, streaming evidence and content identity helpers."""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
import numpy as np
import scipy
from legacy import ROOT, LOCK


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''): h.update(block)
    return h.hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n')


def append(stream, value):
    stream.write(json.dumps(value, sort_keys=True, allow_nan=False)+'\n')


def read_jsonl(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt') as f:
        for line in f:
            if line.strip(): yield json.loads(line, parse_constant=lambda s: (_ for _ in ()).throw(ValueError('Nonfinite JSON: '+s)))


def git_state():
    def git(*args):
        return subprocess.check_output(['git', '-C', str(ROOT), *args], text=True).strip()
    return dict(code_commit=git('rev-parse', 'HEAD'), worktree_dirty=bool(git('status', '--porcelain')))


def utc():
    return datetime.now(timezone.utc).isoformat()


def sources():
    paths = list(Path(__file__).parent.glob('*.py'))+list(Path(__file__).parent.glob('*.json'))
    paths += [Path(__file__).with_name('requirements.txt')]
    paths += [ROOT/p for p in LOCK['files']]
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(set(paths))}


def outside(path):
    p = Path(path).resolve()
    if p == ROOT or ROOT in p.parents: raise ValueError('Output must be outside Git worktree')
    return p


def environment():
    return dict(python=sys.version, numpy=np.__version__, scipy=scipy.__version__,
                threads={k: __import__('os').environ.get(k) for k in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS')})


def outputs(root):
    return [{'relative_path': str(p.relative_to(root)), 'sha256': sha(p), 'size_bytes': p.stat().st_size}
            for p in sorted(Path(root).rglob('*')) if p.is_file() and p.name != 'run.json']
