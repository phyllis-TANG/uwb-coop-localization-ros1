#!/usr/bin/env python3
"""Plot already computed development windows; no field fitting or new labels."""
import argparse
import csv
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/"tools/field_20261024_25"))
from normalize import new_run, finish_run
from run_nightly import sha256


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--development",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    started=time.monotonic()
    run=new_run(args.output,"sandbox_development_plot",[ROOT/"tools/field_20261024_25/development_config.json"],sys.argv)
    run["source_sha256"][str(Path(__file__).resolve().relative_to(ROOT))]=sha256(__file__)
    try:
        path=args.development/"link_windows.csv"
        run["inputs"]=[{"asset_id":"development_windows","relative_path":"link_windows.csv","sha256":sha256(path)}]
        with path.open(newline="") as f:rows=list(csv.DictReader(f))
        fig,axes=plt.subplots(4,2,figsize=(12,12),constrained_layout=True)
        for index,trial in enumerate(["T08","T10","T12","T14"]):
            for car,target,label,color in [("car1","node_0","Car1 to Car2","#2463a6"),("car2","node_1","Car2 to Car1","#c15b25")]:
                selected=sorted([r for r in rows if r["experiment_id"]==trial and r["vehicle_id"]==car and r["target_id"]==target],key=lambda r:float(r["window_start_s"]))
                t=[float(r["window_start_s"])+.5 for r in selected]
                for ax,column,scale in [(axes[index,0],"range_median_m",1.),(axes[index,1],"valid_frame_fraction",100.)]:
                    y=[float(r[column])*scale if r[column] else float("nan") for r in selected]
                    ax.plot(t,y,color=color,lw=1.2,label=label)
            axes[index,0].set_title(trial+" peer range: 1 s medians")
            axes[index,0].set_ylabel("Range (m)")
            axes[index,1].set_title(trial+" peer entry availability")
            axes[index,1].set_ylabel("Valid raw frames (%)")
            axes[index,1].set_ylim(0,103)
            for ax in axes[index]:
                ax.grid(alpha=.2)
                ax.set_xlabel("Seconds from first bag receipt (arrival only)")
                ax.legend(fontsize=8,loc="best")
        fig.suptitle("Development bags only; directed raw entries; no localization truth\nArrival-time bins are not synchronized measurement bins; medians hide within-bin spikes",fontsize=12)
        for ext in ("png","svg"):fig.savefig(args.output/("development_peer."+ext),dpi=160)
        plt.close(fig)
        run["limitations"]=["visualization of existing fixed windows only; no synchronized truth or NLOS labels"]
        finish_run(args.output,run,"DONE",started)
    except Exception as e:
        finish_run(args.output,run,"FAILED",started,e)
        raise


if __name__=="__main__":main()
