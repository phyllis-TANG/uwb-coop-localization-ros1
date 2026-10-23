#!/usr/bin/env python3
"""Versioned path/checkpoint compatibility, separate from execution evidence."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shlex

VERSION='1.2.0'
MANIFEST=Path('tools/integrity_compat/v1_2_0/manifest.json')
RUNNER='tools/run_single_car_integrity_experiment.py'


def checksum(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):digest.update(block)
    return digest.hexdigest()


def within(root,relative):
    relative=Path(relative)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Expected a repository-relative path: '+str(relative))
    root=Path(root).resolve();path=(root/relative).resolve()
    if not path.is_relative_to(root):raise ValueError('Path escapes expected root: '+str(relative))
    return path


def compatibility_manifest(repository_root):
    root=Path(repository_root).resolve()
    manifest=json.loads((root/MANIFEST).read_text())
    if manifest['compatibility_version']!=VERSION:raise ValueError('Unknown compatibility version')
    for relative,expected in manifest['compatibility_sources'].items():
        if checksum(within(root,relative))!=expected:
            raise ValueError('Compatibility source hash mismatch: '+relative)
    for relative,entry in manifest['source_replacements'].items():
        if checksum(within(root,entry['snapshot']))!=entry['original_sha256']:
            raise ValueError('Original source snapshot changed: '+relative)
    return manifest


def verify_execution_state(out,repository_root,current):
    """Only the exact registered runner patch can differ from its execution lock.

    Estimator/generator/test hashes and original protocol/config remain strict.
    Neither the old lock nor its recorded expected hashes are ever rewritten.
    """
    out=Path(out);root=Path(repository_root)
    expected=json.loads((out/'source_lock.json').read_text())['locked']
    if current['protocol_sha256']!=expected['protocol_sha256'] or current['config_sha256']!=expected['config_sha256']:
        raise ValueError('Frozen protocol/config changed')
    if set(current['sources'])!=set(expected['sources']):raise ValueError('Execution source set changed')
    manifest=compatibility_manifest(root)
    changed={name for name in expected['sources'] if current['sources'][name]!=expected['sources'][name]}
    if not changed:return dict(mode='strict',compatibility_version=VERSION,changed_execution_sources=[])
    if changed!={RUNNER}:raise ValueError('Unregistered execution source change: '+', '.join(sorted(changed)))
    if checksum(out/'source_lock.json') not in manifest['supported_execution_source_lock_sha256']:
        raise ValueError('Execution lock not registered for this compatibility version')
    entry=manifest['source_replacements'][RUNNER]
    if expected['sources'][RUNNER]!=entry['original_sha256'] or current['sources'][RUNNER]!=entry['compatible_sha256']:
        raise ValueError('Registered runner replacement hash mismatch')
    return dict(mode='registered_compatibility',compatibility_version=VERSION,changed_execution_sources=sorted(changed),
                original_execution_lock_sha256=checksum(out/'source_lock.json'))


def resolve_input(out,repository_root,record,protocol):
    """Never reopen the original absolute path, even if it still exists.

    Prefer ONLY this experiment's own sensors or this repository's declared bag.
    A missing or corrupt local copy fails; there is no fallback to old evidence.
    """
    out=Path(out).resolve();root=Path(repository_root).resolve()
    if record['group'] in ('development','diagnostic'):
        path=within(out,Path('runs')/record['id']/'sensors.jsonl')
        resolution='current_experiment'
    elif record['group']=='historical':
        prefix='history_'
        if not record['id'].startswith(prefix):raise ValueError('Unknown historical run ID')
        identifier=record['id'][len(prefix):]
        cases=[case for case in protocol['historical_cases'] if case['id']==identifier]
        if len(cases)!=1:raise ValueError('Historical run must match one protocol case')
        case=cases[0]
        if case['sha256']!=record['input_sha256']:raise ValueError('Protocol/run input hashes disagree')
        path=within(root,case['bag']);resolution='current_repository'
    else:raise ValueError('Unsupported input group: '+str(record['group']))
    if not path.is_file():raise FileNotFoundError('Current input missing (old absolute path is provenance only): '+str(path))
    actual=checksum(path)
    if actual!=record['input_sha256']:raise ValueError('Current input SHA256 mismatch: '+str(path))
    return dict(run_id=record['id'],resolved_input_path=str(path),recorded_input_path=record['input_path'],
                input_sha256=actual,resolution=resolution)


def verify_record(out,repository_root,record,protocol):
    out=Path(out).resolve();target=within(out,Path('runs')/record['id'])
    if record['source_lock_sha256']!=checksum(out/'source_lock.json'):
        raise ValueError('Resume execution-lock hash mismatch: '+record['id'])
    if record.get('config_sha256') and record['config_sha256']!=checksum(out/'estimator_config.json'):
        raise ValueError('Resume config hash mismatch: '+record['id'])
    threshold=checksum(out/'thresholds.json') if record['group']=='diagnostic' else None
    if record['threshold_sha256']!=threshold:raise ValueError('Resume threshold hash mismatch: '+record['id'])
    resolution=resolve_input(out,repository_root,record,protocol)
    if not record.get('output_files'):raise ValueError('Missing output hash manifest: '+record['id'])
    for relative,expected in record['output_files'].items():
        if checksum(within(target,relative))!=expected:
            raise ValueError('Saved output changed: '+record['id']+':'+relative)
    return resolution


def handoff_text(out,repository_root,stage,records):
    out=Path(out).resolve();root=Path(repository_root).resolve()
    protocol=json.loads((out/'protocol.json').read_text())
    argument=str(out.relative_to(root)) if out.is_relative_to(root) else str(out)
    counts={status:sum(r['status']==status for r in records) for status in sorted({r['status'] for r in records})}
    resume='OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 tools/run_single_car_integrity_experiment.py --experiment '+shlex.quote(argument)+' --resume-only'
    audit='OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 tools/verify_single_car_integrity_artifacts.py --experiment '+shlex.quote(argument)
    return ('# 定位完好性试验交接（兼容修复 '+VERSION+'）\n\n'
        +'实验标识：'+protocol.get('experiment',out.name)+'\n\n仓库：`'+str(root)+'`\n\n当前实验目录：`'+str(out)+'`\n\n'
        +'阶段：'+stage+'；运行状态：'+json.dumps(counts,ensure_ascii=False)+'。\n\n'
        +'原绝对输入路径仅作来源记录。恢复使用当前实验的sensors.jsonl或当前仓库的协议bag，并严格核对原SHA256；原执行源码锁、阈值和结果保持不变。\n\n'
        +'从上述仓库目录执行；依赖按tools/requirements-integrity-feasibility.txt提供：\n\n```bash\n'+resume+'\n'+audit+'\n```\n\n'
        +'--resume-only仅核对已存在运行，任何缺失/未完成项即停止，绝不启动估计器、不重新选择阈值。兼容版本/源码快照与哈希见tools/integrity_compat/v1_2_0/manifest.json。\n\n'
        +'本交接文件为新恢复元数据，不覆盖原根目录HANDOFF或旧报告；不启动真实小车、不默认启用监测器、不合并main。\n')


def preserve_original_artifact_hashes(repository_root,ledger):
    """Audit old ledger with explicit original snapshots for changed code files."""
    root=Path(repository_root);manifest=compatibility_manifest(root);checked=0;replacements=[]
    for line in Path(ledger).read_text().splitlines():
        expected,relative=line.split('  ',1);path=within(root,relative)
        if checksum(path)!=expected:
            entry=manifest['source_replacements'].get(relative)
            if not entry or expected!=entry['original_sha256'] or checksum(path)!=entry['compatible_sha256']:
                raise ValueError('Original artifact changed: '+relative)
            # Snapshot already checked by compatibility_manifest().
            replacements.append(relative)
        checked+=1
    return dict(original_ledger_entries_checked=checked,explicit_source_replacements=sorted(replacements),
                original_evidence_bytes_unchanged=True,compatibility_version=VERSION)
