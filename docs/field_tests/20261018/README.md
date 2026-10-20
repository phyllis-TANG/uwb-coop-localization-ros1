# 2026-10-18 minimal two-car offline graph comparison

This is an offline diagnostic, not a calibrated localization result. The raw
archive and independent notes stay outside Git and are not modified. The
script reads bags directly from the tar archive, checks their SHA-256 entries
against its `BAG_SHA256SUMS.txt`, and writes the resulting JSON and trajectory
CSV into `results/`. No ROS node, simulator, or vehicle is started.

## Static cross-check before fitting

The independent L-run note places Car1 at antenna `[1.50, 4.00, 0.20]` and
Car2's measured endpoint at `[2.95, 3.04, 0.20]`, with direct antenna-center
tape distance approximately 1.743 m. The straight-run note reuses these XY
coordinates for its start. The separate mount survey corrects Car1 height to
0.17 m; the original notes remain unchanged. This makes the coordinate-derived
3D distance 1.7393 m. In the L bag's stationary 85–94.8 s interval, valid
`node_1 -> node_0` and `node_0 -> node_1` medians are 1.615 m (490 samples)
and 1.643 m (440). In the straight bag's stationary 0–5 s interval they are
1.6165 m (264) and 1.643 m (237). Odom is unchanged within these windows.
The repeated ~1.62/1.64 m reading is therefore an observed discrepancy of
roughly 10–13 cm from the ~1.74 m manual distance, not an optimizer target or
calibration datum. The field user separately confirmed that all four wall
nodes stayed in their October 17 reinstalled positions and that static A's
2.93 m tape measurement was between the antenna centers.

The separate `020151` bag is named for the same `[1.50, 4.00]` /
`[2.95, 3.04]` antenna XY placement. Both planar odom paths are 0 m over
25.00 s. Its valid peer medians are **1.604 m (1251/1256)** for Car1-to-Car2
and **1.631 m (1148/1241)** for the reverse direction. They are 0.139 m and
0.112 m below the 1.743 m tape value recorded in the *L-run note*; `020151`
has no independent tape note in the archive. This is corroborating UWB data,
not a new measured tape reference, and it was not used to fit either graph.

## Model and fixed comparison

`tools/two_car_offline_graph.py` extends the repository's existing single-car
fixed-height SE(2) batch graph structure. At 1 s keyframes it uses the same
start-position prior (0.2 m), heading prior (5°), between-odom uncertainties
(0.03 m and 2° per sqrt(second)), ±0.4 s median range bins, and robust wall
range factors (0.2 m) for both solutions. The joint solution adds one robust
inter-car factor (0.2 m) per keyframe. Available directions are each reduced to
a median and then averaged into this **single** factor. The independent
solution uses the same binned input and reports unused peer residuals as a
diagnostic. No measured endpoint or direct tape value enters optimization.
Both solutions use raw wall and peer ranges without bias in the primary run.
There is no range gate selected using the endpoint.

All sensor streams use ROS bag receipt time for cross-car alignment because
message-header clocks differ. Matching peer messages by nearest bag receipt
within 30 ms produces 3,704 pairs in the L bag and 2,590 in the straight bag;
median absolute receipt-time gaps are 0.58 and 2.78 ms, while median Car2-minus-
Car1 **header** gaps are -29.61 and -65.91 ms. These pairs are not strictly
simultaneous physical observations. A previous both-moving bag had an ~45.6 ms
header gap. The ±0.4 s bins are a modeling choice; shifting Car2 peer receive
times by ±0.1 s is checked separately.

The base state is assumed to be the odom `base_footprint` coincident with the
survey's **approximate chassis geometric center**. The survey's body-frame
antenna offsets `[+0.08, -0.06]` m (Car1) and `[+0.12, -0.08]` m (Car2) are
rotated by estimated yaw; fixed antenna heights are 0.17 and 0.20 m. Each
bag's first keyframed odom pose is translated to initialize its antenna at
the noted start coordinate. Optimization may move it because the start prior
is soft. Approximate initial headings are L: Car1 0°, Car2 +90°;
straight: Car1 -90°, Car2 0°. They represent placement hypotheses, not
surveyed orientations, and were not computed from measured endpoints.
The odom origin-to-chassis-center transform and global heading remain
unverified. The stationary car is allowed to shift under uncertain odom and
wall constraints; this is reported rather than suppressed.

## Primary results: uncorrected wall and peer ranges

End XY coordinates are median antenna positions over the last five keyframes.
Endpoint errors below compare with the *independent manual XY notes*. Direct
tape comparison uses the estimated 3D antenna-to-antenna distance, including
the 0.03 m height difference. The two endpoint references disagree in the
straight bag (coordinates imply 1.5015 m; tape says approximately 1.54 m).

| Bag / method | Car1 end XY m; manual difference | Car2 end XY m; manual difference | End inter-car m; minus tape | Median abs wall residual C1/C2 m | Median abs peer residual m |
| --- | --- | --- | --- | --- | --- |
| L / independent | (1.470, 4.428); 0.429 | (2.714, 3.660); 0.663 | 1.462; -0.281 | 0.147 / 0.335 | 0.172 |
| L / joint | (1.405, 4.433); 0.443 | (2.782, 3.649); 0.631 | 1.585; -0.158 | 0.162 / 0.308 | 0.047 |
| Straight / independent | (1.228, 3.476); 0.543 | (2.768, 3.718); 0.702 | 1.559; +0.019 | 0.163 / 0.175 | 0.058 |
| Straight / joint | (1.242, 3.483); 0.544 | (2.753, 3.713); 0.701 | 1.529; -0.011 | 0.153 / 0.169 | 0.015 |

Complete 1 s antenna and base tracks are in `results/two_car_graph_trajectories.csv`.
In the L bag the independent/joint estimated antenna path lengths are C1
0.126/0.221 m and C2 2.178/2.546 m; in the straight bag they are C1
1.351/1.329 m and C2 0.108/0.134 m. The bag odom paths are exactly 0 m for
the nominally static car and about 2.112 m (L Car2) or 1.013 m (straight
Car1). Estimated stationary-car motion is a model inconsistency to examine,
not physical ground truth. The raw wall fit is particularly poor in the L bag.

## Odom, weighting, and unit audit

Bag nanoseconds are converted to **seconds** once (`ns * 1e-9`); keyframes
are 1 s apart. Odom XY and yaw are interpolated on the *bag receipt-time*
axis. Each odom constraint converts consecutive local-frame XY displacements
to the preceding pose's body frame, then compares them with the estimated
base-to-base body displacement and wrapped yaw change. Its standard deviations
are `0.03 * sqrt(dt_seconds)` m per XY component and
`radians(2) * sqrt(dt_seconds)` for yaw. The start antenna XY prior is 0.2 m
per component; heading is 5°. Wall and peer range scales are each 0.2 m,
with a pseudo-Huber range loss. There are eight wall factors per keyframe,
versus only four total XY start-prior residuals across the two cars. Hence
numerous systematically biased wall observations can overcome the start prior
and small per-step odom deviations. These are inherited exploratory weights,
not calibrated noise estimates.

The optimized first-keyframe antenna is displaced from its manual start by
**0.345/0.854 m** (L independent Car1/Car2), **0.384/0.458 m** (L joint),
**0.653/0.611 m** (straight independent), and **0.625/0.638 m** (straight
joint). For the static car, the RMS error of each estimated odom between-step
translation is only **0.0020/0.0031 m** (L independent/joint) or
**0.0033/0.0037 m** (straight). Accumulated across 92 or 55 steps, this
permits **0.126/0.221 m** and **0.108/0.134 m** antenna path respectively,
despite zero bag odom path. These paths include any antenna movement from
estimated yaw; the corresponding estimated *base* paths are 0.125/0.220 m
and 0.106/0.132 m, so lever-arm rotation is not the main cause.

For straight Car1, keyframe-interpolated odom path is **1.013 m**, whereas
the estimated *base* paths are **1.349/1.327 m** and antenna paths
**1.351/1.329 m**. Estimated between-step translation differs from odom by
RMS **0.0088/0.0084 m** per second, below the 0.03 m factor scale but
accumulating through the trajectory. Estimated net displacement is only
**1.158/1.140 m**; the larger path total also contains small reversals and
lateral adjustments driven by the range factors. There is no seconds-versus-
nanoseconds or body/world rotation error found in this check. The large start
prior displacement and biased wall ranges are more consequential than the
lever arm. These diagnostics explain the optimizer's behavior; they do not
validate the assumed odom-to-chassis transform or the factor weights.

The primary runs have 93 (L) and 56 (straight) keyframes, respectively, with
8 wall factors and **one** peer factor per keyframe. Every keyframe bin had the
required minimum five samples per wall and at least one peer direction. Raw
message coverage is in the JSON: walls are 99.76–100% valid across the two
bags; L Car2 peer is 3830/4729 (80.99%), while straight Car2 peer is
2814/2861 (98.36%). Binning coverage does not imply every raw sample is valid.

## Prespecified sensitivity checks

All sensitivities rerun both independent and joint solutions with the same
changed input; endpoints are still evaluation only. Each entry below gives
**Car1/Car2 manual endpoint XY error; static-car estimated antenna path; end
inter-car distance**, all in meters, for the *joint* run. The complete
independent **and** joint rows, including static net drift, are in
`results/two_car_graph_sensitivity.csv`. “Static-car path” is used to expose
optimizer movement despite zero recorded odom; it is not physical drift.

| Scenario | L: C1/C2 error; static C1 path; distance | Straight: C1/C2 error; static C2 path; distance |
| --- | --- | --- |
| Primary | 0.443/0.631; 0.221; 1.585 | 0.544/0.701; 0.134; 1.529 |
| Moving heading +15° | 0.443/0.633; 0.224; 1.585 | 0.545/0.702; 0.144; 1.529 |
| Moving heading −15° | 0.443/0.630; 0.218; 1.585 | 0.544/0.701; 0.126; 1.529 |
| Static heading +90° | 0.443/0.631; 0.221; 1.585 | 0.544/0.701; 0.134; 1.529 |
| Static heading −90° | 0.443/0.631; 0.221; 1.585 | 0.544/0.701; 0.134; 1.529 |
| Zero lever arms | 0.444/0.630; 0.192; 1.585 | 0.544/0.701; 0.133; 1.529 |
| Odom translation σ = 0.01 m | 0.442/0.634; 0.113; 1.565 | 0.606/0.700; 0.043; 1.512 |
| Start XY prior σ = 0.05 m | 0.443/0.633; 0.485; 1.585 | 0.542/0.700; 0.572; 1.529 |
| Wall range scale = 0.4 m | 0.438/0.623; 0.276; 1.620 | 0.555/0.677; 0.152; 1.523 |
| Peer range scale = 0.4 m | 0.436/0.646; 0.141; 1.527 | 0.544/0.702; 0.116; 1.542 |
| Car2 peer time +0.1 s | 0.443/0.631; 0.221; 1.585 | 0.544/0.702; 0.134; 1.528 |
| Car2 peer time −0.1 s | 0.443/0.631; 0.222; 1.585 | 0.544/0.701; 0.133; 1.529 |
| Static A directional peer offsets | 0.440/0.637; 0.209; 1.561 | 0.546/0.701; 0.130; 1.504 |
| P1 wall correction on **Car2 only** | 0.382/0.183; 0.295; 1.777 | 0.520/0.104; 0.166; 1.600 |

The stronger start prior can *increase* path drift: it holds the start closer
to the manual mark while biased wall factors still pull later states. Smaller
reported separation changes under heading and ±0.1 s time shifts do not
verify the headings or synchronized acquisition. Static A's +0.007/+0.057 m
directional offsets were measured at 2.93 m and are not known to transfer to
the shorter moving runs.

With Car2-only P1 correction, Car2 independent endpoint error drops from
0.663 to 0.092 m (L) and 0.702 to 0.033 m (straight), but independent end
separation becomes 2.103 and 1.747 m. The joint version changes those to
1.777 and 1.600 m; its Car2 endpoint errors rise to 0.183 and 0.104 m.
These are diagnostic results of transferring a P1 correction, not a validated
dynamic correction. The fitted peer residual is necessarily reduced by a peer
factor and is **not independent accuracy evidence**.

There is no continuous trajectory truth, so no trajectory RMSE/ATE or general
accuracy claim is possible. Major unresolved items are the odom-to-chassis
reference transform, surveyed initial headings, manual XY versus tape
disagreement, spatial/temporal wall range bias, and the ~10–13 cm static peer
discrepancy at the shared L-end/straight-start placement.

## Reproduce

Run from the repository root with Python 3, `numpy`, `scipy`, and `rosbags`.
The audited cloud run used numpy 2.3.5, scipy 1.17.0, and rosbags 0.11.7:

```bash
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 python tools/two_car_offline_graph.py \
  --archive /path/to/field_tests_20261018.tar.gz \
  --output docs/field_tests/20261018/results
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 python -m unittest discover \
  -s tools -p test_two_car_offline_graph.py -v
```

The run used archive SHA-256
`c743dc90f3534812fc76073fdc0c594cb0e6cdd33ab82521d8c913fc4c90fcf9`.
`results/two_car_graph_summary.json` records all inputs, per-scenario metrics,
sample coverage, timing diagnostics, odom/prior diagnostics, the separate
`020151` cross-check, and exact bag hashes. The sensitivity CSV contains
every independent/joint scenario in a single reviewable table.
