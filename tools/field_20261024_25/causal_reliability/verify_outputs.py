#!/usr/bin/env python3
"""Independent archived row audit. Does not import online engine or generator.

Reconstructs peer geometry, gain, gate transitions, caps, Joseph covariance and
held output. Reads every event/state/estimate and recomputes per-car metrics.
"""
import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import numpy as np
from io_utils import dump,gzread,sha,utc

CARS=("car1","car2")
GATED={"gate_only","gate_cap","gate_cap_shadow"}
NONFEEDBACK={"shadow_only","gate_cap_shadow"}


def require(condition,message):
    if not condition:raise ValueError(message)


def close(a,b,message,atol=2e-10):
    if not np.allclose(a,b,rtol=2e-10,atol=atol):raise ValueError(message)


def wrapped(angle):return math.atan2(math.sin(angle),math.cos(angle))


def state_plus(x,delta):
    result=np.array(x)+np.array(delta);result[2]=wrapped(result[2]);result[5]=wrapped(result[5]);return result


def covariance(value):
    P=np.asarray(value,dtype=float)
    require(P.shape==(6,6) and np.isfinite(P).all(),"nonfinite/wrong covariance")
    close(P,P.T,"asymmetric covariance")
    require(float(np.linalg.eigvalsh(P)[0])>=-1e-9,"non-PSD covariance")
    return P


def antenna(state,twist,dt,cc):
    vx,vy,w=twist;a=w*dt
    if abs(a)<1e-8:travel=np.array([vx*dt-vy*w*dt*dt/2,vy*dt+vx*w*dt*dt/2])
    else:travel=np.array([(vx*math.sin(a)+vy*(math.cos(a)-1))/w,(vx*(1-math.cos(a))+vy*math.sin(a))/w])
    lever=cc.get("antenna_body_xy_m",cc.get("antenna_body_xyz_m"))["value"][:2]
    rotated=np.array([[math.cos(a),-math.sin(a)],[math.sin(a),math.cos(a)]])@lever+travel
    yaw=state[2];offset=np.array([[math.cos(yaw),-math.sin(yaw)],[math.sin(yaw),math.cos(yaw)]])@rotated
    height=cc["antenna_height_m"]["value"] if "antenna_height_m" in cc else cc["base_height_m"]["value"]+cc["antenna_body_xyz_m"]["value"][2]
    point=np.r_[np.array(state[:2])+offset,height]
    J=np.zeros((3,3));J[:2,:2]=np.eye(2);J[:2,2]=[-offset[1],offset[0]]
    return point,J


def peer_geometry(x,stamp,anchors,twists,config):
    positions=[];jacobians=[]
    for i,car in enumerate(CARS):
        age=stamp-anchors[car];require(0<=age<=config["max_extrapolation_ns"],"peer used unsupported odom")
        point,jac=antenna(x[3*i:3*i+3],twists[car],age/1e9,config["vehicles"][car]);positions.append(point);jacobians.append(jac)
    delta=positions[0]-positions[1];expected=float(np.linalg.norm(delta));unit=delta/expected
    return expected,np.r_[unit@jacobians[0],-unit@jacobians[1]]


def gate_step(state,config,z):
    state=dict(state)
    if abs(z)>config["gate_z"]:
        state["bad"]+=1;state["good"]=0
        if state["bad"]>=config["quarantine_bad_count"]:state["closed"]=True
        accepted=False
    else:
        state["bad"]=0;state["good"]+=1
        if state["closed"] and state["good"]>=config["reopen_good_count"]:state["closed"]=False
        accepted=not state["closed"]
    return state,accepted


def audit_unit(path,protocol,expected_fingerprint):
    run=json.loads((path/"run.json").read_text());require(run["status"]=="DONE","unit not complete")
    require(run["fingerprint_sha256"]==expected_fingerprint,"unit fingerprint mismatch")
    for item in run["outputs"]:require(sha(path/item["relative_path"])==item["sha256"],"unit output hash changed: "+item["relative_path"])
    inputs=list(gzread(path/"inputs.jsonl.gz"));truth={(r["vehicle_id"],r["state_epoch_ns"]):r["pose"] for r in gzread(path/"truth.jsonl.gz")}
    serialized=json.dumps(inputs,sort_keys=True,allow_nan=False,separators=(",",":"))
    require(hashlib.sha256(serialized.encode()).hexdigest()==run["input_sha256"],"canonical input identity mismatch")
    origin=run["origin_epoch_ns"];policy=protocol["policy"];config=protocol["baseline_config"]
    gate={m:{c:dict(bad=0,good=0,closed=False) for c in CARS} for m in protocol["methods"]}
    offsets={m:np.zeros(6) for m in NONFEEDBACK};offset_time={m:None for m in NONFEEDBACK}
    event_iterator=iter(gzread(path/"events.jsonl.gz"));current=next(event_iterator,None)
    previous_cov={};previous_receive=-1;anchors={};twists={};last_peer={};seen={m:set() for m in protocol["methods"]};consumed_link={m:{} for m in protocol["methods"]};counts=Counter();failures=Counter();metrics={};recovery={}
    csv_stream=(path/"estimate.csv").open(newline="");estimates=iter(csv.DictReader(csv_stream));event_index=0
    try:
        for tick in gzread(path/"states.jsonl.gz"):
            publication=tick["publish_receive_epoch_ns"];require(type(publication) is int,"noninteger publication")
            while current is not None and current["admitted_at_publication_ns"]==publication:
                require(current["event_index"]==event_index,"event index gap/duplication")
                event=inputs[event_index];row=event["row"];receive=row["receive_epoch_ns"]
                require(type(receive) is int and type(row["header_epoch_ns"]) is int,"timestamps lost exact ns")
                require(previous_receive<=receive<=publication,"arrival order/future admission")
                previous_receive=receive;reference=current["methods"]["independent"]
                for method,item in current["methods"].items():
                    require(item["shadow_state"]==reference["feedback_state"],"shadow mean differs from independent at event")
                    require(item["shadow_covariance"]==reference["feedback_covariance"],"shadow covariance contaminated at event")
                    require(np.isfinite(item["feedback_state"]).all(),"nonfinite feedback state")
                    P=np.array(item["feedback_covariance"])
                    if previous_cov.get(method)!=item["feedback_covariance"]:covariance(P);previous_cov[method]=item["feedback_covariance"]
                    decision=item["decision"];status=decision["status"];counts[method+":"+status]+=1
                    identity=(event["kind"],row["vehicle_id"],row["source_file_sha256"],int(row["record_index"]),int(row.get("link_index") or 0))
                    duplicate=identity in seen[method];seen[method].add(identity)
                    if status=="duplicate_trace":require(duplicate,"duplicate trace without prior input")
                    if status in ("wall_updated","peer_updated","peer_output_only","peer_gate_rejected"):
                        require(not duplicate and event["kind"]=="range","range information added twice or from wrong type")
                        require(row["source"]=="raw" and str(row["primary_observation"]) in ("1","True"),"bridge added information")
                        require(row.get("pairing_status") not in ("ambiguous_header","paired_mismatch"),"ambiguous pair added information")
                        require(str(row["valid"]) in ("1","True") and math.isfinite(float(row["range_m"])) and float(row["range_m"])>0,"invalid range added information")
                        stamp=decision["measurement_epoch_ns"]
                        require(type(stamp) is int and 0<=receive-stamp<=config["max_measurement_latency_ns"],"future/stale measurement updated state")
                        car=row["vehicle_id"];require(row["tag_id"]==("node_1" if car=="car1" else "node_0"),"source tag identity mismatch")
                        is_peer=row["target_id"] in ("node_0","node_1")
                        involved=CARS if is_peer else (car,)
                        for c in involved:require(c in anchors and 0<=stamp-anchors[c]<=config["max_extrapolation_ns"],"unsupported range increased information")
                        if is_peer:require(car=="car1" and row["target_id"]=="node_0" and method not in ("independent","odom_only"),"reverse or independent peer increased information")
                        else:require(row["target_id"] in config["anchors_xyz_m"]["value"] and method!="odom_only","unknown wall increased information")
                        link=(car,row["target_id"])
                        if link in consumed_link[method]:require(stamp-consumed_link[method][link]>=config["min_range_spacing_ns"],"range exceeded fixed link rate")
                        consumed_link[method][link]=stamp
                    if status.startswith("numerical_"):failures[method+":"+status]+=1
                    if method in NONFEEDBACK:
                        require(item["feedback_state"]==reference["feedback_state"] and item["feedback_covariance"]==reference["feedback_covariance"],"peer feedback into nonfeedback engine")
                    d=decision.get("reliability")
                    if d is None:continue
                    require(event["kind"]=="range" and row["vehicle_id"]=="car1" and row["target_id"]=="node_0","policy applied to wrong direction/type")
                    require(row["source"]=="raw" and str(row["primary_observation"]) in ("1","True"),"policy used bridge/nonprimary")
                    stamp=decision["measurement_epoch_ns"]
                    if method in last_peer:require(stamp-last_peer[method]>=config["min_range_spacing_ns"],"gate exceeded shared link rate")
                    last_peer[method]=stamp
                    x=np.array(d["pre_feedback_state"]);prior=covariance(d["pre_feedback_covariance"])
                    predicted,H=peer_geometry(x,stamp,anchors,twists,config)
                    close(predicted,d["expected_range_m"],"peer geometric prediction mismatch")
                    close(H,d["H"],"six-dimensional peer Jacobian mismatch")
                    innovation=float(row["range_m"])-predicted;R=d["base_variance_m2"]
                    close(innovation,d["innovation_m"],"innovation mismatch");z=innovation/math.sqrt(float(H@prior@H+R))
                    close(z,d["z"],"innovation normalization mismatch")
                    require(d["gate_before"]==gate[method],"gate state leaked or changed off-stream")
                    if method in GATED:
                        gate[method][row["vehicle_id"]],accepted=gate_step(gate[method][row["vehicle_id"]],policy,z)
                    else:accepted=True
                    require(d["gate_after"]==gate[method] and bool(d["accepted"])==accepted,"gate transition/recovery mismatch")
                    if not accepted:
                        raw_gain=prior@H/float(H@prior@H+R)
                        close(raw_gain,d["raw_gain"],"rejected counterfactual gain mismatch")
                        close(state_plus(x,raw_gain*innovation),d["raw_proposal"],"rejected uncapped proposal missing")
                        J=np.eye(6)-np.outer(raw_gain,H)
                        close(J@prior@J.T+np.outer(raw_gain,raw_gain)*R,d["raw_proposal_covariance"],"rejected counterfactual covariance mismatch")
                        require(status=="peer_gate_rejected","rejected gate committed peer")
                        if method in NONFEEDBACK:offsets[method][:]=0
                        continue
                    effective=R/(min(1.,policy["huber_delta"]/max(abs(innovation)/math.sqrt(R),1e-12))) if method=="huber" else R
                    raw_gain=prior@H/float(H@prior@H+effective);gain=raw_gain.copy()
                    close(raw_gain,d["raw_gain"],"raw gain mismatch");close(effective,d["effective_variance_m2"],"Huber variance mismatch")
                    close(state_plus(x,raw_gain*innovation),d["raw_proposal"],"uncapped proposal missing/inconsistent")
                    for i,health in enumerate(d["health"]):
                        info=np.zeros((2,2))
                        for vector in health["wall_xy_jacobians"]:info+=np.outer(vector,vector)/config["weights"]["wall_sigma_m"]["value"]**2
                        minimum=float(np.linalg.eigvalsh(info)[0]);healthy=len(health["wall_xy_jacobians"])>=3 and minimum>=policy["healthy_information_min"]
                        close(minimum,health["information_min"],"health information mismatch")
                        cap=policy["healthy_shift_cap_m"] if healthy else policy["weak_shift_cap_m"]
                        close(cap,health["cap_m"],"health cap mismatch")
                        norm=float(np.linalg.norm(raw_gain[3*i:3*i+2]*innovation));scale=min(1.,cap/norm) if d["cap_enabled"] and norm>0 else 1.
                        close(scale,d["cap_scales"][i],"cap scale mismatch");gain[3*i:3*i+3]*=scale
                        if d["cap_enabled"]:require(d["actual_shift_xy_m"][i]<=cap+1e-10,"cap violated")
                        counts[method+":clip_"+CARS[i]]+=int(scale<1.)
                    close(gain,d["actual_gain"],"actual gain mismatch")
                    close(state_plus(x,gain*innovation),d["proposal"],"capped mean/yaw mismatch")
                    for K,field in ((raw_gain,"raw_proposal_covariance"),(gain,"proposal_covariance")):
                        J=np.eye(6)-np.outer(K,H);expected=J@prior@J.T+np.outer(K,K)*effective
                        close(expected,d[field],"Joseph covariance/gain inconsistency");covariance(d[field])
                    require(bool(d["committed"])==(method not in NONFEEDBACK),"commit semantics changed")
                    if method in NONFEEDBACK:
                        offsets[method]=np.array(d["proposal"])-x;offsets[method][2]=wrapped(offsets[method][2]);offsets[method][5]=wrapped(offsets[method][5]);offset_time[method]=receive
                    else:
                        close(item["feedback_state"],d["proposal"],"feedback mean not committed");close(item["feedback_covariance"],d["proposal_covariance"],"feedback covariance not committed")
                if event["kind"]=="odom" and reference["decision"]["status"] in ("initialized","odometry_predicted"):
                    car=row["vehicle_id"];anchors[car]=reference["decision"]["measurement_epoch_ns"];twists[car]=[float(row[k]) for k in ("linear_x","linear_y","angular_z")]
                event_index+=1;current=next(event_iterator,None)
            require(tick["input_events_consumed"]==event_index,"publication consumed count mismatch")
            require(current is None or current["admitted_at_publication_ns"]>publication,"future event journal ordering")
            tick_errors={}
            for method,item in tick["methods"].items():
                if method in NONFEEDBACK:
                    delta=offsets[method] if offset_time[method] is not None and 0<=publication-offset_time[method]<=policy["output_hold_ns"] else np.zeros(6)
                    close(item["output_delta"],delta,"held correction/expiry mismatch")
                else:delta=np.zeros(6)
                for i,car in enumerate(CARS):
                    state=item["vehicles"][car];pose=state["pose"];record=next(estimates)
                    require(record["method_id"]==method and record["vehicle_id"]==car and int(record["publish_receive_epoch_ns"])==publication,"estimate CSV identity mismatch")
                    require(record["z_m"]=="","unestimated z not empty")
                    if pose is None:
                        require(record["x_m"]=="" and record["valid"]=="0","null state became trusted/zero")
                    else:
                        expected=state_plus(item["feedback_state"],delta)[3*i:3*i+3]
                        close(pose,expected,"published output differs from feedback plus declared correction")
                        close([float(record[k]) for k in ("x_m","y_m","yaw_rad")],pose,"CSV pose differs from state record")
                        if np.any(delta[3*i:3*i+3]):require(state["covariance"] is None and record["covariance"]=="","held output falsely assigned calibrated covariance")
                    stamp=state.get("state_epoch_ns");seconds=((stamp if stamp is not None else publication)-origin)/1e9
                    phase=next((name for name,(start,end) in protocol["evaluation"]["phases"].items() if start<=seconds<end),None)
                    if phase is None:continue
                    stats=metrics.setdefault((method,car,phase),dict(n_states=0,errors=[],above=0));stats["n_states"]+=1;error=None
                    if state["valid"]:
                        require(stamp is not None and stamp<=publication and pose is not None,"invalid trusted state/time")
                        target=truth[(car,stamp)];error=math.hypot(pose[0]-target[0],pose[1]-target[1]);stats["errors"].append(error)
                        stats["above"]+=int(error>protocol["evaluation"]["exploratory_error_limit_m"])
                    tick_errors[method,car]=(stamp,error)
            for (method,car),(stamp,error) in tick_errors.items():
                base=tick_errors.get(("independent",car),(None,None))[1]
                if stamp is not None and stamp>=origin+int(protocol["fault_end_s"]*1e9):recovery.setdefault((method,car),{})[stamp]=None if error is None or base is None else error-base
            counts["publication_records"]+=1
        require(current is None and event_index==len(inputs),"unread/extra event rows")
        require(next(estimates,None) is None,"extra estimate CSV rows")
    finally:csv_stream.close()
    saved=json.loads((path/"metrics.json").read_text())
    require(len(saved)==len(metrics),"metric group count mismatch")
    for metric in saved:
        key=(metric["method"],metric["vehicle_id"],metric["phase"]);actual=metrics[key];errors=actual["errors"]
        require(metric["n_states"]==actual["n_states"] and metric["valid_states"]==len(errors) and metric["over_error_limit_rows"]==actual["above"],"metric counts mismatch")
        if errors:
            close(math.sqrt(sum(e*e for e in errors)/len(errors)),metric["xy_rmse_m"],"metric RMSE differs from actual state rows")
            close(max(errors),metric["xy_max_m"],"metric max differs from actual state rows")
        start=None;delay=None
        for stamp,excess in sorted(recovery.get(key[:2],{}).items()):
            if excess is None or excess>protocol["evaluation"]["recovery_threshold_excess_m"]:start=None;continue
            if start is None:start=stamp
            if (stamp-start)/1e9>=protocol["evaluation"]["recovery_dwell_s"]:delay=(start-origin)/1e9-protocol["fault_end_s"];break
        require(delay==metric["recovery_start_delay_s"],"recovery timing mismatch")
    return dict(run_id=run["run_id"],status="DONE",events_read=event_index,counts=dict(counts),failures=dict(failures),metric_rows_recomputed=len(saved))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--results",type=Path,required=True);parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args(argv);started=time.monotonic()
    try:
        if args.output.exists():raise FileExistsError(args.output)
        protocol=json.loads((args.results/"frozen_protocol.json").read_text());lock=json.loads((args.results/"source_lock.json").read_text())
        inventory=json.loads((args.results/"inventory.json").read_text());reports=[]
        for row in inventory:
            if row["status"]!="DONE":continue
            path=args.results/"runs"/row["id"];require(sha(path/"run.json")==row["run_json_sha256"],"inventory/run hash mismatch")
            reports.append(audit_unit(path,protocol,lock["fingerprint_sha256"]))
            print(row["id"],"READBACK_OK",flush=True)
        result=dict(schema_version=1,status="DONE",created_at_utc=utc(),elapsed_s=time.monotonic()-started,
            verifier_imports_online_estimator=False,verifier_imports_generator=False,verifier_imports_evaluator=False,
            fingerprint_sha256=lock["fingerprint_sha256"],runs=reports,inventory_status_counts=dict(Counter(row["status"] for row in inventory)),
            scope="all generated events, states, gate/recovery, gain/cap/covariance, CSV and per-car metrics; synthetic only")
        dump(args.output,result);return 0
    except Exception as error:print(type(error).__name__+": "+str(error),file=sys.stderr);return 1


if __name__=="__main__":sys.exit(main())
