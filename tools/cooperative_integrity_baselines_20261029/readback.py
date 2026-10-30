#!/usr/bin/env python3
"""New readout version for saved results; never calls estimator or modifies runs."""
import argparse
import csv
from collections import Counter
import gzip
import json
from pathlib import Path
from common import SPEC,new_output,write_json,csv_write,sha
from inputs import make
from independent import verify,verify_input_prefix
from evaluate import evaluate


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--runs',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    out=new_output(a.output);records=[]
    for scenario in SPEC['scenarios_in_execution_order']:
        case=a.runs/scenario;dest=out/scenario;dest.mkdir()
        with gzip.open(case/'monitor.jsonl.gz','rt') as f:rows=[json.loads(line) for line in f]
        config,events,truth,receipt=make(scenario)
        assert receipt['canonical_events_sha256']==json.loads((case/'INPUT.json').read_text())['canonical_events_sha256']
        result=evaluate(scenario,rows,truth,config)
        for name,values in result.items():
            if values:csv_write(dest/(name+'.csv'),values)
        for name in ('metrics','trajectory','declarations','ss'):
            with (dest/(name+'.csv')).open(newline='') as f:new=list(csv.DictReader(f))
            with (case/(name+'.csv')).open(newline='') as f:old=list(csv.DictReader(f))
            # Canonical JSON reorders dictionary keys, hence profile row order.
            # Require exact values and multiplicities, not artificial byte equality.
            assert Counter(tuple(sorted(r.items())) for r in new)==Counter(tuple(sorted(r.items())) for r in old)
        proof=verify(rows,config);proof['raw_prefix']=verify_input_prefix(rows,events,config)
        write_json(dest/'CHECKS.json',proof)
        records.append(dict(scenario=scenario,status='DONE',input_canonical_sha256=receipt['canonical_events_sha256'],
            monitor_sha256=sha(case/'monitor.jsonl.gz'),recomputed_csv_values_and_multiplicities_exact=('metrics','trajectory','declarations','ss'),
            episodes_revision='track pre-existing alarm onset, not fresh delay at error episode start',checks=proof))
        print(scenario,'READBACK PASS',flush=True)
    write_json(out/'INDEX.json',dict(status='PASS',estimator_reruns=0,cases=records))
if __name__=='__main__':main()
