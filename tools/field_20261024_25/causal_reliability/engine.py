"""Online peer policies on the PR46/48 six-dimensional SE(2) EKF.

No simulator, evaluator, truth or fault-label imports. Baseline's default path is
unchanged; this module changes only an already admitted peer gain/commit policy.
"""
from collections import Counter
import copy
import math
from pathlib import Path
import sys
import time

import numpy as np

BASELINE_PATH=Path(__file__).resolve().parents[1]/"causal_baselines"
sys.path.append(str(BASELINE_PATH))
import model

METHODS=("odom_only","independent","joint","huber","gate_only","cap_only",
         "gate_cap","shadow_only","gate_cap_shadow")
GATED={"gate_only","gate_cap","gate_cap_shadow"}
CAPPED={"cap_only","gate_cap","gate_cap_shadow"}
NONFEEDBACK={"shadow_only","gate_cap_shadow"}


def online_config(config):
    required=("gate_z","quarantine_bad_count","reopen_good_count","huber_delta",
              "healthy_information_min","healthy_shift_cap_m","weak_shift_cap_m","output_hold_ns")
    out={key:copy.deepcopy(config[key]) for key in required}
    for key,value in out.items():
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
            raise ValueError("positive finite online policy required: "+key)
    for key in ("quarantine_bad_count","reopen_good_count","output_hold_ns"):
        if type(out[key]) is not int:raise ValueError("integer online policy required: "+key)
    return out


class Gate:
    def __init__(self,config):
        self.config=config
        self.state={c:{"bad":0,"good":0,"closed":False} for c in model.CARS}

    def admit(self,car,z):
        state=self.state[car]
        if abs(z)>self.config["gate_z"]:
            state["bad"]+=1;state["good"]=0
            if state["bad"]>=self.config["quarantine_bad_count"]:state["closed"]=True
            return False
        state["bad"]=0;state["good"]+=1
        if state["closed"] and state["good"]>=self.config["reopen_good_count"]:state["closed"]=False
        return not state["closed"]


def joseph(P,H,K,variance):
    J=np.eye(6)-np.outer(K,H)
    out=J@P@J.T+np.outer(K,K)*variance
    return (out+out.T)/2


def shifted(x,delta):
    out=x+delta
    out[2],out[5]=model.wrap(out[2]),model.wrap(out[5])
    return out


class PeerPolicy:
    def __init__(self,method,config,shadow):
        self.method=method;self.config=online_config(config);self.shadow=shadow
        self.gate=Gate(self.config);self.counts=Counter()
        self.output_delta=np.zeros(6);self.output_receive_ns=None

    def health(self,measured):
        result=[]
        for car in model.CARS:
            rows=[v for (c,t),(stamp,v) in self.shadow.wall_geometry.items()
                  if c==car and 0<=measured-stamp<=self.shadow.config["geometry_window_ns"]]
            info=np.zeros((2,2))
            for row in rows:info+=np.outer(row,row)/self.shadow.config["weights"]["wall_sigma_m"]["value"]**2
            minimum=float(np.linalg.eigvalsh(info)[0]);healthy=len(rows)>=3 and minimum>=self.config["healthy_information_min"]
            result.append(dict(vehicle_id=car,wall_links=len(rows),wall_xy_jacobians=[v.tolist() for v in rows],information_min=minimum,healthy=bool(healthy),
                cap_m=self.config["healthy_shift_cap_m"] if healthy else self.config["weak_shift_cap_m"]))
        return result

    def gain(self,engine,row,measured,H,expected,innovation,variance,K):
        prior=engine.x.copy();P=engine.P.copy()
        z=innovation/math.sqrt(float(H@P@H+variance))
        before=copy.deepcopy(self.gate.state)
        accepted=self.gate.admit(row["vehicle_id"],z) if self.method in GATED else True
        diagnostic=dict(innovation_reference="event_pre_feedback_state_and_covariance",pre_feedback_state=prior.tolist(),
            pre_feedback_covariance=P.tolist(),H=H.tolist(),expected_range_m=expected,innovation_m=innovation,
            base_variance_m2=variance,z=z,gate_before=before,gate_after=copy.deepcopy(self.gate.state),
            gate_enabled=self.method in GATED,accepted=bool(accepted),gate_source=row["vehicle_id"],
            health=self.health(measured),cap_enabled=self.method in CAPPED,nonfeedback=self.method in NONFEEDBACK,
            shadow_state=self.shadow.x.tolist(),shadow_covariance=self.shadow.P.tolist(),
            covariance_semantics="observation_dependent_gain_Joseph_engineering_covariance_not_calibrated_posterior")
        # Preserve the counterfactual unbounded proposal even when the gate rejects.
        diagnostic.update(raw_gain=K.tolist(),raw_proposal=shifted(prior,K*innovation).tolist(),
            raw_proposal_covariance=joseph(P,H,K,variance).tolist())
        self.counts["eligible_peer"]+=1
        if not accepted:
            self.counts["gate_rejected"]+=1
            if self.method in NONFEEDBACK:self.output_delta[:]=0
            return dict(accepted=False,diagnostics=diagnostic)
        effective=variance;weight=1.
        if self.method=="huber":
            weight=min(1.,self.config["huber_delta"]/max(abs(innovation)/math.sqrt(variance),1e-12))
            effective=variance/weight;K=P@H/float(H@P@H+effective)
        raw_K=K.copy();raw_delta=raw_K*innovation
        raw_proposal=shifted(prior,raw_delta)
        scales=[1.,1.];norms=[]
        for i in range(2):
            sl=slice(3*i,3*i+3);norm=float(np.linalg.norm(raw_delta[3*i:3*i+2]));norms.append(norm)
            if self.method in CAPPED and norm>diagnostic["health"][i]["cap_m"]:
                scales[i]=diagnostic["health"][i]["cap_m"]/norm;K[sl]*=scales[i]
                self.counts["clipped_"+model.CARS[i]]+=1
        diagnostic.update(raw_gain=raw_K.tolist(),actual_gain=K.tolist(),huber_weight=weight,effective_variance_m2=effective,
            raw_proposal=raw_proposal.tolist(),raw_proposal_covariance=joseph(P,H,raw_K,effective).tolist(),
            cap_scales=scales,raw_shift_xy_m=norms,actual_shift_xy_m=[norms[i]*scales[i] for i in range(2)],
            clipped=[scale<1. for scale in scales],receive_epoch_ns=int(row["receive_epoch_ns"]),measurement_epoch_ns=measured)
        return dict(accepted=True,diagnostics=diagnostic,gain=K,variance=effective,commit=self.method not in NONFEEDBACK)

    def record_proposal(self,proposal,covariance,control):
        diagnostic=control["diagnostics"]
        diagnostic.update(proposal=proposal.tolist(),proposal_covariance=covariance.tolist(),committed=control["commit"])
        self.counts["proposal_valid"]+=1
        if self.method in NONFEEDBACK:
            self.output_delta=proposal-np.array(diagnostic["pre_feedback_state"])
            self.output_delta[2],self.output_delta[5]=model.wrap(self.output_delta[2]),model.wrap(self.output_delta[5])
            self.output_receive_ns=diagnostic["receive_epoch_ns"]

    def delta_at(self,publication):
        if self.method not in NONFEEDBACK or self.output_receive_ns is None:return np.zeros(6)
        age=publication-self.output_receive_ns
        return self.output_delta.copy() if 0<=age<=self.config["output_hold_ns"] else np.zeros(6)


class Candidate:
    """Same Baseline EKF with a private, independent Odom/wall shadow."""
    def __init__(self,method,baseline_config,policy_config):
        if method not in METHODS:raise ValueError("unknown comparison method")
        self.method=method
        self.core_seconds=0.;self.shadow_seconds=0.
        self.shadow=model.Baseline("independent",baseline_config)
        self.policy=None if method in model.METHODS else PeerPolicy(method,policy_config,self.shadow)
        self.engine=model.Baseline(method if method in model.METHODS else "joint",baseline_config,self.policy)

    def process(self,event):
        started=time.perf_counter();shadow_decision=self.shadow.process(event)
        self.shadow_seconds+=time.perf_counter()-started
        started=time.perf_counter();decision=self.engine.process(event)
        self.core_seconds+=time.perf_counter()-started
        decision["shadow_status"]=shadow_decision["status"]
        return decision

    def snapshot(self,publication):
        states=self.engine.snapshot(publication)
        delta=self.policy.delta_at(publication) if self.policy else np.zeros(6)
        for i,car in enumerate(model.CARS):
            state=states[car]
            if state["pose"] is None:continue
            correction=delta[3*i:3*i+3]
            if np.any(correction):
                pose=np.array(state["pose"])+correction;pose[2]=model.wrap(pose[2])
                state["pose"]=pose.tolist();state["covariance"]=None
                state["output_covariance_reason"]="output_only_held_correction_no_calibrated_covariance"
        return states

    def state_record(self,publication):
        return dict(vehicles=self.snapshot(publication),feedback_state=self.engine.x.tolist(),
            feedback_covariance=self.engine.P.tolist(),shadow_state=self.shadow.x.tolist(),shadow_covariance=self.shadow.P.tolist(),
            cumulative_event_status=dict(self.engine.counts),
            gate=copy.deepcopy(self.policy.gate.state) if self.policy else None,
            output_delta=self.policy.delta_at(publication).tolist() if self.policy else [0.]*6,
            policy_counts=dict(self.policy.counts) if self.policy else {},
            covariance_semantics="engineering_filter_covariance; held_nonfeedback_output_has_no_covariance")
