# Two-car gyro + residual-bias fixed-lag FGO

Base kernel is pinned to `ca8fbac4dbdf678074be5fb80bf6aff472d258e6`; all adaptations live here. Research scope, tolerances, explicit field assumptions and results: [REPORT](../../docs/field_tests/20261024_25/two_car_imu_fgo_20261028/REPORT.md), [MODEL](../../docs/field_tests/20261024_25/two_car_imu_fgo_20261028/MODEL.md), [HANDOFF](../../docs/field_tests/20261024_25/two_car_imu_fgo_20261028/HANDOFF.md).

- M0: exact original independent six-dimensional F0/D0.
- M1: exact original joint six-dimensional F0/D1, existing pseudo-Huber peer.
- M2: eight-dimensional independent F3 (two per-car stopping tests).
- M3: eight-dimensional joint F3, same directed pseudo-Huber peer as M1.

All methods consume identical arrived events/config bytes. No quality controller, gate, rollback, IMU quaternion absolute yaw, or acceleration integration. Missing gyro removes the angular edge and holds prediction yaw; bias random walk remains. M0/M1 have no bias state (JSON null/CSV empty). Joint-frame transaction on solver failure is retained and disclosed; M2 is model/success-solution equivalent to two independent F3 objectives, not a claim of asynchronous failure-publication equivalence.

Python 3.10.12; tested packages listed in requirements.txt. Install only into a separate external environment if needed; no ROS dependency/startup. Set BLAS/OMP threads to 1. All replay/export destinations must be new directories outside Git. `pinned.py` checks original dependency SHAs and scopes legacy absolute imports.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tools/two_car_imu_fgo -p 'test*contract.py' -v
python tools/two_car_imu_fgo/replay.py --events EVENTS.jsonl.gz --config CONFIG.json --method M3 --output NEW_EXTERNAL_DIRECTORY
```

Do **not** restart completed matrices: batch.py/field_batch.py freeze full plans and reject reuse/overwrite. repair.py records exactly four BUG01 repairs; originals remain. new_inputs.py extracts only SHA-bound T08/T10 from the original archive after old-field checks; it does not construct a global solve when required values are missing. These drivers expose actions, not standing authorization for additional experiments.

Saved-evidence verification does not run optimization:

```bash
python tools/two_car_imu_fgo/evaluate.py --matrix EXTRACTED/synthetic-selected-v2 --output NEW_SYNTHETIC_READBACK
python tools/two_car_imu_fgo/evaluate_field.py --matrix EXTRACTED/old-selected-v2 --output NEW_OLD_READBACK
python tools/two_car_imu_fgo/verify_pairs.py --artifacts EXTRACTED --output NEW_PAIR_RECEIPT.json
python tools/two_car_imu_fgo/field_readback.py --bag ORIGINAL_ALLOWLISTED.bag --packets EXTRACTED/old-inputs-v2/015334 --output NEW_RAW_RECEIPT.json
```

`independent.py` is a separate scalar residual/finite-difference/SVD/receipt-support implementation; it imports no online solver or analytic Jacobian. Field readback shares bag envelope traversal, but independently decodes ROS fields using embedded schemas versus rosbags production. `verify_prefix.py` is an explicit online contract control and is not presented as independent. Full unknowns, statuses and denominators are preserved.
