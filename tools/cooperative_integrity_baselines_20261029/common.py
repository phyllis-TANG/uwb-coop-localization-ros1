"""Small immutable deliverables; no raw bags/videos or bulk caches."""
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SPEC = json.loads((HERE/'spec.json').read_text())


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def csv_write(path, rows):
    with Path(path).open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)


def source_lock():
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(HERE.glob('*')) if p.is_file()}


def new_output(path):
    path = Path(path).resolve()
    if path == ROOT or ROOT in path.parents:
        raise ValueError('Full run output must be outside the Git worktree')
    if shutil.disk_usage(path.parent).free < 500_000_000:
        raise RuntimeError('Insufficient workspace space; no fallback')
    path.mkdir(exist_ok=False)
    return path


def size_guard(root):
    total = sum(p.stat().st_size for p in Path(root).rglob('*') if p.is_file())
    if total > SPEC['max_new_artifacts_bytes']:
        raise RuntimeError('100 MB evidence cap exceeded')
    return total


def head():
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
