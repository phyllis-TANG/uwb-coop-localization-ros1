# 2026-10-17 wall-UWB reinstall and Car2 2D offline pilot

## Setup and references

Four wall nodes were reinstalled and manually remeasured. Their coordinates
are recorded in `session_config.json`. Car2's UWB antenna is node_0 at
approximately 0.20 m height. The automatic L run started at A=(2.00, 2.00,
0.20) m and stopped at manually measured C=(3.03, 2.95, 0.20) m. There is no
continuous trajectory ground truth. Initial heading and antenna-to-base
lever arm were not independently measured.

The P1 static bag at A supplies frozen, site-specific per-link range
corrections. These corrections must not be interpreted as intrinsic hardware
biases or assumed valid throughout the room. The original bags remain outside
the Git repository; configured SHA-256 values identify the selected inputs.

## Automatic L: endpoint differences from manual C

| Method | Endpoint difference |
| --- | ---: |
| Raw standalone UWB XY | 0.5128 m |
| Corrected standalone UWB XY | 0.0782 m |
| Start-aligned wheel Odom | 0.0351 m |
| Unfiltered 2D batch graph | 0.0904 m |

A persistent node_10 anomaly occurred near the start: its initial five-second
median was 5.812 m, while surveyed geometry predicted 3.137 m. The 0.60 m
Odom-innovation gate rejected 20 node_10 and 4 node_8 keyframe bins. Its graph
start error was 0.1597 m and displacement-vector error was 0.2411 m, compared
with 0.6028 m and 0.6721 m without a gate. A retrospective manual node_10
mask yielded 0.0847 m and 0.1726 m, respectively. All three graph variants
had approximately 0.0904 m endpoint difference. The manual mask is a
diagnostic intervention, not a deployable detection algorithm.

## Cross-check on 2026-10-11 L runs

The same 0.60 m gate rejected one node_3 bin at 50 s in keyboard_L and no
bins in automatic_L. Keyboard_L standalone XY at 50 s is explicitly missing
(NaN); the graph retains its other ranges and Odom constraints. The gated
keyboard graph changed by 0.0016 m on average and 0.0127 m at most, with
displacement-vector error 0.2666 -> 0.2667 m. Automatic_L was unchanged.
Neither old run gained endpoint accuracy from this gate.

## Interpretation

Endpoint checks alone cannot establish full trajectory accuracy. Odom was
closer to the manually measured endpoint than the graph in the 2026-10-17
run. The gate depends on aligned Odom and could discard good UWB data when
Odom drifts. Anchor survey uncertainty, spatially varying radio error,
approximate initial heading, and an unmeasured lever arm remain limitations.

This is a single-car offline baseline. Do not present it as real-time or
two-car cooperative localization. Next development should replay recorded
bags, preserve diagnostics for rejected links, and then evaluate a two-car
relative-range constraint with independent references.

## Next field session

See the [2026-10-18 eight-hour runbook](../20261018_RUNBOOK.md) for the
single-car recheck, two-car data prerequisites, static/one-moving-car
experiments, and the first offline cooperative-estimation comparison.
