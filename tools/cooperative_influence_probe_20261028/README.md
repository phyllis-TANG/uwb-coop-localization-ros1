# Minimal cooperative influence-control development

Read the owned docs `REPORT.md`, `METHODS.md`, `FROZEN_CONFIG.json`, and `RUN_INDEX.json`. This is a two-case, single exposed-seed development check, not a validated protection algorithm.

- `bindings.py` locks unchanged F0 + gate imports. No IMU or shared source edits.
- `core.py` uses a private G0 reference from startup, full joint prior, fixed peer weighting, and actual nonlinear antenna-XY constraints. `replay_control.py` uses the original receive frontend.
- `prepare.py` verifies the exact PR70 revision/input/baseline identities; no regeneration.
- `run_development.py` freezes exactly 16 cells: four reused baselines, four output-clipping derivations, eight new main graphs (each has its own private reference). No retry/overwrite or extra methods.
- `test_contract.py`, `test_index.py` cover implementation, failure semantics, prefix, history, and the symmetric one-dimensional clipping-equivalence boundary.
- `independent.py`, `evaluate.py` read full saved objectives, priors, reference states, and published antenna budgets without importing online solver/Jacobian code.
- `present.py` generates all-case tables/figures from saved results only.

Execution commit is `312180ef51c6ea4ba394bc85618674ec36ff786d`; later reader/documentation commits do not change that identity. Each new run has a separate reference graph; include its cost. `accepted_graph` describes the actual publication, while `main_accepted_graph` and `main_pose` retain internal graph results. Clipping/fallback never feeds back into the main graph. Covariance is null for all controlled outputs.

Used environment: Python3.10.12, NumPy2.2.6, SciPy1.15.3, Matplotlib3.10.9, single BLAS/OMP thread. The original contract test fixture uses the recorded external task path; the independent artifact reader is relocatable via `--root` and `--output`. Matrix paths are immutable; do not rerun because the final delivery HEAD differs from the execution commit.
