"""Score causal display updates under two-second expiry; publish aggregate comparisons."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from motion import motion_margin

P = json.loads((Path(__file__).resolve().parent / "protocol.json").read_text())
METHODS = P["methods"]
HZ = P["clock_hz"]
NT = P["ticks_per_replay"]
EXP = P["expiry_ticks_inclusive"]
TICK = np.arange(NT)
NS = 1_000_000_000 // HZ
LIMITS = [round(100 * x) for x in P["horizontal_alert_limits_m"]]


def make_display(z, method, vehicle, phase):
    """No truth argument. Priority alerts retain their archived arrival times."""
    epoch = np.arange(1,64)
    accepted = z["accepted"][method]
    closed = np.zeros(len(epoch),bool) if phase is None else np.isin((epoch-phase) % P["cycle_s"],P["closed_source_epoch_modulo"])
    send = ~closed | ~accepted
    sent = epoch[send]
    arrivals = z["ready"][method,send]
    ix = np.searchsorted(arrivals,TICK/HZ,side="right")-1
    source = np.where(ix>=0,sent[np.maximum(0,ix)],-1)
    age = np.where(source>0,TICK-HZ*source,-1)
    src_idx = np.maximum(0,source-1)
    status = np.select([source<0,age>EXP,~accepted[src_idx]],["waiting","expired","alert"],default="issued")
    use = status=="issued"
    k = np.searchsorted(z["odo_recv_ns"][vehicle],TICK*NS,side="right")-1
    ss = HZ*source[use]
    kk = k[use]
    assert np.all(kk>=ss) and np.all(z["odo_recv_ns"][vehicle,kk]<=TICK[use]*NS)
    assert np.all(z["odo_recv_ns"][vehicle,np.minimum(kk+1,1280)]>TICK[use]*NS)
    disp = z["odo_xy"][vehicle,kk]-z["odo_xy"][vehicle,ss]
    xy = np.full((NT,2),np.nan)
    xy[use]=z["pos"][method,vehicle,src_idx[use]]+disp
    hpl = np.full(NT,np.nan)
    growth = np.fromiter((motion_margin(j-s,j,(tick-j)/HZ,float(z["lever_m"][vehicle]),np.linalg.norm(d),
                                        float(z["sigma_xy"]),float(z["sigma_yaw"]))
                         for j,s,tick,d in zip(kk,ss,TICK[use],disp)),dtype=float,count=len(kk))
    hpl[use]=z["hpl"][method,vehicle,src_idx[use]]+growth
    assert np.all(age[use]<=EXP) and np.all(age[status=="expired"]>EXP) and np.all(np.isnan(hpl[~use]))
    assert np.all(send[~accepted])
    stream_status = np.where(source<0,"none",np.where(accepted[src_idx],"accepted","alert"))
    audit = dict(sources=len(epoch),scheduled_closed=int(sum(closed)),total_alerts=int(sum(~accepted)),
                 forwarded_alerts=int(sum(send & ~accepted)),closed_slot_alerts=int(sum(closed & ~accepted)),
                 dropped_numerical=int(sum(~send)),forwarded_numerical=int(sum(send & accepted)))
    return dict(source=source,age_ticks=age,status=status,last_source_status=stream_status,hpl_m=hpl,xy=xy),audit


def add_scores(display, truth, robot):
    xy=display["xy"]
    out={k:v for k,v in display.items() if k!="xy"}
    out["pe_m"]=np.linalg.norm(xy-truth[:,robot],axis=1)
    return pd.DataFrame({"tick":TICK,**out})


def metric(block):
    n=len(block)
    h=block.hpl_m.to_numpy()
    e=block.pe_m.to_numpy()
    valid=np.isfinite(h)
    assert np.array_equal(valid,np.isfinite(e))
    summary={"ticks":n,"issued":int(valid.sum()),"waiting":int((block.status=="waiting").sum()),
             "alert":int((block.status=="alert").sum()),"expired":int((block.status=="expired").sum()),
             "breaches":int(np.sum(e>h))}
    assert sum(summary[k] for k in ("issued","waiting","alert","expired"))==n
    for label,x in (("pe",e),("hpl",h)):
        summary[label+"_median_cm"]=100*np.median(x[valid]) if valid.any() else np.nan
        summary[label+"_p95_cm"]=100*np.percentile(x[valid],95) if valid.any() else np.nan
    for cm in LIMITS:
        available = h<=cm/100
        summary[f"avail_{cm}_ticks"]=int(sum(available))
        summary[f"avail_{cm}_pct"]=100*sum(available)/n
        summary[f"misleading_{cm}_ticks"]=int(sum(available & (e>cm/100)))
    if valid.any():
        summary["minimum_margin_cm"]=100*min((h-e)[valid])
    else: summary["minimum_margin_cm"]=np.nan
    return summary


def aggregate(table,groups):
    return pd.DataFrame([{**dict(zip(groups,key)),**metric(block)} for key,block in table.groupby(groups,sort=False,observed=True)])


def run(inputs, output):
    chunks = []
    for seed in P["splits"]["holdout"]:
        for scene in P["scenes"]:
            name = f"{seed}_{scene}"
            with np.load(inputs / f"{name}_sources.npz") as observations:
                data = dict(observations)
            displays = []
            for phase in [None, P["primary_phase"], *P["alternative_phases"]]:
                policy = "continuous" if phase is None else f"phase{phase}"
                for m, method in enumerate(METHODS):
                    for vehicle in range(2):
                        display, _ = make_display(data, m, vehicle, phase)
                        displays.append((policy, method, vehicle, display))
            with np.load(inputs / f"{name}_truth.npz") as reference:
                truth = reference["truth"]
                for policy, method, vehicle, display in displays:
                    frame = add_scores(display, truth, vehicle)
                    frame["policy"], frame["method"], frame["robot"] = policy, method, vehicle + 1
                    chunks.append(frame)
    frame = pd.concat(chunks, ignore_index=True)
    groups = ["policy", "method", "robot"]
    output.mkdir(exist_ok=True, parents=True)
    aggregate(frame, groups).to_csv(output / "full_clock.csv",index=False)
    band = frame[(frame.age_ticks > 22) & (frame.age_ticks <= 40)]
    aggregate(band, groups).to_csv(output / "late_age.csv",index=False)
    endpoint = frame[frame.age_ticks == 40]
    aggregate(endpoint, groups).to_csv(output / "two_seconds.csv",index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    a=parser.parse_args()
    run(a.inputs, a.out)
