# Monitor-only cooperative integrity baselines

Read `docs/research/cooperative_integrity_baselines_20261029/COMMANDS.md` before running.
Only seed101 nominal / car1_common_wall_bias / peer_bias are allowed. The original
19-file PR68 kernel lock is verified on import; no core files are changed.

`engine.py` wraps the original G1 with three independent source-exclusion graphs.
`influence.py` propagates common primitive sensitivities through each graph's QR
history. `monitors.py` fits only the B1 four-range nuisance XY for a consistency
statistic; it is not another published localization trajectory.
`decisions.py` freezes alarms/engineering availability. No truth enters these.
`evaluate.py` alone reads truth. `independent.py` is a separate scalar/FD reader
with NumPy/stdlib only. `readback.py` reconstructs input in RAM for readout only.

15 contracts plus eight semantic corruption controls passed. Current source has
post-run readout/negative/packaging additions: do not claim it was the unchanged
online execution commit. Full provenance is in RUN_INDEX and SOURCE_AUDIT.

For a fresh controlled run, use a new external output directory, explicit
`run.py --phase pair`, then the exact same frozen source `--phase peer`.
Never overwrite an existing output or regenerate completed results merely to
review them. The lightweight evidence cap is 100MB; no bags/videos are read.
