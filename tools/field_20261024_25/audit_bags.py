#!/usr/bin/env python3
"""Offline intake QC for the eight formal 2026-10-25 dynamic bags.

No ROS, serial, motion, or network access. Input hashes are checked before any
bag is parsed. Quality/availability checks do not certify position accuracy.
"""
import argparse
import hashlib
import json
import math
import struct
import sys
from pathlib import Path
from collections import defaultdict, Counter

import numpy as np
import bag_decoder as a


def validate_frame3(text):
    """Validate wrapper JSON against its original checksum-protected packet."""
    p = json.loads(text)
    packet = bytes.fromhex(p["packet_hex"])
    a.require(len(packet) >= 22, "Frame3 packet shorter than 22 bytes")
    a.require(p["schema"] == "linktrack_frame3_raw_v1", "unexpected raw Frame3 JSON schema")
    a.require(packet[:2] == b"\x55\x05", "invalid Frame3 header/function")
    a.require(len(packet) == struct.unpack_from("<H", packet, 2)[0]
              == 22 + 7 * packet[20], "Frame3 declared length/node count mismatch")
    a.require((sum(packet[:-1]) & 255) == packet[-1], "invalid Frame3 checksum")
    a.require(p["role"] == packet[4] and p["node_id"] == packet[5], "Frame3 identity mismatch")
    a.require(p["local_time_ms"] == struct.unpack_from("<I", packet, 6)[0],
              "Frame3 local time mismatch")
    a.require(p["system_time_ms"] == struct.unpack_from("<I", packet, 10)[0],
              "Frame3 system time mismatch")
    a.require(abs(p["voltage_v"] - struct.unpack_from("<H", packet, 18)[0] / 1000.) < 1e-9,
              "Frame3 voltage mismatch")
    a.require(len(p["nodes"]) == packet[20], "Frame3 JSON node count mismatch")
    for index, node in enumerate(p["nodes"]):
        offset = 21 + 7 * index
        distance = int.from_bytes(packet[offset+2:offset+5], "little", signed=True) / 1000.
        a.require((node["role"], node["node_id"]) == (packet[offset], packet[offset+1]),
                  "Frame3 peer identity mismatch")
        a.require(abs(node["distance_m"] - distance) < 1e-9, "Frame3 distance mismatch")
        a.require(node["fp_rssi_db"] == -packet[offset+5] / 2.
                  and node["rx_rssi_db"] == -packet[offset+6] / 2., "Frame3 RSSI mismatch")
    return p


def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.integer):return int(x)
 if isinstance(x,np.floating):x=float(x)
 if isinstance(x,float) and not math.isfinite(x):return None
 return x

def stats(v):return a.stats(v)
def rawstamp(p):return int(p['stamp_secs'])*10**9+int(p['stamp_nsecs'])

def intervals(times):
 times=np.array(times,dtype=np.int64);d=np.diff(times)
 return {'interval_ms':stats(d/1e6),'backwards':int(sum(d<0)),'duplicates':int(sum(d==0)),'gaps_over_0_1s':int(sum(d>1e8)),'gaps_over_0_5s':int(sum(d>5e8)),'gaps_over_1s':int(sum(d>1e9))}

def runs(rows,selector,start):
 out=[];current=None
 for t,m in rows:
  label=selector(m)
  if label!=current:
   if out:out[-1]['last_s']=last
   out.append({'kind':label,'first_s':(t-start)/1e9,'messages':0})
   current=label
  out[-1]['messages']+=1;last=(t-start)/1e9
 if out:out[-1]['last_s']=last
 return out

def audit(path,trial,expected_count):
 conn,raw=a.load_bag(path);start=min(t for i,t,d in raw);end=max(t for i,t,d in raw)
 dec={i:a.Decoder(c['type'],c['definition']) for i,c in conn.items()}
 groups=defaultdict(list)
 for i,t,d in raw:groups[conn[i]['topic']].append((t,dec[i].decode(d,conn[i]['type'])))
 report={'trial':trial,'filename':path.name,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'all_message_bytes_decoded':True,'count':len(raw),'expected_count_from_operator':expected_count,'count_matches':len(raw)==expected_count,'duration_s':(end-start)/1e9,'start_epoch_ns':start,'end_epoch_ns':end,'topics':{},'raw_car1':{},'pairing':{},'ranges':{},'odom':{},'commands':{},'device_timing':{},'logs':[]}
 for topic,rows in sorted(groups.items()):
  ts=[t for t,m in rows]
  s={'count':len(rows),'first_s':(min(ts)-start)/1e9,'last_s':(max(ts)-start)/1e9,'head_gap_s':(min(ts)-start)/1e9,'tail_gap_s':(end-max(ts))/1e9,'receive_span_s':(max(ts)-min(ts))/1e9,'receive':intervals(ts),'connections':[{'callerid':c['callerid'],'type':c['type'],'md5sum':c['md5sum']} for c in conn.values() if c['topic']==topic]}
  if 'header' in rows[0][1]:
   hh=[a.stamp(m) for t,m in rows];seq=[m['header']['seq'] for t,m in rows]
   dd=np.diff(seq)
   s['header']=intervals(hh);s['header']['seq_backwards']=int(sum(dd<0));s['header']['seq_duplicates']=int(sum(dd==0));s['header']['seq_missing_estimate']=int(np.maximum(dd-1,0).sum());s['header']['receive_minus_stamp_ms']=stats((np.array(ts)-np.array(hh))/1e6)
   s['header']['frames']=dict(Counter(m['header']['frame_id'] for t,m in rows))
  report['topics'][topic]=s
  if topic.endswith('/odom'):
   xy=np.array([[m['pose']['pose']['position'][k] for k in 'xy'] for t,m in rows]);zz=np.array([m['pose']['pose']['position']['z'] for t,m in rows]);yy=np.unwrap([a.yaw(m['pose']['pose']['orientation']) for t,m in rows]);lin=[math.hypot(m['twist']['twist']['linear']['x'],m['twist']['twist']['linear']['y']) for t,m in rows];ang=[m['twist']['twist']['angular']['z'] for t,m in rows]
   active=[(t,m) for (t,m),v,w in zip(rows,lin,ang) if v>.005 or abs(w)>.02]
   report['odom'][topic]={'first_xy':xy[0].tolist(),'last_xy':xy[-1].tolist(),'net_delta_xy':(xy[-1]-xy[0]).tolist(),'path_length_xy_m':float(np.linalg.norm(np.diff(xy,axis=0),axis=1).sum()),'max_from_first_xy_m':float(np.linalg.norm(xy-xy[0],axis=1).max()),'yaw_start_deg':float(np.degrees(yy[0])),'yaw_end_deg':float(np.degrees(yy[-1])),'yaw_net_deg':float(np.degrees(yy[-1]-yy[0])),'linear_speed_mps':stats(lin),'angular_speed_rps':stats(ang),'position_z':stats(zz),'active_first_s':(active[0][0]-start)/1e9 if active else None,'active_last_s':(active[-1][0]-start)/1e9 if active else None,'child_frames':dict(Counter(m['child_frame_id'] for t,m in rows))}
  if topic.endswith('/cmd_vel'):
   def label(m):
    v=m['linear']['x'];w=m['angular']['z']
    return 'forward_with_possible_heading_correction' if v>.001 else 'reverse' if v<-.001 else 'turn_right_in_place' if w<-.001 else 'turn_left_in_place' if w>.001 else 'zero'
   report['commands'][topic]={'runs':runs(rows,label,start),'linear_x':stats([m['linear']['x'] for t,m in rows]),'angular_z':stats([m['angular']['z'] for t,m in rows])}
  if topic.endswith('/uwb/ranges'):
   vals=defaultdict(list);times=defaultdict(list);invalid=Counter();quality=Counter();empties=[]
   for t,m in rows:
    if not m['ranges']:empties.append((t-start)/1e9)
    for n in m['ranges']:
     aid=n['anchor_id'];v=n['range'];vals[aid].append(v)
     if math.isfinite(v) and v>0:times[aid].append(t)
     else:invalid[aid]+=1
     if not math.isfinite(n['quality']):quality['nonfinite']+=1
     else:quality['finite']+=1
   report['ranges'][topic]={'tag_ids':dict(Counter(m['tag_id'] for t,m in rows)),'empty_messages':len(empties),'empty_first_s':min(empties) if empties else None,'empty_last_s':max(empties) if empties else None,'quality':dict(quality),'links':{aid:{'distance_m':stats(v),'entry_count':len(v),'frame_fraction':len(v)/len(rows),'invalid_count':invalid[aid],'valid_first_s':(min(times[aid])-start)/1e9 if times[aid] else None,'valid_last_s':(max(times[aid])-start)/1e9 if times[aid] else None,'valid_receive_timing':intervals(times[aid]) if times[aid] else {}} for aid,v in vals.items()}}
  if topic=='/rosout':report['logs']=[{'time_s':(t-start)/1e9,'level':m['level'],'node':m['name'],'message':m['msg']} for t,m in rows]
 parsed=[];bad=[]
 for t,m in groups['/car1/uwb/frame3']:
  try:
   p=validate_frame3(m['data'])
   parsed.append((t,p))
  except Exception as e:bad.append({'receive_s':(t-start)/1e9,'error':repr(e)})
 seq=[p['sequence'] for t,p in parsed];dd=np.diff(seq)
 report['raw_car1']={'validated_packets':len(parsed),'bad_packets':bad,'sequence_missing_estimate':int(np.maximum(dd-1,0).sum()),'sequence_backwards':int(sum(dd<0)),'sequence_duplicates':int(sum(dd==0)),'header':intervals([rawstamp(p) for t,p in parsed])}
 for car,rawrows in [('car1',parsed),('car2',groups['/car2/nlink_linktrack_nodeframe3'])]:
  stamped=rawstamp if car=='car1' else a.stamp
  simple=defaultdict(list);original=defaultdict(list)
  for t,m in groups['/'+car+'/uwb/ranges']:simple[a.stamp(m)].append(m)
  for t,m in rawrows:original[stamped(m)].append(m)
  common=set(simple)&set(original);mismatches=[];links=0
  for h in common:
   p=original[h][0];source={'node_'+str(n['node_id']):n['distance_m'] for n in p['nodes']} if car=='car1' else {'node_'+str(n['id']):n['dis'] for n in p['nodes']}
   dst=simple[h][0]
   if len(source)!=len(dst['ranges']):mismatches.append({'stamp_ns':h,'count_mismatch':True})
   for n in dst['ranges']:
    if n['anchor_id'] not in source or abs(source.get(n['anchor_id'],0)-n['range'])>1e-7:mismatches.append({'stamp_ns':h,'link':n['anchor_id']})
    links+=1
  onlyraw=set(original)-set(simple);onlyrange=set(simple)-set(original)
  report['pairing'][car]={'same_header_frames':len(common),'compared_links':links,'distance_or_count_mismatches':len(mismatches),'examples':mismatches[:5],'raw_duplicate_stamp_messages':sum(len(v)-1 for v in original.values()),'range_duplicate_stamp_messages':sum(len(v)-1 for v in simple.values()),'raw_only_frames':len(onlyraw),'range_only_frames':len(onlyrange),'raw_only_before_range_start':sum(h<min(simple) for h in onlyraw),'raw_only_after_range_end':sum(h>max(simple) for h in onlyraw),'range_only_before_raw_start':sum(h<min(original) for h in onlyrange),'range_only_after_raw_end':sum(h>max(original) for h in onlyrange)}
  tt=np.array([p['local_time_ms'] if car=='car1' else p['local_time'] for t,p in rawrows],dtype=np.int64)
  ss=np.array([p['system_time_ms'] if car=='car1' else p['system_time'] for t,p in rawrows],dtype=np.int64)
  report['device_timing'][car]={'local_ms_diff':stats(np.diff(tt)),'local_nonpositive':int(sum(np.diff(tt)<=0)),'system_ms_diff':stats(np.diff(ss)),'system_nonpositive':int(sum(np.diff(ss)<=0)),'raw_empty_frames':sum(not p['nodes'] for t,p in rawrows)}
 return report


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def input_plan(data_root, manifest):
    rows = manifest.get("formal_bags")
    a.require(isinstance(rows, list) and bool(rows), "manifest.formal_bags must be a nonempty list")
    planned, seen = [], set()
    base = (data_root / "extracted" / "bags").resolve()
    for row in rows:
        identity = row["id"]
        a.require(identity not in seen, "duplicate formal bag id: " + identity)
        seen.add(identity)
        relative = Path(row["relative_path"])
        a.require(not relative.is_absolute() and ".." not in relative.parts,
                  "unsafe manifest bag relative_path: " + str(relative))
        path = (base / relative).resolve()
        try:
            path.relative_to(base)
        except ValueError as error:
            raise a.BagError("bag path escapes data-root extraction directory") from error
        a.require(path.is_file(), "missing extracted bag: " + str(relative))
        expected = row["sha256"].lower()
        a.require(len(expected) == 64 and all(c in "0123456789abcdef" for c in expected),
                  "invalid manifest sha256 for " + identity)
        actual = sha256_file(path)
        a.require(actual == expected, "SHA256 mismatch for " + identity + ": " + actual)
        planned.append((row, path, actual))
    return planned


def qc_summary(reports):
    failures, observations = [], []
    for report in reports:
        identity = report["trial"]
        if not report["count_matches"]:
            failures.append(identity + ": message count differs from operator record")
        if report["raw_car1"]["bad_packets"]:
            failures.append(identity + ": invalid Car1 raw Frame3 packet(s)")
        required = ["/" + car + "/" + topic for car in ("car1", "car2")
                    for topic in ("odom", "imu", "PowerVoltage", "uwb/ranges")]
        required += ["/car1/uwb/frame3", "/car2/nlink_linktrack_nodeframe3"]
        movers = ("car1", "car2") if identity in ("T12", "T13") else (
            ("car1",) if identity in ("T10", "T11") else ("car2",))
        required += ["/" + car + "/cmd_vel" for car in movers]
        for topic in required:
            if topic not in report["topics"]:
                failures.append(identity + ": missing recorded topic " + topic)
        for topic, item in report["ranges"].items():
            if item["empty_messages"]:
                observations.append(identity + " " + topic + ": empty range frames")
            if any(link["invalid_count"] for link in item["links"].values()):
                observations.append(identity + " " + topic + ": nonpositive/nonfinite distance entries")
        for car, pair in report["pairing"].items():
            if pair["distance_or_count_mismatches"]:
                failures.append(identity + ": raw/ranges mismatch for " + car)
            if pair["raw_duplicate_stamp_messages"] or pair["range_duplicate_stamp_messages"]:
                observations.append(identity + ": repeated raw/ranges header stamps for " + car)
            interior_raw = pair["raw_only_frames"] - pair["raw_only_before_range_start"] - pair["raw_only_after_range_end"]
            interior_ranges = pair["range_only_frames"] - pair["range_only_before_raw_start"] - pair["range_only_after_raw_end"]
            if interior_raw or interior_ranges:
                observations.append(identity + ": interior unmatched raw/ranges frames for " + car)
        for topic, item in report["topics"].items():
            if topic == "/rosout" or "header" not in item:
                continue
            header = item["header"]
            if any(header[k] for k in ("backwards", "duplicates", "seq_backwards",
                                        "seq_duplicates", "seq_missing_estimate")):
                observations.append(identity + ": header/sequence discontinuity " + topic)
    return {"status": "pass" if not failures else "fail",
            "formal_bags": len(reports),
            "decoded_messages": sum(r["count"] for r in reports),
            "validated_car1_raw_packets": sum(r["raw_car1"]["validated_packets"] for r in reports),
            "failures": failures, "observations_requiring_review": observations,
            "scope": "File/message structure and recorded acquisition chain only; not positioning accuracy or visual reference acceptance."}


def markdown_report(payload):
    summary = payload["summary"]
    lines = [
        "# 2026-10-25 formal dynamic bag QC", "",
        "Status: **" + summary["status"].upper() + "** (file/schema/acquisition-chain checks only).", "",
        "All input SHA256 values were checked against the manifest before parsing.",
        "Decoded **{:,}** messages across {} formal bags; validated **{:,}** Car1 raw Frame3 packets.".format(
            summary["decoded_messages"], summary["formal_bags"], summary["validated_car1_raw_packets"]), "",
        "| Trial | Messages | Duration s | C1 peer entries % | C2 peer entries % | Max sensor receipt gap ms |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in payload["bags"]:
        fractions = []
        for car in ("car1", "car2"):
            aid = "node_0" if car == "car1" else "node_1"
            link = r["ranges"].get("/"+car+"/uwb/ranges", {}).get("links", {}).get(aid, {})
            fractions.append(100 * link.get("frame_fraction", 0))
        maximum = max((t["receive"]["interval_ms"].get("max", 0)
                       for name, t in r["topics"].items()
                       if name != "/rosout" and "header" in t), default=0)
        lines.append("| {} | {} | {:.3f} | {:.2f} | {:.2f} | {:.1f} |".format(
            r["trial"], r["count"], r["duration_s"], fractions[0], fractions[1], maximum))
    lines += ["", "## Interpretation and limitations", "",
        "- Peer-entry fraction is per recorded range frame, not radio packet-delivery probability. Keep the two directed peer streams separate.",
        "- Paired raw/ranges frames are compared by exact header stamp with a 1e-7m distance tolerance. Boundary-only unmatched frames are subscriber start/stop effects, not proof of link loss.",
        "- Header and device times must be inspected separately from bag receipt time. Receipt gaps and negative receive-minus-header values do not identify RF outages or a calibrated clock delay.",
        "- quality=NaN means unknown by driver design. It is not a measured confidence score.",
        "- Odometry and recorded command phases verify feedback/controller evidence only. They are not independent room coordinates, distances, or trajectory ground truth.",
        "- Car2 odom position.z must not be interpreted as physical antenna height.",
        "- Requested /tf and /tf_static may have no actual messages; explicit frame/marker-to-antenna alignment is still required.",
        "- /rosout can contain latched historical INFO messages with out-of-order stamps from different publishers.",
        "- T10/T11 are about 57s and do not provide a 20s static lead-in, although their recorded actions are complete.",
        "- Occlusion effect, camera calibration/extrinsics, video-to-bag synchronization, and final localization accuracy remain separate acceptance gates.", "",
        "## Failures", ""]
    lines += ["- " + item for item in summary["failures"]] or ["None."]
    lines += ["", "## Observations requiring review", ""]
    lines += ["- " + item for item in summary["observations_requiring_review"]] or ["None from the automated continuity checks."]
    lines += ["", "## Reproduce", "", "Run the repository's sandbox role runbook, or:", "",
              chr(96) * 3 + "bash",
              'python3 tools/field_20261024_25/audit_bags.py --data-root "$DATA_ROOT" --output "$OUTPUT_ROOT/bag_qc"',
              chr(96) * 3, "",
              "Requires Python 3.8+ and numpy; no ROS/hardware/network access. The output directory must be empty unless --overwrite is supplied.",
              "Machine-readable provenance, input hashes, topic schemas/counts, raw-packet checks, pairing, timing and command/odom summaries are in bag_qc.json.", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New/empty output directory")
    parser.add_argument("--manifest", type=Path, default=Path(__file__).resolve().parents[2] /
                        "docs/field_tests/20261024_25/manifest.json")
    parser.add_argument("--overwrite", action="store_true",
                        help="Allow replacing bag_qc.json and BAG_QC_REPORT.md in an existing output directory")
    args = parser.parse_args(argv)
    try:
        if args.output.exists():
            a.require(args.output.is_dir(), "--output exists and is not a directory")
            a.require(args.overwrite or not any(args.output.iterdir()),
                      "--output is not empty; choose a new directory or explicitly use --overwrite")
        manifest_bytes = args.manifest.read_bytes()
        manifest = json.loads(manifest_bytes)
        planned = input_plan(args.data_root, manifest)  # All hashes before parsing.
        reports = []
        for row, path, actual_hash in planned:
            print("Auditing {}...".format(row["id"]), flush=True)
            result = audit(path, row["id"], int(row["expected_messages"]))
            result["relative_path"] = row["relative_path"]
            result["split"] = row.get("split", "unspecified")
            result["manifest_sha256_match"] = actual_hash == row["sha256"].lower()
            reports.append(clean(result))
        source_root = Path(__file__).resolve().parents[2]
        source_hashes = {}
        for source in (Path(__file__).resolve(), Path(a.__file__).resolve()):
            source_hashes[str(source.relative_to(source_root))] = sha256_file(source)
        payload = {
            "schema": "uwb_field_20261024_25_bag_qc_v1",
            "provenance": {
                "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                "source_sha256": source_hashes,
                "input_paths_relative_to": "DATA_ROOT/extracted/bags",
                "numpy_version": np.__version__,
                "python_version": ".".join(map(str, sys.version_info[:3])),
                "all_input_sha256_checked_before_decode": True,
            },
            "summary": qc_summary(reports),
            "bags": reports,
        }
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "bag_qc.json").write_text(json.dumps(payload, ensure_ascii=False,
                                                          indent=2, allow_nan=False) + "\n", encoding="utf-8")
        (args.output / "BAG_QC_REPORT.md").write_text(markdown_report(payload), encoding="utf-8")
        print(json.dumps(payload["summary"], ensure_ascii=False))
        return 0 if payload["summary"]["status"] == "pass" else 1
    except (OSError, ValueError, KeyError, struct.error, UnicodeError) as error:
        print("ERROR: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
