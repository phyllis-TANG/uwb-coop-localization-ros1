"""Authorized finite mechanism inputs; PR88 generation equations unchanged."""
import argparse
import copy
import json
from pathlib import Path
from support import CONDITIONS, MOTIONS, dump, new_output, protocol, sha, sources, write_lines
from bindings import clone, generator


def specification(p, partition, seed, motion):
    if seed not in p['partitions'][partition]['seeds'] or motion not in MOTIONS:
        raise ValueError('Outside frozen seed/motion partition')
    spec = copy.deepcopy(p['generation'][motion])
    spec['seed'] = seed
    return spec


def make(p, partition, seed, motion, condition):
    if condition not in p['partitions'][partition]['conditions']:
        raise ValueError('Outside frozen condition list')
    spec = specification(p, partition, seed, motion)
    # Validate all PR88 checks on the same geometry at its original 32s scale.
    # Only the authorized longer duration and seed guard differ in this adapter.
    def validate(value):
        if value != spec or value['duration_s'] != 96:
            raise ValueError('Generation spec differs from frozen protocol')
        check = copy.deepcopy(value)
        check['seed'] = 7
        check['duration_s'] = 32
        for car in check['trajectories']:
            check['trajectories'][car] = [q for q in check['trajectories'][car] if q['t_s'] <= 32]
        check['fault_start_s'] = 6
        generator.validate(check)
    generate = clone(generator.make, validate=validate, sources=sources)
    config, events, truth, labels = generate(spec, condition)
    for row in events:
        row['case_id'] = f'synthetic_mechanism_seed{seed}_{motion}'
    labels.update(partition=partition, motion=motion, development_only=partition=='development',
        independent_test=partition=='test', independent_validation=False,
        independent_validation_scope='small controlled-model test runs only; not field validation or integrity certification')
    return config, events, truth, labels, spec


def save(p, partition, seed, motion, condition, output):
    config, events, truth, labels, spec = make(p, partition, seed, motion, condition)
    root = new_output(output)
    dump(root/'config.json', config)
    dump(root/'labels.json', labels)
    dump(root/'generation.json', spec)
    write_lines(root/'events.jsonl.gz', events)
    write_lines(root/'truth.jsonl.gz', truth)
    manifest = dict(partition=partition, seed=seed, motion=motion, condition=condition,
        event_count=len(events), truth_count=len(truth), source_sha256=sources(),
        files={q.name:sha(q) for q in root.iterdir()}, estimator_inputs=['config.json','events.jsonl.gz'],
        truth_and_labels_are_estimator_inputs=False)
    dump(root/'manifest.json', manifest)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', required=True, type=Path)
    parser.add_argument('--partition', required=True, choices=('development','calibration','test'))
    parser.add_argument('--seed', required=True, type=int)
    parser.add_argument('--motion', required=True, choices=MOTIONS)
    parser.add_argument('--condition', required=True, choices=CONDITIONS)
    parser.add_argument('--output', required=True, type=Path)
    a = parser.parse_args()
    m = save(protocol(a.protocol), a.partition, a.seed, a.motion, a.condition, a.output)
    print(json.dumps({k:m[k] for k in ('partition','seed','motion','condition','event_count')}))
