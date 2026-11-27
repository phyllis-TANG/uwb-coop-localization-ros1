# Ninety-second two-rover lunar replay

This source-only example constructs two different rover paths on the archived LuSNAR Moon_1 terrain, generates noisy range and odometry observations, and compares three causal integrity monitors. It also repeats three nominal runs with a fixed idealised screen that removes the obstructed range measurements. The screen is a synthetic dropout control. The main terrain has line of sight on all tested links.

## Run locally

Requires Python 3.10 or later, NumPy and SciPy. The reference environment used Python 3.12.14, NumPy 2.3.5 and SciPy 1.17.0. From this example directory, run:

```sh
python run.py --repo-root /path/to/local/project --out /tmp/uwb-lunar-replay --check
```

Choose a new or empty output directory. Add `--jobs 4` to score independent runs in parallel. All reads and writes are local. The checkout must contain these two existing files under `docs/research/lunar_end_to_end/continuous/`. The generator checks their SHA-256 hashes before use.

| Repository file | SHA-256 |
|---|---|
| terrain.npz | 344460e63fb7a7d9d7596bbf66a55523792046b7a24a702e7703830c6150104c |
| CLOUD_SUPPORT.npz | ec37e5be77876350d2e71b04237502b7ed8a2c0773066617178e8a43e0b2b137 |

LuSNAR supplies the synthetic LiDAR data. The 90-second paths are constructed trajectories. The study uses the 0.4 m archived height grid and its observed-node mask. The generator verifies the grid against the registered point returns and checks terrain support along both paths and the ranging lines. Cite Jiayi Liu and colleagues, *LuSNAR: A Lunar Segmentation, Navigation and Reconstruction Dataset Based on Multisensor for Autonomous Exploration*, arXiv:2407.06512. The code includes its MIT license notice.

## Experiments and outputs

- **Main study.** Two anchor layouts, three paired noise draws and two fault conditions give 12 runs at 1 Hz, with 91 joint measurement epochs per run. The peer bias first reaches 2 cm at 30 s, reaches 30 cm at 44 s, stays at this level through 59 s and is removed at 60 s. The monitors receive shared noisy observations and a noisy position prior. The scorer loads the reference after estimation.
- **Screen study.** A fixed opaque box intersects two anchor links in the surrounding-anchor layout. For three nominal replays, it removes 24 of the 819 range values per run across 22 epochs at 33–54 s. All other inputs match the paired unobstructed run. `screen_blocked_epochs` is the affected subset of `screen_all_epochs`.
- **Output.** `source_coverage.csv` contains counts and medians by rover, method and experiment. Coverage uses only epochs where the method issued a numerical horizontal protection level (HPL). A detector-only pass contributes to the pass count and has no HPL. `primary_inputs/`, `screen_inputs/` and `source_epochs.csv.gz` are generated locally for inspection. Compute times are local measurements and may vary. The check concerns source-epoch results.

Expected HPL counts and exceedances pooled across the two layouts or the three screen controls are shown below. An exceedance is a horizontal error strictly greater than the issued HPL.

| Sample | Epochs per rover | Selective HPLs issued | Selective exceedances, R1/R2 | Nine-bias HPLs issued | Nine-bias exceedances, R1/R2 |
|---|---:|---:|---:|---:|---:|
| Main | 1,092 | 1,076 | 0 / 0 | 1,035 | 40 / 0 |
| Screen, all epochs | 273 | 273 | 0 / 0 | 205 | 20 / 0 |
| Screen, affected epochs | 66 | 66 | 0 / 0 | 0 | — |

The 40 main-study exceedances comprise one 20-epoch interval repeated in the identical pre-fault portions of a matched nominal/fault pair. These counts describe the specified simulations and do not estimate mission-level rare-event risk.

[20 Hz availability and recovery](CLOCK.md) describes how to re-score the locally generated output over the full display clock.
