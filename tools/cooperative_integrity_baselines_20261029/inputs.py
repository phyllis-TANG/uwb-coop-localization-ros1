"""Only seed101, exact frozen generator and PR68's sole wall adapter, in RAM."""
import copy
import gzip
import hashlib
import io
import json
from binding import simulate
from common import ROOT, SPEC, canonical, digest, sha


def gzip_bytes(rows):
    stream = io.BytesIO()
    with gzip.GzipFile(fileobj=stream,filename='',mode='wb',mtime=0) as z:
        z.write(('\n'.join(canonical(row) for row in rows)+'\n').encode())
    return stream.getvalue()


def make(scenario):
    if scenario not in SPEC['scenarios_in_execution_order']: raise ValueError('Outside frozen three cases')
    base = 'nominal' if scenario == 'car1_common_wall_bias' else scenario
    config, events, truth, labels = simulate.make_case(101,base)
    modified = 0
    if scenario == 'car1_common_wall_bias':
        # Literal PR68 prepare.py adapter; verify every other scalar/metadata.
        original = copy.deepcopy(events)
        for row in events:
            if row['kind']=='uwb' and row['vehicle_id']=='car1' and 24_000_000_000 <= row['header_epoch_ns']-simulate.EPOCH_NS <38_000_000_000:
                for key in ('node_10','node_2','node_3','node_8'):row['value'][key] += .30; modified += 1
        assert modified == 1120
        for a,b in zip(original,events):
            target = a['kind']=='uwb' and a['vehicle_id']=='car1' and 24_000_000_000<=a['header_epoch_ns']-simulate.EPOCH_NS<38_000_000_000
            for key in a:
                if key != 'value': assert a[key] == b[key]
            for key,value in a['value'].items():
                if target and key in config['models']['car1']['anchors_xyz_m']:
                    assert abs(b['value'][key]-value-.30)<1e-15
                else: assert b['value'][key] == value
        del original
    encoded = gzip_bytes(events)
    config_bytes = (json.dumps(config,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
    input_index = json.loads((ROOT/'docs/field_tests/20261024_25/cooperative_peer_gate_probe_20261028/review/input_index.json').read_text())
    old = next(c for c in input_index['cases'] if c['seed']==101 and c['scenario']==scenario)
    actual = dict(events_gzip_sha256=hashlib.sha256(encoded).hexdigest(),
        canonical_events_sha256=digest(events), config_sha256=hashlib.sha256(config_bytes).hexdigest(),
        truth_canonical_sha256=digest(truth), event_count=len(events), modified_wall_scalars=modified,
        input_mode=SPEC['input_mode'], original_archive_readback=False,
        original_registered_files=old['files'],
        registered_event_bytes_equal=hashlib.sha256(encoded).hexdigest()==old['files']['events.jsonl.gz'],
        registered_config_bytes_equal=hashlib.sha256(config_bytes).hexdigest()==old['files']['config.json'],
        registered_truth_bytes_equal=hashlib.sha256(('\n'.join(canonical(r) for r in truth)+'\n').encode()).hexdigest()==old['files']['truth.jsonl'])
    # The original compressed event payload is unavailable: do not assert a
    # gzip hash proves scalar mismatch or equality. Record fresh payload SHA;
    # configuration/truth must be exact, then verify all saved estimates/bins.
    assert actual['registered_config_bytes_equal'] and actual['registered_truth_bytes_equal']
    return config, events, truth, actual
