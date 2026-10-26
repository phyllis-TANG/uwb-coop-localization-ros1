"""Generate normalized events first; truth/labels stay outside online API."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

sys.path.append(str(Path(__file__).resolve().parents[1]/"causal_baselines"))
import model
import synthetic_validation as legacy


def canonical_json(value):
    return json.dumps(value,sort_keys=True,allow_nan=False,separators=(",",":"))


def plan(protocol,seeds=None):
    rows=[]
    for scenario in protocol["scenarios"]:
        for role in protocol["roles"]:
            effective="car1" if scenario in protocol["role_invariant_scenarios"] else role
            for seed in seeds if seeds is not None else protocol["development_seeds"]:
                identifier=f"{scenario}__{role}__{seed}"
                canonical=f"{scenario}__{effective}__{seed}"
                rows.append(dict(id=identifier,scenario=scenario,role=role,seed=seed,canonical_id=canonical,
                    duplicate_of=canonical if canonical!=identifier else None))
    if len(rows)>protocol["maximum_planned_combinations"]:raise ValueError("plan exceeds frozen combination budget")
    return rows


def generate(protocol,scenario,role,seed):
    if scenario not in protocol["scenarios"] or role not in model.CARS:raise ValueError("unknown synthetic condition")
    config=copy.deepcopy(protocol["baseline_config"])
    config["validation_protocol"]=dict(protocol["noise"],duration_s=protocol["duration_s"],odom_dt_ns=protocol["odom_dt_ns"])
    events,truth,origin,end=legacy.fixture(config,seed,"noisy_nominal")
    start,finish=protocol["fault_start_s"],protocol["fault_end_s"]
    f=protocol["faults"];out=[]
    for event in events:
        row=event["row"];seconds=(int(row["header_epoch_ns"])-origin)/1e9;active=start<=seconds<finish
        own=row["vehicle_id"]
        if event["kind"]=="odom":
            if scenario=="async_missing" and own==role and f["odom_dropout_interval_s"][0]<=seconds<f["odom_dropout_interval_s"][1]:continue
            if scenario in ("weak_wall_correct_peer","weak_wall_peer_bias") and own==role:
                accumulated=max(0,min(seconds,finish)-start)
                row["position_x"]+=f["weak_odom_local_drift_m_s"]*accumulated
                yaw=2*np.arctan2(row["orientation_z"],row["orientation_w"])+f["weak_odom_yaw_drift_rad_s"]*accumulated
                row["orientation_z"],row["orientation_w"]=float(np.sin(yaw/2)),float(np.cos(yaw/2))
        else:
            peer=row["target_id"] not in model.WALLS
            if active and scenario in ("weak_wall_correct_peer","weak_wall_peer_bias") and own==role and not peer and row["target_id"]!=f["weak_wall_keep_target"]:continue
            if peer and own=="car1" and active:
                if scenario in ("peer_bias","weak_wall_peer_bias"):row["range_m"]+=f["peer_bias_m"]
                elif scenario=="pulse" and f["pulse_interval_s"][0]<=seconds<f["pulse_interval_s"][1]:row["range_m"]+=f["pulse_m"]
                elif scenario=="ramp":row["range_m"]+=f["ramp_max_m"]*(seconds-start)/(finish-start)
                if scenario=="async_missing" and int(row["record_index"])%f["delay_every_record_mod"]==0:row["receive_epoch_ns"]+=f["extra_peer_delay_ns"]
            if active and scenario=="coherent_fault":
                positions={}
                for car in model.CARS:
                    positions[car]=model.antenna_at(truth(car,int(row["header_epoch_ns"])),np.zeros(3),0,config["vehicles"][car])[0]
                altered={car:value.copy() for car,value in positions.items()};altered[role][:2]+=f["coherent_displacement_room_xy_m"]
                if peer:
                    old=np.linalg.norm(positions["car1"]-positions["car2"]);new=np.linalg.norm(altered["car1"]-altered["car2"])
                else:
                    anchor=np.array(config["anchors_xyz_m"]["value"][row["target_id"]])
                    old=np.linalg.norm(positions[own]-anchor);new=np.linalg.norm(altered[own]-anchor)
                row["range_m"]+=float(new-old)
        out.append(event)
    def key(event):
        row=event["row"];return int(row["receive_epoch_ns"]),int(row["record_index"]),int(row.get("link_index") or 0)
    out.sort(key=key)
    truth_rows=[]
    for k in range(int(protocol["duration_s"]*1e9)//protocol["odom_dt_ns"]+1):
        stamp=origin+k*protocol["odom_dt_ns"]
        for car in model.CARS:
            pose=truth(car,stamp)
            truth_rows.append(dict(vehicle_id=car,state_epoch_ns=stamp,pose=pose.tolist()))
    labels=dict(scenario=scenario,role=role,fault_interval_s=[start,finish],injection=f,
                note="evaluation only; never passed to Candidate or PeerPolicy")
    identity=hashlib.sha256(canonical_json(out).encode()).hexdigest()
    return out,truth_rows,labels,origin,end,identity
