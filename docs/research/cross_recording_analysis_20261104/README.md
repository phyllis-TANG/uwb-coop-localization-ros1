# Cross-recording analysis, 2026-11-04

This review package implements the three agreed tasks: qualify the historical
recordings; measure recording influence and static error components; prepare
figures from the resulting evidence. It does not replace the live manuscript.

## Reproduce

Python 3 with NumPy and Matplotlib for analysis. Regenerating the review PDF
additionally requires ReportLab; the report font is included under `assets/`.
FontTools is needed only to rebuild that subset from an original Noto font.

```bash
python analyze.py
python verify.py
python make_report.py
```

The portable `sources/` directory contains the actual analysis inputs. In the
original checkout, `python analyze.py --collect-sources` rebuilds the E3 matched
epoch table from the PR95 trajectory readback. `E3_trajectory_provenance.json`
records all 40 original trajectory/summary file hashes. The numeric source
manifest is written to `results/SOURCE_MANIFEST.json`.

## Outputs

- `results/recording_eligibility_116.csv`: every row of the original register,
  with a current metric qualification and an explicit next action. PR95 closes
  the old missing-trajectory item for E3 and the incomplete E4 stop results.
- `results/E3_error_decomposition_240.csv`: per recording/profile/phase/robot/
  estimator MSE, squared mean error, and centered within-window spread.
- `results/E3_C_decomposition_80.csv`: the same empirical decomposition of C.
- `results/E3_T_leave_one_out.csv`: 12 phase/robot/method group contrasts.
- `results/E3_leave_one_out_all_80.csv`: every actual omission, including all
  normal, human-operation and recovery cases. These scopes overlap in original
  recordings and are not extra independent acquisitions.
- `results/E2_common_stop_MSE_36.csv`: three historical recordings, three
  calibration profiles, two robots and two methods. Each uses the original five
  endpoint states, with an epoch-wise MSE instead of squaring the median endpoint
  difference. Original median endpoint differences reproduce exactly.
- `results/E2_calibration_contrasts_12.csv`: both historical correction profiles
  against raw data for every recording and robot; no result-based omissions.
- Three vector PDF / PNG figure pairs and the four-page Chinese review PDF.

## Statistical and estimator identities

Negative D means cooperation reduces measured-reference MSE. Positive C means
correction reduces the relative cooperative advantage. T = mean(C in B) minus
mean(C in A); there is no per-recording T without an explicit A/B pairing.

MSE = squared mean error + centered within-window spread, using divisor N. This
is a finite-window identity relative to a measured reference, not a population
estimator bias/variance theorem. Leave-one-out ranges are sensitivity ranges,
not confidence intervals. Reference uncertainty is not inferred from them.

E2 sources are pinned to repository HEAD 228be4e1c7a4234dc7e91538f4c304231463756f
(same historical content used by draft source d39b284e2a1dd84a322a359187a4e4b926a56e62).
They are full-recording batch estimates with the archived body-frame mounts and
Odom initialization. E3 is the dedicated static antenna-frame fixed-lag model
and initializes each raw/corrected profile separately. Shared metric formulas
do not establish identical estimator configurations. Their results are not
pooled, and the analysis is not an estimator refit or a new causal replay.

The aggregate historical input files can support the old batch calculation.
They cannot alone reproduce the current receipt-ordered fixed-lag front end,
including late-data handling, odometry freshness and closed-bin availability.
An exact unified replay must use raw message receipt events and a separately
recorded dynamic-frame adapter/configuration. The static confirmation adapter
explicitly refuses moving odometry and must not be reused for E2 motion.

## Time and acquisition units

The verified E3 normal windows contain 150 unique recording-seconds; all phases
contain 375. Saved trajectory spans sum to 2498 seconds, while the first-to-last
saved timestamps span approximately 3848 seconds. These describe different
quantities and are not the total historical raw-bag duration. Placement A was
collected before B, so the chronology figure does not isolate a temporal effect.
The repository-wide 2-4 hour estimate remains unverified.

The early three E2 recordings share a date; they are not three independent
cross-day calibration sessions. E3 records also share placement references and
the inherited calibration. Calibration-source recordings, development runs,
interrupted attempts, simulation records and protected holdouts keep their
original identities in the inventory.

## Figure selection

Use the chronology as a cross-recording diagnostic, with every observation
shown. Use the mean-offset/spread plot to explain the static result; the log
ordinate makes the small spread component visible. The historical C plot is
an extension across movement conditions, with its batch identity stated.
These are candidate figures for review; adding all three to the 8-page paper
would duplicate existing result displays. No cross-session boxplot is claimed
until comparable sessions and actual per-session sampling units are established.

## Remaining data work

1. Exact E2/E4 raw/corrected fixed-lag replay: original bags/receipt streams,
   compatible dynamic-frame adapter, frozen geometry/initialization, and
   common measured-stop windows. This package completes archived-trajectory
   remeasurement, not that new estimator experiment.
2. Four Oct18 static XY candidates (B056/B062/B065/B066): preserve B062's
   calibration-source role and B056's shared endpoint reference. Audit raw bags
   before claiming additional independent positions or sessions.
3. Oct24-25 candidates: retain protected holdout status and check the exact
   reference, stop interval, mount and timing provenance recorded per row.
4. Confirm actual raw-bag durations from metadata before publishing an hours
   claim. None of the above requires changing already measured outcomes.
