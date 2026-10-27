"""Field-input audit adapted from PR52's independent verifier.

No online estimator, generator, evaluator or bridge imports. Every archived
policy proposal is recomputed. Existing PR52 math helpers are independent of
its estimator. No truth file or positional error is created/read.
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

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"causal_reliability"))
from verify_outputs import require, close, wrapped, state_plus, covariance, peer_geometry, gate_step, CARS, GATED, NONFEEDBACK
from io_utils import gzread,sha


def write(path,value):
    with Path(path).open("x") as f:
        json.dump(value,f,ensure_ascii=False,allow_nan=False,indent=2);f.write("\n")


def verify_outputs(root,run):
    require(run["status"]=="DONE_EXPLORATORY_ONLY","incomplete run")
    for rel,expected in run["outputs"].items():
        p=Path(rel)
        require(not p.is_absolute() and ".." not in p.parts,"unsafe archive path")
        require(sha(root/p)==expected,"modified output: "+rel)

def audit_profile(path,protocol,run,inputs):
    origin=run["origin_epoch_ns"];policy=protocol["policy"];config=protocol["baseline_config"]
    gate={m:{c:dict(bad=0,good=0,closed=False) for c in CARS} for m in protocol["methods"]}
    offsets={m:np.zeros(6) for m in NONFEEDBACK};offset_time={m:None for m in NONFEEDBACK}
    event_iterator=iter(gzread(path/"events.jsonl.gz"));current=next(event_iterator,None)
    previous_cov={};previous_receive=-1;anchors={};twists={};own_odom={};last_peer={};seen={m:set() for m in protocol["methods"]};consumed_link={m:{} for m in protocol["methods"]};counts=Counter();failures=Counter()
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
                    car=row["vehicle_id"];own_odom[car]=row;anchors[car]=reference["decision"]["measurement_epoch_ns"];twists[car]=[float(row[k]) for k in ("linear_x","linear_y","angular_z")]
                event_index+=1;current=next(event_iterator,None)
            require(tick["input_events_consumed"]==event_index,"publication consumed count mismatch")
            require(current is None or current["admitted_at_publication_ns"]>publication,"future event journal ordering")
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
                        if np.any(delta[3*i:3*i+3]):require(state["covariance"] is None and record["pose_covariance"]=="","held output falsely assigned calibrated covariance")
                    if pose is not None:
                        require(int(record['valid']) == int(state['valid']), 'CSV availability differs')
                        for field in ('source_record_index','source_header_epoch_ns','source_receive_epoch_ns','state_epoch_ns'):
                            require(int(record[field]) == state[field], 'CSV provenance differs')
                        if state['covariance'] is None:
                            require(record['pose_covariance'] == '', 'null output covariance hidden')
                        else:
                            close(json.loads(record['pose_covariance']), state['covariance'], 'CSV covariance differs')
                        require(state["source_record_index"] == own_odom[car]["record_index"], "not latest accepted own odom")
                        require(state["source_header_epoch_ns"] == own_odom[car]["header_epoch_ns"], "header provenance changed")
                        require(state["source_receive_epoch_ns"] == own_odom[car]["receive_epoch_ns"], "receive provenance changed")
                        require(state["state_epoch_ns"] == anchors[car] <= publication, "future/wrong state epoch")
                        if state["valid"]:require(0 <= publication-anchors[car] <= config["max_publish_age_ns"], "trusted stale output")
            counts["publication_records"]+=1
        require(current is None and event_index==len(inputs),"unread/extra event rows")
        require(next(estimates,None) is None,"extra estimate CSV rows")
    finally:csv_stream.close()
    return dict(status="DONE",events_read=event_index,counts=dict(counts),failures=dict(failures),field_accuracy_evaluated=False)


def baseline_parity(directory, previous):
    """Compare all base rows to registered PR53; metadata/version fields differ."""
    fields = ('valid','fallback_status','frame_id','state_epoch_ns','source_header_epoch_ns',
              'source_receive_epoch_ns','source_record_index','receipt_age_ns')
    key = lambda r:(r['method_id'],r['vehicle_id'],r['publish_receive_epoch_ns'])
    with (previous/'estimate.csv').open() as f: old = {key(r):r for r in csv.DictReader(f)}
    count = 0; maximum = 0.0
    with (directory/'estimate.csv').open() as f:
        for row in csv.DictReader(f):
            if row['method_id'] not in ('odom_only','independent','joint'): continue
            before = old.pop(key(row))
            require(all(row[k] == before[k] for k in fields), 'PR53 availability/provenance/status regression')
            for k in ('x_m','y_m','yaw_rad'):
                require(bool(row[k]) == bool(before[k]), 'PR53 null state regression')
                if row[k]:
                    difference = abs(float(row[k])-float(before[k])); maximum=max(maximum,difference)
                    close(float(row[k]),float(before[k]),'PR53 pose regression')
            a,b=row['pose_covariance'],before['pose_covariance']
            require(bool(a)==bool(b), 'PR53 covariance null regression')
            if a:close(json.loads(a),json.loads(b),'PR53 covariance regression')
            count += 1
    require(not old, 'missing PR53 rows')
    return dict(rows=count,maximum_pose_component_difference=maximum,all_base_rows_equal_within_2e_10=True)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results',type=Path,required=True)
    p.add_argument('--pr53-results',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args(argv);start=time.monotonic()
    require(not args.output.exists(),'audit output already exists')
    root=args.results;run=json.loads((root/'run.json').read_text())
    verify_outputs(root,run)
    protocol=json.loads((root/'protocol.json').read_text())
    require(sha(args.pr53_results/'run.json')==protocol['pr53_run_sha256'],'unregistered PR53 evidence')
    previous=json.loads((args.pr53_results/'run.json').read_text())
    for rel,digest in previous['outputs'].items():require(sha(args.pr53_results/rel)==digest,'modified PR53 output')
    inputs=list(gzread(root/'inputs.jsonl.gz'))
    serialized=json.dumps(inputs,sort_keys=True,allow_nan=False,separators=(',',':'))
    require(hashlib.sha256(serialized.encode()).hexdigest()==run['canonical_input_sha256'],'input canonical identity changed')
    require(all(e['row']['experiment_id']=='T10' and e['row']['source_file_sha256']==protocol['bag_sha256'] for e in inputs),'non-T10 input')
    reports={}
    for profile in protocol['profiles']:
        name=profile['id'];directory=root/name
        config=json.loads((directory/'config.json').read_text())
        require(config==json.loads((args.pr53_results/name/'config.json').read_text()),'PR53 numerical configuration changed')
        report=audit_profile(directory,{**protocol,'baseline_config':config},run,inputs)
        report['pr53_baseline_parity']=baseline_parity(directory,args.pr53_results/name)
        reports[name]=report
        print(name,'INDEPENDENT_AUDIT_OK',flush=True)
    result=dict(status='DONE',elapsed_s=time.monotonic()-start,profiles=reports,
        total_input_events_read=sum(r['events_read'] for r in reports.values()),
        total_method_decisions=sum(sum(v for k,v in r['counts'].items() if k!='publication_records' and ':clip_' not in k) for r in reports.values()),
        verifier_imports_online_estimator=False,field_accuracy_evaluated=False)
    write(args.output,result)


if __name__ == '__main__':main()
