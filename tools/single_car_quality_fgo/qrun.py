#!/usr/bin/env python3
"""Single Q0/Q1/Q2/Q3 run; immutable ledger then physically flushed output time."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import sys
import time
from bridge import base_replay
from qconfig import validate
from qfrontend import Pipeline
from qio import append,clean,dump,external_path,git_state,gzip_writer,outputs,packages,read_jsonl,sha,sources,utc

COLUMNS=[k for k in base_replay.COLUMNS if k not in ('estimated_available_epoch_ns','publication_delay_s','estimated_worker_queue_s')]+['q_group','publication_id','actual_available_time_source']


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--events-jsonl',type=Path,required=True);p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--anchor-monotonic-ns',type=int);p.add_argument('--anchor-host-epoch-ns',type=int);p.add_argument('--max-seconds',type=float,default=120.);a=p.parse_args(argv)
    started=time.monotonic();meta=None
    try:
        config=json.loads(a.config.read_text());validate(config);events=list(read_jsonl(a.events_jsonl));base_replay.validate_events(events,config['base']);root=external_path(a.output);root.mkdir(parents=True,exist_ok=False)
        origin=events[0]['receive_epoch_ns'];lock=sources();anchor=a.anchor_monotonic_ns if a.anchor_monotonic_ns is not None else time.monotonic_ns();hostanchor=a.anchor_host_epoch_ns if a.anchor_host_epoch_ns is not None else time.time_ns()
        meta=dict(schema_version=1,interface_version='quality_fgo_v1',status='IN_PROGRESS',created_at_utc=utc(),**git_state(),group=config['group'],source_sha256=lock,config_sha256=sha(a.config),input_sha256=sha(a.events_jsonl),
            command_argv=[sys.executable,__file__]+(list(argv) if argv is not None else sys.argv[1:]),environment=dict(python=sys.version,packages=packages()),origin_receive_epoch_ns=origin,
            host_anchor_monotonic_ns=anchor,host_anchor_epoch_ns=hostanchor,timing_mode='paced_actual' if config['timing']['paced'] else 'accelerated_development_virtual',publications=0,field_accuracy_evaluated=False)
        dump(root/'run.json',meta);dump(root/'config.json',config);state_counts=Counter();reason_counts=Counter();pose_status=Counter()
        with gzip_writer(root/'graphs.jsonl.gz') as graphs,gzip_writer(root/'quality_ledger.jsonl.gz') as ledger,gzip_writer(root/'publications.jsonl.gz') as pubs,gzip_writer(root/'availability.jsonl.gz') as availability,gzip_writer(root/'input_decisions.jsonl.gz') as inputs,(root/'published.csv').open('x',newline='') as csvstream:
            writer=csv.DictWriter(csvstream,fieldnames=COLUMNS,lineterminator='\n');writer.writeheader()
            def ledger_sink(row):
                state_counts[row['policy']['state']]+=1;reason_counts[row['policy']['reason']]+=1;append(ledger,row)
            def publication_sink(output):
                before=time.monotonic_ns();row=output['row'];pose_status[row['status']]+=1
                pre=output.pop('available_receive_epoch_ns');output['compute_ready_receive_epoch_ns']=pre;output['actual_available_receive_epoch_ns']=None;output['availability_record_required']=True
                append(pubs,output)
                r=base_replay.csv_row(row,config['base']['arm']);r={k:r.get(k) for k in COLUMNS};r.update(q_group=config['group'],publication_id=output['publication_id'],actual_available_time_source='join availability.jsonl.gz by publication_id');writer.writerow(r)
                for stream in (graphs,ledger,pubs,inputs,csvstream):stream.flush()
                mono=time.monotonic_ns();host=time.time_ns();extra=mono-before
                available=origin+mono-anchor if config['timing']['paced'] else pre+extra
                actual=dict(record_type='actual_output_available',publication_id=output['publication_id'],group=config['group'],state_epoch_ns=output['state_epoch_ns'],availability_cutoff_epoch_ns=output['availability_cutoff_epoch_ns'],available_receive_epoch_ns=available,
                    data_flushed_host_monotonic_ns=mono,data_flushed_host_epoch_ns=host,host_anchor_monotonic_ns=anchor,host_anchor_epoch_ns=hostanchor,
                    timing_mode=output['timing_mode'],complete_processor_wall_s=output['measured_complete_processor_wall_s']+extra/1e9,
                    actual_release_delay_s=(available-output['state_epoch_ns'])/1e9,post_cutoff_total_delay_s=max(0.,(available-output['availability_cutoff_epoch_ns'])/1e9),queue_and_scheduling_not_separated=True,
                    interpretation='paced: measured host elapsed mapped to declared receive origin; accelerated: virtual FIFO plus measured compute, not actual reception latency',includes_graph_ledger_pose_data_flush=True)
                append(availability,actual);availability.flush();meta['publications']+=1
                if meta['publications']%10==0:dump(root/'run.json',meta)
                return actual
            pipeline=Pipeline(config,origin,graph_sink=lambda r:append(graphs,r),ledger_sink=ledger_sink,publication_sink=publication_sink,anchor_mono_ns=anchor,anchor_epoch_ns=hostanchor)
            for index,event in enumerate(events):
                if time.monotonic()-started>a.max_seconds:raise TimeoutError('bounded Q replay wall clock')
                pipeline.ingest(event);flags=[];safe=clean(event,flags=flags);append(inputs,dict(event_index=index,input=safe,nonfinite_input_fields=flags))
            pipeline.finish()
        roles={'main':pipeline.main,**pipeline.shadows}
        dump(root/'summary.json',dict(group=config['group'],publications=pipeline.publications,pose_status=dict(pose_status),quality_state_counts=dict(state_counts),quality_reason_counts=dict(reason_counts),
            role_summaries={k:dict(peak_solve_keyframes=f.graph.peak_solve_states,peak_transient_keyframes=f.graph.peak_transient_states,marginalizations=f.graph.marginalizations,source_buffer_peaks=f.sensor_peaks,
                final_prior=dict(point=f.graph.prior.point.tolist(),matrix=f.graph.prior.matrix.tolist(),offset=f.graph.prior.offset.tolist())) for k,f in roles.items()},
            quality_enabled=config['quality_enabled'],shadow_graphs=len(pipeline.shadows),history_rollback=False,bias_locking=False,field_accuracy_evaluated=False))
        if lock!=sources():raise ValueError('source fingerprint changed during run')
        meta.update(status='DONE',finished_at_utc=utc(),elapsed_s=time.monotonic()-started,outputs=outputs(root));dump(root/'run.json',meta)
        print(json.dumps(dict(status='DONE',group=config['group'],publications=pipeline.publications,elapsed_s=meta['elapsed_s'])));return 0
    except (Exception,KeyboardInterrupt) as error:
        if meta is not None:meta.update(status='FAILED',error=type(error).__name__+': '+str(error),elapsed_s=time.monotonic()-started,outputs=outputs(a.output));dump(a.output/'run.json',meta)
        print(type(error).__name__+': '+str(error),file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
