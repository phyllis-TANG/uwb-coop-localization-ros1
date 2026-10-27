"""Strict portable records and source identities, independent of sensor semantics."""
import datetime
from contextlib import contextmanager
import gzip
import hashlib
import importlib.metadata
import io
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            digest.update(block)
    return digest.hexdigest()


def clean(value, path='', flags=None):
    if flags is None:
        flags = []
    if isinstance(value, float) and not math.isfinite(value):
        flags.append(dict(path=path, original=repr(value)))
        return None
    if isinstance(value, dict):
        return {k: clean(v, path + '.' + str(k), flags) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [clean(v, path + '[' + str(k) + ']', flags) for k, v in enumerate(value)]
    return value


def dump(path, value):
    path = Path(path); temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + '\n')
    temporary.replace(path)


def append(stream, value):
    stream.write(json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':')) + '\n')


@contextmanager
def gzip_writer(path):
    with Path(path).open('xb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, compresslevel=2, mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding='utf-8') as stream:
                yield stream


def read_jsonl(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8') as stream:
        for index, line in enumerate(stream):
            if line.strip():
                yield json.loads(line)


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def git_state():
    try:
        def git(*args):
            return subprocess.run(['git', *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
        return dict(code_commit=git('rev-parse', 'HEAD'), branch=git('branch', '--show-current'), worktree_dirty=bool(git('status', '--porcelain')))
    except subprocess.CalledProcessError:
        return dict(code_commit=None, branch=None, worktree_dirty=None, git_reason='archive execution without Git; recorded source SHA remains authoritative')


def sources():
    paths = list(HERE.glob('*.py')) + list(HERE.glob('*.json'))
    paths += [HERE.parent / 'causal_baselines' / name for name in ['model.py', 'replay.py', 'synthetic_config.json']]
    paths += [ROOT / 'docs/field_tests/20261024_25/imu_parallel_20261027/CONTRACT.json']
    return {str(path.relative_to(ROOT)): sha(path) for path in sorted(paths)}


def packages():
    return sorted(f"{p.metadata['Name']}=={p.version}" for p in importlib.metadata.distributions())


def outputs(root):
    return [dict(relative_path=str(p.relative_to(root)), sha256=sha(p), size_bytes=p.stat().st_size)
            for p in sorted(Path(root).rglob('*')) if p.is_file() and p.name != 'run.json']


def external_path(path):
    path = Path(path).resolve()
    if path.is_relative_to(ROOT) or ROOT.is_relative_to(path):
        raise ValueError('new results must be in an external directory outside/without the checkout')
    return path
