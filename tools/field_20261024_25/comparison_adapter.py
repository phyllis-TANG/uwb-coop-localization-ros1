#!/usr/bin/env python3
"""Causal observation interface and synthetic-only fixed comparison prototype.

No field localization CLI is exposed. The numerical fixture validates interface,
geometry, peer isolation and predict-only behavior. It is not an approved field
estimator, a fixed-lag smoother, or a transfer of historical calibration.
"""
import argparse
import copy
import json
import math
from pathlib import Path
import sys
import time

import numpy as np
from scipy.optimize import least_squares

from normalize import TAGS, WALLS, SESSION, new_run, finish_run, write_table
from run_nightly import atomic_json

CONFIG=Path(__file__).with_name("synthetic_comparison_config.json")


def flag(value):return value in (1,True,"1")


class ArrivalAdapter:
    """Consume each eligible observation once; never inspect a future header to
    admit it early. Call separately for each whole experiment and each method.
    """
    def __init__(self,rows,max_age_ns):
        self.rows=[]
        self.last=None
        self.index=0
        self.max_age_ns=max_age_ns
        seen=set()
        experiments=set()
        for r in rows:
            experiments.add(r["experiment_id"])
            if r["vehicle_id"] not in TAGS or r["tag_id"]!=TAGS[r["vehicle_id"]]:
                raise ValueError("vehicle/tag identity mismatch")
            key=(r["vehicle_id"],r["record_index"],r["link_index"])
            if key in seen:raise ValueError("duplicate trace row")
            seen.add(key)
            value=float(r["range_m"]) if r["range_m"] not in (None,"") else float("nan")
            car=r["vehicle_id"]
            expected=WALLS|{TAGS["car2" if car=="car1" else "car1"]}
            if (r["source"]=="raw" and flag(r["primary_observation"]) and flag(r["valid"])
                and r["pairing_status"]!="ambiguous_header" and math.isfinite(value) and value>0 and r["target_id"] in expected):
                self.rows.append(dict(r,receive_epoch_ns=int(r["receive_epoch_ns"]),range_m=value))
        if len(experiments)>1:raise ValueError("adapter accepts one experiment at a time")
        self.rows.sort(key=lambda r:(r["receive_epoch_ns"],int(r["record_index"]),int(r["link_index"])))

    def take(self,cutoff_ns):
        if not isinstance(cutoff_ns,int):raise ValueError("cutoff must be exact integer ns")
        if self.last is not None and cutoff_ns<self.last:raise ValueError("cutoff must be monotonic")
        self.last=cutoff_ns
        latest={}
        while self.index<len(self.rows) and self.rows[self.index]["receive_epoch_ns"]<=cutoff_ns:
            r=self.rows[self.index]
            self.index+=1
            if cutoff_ns-r["receive_epoch_ns"]<=self.max_age_ns:
                latest[(r["vehicle_id"],r["target_id"])]=r
        return [latest[k] for k in sorted(latest)]


def wrap(value):return math.atan2(math.sin(value),math.cos(value))


def rotation(yaw):return np.array([[math.cos(yaw),-math.sin(yaw)],[math.sin(yaw),math.cos(yaw)]])


def antenna(state,car,config):
    lever=config["body_to_antenna_xyz_m"][car]
    xy=state[:2]+rotation(state[2])@np.asarray(lever[:2])
    return np.r_[xy,config["base_height_m"][car]+lever[2]]


def wall_distance(state,car,target,config):
    return float(np.linalg.norm(antenna(state,car,config)-np.asarray(config["anchors_xyz_m"][target])))


class FixedComparison:
    def __init__(self,initial_room_states,initial_odom,config):
        if config.get("scope")!="synthetic_only_not_field_calibration":
            raise ValueError("this numerical prototype is synthetic only; field calibration is not established")
        self.config=copy.deepcopy(config)
        self.states={c:np.array(initial_room_states[c],dtype=float) for c in TAGS}
        self.previous_odom={c:np.array(initial_odom[c],dtype=float) for c in TAGS}
        self.align={c:rotation(self.states[c][2]-self.previous_odom[c][2]) for c in TAGS}

    def step(self,odom,observations,method):
        if method not in ("odom_only","independent","joint"):raise ValueError("unknown method")
        config=self.config
        predicted={}
        for car in TAGS:
            delta=np.asarray(odom[car])-self.previous_odom[car]
            predicted[car]=self.states[car].copy()
            predicted[car][:2]+=self.align[car]@delta[:2]
            predicted[car][2]=wrap(predicted[car][2]+wrap(delta[2]))
        wall=[r for r in observations if r["target_id"] in WALLS] if method!="odom_only" else []
        peers=[r["range_m"] for r in observations if r["target_id"] not in WALLS] if method=="joint" else []
        target_peer=float(np.median(peers)) if peers else None
        cars=list(TAGS)
        def residual(x,active_cars):
            states={c:x[3*i:3*i+3] for i,c in enumerate(active_cars)}
            out=[]
            for car in active_cars:
                d=states[car]-predicted[car]
                out.extend(d[:2]/config["odom_xy_sigma_m"])
                out.append(wrap(d[2])/config["odom_yaw_sigma_rad"])
            for r in wall:
                if r["vehicle_id"] not in active_cars:continue
                out.append((wall_distance(states[r["vehicle_id"]],r["vehicle_id"],r["target_id"],config)-r["range_m"])/config["wall_sigma_m"])
            if target_peer is not None:
                out.append((np.linalg.norm(antenna(states["car1"],"car1",config)-antenna(states["car2"],"car2",config))-target_peer)/config["peer_sigma_m"])
            return np.array(out)
        x0=np.concatenate([predicted[c] for c in cars])
        if wall or peers:
            groups=[[c] for c in cars] if method=="independent" else [cars]
            estimates={}
            success=True
            nfev=0
            for group in groups:
                prior=np.concatenate([predicted[c] for c in group])
                result=least_squares(lambda v:residual(v,group),prior,max_nfev=config["max_nfev"],loss="linear")
                good=bool(result.success and np.isfinite(result.x).all())
                success=success and good
                nfev+=int(result.nfev)
                for i,c in enumerate(group):estimates[c]=(result.x if good else prior)[3*i:3*i+3]
            x=np.concatenate([estimates[c] for c in cars])
        else:
            x=x0
            success=True
            nfev=0
        self.states={c:x[3*i:3*i+3].copy() for i,c in enumerate(cars)}
        self.previous_odom={c:np.asarray(odom[c]).copy() for c in TAGS}
        per_car={c:sum(r["vehicle_id"]==c for r in wall) for c in cars}
        d={"method":method,"solver_success":success,"nfev":nfev,"wall_factors":len(wall),"wall_factors_by_car":per_car,
            "peer_directed_entries":len(peers),"peer_factors":int(target_peer is not None),
            "measurement_degraded":any(n<3 for n in per_car.values()),"causal":True,"failed_solve_fallback":"affected solve uses odom prediction; valid false if any solver failed"}
        return copy.deepcopy(self.states),d


def synthetic(config):
    """Exact noiseless moving fixture; generated truth is explicitly synthetic."""
    initial={"car1":np.array([1.,1.,.2]),"car2":np.array([3.,2.,-.3])}
    origin=1792925285431466217
    initial_odom={c:np.zeros(3) for c in TAGS}
    models={m:FixedComparison(initial,initial_odom,config) for m in ("odom_only","independent","joint")}
    output,diagnostics=[],[]
    for tick in range(10):
        odom={"car1":np.array([tick*.05,0.,tick*.01]),"car2":np.array([0.,tick*.03,-tick*.02])}
        truth={c:np.r_[initial[c][:2]+rotation(initial[c][2])@odom[c][:2],wrap(initial[c][2]+odom[c][2])] for c in TAGS}
        rows=[]
        for car in TAGS:
            for target in sorted(WALLS):
                rows.append(dict(experiment_id="synthetic",vehicle_id=car,tag_id=TAGS[car],target_id=target,
                    range_m=wall_distance(truth[car],car,target,config),source="raw",primary_observation=1,
                    valid=1,receive_epoch_ns=origin+tick*10**9,record_index=len(rows),link_index=0,pairing_status="raw_only"))
        distance=float(np.linalg.norm(antenna(truth["car1"],"car1",config)-antenna(truth["car2"],"car2",config)))
        for car,target in [("car1","node_0"),("car2","node_1")]:
            rows.append(dict(experiment_id="synthetic",vehicle_id=car,tag_id=TAGS[car],target_id=target,
                range_m=distance,source="raw",primary_observation=1,valid=1,receive_epoch_ns=origin+tick*10**9,
                record_index=len(rows),link_index=0,pairing_status="raw_only"))
        for method,model in models.items():
            observations=ArrivalAdapter(rows,config["max_arrival_age_ns"]).take(origin+tick*10**9)
            states,d=model.step(odom,observations,method)
            d.update(tick=tick,synthetic_state_error_m=max(float(np.linalg.norm(states[c][:2]-truth[c][:2])) for c in TAGS))
            diagnostics.append(d)
            for car in TAGS:
                state=states[car]
                output.append(dict(experiment_id="synthetic",method_id=method,vehicle_id=car,canonical_time_s=float(tick),
                    frame_id="synthetic_room_base",x_m=float(state[0]),y_m=float(state[1]),z_m=None,yaw_rad=float(state[2]),
                    valid=d["solver_success"],diagnostic_id=f"{method}:{tick}",source_version="generated_noiseless_fixture_v1",
                    config_version="synthetic_comparison_config_v1",reference_version="synthetic_only"))
    return output,diagnostics


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args(argv)
    run=None
    started=time.monotonic()
    try:
        run=new_run(args.output,"sandbox_synthetic_comparison",[CONFIG,SESSION/"geometry.json"],
                    [sys.executable,__file__]+(list(argv) if argv is not None else sys.argv[1:]))
        config=json.loads(CONFIG.read_text())
        rows,diagnostics=synthetic(config)
        write_table(args.output/"estimate.csv",rows,list(rows[0]))
        atomic_json(args.output/"diagnostics.json",{"schema_version":1,"scope":"synthetic_only","ticks":diagnostics})
        blocked={trial:{"status":"BLOCKED","reasons":[
            "base_footprint to antenna transform not independently established",
            "per-vehicle room initialization and clock mapping not validated",
            "independent visual reference and video synchronization not accepted"]+
            (["T12 actual initial XY unknown; endpoint inversion forbidden"] if trial=="T12" else [])}
            for trial in ("T08","T10","T12","T14")}
        atomic_json(args.output/"field_readiness.json",blocked)
        (args.output/"report.md").write_text("# 合成适配验证\n\n60条状态、30次单步比较仅来自无噪声合成输入。\n\n验证三维斜距、body lever-arm旋转、按接收时刻因果门控、独立解peer隔离、缺链路预测和固定参数可复现。\n\n当前状态加前一估计/里程增量先验，无平滑、无未来插值；两向peer聚合为一个因子。参数只用于合成夹具。\n\n实包状态见field_readiness.json：四个开发包均受外参/同步/独立参考门槛限制，T12另缺实际起点。未运行实包定位，未计算留出定位误差。\n",encoding="utf-8")
        run["limitations"]=["synthetic validation only; all field localization blocked"]
        finish_run(args.output,run,"DONE",started)
        return 0
    except (Exception,KeyboardInterrupt) as e:
        if run is not None:finish_run(args.output,run,"FAILED",started,e)
        print("ERROR: "+str(e),file=sys.stderr)
        return 2


if __name__=="__main__":sys.exit(main())
