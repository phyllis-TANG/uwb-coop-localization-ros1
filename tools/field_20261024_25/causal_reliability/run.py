#!/usr/bin/env python3
"""Bounded, fingerprinted SE(2) development comparison; --resume is explicit."""
import argparse
from collections import Counter
import copy
import csv
import json
import os
from pathlib import Path
import sys
import time

from engine import Candidate, METHODS, NONFEEDBACK
import model
from simulate import generate,plan
from evaluate import evaluate
from io_utils import DEFAULT_PROTOCOL,append,dump,environment_packages,git_state,gzread,gzwrite,output_hashes,provenance,sha,utc,verify_unit,verify_saved_root


def ensure_external(output):
    from io_utils import ROOT
    output=Path(output).resolve()
    if output.is_relative_to(ROOT):raise ValueError("large results must be outside Git checkout")
    if output==ROOT or ROOT.is_relative_to(output):raise ValueError("output may not contain the checkout")
    return output


def process(events,config,policy,origin,end,methods=METHODS,deadline=None):
    """The estimator receives only arrived normalized rows, config and policy."""
    if config["scope"]=="field" and any(e["row"]["experiment_id"] not in ("T08","T10","T12","T14") for e in events):
        raise ValueError("whole-bag holdout gate")
    engines={method:Candidate(method,config,policy) for method in methods}
    if len(events)>config["max_events"]:raise ValueError("event budget exceeded")
    events=sorted(events,key=lambda event:(int(event["row"]["receive_epoch_ns"]),int(event["row"]["record_index"]),int(event["row"].get("link_index") or 0)))
    pointer=0;ticks=list(range(origin,end+1,config["publish_period_ns"]))
    if not ticks or ticks[-1]!=end:ticks.append(end)
    costs={m:0. for m in methods}
    for tick in ticks:
        if deadline is not None and time.monotonic()>deadline:raise TimeoutError("registered computation deadline exceeded")
        bundles=[]
        while pointer<len(events) and int(events[pointer]["row"]["receive_epoch_ns"])<=tick:
            if pointer%64==0 and deadline is not None and time.monotonic()>deadline:raise TimeoutError("registered event computation deadline exceeded")
            event=events[pointer];details={}
            for method,engine in engines.items():
                before=time.perf_counter();decision=engine.process(event);costs[method]+=time.perf_counter()-before
                details[method]=dict(decision=decision,feedback_state=engine.engine.x.tolist(),feedback_covariance=engine.engine.P.tolist(),
                    shadow_state=engine.shadow.x.tolist(),shadow_covariance=engine.shadow.P.tolist())
            bundles.append(dict(event_index=pointer,admitted_at_publication_ns=tick,methods=details));pointer+=1
        states={m:e.state_record(tick) for m,e in engines.items()}
        yield dict(publish_receive_epoch_ns=tick,input_events_consumed=pointer,methods=states),bundles,dict(total=costs.copy(),core={m:e.core_seconds for m,e in engines.items()},shadow={m:e.shadow_seconds for m,e in engines.items()})


def run_unit(path,condition,protocol,lock,deadline):
    started=time.monotonic()
    events,truth,labels,origin,end,input_hash=generate(protocol,condition["scenario"],condition["role"],condition["seed"])
    path.mkdir(parents=True,exist_ok=False)
    run=dict(schema_version=1,run_id=condition["id"],role="A_synthetic_development",status="IN_PROGRESS",created_at_utc=utc(),
        **git_state(),condition=condition,fingerprint_sha256=lock["fingerprint_sha256"],input_sha256=input_hash,outputs=[],
        input_identity_algorithm="sha256 of sorted-key compact canonical JSON event array",origin_epoch_ns=origin,end_epoch_ns=end,
        field_accuracy_evaluation_performed=False,synthetic_truth_only=True)
    dump(path/"run.json",run)
    try:
        for name,rows in (("inputs.jsonl.gz",events),("truth.jsonl.gz",truth)):
            with gzwrite(path/name) as stream:
                for row in rows:append(stream,row)
        dump(path/"labels.json",labels)
        ticks=[];publications=0;event_count=0
        with gzwrite(path/"states.jsonl.gz") as state_stream,gzwrite(path/"events.jsonl.gz") as event_stream:
            for state,bundles,costs in process(events,protocol["baseline_config"],protocol["policy"],origin,end,protocol["methods"],min(deadline,started+protocol["budget"]["per_combination_timeout_s"])):
                append(state_stream,state);ticks.append(state);publications+=1
                for event in bundles:append(event_stream,event);event_count+=1
                if publications%100==0:
                    state_stream.flush();event_stream.flush();run.update(publications_completed=publications,events_completed=event_count)
                    dump(path/"run.json",run)
        core_costs=costs["core"];shadow_costs=costs["shadow"];costs=costs["total"]
        metrics=evaluate(ticks,truth,protocol,origin)
        for row in metrics:row.update(scenario=condition["scenario"],role=condition["role"],seed=condition["seed"],run_id=condition["id"])
        dump(path/"metrics.json",metrics);dump(path/"compute_cost.json",dict(method_process_seconds=costs,includes_private_shadow_work=True,
            method_core_seconds=core_costs,method_shadow_seconds=shadow_costs,
            note="per-event CPU wall duration; diagnostic harness serialization excluded; unoptimized private shadow timed separately"))
        with (path/"estimate.csv").open("x",newline="") as stream:
            columns=["experiment_id","method_id","vehicle_id","canonical_time_s","frame_id","x_m","y_m","z_m","yaw_rad","valid","diagnostic_id","source_version","config_version","reference_version","publish_receive_epoch_ns","state_epoch_ns","fallback_status","covariance","covariance_reason"]
            writer=csv.DictWriter(stream,fieldnames=columns);writer.writeheader()
            for index,tick in enumerate(ticks):
                for method,item in sorted(tick["methods"].items()):
                    for car,state in item["vehicles"].items():
                        pose=state["pose"]
                        writer.writerow(dict(experiment_id=condition["id"],method_id=method,vehicle_id=car,canonical_time_s=(tick["publish_receive_epoch_ns"]-origin)/1e9,
                            frame_id=state["frame_id"],x_m=pose[0] if pose else None,y_m=pose[1] if pose else None,z_m=None,yaw_rad=pose[2] if pose else None,
                            valid=int(state["valid"]),diagnostic_id=index,source_version=lock["fingerprint_sha256"],config_version=lock["protocol_sha256"],reference_version="generated_truth_evaluation_only",
                            publish_receive_epoch_ns=tick["publish_receive_epoch_ns"],state_epoch_ns=state.get("state_epoch_ns"),fallback_status=state["fallback_status"],
                            covariance=json.dumps(state["covariance"],allow_nan=False) if state["covariance"] is not None else None,covariance_reason=state.get("output_covariance_reason")))
        run.update(status="DONE",publications_completed=publications,events_completed=event_count)
    except (Exception,KeyboardInterrupt) as error:
        run.update(status="FAILED",error_type=type(error).__name__,error=str(error));raise
    finally:
        run.update(elapsed_s=time.monotonic()-started,finished_at_utc=utc(),outputs=output_hashes(path));dump(path/"run.json",run)
    return run


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True);parser.add_argument("--protocol",type=Path,default=DEFAULT_PROTOCOL)
    parser.add_argument("--resume",action="store_true");parser.add_argument("--smoke",action="store_true")
    parser.add_argument("--max-seconds",type=int,default=7200)
    args=parser.parse_args(argv);started=time.monotonic()
    try:
        if not 0<args.max_seconds<=21600:raise ValueError("six-hour maximum")
        for key in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS"):
            if os.environ.get(key)!="1":raise ValueError(key+" must be 1")
        output=ensure_external(args.output);protocol=json.loads(args.protocol.read_text());lock=provenance(args.protocol)
        if not set(protocol["methods"])==set(METHODS):raise ValueError("all preregistered comparison methods required")
        # UTC conversion must not depend on machine timezone.
        import calendar
        task_end=calendar.timegm(time.strptime(protocol["budget"]["task_start_utc"],"%Y-%m-%dT%H:%M:%SZ"))+protocol["budget"]["task_max_seconds"]
        remaining=task_end-time.time()
        if remaining<=0:raise TimeoutError("overall task wall budget already exhausted")
        deadline=started+min(args.max_seconds,protocol["budget"]["total_matrix_timeout_s"],remaining)
        if output.exists():
            if not args.resume:raise FileExistsError("first launch must use a new output path; use explicit matching --resume")
            if json.loads((output/"source_lock.json").read_text())!=lock:raise ValueError("resume source/config/dependency fingerprint mismatch; use a new version/output")
            if verify_saved_root(output)["smoke"]!=args.smoke:raise ValueError("resume smoke/matrix mode mismatch")
        else:
            if args.resume:raise FileNotFoundError("resume requires an existing output")
            output.mkdir(parents=True);dump(output/"source_lock.json",lock);dump(output/"frozen_protocol.json",protocol)
            dump(output/"run.json",dict(schema_version=1,status="IN_PROGRESS",role="A_causal_reliability",created_at_utc=utc(),**git_state(),smoke=args.smoke,
                fingerprint_sha256=lock["fingerprint_sha256"],argv=[sys.executable,__file__]+(list(argv) if argv is not None else sys.argv[1:]),python_packages=environment_packages()))
        planned=plan(protocol,[protocol["smoke_seed"]] if args.smoke else None)
        if args.smoke:planned=[row for row in planned if row["scenario"] in ("normal","weak_wall_correct_peer","peer_bias","coherent_fault") and row["role"]=="car1"]
        dump(output/"plan.json",planned);inventory=[];failures=Counter();budget_stop=False
        for condition in planned:
            if condition["duplicate_of"]:
                inventory.append(dict(**condition,status="DEDUPLICATED",reason="role invariant input; same seed, not another independent run"));continue
            path=output/"runs"/condition["id"]
            if time.monotonic()>deadline or budget_stop:
                inventory.append(dict(**condition,status="BLOCKED",reason="registered budget/failure limit reached"));continue
            try:
                if path.exists():
                    if not args.resume:raise FileExistsError("unexpected existing run")
                    *_,input_hash=generate(protocol,condition["scenario"],condition["role"],condition["seed"])
                    unit=verify_unit(path,lock["fingerprint_sha256"],input_hash)
                else:unit=run_unit(path,condition,protocol,lock,deadline)
                inventory.append(dict(**condition,status=unit["status"],elapsed_s=unit["elapsed_s"],input_sha256=unit["input_sha256"],run_json_sha256=sha(path/"run.json")))
                print(condition["id"],unit["status"],round(unit["elapsed_s"],3),flush=True)
            except (Exception,KeyboardInterrupt) as error:
                signature=type(error).__name__+":"+str(error);failures[signature]+=1
                inventory.append(dict(**condition,status="FAILED",error=signature))
                print(condition["id"],"FAILED",signature,flush=True)
                if failures[signature]>=protocol["budget"]["maximum_attempts_same_error"] or isinstance(error,KeyboardInterrupt):budget_stop=True
            dump(output/"inventory.json",inventory)
        dump(output/"inventory.json",inventory)
        run=json.loads((output/"run.json").read_text());counts=dict(Counter(row["status"] for row in inventory))
        run.update(status="DONE" if not any(key in counts for key in ("FAILED","BLOCKED")) else "FAILED",elapsed_s=time.monotonic()-started,finished_at_utc=utc(),counts=counts,
            resume_command=[sys.executable,__file__,"--output",str(output),"--protocol",str(args.protocol),"--resume"]+(["--smoke"] if args.smoke else []),outputs=output_hashes(output))
        dump(output/"run.json",run);print(json.dumps(dict(status=run["status"],counts=counts,elapsed_s=run["elapsed_s"])))
        return 0 if run["status"]=="DONE" else 1
    except (Exception,KeyboardInterrupt) as error:
        print(type(error).__name__+": "+str(error),file=sys.stderr);return 1


if __name__=="__main__":sys.exit(main())
