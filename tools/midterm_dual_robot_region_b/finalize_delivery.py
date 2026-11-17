"""Publish metadata after zero-search archive checks; never execute experiments."""
import argparse
import datetime
from common import *


def finalize(a_report, payload):
    cross = read(a_report)
    assert cross['locked_b_sha'] == payload
    assert cross['cross_readback'] == 'INCOMPLETE'
    assert cross['planned'] == 48 and cross['certified'] == 44
    assert cross['not_certified'] == 4
    assert all(x['execution_status'] == 'NOT_RUN' and
               x['reason'] == 'OUTSIDE_USER_AUTHORIZED_PLAN'
               for x in cross['attempts'])
    assert all(x['certificate_valid'] for x in cross['results'])
    manifest = read(DOC/'evidence/MANIFEST.json')
    assert cross['archive_hash'] == manifest['archive_hash']
    readback = read(DOC/'results/READBACK.json')
    gate = read(DOC/'GATE.json')
    assert readback['status'] == 'PASS' and readback['completed'] == 44
    assert gate['status'] == 'FAIL' and not gate['random_authorized_to_execute']
    for name, h in read(DOC/'FREEZE_MANIFEST.json')['files'].items():
        assert sha(ROOT/name) == h, name
    write(DOC/'results/A_ARCHIVE_READBACK.json', cross)
    manifest.update(source_commit=payload, status='RESULTS_READY',
                    stages_completed=['development', 'deterministic', 'zero_search_readback'],
                    random_stage='SKIPPED_GATE_FAILED',
                    random_gate_reasons=gate['reasons'],
                    denominators=dict(deterministic_planned=44, deterministic_completed=44,
                                      deterministic_failed=0, deterministic_unexecuted=0,
                                      random_planned=240, random_completed=0,
                                      random_unexecuted=240,
                                      a_compatibility_planned=48, a_compatibility_not_run=4),
                    certificate_status=dict(b_per_method='PASS', a_per_method='PASS',
                                            whole_zero_search_readback='PASS',
                                            a_archive='INCOMPLETE_ONLY_4_OUTSIDE_USER_PLAN'),
                    delivery_checks=dict(portable_hashes='PASS', frozen_sources='PASS'),
                    ready_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    write(DOC/'RESULTS_READY.json', manifest)
    progress = read(DOC/'PROGRESS.json')
    progress.update(stage='delivery_complete', last_updated=manifest['ready_at'],
                    current_case=None, delivery_blocked=None,
                    blocked='RANDOM_GATE_COST_EXCEEDS_2_SECONDS')
    write(DOC/'PROGRESS.json', progress)
    with (DOC/'STAGE_PROGRESS.md').open('a') as f:
        f.write('\n交付完成：A原生归档入口独立复核44条证书通过；其48条兼容分母中4条为用户未授权的特殊N4，因此原生状态INCOMPLETE如实保留。RESULTS_READY发布授权44/44及随机0/240；只推荐先优化独立认证成本。\n')
    files = sorted(p for folder in (DOC, ROOT/'tools/midterm_dual_robot_region_b')
                   for p in folder.rglob('*')
                   if p.is_file() and '__pycache__' not in p.parts
                   and p.name != 'SHA256SUMS')
    (DOC/'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.relative_to(ROOT)}\n' for p in files))
    print(json.dumps(dict(status='RESULTS_READY', hashed_files=len(files),
                          payload_sha=payload, experiments_executed=0)))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--a-report', type=Path, required=True)
    p.add_argument('--payload', required=True)
    a = p.parse_args()
    finalize(a.a_report, a.payload)
