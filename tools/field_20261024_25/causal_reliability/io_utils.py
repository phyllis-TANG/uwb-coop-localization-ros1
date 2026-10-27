"""Strict JSON, streaming gzip, source identities and non-overwriting journals."""
import datetime
import gzip
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
DEFAULT_PROTOCOL=ROOT/"docs/field_tests/20261024_25/causal_reliability_20261027/frozen_protocol.json"


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda:stream.read(1048576),b""):digest.update(block)
    return digest.hexdigest()


def dump(path,value):
    path=Path(path);temporary=path.with_suffix(path.suffix+".tmp")
    temporary.write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+"\n")
    temporary.replace(path)


def append(stream,value):stream.write(json.dumps(value,sort_keys=True,allow_nan=False,separators=(",",":"))+"\n")


def gzwrite(path):return gzip.open(path,"xt",encoding="utf-8",compresslevel=2)


def gzread(path):
    with gzip.open(path,"rt",encoding="utf-8") as stream:
        for line in stream:yield json.loads(line)


def provenance(protocol):
    import numpy
    sources=sorted(HERE.glob("*.py"))+sorted((HERE.parent/"causal_baselines").glob("*.py"))+[HERE.parent/name for name in ("normalize.py","development.py","prepare.py","run_nightly.py")]
    environment=dict(python=platform.python_version(),numpy=numpy.__version__,thread_env={key:os.environ.get(key) for key in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS")})
    lock=dict(source_sha256={str(path.relative_to(ROOT)):sha(path) for path in sources},protocol_sha256=sha(protocol),environment=environment)
    text=json.dumps(lock,sort_keys=True,separators=(",",":"));lock["fingerprint_sha256"]=hashlib.sha256(text.encode()).hexdigest()
    return lock


def git_state():
    def command(*args):return subprocess.run(["git",*args],cwd=ROOT,check=True,capture_output=True,text=True).stdout.strip()
    return dict(code_commit=command("rev-parse","HEAD"),branch=command("branch","--show-current"),worktree_dirty=bool(command("status","--porcelain")))


def output_hashes(root):return [{"relative_path":str(path.relative_to(root)),"sha256":sha(path)} for path in sorted(Path(root).rglob("*")) if path.is_file() and path.name!="run.json"]


def verify_unit(path,fingerprint,input_sha):
    run=json.loads((path/"run.json").read_text())
    if run["status"]!="DONE" or run["fingerprint_sha256"]!=fingerprint or run["input_sha256"]!=input_sha:raise ValueError("cannot resume incomplete or different source/input: "+str(path))
    for item in run["outputs"]:
        if sha(path/item["relative_path"])!=item["sha256"]:raise ValueError("saved output changed: "+item["relative_path"])
    return run


def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()


def environment_packages():return sorted(f"{p.metadata['Name']}=={p.version}" for p in importlib.metadata.distributions())


def verify_saved_root(output):
    """Validate completed evidence and unit provenance before any resume writes."""
    output=Path(output).resolve();run=json.loads((output/"run.json").read_text())
    for item in run.get("outputs",[]):
        relative=Path(item["relative_path"])
        if relative.is_absolute() or ".." in relative.parts:raise ValueError("unsafe saved output path")
        path=(output/relative).resolve()
        if not path.is_relative_to(output) or sha(path)!=item["sha256"]:raise ValueError("saved root output hash mismatch: "+str(relative))
    inventory=output/"inventory.json"
    if inventory.exists():
        for row in json.loads(inventory.read_text()):
            if row["status"]=="DONE" and sha(output/"runs"/row["id"]/"run.json")!=row["run_json_sha256"]:
                raise ValueError("saved unit run provenance changed: "+row["id"])
    return run
