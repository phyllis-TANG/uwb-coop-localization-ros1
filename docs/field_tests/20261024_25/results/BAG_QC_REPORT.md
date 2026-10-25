# 2026-10-25 formal dynamic bag QC

Status: **PASS** (file/schema/acquisition-chain checks only).

All input SHA256 values were checked against the manifest before parsing.
Decoded **311,144** messages across 8 formal bags; validated **52,758** Car1 raw Frame3 packets.

| Trial | Messages | Duration s | C1 peer entries % | C2 peer entries % | Max sensor receipt gap ms |
|---|---:|---:|---:|---:|---:|
| T08 | 70766 | 242.633 | 99.79 | 96.72 | 426.6 |
| T09 | 39387 | 132.147 | 99.80 | 96.33 | 380.8 |
| T10 | 16998 | 56.947 | 99.93 | 92.08 | 117.1 |
| T11 | 17108 | 57.322 | 99.93 | 96.10 | 642.0 |
| T12 | 40952 | 135.093 | 99.72 | 94.97 | 451.7 |
| T13 | 36945 | 121.000 | 99.84 | 87.73 | 346.4 |
| T14 | 48356 | 163.745 | 99.79 | 94.97 | 413.7 |
| T15 | 40632 | 136.166 | 99.94 | 92.11 | 93.2 |

## Interpretation and limitations

- Peer-entry fraction is per recorded range frame, not radio packet-delivery probability. Keep the two directed peer streams separate.
- Paired raw/ranges frames are compared by exact header stamp with a 1e-7m distance tolerance. Boundary-only unmatched frames are subscriber start/stop effects, not proof of link loss.
- Header and device times must be inspected separately from bag receipt time. Receipt gaps and negative receive-minus-header values do not identify RF outages or a calibrated clock delay.
- quality=NaN means unknown by driver design. It is not a measured confidence score.
- Odometry and recorded command phases verify feedback/controller evidence only. They are not independent room coordinates, distances, or trajectory ground truth.
- Car2 odom position.z must not be interpreted as physical antenna height.
- Requested /tf and /tf_static may have no actual messages; explicit frame/marker-to-antenna alignment is still required.
- /rosout can contain latched historical INFO messages with out-of-order stamps from different publishers.
- T10/T11 are about 57s and do not provide a 20s static lead-in, although their recorded actions are complete.
- Occlusion effect, camera calibration/extrinsics, video-to-bag synchronization, and final localization accuracy remain separate acceptance gates.

## Failures

None.

## Observations requiring review

None from the automated continuity checks.

## Reproduce

Run the repository's sandbox role runbook, or:

```bash
python3 tools/field_20261024_25/audit_bags.py --data-root "$DATA_ROOT" --output "$OUTPUT_ROOT/bag_qc"
```

Requires Python 3.8+ and numpy; no ROS/hardware/network access. The output directory must be empty unless --overwrite is supplied.
Machine-readable provenance, input hashes, topic schemas/counts, raw-packet checks, pairing, timing and command/odom summaries are in bag_qc.json.
