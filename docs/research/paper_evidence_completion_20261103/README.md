# Local evidence completion for the November 3 paper outline

This package fills the saved-output gaps listed in section 10 of the supplied `UWB_Paper_Outline_and_Evidence_Audit_v1.docx`. Start with `GAP_AUDIT.md`, then `verification/REPORT.json`. It includes the supplied outline as text, original saved results, all requested static and dynamic estimated trajectories, their configurations, stop references, and portable numerical readback. The original Word and ZIP remain local source artifacts; this is an accompanying evidence PR, not the other environment's unpushed commit `228be4e1`.

## Results now accessible

| Need in the outline | Delivered files | Status |
|---|---|---|
| A2/B2 full frozen results | `dynamic/reserved/RESERVED_RESULTS.json`, `PROTOCOL.json`, `FINAL_LOCK.json`, `REFERENCES.json`, original result text | Available; all 16 stop/car rows independently recomputed |
| Static trajectories and common times | `static/runs/`, `verification/static_common_times.json` | All 10 confirmation bags, both profiles, I/J/W025; 160 paired rows recomputed |
| A1/B1 and A2/B2 dynamic trajectories | `dynamic/runs/`, `references/`, `verification/dynamic_common_times.json` | 15 method trajectories over 5 file/initialization units; all 32 stop/car rows recomputed |
| Scene and hardware binding | `setup/`, saved per-run configurations, `GAP_AUDIT.md` | Anchor coordinates, reference points and adopted offsets available; model identification and precise odom-frame mounting remain partly unresolved |

The expanded static statistics in the supplied audit also pass independent readback from saved trajectories: all 20 scope/car/method interaction rows reproduce, including the all-ten-normal scope and both recovery inclusion rules. This is post-hoc reuse of exposed observations. Windows within the same bag are not independent new experiments.

## Plotting inputs

- `verification/static_main_40_rows.json`: five N bags × two cars × two profiles × I/J, with MSE, average estimated antenna XY, reference XY and common count.
- `verification/static_plot_rows.json`: all phases and I/J/W025 for the ten confirmation bags.
- `verification/static_pair_rows.json`: D and reference sensitivity per run/profile/phase/car/arm.
- `verification/static_scope_20_readback.json`: five scope definitions and their C/T summaries checked against the supplied audit.
- `verification/dynamic_all_32_stop_rows.json`: all A1/B1/A2/B2 stop/car comparisons, including B2 prefix and continuation, stable windows, reference coordinates, mean antenna positions and validity counts.
- Raw saved *estimated* paths are in `static/runs/` and `dynamic/runs/`. They are not ground-truth paths. Preserve invalid/warmup states in coverage and do not connect B2 prefix to continuation as one uninterrupted estimate.

Dynamic `pose` is `[x1,y1,yaw1,gyro_bias1,x2,y2,yaw2,gyro_bias2]` in the adopted body frame. Convert to antenna XY with each run's `models.<car>.base_to_antenna_body_xy_m` and yaw before comparing to references. Static poses use three entries per car, with antenna XY already in the first two positions. Static and dynamic estimators are distinct implementations/configurations; static I/J/W025 has no subsequently added gyro factor.

Use integer nanoseconds. The exported common-time files use decimal strings to avoid JavaScript's integer precision limit; original saved trajectory JSON retains its original integer representation. Python's JSON parser preserves these integers. `cutoff_ns` is a receipt-based cutoff, not proof of hardware synchronization.

## Reproduce this verification

From this directory, run `python verify_bundle.py` (Python standard library only). The script checks transferred source-file identities, aligned timelines, original validity masks, MSE/RMSE, means, dynamic median/p95, paired differences and conditional reference intervals. It checks the static profile intersections and the supplied audit's 20 scope comparisons. No raw bags, optimizer, ROS, external Python packages or local absolute source paths are required.

The numerical tolerance is 1e-10. The checked maximum absolute discrepancy is recorded in `verification/REPORT.json`. JSON source files were whitespace-compacted with values preserved. `SOURCE_MANIFEST.json` records original and transferred hashes; `DELIVERY_SHA256.json` covers the complete PR package including the generated verification files.

Original evaluation scripts are retained as provenance and may depend on the original Windows paths. Use `verify_bundle.py` for portable readback. The older `RESULT_READBACK.json` is an earlier receipt; `verification/REPORT.json` is the new check. The incoming outline's statement that trajectories have not been independently checked describes its earlier audit, superseded for these specific saved outputs by this PR.

## Evaluation meaning

Reference uncertainty is the operator's 1–2 cm estimate, conservatively modeled here by a ball of radius sqrt(2) × 0.02 m. These are conditional sensitivity envelopes, not confidence intervals or certified risk bounds. A1/B1 are development data; A2/B2 were frozen for the original three configurations and are now exposed for any new hypothesis. B2 has a technical interruption and fresh initialization. In B2 continuation, B is an initialization stop, not a post-motion recovery endpoint. Retain the B1 W025 large error and all originally reported failures.

The wider manuscript can use historical single-/dual-car evidence as described in the supplied outline, but this PR does not independently revalidate all 116 inventory records or all historical estimator versions. The remaining work is manuscript integration, hardware/source clarification where explicitly marked, and model/literature alignment. No new field collection is implied by this transfer.
