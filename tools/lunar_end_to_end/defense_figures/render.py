"""Render the three 16:9 Moon_1 defense figures using only archived evidence."""

import argparse
import csv
from fractions import Fraction as F
import gzip
import hashlib
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import colors, font_manager, patches
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "docs/research/lunar_end_to_end"
ROUND = DATA / "round2_radius"
OUT = DATA / "defense_figures"
INK, BLUE, ORANGE, GREEN, RED = "#182c39", "#005a81", "#a5440b", "#116859", "#9b2936"
PAPER = "#ffffff"
font = (
    "Times New Roman"
    if any(f.name == "Times New Roman" for f in font_manager.fontManager.ttflist)
    else "Liberation Serif"
)
plt.rcParams.update(
    {
        "font.family": font,
        "font.size": 16,
        "text.color": INK,
        "axes.labelcolor": INK,
        "xtick.color": INK,
        "ytick.color": INK,
        "pdf.fonttype": 42,
        "savefig.facecolor": PAPER,
    }
)


def read(p):
    return json.loads(
        gzip.decompress(p.read_bytes()) if p.suffix == ".gz" else p.read_bytes()
    )


def canvas(title, subtitle):
    fig = plt.figure(figsize=(16, 9), facecolor=PAPER)
    fig.text(0.055, 0.927, title, fontsize=32, weight="bold")
    fig.text(0.056, 0.872, subtitle, fontsize=19)
    return fig


def export(fig, name):
    for ext in ("png", "pdf"):
        fig.savefig(OUT / f"{name}.{ext}", dpi=200)
    plt.close(fig)


def route_map():
    fig = canvas(
        "Moon_1 reconstruction and the four evaluation epochs",
        "Evaluation maps (right): both cars follow one source trajectory. Car 1 samples it 5 s later than Car 2 at each scene time.",
    )
    fig.text(0.055, 0.777, "Historical Isaac Lab replay", fontsize=23, weight="bold")
    src = OUT / "isaac_replay_7s.png"
    im = Image.open(src)
    assert im.size == (1920, 1080)
    ax = fig.add_axes([0.055, 0.295, 0.46, 0.46])
    ax.imshow(im)
    ax.axis("off")
    fig.text(
        0.055,
        0.251,
        "Terrestrial tracks on a LuSNAR display mesh",
        fontsize=19,
        weight="bold",
    )
    fig.text(
        0.055,
        0.206,
        "Kinematic replay with decorative craters.",
        fontsize=16,
        linespacing=1.4,
    )
    ds = [DATA / "continuous", DATA / "replication"]
    grids = [np.load(d / "terrain.npz") for d in ds]
    vmin = min(float(g["terrain"].min()) for g in grids)
    vmax = max(float(g["terrain"].max()) for g in grids)
    palette = colors.LinearSegmentedColormap.from_list(
        "height", ["#ebf5e9", "#99c6ab", "#448575"]
    )
    norm = colors.Normalize(vmin, vmax)
    for d, g, y, title in zip(
        ds, grids, [0.525, 0.155], ["Main segment", "Second segment"]
    ):
        rt = read(d / "ROUTE.json")
        ax = fig.add_axes([0.482, y, 0.478, 0.265])
        low = g["low"]
        step = float(g["res"])
        terrain = g["terrain"]
        mask = g["observed"].astype(bool)
        high = low + step * (np.array(terrain.shape) - 1)
        ext = [
            low[0] - step / 2,
            high[0] + step / 2,
            low[1] - step / 2,
            high[1] + step / 2,
        ]
        rgba = palette(norm(terrain))
        rgba[~mask] = colors.to_rgba("#eb9b78")
        ax.imshow(
            rgba.transpose(1, 0, 2), extent=ext, origin="lower", interpolation="nearest"
        )
        xy = np.asarray(rt["xyz_m"])
        anchors = np.asarray(rt["anchors_xyz_m"])
        ax.scatter(*anchors[:, :2].T, marker="^", s=62, color=INK)
        for k, col in enumerate((BLUE, ORANGE)):
            dense = np.asarray(rt["dense_xyz_m"])[:, k, :2]
            ax.plot(*dense.T, color=col, lw=2.8)
            for index, marker in [(0, "o"), (11, "D")]:
                ax.scatter(
                    *xy[index, k, :2],
                    marker=marker,
                    s=78,
                    color=col,
                    edgecolors="white",
                    linewidths=1,
                    zorder=5,
                )
        ax.set_aspect("equal")
        ax.margins(0.07, 0.15)
        ax.set_ylabel("y (m)", fontsize=15)
        ax.tick_params(labelsize=14)
        if d == ds[1]:
            ax.set_xlabel("moon_map x (m)", fontsize=15)
        ax.yaxis.set_major_locator(MaxNLocator(3, integer=True))
        ax.xaxis.set_major_locator(MaxNLocator(6, integer=True))
        t = rt["times_s"][11]
        ax.set_title(
            f"{title}   |   scene time 0 and {t:.2f} s",
            fontsize=18,
            weight="bold",
            pad=3,
        )
    handles = [
        Line2D([], [], color=c, lw=3, label=f"Car {i+1}")
        for i, c in enumerate((BLUE, ORANGE))
    ]
    handles.extend(
        Line2D([], [], marker=m, ls="", color=INK, label=l)
        for m, l in [("^", "Synthetic anchor"), ("o", "Index 0"), ("D", "Index 11")]
    )
    fig.legend(
        handles=handles,
        loc="lower center",
        bbox_to_anchor=(0.72, 0.013),
        ncol=5,
        frameon=False,
        fontsize=15,
        handlelength=1,
        columnspacing=1,
    )
    cb = fig.colorbar(
        plt.cm.ScalarMappable(norm, palette),
        cax=fig.add_axes([0.057, 0.098, 0.228, 0.016]),
        orientation="horizontal",
    )
    cb.ax.tick_params(labelsize=13)
    fig.text(0.055, 0.142, "Observed grid  ·  terrain z (m)", fontsize=15)
    fig.patches.append(
        patches.Rectangle(
            (0.326, 0.096), 0.025, 0.023, transform=fig.transFigure, facecolor="#eb9b78"
        )
    )
    fig.text(0.36, 0.096, "Filled grid", fontsize=15)
    fig.text(
        0.055,
        0.031,
        "Evaluation uses synthetic ranges and known antenna heights.",
        fontsize=14,
    )
    export(fig, "01_scene")


def verify():
    case = "main_start_normal"
    data = read(ROUND / "witnesses" / f"{case}.json")
    x = read(ROUND / "inputs/zero" / f"{case}.json")["original"]
    assert (
        x["input_hash"]
        == data["input_hash"]
        == hashlib.sha256(
            json.dumps(
                {k: v for k, v in x.items() if k != "input_hash"},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
    )
    assert (
        x["bias_domain"] == ["0", "0"]
        and list(map(F, x["variance"])) == [F(1, 625)] * 9
    )
    old = read(DATA / "radius_resolution/results" / case / "fine_matched.json.gz")
    nodes = {n["id"]: n for n in old["certificate"]["nodes"]}
    w = data["vehicles"]["p"]
    stats = []
    pts = []
    for p in w["points"]:
        coords = list(map(F, p["xy4"]))
        node = nodes[p["leaf"]]
        assert node["kind"] == "INSIDE" and coords == [
            (F(a) + F(b)) / 2 for a, b in node["box"]
        ]
        xyz = [
            coords[2 * i : 2 * i + 2] + [F(x["heights"][car])]
            for i, car in enumerate("ps")
        ]
        links = [
            (v, list(map(F, x["anchors"][f"a{k}"]))) for v in xyz for k in range(4)
        ] + [(xyz[0], xyz[1])]
        terms = []
        for (a, b), (l, h), var in zip(
            links, x["observations"], x["variance"], strict=True
        ):
            assert l == h
            q = sum((u - v) ** 2 for u, v in zip(a, b))
            scale = 10**30
            k = math.isqrt(q.numerator * scale**2 // q.denominator)
            lo = F(k, scale)
            hi = lo if lo**2 == q else F(k + 1, scale)
            y = F(l)
            terms.append(max(abs(lo - y), abs(hi - y)) ** 2 / F(var))
        assert (
            terms == [F(hi) for _, hi in p["terms"]]
            and sum(terms) == F(p["upper"]) <= 26
        )
        pts.append(coords[:2])
        stats.append(sum(terms))
    d2 = sum((u - v) ** 2 for u, v in zip(*pts))
    assert d2 == F(w["distance2"]) and d2 / 4 == F(w["min_radius2"]) > F(1, 100)
    (OUT / "witness_check.json").write_text(
        json.dumps(
            dict(
                case=case,
                car="p",
                status="PASS",
                input_hash=x["input_hash"],
                leaf_ids=[p["leaf"] for p in w["points"]],
                xy4=[p["xy4"] for p in w["points"]],
                statistic_upper_exact=list(map(str, stats)),
                distance_squared_m2_exact=str(d2),
                half_distance_squared_m2_exact=str(d2 / 4),
            ),
            indent=2,
        )
        + "\n"
    )
    return np.array(pts, dtype=float), [float(s) for s in stats], 100 * math.sqrt(d2)


def witness():
    pts, stats, distance = verify()
    fig = canvas(
        "Two feasible positions rule out a 10 cm radius",
        "Main segment  ·  first epoch (scene time 0 s)  ·  Car 1 horizontal antenna position  ·  peer bias fixed at zero",
    )
    mid = pts.mean(axis=0)
    rel = (pts - mid) * 100
    ax = fig.add_axes([0.07, 0.19, 0.45, 0.60])
    for rad, ls, color in [(10, "--", ORANGE), (distance / 2, "-", BLUE)]:
        ax.add_patch(
            patches.Circle((0, 0), rad, fill=False, lw=2.4, ls=ls, color=color)
        )
    ax.plot(*rel.T, color=INK, lw=1.7)
    ax.scatter(*rel.T, s=90, color=BLUE, zorder=5)
    for p, letter in zip(rel, "AB"):
        ax.annotate(
            letter,
            p,
            xytext=(10, 0),
            textcoords="offset points",
            weight="bold",
            fontsize=18,
        )
    ax.plot([-19, -9], [-18, -18], lw=3, color=INK)
    ax.text(-14, -17, "10 cm", ha="center", fontsize=14)
    ax.set(
        xlim=(-21, 21),
        ylim=(-21, 21),
        aspect="equal",
        xlabel="Local x (cm)",
        ylabel="Local y (cm)",
    )
    ax.set_xticks([-20, -10, 0, 10, 20])
    ax.set_yticks([-20, -10, 0, 10, 20])
    ax.tick_params(labelsize=14)
    fig.text(0.08, 0.065, "Local origin: midpoint of A and B in moon_map.", fontsize=15)
    fig.text(
        0.54,
        0.748,
        "Both joint positions pass the nine-range test",
        fontsize=21,
        weight="bold",
    )
    fig.text(
        0.54,
        0.679,
        "Certified upper bounds on the weighted sum of squared residuals",
        fontsize=16,
    )
    # Round upward when displaying an upper bound.
    fig.text(
        0.54,
        0.601,
        f"A   ≤ {math.ceil(stats[0]*1000)/1000:.3f}       B   ≤ {math.ceil(stats[1]*1000)/1000:.3f}       Threshold   26",
        fontsize=19,
    )
    fig.text(
        0.54,
        0.465,
        f"Projected separation: {distance:.2f} cm",
        fontsize=25,
        weight="bold",
    )
    fig.text(
        0.54, 0.375, "A 10 cm circle spans at most 20 cm.", fontsize=22, color=ORANGE
    )
    fig.text(
        0.54,
        0.260,
        f"Any enclosing radius ≥ {math.floor(distance/2*100)/100:.2f} cm",
        fontsize=24,
        weight="bold",
        color=BLUE,
    )
    fig.text(
        0.54,
        0.145,
        "The midpoint gives the smallest circle for these two points.\nMoving the center cannot reduce the required radius.",
        fontsize=16,
        linespacing=1.35,
    )
    export(fig, "02_witness")


def contrast():
    def rows(name):
        with (ROUND / name).open() as f:
            return list(csv.DictReader(f))

    a = rows("attribution.csv")
    m = {(r["case"], r["car"]): r for r in rows("matched.csv")}
    assert len(a) == len(m) == 8 and {(r["case"], r["car"]) for r in a} == set(m)
    fig = canvas(
        "How measurement assumptions change the outer radius",
        "P4 horizontal radius (cm) at the published antenna position  ·  threshold 26  ·  search resolution 0.025 m",
    )
    columns = [
        (0.059, "Segment / epoch"),
        (0.275, "Car"),
        (0.38, "Baseline"),
        (0.52, "Known-zero"),
        (0.70, "Assumed 2 cm"),
        (0.88, "Matched 2 cm"),
    ]
    for x, l in columns:
        fig.text(
            x, 0.763, l, ha="left" if x < 0.1 else "center", fontsize=19, weight="bold"
        )
    for x, l in [
        (0.38, "old ranges · σ = 4 cm"),
        (0.52, "old ranges · σ = 4 cm"),
        (0.70, "old ranges · old fix"),
        (0.88, "new ranges · new fix"),
    ]:
        fig.text(x, 0.725, l, ha="center", fontsize=14)
    for i, r in enumerate(a):
        y = 0.657 - i * 0.054
        if i % 2 == 0:
            fig.add_artist(
                Line2D(
                    [0.055, 0.955],
                    [y + 0.043, y + 0.043],
                    transform=fig.transFigure,
                    color="#66808b",
                    lw=0.8,
                )
            )
        name = r["case"]
        car = r["car"]
        mm = m[name, car]
        label = (
            ("Main" if name.startswith("main") else "Second")
            + " / "
            + ("start" if "_start_" in name else "middle")
        )
        if i % 2 == 0:
            fig.text(0.059, y, label, fontsize=18)
        fig.text(0.275, y, "1" if car == "p" else "2", ha="center", fontsize=17)
        for x, v in [
            (0.38, r["baseline_cm"]),
            (0.52, r["zero_outer_cm"]),
            (0.70, r["tight_outer_cm"]),
            (0.88, mm["outer_cm"]),
        ]:
            invalid = x == 0.70 and float(v) <= 10 and r["tight_truth"] == "NO"
            fig.text(
                x,
                y,
                f"{float(v):.2f}" + (" *" if invalid else ""),
                ha="center",
                fontsize=19,
                color=RED if invalid else INK,
                weight="bold" if invalid else "normal",
            )
    fig.text(
        0.059,
        0.176,
        "* At both starred epochs, the tightened model excludes the true joint position.",
        fontsize=19,
        color=RED,
        weight="bold",
    )
    fig.text(
        0.059,
        0.107,
        "Peer bias: ±0.60 m except in the known-zero column. Matched ranges use the same standardized noise draws at σ = 2 cm.",
        fontsize=16,
    )
    fig.text(
        0.059,
        0.056,
        "These are state-time radii. The 2 cm noise level is a synthetic assumption; real-time availability was not evaluated.",
        fontsize=16,
    )
    export(fig, "03_assumptions")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    panels = {"scene": route_map, "witness": witness, "assumptions": contrast}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("panel", choices=["all", *panels], default="all", nargs="?")
    panel = parser.parse_args().panel
    for name, render in panels.items():
        if panel in ("all", name):
            render()
