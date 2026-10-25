#!/usr/bin/env python3
"""Independently reconcile every exported row against original bag records.

Uses the strict bag decoder but not normalize.convert/flatten_numeric. Checks
counts and SHA256 of typed, ordered field signatures for all five CSV tables.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import audit_bags
import bag_decoder as bag
from development import verify_normalized
from normalize import SESSION, new_run, finish_run
from run_nightly import atomic_json, sha256, validate_configuration

KINDS=("ranges","frames","odom","imu","commands")


def numeric(value):
    if isinstance(value,list):return [numeric(v) for v in value]
    return value if math.isfinite(value) else None


def append(digests,counts,trial,kind,value):
    key=(trial,kind)
    digests[key].update((json.dumps(value,allow_nan=False,separators=(",",":"))+"\n").encode())
    counts[key]+=1


def prefix(index,receive,header,seq,frame):return [index,receive,header,seq,frame]


def vec(d,keys):return [numeric(d[k]) for k in keys]


def expected_signatures(planned):
    digests=defaultdict(hashlib.sha256)
    counts=Counter()
    for row,path,h in planned:
        trial=row["id"]
        connections,records=bag.load_bag(path)
        decoders={i:bag.Decoder(c["type"],c["definition"]) for i,c in connections.items()}
        for index,(i,t,payload) in enumerate(records):
            topic=connections[i]["topic"]
            if not topic.startswith(("/car1/","/car2/")):continue
            m=decoders[i].decode(payload,connections[i]["type"])
            car=topic.split("/")[1]
            c1=car=="car1"
            raw=topic.endswith(("/uwb/frame3","/nlink_linktrack_nodeframe3"))
            bridge=topic.endswith("/uwb/ranges")
            if topic.endswith("/uwb/frame3"):
                m=json.loads(m["data"])
                stamp=int(m["stamp_secs"])*10**9+int(m["stamp_nsecs"])
                seq,frame=None,m["frame_id"]
            elif "header" in m:
                stamp=m["header"]["stamp"]["secs"]*10**9+m["header"]["stamp"]["nsecs"]
                seq,frame=m["header"]["seq"],m["header"]["frame_id"]
            else:stamp,seq,frame=None,None,None
            base=[car,topic]+prefix(index,t,stamp,seq,frame)
            if raw or bridge:
                source="raw" if raw else "bridge"
                tag=("node_"+str(m["node_id" if c1 else "id"])) if raw else m["tag_id"]
                local=m["local_time_ms" if c1 else "local_time"] if raw else None
                system=m["system_time_ms" if c1 else "system_time"] if raw else None
                nodes=m["nodes"] if raw else m["ranges"]
                append(digests,counts,trial,"frames",base+[source,tag,len(nodes),local,system,m.get("sequence")])
                for li,n in enumerate(nodes):
                    target="node_"+str(n["node_id" if c1 else "id"]) if raw else n["anchor_id"]
                    distance=n["distance_m" if c1 else "dis"] if raw else n["range"]
                    fp=n["fp_rssi_db" if c1 else "fp_rssi"] if raw else None
                    rx=n["rx_rssi_db" if c1 else "rx_rssi"] if raw else None
                    quality=None if raw else numeric(n["quality"])
                    append(digests,counts,trial,"ranges",base+[source,li,tag,target,numeric(distance),fp,rx,quality,local,system,
                        int(raw),int(math.isfinite(distance) and distance>0)])
            elif topic.endswith("/odom"):
                p=m["pose"]["pose"];v=m["twist"]["twist"]
                values=vec(p["position"],"xyz")+vec(p["orientation"],"xyzw")+vec(v["linear"],"xyz")+vec(v["angular"],"xyz")
                append(digests,counts,trial,"odom",base+[m["child_frame_id"]]+values+[numeric(m["pose"]["covariance"]),numeric(m["twist"]["covariance"])])
            elif topic.endswith("/imu"):
                values=vec(m["orientation"],"xyzw")+vec(m["angular_velocity"],"xyz")+vec(m["linear_acceleration"],"xyz")
                append(digests,counts,trial,"imu",base+values+[numeric(m[k+"_covariance"]) for k in ("orientation","angular_velocity","linear_acceleration")])
            elif topic.endswith("/cmd_vel"):
                append(digests,counts,trial,"commands",base+vec(m["linear"],"xyz")+vec(m["angular"],"xyz"))
    return digests,counts


def actual_signatures(root,manifest):
    digests=defaultdict(hashlib.sha256)
    counts=Counter()
    identity={r["id"]:r for r in manifest["formal_bags"]}
    def integer(r,k):return int(r[k]) if r[k]!="" else None
    def real(r,k):return float(r[k]) if r[k]!="" else None
    for kind in KINDS:
        with (root/(kind+".csv")).open(newline="") as stream:
            for r in csv.DictReader(stream):
                trial=r["experiment_id"]
                expected=identity[trial]
                bag.require(r["source_file_sha256"]==expected["sha256"] and r["source_asset_id"]=="bags","CSV input provenance mismatch")
                bag.require(float(r["canonical_time_s"])==(int(r["receive_epoch_ns"])-expected["first_bag_receive_epoch_ns"])/1e9,"arrival time arithmetic mismatch")
                base=[r["vehicle_id"],r["topic"]]+prefix(integer(r,"record_index"),integer(r,"receive_epoch_ns"),
                    integer(r,"header_epoch_ns"),integer(r,"header_seq"),r["frame_id"] if r["header_epoch_ns"] else None)
                if kind=="frames":
                    values=[r["source"],r["tag_id"],integer(r,"entry_count"),integer(r,"device_local_time_ms"),integer(r,"device_system_time_ms"),integer(r,"raw_sequence")]
                elif kind=="ranges":
                    values=[r["source"],integer(r,"link_index"),r["tag_id"],r["target_id"],real(r,"range_m"),real(r,"fp_rssi_db"),
                        real(r,"rx_rssi_db"),real(r,"quality"),integer(r,"device_local_time_ms"),integer(r,"device_system_time_ms"),
                        integer(r,"primary_observation"),integer(r,"valid")]
                elif kind=="odom":
                    values=[r["child_frame_id"]]+[real(r,p+"_"+k) for p,keys in [("position","xyz"),("orientation","xyzw"),("linear","xyz"),("angular","xyz")] for k in keys]
                    values += [json.loads(r["pose_covariance"]),json.loads(r["twist_covariance"])]
                    if r["vehicle_id"]=="car2":bag.require(r["position_z_semantics"]=="driver_yaw_related_not_height","Car2 z semantics lost")
                elif kind=="imu":
                    values=[real(r,p+"_"+k) for p,keys in [("orientation","xyzw"),("angular_velocity","xyz"),("linear_acceleration","xyz")] for k in keys]
                    values += [json.loads(r[k+"_covariance"]) for k in ("orientation","angular_velocity","linear_acceleration")]
                else:values=[real(r,p+"_"+k) for p in ("linear","angular") for k in "xyz"]
                append(digests,counts,trial,kind,base+values)
    return digests,counts


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-root",type=Path,required=True)
    p.add_argument("--normalized",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args(argv)
    started=time.monotonic();run=None
    try:
        run=new_run(args.output,"sandbox_export_audit",[SESSION/"manifest.json",SESSION/"geometry.json"],
                    [sys.executable,__file__]+(list(argv) if argv is not None else sys.argv[1:]))
        normalized=verify_normalized(args.normalized)
        manifest,_=validate_configuration()
        planned=audit_bags.input_plan(args.data_root,manifest)
        run["inputs"]=[*normalized["inputs"],{"asset_id":"normalized","relative_path":"run.json","sha256":sha256(args.normalized/"run.json")}]
        ed,ec=expected_signatures(planned)
        ad,ac=actual_signatures(args.normalized,manifest)
        bag.require(ec==ac,"export row counts differ from original bags")
        checks=[]
        for key in sorted(ec):
            same=ed[key].hexdigest()==ad[key].hexdigest()
            checks.append({"experiment_id":key[0],"table":key[1],"rows":ec[key],"typed_signature_sha256":ad[key].hexdigest(),"matches_bag":same})
        atomic_json(args.output/"verification.json",{"schema_version":1,"checks":checks,"all_rows":sum(ec.values()),"all_match":all(c["matches_bag"] for c in checks)})
        bag.require(all(c["matches_bag"] for c in checks),"export field signatures differ from original bags")
        finish_run(args.output,run,"DONE",started)
        return 0
    except (Exception,KeyboardInterrupt) as e:
        if run is not None:finish_run(args.output,run,"FAILED",started,e)
        print("ERROR: "+str(e),file=sys.stderr)
        return 2


if __name__=="__main__":sys.exit(main())
