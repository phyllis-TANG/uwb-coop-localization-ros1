"""Truth is used here only after all online estimates have been produced."""
import numpy as np
from protocol import CARS


def recovery(times, values, baseline, end, excess, dwell):
    good = values <= baseline+excess
    start = int(np.searchsorted(times, end))
    for i in range(start, len(times)):
        j = int(np.searchsorted(times, times[i]+dwell, side="left"))
        if j < len(times) and np.all(good[i:j+1]):
            return float(times[i]-end)
    return None


def metrics(config, trial_id, scenario, source, seed, times, truth, estimates, diagnostics):
    errors = {m: np.linalg.norm(x-truth[:, :, :2], axis=2) for m, x in estimates.items()}
    rows = []
    for method, err in errors.items():
        for i, car in enumerate(CARS):
            for phase, mask in [("all", np.ones(len(times), dtype=bool)),
                                ("fault", (times >= config["fault_start_s"]) & (times < config["fault_end_s"])),
                                ("recovery", times >= config["fault_end_s"])]:
                e = err[mask, i]
                base = errors["independent"][mask, i]
                shift = np.linalg.norm(estimates[method][mask, i]-estimates["independent"][mask, i], axis=1)
                rows.append({"trial_id": trial_id, "scenario": scenario, "seed": seed, "source_car": source,
                             "method_id": method, "vehicle_id": car, "role": "source" if source == car else "other",
                             "phase": phase, "n": len(e), "rmse_m": float(np.sqrt(np.mean(e**2))),
                             "p95_m": float(np.quantile(e, .95)), "p99_m": float(np.quantile(e, .99)),
                             "max_m": float(np.max(e)), "error_failure_fraction": float(np.mean(e > config["failure_error_m"])),
                             "any_error_failure": bool(np.any(e > config["failure_error_m"])),
                             "solver_failure_fraction": float(np.mean([not diagnostics[method][k]["solver_success"] for k in np.flatnonzero(mask)])),
                             "excess_rmse_m": float(np.sqrt(np.mean(e**2))-np.sqrt(np.mean(base**2))),
                             "shift_from_independent_max_m": float(np.max(shift)),
                             "recovery_s": None if scenario == "normal" else recovery(times, err[:, i], errors["independent"][:, i],
                                config["fault_end_s"], config["recovery_excess_m"], config["recovery_dwell_s"])})
    return rows


def summarize(rows, config):
    """20 independent seed blocks; mirrors are averaged inside each seed."""
    out = []
    for scenario in config["scenarios"]:
        for method in config["methods"]:
            for role in ("source", "other"):
                for phase in ("all", "fault", "recovery"):
                    group = [r for r in rows if (r["scenario"], r["method_id"], r["role"], r["phase"]) == (scenario, method, role, phase)]
                    if not group:
                        continue
                    entry = {"scenario": scenario, "method_id": method, "role": role, "phase": phase, "runs": len(group)}
                    for name in ("rmse_m", "p95_m", "p99_m", "max_m", "excess_rmse_m", "error_failure_fraction", "solver_failure_fraction"):
                        entry["mean_"+name] = float(np.mean([r[name] for r in group]))
                    entry["runs_with_error_failure"] = sum(r["any_error_failure"] for r in group)
                    rec = [r["recovery_s"] for r in group if r["recovery_s"] is not None]
                    entry["recovery_censored_runs"] = len(group)-len(rec) if scenario != "normal" else None
                    entry["median_recovery_s"] = float(np.median(rec)) if rec else None
                    out.append(entry)
    paired = []
    for scenario in config["scenarios"]:
        for role in ("source", "other"):
            for comparison in ("fixed", "huber", "no_firewall", "independent"):
                group = [r for r in rows if r["scenario"] == scenario and r["role"] == role and r["phase"] == "fault"]
                by = {(r["seed"], r["source_car"], r["method_id"]): r for r in group}
                seeds = sorted({r["seed"] for r in group})
                if not seeds:
                    continue
                deltas = [np.mean([by[s, c, "firewall"]["rmse_m"]-by[s, c, comparison]["rmse_m"] for c in config["source_vehicles"]]) for s in seeds]
                boot_rng = np.random.default_rng(731)
                boot = np.mean(boot_rng.choice(deltas, size=(4000, len(deltas)), replace=True), axis=1)
                paired.append({"scenario": scenario, "role": role, "comparison": "firewall_minus_"+comparison,
                               "seed_blocks": len(seeds), "mean_delta_rmse_m": float(np.mean(deltas)),
                               "seed_bootstrap_ci95_m": np.quantile(boot, [.025, .975]).tolist(),
                               "improved_seed_blocks": int(sum(d < 0 for d in deltas))})
    return {"schema_version": 1, "scope": "synthetic_only", "aggregates": out, "paired": paired,
            "uncertainty": "seed-block bootstrap; 4000 resamples; mirrors averaged inside seed; no multiple-comparison correction"}
