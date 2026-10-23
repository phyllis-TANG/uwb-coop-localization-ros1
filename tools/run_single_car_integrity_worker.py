#!/usr/bin/env python3
"""Streaming estimator executable: config+sensors only, no truth or fault input."""
from __future__ import annotations
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import time
from single_car_integrity import IntegrityReplay
from single_car_sequential_replay import Event, bag_events


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--sensors',type=Path)
    group.add_argument('--bag',type=Path)
    parser.add_argument('--thresholds',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    config=json.loads(args.config.read_text())
    allowed={'model','replay','lag_s','max_nfev','max_sensor_samples','monitor_rules'}
    if set(config)!=allowed:
        raise ValueError('Estimator config must not contain evaluation data or unknown fields')
    thresholds=json.loads(args.thresholds.read_text())['values'] if args.thresholds else None
    args.output.mkdir(parents=True,exist_ok=False)
    started=time.perf_counter(); diagnostics={}
    with (args.output/'updates.jsonl').open('x') as stream:
        def sink(row):
            row['actual_output_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
            stream.write(json.dumps(row,sort_keys=True,allow_nan=False)+'\n'); stream.flush()
        replay=IntegrityReplay(config,sink,thresholds)
        if args.bag:
            for event in bag_events(args.bag,diagnostics):
                replay.ingest(event)
        else:
            with args.sensors.open() as sensor_stream:
                for line in sensor_stream:
                    payload=json.loads(line)
                    if set(payload)!={'received_s','kind','header_s','value'}:
                        raise ValueError('Unexpected sensor fields: no truth/labels allowed')
                    replay.ingest(Event(**payload))
        replay.finish()
    result=dict(wall_s=time.perf_counter()-started,output_count=replay.monitored_outputs,
                counters=dict(replay.full.counters),sensor_buffer_peaks=replay.full.sensor_peaks,
                peak_states=replay.full.graph.peak_solve_states,
                marginalizations=replay.full.graph.marginalizations,
                input_diagnostics=diagnostics,config_sha256=hashlib.sha256(args.config.read_bytes()).hexdigest())
    (args.output/'worker_summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    main()
