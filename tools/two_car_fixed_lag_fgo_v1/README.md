# Two-car F0 fixed-lag minimum comparison

See the committed [preregistration](../../docs/field_tests/20261024_25/two_car_fixed_lag_fgo_v1/SPEC.md).
All output directories must be new and outside Git. Run from the repository root:

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
python -m unittest discover -s tools/two_car_fixed_lag_fgo_v1 -p 'test_*.py' -v
python tools/two_car_fixed_lag_fgo_v1/simulate.py --seed 7 --scenario nominal --output /outside/dev-input
python tools/two_car_fixed_lag_fgo_v1/replay.py --events-jsonl /outside/dev-input/events.jsonl.gz \
  --config /outside/dev-input/config.json --arm D1 --output /outside/dev-D1
```

`D0` and `D1` use the same six-dimensional graph and source-pinned single-car
objective. D0 omits peer residuals. D1 adds the prescribed single directed link.
IMU remains an ignored diagnostic event and a reserved future ablation interface.
Both car extrinsics are fixed configuration, not unidentifiable free variables.

Formal `batch.py --output /outside/formal --test-receipt /outside/tests.json`
requires a clean committed checkout and a PASS receipt whose `source_sha256`
equals `io_utils.sources()`. It creates all 24 index entries before execution,
copies execution source, uses seeds 101/211/307 once, and retains failed cells.
There is no resume/retry or result-based seed selection. Input/config hashes are
identical within each D0/D1 pair. `report.py --matrix /outside/formal --output
/outside/report` verifies manifests and evaluates independently saved truth.

The CLI currently refuses field scope and cases without the `synthetic_` prefix.
Historical readiness is documented separately; changing a scope string cannot
authorize a field run. No ROS imports, vehicles or endpoint factors are used.

Output `valid` means the graph solve was accepted; warmup and Odom prediction
fallback remain finite outputs and are reported separately. `peer_factor_used`
means added to the maintained graph (including warmup), not proof that a solver
accepted a correction. `snapshot` records only the active graph at that update;
published poses are immutable and external output history is not estimator cache.
Joint priors preserve complete information and affine offset. Solver failures
leave predicted states; marginal failures roll back the maintained graph and
publish a failed prediction. Missing either Odom bracket invalidates that common
keyframe. Missing peer simply adds no peer factor, including after recovery;
prior correlation from earlier valid peer factors is retained.

All timing is virtual. The wait is one second plus measured update work and an
estimated single-worker queue; IO and transport are not vehicle latency evidence.
