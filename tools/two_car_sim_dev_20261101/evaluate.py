"""Independent per-car whole-run evaluation; never imported by online code.

All durations use state hold [t,t+1), including t=0 no-publication. This is
sampled engineering exposure, not an integrity risk bound. Unknown is retained.
Recovery criteria remain unset, so no recovery time is inferred from the data.
"""
import argparse
import json
import math
from pathlib import Path
from common import CARS, dump, lines, sha


def antenna(p, model):
    lx, ly = model['base_to_antenna_body_xy_m']
    c, s = math.cos(p[2]), math.sin(p[2])
    return [p[0]+c*lx-s*ly, p[1]+s*lx+c*ly]


def rmse(values):
    return math.sqrt(sum(v*v for v in values)/len(values)) if values else None


def load(run, input_root):
    run, input_root = Path(run), Path(input_root)
    meta = json.loads((run/'run.json').read_text())
    manifest = json.loads((input_root/'manifest.json').read_text())
    if meta['status'] != 'DONE':
        raise ValueError('Incomplete replay')
    for name, digest in manifest['files'].items():
        if sha(input_root/name) != digest:
            raise ValueError('Input manifest SHA mismatch: '+name)
    if meta['input_sha256'] != sha(input_root/'events.jsonl.gz') or meta['config_sha256'] != sha(input_root/'config.json') or sha(run/'config.json') != meta['config_sha256']:
        raise ValueError('Replay/input binding')
    for name, digest in meta['outputs'].items():
        if sha(run/name) != digest:
            raise ValueError('Replay output SHA mismatch: '+name)
    labels = json.loads((input_root/'labels.json').read_text())
    config = json.loads((run/'config.json').read_text())
    truth = {r['state_epoch_ns']:r for r in lines(input_root/'truth.jsonl.gz')}
    rows = list(lines(run/'updates.jsonl.gz'))
    if len({r['state_epoch_ns'] for r in rows}) != len(rows):
        raise ValueError('Duplicate publications')
    return meta, labels, config, truth, {r['state_epoch_ns']:r for r in rows}


def evaluate(run, input_root, reference=None, nominal_run=None, nominal_input=None):
    meta, labels, config, truth, rows = load(run, input_root)
    horizon, origin = labels['duration_s'], labels['epoch_ns']
    if set(truth) != {origin+t*10**9 for t in range(horizon+1)}:
        raise ValueError('Missing whole-run truth grid')
    if any(t < origin or t >= origin+horizon*10**9 for t in rows):
        raise ValueError('Publication outside evaluation horizon')
    refs = None
    nominal = None
    if reference:
        rm, _, _, _, refs = load(reference, input_root)
        if rm['input_sha256'] != meta['input_sha256'] or rm['config_sha256'] != meta['config_sha256']:
            raise ValueError('Unpaired inputs')
    if bool(nominal_run) != bool(nominal_input):
        raise ValueError('Both nominal-run and nominal-input required')
    if nominal_run:
        nm, nl, nc, nt, nominal = load(nominal_run, nominal_input)
        if (nm['method_id'] != meta['method_id'] or nm['config_sha256'] != meta['config_sha256']
                or nl['fault'] is not None or labels['fault'] is None
                or any(nl[k] != labels[k] for k in ('seed','spec_sha256','duration_s','epoch_ns')) or nt != truth):
            raise ValueError('Nominal pairing requires same model/design/seed/truth and method')
    result = dict(development_only=True, independent_validation=False, method=meta['method_id'],
        condition=labels['condition'], duration_s=horizon, sample_convention='state hold [t,t+1), includes startup and no publication',
        recovery_criterion=None, recovery_time_s=None, recovery_status='NOT_FROZEN_NO_RECOVERY_CLAIM',
        probability_or_protection_level_claim=False, cars={}, monitor={}, reference_method=None if refs is None else rm['method_id'])
    for ci, car in enumerate(CARS):
        errors, base_errors, valid_errors, paired, differences, recovery_errors, nominal_tail = [], [], [], [], [], [], []
        finite_s = valid_s = failure_s = no_publication_s = 0
        for t in range(horizon):
            epoch = origin+t*10**9
            row = rows.get(epoch)
            if row is None:
                no_publication_s += 1
                continue
            p = row.get('pose')
            if p is None or not all(math.isfinite(v) for v in p):
                failure_s += 1
                continue
            p = p[4*ci:4*ci+4]
            xy, target = antenna(p, config['models'][car]), truth[epoch]['cars'][car]
            error = math.dist(xy, target['antenna_xyz_m'][:2])
            base_error = math.dist(p[:2], target['pose'][:2])
            errors.append(error)
            base_errors.append(base_error)
            finite_s += 1
            if row['estimate_valid'][car]:
                valid_s += 1
                valid_errors.append(error)
            if 'failed' in row['status'] or 'error' in row['status']:
                failure_s += 1
            if labels['fault'] and t >= labels['fault']['interval_s'][1]:
                recovery_errors.append(error)
                normal_row = None if nominal is None else nominal.get(epoch)
                if normal_row is not None and normal_row['pose'] is not None and row['estimate_valid'][car] and normal_row['estimate_valid'][car]:
                    nominal_tail.append(math.dist(xy, antenna(normal_row['pose'][4*ci:4*ci+4], config['models'][car])))
            ref = None if refs is None else refs.get(epoch)
            if ref is not None and ref['pose'] is not None and row['estimate_valid'][car] and ref['estimate_valid'][car]:
                q = antenna(ref['pose'][4*ci:4*ci+4], config['models'][car])
                paired.append((error, math.dist(q, target['antenna_xyz_m'][:2])))
                differences.append(math.dist(xy, q))
        result['cars'][car] = dict(whole_run_s=horizon, finite_s=finite_s, valid_s=valid_s,
            no_publication_s=no_publication_s, failure_s=failure_s, invalid_or_no_publication_s=horizon-valid_s,
            antenna_xy_rmse_all_finite_m=rmse(errors), base_xy_rmse_all_finite_m=rmse(base_errors),
            antenna_xy_rmse_valid_m=rmse(valid_errors), paired_valid_s=len(paired),
            paired_delta_rmse_m=None if not paired else rmse([a for a,b in paired])-rmse([b for a,b in paired]),
            paired_antenna_displacement_rms_m=rmse(differences),
            post_fault_rmse_m=rmse(recovery_errors), post_fault_finite_s=len(recovery_errors),
            paired_nominal_post_fault_displacement_rms_m=rmse(nominal_tail),
            paired_nominal_post_fault_common_valid_s=len(nominal_tail))
    for monitor in ('B1', 'B2'):
        result['monitor'][monitor] = {}
        for declaration in ('local', 'network'):
            result['monitor'][monitor][declaration] = {}
            for ci, car in enumerate(CARS):
                by_al = {}
                for al in (.10, .05, .20):
                    sums = dict(available_s=0, unknown_s=0, failure_s=0, alarm_s=0, computable_s=0,
                        overlimit_error_known_s=0, overlimit_no_alarm_s=0, overlimit_available_no_alarm_s=0,
                        overlimit_unknown_s=0, unknown_error_s=0, unprotected_or_unknown_error_s=0)
                    for t in range(horizon):
                        epoch = origin+t*10**9
                        row = rows.get(epoch)
                        dec = None if row is None else row.get('monitor', {}).get(monitor, {}).get(declaration)
                        if dec is not None and declaration == 'local':
                            dec = dec.get(car)
                        dec = dec or dict(status='unknown', alarm=False, available=False)
                        status = dec['status']
                        if status not in ('available', 'alarm', 'unknown', 'failure'):
                            raise ValueError('Invalid declaration status')
                        if bool(dec['alarm']) != (status == 'alarm') or bool(dec['available']) != (status == 'available'):
                            raise ValueError('Inconsistent declaration')
                        sums['available_s'] += status == 'available'
                        sums['unknown_s'] += status == 'unknown'
                        sums['failure_s'] += status == 'failure'
                        sums['alarm_s'] += status == 'alarm'
                        sums['computable_s'] += status in ('available', 'alarm')
                        p = None if row is None else row.get('pose')
                        if p is None or not all(math.isfinite(v) for v in p):
                            sums['unknown_error_s'] += 1
                            sums['unprotected_or_unknown_error_s'] += 1
                            continue
                        error = math.dist(antenna(p[4*ci:4*ci+4], config['models'][car]), truth[epoch]['cars'][car]['antenna_xyz_m'][:2])
                        over = error > al
                        sums['overlimit_error_known_s'] += over
                        sums['overlimit_no_alarm_s'] += over and not dec['alarm']
                        sums['overlimit_available_no_alarm_s'] += over and dec['available'] and not dec['alarm']
                        sums['overlimit_unknown_s'] += over and status in ('unknown', 'failure')
                        sums['unprotected_or_unknown_error_s'] += over and not dec['alarm']
                    sums['normal_alarm_occupancy_fraction'] = (sums['alarm_s']/horizon
                        if labels['fault'] is None and sums['computable_s'] == horizon else None)
                    by_al[str(al)] = sums
                result['monitor'][monitor][declaration][car] = by_al
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', required=True, type=Path)
    p.add_argument('--input', required=True, type=Path)
    p.add_argument('--reference-run', type=Path)
    p.add_argument('--nominal-run', type=Path)
    p.add_argument('--nominal-input', type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    if a.output.exists():
        raise ValueError('Refuse overwrite')
    dump(a.output, evaluate(a.run, a.input, a.reference_run, a.nominal_run, a.nominal_input))
    print(json.dumps(dict(status='DONE', development_only=True, output=str(a.output))))
