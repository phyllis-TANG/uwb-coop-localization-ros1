"""T10-only evidence intake; no estimator or reference calibration here."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
SESSION = ROOT / 'docs/field_tests/20261024_25'
VIDEO = SESSION / 'video_reference_20261026'
DOCS = SESSION / 't10_closure_20261027'
BASE_COMMIT = '32445a299b3f4674b865c4d78c4f662e51b5b857'
OLD_COMMIT = '4a379da4044a5fd6d36cb8c3e2c53f4a7d120d5b'
BAG_SHA = 'f2853240661be0cef53e77cee9a5a33f74cfb1524231d2eb94b2dcacaa57c558'
MOV_SHA = 'f7ec52ce2393d78eb250fce0e25ce4616e1c34f2ddf3e37cd2c73e147fc64967'
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'causal_baselines'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'parameter_clock_prep'))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def write(path, value):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def git_blob(rev, path):
    return subprocess.check_output(['git', 'show', rev + ':' + path], cwd=ROOT)


def verify_manifest_compatibility(old, current):
    # Fail closed on every semantic change except the dispatch's enumerated
    # media-only fields. This is evidence reuse, not a new normalization run.
    allowed = {'assets', 'motion_videos', 'pending_videos',
               'pending_qc_video_assets', 'coordinator_reconciliation'}
    changed = {k for k in set(old) | set(current) if old.get(k) != current.get(k)}
    if changed - allowed: raise ValueError('non-media manifest change: ' + str(changed - allowed))
    for asset_id in ('bags', 'T10_video'):
        a = next(x for x in old['assets'] if x['id'] == asset_id)
        b = next(x for x in current['assets'] if x['id'] == asset_id)
        if a != b: raise ValueError('selected asset identity changed: ' + asset_id)
    selected = lambda m: next(x for x in m['motion_videos'] if x['experiment_id']=='T10')
    if selected(old)!=selected(current) or selected(current)['sha256']!=MOV_SHA:
        raise ValueError('selected T10 MOV metadata changed')
    a = next(x for x in current['formal_bags'] if x['id'] == 'T10')
    if a['sha256'] != BAG_SHA or a['split'] != 'development' or '184755' not in a['relative_path']:
        raise ValueError('only the successful development retry is authorized')
    return sorted(changed)


def verify_normalized(root):
    root = Path(root)
    registered = json.loads((ROOT / 'tools/field_20261024_25/causal_baselines/results_summary/reuse_receipt.json').read_text())
    if sha(root / 'run.json') != registered['registered_run_sha256']:
        raise ValueError('PR45 registered run hash mismatch')
    run = json.loads((root / 'run.json').read_text())
    if run['status'] != 'DONE' or run['role'] != 'sandbox_normalization': raise ValueError('invalid PR45 run')
    checked = []
    for item in run['outputs']:
        p = Path(item['relative_path'])
        if p.is_absolute() or '..' in p.parts or sha(root / p) != item['sha256']:
            raise ValueError('normalized output hash/path mismatch: ' + str(p))
        checked.append(item)
    old_manifest = git_blob(OLD_COMMIT, 'docs/field_tests/20261024_25/manifest.json')
    old_geometry = git_blob(OLD_COMMIT, 'docs/field_tests/20261024_25/geometry.json')
    if hashlib.sha256(old_manifest).hexdigest() != run['config_sha256']['manifest.json']:
        raise ValueError('historical manifest fingerprint mismatch')
    if hashlib.sha256(old_geometry).hexdigest() != run['config_sha256']['geometry.json']:
        raise ValueError('historical geometry fingerprint mismatch')
    if json.loads(old_geometry) != json.loads((SESSION / 'geometry.json').read_text()):
        raise ValueError('geometry semantic change')
    changed = verify_manifest_compatibility(json.loads(old_manifest), json.loads((SESSION / 'manifest.json').read_text()))
    return {'status':'DONE', 'parent_run_sha256':sha(root / 'run.json'), 'outputs_checked':checked,
            'current_manifest_sha256':sha(SESSION / 'manifest.json'), 'current_geometry_sha256':sha(SESSION / 'geometry.json'),
            'manifest_changed_fields':changed, 'formal_bags_unchanged':True,
            'normalization_executed':False, 'old_run_mutated':False,
            'policy':'verify registered bytes plus explicit media-only compatibility; do not rewrite run.json'}


def verify_video_artifacts():
    registry = json.loads((VIDEO / 'artifact_manifest.json').read_text())
    for item in registry['files']:
        p = Path(item['relative_path'])
        if p.is_absolute() or '..' in p.parts or sha(VIDEO / p) != item['sha256']:
            raise ValueError('PR49 artifact mismatch: ' + str(p))
    return {'status':'DONE','registry_sha256':sha(VIDEO / 'artifact_manifest.json'),
            'artifacts_verified':len(registry['files']), 'media_decode_repeated':False}


def start(output, role):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    commit = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    dirty = bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip())
    deps = list(Path(__file__).parent.glob('*.py'))
    for sub in ('causal_baselines','parameter_clock_prep'):
        deps += list((Path(__file__).parent.parent / sub).glob('*.py'))
        deps += list((Path(__file__).parent.parent / sub).glob('*.json'))
    run = {'schema_version':1,'role':role,'status':'IN_PROGRESS', 'base_commit':BASE_COMMIT,
        'source_code_commit':commit,'worktree_dirty':dirty,'created_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
        'command_argv':[sys.executable]+sys.argv,'python':sys.version,
        'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in deps},
        'config_sha256':{f:sha(SESSION / f) for f in ('manifest.json','geometry.json')},'inputs':[]}
    write(output / 'checkpoint.json',run)
    return run


def finish(output, run, status):
    run['status'] = status
    run['outputs'] = [{'relative_path':str(p.relative_to(output)),'sha256':sha(p),'size_bytes':p.stat().st_size}
                      for p in sorted(Path(output).rglob('*')) if p.is_file() and p.name != 'run.json']
    write(Path(output) / 'run.json',run)
