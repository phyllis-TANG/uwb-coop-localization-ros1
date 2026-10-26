"""Synthetic evaluation only, outside the online estimator's import graph."""
import math
import numpy as np


def phase_at(protocol,seconds):
    for phase,(start,end) in protocol["evaluation"]["phases"].items():
        if start<=seconds<end:return phase
    return None


def evaluate(states,truth,protocol,origin):
    groups={};recovery={}
    lookup={(r["vehicle_id"],r["state_epoch_ns"]):r["pose"] for r in truth}
    by_tick={}
    for tick in states:
        publication=tick["publish_receive_epoch_ns"];independent=tick["methods"]["independent"]["vehicles"]
        errors={}
        for method,detail in tick["methods"].items():
            for car,state in detail["vehicles"].items():
                stamp=state.get("state_epoch_ns");seconds=((stamp if stamp is not None else publication)-origin)/1e9
                phase=phase_at(protocol,seconds)
                if phase is None:continue
                key=(method,car,phase);group=groups.setdefault(key,dict(n_states=0,errors=[],squared=0.,above=0))
                group["n_states"]+=1
                error=None
                if state["valid"] and stamp is not None and state["pose"] is not None:
                    target=lookup[(car,stamp)];error=float(np.linalg.norm(np.array(state["pose"][:2])-target[:2]))
                    group["errors"].append(error);group["squared"]+=error*error;group["above"]+=int(error>protocol["evaluation"]["exploratory_error_limit_m"])
                errors[method,car]=(stamp,error)
        for (method,car),(stamp,error) in errors.items():
            base=errors.get(("independent",car),(None,None))[1]
            if stamp is not None and stamp>=origin+int(protocol["fault_end_s"]*1e9):
                recovery.setdefault((method,car),{})[stamp]=None if error is None or base is None else error-base
    result=[]
    for (method,car,phase),group in sorted(groups.items()):
        e=group["errors"];delay=None;start=None
        for stamp,excess in sorted(recovery.get((method,car),{}).items()):
            if excess is None or excess>protocol["evaluation"]["recovery_threshold_excess_m"]:start=None;continue
            if start is None:start=stamp
            if (stamp-start)/1e9>=protocol["evaluation"]["recovery_dwell_s"]:
                delay=(start-origin)/1e9-protocol["fault_end_s"];break
        result.append(dict(method=method,vehicle_id=car,phase=phase,n_states=group["n_states"],valid_states=len(e),
            xy_rmse_m=math.sqrt(group["squared"]/len(e)) if e else None,xy_max_m=max(e) if e else None,
            over_error_limit_rows=group["above"],recovery_start_delay_s=delay,
            scope="synthetic_development; at explicit state time; paired seeds, not independent frames"))
    return result
