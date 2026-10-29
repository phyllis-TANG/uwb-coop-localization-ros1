# Minimal scalar peer DCS comparison

This directory owns the DCS adapter and artifact-only readers. No shared kernel is edited. See ../../docs/field_tests/20261024_25/cooperative_dcs_probe_20261028/REPORT.md and FORMULA_MAP.md.

- `source_lock.json`: exact unchanged F0 + PR68 gate dependencies; `scipy_lock.json`: version/function-file identity needed by the deliberate IRLS curvature adapter.
- `kernel.py`: scalar DCS replaces the peer pseudo-Huber; original nonpeer terms and TRF remain. `replay_dcs.py` wraps the unchanged arrival frontend.
- `prepare.py`: verifies/copies 27 matched baselines and nine input bundles; no estimator execution.
- `run_matrix.py`: commit/test guards, immutable 36-cell plan, exactly nine new runs, no resume/retry/overwrite.
- `independent.py`, `evaluate.py`: scalar independent equations and all-record FD/objective/factor/prior readback; no solver imports.
- `present.py`: tables and all-seed synchronized figures from saved evidence.
- `pack.py`: immutable Git-external evidence package; no network writes.

Execution commit is 19f1bbaa42d6631cc3c2d8660953d13a17ae76de. Later reader/documentation commits do not change completed experiment provenance. Do not rerun the matrix merely because delivery HEAD has changed. Use the archive's frozen execution source if reconstructing an authorized new version; original result paths deliberately refuse overwrite.

Dependencies used: Python 3.10.12, NumPy 2.2.6, SciPy 1.15.3, Matplotlib 3.10.9. BLAS/OMP one thread. Contract tests are 13 test methods; original F0 27 tests are retained. The original contract source uses the absolute task evidence path for its archived-prefix fixture; portable evaluation instead accepts `--matrix` and was separately verified after relocation.

The new DCS loss is a disclosed scalar adaptation with an integrated IRLS-consistent objective, not a reproduction of the paper's full SLAM experiment. Phi=1 was frozen before runs. No calibrated NIS, integrity bound, new gate, IMU, rollback, or field deployment.
