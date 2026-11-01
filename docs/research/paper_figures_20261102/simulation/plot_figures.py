#!/usr/bin/env python3
"""Plot saved, repository-verified results; never run a localization solver."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator, ScalarFormatter
import numpy as np

ROOT = Path(__file__).resolve().parent
BLUE, ORANGE, PURPLE, GREY = "#0072B2", "#D55E00", "#7B3294", "#666666"
T_CRIT_DF3 = 3.182446305284263


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def style():
    plt.rcParams.update({
        "font.family": "STIXGeneral", "mathtext.fontset": "stix",
        "font.size": 9.5, "axes.labelsize": 9.5, "axes.titlesize": 10,
        "xtick.labelsize": 9, "ytick.labelsize": 9,
        "legend.fontsize": 9, "axes.linewidth": .65,
        "lines.linewidth": 1.3, "lines.markersize": 4,
        "xtick.direction": "out", "ytick.direction": "out",
        "xtick.major.width": .6, "ytick.major.width": .6,
        "xtick.major.size": 3, "ytick.major.size": 3,
        "axes.facecolor": "white", "figure.facecolor": "white",
        "savefig.facecolor": "white", "pdf.fonttype": 42,
        "ps.fonttype": 42, "svg.fonttype": "none",
    })


def format_axis(ax, nonnegative=False):
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color=".87", linewidth=.45)
    ax.set_axisbelow(True)
    ax.yaxis.set_major_locator(MaxNLocator(nbins=5))
    fmt = ScalarFormatter(useMathText=True)
    fmt.set_powerlimits((-2, 3))
    ax.yaxis.set_major_formatter(fmt)
    if nonnegative:
        ax.set_ylim(bottom=0)


def save(fig, name):
    out = ROOT / "figures"
    out.mkdir(exist_ok=True)
    fig.savefig(out / f"{name}.pdf", metadata={"Creator": "Matplotlib; saved-result plotting only"})
    fig.savefig(out / f"{name}.svg")
    fig.savefig(out / f"{name}.png", dpi=600)
    plt.close(fig)


def verify_pr92(configs, pairs):
    assert len(configs) == 96, "Expected 48 runs x two robot-level metric rows"
    assert len(pairs) == 16
    seeds = sorted({r["seed"] for r in configs})
    assert len(seeds) == 4
    key = lambda r: tuple(r[k] for k in ("seed", "car", "geometry", "processing", "method"))
    index = {key(r): r for r in configs}
    assert len(index) == len(configs), "Duplicate configuration"
    errors = {"D": 0., "C": 0., "T": 0.}
    for r in configs:
        assert r["primary_evaluable"] == "True"
        assert int(r["common_count"]) == 88
        assert int(r["accepted_count"]) == 88
        assert int(r["finite_count"]) == 90
        assert int(r["failed_count"]) == 0
    for r in pairs:
        c = {}
        for g in ("G1", "G2"):
            mse = lambda p, m: float(index[(r["seed"], r["car"], g, p, m)]["MSE_common_m2"])
            d = {p: mse(p, r["method"]) - mse(p, "M2") for p in ("raw", "historical")}
            for p in d:
                errors["D"] = max(errors["D"], abs(d[p] - float(r[f"D_{g}_{p}"])))
            c[g] = d["historical"] - d["raw"]
            errors["C"] = max(errors["C"], abs(c[g] - float(r[f"C_{g}"])))
        errors["T"] = max(errors["T"], abs(c["G2"] - c["G1"] - float(r["T_m2"])))
    assert max(errors.values()) < 1e-12
    summaries = []
    for car in ("car1", "car2"):
        for method in ("M3", "M3W025"):
            a = np.array([float(r["T_m2"]) for r in pairs if r["car"] == car and r["method"] == method])
            mean = float(a.mean())
            half = float(T_CRIT_DF3 * a.std(ddof=1) / np.sqrt(len(a)))
            summaries.append(dict(robot=car, method=method, n=4, mean_T_m2=mean,
                                  descriptive_t95_m2=[mean-half, mean+half], signs=np.sign(a).astype(int).tolist()))
    masks = json.loads((ROOT / "data/pr92_common_masks.json").read_text())
    return index, seeds, dict(status="PASS", scope="Saved configuration-level MSE arithmetic, not trajectory reprocessing",
                             configuration_rows=96, interaction_rows=16, max_abs_errors_m2=errors,
                             summaries=summaries, common_mask_records=len(masks))


def paired_main(index, seeds):
    fig, axes = plt.subplots(2, 2, figsize=(7.16, 5.05))
    fig.subplots_adjust(left=.095, right=.985, bottom=.16, top=.86, wspace=.35, hspace=.65)
    fig.suptitle("Calibration and placement effects: controlled simulation", y=.99, fontsize=10.5)
    handles = [Line2D([], [], color=BLUE, marker="o", label="Independent (M2)"),
               Line2D([], [], color=ORANGE, marker="s", linestyle="--", label="Cooperative (M3)"),
               Line2D([], [], color=PURPLE, marker="D", label="Paired effect D")]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(.53, .956), ncol=3,
               frameon=False, handlelength=1.8, columnspacing=1.1)
    offsets = np.linspace(-.075, .075, len(seeds))
    for row, car in enumerate(("car1", "car2")):
        left, right = axes[row]
        left.set_title(f"({'ac'[row]}) Robot {row+1}: absolute error", pad=10)
        right.set_title(f"({'bd'[row]}) Robot {row+1}: relative effect", pad=10)
        for g, xs in (("G1", np.array([0., 1.])), ("G2", np.array([3., 4.]))):
            for method, colour, marker, ls in (("M2", BLUE, "o", "-"), ("M3", ORANGE, "s", "--")):
                ys = []
                for k, seed in enumerate(seeds):
                    y = [float(index[(seed, car, g, p, method)]["MSE_common_m2"]) for p in ("raw", "historical")]
                    ys.append(y)
                    left.plot(xs+offsets[k], y, color=colour, marker=marker, markersize=2.8,
                              linewidth=.6, linestyle=ls, alpha=.4)
                left.plot(xs, np.mean(ys, axis=0), color=colour, marker=marker, markersize=4.5,
                          linewidth=1.5, linestyle=ls, zorder=5)
            effects = []
            for k, seed in enumerate(seeds):
                y = [float(index[(seed, car, g, p, "M3")]["MSE_common_m2"])
                     - float(index[(seed, car, g, p, "M2")]["MSE_common_m2"])
                     for p in ("raw", "historical")]
                effects.append(y)
                right.plot(xs+offsets[k], y, color=PURPLE, marker="D", markersize=2.8,
                           linewidth=.6, alpha=.4)
            right.plot(xs, np.mean(effects, axis=0), color=PURPLE, marker="D", markersize=4.5,
                       linewidth=1.5, zorder=5)
        for ax in (left, right):
            ax.set_xlim(-.38, 4.38)
            ax.set_xticks([0, 1, 3, 4], ["Raw", "Corrected", "Raw", "Corrected"])
            ax.text(.5, -.25, "G1", ha="center", va="top", transform=ax.get_xaxis_transform())
            ax.text(3.5, -.25, "G2", ha="center", va="top", transform=ax.get_xaxis_transform())
            format_axis(ax, nonnegative=(ax is left))
        left.set_ylabel(r"Position MSE (m$^2$)")
        right.set_ylabel(r"$D$ (m$^2$)")
        right.axhline(0, color=".15", linewidth=.7, zorder=1)
    fig.text(.5, .016, "Thin lines: four paired seeds. Bold lines: means. Common accepted epochs: 88/90 per seed.",
             ha="center", va="bottom", fontsize=9)
    save(fig, "pr92_paired_main_ieee")


def field_summary(rows):
    fig, axes = plt.subplots(1, 2, figsize=(7.16, 2.65), sharex=True, sharey=True)
    fig.subplots_adjust(left=.18, right=.98, top=.78, bottom=.30, wspace=.25)
    fig.suptitle("Exploratory field summary: placement interaction", y=.98, fontsize=10.5)
    all_lo = min(float(r["T_sensitivity_low_m2"]) for r in rows)
    all_hi = max(float(r["T_sensitivity_high_m2"]) for r in rows)
    margin = .08 * (all_hi-all_lo)
    for k, car in enumerate(("Car1", "Car2")):
        ax = axes[k]
        ax.set_title(f"({'ab'[k]}) Robot {k+1}", pad=8)
        for pos, method, colour, marker in ((1, "J", ORANGE, "s"), (0, "W025", GREY, "^")):
            r = next(r for r in rows if r["robot"] == car and r["method"] == method)
            c1, c2, t, lo, hi = [float(r[x]) for x in ("C_G1_m2", "C_G2_m2", "T_m2", "T_sensitivity_low_m2", "T_sensitivity_high_m2")]
            assert abs(c2-c1-t) < 1.1e-6, "Rounded manuscript values do not match"
            assert lo < t < hi
            ax.errorbar(t, pos, xerr=[[t-lo], [hi-t]], color=colour, marker=marker,
                        markersize=5, linewidth=1.2, capsize=3, linestyle="none")
        ax.axvline(0, color=".15", linewidth=.7)
        ax.set_xlim(all_lo-margin, all_hi+margin)
        ax.set_ylim(-.45, 1.45)
        ax.set_yticks([1, 0], ["Full peer (J)", "Reduced peer (W025)"])
        ax.set_xlabel(r"Placement interaction $T$ (m$^2$)")
        ax.xaxis.set_major_locator(MaxNLocator(nbins=4))
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="x", color=".87", linewidth=.45)
        ax.set_axisbelow(True)
    fig.text(.5, .11, "Five static bags: G1 n=2; G2 n=3. Points: manuscript summary values.", ha="center", fontsize=9)
    fig.text(.5, .04, "Whiskers: conditional reference sensitivity (±2 cm per axis), not confidence intervals.", ha="center", fontsize=9)
    save(fig, "field_interaction_summary_ieee")


def main():
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
    style()
    configs = read_csv(ROOT / "data/pr92_per_configuration.csv")
    pairs = read_csv(ROOT / "data/pr92_per_seed_interactions.csv")
    index, seeds, audit = verify_pr92(configs, pairs)
    paired_main(index, seeds)
    field_summary(read_csv(ROOT / "data/field_interaction_summary.csv"))
    audit["static_five_bag_core"] = {"status": "COMPLETED_IN_COMPANION_STATIC_DIRECTORY", "path": "../static/README.md"}
    audit["figure_style"] = {"width_in": 7.16, "font": "STIXGeneral (Times-style serif)",
        "pdf_fonts_embedded": True, "png_dpi": 600, "colour_and_shape_encoding": True,
        "ieee_reference": "General IEEE Author Center graphics guidance, not an IV-specific certification"}
    audit["new_localization_runs"] = 0
    audit["file_sha256"] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in sorted((ROOT / "data").glob("*"))}
    (ROOT / "verification.json").write_text(json.dumps(audit, indent=2)+"\n")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
