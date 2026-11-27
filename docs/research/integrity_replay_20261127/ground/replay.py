"""Run the terrestrial analysis code with a local copy of the simulation extension archive."""
import argparse
import csv
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
MEMBER_ROOT = "UWB_Simulation_Extension_Replay"
SCENES = ("nominal", "wall", "peer_step", "peer_ramp")
SEEDS = (2026111901, 2026111902)


def unpack_selected(archive, root, names):
    for name in sorted(names):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(f"{MEMBER_ROOT}/{name}") as src, target.open("wb") as dst:
            shutil.copyfileobj(src, dst)


def run(root, program, *args):
    env = {**os.environ, "OMP_NUM_THREADS":"1", "OPENBLAS_NUM_THREADS":"1",
           "MKL_NUM_THREADS":"1", "PYTHONDONTWRITEBYTECODE":"1"}
    result = subprocess.run([sys.executable, str(root / program), *map(str, args)],
                            cwd=root, env=env, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"{program} failed:\n{result.stderr}")


def table(path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def collect(root, studies):
    results = {}
    if "age" in studies:
        run(root, "age/run.py", "--inputs", root/"age/inputs", "--out", root/"age/results")
        for name in ("full_clock", "late_age", "two_seconds"):
            results["age_" + name] = table(root / f"age/results/{name}.csv")
    if "gyro" in studies:
        run(root, "gyro/replay.py")
        for name in ("ground_summary", "controlled_motion"):
            results["gyro_" + name] = table(root / f"gyro/results/{name}.csv")
    if "anchor" in studies:
        run(root,"anchor/check_anchor.py")
        run(root,"anchor/verify_target.py")
        results["anchor_target"] = table(root / "anchor/target.csv")
        results["anchor_bounds"] = table(root / "anchor/bounds.csv")
    return results


def experiment(archive_path, studies):
    names = set()
    if "age" in studies or "gyro" in studies:
        names.update(f"age/inputs/{seed}_{scenario}_{kind}.npz" for seed in SEEDS
                     for scenario in SCENES for kind in ("sources","truth"))
    if "gyro" in studies:
        names.update(f"gyro/inputs/wheel_{seed}.npz" for seed in SEEDS)
        names.add("gyro/inputs/trajectory_template.json")
    if "anchor" in studies:
        names.add("anchor/observation.json")
    with TemporaryDirectory(prefix="uwb_ground_") as temp:
        root = Path(temp)
        for study in studies:
            shutil.copytree(HERE / study, root / study)
        with ZipFile(archive_path) as archive:
            unpack_selected(archive,root,names)
        return collect(root,studies)


def print_summary(tables):
    for r in tables.get("age_full_clock", []):
        if r["policy"] in ("continuous","phase0"):
            print("Age",r["policy"],r["method"],f"Robot {r['robot']}",f"50 cm time available {float(r['avail_50_pct']):.2f}%")
    for r in tables.get("gyro_ground_summary", []):
        if r["motion_group"]=="all":
            print("Gyro",r["profile"],f"Robot {r['robot']}",f"50 cm time available {float(r['available_at_50cm_pct']):.2f}%")
    for r in tables.get("anchor_target",[]):
        print("Anchor",f"{r['anchor_offset_cm']} cm",f"Robot {r['robot']}",r["decision_at_20cm"])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-archive",type=Path,required=True)
    parser.add_argument("--study",choices=("all","age","gyro","anchor"),default="all")
    parser.add_argument("--out",type=Path,help="Optional local directory for aggregate result tables")
    args=parser.parse_args()
    studies = ("age","gyro","anchor") if args.study=="all" else (args.study,)
    results=experiment(args.local_archive,studies)
    print_summary(results)
    if args.out:
        args.out.mkdir(parents=True,exist_ok=True)
        for name, rows in results.items():
            with (args.out / (name+".csv")).open("w",newline="") as f:
                writer = csv.DictWriter(f,fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)


if __name__=="__main__":
    main()
